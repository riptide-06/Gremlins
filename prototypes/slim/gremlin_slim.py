# /// script
# requires-python = ">=3.11"
# dependencies = ["slima2a==0.7.1", "slim-bindings==2.0.0", "httpx>=0.28,<1"]
# ///
"""Optional A2A-over-SLIM gateway, local node, and client in one file.

Run with uv run --script gremlin_slim.py, not inside the Cloud Run environment.
AGNTCY's slima2a pins a2a-sdk 1.1.0; the deployed app uses 1.2.2.
The gateway holds no Gremlin credentials or memory. It forwards the caller's
bearer from SLIM RPC metadata to one fixed upstream, which enforces all roles.
Loopback plaintext SLIM node: synthetic testing only, not a hosted secure relay.
"""
import argparse
import asyncio
from datetime import timedelta
import json
import os
import re
import secrets
from urllib.parse import urlsplit

import httpx
import slim_bindings as slim
from a2a.helpers import new_text_message
from a2a.types import AgentCard, Role, SendMessageRequest, SendMessageResponse
from google.protobuf.json_format import MessageToDict, MessageToJson, ParseDict, ParseError
from slima2a import initialize_slim_service, setup_slim_client
from slima2a.types.v1.a2a_pb2_slimrpc import (
    A2AServiceServicer, A2AServiceStub, add_A2AServiceServicer_to_server,
)

DEFAULT_UPSTREAM = "https://gremlin-331254975906.us-west1.run.app"
DEFAULT_NAME = "ucsc/gremlins/gateway"
DEFAULT_NODE = "http://127.0.0.1:46357"


def event(event_name, **fields):
    print(json.dumps({"event": event_name, **fields}), flush=True)


def rpc_error(code, message):
    return slim.RpcError.Rpc(code=code, message=message, details=None)


def validate_upstream(url):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Upstream must be a base URL without credentials, query, or fragment.")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("Upstream must use HTTPS (HTTP is allowed only on loopback).")
    return url.rstrip("/")


async def upstream_endpoint(http, base):
    base = validate_upstream(base)
    response = await http.get(base + "/.well-known/agent-card.json")
    response.raise_for_status()
    card = ParseDict(response.json(), AgentCard())
    endpoint = next((i.url for i in card.supported_interfaces if i.protocol_binding == "JSONRPC"), None)
    if not endpoint:
        raise ValueError("Upstream does not advertise JSONRPC.")
    endpoint = validate_upstream(endpoint)
    if urlsplit(endpoint).netloc != urlsplit(base).netloc or urlsplit(endpoint).scheme != urlsplit(base).scheme:
        raise ValueError("Refusing to forward credentials to a different origin from discovery.")
    return endpoint


class Gateway(A2AServiceServicer):
    def __init__(self, http, endpoint):
        self.http, self.endpoint = http, endpoint

    async def SendMessage(self, request, context):
        auth = context.metadata().get("authorization", "")
        token = auth[7:] if isinstance(auth, str) and auth.startswith("Bearer ") else ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
            event("slim_authentication_denied")
            raise rpc_error(slim.RpcCode.UNAUTHENTICATED, "Set authorization bearer in RPC metadata, never in message text.")
        params = MessageToDict(request)
        body = {"jsonrpc": "2.0", "id": secrets.token_hex(8), "method": "SendMessage", "params": params}
        # Match the HTTP service's wire limit, not just protobuf byte size.
        encoded = json.dumps(body).encode()
        if len(encoded) > 16000:
            raise rpc_error(slim.RpcCode.INVALID_ARGUMENT, "Request too large.")
        event("slim_request_forwarded", contents="REDACTED")
        try:
            response = await self.http.post(self.endpoint, content=encoded,
                                           headers={"Authorization": auth, "Content-Type": "application/json", "A2A-Version": "1.0"})
            if response.status_code in (401, 403):
                event("slim_authentication_denied")
                raise rpc_error(slim.RpcCode.UNAUTHENTICATED, "Gremlin rejected the credential. Sign in to rotate expired/revoked credentials.")
            if response.status_code == 413:
                raise rpc_error(slim.RpcCode.INVALID_ARGUMENT, "Request too large.")
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                # Never emit untrusted upstream errors or request contents.
                raise rpc_error(slim.RpcCode.INVALID_ARGUMENT, "Upstream rejected the A2A request.")
            result = ParseDict(payload["result"], SendMessageResponse())
        except (httpx.HTTPError, ValueError, KeyError, ParseError):
            event("slim_upstream_failed")
            raise rpc_error(slim.RpcCode.UNAVAILABLE, "Upstream request failed.") from None
        # Explain the added transport without changing permissions or memory.
        if result.HasField("message"):
            for part in result.message.parts:
                if part.WhichOneof("content") != "text":
                    continue
                try:
                    value = json.loads(part.text)
                except ValueError:
                    continue
                if isinstance(value, dict) and isinstance(value.get("guide"), dict):
                    value["guide"]["slim_transport"] = (
                        "You connected through A2A over SLIM SlimRPC. Put authorization: Bearer <token> "
                        "in RPC metadata; the gateway forwards it as an HTTP header to Gremlin. "
                        "SLIM names/shared secrets do not grant student privileges. "
                        "Use gremlin_slim.py call; the backend still enforces your role and revocation."
                    )
                    part.text = json.dumps(value, ensure_ascii=False)
        event("slim_response_returned", contents="REDACTED")
        return result
    # All other generated RPC methods retain UNIMPLEMENTED defaults. No task,
    # history, streaming, subscription, or push path can bypass HTTP permissions.


