# /// script
# requires-python = ">=3.11"
# dependencies = ["a2a-sdk==1.2.2"]
# ///
"""Self-instructing A2A client: GREMLIN_TOKEN=... uv run gremlin_client.py URL hello"""
import argparse
import asyncio
import json
import os

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from google.protobuf.json_format import MessageToJson


async def call(url, action, text):
    token = os.environ.get("GREMLIN_TOKEN")
    if not token:
        raise SystemExit("Set GREMLIN_TOKEN privately. Never place it in message text.")
    async with httpx.AsyncClient(timeout=20, headers={"Authorization": "Bearer " + token}) as http:
        card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
        client = await create_client(agent=card, client_config=ClientConfig(streaming=False, httpx_client=http))
        try:
            async for event in client.send_message(SendMessageRequest(message=new_text_message(
                json.dumps({"action": action, "text": text}), role=Role.ROLE_USER))):
                print(MessageToJson(event[0] if isinstance(event, tuple) else event, indent=2))
        finally:
            await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Service base URL, without /a2a")
    parser.add_argument("action", choices=["hello", "read", "remember", "contribute"])
    parser.add_argument("text", nargs="?", default="")
    args = parser.parse_args()
    asyncio.run(call(args.url, args.action, args.text))
