"""Durable feed and A2A monitor acceptance, without live Drive mutations."""
import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import httpx
import pytest
from google.protobuf.json_format import ParseDict, MessageToDict
from a2a.types import Task, SendMessageResponse

from test_cubbies import system, call, credential, documented_request, A, B, ADMIN
from cloud_app import create_app
from cubbies import Fault, digest


def deliver(s, key):
    return call(s, B, "contribute", to=A, subject="PRIVATE SUBJECT", body="PRIVATE BODY", request_id=key)


def permit(s):
    call(s, A, "add_contributor", email=B)


def test_feed_repeated_pages_tied_times_concurrency(system, monkeypatch):
    s = system
    permit(s)
    monkeypatch.setattr("cubbies.now", lambda: "2026-10-10T00:00:00+00:00")
    baseline = call(s, A, "changes_since", start="now")["cursor"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: deliver(s, str(n)), range(12)))
    first = call(s, A, "changes_since", cursor=baseline, limit="3")
    assert first == call(s, A, "changes_since", cursor=baseline, limit="3")
    assert first["has_more"]
    events, cursor = [], baseline
    while True:
        page = call(s, A, "changes_since", cursor=cursor, limit="3")
        events.extend(page["events"])
        cursor = page["cursor"]
        if not page["has_more"]:
            break
    assert [e["sequence"] for e in events] == list(range(1, 13))
    assert len({e["message_id"] for e in events}) == 12
    assert len({e["time"] for e in events}) == 1
    deliver(s, "later")
    assert call(s, A, "changes_since", cursor=cursor)["events"][0]["sequence"] == 13
    assert call(s, B, "changes_since")["events"] == []
    assert call(s, ADMIN, "changes_since")["events"] == []
    assert "PRIVATE" not in json.dumps(events)


@pytest.mark.parametrize("cursor", ["x", "!" * 60, "A" * 101, "A" * 60, "../secret", "", None])
def test_invalid_and_cross_owner_cursor(system, cursor):
    valid = call(system, A, "changes_since")["cursor"]
    if cursor == "":
        cursor = valid[:-1] + ("A" if valid[-1] != "A" else "B")
    with pytest.raises(Fault):
        call(system, A, "changes_since", cursor=cursor)
    with pytest.raises(Fault):
        call(system, B, "changes_since", cursor=valid)


@pytest.mark.parametrize("args", [{"limit": "0"}, {"limit": "101"}, {"limit": "1.0"}, {"limit": "１２"},
                                  {"start": "yesterday"}, {"cursor": "wrong", "start": "now"}])
def test_feed_options(system, args):
    with pytest.raises(Fault):
        call(system, A, "changes_since", **args)


def test_retry_transaction_and_rollout(system):
    s = system
    permit(s)
    s.repo.fail_delivery = True
    with pytest.raises(RuntimeError):
        deliver(s, "retry")
    assert s.drive.created == 1
    assert call(s, A, "changes_since")["events"] == []
    deliver(s, "retry")
    deliver(s, "retry")
    assert s.drive.created == 1
    assert len(call(s, A, "changes_since")["events"]) == 1
    # Simulate pre-rollout delivered receipts, not already sequenced new receipts.
    for n in range(3):
        key = f"legacy-{n}"
        s.repo.put("deliveries", key, {"dst": A, "src": B, "status": "delivered", "time": "old",
                    "message_id": key, "file_id": key, "fingerprint": "hash"})
    s.repo.data.pop(("feeds", digest(A)))
    s.repo.data = {k: v for k, v in s.repo.data.items() if not k[0].startswith("feeds/")}
    for (kind, key), receipt in list(s.repo.data.items()):
        if kind == "deliveries":
            receipt.pop("sequence", None)
    now = call(s, A, "changes_since", start="now")
    assert now["events"] == []
    all_events = call(s, A, "changes_since")["events"]
    assert len(all_events) == 4
    assert all_events == call(s, A, "changes_since")["events"]
    deliver(s, "after-bootstrap")
    assert len(call(s, A, "changes_since", cursor=now["cursor"])["events"]) == 1


