"""Brain: the one place a model is called. Stateless by construction.

    brain.complete(system, user, schema) -> dict | None

Callers build `system` and `user` from the current box only. A Brain never
keeps history, never sees a previous call, and returns None when the model
could not produce JSON that conforms to `schema` within one retry.

LiteLLMBrain: groq/openai/gpt-oss-120b, then nvidia_nim/nvidia/nemotron-3-super-120b-a12b,
then gemini/gemini-2.5-flash (GREMLIN_MODELS overrides), temperature 0, JSON mode.
CachedBrain: replay cache keyed by the prompt hash, so demos are instant and identical.
ScriptedBrain: canned answers for tests and offline demos.
BayleafBrain: TODO stub for the Bayleaf runtime.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

PRIMARY = "groq/openai/gpt-oss-120b"
FALLBACK = "nvidia_nim/nvidia/nemotron-3-super-120b-a12b"
THIRD = "gemini/gemini-2.5-flash"
MAX_TOKENS = 2048
CACHE_DIR = Path(__file__).resolve().parent / "out" / "cache"


def model_list() -> list[str]:
    """GREMLIN_MODELS="groq/...,nvidia_nim/...,gemini/..." overrides the default order.
    Only models whose provider key is present are kept, so a missing key never costs a call."""
    raw = os.environ.get("GREMLIN_MODELS")
    models = [m.strip() for m in raw.split(",") if m.strip()] if raw else [PRIMARY, FALLBACK, THIRD]
    keys = {"groq/": "GROQ_API_KEY", "nvidia_nim/": "NVIDIA_NIM_API_KEY", "gemini/": "GEMINI_API_KEY"}
    out = []
    for m in models:
        needed = next((k for prefix, k in keys.items() if m.startswith(prefix)), None)
        if needed is None or os.environ.get(needed):
            out.append(m)
    return out or [PRIMARY, FALLBACK]

_TYPES = {"object": dict, "array": list, "string": str, "number": (int, float),
          "integer": int, "boolean": bool, "null": type(None)}


def conforms(value: Any, schema: dict) -> bool:
    """Small structural check: type, required, properties, items, enum. No $ref."""
    if "enum" in schema and value not in schema["enum"]:
        return False
    kind = schema.get("type")
    if kind:
        kinds = kind if isinstance(kind, list) else [kind]
        if not any(isinstance(value, _TYPES[k]) for k in kinds if k in _TYPES):
            return False
        if isinstance(value, bool) and "boolean" not in kinds:
            return False
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                return False
        for key, sub in schema.get("properties", {}).items():
            if key in value and not conforms(value[key], sub):
                return False
    if isinstance(value, list) and "items" in schema:
        return all(conforms(v, schema["items"]) for v in value)
    return True


def parse_json_object(text: str) -> dict | None:
    """Accept a bare object, or an object wrapped in prose/code fences."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1]):
        if candidate.startswith("{"):
            try:
                value = json.loads(candidate)
            except ValueError:
                continue
            if isinstance(value, dict):
                return value
    return None


class Brain(Protocol):
    def complete(self, system: str, user: str, schema: dict) -> dict | None: ...


class ScriptedBrain:
    """Returns queued answers in order; records every prompt it saw."""

    def __init__(self, answers: list[dict | None] | None = None, default: dict | None = None):
        self.answers = list(answers or [])
        self.default = default
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, schema: dict) -> dict | None:
        self.calls.append({"system": system, "user": user, "schema": schema})
        answer = self.answers.pop(0) if self.answers else self.default
        return answer if answer is not None and conforms(answer, schema) else None