def shared_secret():
    secret = os.environ.get("SLIM_SHARED_SECRET", "")
    if len(secret) < 32:
        raise SystemExit("Set SLIM_SHARED_SECRET to a shared random value of at least 32 characters.")
    return secret


def split_name(name):
    parts = name.split("/")
    if len(parts) != 3 or not all(parts):
        raise ValueError("SLIM name must be namespace/group/name.")
    return parts


async def run_node():
    service = await initialize_slim_service(log_level="warn")
    try:
        await service.run_server_async(slim.new_insecure_server_config("127.0.0.1:46357"))
        event("slim_node_ready", address=DEFAULT_NODE, warning="Loopback plaintext; synthetic demo only")
        await asyncio.Event().wait()
    finally:
        await service.shutdown_async()


async def run_gateway(args):
    secret = shared_secret()
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as http:
        endpoint = await upstream_endpoint(http, args.upstream)
        service, app, name, connection = await setup_slim_client(
            *split_name(args.name), slim_url=args.node, secret=secret, log_level="warn")
        server = slim.Server.new_with_connection(app, name, connection)
        add_A2AServiceServicer_to_server(Gateway(http, endpoint), server)
        event("slim_gateway_ready", name=args.name, upstream=endpoint, contents="REDACTED")
        try:
            await server.serve_async()
        finally:
            await service.shutdown_async()


async def run_client(args):
    token = os.environ.get("GREMLIN_TOKEN", "")
    if not token:
        raise SystemExit("Set GREMLIN_TOKEN privately to your student or advisor credential.")
    service, app, _, connection = await setup_slim_client(
        "ucsc", "gremlins", "client-" + secrets.token_hex(6),
        slim_url=args.node, secret=shared_secret(), log_level="warn")
    channel = slim.Channel.new_with_connection(app, slim.Name(*split_name(args.name)), connection)
    stub = A2AServiceStub(channel)
    request = SendMessageRequest(message=new_text_message(
        json.dumps({"action": args.action, "text": args.text}), role=Role.ROLE_USER))
    try:
        response = await stub.SendMessage(request, timeout=timedelta(seconds=25),
                                          metadata={"authorization": "Bearer " + token})
        print(MessageToJson(response, indent=2))
    finally:
        await service.shutdown_async()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["node", "gateway", "call"])
    parser.add_argument("action", nargs="?", choices=["hello", "read", "remember", "contribute"])
    parser.add_argument("text", nargs="?", default="")
    parser.add_argument("--node", default=DEFAULT_NODE)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--upstream", default=DEFAULT_UPSTREAM)
    args = parser.parse_args()
    if args.mode == "call" and args.action is None:
        parser.error("call requires an action")
    try:
        asyncio.run({"node": run_node, "gateway": lambda: run_gateway(args),
                     "call": lambda: run_client(args)}[args.mode]())
    except KeyboardInterrupt:
        pass