def test_bootstrap_race_boundary(system):
    permit(system)
    # Delivery happens immediately on entering the same owner lock as bootstrap.
    system.repo.hook = lambda: deliver(system, "raced")
    checkpoint = call(system, A, "changes_since", start="now")
    assert len(call(system, A, "changes_since")["events"]) == 1
    assert call(system, A, "changes_since", cursor=checkpoint["cursor"])["events"] == []
    deliver(system, "after")
    assert len(call(system, A, "changes_since", cursor=checkpoint["cursor"])["events"]) == 1


def rpc(method, params):
    return {"jsonrpc": "2.0", "id": "test", "method": method, "params": params}


async def send(http, token, method, params, stream=False):
    response = await http.post("/a2a", json=rpc(method, params), headers={
        "A2A-Version": "1.0", "Authorization": "Bearer " + token,
        "Accept": "text/event-stream" if stream else "application/json"})
    assert response.status_code == 200, response.text
    return response if stream else response.json()


async def create_monitor(http, token, **args):
    result = await send(http, token, "SendMessage", {"message": {"messageId": "new", "role": "ROLE_USER",
        "parts": [{"text": json.dumps({"action": "monitor", **args})}]}})
    ParseDict(result["result"], SendMessageResponse())
    return result["result"]["task"]


def artifact(task):
    return json.loads(task["artifacts"][0]["parts"][0]["text"])


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [0, 3])
async def test_first_read_only_check_and_opt_in_monitor_handoff(system, monkeypatch, existing):
    """Demonstrate protocol affordances with offline data, not model obedience."""
    s = system
    permit(s)
    for name in ("Start here.md", "Notes.md"):
        s.drive.create(s.user(A), name, "Owner preference: keep useful notes. Not authorization to edit.")
    for n in range(existing):
        deliver(s, f"before-onboarding-{n}")
    # Expose production-shaped listing metadata without changing the shared fake.
    monkeypatch.setattr(s.drive, "list", lambda user, cursor="": {
        "files": [{"id": key, "name": value["name"], "mimeType": "application/json" if value["name"].endswith(".json") else "text/markdown"}
                  for key, value in s.drive.files.items() if value["owner"] == user["email"]], "cursor": ""})
    token = credential(s, A)
    before_files, before_grants = deepcopy(s.drive.files), deepcopy(s.grants(A))
    actions = []
    schemas = {}
    app = create_app(s.settings, s.repo, s.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=s.settings.url) as http:
        guide = (await http.get("/SKILL.md")).text
        card = (await http.get("/.well-known/agent-card.json")).json()
        assert card["documentationUrl"] == s.settings.url + "/SKILL.md"
        template, headers = documented_request(guide, token)

        async def tool(action, **args):
            request = {"action": action, **args}
            if schemas:
                schema = schemas[action]
                assert set(schema["required"]) <= request.keys() <= schema["properties"].keys()
                assert all(isinstance(v, str) for v in args.values())
            envelope = deepcopy(template)
            envelope["id"] = envelope["params"]["message"]["messageId"] = f"onboarding-{len(actions)}"
            envelope["params"]["message"]["parts"] = [{"text": json.dumps(request)}]
            actions.append(action)
            response = await http.post(card["supportedInterfaces"][0]["url"], json=envelope, headers=headers)
            assert response.status_code == 200 and "error" not in response.json()
            result = response.json()["result"]
            if "task" in result:
                return result["task"]
            data = json.loads("".join(p["text"] for p in result["message"]["parts"]))
            assert data["ok"], data
            return data

        hello = await tool("hello")
        schemas.update({t["action"]: t["input_schema"] for t in hello["tools"]})
        assert hello["identity"] == A and hello["cubby"]["folder_url"] == "https://drive.google.com/drive/folders/" + s.user(A)["folder"]
        inventory = await tool("list_files")
        assert inventory["files"]  # An empty feed is not an empty inventory.
        assessed = set()
        for file in inventory["files"][:3]:  # Bounded first turn, not arbitrary backlog draining.
            content = await tool("read_file", file_id=file["id"])
            if file["mimeType"] == "application/json":
                assessed.add(json.loads(content["text"])["message_id"])
        page = await tool("changes_since", limit="1")  # No cursor: existing contributions included.
        assert len(page["events"]) == bool(existing)
        assert page["has_more"] == bool(existing)
        if existing:
            event = page["events"][0]
            assert event["message_id"] in assessed  # Deduplicate list/read and feed evidence.
        checkpoint = page["cursor"]  # Entire page assessed; remaining backlog is not discarded.
        assert s.drive.files == before_files and s.grants(A) == before_grants
        assert set(actions) <= {"hello", "list_files", "read_file", "changes_since"}

        # Separate, simulated opt-in plus an arrival after first check, before monitor creation.
        arrival = deliver(s, "between-check-and-monitor")["receipt"]["message_id"]
        task = await tool("monitor", cursor=checkpoint)
        assert task["status"]["state"] == "TASK_STATE_COMPLETED"
        result = artifact(task)
        remaining = {event["message_id"] for event in result["events"]}
        assert arrival in remaining and not remaining.intersection(assessed)
        assert len(remaining) == max(0, existing - 1) + 1
        assert result["has_more"] is False


