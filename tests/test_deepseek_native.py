import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
from deepseek_proxy import DeepSeekProxy

TOKEN = "fixture-relay-token-" + "x" * 32
KEY = "synthetic-provider-secret"


@pytest.fixture
def relay(tmp_path, monkeypatch):
    relay = DeepSeekProxy(KEY, TOKEN, tmp_path / "relay", allowed_tools={"mcp__benchmark__read"}, max_requests=1)
    client = TestClient(relay.app)
    requests = []

    def upstream(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "done"}}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 2}})

    provider = httpx.Client(transport=httpx.MockTransport(upstream))
    monkeypatch.setattr("deepseek_proxy.httpx.Client", lambda **kwargs: provider)
    return relay, client, requests


def post(client, body, token=TOKEN):
    return client.post("/chat/completions", json=body, headers={"Authorization": "Bearer " + token})


@pytest.mark.parametrize("body,token,code", [
    ({"model": "deepseek-flash"}, "wrong", 401),
    ({"model": "other"}, TOKEN, 400),
    ({"model": "deepseek-flash", "tools": [{"function": {"name": "shell"}}]}, TOKEN, 400),
    ({"model": "deepseek-flash", "thinking": {"type": "enabled"}}, TOKEN, 400),
    ({"model": "deepseek-flash", "chat_template_kwargs": {"enable_thinking": True}}, TOKEN, 400),
    ({"model": "deepseek-flash", "thinking": None}, TOKEN, 400),
    (["invalid"], TOKEN, 400),
])
def test_out_of_scope_request_never_reaches_provider(relay, body, token, code):
    proxy, client, requests = relay
    assert post(client, body, token).status_code == code
    assert requests == [] and proxy.records == []


def test_authorized_request_is_nonthinking_and_budget_is_enforced(relay):
    proxy, client, requests = relay
    body = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "test"}],
            "temperature": 1, "seed": 123, "reasoning_effort": "off", "max_tokens": 50000}
    assert post(client, body).status_code == 200
    sent = json.loads(requests[0].content)
    assert sent["thinking"] == {"type": "disabled"}
    assert sent["max_tokens"] == 4096 and sent["temperature"] == 0 and "seed" not in sent
    assert requests[0].url == "https://api.deepseek.com/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer " + KEY
    assert post(client, body).status_code == 400
    assert len(requests) == 1
    assert proxy.records[0]["usage"] == [{"prompt_tokens": 5, "completion_tokens": 2}]
    assert KEY not in "".join(p.read_text() for p in proxy.output.glob("*"))


def test_provider_reasoning_is_recorded_as_error(tmp_path, monkeypatch):
    proxy = DeepSeekProxy(KEY, TOKEN, tmp_path / "relay", allowed_tools=set())
    client = TestClient(proxy.app)
    provider = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
        "choices": [{"message": {"content": KEY, "reasoning_content": "unexpected"}}]})))
    monkeypatch.setattr("deepseek_proxy.httpx.Client", lambda **kwargs: provider)
    assert post(client, {"model": "deepseek-flash"}).status_code == 502
    assert proxy.records[0]["status"] == "error"
    assert proxy.records[0]["reasoning_observed"] is True
    assert KEY not in "".join(p.read_text() for p in proxy.output.glob("*"))


