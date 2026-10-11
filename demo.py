"""End-to-end demo: the judge's six questions through the advocate, the wall, and
four department gremlins (ISO, CMPM advising, college advising, financial aid).

    uv run demo.py                      # fresh copy of the real boxes under out/demo/, transport auto
    uv run demo.py --live               # write into docs/boxes/ for real
    uv run demo.py --transport slim     # require A2A over SLIM for ISO (node must be up)
    uv run demo.py --questions c1,d1    # a subset, by id (see docs/QUESTIONS.md)

Transport auto: if a SLIM node answers on 127.0.0.1:46357 and SLIM_SHARED_SECRET
is set, the demo starts dept_gremlin.py on port 10001 and a gremlin_slim.py
gateway in front of it, and every ISO call travels agent -> SLIM -> gateway ->
A2A; the other three gremlins run in-process. Otherwise all four run in-process.

Each step prints: departments in scope, fields shared (and withheld, held,
awaiting approval), needs, ranked options, the verdict with its brief, and every
line written to the student box. ASK_STUDENT questions are re-asked after the
student approves the field; c1 is asked again after the deadline moves to 2 days
away, to show the same question change verdict on new information.
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

from advocate import Advocate, Verdict, build_depts, over_a2a
from box import MarkdownBoxStore
from brain import default_brain
from dept_gremlin import DeptGremlin, empty_answer
from wall import approve

HERE = Path(__file__).resolve().parent
BOXES = HERE / "docs" / "boxes"
SLIM_SCRIPT = next((p for p in (HERE / "gremlin_slim.py", HERE / "prototypes" / "slim" / "gremlin_slim.py") if p.exists()),
                   HERE / "prototypes" / "slim" / "gremlin_slim.py")
SLIM_NODE = ("127.0.0.1", 46357)
DEPT_PORT = 10001
GATEWAY_NAME = "ucsc/gremlins/iso"

QUESTIONS = [
    ("c1", "Can I drop my 5-unit GE and go from 17 to 12 units?"),
    ("p1", "My college adviser approved me to take 10 units this quarter, so I can drop to 10, right?"),
    ("e1", "I've been dealing with a health issue and can't handle 17 units. What can I do?"),
    ("a1", "Can I take a second on-campus job, 12 more hours a week?"),
    ("d1", "Should I add CMPM 120 now and go to 22 units, or wait until next year?"),
    ("e2", "Can I drop my 5-unit GE and go from 17 to 12 units?"),   # same as c1, after days_to_deadline -> 2
]
REAL = ("iso", "cmpm", "college", "finaid", "student")


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
            "uv", "run", "--script", str(SLIM_SCRIPT), "gateway", "--upstream", f"http://127.0.0.1:{DEPT_PORT}", "--name", GATEWAY_NAME],
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
                "uv", "run", "--script", str(SLIM_SCRIPT), "answer", request, "--name", GATEWAY_NAME],
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
    log(f"  in scope: {[d.dept for d in v.depts]}")
    log(f"  VERDICT: {v.kind}" + (f"  authority={v.authority}" if v.authority else "") + (f"  triggers={v.escalations}" if v.escalations else "")
        + (f"  ask={v.ask}" if v.ask else ""))
    if v.answer:
        log(f"  answer: {v.answer}")
    if v.brief:
        for k, val in v.brief.items():
            log(f"  brief.{k}: {'; '.join(val) if isinstance(val, list) else val}")
    for section, line in v.written:
        log(f"  wrote section {section}: {line[:150]}")


def run(store: MarkdownBoxStore, brain=None, transport: str = "auto", log=print,
        questions: list[tuple[str, str]] | None = None) -> list[Verdict]:
    slim = None
    depts = build_depts(store, brain)
    if transport in ("auto", "slim") and slim_node_up() and os.environ.get("SLIM_SHARED_SECRET"):
        slim = SlimTransport(store.root, log)
        slim.start()
        depts["iso"] = slim.caller()
        log("transport: ISO over A2A over SLIM (agent -> SLIM node -> gateway -> ISO gremlin on :10001); CMPM, college, finaid in-process")
    elif transport == "slim":
        raise SystemExit("SLIM node is not up on 127.0.0.1:46357 (or SLIM_SHARED_SECRET unset). Start: uv run --script gremlin_slim.py node")
    elif transport == "a2a":
        depts["iso"] = over_a2a(f"http://127.0.0.1:{DEPT_PORT}")
        log(f"transport: ISO over A2A over HTTP to a dept_gremlin.py you started on :{DEPT_PORT}; the rest in-process")
    else:
        log("transport: in-process (no SLIM node detected)")
    log(f"boxes: {getattr(store, 'root', None) or store}   student box: {store.path('student')}   departments: {', '.join(depts)}")
    adv = Advocate(store=store, depts=depts)
    verdicts: list[Verdict] = []
    questions = questions or QUESTIONS
    try:
        for label, question in questions:
            if label == "e2":
                try:
                    store.set_field("student", "days_to_deadline", "2")
                except KeyError:
                    store.append("student", 1, "days_to_deadline: 2")
                log(f"\n  student box changed: days_to_deadline: 2 (new information) -> re-ask c1")
            log(f"\n== {label}: {question}")
            v = adv.ask_sync(question, f"demo-{label}")
            show(v, log)
            verdicts.append(v)
            if v.kind == "ASK_STUDENT":
                asked = [(r.dept, f) for r in v.depts for f in r.ask
                         if store.load("student").permission(f, r.dept) == "ask"]
                for dept, f in asked:
                    approve(store, "student", f, dept)
                    log(f"\n  student approves sharing '{f}' with {dept.upper()} (approve_share)")
                if asked:
                    log("  -> re-ask with the approved fields")
                    v = adv.ask_sync(question, f"demo-{label}-b")
                    show(v, log)
                    verdicts.append(v)
        if len(verdicts) >= 2 and questions[0][0] == "c1" and questions[-1][0] == "e2":
            log(f"\n  verdict change on new information: {verdicts[0].kind} (c1) -> {verdicts[-1].kind} (e2)")
    finally:
        if slim:
            slim.stop()
    return verdicts


def prepare_boxes(live: bool) -> MarkdownBoxStore:
    if live:
        return MarkdownBoxStore(BOXES)
    target = HERE / "out" / "demo" / datetime.now().strftime("%Y%m%d-%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    for name in REAL:
        src = MarkdownBoxStore(BOXES).path(name)
        shutil.copy(src, target / f"{name}.md")
    return MarkdownBoxStore(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="use docs/boxes/ directly instead of a fresh copy")
    parser.add_argument("--transport", choices=["auto", "inprocess", "a2a", "slim"], default="auto")
    parser.add_argument("--questions", default="", help="comma-separated ids from QUESTIONS (default: all)")
    parser.add_argument("--store", choices=["markdown", "cubby"], default="markdown",
                        help="cubby: the student box is gremlin-student.md in the real Campus Cubby (CUBBY_URL, CUBBY_TOKEN)")
    args = parser.parse_args()
    wanted = {q.strip() for q in args.questions.split(",") if q.strip()}
    chosen = [q for q in QUESTIONS if not wanted or q[0] in wanted]
    if args.store == "cubby":
        from cubby_store import CubbyBoxStore, CubbyClient
        store = CubbyBoxStore(CubbyClient(os.environ["CUBBY_URL"], os.environ["CUBBY_TOKEN"]), MarkdownBoxStore(BOXES))
        if not store.exists("student"):
            raise SystemExit("No gremlin-student.md in the cubby yet: run `uv run cubby_store.py seed` first.")
    else:
        store = prepare_boxes(args.live)
    run(store, brain=default_brain(), transport=args.transport, questions=chosen)