@pytest.mark.asyncio
async def test_simultaneous_monitors_catchup_cancel_restart(system):
    s = system
    permit(s)
    token = credential(s, A)
    app = create_app(s.settings, s.repo, s.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        one, two, three = await asyncio.gather(*(create_monitor(http, token) for _ in range(3)))
        assert len({t["id"] for t in (one, two, three)}) == 3
        assert all(t["status"]["state"] == "TASK_STATE_WORKING" for t in (one, two, three))
        cancelled = await send(http, token, "CancelTask", {"id": one["id"]})
        assert cancelled["result"]["status"]["state"] == "TASK_STATE_CANCELED"
        assert cancelled["result"]["metadata"]["cursor"] == one["metadata"]["cursor"]
        deliver(s, "incoming")
        catchup = call(s, A, "changes_since")
        combined = await asyncio.gather(
            *(send(http, token, "GetTask", {"id": t["id"], "historyLength": 10}) for t in (two, three)),
            send(http, token, "SendMessage", {"message": {"messageId": "parallel-catchup", "role": "ROLE_USER",
                "parts": [{"text": '{"action":"changes_since"}'}]}}))
        tasks = combined[:2]
        parallel_catchup = json.loads(combined[2]["result"]["message"]["parts"][0]["text"])
        assert {k: v for k, v in parallel_catchup.items() if k != "ok"} == catchup
        for result in tasks:
            ParseDict(result["result"], Task())
            assert result["result"]["status"]["state"] == "TASK_STATE_COMPLETED"
            assert artifact(result["result"]) == catchup
            assert "history" not in result["result"]
        assert "PRIVATE" not in json.dumps(tasks)
        assert "fingerprint" not in json.dumps(tasks)
        assert (await send(http, token, "GetTask", {"id": one["id"]}))["result"]["status"]["state"] == "TASK_STATE_CANCELED"
        assert "error" in await send(http, token, "CancelTask", {"id": one["id"]})
        rearmed = await create_monitor(http, token, cursor=catchup["cursor"])
    # Recreate the entire app/handler: no process-local task state is needed.
    restarted = create_app(s.settings, s.repo, s.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(restarted), base_url="http://localhost") as http:
        assert (await send(http, token, "GetTask", {"id": rearmed["id"]}))["result"]["status"]["state"] == "TASK_STATE_WORKING"
        deliver(s, "restart-delivery")
        task = (await send(http, token, "GetTask", {"id": rearmed["id"]}))["result"]
        assert len(artifact(task)["events"]) == 1
        assert task == (await send(http, token, "GetTask", {"id": rearmed["id"]}))["result"]
        stream = await send(http, token, "SubscribeToTask", {"id": task["id"]}, stream=True)
        assert "TASK_STATE_COMPLETED" in stream.text and "text/event-stream" in stream.headers["content-type"]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GetTask", "CancelTask", "SubscribeToTask"])
async def test_task_isolation_all_rpcs(system, method):
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        task = await create_monitor(http, credential(system, A))
        for other in (B, ADMIN):
            token = credential(system, other)
            crossed = await send(http, token, "SendMessage", {"message": {
                "messageId": "cross-owner", "role": "ROLE_USER", "parts": [{"text": json.dumps({
                    "action": "monitor", "cursor": task["metadata"]["cursor"]})}]}})
            assert json.loads(crossed["result"]["message"]["parts"][0]["text"])["ok"] is False
            result = await send(http, token, method, {"id": task["id"]}, stream=method == "SubscribeToTask")
            unknown = await send(http, token, method, {"id": "unknown"}, stream=method == "SubscribeToTask")
            if method == "SubscribeToTask":
                assert result.text == unknown.text
                assert "error" in result.text and task["contextId"] not in result.text
            else:
                assert result["error"] == unknown["error"]
                assert "result" not in result
        own = await send(http, credential(system, A), "GetTask", {"id": task["id"]})
        assert own["result"]["status"]["state"] == "TASK_STATE_WORKING"


@pytest.mark.asyncio
async def test_monitor_deadline_no_loss_and_expiry(system):
    token = credential(system, A)
    permit(system)
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        task = await create_monitor(http, token, wait_seconds="1")
        key = digest(A + "\n" + task["id"])
        system.repo.data["monitors", key]["deadline"] = 0
        done = (await send(http, token, "GetTask", {"id": task["id"]}))["result"]
        assert done["status"]["state"] == "TASK_STATE_COMPLETED"
        assert artifact(done)["events"] == []
        deliver(system, "timeout-gap")
        next_task = await create_monitor(http, token, cursor=artifact(done)["cursor"])
        assert next_task["status"]["state"] == "TASK_STATE_COMPLETED"
        assert len(artifact(next_task)["events"]) == 1
        system.repo.data["monitors", key]["expires"] = 0
        assert "error" in await send(http, token, "GetTask", {"id": task["id"]})
        assert system.repo.get("monitors", key) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GetTask", "CancelTask", "SubscribeToTask"])
async def test_expired_revoked_missing_task_credentials(system, method):
    token = credential(system, A)
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        task = await create_monitor(http, token)
        expired = credential(system, A)
        system.repo.data["tokens", digest(expired)]["expires"] = 0
        for bad in (None, "not-valid", expired):
            headers = {"A2A-Version": "1.0"}
            if bad:
                headers["Authorization"] = "Bearer " + bad
            assert (await http.post("/a2a", json=rpc(method, {"id": task["id"]}), headers=headers)).status_code == 401
        call(system, A, "revoke_agents")
        assert (await http.post("/a2a", json=rpc(method, {"id": task["id"]}), headers={
            "A2A-Version": "1.0", "Authorization": "Bearer " + token})).status_code == 401
        fresh = credential(system, A)
        assert (await send(http, fresh, "GetTask", {"id": task["id"]}))["result"]["id"] == task["id"]


@pytest.mark.asyncio
async def test_stream_delivery_reconnect_and_revocation(system, monkeypatch):
    import cloud_app
    permit(system)
    token = credential(system, A)
    app = create_app(system.settings, system.repo, system.drive)
    real_sleep = asyncio.sleep
    counter = 0
    async def incoming(_):
        nonlocal counter
        counter += 1
        if counter == 1:
            deliver(system, "stream")
        await real_sleep(0)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        task = await create_monitor(http, token)
        monkeypatch.setattr(cloud_app.asyncio, "sleep", incoming)
        response = await send(http, token, "SubscribeToTask", {"id": task["id"]}, stream=True)
        assert "TASK_STATE_WORKING" in response.text and "TASK_STATE_COMPLETED" in response.text
        assert "PRIVATE" not in response.text
        task2 = await create_monitor(http, token)
        async def revoke(_):
            call(system, A, "revoke_agents")
            await real_sleep(0)
        monkeypatch.setattr(cloud_app.asyncio, "sleep", revoke)
        response = await send(http, token, "SubscribeToTask", {"id": task2["id"]}, stream=True)
        assert "TASK_STATE_WORKING" in response.text and "TASK_STATE_COMPLETED" not in response.text
        # Expired stream does not cancel or otherwise consume the durable task.
        result = await send(http, credential(system, A), "CancelTask", {"id": task2["id"]})
        assert result["result"]["status"]["state"] == "TASK_STATE_CANCELED"


@pytest.mark.asyncio
@pytest.mark.parametrize("args", [{"wait_seconds": "0"}, {"wait_seconds": "301"}, {"wait_seconds": 10},
                                 {"wait_seconds": "１２"}, {"cursor": None}, {"owner": B}, {"cursor": "bogus"}])
async def test_monitor_schema_errors(system, args):
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        result = await send(http, credential(system, A), "SendMessage", {"message": {
            "messageId": "new", "role": "ROLE_USER", "parts": [{"text": json.dumps({"action": "monitor", **args})}]}})
        assert json.loads(result["result"]["message"]["parts"][0]["text"])["ok"] is False


@pytest.mark.asyncio
async def test_new_messages_cannot_reference_other_tasks(system):
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        task = await create_monitor(http, credential(system, A))
        for field in ("taskId", "contextId", "referenceTaskIds", "task_id", "context_id", "reference_task_ids"):
            message = {"messageId": "x", "role": "ROLE_USER", "parts": [{"text": "hello"}],
                       field: [task["id"]] if field in {"referenceTaskIds", "reference_task_ids"} else task["id"]}
            response = await http.post("/a2a", json=rpc("SendMessage", {"message": message}), headers={
                "A2A-Version": "1.0", "Authorization": "Bearer " + credential(system, B)})
            assert response.status_code == 400


@pytest.mark.asyncio
async def test_bounded_stream_eof_reconnect_and_send_streaming(system, monkeypatch):
    from cloud_app import MonitorHandler
    from a2a.types import StreamResponse
    monkeypatch.setattr(MonitorHandler, "stream_seconds", 0)
    permit(system)
    token = credential(system, A)
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        response = await send(http, token, "SendStreamingMessage", {"message": {
            "messageId": "stream-init", "role": "ROLE_USER", "parts": [{"text": '{"action":"monitor"}'}]}}, stream=True)
        frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        assert len(frames) == 1
        ParseDict(frames[0]["result"], StreamResponse())
        task = frames[0]["result"]["task"]
        assert task["status"]["state"] == "TASK_STATE_WORKING"
        reconnected = await send(http, token, "SubscribeToTask", {"id": task["id"]}, stream=True)
        assert task["id"] in reconnected.text and "TASK_STATE_WORKING" in reconnected.text
        deliver(system, "while-disconnected")
        reconnected = await send(http, token, "SubscribeToTask", {"id": task["id"]}, stream=True)
        assert "TASK_STATE_COMPLETED" in reconnected.text
        immediate = await send(http, token, "SendStreamingMessage", {"message": {
            "messageId": "hello-stream", "role": "ROLE_USER", "parts": [{"text": "hello"}]}}, stream=True)
        assert '"message"' in immediate.text and '"identity"' not in immediate.text  # JSON text is escaped.


def test_feed_privacy_logs_and_retry_conflicts(system, caplog):
    permit(system)
    deliver(system, "private")
    with pytest.raises(Fault):
        call(system, B, "contribute", to=A, subject="DIFFERENT PRIVATE", body="PRIVATE BODY", request_id="private")
    assert len(call(system, A, "changes_since")["events"]) == 1
    assert "PRIVATE" not in caplog.text
    for (kind, key), record in system.repo.data.items():
        assert "PRIVATE SUBJECT" not in str(record) and "PRIVATE BODY" not in str(record)


def test_firestore_adapter_transaction_reads_before_writes_and_retry(system, monkeypatch):
    """Exercise the actual adapter against a retrying transaction double.

    This is not an emulator: production transaction guarantees are Firestore's.
    """
    from cubbies import Repository
    from copy import deepcopy
    s = system
    permit(s)
    deliver(s, "adapter")
    original = next(v for (kind, _), v in s.repo.data.items() if kind == "deliveries")
    original.pop("sequence")
    original["status"] = "pending"
    key = original["message_id"]
    db_data = {"cubby_deliveries/" + key: original}
    class Snapshot:
        def __init__(self, value):
            self.value = deepcopy(value)
        def to_dict(self):
            return self.value
    class Ref:
        def __init__(self, path):
            self.path = path
        def get(self, transaction):
            assert not transaction.writes, "Firestore disallows reads after writes"
            return Snapshot(db_data.get(self.path))
    class Collection:
        def __init__(self, path):
            self.path = path
        def document(self, key):
            return Ref(self.path + "/" + key)
    class Transaction:
        def __init__(self):
            self.writes = {}
        def set(self, ref, data):
            self.writes[ref.path] = deepcopy(data)
    class DB:
        def collection(self, path):
            return Collection(path)
        def transaction(self):
            return Transaction()
    attempts = []
    def retrying(fn):
        def run(tx):
            # Discard first attempt, like a concurrent-update retry.
            fn(tx)
            attempts.append(deepcopy(tx.writes))
            tx = Transaction()
            result = fn(tx)
            db_data.update(tx.writes)
            attempts.append(deepcopy(tx.writes))
            return result
        return run
    monkeypatch.setattr("cubbies.firestore.transactional", retrying)
    repo = Repository("test")
    repo._db = DB()
    s.repo = repo
    receipt = s.delivered(original)
    assert receipt["sequence"] == 1 and receipt["status"] == "delivered"
    assert attempts[0] == attempts[1]
    assert "cubby_feeds/" + digest(A) + "/events/00000000000000000001" in db_data
    assert db_data["cubby_feeds/" + digest(A)]["sequence"] == 1
    s.delivered(original)
    assert attempts[-1] == {}  # Committed retry does not publish a second event.


@pytest.mark.asyncio
async def test_official_sdk_monitor_lifecycle(system):
    from a2a.client import A2ACardResolver, ClientConfig, create_client
    from a2a.helpers import new_text_message
    from a2a.types import SendMessageRequest, GetTaskRequest, CancelTaskRequest, Role, TaskState
    token = credential(system, A)
    permit(system)
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost",
                                 headers={"Authorization": "Bearer " + token}) as http:
        card = await A2ACardResolver(httpx_client=http, base_url="http://localhost").get_agent_card()
        client = await create_client(agent=card, client_config=ClientConfig(streaming=False, httpx_client=http))
        try:
            async for event in client.send_message(SendMessageRequest(message=new_text_message(
                    '{"action":"monitor"}', role=Role.ROLE_USER))):
                response = event[0] if isinstance(event, tuple) else event
                task = response.task
                break
            assert task.status.state == TaskState.TASK_STATE_WORKING
            assert (await client.get_task(GetTaskRequest(id=task.id))).id == task.id
            deliver(system, "sdk-monitor")
            done = await client.get_task(GetTaskRequest(id=task.id))
            assert done.status.state == TaskState.TASK_STATE_COMPLETED
            async for event in client.send_message(SendMessageRequest(message=new_text_message(
                    '{"action":"monitor"}', role=Role.ROLE_USER))):
                response = event[0] if isinstance(event, tuple) else event
                task = response.task
                break
            cancelled = await client.cancel_task(CancelTaskRequest(id=task.id))
            assert cancelled.status.state == TaskState.TASK_STATE_CANCELED
        finally:
            await client.close()
