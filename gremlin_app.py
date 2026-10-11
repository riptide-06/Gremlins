"""Gremlin Labs: the student's gremlin as a web app and an MCP server, built on Campus Cubbies.

Sign-in is Campus Cubbies' own pairing (prototypes/cubbies/SKILL.md): this app asks the
cubby service for a device code, the student approves it with their UCSC Google account
on cubby.bayleaf.dev, and the bearer that comes back is the student's own credential. The
student box then lives as `gremlin-student.md` in the student's My Cubby folder in Drive
(cubby_store.CubbyBoxStore); department boxes stay on this server. No Google OAuth, no
Firestore, no second login: Campus Cubbies is the boundary, this is what argues inside it.

    DEMO_TOKEN=judge LOCAL_HTTP=1 uv run uvicorn gremlin_app:app --port 8080 --no-access-log
    open /                       the site (sign in with your UCSC account via Campus Cubbies)
    open /demo?token=judge       judge mode: the synthetic student, no account needed

Routes: /, /demo, /health, /api/connect/start, /api/connect/poll, /api/me, /api/logout,
/api/ask, /api/approve, /api/set, /api/permission, /api/box, /api/open_items, /api/reset,
and /mcp (session cookie, or `Authorization: Bearer <your Campus Cubbies token>`).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import time

import httpx
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

from advocate import DEPARTMENTS, Advocate, build_depts, dept_urls_from_env
from box import MarkdownBoxStore, seed_student_box
from cubby_store import CubbyAuthError, CubbyBoxStore, CubbyClient, CubbyError
from mcp_server import CURRENT_ADVOCATE, build_mcp

logger = logging.getLogger("gremlin")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

DEMO_UID = "demo"
_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
SITE = Path(__file__).with_name("site.html")
CSP = ("default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


def emit(event, **fields):
    logger.info(json.dumps({"event": event, **fields}))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class Settings:
    url: str = os.getenv("PUBLIC_URL", "http://localhost:8080").rstrip("/")
    cubby_url: str = os.getenv("CUBBY_URL", "https://cubby.bayleaf.dev").rstrip("/")
    session_secret: str = os.getenv("SESSION_SECRET", "")
    local_http: bool = os.getenv("LOCAL_HTTP") == "1"
    box_dir: str = os.getenv("BOX_DIR", str(Path(__file__).with_name("docs") / "boxes"))   # tracked boxes: served from a copy under out/
    demo_token: str = os.getenv("DEMO_TOKEN", "")
    demo_box: str = os.getenv("DEMO_BOX", "student")
    hello_ttl: int = 300
    iso_url: str = os.getenv("ISO_URL", "")


@dataclass
class Identity:
    identity: str
    folder_url: str
    roles: list = field(default_factory=list)


class Pairing:
    """Campus Cubbies device pairing from this server: start, then poll the exchange."""

    def __init__(self, origin: str, http: httpx.Client):
        self.origin, self.http = origin.rstrip("/"), http

    def start(self) -> dict:
        r = self.http.post(self.origin + "/auth/device")
        if r.status_code != 200:
            raise CubbyError(f"pairing start failed ({r.status_code})")
        data = r.json()
        complete = str(data.get("verification_uri_complete", ""))
        if str(data.get("verification_uri", "")) != self.origin + "/connect" or not complete.startswith(self.origin + "/connect?code="):
            raise CubbyError("pairing page is not on the Campus Cubbies origin")
        return {"device_code": data["device_code"], "user_code": data["user_code"], "verification_uri_complete": complete,
                "interval": int(data.get("interval", 5)), "expires_in": int(data.get("expires_in", 600))}

    def poll(self, user_code: str, device_code: str) -> dict:
        r = self.http.post(self.origin + "/auth/token", data={"user_code": user_code, "device_code": device_code},
                           headers={"Content-Type": "application/x-www-form-urlencoded"})
        if r.status_code == 200:
            data = r.json()
            return {"status": "connected", "access_token": data["access_token"], "expires_in": int(data.get("expires_in", 172800))}
        if r.status_code == 400:
            return {"status": r.json().get("error", "invalid_request")}
        if r.status_code == 503:
            return {"status": "unavailable"}
        raise CubbyError(f"pairing exchange failed ({r.status_code})")


DEFAULT_BOX_DIR = str(Path(__file__).with_name("docs") / "boxes")
WORK_BOX_DIR = Path(__file__).with_name("out") / "boxes"


def working_boxes(box_dir: str) -> MarkdownBoxStore:
    """Every answer appends a session line to the department boxes and the judge's student box.
    When the boxes are the tracked ones under docs/, work on a copy under out/ (gitignored) so a
    local run never dirties the repository; an explicit BOX_DIR is used as is."""
    if Path(box_dir).resolve() != Path(DEFAULT_BOX_DIR).resolve():
        return MarkdownBoxStore(box_dir)
    WORK_BOX_DIR.mkdir(parents=True, exist_ok=True)
    for src in Path(box_dir).glob("*.md"):
        (WORK_BOX_DIR / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return MarkdownBoxStore(str(WORK_BOX_DIR))


def create_app(settings: Settings | None = None, boxes: MarkdownBoxStore | None = None, brain=None,
               cubby_http: httpx.Client | None = None) -> Starlette:
    settings = settings or Settings()
    boxes = boxes or working_boxes(settings.box_dir)
    http = cubby_http or httpx.Client(timeout=30)
    pairing = Pairing(settings.cubby_url, http)
    urls = dept_urls_from_env()
    if settings.iso_url:
        urls["iso"] = settings.iso_url
    depts = build_depts(boxes, brain, urls)
    hello_cache: dict[str, tuple[Identity, float]] = {}

    # ---- identity and stores -----------------------------------------------------------
    def identity_for(token: str) -> Identity | None:
        """hello with the student's own Campus Cubbies token; cached briefly, keyed by its hash."""
        key = digest(token)
        hit = hello_cache.get(key)
        if hit and hit[1] > time.time():
            return hit[0]
        try:
            me = CubbyClient(settings.cubby_url, token, http=http).hello()
        except CubbyError:
            return None
        ident = Identity(str(me.get("identity", "")), str((me.get("cubby") or {}).get("folder_url", "")), list(me.get("roles", [])))
        hello_cache[key] = (ident, time.time() + settings.hello_ttl)
        return ident

    def store_for(uid: str, token: str | None):
        if uid == DEMO_UID or not token:
            return boxes
        return CubbyBoxStore(CubbyClient(settings.cubby_url, token, http=http), boxes)

    def advocate_for(uid: str, token: str | None) -> Advocate:
        return Advocate(store=store_for(uid, token), student_box=settings.demo_box if uid == DEMO_UID else "student", depts=depts)

    def session_caller(request) -> tuple[str, str | None] | None:
        uid = request.session.get("uid")
        if uid == DEMO_UID:
            return DEMO_UID, None
        token = request.session.get("cubby_token")
        if uid == "cubby" and token and request.session.get("expires", 0) > time.time():
            return "cubby", token
        return None

    async def api_caller(request) -> tuple[str, str | None] | None:
        """Who is calling /api: the signed-in session (same-origin, marked request) or a Campus Cubbies bearer."""
        caller = session_caller(request)
        if caller:
            origin = request.headers.get("origin") or request.headers.get("referer", "")
            if request.headers.get("x-gremlin") != "1" or (origin and not origin.startswith(settings.url)):
                return None
            return caller
        auth = request.headers.get("authorization", "")
        raw = auth[7:] if auth.startswith("Bearer ") else ""
        if 32 <= len(raw) <= 128 and await asyncio.to_thread(identity_for, raw):
            return "cubby", raw
        return None

    def denied():
        return JSONResponse({"error": "Sign in with your UCSC account through Campus Cubbies, open the judge link, or send your Campus Cubbies bearer."}, status_code=401)

    async def body_of(request) -> dict:
        try:
            data = await request.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    # ---- pages ---------------------------------------------------------------------------
    async def site(request):
        return HTMLResponse(SITE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin",
                                                                       "X-Content-Type-Options": "nosniff", "Content-Security-Policy": CSP})

    async def chat_redirect(request):
        return RedirectResponse("/#chat", status_code=303)

    async def demo(request):
        token = request.query_params.get("token", "")
        if not settings.demo_token or not hmac.compare_digest(token, settings.demo_token):
            return RedirectResponse("/#nojudge", status_code=303)
        request.session.clear()
        request.session.update({"uid": DEMO_UID, "csrf": secrets.token_urlsafe(32)})
        if not getattr(request.app.state, "demo_pristine", None) and boxes.exists(settings.demo_box):
            request.app.state.demo_pristine = {name: boxes.load(name).text for name in (settings.demo_box, *depts) if boxes.exists(name)}
        emit("demo_login")
        return RedirectResponse("/#chat", status_code=303)

    async def health(request):
        return JSONResponse({"ok": True, "departments": list(depts)})

    # ---- connect: Campus Cubbies pairing --------------------------------------------------
    async def connect_start(request):
        if request.headers.get("x-gremlin") != "1":
            return denied()
        try:
            p = await asyncio.to_thread(pairing.start)
        except (CubbyError, httpx.HTTPError, ValueError, KeyError) as exc:
            emit("pairing_start_failed", reason=type(exc).__name__)
            return JSONResponse({"error": "Campus Cubbies is not reachable right now. Try again in a minute."}, status_code=503)
        request.session["pairing"] = {"device_code": p["device_code"], "user_code": p["user_code"], "interval": p["interval"],
                                      "deadline": time.time() + p["expires_in"], "last": 0.0}
        emit("pairing_started")
        return JSONResponse({"verification_uri_complete": p["verification_uri_complete"], "user_code": p["user_code"],
                             "interval": p["interval"], "expires_in": p["expires_in"]})

    async def connect_poll(request):
        if request.headers.get("x-gremlin") != "1":
            return denied()
        p = request.session.get("pairing")
        if not p:
            return JSONResponse({"status": "none", "error": "Start a connection first."}, status_code=400)
        if time.time() > p["deadline"]:
            request.session.pop("pairing", None)
            return JSONResponse({"status": "expired", "error": "The approval window closed. Start again."}, status_code=400)
        if time.time() - p.get("last", 0) < max(1, p["interval"] - 1):
            return JSONResponse({"status": "authorization_pending"})
        p["last"] = time.time()
        request.session["pairing"] = p
        try:
            result = await asyncio.to_thread(pairing.poll, p["user_code"], p["device_code"])
        except (CubbyError, httpx.HTTPError, ValueError, KeyError) as exc:
            emit("pairing_poll_failed", reason=type(exc).__name__)
            return JSONResponse({"status": "unavailable", "error": "Campus Cubbies is not reachable right now."}, status_code=503)
        status = result["status"]
        if status == "slow_down":
            p["interval"] += 5
            request.session["pairing"] = p
            return JSONResponse({"status": "authorization_pending", "interval": p["interval"]})
        if status in ("authorization_pending", "unavailable"):
            return JSONResponse({"status": status})
        if status != "connected":
            request.session.pop("pairing", None)
            return JSONResponse({"status": status, "error": "The approval window closed or the code was already used. Start again."}, status_code=400)
        token = result["access_token"]
        ident = await asyncio.to_thread(identity_for, token)
        if not ident:
            return JSONResponse({"status": "error", "error": "Connected, but Campus Cubbies did not answer hello."}, status_code=503)
        request.session.clear()
        request.session.update({"uid": "cubby", "cubby_token": token, "identity": ident.identity, "folder_url": ident.folder_url,
                                "expires": time.time() + result["expires_in"] - 60, "csrf": secrets.token_urlsafe(32)})
        store = store_for("cubby", token)
        try:
            created = await asyncio.to_thread(seed_student_box, store, "student", ident.identity,
                                              ident.identity.split("@")[0] or "student", ident.identity)
        except CubbyError as exc:
            emit("student_box_seed_failed", reason=str(exc)[:80])
            created = False
        emit("cubby_connected", created=created)
        return JSONResponse({"status": "connected", "identity": ident.identity, "folder_url": ident.folder_url, "created": created})

    async def me(request):
        caller = session_caller(request)
        base = {"public_url": settings.url, "cubby_url": settings.cubby_url,
                "departments": {d: boxes.load(d).meta.get("name", d.upper()) for d in depts if boxes.exists(d)},
                "demo_available": bool(settings.demo_token)}
        if not caller:
            return JSONResponse({"connected": False, **base})
        uid, token = caller
        if uid == DEMO_UID:
            return JSONResponse({"connected": True, "demo": True, "identity": "demo student (synthetic)", "folder_url": "", **base})
        return JSONResponse({"connected": True, "demo": False, "identity": request.session.get("identity", ""),
                             "folder_url": request.session.get("folder_url", ""), **base})

    async def logout(request):
        request.session.clear()
        return JSONResponse({"ok": True})

    # ---- the gremlin ---------------------------------------------------------------------
    def cubby_failure(exc: Exception, request=None):
        emit("cubby_error", reason=type(exc).__name__)
        if isinstance(exc, CubbyAuthError):
            # Revoked on Campus Cubbies (revoke_agents) or expired: drop the session so the site asks to reconnect.
            if request is not None and request.session.get("uid") == "cubby":
                request.session.clear()
            return JSONResponse({"error": "Campus Cubbies no longer accepts this connection. Connect again.", "reconnect": True}, status_code=401)
        return JSONResponse({"error": f"Your cubby did not answer: {str(exc)[:160]}"}, status_code=503)

    async def api_ask(request):
        caller = await api_caller(request)
        if not caller:
            return denied()
        body = await body_of(request)
        question = str(body.get("question", "")).strip()[:4000]
        if not question:
            return JSONResponse({"error": "question is required"}, status_code=400)
        declined = {str(f) for f in (body.get("declined") or []) if _FIELD.match(str(f))}
        emit("api_ask", demo=caller[0] == DEMO_UID)
        try:
            verdict = await advocate_for(*caller).ask(question, declined=declined or None)
        except (CubbyError, FileNotFoundError, httpx.HTTPError) as exc:
            return cubby_failure(exc, request)
        return JSONResponse(verdict.to_dict())

    async def api_approve(request):
        caller = await api_caller(request)
        if not caller:
            return denied()
        body = await body_of(request)
        field_name, dept = str(body.get("field", "")).strip(), str(body.get("dept", "")).strip()
        if not _FIELD.match(field_name) or not _FIELD.match(dept):
            return JSONResponse({"ok": False, "error": "bad field or dept"}, status_code=400)
        from wall import approve as wall_approve
        adv = advocate_for(*caller)
        try:
            ok = await asyncio.to_thread(wall_approve, adv.store, adv.student_box, field_name, dept)
        except (CubbyError, FileNotFoundError, httpx.HTTPError) as exc:
            return cubby_failure(exc, request)
        return JSONResponse({"ok": ok, "field": field_name, "dept": dept})

    async def api_box(request):
        caller = await api_caller(request)
        if not caller:
            return denied()
        adv = advocate_for(*caller)
        try:
            box = await asyncio.to_thread(adv.store.load, adv.student_box)
        except (CubbyError, FileNotFoundError, httpx.HTTPError) as exc:
            return cubby_failure(exc, request)
        return JSONResponse({"box": box.text[:100_000], "fields": box.fields, "permissions": box.permissions,
                             "departments": box.departments, "preferences": box.preferences,
                             "student": "demo student (synthetic)" if caller[0] == DEMO_UID else request.session.get("identity", "you"),
                             "location": str(adv.store.path(adv.student_box))})

    async def api_set(request):
        caller = await api_caller(request)
        if not caller:
            return denied()
        body = await body_of(request)
        field_name, value = str(body.get("field", "")).strip(), str(body.get("value", "")).strip()[:120]
        if not _FIELD.match(field_name) or "\n" in value or field_name in ("name", "email"):
            return JSONResponse({"ok": False, "error": "bad field"}, status_code=400)
        adv = advocate_for(*caller)
        try:
            try:
                await asyncio.to_thread(adv.store.set_field, adv.student_box, field_name, value)
            except KeyError:
                await asyncio.to_thread(adv.store.append, adv.student_box, 1, f"{field_name}: {value}")
        except (CubbyError, FileNotFoundError, httpx.HTTPError) as exc:
            return cubby_failure(exc, request)
        return JSONResponse({"ok": True, "field": field_name, "value": value})

    async def api_permission(request):
        caller = await api_caller(request)
        if not caller:
            return denied()
        body = await body_of(request)
        field_name, dept, value = str(body.get("field", "")).strip(), str(body.get("dept", "")).strip(), str(body.get("value", "")).strip().lower()
        if not _FIELD.match(field_name) or not re.match(r"^[A-Za-z][A-Za-z0-9_ .]{0,30}$", dept) or value not in ("yes", "no", "ask", "never"):
            return JSONResponse({"ok": False, "error": "bad field, dept, or value"}, status_code=400)
        if field_name in ("name", "email") and value != "never":
            return JSONResponse({"ok": False, "error": "name and email are never shared"}, status_code=400)
        adv = advocate_for(*caller)
        try:
            await asyncio.to_thread(adv.store.set_permission, adv.student_box, field_name, dept, value)
        except KeyError as exc:
            return JSONResponse({"ok": False, "error": f"unknown {exc}"}, status_code=400)
        except (CubbyError, FileNotFoundError, httpx.HTTPError) as exc:
            return cubby_failure(exc, request)
        return JSONResponse({"ok": True, "field": field_name, "dept": dept, "value": value})

    async def api_open_items(request):
        caller = await api_caller(request)
        if not caller:
            return denied()
        try:
            return JSONResponse(await asyncio.to_thread(advocate_for(*caller).open_items))
        except (CubbyError, FileNotFoundError, httpx.HTTPError) as exc:
            return cubby_failure(exc, request)

    async def api_reset(request):
        """Judge mode only: the synthetic student and the department session logs go back to the start."""
        caller = await api_caller(request)
        if not caller:
            return denied()
        pristine = getattr(request.app.state, "demo_pristine", None)
        if caller[0] != DEMO_UID or not pristine:
            return JSONResponse({"ok": False, "error": "reset is only for the demo student"}, status_code=400)
        for name, text in pristine.items():
            await asyncio.to_thread(boxes.write, name, text)
        emit("demo_reset")
        return JSONResponse({"ok": True, "restored": sorted(pristine)})

    # ---- MCP ---------------------------------------------------------------------------
    class McpGuard:
        """/mcp is reachable with the signed-in session cookie or with the student's own Campus
        Cubbies bearer. The caller's advocate is request-local; nothing is held between calls."""

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http" or not scope["path"].startswith("/mcp"):
                await self.app(scope, receive, send)
                return
            sess = scope.get("session") or {}
            caller = None
            auth = dict(scope["headers"]).get(b"authorization", b"")
            if auth:
                # An explicit credential decides on its own; a cookie riding along cannot rescue a bad bearer.
                raw = auth[7:] if auth.startswith(b"Bearer ") else b""
                if 32 <= len(raw) <= 128:
                    try:
                        token = raw.decode("ascii")
                    except UnicodeDecodeError:
                        token = ""
                    if token and await asyncio.to_thread(identity_for, token):
                        caller = ("cubby", token)
            elif sess.get("uid") == DEMO_UID:
                caller = (DEMO_UID, None)
            elif sess.get("uid") == "cubby" and sess.get("cubby_token") and sess.get("expires", 0) > time.time():
                caller = ("cubby", sess["cubby_token"])
            if not caller:
                emit("mcp_authentication_denied")
                await JSONResponse({"error": "Send your Campus Cubbies bearer (Authorization: Bearer ...) or sign in on the site first."},
                                   status_code=401)(scope, receive, send)
                return
            marker = CURRENT_ADVOCATE.set(advocate_for(*caller))
            try:
                emit("mcp_request", demo=caller[0] == DEMO_UID)
                await self.app(scope, receive, send)
            finally:
                CURRENT_ADVOCATE.reset(marker)

    mcp = build_mcp(CURRENT_ADVOCATE.get, stateless_http=True, json_response=True, streamable_http_path="/mcp",
                    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    mcp_routes = mcp.streamable_http_app().routes
    app = Starlette(routes=[Route("/", site), Route("/chat", chat_redirect), Route("/demo", demo), Route("/health", health), Route("/healthz", health),
                            Route("/api/connect/start", connect_start, methods=["POST"]), Route("/api/connect/poll", connect_poll, methods=["POST"]),
                            Route("/api/me", me), Route("/api/logout", logout, methods=["POST"]),
                            Route("/api/ask", api_ask, methods=["POST"]), Route("/api/approve", api_approve, methods=["POST"]),
                            Route("/api/set", api_set, methods=["POST"]), Route("/api/permission", api_permission, methods=["POST"]),
                            Route("/api/box", api_box), Route("/api/open_items", api_open_items), Route("/api/reset", api_reset, methods=["POST"]),
                            *mcp_routes],
                    lifespan=lambda _app: mcp.session_manager.run())
    app.add_middleware(McpGuard)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret or secrets.token_urlsafe(48),
                       https_only=not settings.local_http, same_site="lax", max_age=172800)
    app.state.mcp = mcp
    app.state.boxes = boxes
    app.state.settings = settings
    return app


app = create_app()
