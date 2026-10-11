"""CubbyBoxStore against a fake Campus Cubbies service that speaks the real wire format
(A2A 1.0 SendMessage envelope, {ok, ...} tool results, exact-match edits, revisions)."""
import json
import shutil
from pathlib import Path

import httpx
import pytest

from advocate import Advocate, DeptGremlin, in_process
from box import MarkdownBoxStore, seed_student_box
from brain import ScriptedBrain
from conftest import good_answer
from cubby_store import CubbyBoxStore, CubbyClient, CubbyError, section_edit

BOXES = Path(__file__).resolve().parent.parent / "docs" / "boxes"


class FakeCubbies:
    """Enough of prototypes/cubbies to test against: files with versions, one-match edits."""

    def __init__(self, token="t" * 40):
        self.token, self.files, self.calls, self.next = token, {}, [], 1

    def tool(self, action, args):
        if action == "hello":
            return {"identity": "demo@ucsc.edu", "roles": ["owner", "contributor"], "cubby": {"folder_id": "f1", "folder_url": "https://drive.google.com/drive/folders/f1"}}
        if action == "list_files":
            return {"files": [{"id": i, "name": f["name"], "mimeType": "text/plain", "version": str(f["version"])} for i, f in self.files.items()], "cursor": ""}
        if action == "read_file":
            f = self.files[args["file_id"]]
            return {"file_id": args["file_id"], "name": f["name"], "text": f["text"], "revision": str(f["version"])}
        if action == "create_file":
            fid = f"id{self.next}"; self.next += 1
            self.files[fid] = {"name": args["name"], "text": args["text"], "version": 1}
            return {"id": fid, "name": args["name"], "version": "1"}
        if action == "edit_file":
            f = self.files[args["file_id"]]
            if str(f["version"]) != args["revision"]:
                raise ValueError("File changed. Read again before editing.")
            text, search = f["text"], args["search"]
            first = text.find(search) if search else -1
            if first < 0 or text.find(search, first + 1) >= 0:
                raise ValueError("Search text must match exactly once.")
            f["text"] = text.replace(search, args["replacement"], 1)
            f["version"] += 1
            return {"id": args["file_id"], "version": str(f["version"])}
        raise ValueError("Tool unavailable for this identity.")

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/a2a" and request.headers["a2a-version"] == "1.0"
        if request.headers.get("authorization") != "Bearer " + self.token:
            return httpx.Response(401, json={"error": "unauthorized"})
        body = json.loads(request.content)
        assert body["method"] == "SendMessage" and body["params"]["message"]["role"] == "ROLE_USER"
        tool = json.loads(body["params"]["message"]["parts"][0]["text"])
        self.calls.append(tool["action"])
        try:
            out = {"ok": True, **self.tool(tool["action"], {k: v for k, v in tool.items() if k != "action"})}
        except (ValueError, KeyError) as exc:
            out = {"ok": False, "error": str(exc)}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"],
                                         "result": {"message": {"messageId": "m", "role": "ROLE_AGENT", "parts": [{"text": json.dumps(out)}]}}})


