# /// script
# requires-python = ">=3.10"
# dependencies = ["a2a-sdk[http-server]==1.2.2", "uvicorn>=0.30,<1"]
# ///
"""Local A2A protocol proof, with a server and a client in one file.

uv run gremlin_a2a.py serve
uv run gremlin_a2a.py ask "Hello from Gremlin"

Loopback only. No model, Google access, authentication, consent gate, or SLIM.
Never send real student records to this demo.
"""

import argparse
import asyncio
import json

import httpx
import uvicorn
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Role,
    SendMessageRequest,
    TaskState,
)
from starlette.applications import Starlette
from google.protobuf.json_format import MessageToJson

URL = "http://127.0.0.1:9999"


class DemoDepartment(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        query = get_message_text(context.message)
        print(json.dumps({"received_via": "A2A JSON-RPC", "question": query}), flush=True)
        await updater.add_artifact(
            parts=[new_text_part(
                text=("Hello from the demo campus department. "
                      f"Your A2A request arrived: {query}\n"
                      "This is a deterministic protocol test, not advising or verified policy."),
                media_type="text/plain",
            )]
        )
        await updater.update_status(state=TaskState.TASK_STATE_COMPLETED)

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise NotImplementedError("Cancellation is not supported by this immediate-response demo.")


def serve(host="127.0.0.1", port=9999, public_url=URL):
    card = AgentCard(
        name="Gremlin demo campus department",
        description="A demo echo agent for testing A2A. No real student data.",
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(
            protocol_binding="JSONRPC", protocol_version="1.0", url=public_url,
        )],
        skills=[AgentSkill(
            id="protocol_echo", name="Confirm receipt",
            description="Echo a question to prove an A2A round trip.",
            tags=["demo", "gremlin", "echo"],
            examples=["What should a student check before reducing their course load?"],
        )],
    )
    handler = DefaultRequestHandler(
        agent_executor=DemoDepartment(), task_store=InMemoryTaskStore(), agent_card=card,
    )
    app = Starlette(routes=[
        *create_agent_card_routes(card),
        *create_jsonrpc_routes(handler, "/"),
    ])
    uvicorn.run(app, host=host, port=port)


async def ask(question, url=URL):
    async with httpx.AsyncClient(timeout=15) as http:
        card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
    print(f"Discovered: {card.name}")
    print(f"Sending: {question}")
    client = await create_client(agent=card, client_config=ClientConfig(streaming=False))
    try:
        async for event in client.send_message(SendMessageRequest(
            message=new_text_message(question, role=Role.ROLE_USER),
        )):
            # The SDK yields (Task, update) tuples for task-oriented replies.
            task = event[0] if isinstance(event, tuple) else event
            print(MessageToJson(task, indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    server_parser = commands.add_parser("serve")
    server_parser.add_argument("--host", default="127.0.0.1")
    server_parser.add_argument("--port", type=int, default=9999)
    server_parser.add_argument("--public-url", default=URL,
                               help="URL clients can reach, advertised in the agent card")
    client_parser = commands.add_parser("ask")
    client_parser.add_argument("question")
    client_parser.add_argument("--url", default=URL)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.host, args.port, args.public_url)
    else:
        asyncio.run(ask(args.question, args.url))
