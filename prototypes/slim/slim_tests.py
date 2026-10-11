# /// script
# requires-python = ">=3.11"
# dependencies = ["slima2a==0.7.1", "slim-bindings==2.0.0", "httpx>=0.28,<1"]
# ///
"""Gateway tests in the isolated SLIM environment: uv run --script slim_tests.py."""
import contextlib
import io
import json
import unittest

import httpx
import slim_bindings as slim
from a2a.helpers import new_text_message
from a2a.types import AgentCard, AgentInterface, GetTaskRequest, Role, SendMessageRequest, SendMessageResponse
from google.protobuf.json_format import MessageToDict

from gremlin_slim import Gateway, upstream_endpoint, validate_upstream


TOKEN = "synthetic_" + "x" * 40


class Context:
    def __init__(self, auth="Bearer " + TOKEN):
        self.auth = auth

    def metadata(self):
        return {"authorization": self.auth} if self.auth else {}


def request(action="hello", **extra):
    return SendMessageRequest(message=new_text_message(
        json.dumps({"action": action, **extra}), role=Role.ROLE_USER))


def reply(value):
    return MessageToDict(SendMessageResponse(message=new_text_message(json.dumps(value))))


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.seen = []
        self.status = 200
        self.result = {"jsonrpc": "2.0", "id": "test", "result": reply({"ok": True, "guide": {"authenticated_role": "student"}})}

        def handle(req):
            self.seen.append(req)
            return httpx.Response(self.status, json=self.result)

        self.http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        self.gateway = Gateway(self.http, "https://gremlin.example/a2a")

    async def asyncTearDown(self):
        await self.http.aclose()

    async def test_forward_metadata_and_version_not_credentials_in_body(self):
        result = await self.gateway.SendMessage(request(), Context())
        req = self.seen[0]
        self.assertEqual(req.headers["authorization"], "Bearer " + TOKEN)
        self.assertEqual(req.headers["a2a-version"], "1.0")
        self.assertNotIn(TOKEN, req.content.decode())
        self.assertEqual(json.loads(req.content)["method"], "SendMessage")
        guide = json.loads(result.message.parts[0].text)["guide"]
        self.assertEqual(guide["authenticated_role"], "student")
        self.assertIn("slim_transport", guide)

    async def test_missing_or_malformed_credentials_rejected_without_forward(self):
        for auth in ("", "Bearer short", "Bearer " + TOKEN + "\n", "Basic " + TOKEN):
            with self.assertRaises(slim.RpcError.Rpc) as error:
                await self.gateway.SendMessage(request(text="Bearer " + TOKEN), Context(auth))
            self.assertEqual(error.exception.code, slim.RpcCode.UNAUTHENTICATED)
        self.assertEqual(self.seen, [])

    async def test_upstream_auth_rejection_including_revocation(self):
        for status in (401, 403):
            self.status = status
            with self.assertRaises(slim.RpcError.Rpc) as error:
                await self.gateway.SendMessage(request(), Context())
            self.assertEqual(error.exception.code, slim.RpcCode.UNAUTHENTICATED)

    async def test_advisor_denial_is_returned_without_promotion(self):
        self.result["result"] = reply({"ok": False, "error": "Advisor cannot read student memory."})
        result = await self.gateway.SendMessage(request("read", role="student"), Context())
        value = json.loads(result.message.parts[0].text)
        self.assertFalse(value["ok"])
        self.assertNotIn("entries", value)

    async def test_oversized_request_rejected_without_forward(self):
        with self.assertRaises(slim.RpcError.Rpc) as error:
            await self.gateway.SendMessage(request("remember", text="x" * 16001), Context())
        self.assertEqual(error.exception.code, slim.RpcCode.INVALID_ARGUMENT)
        self.assertEqual(self.seen, [])

    async def test_task_lookup_not_implemented(self):
        with self.assertRaises(slim.RpcError.Rpc) as error:
            self.gateway.GetTask(GetTaskRequest(id="other-student"), Context())
        self.assertEqual(error.exception.code, slim.RpcCode.UNIMPLEMENTED)
        self.assertEqual(self.seen, [])

    async def test_upstream_errors_are_sanitized(self):
        self.result = {"error": {"message": "PRIVATE CONTENT " + TOKEN}}
        with self.assertRaises(slim.RpcError.Rpc) as error:
            await self.gateway.SendMessage(request(), Context())
        self.assertNotIn("PRIVATE CONTENT", str(error.exception))
        self.assertNotIn(TOKEN, str(error.exception))
        self.status = 500
        with self.assertRaises(slim.RpcError.Rpc) as error:
            await self.gateway.SendMessage(request(), Context())
        self.assertEqual(error.exception.code, slim.RpcCode.UNAVAILABLE)
        self.status = 200
        self.result = {"result": {"unexpectedPrivateField": "PRIVATE CONTENT " + TOKEN}}
        with self.assertRaises(slim.RpcError.Rpc) as error:
            await self.gateway.SendMessage(request(), Context())
        self.assertEqual(error.exception.code, slim.RpcCode.UNAVAILABLE)
        self.assertNotIn(TOKEN, str(error.exception))

    async def test_logs_redacted(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            await self.gateway.SendMessage(request("remember", text="PRIVATE CANARY"), Context())
        self.assertNotIn("PRIVATE CANARY", output.getvalue())
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertIn("REDACTED", output.getvalue())

    async def test_discovery_does_not_redirect_credentials(self):
        def handler(req):
            card = AgentCard(supported_interfaces=[AgentInterface(url="https://attacker.example/a2a", protocol_binding="JSONRPC")])
            return httpx.Response(200, json=MessageToDict(card))

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with self.assertRaises(ValueError):
                await upstream_endpoint(http, "https://gremlin.example")
        for url in ("http://remote.example", "https://user:password@gremlin.example", "https://gremlin.example?token=secret"):
            with self.assertRaises(ValueError):
                validate_upstream(url)
        self.assertEqual(validate_upstream("http://127.0.0.1:10000/"), "http://127.0.0.1:10000")


if __name__ == "__main__":
    unittest.main()