@pytest.fixture
def cubby(tmp_path):
    for name in ("iso", "cmpm", "college", "finaid"):
        shutil.copy(BOXES / f"{name}.md", tmp_path / f"{name}.md")
    shutil.copy(BOXES / "student.template.md", tmp_path / "student.template.md")
    fake = FakeCubbies()
    client = CubbyClient("https://cubby.test", fake.token, http=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    return fake, CubbyBoxStore(client, MarkdownBoxStore(tmp_path))


def test_seed_creates_the_box_file_in_the_cubby(cubby):
    fake, store = cubby
    assert not store.exists("student")
    assert seed_student_box(store, "student", "s-1", "Demo Student", "demo@ucsc.edu") is True
    assert seed_student_box(store, "student", "s-1", "Demo Student", "demo@ucsc.edu") is False
    assert [f["name"] for f in fake.files.values()] == ["gremlin-student.md"]
    box = store.load("student")
    assert box.fields["name"] == "Demo Student" and box.permission("name", "iso") == "never"
    assert box.departments == ["ISO", "CMPM", "College", "FinAid"]
    assert store.load("iso").meta["department"] == "iso"      # department boxes come from disk


def test_append_is_an_exact_match_edit_in_the_right_section(cubby):
    fake, store = cubby
    seed_student_box(store, "student", "s-1", "Demo Student", "demo@ucsc.edu")
    store.append("student", 5, "2026-10-11T00:00:00+00:00 | CONVERGED | s | q | best | F-01 | federal")
    store.append("student", 5, "2026-10-11T00:00:01+00:00 | CONVERGED | s | q2 | best | F-02 | federal")
    store.append("student", 8, "2026-10-11T00:00:02+00:00 | ASK_STUDENT | s | q3 | hours | iso")
    text = list(fake.files.values())[0]["text"]
    five = text[text.index("## 5."):text.index("## 6.")]
    assert five.count("CONVERGED") == 2 and five.index("q |") < five.index("q2 |")   # chronological
    assert "ASK_STUDENT" in text[text.index("## 8."):]
    box = store.load("student")
    assert len([l for l in box.section(5).lines if "CONVERGED" in l]) == 2
    assert fake.calls.count("edit_file") == 3 and list(fake.files.values())[0]["version"] == 4


def test_set_field_and_concurrent_change(cubby):
    fake, store = cubby
    seed_student_box(store, "student", "s-1", "Demo Student", "demo@ucsc.edu")
    store.set_field("student", "units", "15")
    assert store.load("student").fields["units"] == "15"
    with pytest.raises(KeyError):
        store.set_field("student", "no_such_field", "1")
    # someone edits the file in Drive between our read and our write: the edit is refused, nothing
    # clobbered. Drive does this by itself for a moment after any write, so the store re-reads and
    # retries a few times; a change that keeps happening is still an error.
    fid = next(iter(fake.files))
    original_read = store.client.read_file
    races = {"left": 2}
    def racing_read(file_id):
        doc = original_read(file_id)
        if races["left"] > 0:
            races["left"] -= 1
            fake.files[fid]["version"] += 1
        return doc
    store.client.read_file = racing_read
    store.RETRIES = (0.0, 0.0, 0.0)
    store.append("student", 4, "x | y")                 # two transient conflicts, then it lands
    assert "x | y" in fake.files[fid]["text"] and races["left"] == 0
    races["left"] = 99
    with pytest.raises(CubbyError):
        store.append("student", 4, "never | lands")
    assert "never | lands" not in fake.files[fid]["text"]


def test_append_many_is_one_read_and_one_edit(cubby):
    fake, store = cubby
    seed_student_box(store, "student", "s-1", "Demo Student", "demo@ucsc.edu")
    store.load("student")                                # learns the file id once
    before = len(fake.calls)
    store.append_many("student", [(7, "t | SHARED | iso | units | s1"), (5, "t | CONVERGED | s1 | q | best | F-01 | federal"),
                                  (4, "t | SESSION | s1 | CONVERGED | iso | F-01 | dropped=0"), (7, "t | SHARED | cmpm | units | s1")])
    assert fake.calls[before:] == ["read_file", "edit_file"]
    box = store.load("student")
    assert [l for l in box.section(7).lines if "SHARED" in l] == ["t | SHARED | iso | units | s1", "t | SHARED | cmpm | units | s1"]
    assert any("CONVERGED" in l for l in box.section(5).lines) and any("SESSION" in l for l in box.section(4).lines)


def test_bad_credential_is_a_clear_error(cubby):
    fake, store = cubby
    store.client.token = "wrong"
    with pytest.raises(CubbyError) as err:
        store.client.hello()
    assert "401" in str(err.value)


def test_section_edit_is_unique_and_keeps_following_sections():
    text = "# S\n\n## 4. Session log\n\n## 5. Converged answers\n\nold line\n\n## 6. Briefs\n"
    search, replacement = section_edit(text, 5, "new line")
    assert text.count(search) == 1
    new = text.replace(search, replacement, 1)
    assert new.index("old line") < new.index("new line") < new.index("## 6. Briefs")
    search, replacement = section_edit(text, 6, "last")
    assert text.replace(search, replacement, 1).endswith("## 6. Briefs\n\nlast\n")


def test_advocate_writes_its_verdict_into_the_cubby(cubby):
    fake, store = cubby
    seed_student_box(store, "student", "s-1", "Demo Student", "demo@ucsc.edu")
    store.set_field("student", "units", "17")
    store.set_field("student", "visa", "F-1")
    brain = ScriptedBrain(default=good_answer(cites=["F-01"], options=[
        {"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}]))
    adv = Advocate(store=store, depts={"iso": in_process(DeptGremlin("iso", store=store, brain=brain))})
    v = adv.ask_sync("Can I drop to 12 units?", "s-cubby")
    assert v.kind == "CONVERGED"
    text = list(fake.files.values())[0]["text"]
    assert "SESSION | s-cubby | CONVERGED" in text and "SHARED | iso" in text
    assert "Demo Student" not in json.dumps(v.to_dict())


def test_set_permission_in_the_cubby(cubby):
    fake, store = cubby
    seed_student_box(store, "student", "s-1", "Demo Student", "demo@ucsc.edu")
    store.set_permission("student", "hours", "college", "yes")
    assert store.load("student").permission("hours", "college") == "yes"
    assert store.load("student").permission("hours", "iso") == "ask"
