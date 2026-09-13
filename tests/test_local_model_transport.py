"""Verify mode/budget isolation and honest failure accounting without a service."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import httpx
from local_model import completion, structured_completion


def config(**changes):
    return SimpleNamespace(**{
        "url": "http://127.0.0.1:18080/v1", "model": "local-test", "seed": 0,
        "max_tokens": 128, "guard_max_tokens": 256, "guard_thinking": True,
        "guard_format": "json_schema", "request_timeout": 300, **changes,
    })


def response(finish="stop"):
    raw = {"choices": [{"finish_reason": finish, "message": {
        "role": "assistant", "content": '{"injected":false}', "reasoning_content": "fixture",
    }}]}
    return raw, Mock(json=lambda: raw, raise_for_status=lambda: None)


def test_guard_thinking_does_not_enable_actor_thinking_or_mutate_budget(monkeypatch):
    raw, result = response(); calls = []
    monkeypatch.setattr(httpx, "post", lambda url, **kw: calls.append((url, kw)) or result)
    cfg = config(); original = vars(cfg).copy(); records = []
    messages = [{"role": "system", "content": "inspect"}, {"role": "user", "content": "untrusted"}]
    schema = {"type": "object", "properties": {"injected": {"type": "boolean"}}}
    assert structured_completion(cfg, "detect_injection", messages, schema, records) == {"injected": False}
    trace = []; completion(cfg, messages, trace)
    guard, actor = [c[1] for c in calls]
    assert guard["json"]["chat_template_kwargs"] == {"enable_thinking": True}
    assert actor["json"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert guard["json"]["max_tokens"] == 256 and actor["json"]["max_tokens"] == 128
    assert guard["timeout"] == actor["timeout"] == 300
    assert not guard["trust_env"] and not actor["trust_env"]
    assert vars(cfg) == original and messages[0]["content"] == "inspect"
    assert records[0]["responses"] == [raw] and trace == [raw]


@pytest.mark.parametrize("options", [
    {"enable_thinking": "true"}, {"enable_thinking": 1}, {"request_timeout": True},
    {"request_timeout": 0}, {"request_timeout": 601}, {"request_timeout": float("nan")},
])
def test_invalid_options_never_reach_the_endpoint(monkeypatch, options):
    post = Mock(); monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(ValueError, match="INVALID_LOCAL_INFERENCE_OPTIONS"):
        completion(config(**options), [], [])
    post.assert_not_called()


def test_reasoning_budget_truncation_keeps_raw_response_and_remains_error(monkeypatch):
    raw, result = response("length")
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: result)
    records = []
    with pytest.raises(ValueError, match="MODEL_OUTPUT_TRUNCATED"):
        structured_completion(config(), "detect_injection", [{"role": "system", "content": "inspect"}], {}, records)
    assert records[0]["responses"] == [raw]


def test_new_options_do_not_allow_a_cloud_endpoint(monkeypatch):
    post = Mock(); monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(ValueError, match="ONLY_LOCAL_MODEL_ENDPOINT_ALLOWED"):
        completion(config(url="https://example.test/v1"), [], [])
    post.assert_not_called()
