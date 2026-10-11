"""End-to-end demo: three questions through the advocate, the wall, and the ISO gremlin.

    uv run demo.py                      # fresh copy of the boxes under out/demo/, transport auto
    uv run demo.py --live               # write into docs/boxes/ for real
    uv run demo.py --transport slim     # require A2A over SLIM (node must be up)

Transport auto: if a SLIM node answers on 127.0.0.1:46357 and SLIM_SHARED_SECRET
is set, the demo starts dept_gremlin.py on port 10001 and a gremlin_slim.py
gateway in front of it, and every department call travels agent -> SLIM ->
gateway -> A2A. Otherwise the ISO gremlin runs in-process.

Each step prints: fields shared (and withheld, held, awaiting approval), needs,
ranked options, the verdict with its brief, and every line written to the
student box. Question 3 is asked twice: before and after flipping final_quarter,
to show the verdict change.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from advocate import Advocate, Verdict, in_process, over_a2a
from box import MarkdownBoxStore
from brain import default_brain
from dept_gremlin import DeptGremlin, empty_answer
from wall import approve

HERE = Path(__file__).resolve().parent
BOXES = HERE / "docs" / "boxes"
SLIM_NODE = ("127.0.0.1", 46357)
DEPT_PORT = 10001
GATEWAY_NAME = "ucsc/gremlins/iso"

QUESTIONS = [
    ("Q1", "I want to drop from 16 to 9 units this quarter because of my job. Can I?"),
    ("Q2", "Am I currently over the on-campus work-hour limit?"),
    ("Q3", "Can I enroll in just 8 units this quarter?"),
]


# ---- transports ---------------------------------------------------------------
def slim_node_up() -> bool:
    try:
        with socket.create_connection(SLIM_NODE, timeout=0.5):
            return True
    except OSError:
        return False


def wait_http(url: str, seconds: float = 30) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


class SlimTransport:
    """ISO over SLIM: dept_gremlin.py server + gremlin_slim.py gateway, both child processes."""

    def __init__(self, box_dir: Path, log):
        self.box_dir, self.log = box_dir, log
        self.procs: list[subprocess.Popen] = []
        self.token = secrets.token_urlsafe(36)  # the dept gremlin needs no auth; the gateway requires a bearer shape

    def start(self) -> None:
        if not os.environ.get("SLIM_SHARED_SECRET"):
            raise RuntimeError("Set SLIM_SHARED_SECRET (same value as the SLIM node) for the SLIM transport.")
        env = {**os.environ, "BOX_DIR": str(self.box_dir)}
        self.procs.append(subprocess.Popen([
            "uv", "run", "dept_gremlin.py", "serve", "--dept", "iso", "--port", str(DEPT_PORT), "--box-dir", str(self.box_dir)],
            cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if not wait_http(f"http://127.0.0.1:{DEPT_PORT}/.well-known/agent-card.json"):
            raise RuntimeError("dept_gremlin.py did not come up on port 10001")
        self.log(f"  [slim] ISO gremlin up on http://127.0.0.1:{DEPT_PORT}")
        gateway = subprocess.Popen([
            "uv", "run", "--script", "gremlin_slim.py", "gateway", "--upstream", f"http://127.0.0.1:{DEPT_PORT}", "--name", GATEWAY_NAME],
            cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.procs.append(gateway)
        deadline = time.time() + 120
        while time.time() < deadline:
            line = gateway.stdout.readline()
            if not line and gateway.poll() is not None:
                raise RuntimeError("gremlin_slim.py gateway exited before becoming ready")
            if "slim_gateway_ready" in line:
                self.log(f"  [slim] gateway {GATEWAY_NAME} ready, upstream {DEPT_PORT}")
                return
        raise RuntimeError("gremlin_slim.py gateway did not become ready")

    def caller(self):
        async def call(session_id: str, question: str, context: dict) -> dict:
            request = json.dumps({"session_id": session_id, "question": question, "context": context}, ensure_ascii=False)
            proc = await asyncio.to_thread(subprocess.run, [
                "uv", "run", "--script", "gremlin_slim.py", "answer", request, "--name", GATEWAY_NAME],
                cwd=HERE, env={**os.environ, "GREMLIN_TOKEN": self.token}, capture_output=True, text=True, timeout=180)
            for line in reversed(proc.stdout.strip().splitlines()):
                if line.startswith("{"):
                    out = json.loads(line)
                    return out if out.get("ok") else empty_answer()
            self.log(f"  [slim] call failed: {proc.stderr.strip()[-300:]}")
            return empty_answer()
        return call

    def stop(self) -> None:
        for p in reversed(self.procs):
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


# ---- printing ---------------------------------------------------------------------
def show(v: Verdict, log) -> None:
    for d in v.depts:
        for i, r in enumerate(d.rounds, 1):
            log(f"  round {i} -> {d.dept.upper()}: shared {r.shared or '[]'}"
                + (f"  withheld(no) {r.withheld}" if r.withheld else "")
                + (f"  held {r.held}" if r.held else "")
                + (f"  awaiting approval {r.ask}" if r.ask else "")
                + (f"  redacted {r.redacted}" if r.redacted else ""))
        log(f"  needs: {d.answer.get('needs') or '[]'}"
            + (f"   ask student: {d.ask}" if d.ask else "") + (f"   blocked by permissions: {d.blocked}" if d.blocked else ""))
        if d.inbound and d.inbound.dropped:
            log(f"  wall dropped {d.inbound.dropped} uncited claim(s)" + (f"; REJECTED: {d.inbound.reason}" if d.inbound.rejected else ""))
    if v.options:
        log("  options (ranked by prefer: lines):")
        for o in v.options:
            attrs = ", ".join(f"{k}={o[k]}" for k in ("units", "hours", "weeks") if o.get(k) is not None)
            log(f"    {o['rank']}. {o['option']}  [{', '.join(o['cites'])}]" + (f"  ({attrs})" if attrs else "")
                + (f"  if: {'; '.join(o['conditions'])}" if o.get("conditions") else ""))
    log(f"  VERDICT: {v.kind}" + (f"  authority={v.authority}" if v.authority else "") + (f"  triggers={v.escalations}" if v.escalations else "")
        + (f"  ask={v.ask}" if v.ask else ""))
    if v.answer:
        log(f"  answer: {v.answer}")
    if v.brief:
        for k, val in v.brief.items():
            log(f"  brief.{k}: {'; '.join(val) if isinstance(val, list) else val}")
    for section, line in v.written:
        log(f"  wrote section {section}: {line[:150]}")


def run(store: MarkdownBoxStore, brain=None, transport: str = "auto", log=print) -> list[Verdict]:
    slim = None
    if transport in ("auto", "slim") and slim_node_up() and os.environ.get("SLIM_SHARED_SECRET"):
        slim = SlimTransport(store.root, log)
        slim.start()
        iso = slim.caller()
        log("transport: A2A over SLIM (agent -> SLIM node -> gateway -> ISO gremlin on :10001)")
    elif transport == "slim":
        raise SystemExit("SLIM node is not up on 127.0.0.1:46357 (or SLIM_SHARED_SECRET unset). Start: uv run --script gremlin_slim.py node")
    elif transport == "a2a":
        iso = over_a2a(f"http://127.0.0.1:{DEPT_PORT}")
        log(f"transport: A2A over HTTP to a dept_gremlin.py you started on :{DEPT_PORT}")
    else:
        iso = in_process(DeptGremlin("iso", store=store, brain=brain))
        log("transport: in-process (no SLIM node detected)")
    log(f"boxes: {store.root}")
    adv = Advocate(store=store, depts={"iso": iso})
    verdicts: list[Verdict] = []
    try:
        for label, question in QUESTIONS[:2]:
            log(f"\n== {label}: {question}")
            v = adv.ask_sync(question, f"demo-{label.lower()}")
            show(v, log)
            verdicts.append(v)
            if v.kind == "ASK_STUDENT":
                for f in v.ask:
                    if store.load("student").permission(f, "iso") == "ask":
                        approve(store, "student", f, "iso")
                        log(f"\n  student approves sharing '{f}' with ISO (approve_share) -> re-ask")
                        v = adv.ask_sync(question, f"demo-{label.lower()}-b")
                        show(v, log)
                        verdicts.append(v)
        label, question = QUESTIONS[2]
        log(f"\n== {label}: {question}   (final_quarter: {store.load('student').fields.get('final_quarter')})")
        before = adv.ask_sync(question, "demo-q3")
        show(before, log)
        verdicts.append(before)
        store.set_field("student", "final_quarter", "yes")
        store.set_field("student", "units", "8")
        log("\n  student box changed: final_quarter: yes, units: 8  -> re-ask")
        after = adv.ask_sync(question, "demo-q3-final")
        show(after, log)
        verdicts.append(after)
        log(f"\n  verdict change: {before.kind} -> {after.kind}")
    finally:
        if slim:
            slim.stop()
    return verdicts


def prepare_boxes(live: bool) -> MarkdownBoxStore:
    if live:
        return MarkdownBoxStore(BOXES)
    target = HERE / "out" / "demo" / datetime.now().strftime("%Y%m%d-%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    for name in ("iso", "student"):
        src = MarkdownBoxStore(BOXES).path(name)
        shutil.copy(src, target / f"{name}.md")
    return MarkdownBoxStore(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="use docs/boxes/ directly instead of a fresh copy")
    parser.add_argument("--transport", choices=["auto", "inprocess", "a2a", "slim"], default="auto")
    args = parser.parse_args()
    run(prepare_boxes(args.live), brain=default_brain(), transport=args.transport)
