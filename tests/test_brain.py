"""Brain contract: JSON mode, schema check, one retry on the fallback, then None."""
import json
from types import SimpleNamespace

from brain import LiteLLMBrain, ScriptedBrain, conforms, parse_json_object, PRIMARY, FALLBACK

SCHEMA = {"type": "object", "required": ["answer", "cites"],
          "properties": {"answer": {"type": "string"}, "cites": {"type": "array", "items": {"type": "string"}},
                         "confidence": {"type": "number"}}}


def reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_conforms():
    assert conforms({"answer": "x", "cites": ["F-01"], "confidence": 0.5}, SCHEMA)
    assert not conforms({"answer": "x"}, SCHEMA)
    assert not conforms({"answer": 1, "cites": []}, SCHEMA)
    assert not conforms({"answer": "x", "cites": [1]}, SCHEMA)
    assert not conforms({"answer": "x", "cites": [], "confidence": True}, SCHEMA)
    assert conforms("in_scope", {"type": "string", "enum": ["in_scope", "out_of_scope"]})
    assert not conforms("maybe", {"type": "string", "enum": ["in_scope", "out_of_scope"]})


def test_parse_json_object_tolerates_fences_and_prose():
    assert parse_json_object('{"a": 1}') == {"a": 1}
    assert parse_json_object('Sure:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('[1,2]') is None
    assert parse_json_object('nope') is None
    assert parse_json_object(None) is None


def test_scripted_brain_checks_schema_and_records_calls():
    brain = ScriptedBrain([{"answer": "a", "cites": []}, {"bad": True}], default={"answer": "d", "cites": []})
    assert brain.complete("s", "u", SCHEMA) == {"answer": "a", "cites": []}
    assert brain.complete("s", "u", SCHEMA) is None
    assert brain.complete("s", "u", SCHEMA) == {"answer": "d", "cites": []}
    assert brain.calls[0]["system"] == "s" and len(brain.calls) == 3


def test_litellm_brain_uses_primary_with_json_mode_and_temperature_zero():
    calls = []
    def fake(**kw):
        calls.append(kw)
        return reply(json.dumps({"answer": "ok", "cites": ["F-01"]}))
    brain = LiteLLMBrain(completion=fake)
    assert brain.complete("SYS", "USR", SCHEMA) == {"answer": "ok", "cites": ["F-01"]}
    assert len(calls) == 1 and calls[0]["model"] == PRIMARY
    assert calls[0]["temperature"] == 0 and calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USR"}]
    assert brain.last["model"] == PRIMARY


def test_litellm_brain_retries_once_on_fallback_then_none():
    calls = []
    def flaky(**kw):
        calls.append(kw["model"])
        if kw["model"] == PRIMARY:
            raise RuntimeError("rate limited")
        return reply("not json at all")
    brain = LiteLLMBrain(completion=flaky)
    assert brain.complete("s", "u", SCHEMA) is None
    assert calls == [PRIMARY, FALLBACK]
    assert [a["ok"] for a in brain.last["attempts"]] == [False, False]
    assert "rate limited" in brain.last["attempts"][0]["error"]


def test_litellm_brain_nonconforming_primary_falls_back():
    def fake(**kw):
        return reply(json.dumps({"answer": 42} if kw["model"] == PRIMARY else {"answer": "x", "cites": []}))
    brain = LiteLLMBrain(completion=fake)
    assert brain.complete("s", "u", SCHEMA) == {"answer": "x", "cites": []}
    assert brain.last["model"] == FALLBACK


def test_brain_is_stateless():
    seen = []
    def fake(**kw):
        seen.append(len(kw["messages"]))
        return reply('{"answer": "x", "cites": []}')
    brain = LiteLLMBrain(completion=fake)
    brain.complete("s1", "u1", SCHEMA)
    brain.complete("s2", "u2", SCHEMA)
    assert seen == [2, 2]  # never accumulates history
