import json
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
from memory_runtime import MemoryRuntime
from native_memory import bearer_app, codex_command, codex_environment, memory_mcp

POLICY = Path(__file__).resolve().parents[1] / "policies/default.aspolicy"
TOKEN = "fixture-token-not-a-secret-" + "x" * 32


@pytest.fixture
def backend(tmp_path):
    runtime = MemoryRuntime(tmp_path / "case", POLICY)
    runtime.begin("Summarize the document.", [{"field": "context", "text": "External test document."}])
    yield runtime
    runtime.close()


def rpc(client, method, params):
    return client.post("/", headers={"Authorization": "Bearer " + TOKEN,
        "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


def call(client, tool, arguments):
    response = rpc(client, "tools/call", {"name": tool, "arguments": arguments})
    assert response.status_code == 200
    return response.json()["result"]


def value(result):
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_mcp_auth_and_no_operator_or_evaluator_tools(backend):
    server = memory_mcp(backend)
    with TestClient(bearer_app(server.streamable_http_app(), TOKEN), base_url="http://127.0.0.1:12345") as client:
        assert client.post("/", json={}).status_code == 401
        tools = rpc(client, "tools/list", {}).json()["result"]["tools"]
        assert {t["name"] for t in tools} == {"read_external_context", "write_memory"}
        for tool in ("approve", "snapshot", "followup", "recall_memory"):
            assert call(client, tool, {}).get("isError")
        assert backend.snapshot() == []
        assert "External test document." in json.dumps(call(client, "read_external_context", {}))


def test_pending_write_through_mcp_and_stale_session_cannot_write(backend):
    server = memory_mcp(backend)
    with TestClient(bearer_app(server.streamable_http_app(), TOKEN), base_url="http://127.0.0.1:12345") as client:
        arguments = {"name": "fact", "content": "The project uses Python.", "request_id": "mcp-1"}
        result = call(client, "write_memory", arguments)
        assert value(result)["status"] == "pending"
        assert backend.snapshot() == []
        backend.followup("What language?")
        assert call(client, "write_memory", arguments)["isError"]
        assert call(client, "read_external_context", {})["isError"]
        assert backend.snapshot() == []
    followup = memory_mcp(backend)
    with TestClient(bearer_app(followup.streamable_http_app(), TOKEN), base_url="http://127.0.0.1:12345") as client:
        tools = rpc(client, "tools/list", {}).json()["result"]["tools"]
        assert {t["name"] for t in tools} == {"recall_memory"}
        assert value(call(client, "recall_memory", {})) == {"memories": []}
        backend.close()
        assert call(client, "recall_memory", {})["isError"]


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "http://example.com/v1",
                                  "http://name:secret@localhost/v1", "http://localhost/v1?key=secret"])
def test_native_provider_cannot_fall_back_to_remote_or_credential_url(url):
    with pytest.raises(ValueError, match="ONLY_LOCAL_MODEL"):
        codex_command("codex", "/tmp/fixture", url, "http://127.0.0.1:12345", "fixture")


def test_native_environment_does_not_forward_cloud_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-openai-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-anthropic-secret")
    monkeypatch.setenv("HTTP_PROXY", "http://example.com")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "synthetic-aws-secret")
    env = codex_environment(TOKEN)
    assert not {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HTTP_PROXY", "AWS_SESSION_TOKEN"} & set(env)
    assert env["AGENTSENTRY_NATIVE_MODEL_KEY"] == "local-protocol-no-secret"
