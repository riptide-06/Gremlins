"""CubbyBoxStore: the student box as a text file inside the student's real Campus
Cubby (Google Drive), read and appended through Campus Cubbies' A2A tools with the
student's own credential. Department boxes stay on disk (they are policy, not the
student's data) and come from the fallback store.

    CUBBY_URL=https://cubby.bayleaf.dev CUBBY_TOKEN=... uv run cubby_store.py check
    CUBBY_URL=... CUBBY_TOKEN=... uv run cubby_store.py seed       # create gremlin-student.md from the template
    BOX_STORE=cubby CUBBY_URL=... CUBBY_TOKEN=... uv run mcp_server.py

Wire format (prototypes/cubbies/SKILL.md): POST {origin}/a2a, A2A 1.0 JSON-RPC
`SendMessage`, the tool call as JSON in the message's text part, the reply's text
parts concatenated and JSON-decoded into {ok, ...} or {ok: false, error}.

Only the student's box travels this way. Every write is an exact-match edit against
the revision just read, so a concurrent change fails loudly instead of clobbering.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid

import httpx

from box import Box, BoxStore, MarkdownBoxStore, _SECTION, parse_box, stamp

FILE_PREFIX = "gremlin-"
TEMPLATE = "student.template.md"


class CubbyError(RuntimeError):
    pass


class CubbyClient:
    """Minimal A2A 1.0 client for the Campus Cubbies tool surface."""

    def __init__(self, origin: str, token: str, http: httpx.Client | None = None, timeout: float = 30.0):
        self.origin = origin.rstrip("/")
        self.token = token
        self.http = http or httpx.Client(timeout=timeout)

    def call(self, action: str, **args) -> dict:
        tool = {"action": action, **{k: str(v) for k, v in args.items()}}
        body = {"jsonrpc": "2.0", "id": "gremlin-" + uuid.uuid4().hex[:12], "method": "SendMessage",
                "params": {"message": {"messageId": uuid.uuid4().hex, "role": "ROLE_USER",
                                       "parts": [{"text": json.dumps(tool, ensure_ascii=False)}]}}}
        headers = {"Content-Type": "application/json", "Accept": "application/json", "A2A-Version": "1.0",
                   "Authorization": "Bearer " + self.token}
        response = self.http.post(self.origin + "/a2a", json=body, headers=headers)
        if response.status_code == 401:
            raise CubbyError("Campus Cubbies rejected the credential (401). Reconnect through the pairing page.")
        if response.status_code >= 400:
            raise CubbyError(f"Campus Cubbies HTTP {response.status_code}")
        envelope = response.json()
        if envelope.get("error"):
            raise CubbyError(f"JSON-RPC error: {envelope['error']}")
        parts = (((envelope.get("result") or {}).get("message") or {}).get("parts")) or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        try:
            out = json.loads(text)
        except ValueError:
            raise CubbyError("Campus Cubbies reply was not JSON") from None
        if not isinstance(out, dict) or not out.get("ok"):
            raise CubbyError(f"{action}: {out.get('error') if isinstance(out, dict) else out}")
        return out

    # -- the four tools the box needs ------------------------------------------
    def hello(self) -> dict:
        return self.call("hello")

    def list_files(self) -> list[dict]:
        files, cursor = [], ""
        while True:
            page = self.call("list_files", **({"cursor": cursor} if cursor else {}))
            files += page.get("files", [])
            cursor = page.get("cursor") or ""
            if not cursor:
                return files

    def read_file(self, file_id: str) -> dict:
        return self.call("read_file", file_id=file_id)

    def create_file(self, name: str, text: str) -> dict:
        return self.call("create_file", name=name, text=text)

    def edit_file(self, file_id: str, revision: str, search: str, replacement: str) -> dict:
        return self.call("edit_file", file_id=file_id, revision=revision, search=search, replacement=replacement)


class CubbyBoxStore:
    """BoxStore whose student box lives in the cubby. Department boxes come from `fallback`."""

    def __init__(self, client: CubbyClient, fallback: BoxStore | None = None, cubby_names: set[str] | None = None):
        self.client = client
        self.fallback = fallback or MarkdownBoxStore()
        self.cubby_names = cubby_names or {"student"}
        self.root = getattr(self.fallback, "root", None)   # seed_student_box reads the template from here

    def _is_cubby(self, name: str) -> bool:
        return name in self.cubby_names or name.startswith("student")

    @staticmethod
    def filename(name: str) -> str:
        return f"{FILE_PREFIX}{name}.md"

    def _find(self, name: str) -> dict | None:
        wanted = self.filename(name)
        for f in self.client.list_files():
            if f.get("name") == wanted and not f.get("trashed"):
                return f
        return None

    def _read(self, name: str) -> dict:
        f = self._find(name)
        if not f:
            raise FileNotFoundError(f"{self.filename(name)} is not in the cubby yet; run `cubby_store.py seed`")
        return self.client.read_file(f["id"])

    # -- BoxStore -------------------------------------------------------------------
    def exists(self, name: str) -> bool:
        if not self._is_cubby(name):
            return self.fallback.exists(name)
        return self._find(name) is not None

    def load(self, name: str) -> Box:
        if not self._is_cubby(name):
            return self.fallback.load(name)
        return parse_box(self._read(name)["text"], name)

    def write(self, name: str, text: str) -> None:
        if not self._is_cubby(name):
            return self.fallback.write(name, text)
        current = self._find(name)
        if current is None:
            self.client.create_file(self.filename(name), text)
        else:
            doc = self.client.read_file(current["id"])
            self.client.edit_file(doc["file_id"], doc["revision"], doc["text"], text)

    def append(self, name: str, section: int, line: str) -> None:
        if not self._is_cubby(name):
            return self.fallback.append(name, section, line)
        doc = self._read(name)
        search, replacement = section_edit(doc["text"], section, line)
        self.client.edit_file(doc["file_id"], doc["revision"], search, replacement)

    def set_field(self, name: str, key: str, value: str) -> None:
        if not self._is_cubby(name):
            return self.fallback.set_field(name, key, value)  # type: ignore[attr-defined]
        doc = self._read(name)
        m = re.search(rf"^{re.escape(key)}:[ \t]*.*$", doc["text"], re.MULTILINE)
        if not m:
            raise KeyError(key)
        # whole line, newline to newline, so prose such as "(units: 15)" can never be the match
        self.client.edit_file(doc["file_id"], doc["revision"], "\n" + m.group(0) + "\n", f"\n{key}: {value}\n")

    def path(self, name: str):
        """Mirrors MarkdownBoxStore.path for callers that print where a box lives."""
        return f"cubby:{self.filename(name)}" if self._is_cubby(name) else self.fallback.path(name)  # type: ignore[attr-defined]


def section_edit(text: str, section: int, line: str) -> tuple[str, str]:
    """The exact-match edit that appends `line` to numbered `section`: search is the
    heading plus everything up to the next heading (unique because headings are), the
    replacement keeps the existing lines and adds the new one at the end."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if (m := _SECTION.match(l)) and int(m.group(1)) == section), None)
    if start is None:
        raise ValueError(f"box has no section {section}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    block = lines[start:end]
    search = "\n".join(block)
    body = block[1:]
    while body and not body[-1].strip():
        body.pop()
    if not body:
        body = [""]
    new_line = line.replace("\n", " ").rstrip()
    if end < len(lines):                      # a later heading follows: keep one blank line before it
        search += "\n"
        replacement = "\n".join([block[0], *body, new_line, ""]) + "\n"
    else:                                     # last section: the file's own trailing newline stays
        replacement = "\n".join([block[0], *body, new_line])
    return search, replacement


def from_env(fallback: BoxStore | None = None) -> CubbyBoxStore | None:
    """BOX_STORE=cubby with CUBBY_URL and CUBBY_TOKEN set -> a CubbyBoxStore, else None."""
    if os.environ.get("BOX_STORE", "").lower() != "cubby":
        return None
    origin, token = os.environ.get("CUBBY_URL", ""), os.environ.get("CUBBY_TOKEN", "")
    if not origin or not token:
        raise CubbyError("BOX_STORE=cubby needs CUBBY_URL and CUBBY_TOKEN")
    return CubbyBoxStore(CubbyClient(origin, token), fallback)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["check", "seed", "show"])
    parser.add_argument("--name", default="student", help="box name (file gremlin-<name>.md in the cubby)")
    args = parser.parse_args(argv)
    origin, token = os.environ.get("CUBBY_URL", ""), os.environ.get("CUBBY_TOKEN", "")
    if not origin or not token:
        print("Set CUBBY_URL and CUBBY_TOKEN (never paste the token into a file or a chat).", file=sys.stderr)
        return 2
    client = CubbyClient(origin, token)
    store = CubbyBoxStore(client)
    if args.command == "check":
        me = client.hello()
        files = client.list_files()
        print(json.dumps({"identity": me.get("identity"), "roles": me.get("roles"), "folder": (me.get("cubby") or {}).get("folder_url"),
                          "files": [f.get("name") for f in files], "box_present": store.exists(args.name)}, indent=1))
        return 0
    if args.command == "seed":
        from box import seed_student_box
        me = client.hello()
        identity = str(me.get("identity", ""))
        created = seed_student_box(store, args.name, args.name, identity.split("@")[0] or "student", identity)
        print("created" if created else "already there", store.filename(args.name), (me.get("cubby") or {}).get("folder_url", ""))
        return 0
    print(store.load(args.name).text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
