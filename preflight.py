"""Pre-demo checklist. Run it before judging; it tells you what is broken.

    uv run preflight.py           # keys, boxes, cache, ports, git (no model calls)
    uv run preflight.py --live    # also one tiny call per configured model
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from advocate import DEPARTMENTS
from box import MarkdownBoxStore
from brain import CACHE_DIR, load_env_file, model_list

HERE = Path(__file__).resolve().parent
OK, WARN, BAD = "ok  ", "warn", "FAIL"


def line(status: str, what: str, detail: str = "") -> None:
    print(f"[{status}] {what}" + (f": {detail}" if detail else ""))


def check_keys() -> None:
    load_env_file()
    keys = {k: bool(os.environ.get(k)) for k in ("GROQ_API_KEY", "NVIDIA_NIM_API_KEY", "GEMINI_API_KEY")}
    present = [k for k, v in keys.items() if v]
    line(OK if present else BAD, "model keys", ", ".join(present) or "none found in .env (demo will run the scripted brain)")
    line(OK, "model order", " -> ".join(model_list()))
    line(OK if os.environ.get("GREMLIN_CACHE", "1") not in ("0", "false", "no") else WARN, "replay cache",
         "on" if os.environ.get("GREMLIN_CACHE", "1") not in ("0", "false", "no") else "off (GREMLIN_CACHE=0): every question is a live call")


def check_boxes() -> None:
    store = MarkdownBoxStore()
    student = store.load("student")
    cols = [d.lower() for d in student.departments]
    missing = [d for d in DEPARTMENTS if d not in cols]
    line(OK if not missing else BAD, "student box", f"{store.path('student').name}, {len(student.fields)} fields, permissions over {student.departments}"
         + (f"; missing columns {missing}" if missing else ""))
    for d in DEPARTMENTS:
        if not store.exists(d):
            line(BAD, f"{d} box", "missing")
            continue
        b = store.load(d)
        bad_regex = []
        for e in b.escalations.values():
            m = re.search(r"~\s*(.+)$", e.when)
            if m:
                try:
                    re.compile(m.group(1).split(" and ")[0].split(" or ")[0], re.I)
                except re.error:
                    bad_regex.append(e.id)
        unverified = sum(1 for f in b.facts.values() if not f.verified)
        line(OK if not bad_regex else BAD, f"{d} box",
             f"{len(b.facts)} facts ({unverified} unverified), {len(b.escalations)} triggers, topics {'yes' if b.meta.get('topics') else 'NO'}"
             + (f"; bad regex in {bad_regex}" if bad_regex else ""))
    logs = sum(1 for d in DEPARTMENTS + ("student",) for l in (store.load(d).section(5 if d != "student" else 4) or type("S", (), {"lines": []})).lines if "SESSION" in l)
    line(OK if logs == 0 else WARN, "session logs in docs/boxes", "clean" if logs == 0 else f"{logs} lines; `git checkout docs/boxes` before a fresh demo")


def check_cache() -> None:
    n = len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0
    line(OK if n >= 12 else WARN, "replay cache entries", f"{n} in {CACHE_DIR.relative_to(HERE)}" + ("" if n >= 12 else "; run `uv run demo.py --live` once so the demo is instant"))


def port(host: str, p: int) -> bool:
    try:
        with socket.create_connection((host, p), timeout=0.4):
            return True
    except OSError:
        return False


def check_ports() -> None:
    line(OK if port("127.0.0.1", 46357) else WARN, "SLIM node :46357", "up" if port("127.0.0.1", 46357) else "not running (demo falls back to in-process; `uv run --script prototypes/slim/gremlin_slim.py node`)")
    line(OK if os.environ.get("SLIM_SHARED_SECRET") else WARN, "SLIM_SHARED_SECRET", "set" if os.environ.get("SLIM_SHARED_SECRET") else "unset (needed for --transport slim)")
    line(OK if port("127.0.0.1", 8080) else WARN, "gremlin_app :8080", "up" if port("127.0.0.1", 8080) else "not running (`DEMO_TOKEN=judge LOCAL_HTTP=1 uv run uvicorn gremlin_app:app --port 8080 --no-access-log`)")
    line(OK if os.environ.get("DEMO_TOKEN") else WARN, "DEMO_TOKEN", "set" if os.environ.get("DEMO_TOKEN") else "unset (judge link needs it)")


def check_site() -> None:
    line(OK if (HERE / "site.html").exists() else BAD, "site.html", "present" if (HERE / "site.html").exists() else "missing: the app serves it at /")
    try:
        import httpx
        r = httpx.get((os.environ.get("CUBBY_URL") or "https://cubby.bayleaf.dev").rstrip("/") + "/.well-known/agent-card.json", timeout=6)
        line(OK if r.status_code == 200 else WARN, "Campus Cubbies", f"agent card {r.status_code}")
    except Exception as exc:
        line(WARN, "Campus Cubbies", f"not reachable from here ({type(exc).__name__}); students can't pair until it is")


def check_git() -> None:
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=HERE).stdout.strip()
        ahead = subprocess.run(["git", "rev-list", "--count", f"origin/{branch}..HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
        dirty = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=HERE).stdout.strip().splitlines()
    except Exception as exc:  # not a git checkout, or git missing
        line(WARN, "git", str(exc)[:80])
        return
    line(OK if ahead in ("", "0") else WARN, "git", f"branch {branch}, {ahead or 0} unpushed commit(s), {len(dirty)} dirty file(s)")


def check_models_live() -> None:
    from brain import LiteLLMBrain
    schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
    for model in model_list():
        brain = LiteLLMBrain(models=[model], timeout=30)
        t0 = time.time()
        out = brain.complete("Reply with JSON only.", 'Return {"ok": true}', schema)
        dt = time.time() - t0
        err = next((a.get("error", "") for a in brain.last.get("attempts", []) if not a.get("ok")), "")
        line(OK if out else BAD, model, f"{dt:.1f}s" + (f" {err[:100]}" if err else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="one tiny call per configured model")
    args = parser.parse_args()
    check_keys()
    check_boxes()
    check_cache()
    check_site()
    check_ports()
    check_git()
    if args.live:
        check_models_live()