@pytest.mark.parametrize("configuration,decision,dispatch,quarantined", [
    ("baseline", "ALLOW", True, False), ("full", "ALLOW", True, True),
    ("full", "BLOCK", False, False), ("full", "ASK", False, False),
])
def test_shared_tool_path_preserves_dispatch_and_observation(configuration, decision, dispatch, quarantined):
    pytest.importorskip("agentdojo")
    from run_agentdojo import LocalPipeline, FunctionCall
    policy = Path(__file__).resolve().parents[1] / "policies/default.aspolicy"
    pipeline = LocalPipeline(SimpleNamespace(configuration=configuration, model="fixture"), policy.read_text())
    pipeline.decision = lambda *args: {"decision": decision, "reason_codes": ["fixture"]}
    runtime = SimpleNamespace(run_function=lambda *args: ("external content", None))
    pipeline.scanner = SimpleNamespace(scan=lambda *args: (None, SimpleNamespace(labels=["INJECTION_RISK"] if dispatch else [])))
    call = FunctionCall(function="search_emails", args={"recipients": "['a@example.com']"}, id="call1")
    message = pipeline.execute_call("Read mail", runtime, {}, call)
    assert pipeline.calls[0]["simulated_dispatch"] is dispatch
    assert call.args["recipients"] == ["a@example.com"]
    assert ("quarantined" in message["content"][0]["content"]) is quarantined
    assert message["tool_call_id"] == "call1" and message["tool_call"] == call
    if not dispatch:
        assert message["error"].startswith("AgentSentry " + decision)


@pytest.mark.parametrize("broken", [False, True])
def test_native_mcp_bridge_preserves_tool_content_and_invalidates_internal_failures(tmp_path, monkeypatch, broken):
    pytest.importorskip("agentdojo")
    import run_dsh_agentdojo as native
    config = SimpleNamespace(model="fixture", configuration="baseline", sdk_python=Path("unused"), max_steps=2, max_tokens=256)
    pipeline = native.NativePipeline(config, (Path(__file__).resolve().parents[1] / "policies/default.aspolicy").read_text(), KEY, tmp_path)
    runtime = SimpleNamespace(functions={"read_file": object()}, run_function=lambda *args: ("actual benchmark content", None))
    monkeypatch.setattr(native, "_function_to_openai", lambda _: {"function": {
        "name": "read_file", "description": "read", "parameters": {"type": "object", "properties": {}}}})
    if broken:
        pipeline.execute_call = lambda *args: {"content": [{"wrong": "shape"}]}

    def session(directory, sdk_python, app, key, **kwargs):
        with TestClient(app, base_url="http://127.0.0.1:12345") as client:
            response = client.post("/", headers={"Accept": "application/json, text/event-stream"}, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "read_file", "arguments": {}}})
            result = response.json()["result"]
            assert bool(result.get("isError")) is broken
            if not broken:
                assert result["content"][0]["text"] == "actual benchmark content"
        # A completed native loop must not hide an internal bridge failure.
        return {"status": "ok", "result": {"final_response": "finished"}}, [{"status": "ok"}]

    monkeypatch.setattr(native, "run_session", session)
    if broken:
        with pytest.raises(ValueError, match="NATIVE_MCP_BRIDGE_ERROR"):
            pipeline.query("Read", runtime, {})
    else:
        result = pipeline.query("Read", runtime, {})
        assert result[3][-1]["content"][0]["content"] == "finished"
        assert pipeline.calls[0]["simulated_dispatch"] is True


def test_exhausted_credit_stops_further_paid_calls_across_relays(tmp_path, monkeypatch):
    state = tmp_path / "quota-stop.json"
    first = DeepSeekProxy(KEY, TOKEN, tmp_path / "first", allowed_tools=set(), quota_state=state)
    second = DeepSeekProxy(KEY, TOKEN, tmp_path / "second", allowed_tools=set(), quota_state=state)
    one, two = TestClient(first.app), TestClient(second.app)
    calls = []
    def exhausted(request):
        calls.append(request)
        return httpx.Response(402, json={"error": {"message": "Insufficient Balance"}})
    provider = httpx.Client(transport=httpx.MockTransport(exhausted))
    monkeypatch.setattr("deepseek_proxy.httpx.Client", lambda **kwargs: provider)
    assert post(one, {"model": "deepseek-flash"}).status_code == 402
    assert json.loads(state.read_text())["reason"] == "API_BALANCE_EXHAUSTED"
    assert post(two, {"model": "deepseek-flash"}).status_code == 402
    assert len(calls) == 1 and second.records == []