class LiteLLMBrain:
    def __init__(self, models: list[str] | None = None, temperature: float = 0.0,
                 max_tokens: int = MAX_TOKENS, timeout: float = 60.0, completion=None):
        self.models = models or [PRIMARY, FALLBACK]
        self.temperature, self.max_tokens, self.timeout = temperature, max_tokens, timeout
        self._completion = completion
        self.last: dict = {}

    def _call(self, **kwargs):
        if self._completion is None:
            import litellm
            litellm.suppress_debug_info = True
            litellm.drop_params = True  # fallback providers may reject reasoning_effort
            self._completion = litellm.completion
        return self._completion(**kwargs)

    def complete(self, system: str, user: str, schema: dict) -> dict | None:
        """One attempt per model: primary, then one retry on the fallback, then None."""
        self.last = {"attempts": []}
        for model in self.models:
            attempt = {"model": model}
            try:
                response = self._call(
                    model=model, temperature=self.temperature, max_tokens=self.max_tokens,
                    timeout=self.timeout, response_format={"type": "json_object"},
                    reasoning_effort="low",
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                text = response.choices[0].message.content
                value = parse_json_object(text)
                attempt["ok"] = value is not None and conforms(value, schema)
                if attempt["ok"]:
                    self.last["attempts"].append(attempt)
                    self.last["model"] = model
                    return value
                attempt["error"] = "invalid or non-conforming JSON"
            except Exception as exc:  # provider, network, auth: fall through to the next model
                attempt["ok"], attempt["error"] = False, f"{type(exc).__name__}: {exc}"[:300]
            self.last["attempts"].append(attempt)
        return None


class CachedBrain:
    """Replay cache around any Brain: the same (system, user, schema) returns the same
    answer without a model call. Keyed by a hash of the prompt, so a changed box or a
    changed context is a different key. Session ids are not in the prompt, so a demo
    replays identically. GREMLIN_CACHE=0 turns it off; GREMLIN_CACHE_DIR moves it."""

    def __init__(self, inner: Brain, directory: str | os.PathLike | None = None):
        self.inner = inner
        self.dir = Path(directory or os.environ.get("GREMLIN_CACHE_DIR") or CACHE_DIR)
        self.hits = 0
        self.misses = 0

    @property
    def last(self) -> dict:
        return getattr(self.inner, "last", {}) or {}

    def key(self, system: str, user: str, schema: dict) -> str:
        import hashlib
        blob = json.dumps([system, user, schema], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def complete(self, system: str, user: str, schema: dict) -> dict | None:
        path = self.dir / f"{self.key(system, user, schema)}.json"
        if path.exists():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if conforms(value, schema):
                    self.hits += 1
                    if hasattr(self.inner, "last"):
                        self.inner.last = {"attempts": [{"model": "cache", "ok": True}], "model": "cache"}
                    return value
            except (ValueError, OSError):
                pass
        value = self.inner.complete(system, user, schema)
        self.misses += 1
        if value is not None:
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
            except OSError:
                pass
        return value


class BayleafBrain:
    """TODO: Bayleaf runtime. Same contract: complete(system, user, schema) -> dict | None.

    Wire once the Bayleaf repo is available: construct the client here, send
    system+user as one stateless request with a JSON output constraint built
    from `schema`, parse with parse_json_object, check with conforms, one retry.
    """

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    def complete(self, system: str, user: str, schema: dict) -> dict | None:
        raise NotImplementedError("BayleafBrain is not wired yet; use LiteLLMBrain or ScriptedBrain.")


def load_env_file(path: str | os.PathLike | None = None) -> None:
    """Load KEY=value lines from a .env file into os.environ without overriding."""
    candidates = [Path(path)] if path else [Path(__file__).resolve().parent / ".env",
                                             Path(__file__).resolve().parent.parent / ".env"]
    for p in candidates:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return


def default_brain() -> Brain:
    """LiteLLMBrain (wrapped in the replay cache unless GREMLIN_CACHE=0) when a provider
    key is present, else a ScriptedBrain that returns None."""
    load_env_file()
    if os.environ.get("GROQ_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        brain: Brain = LiteLLMBrain(models=model_list())
        if os.environ.get("GREMLIN_CACHE", "1") not in ("0", "false", "no"):
            brain = CachedBrain(brain)
        return brain
    return ScriptedBrain()
