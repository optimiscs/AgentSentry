import pytest
from fastapi.testclient import TestClient
from agentsentry.api.app import create_app
from agentsentry.schemas import ToolCall


@pytest.mark.case("TC-33")
def test_auth_origin_and_operator_separation(rt):
    with TestClient(create_app(runtime=rt, settings=rt.settings)) as c:
        assert c.get("/api/status").status_code == 401
        agent = {"Authorization": "Bearer " + rt.agent_token}
        operator = {"Authorization": "Bearer " + rt.operator_token}
        assert c.get("/api/status", headers=agent).status_code == 200
        assert (
            c.post("/api/sessions", headers=agent, json={"task": "review"}).status_code
            == 403
        )
        assert (
            c.post(
                "/api/approvals",
                headers=agent,
                json={"approval_id": "fake", "approve": True},
            ).status_code
            == 403
        )
        assert (
            c.get(
                "/api/status", headers={**operator, "Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert (
            c.get(
                "/api/status", headers={**operator, "Host": "evil.example"}
            ).status_code
            == 400
        )
        assert c.post("/mcp/", json={}).status_code == 401
        s = c.post("/api/sessions", headers=operator, json={"task": "review"}).json()
        read = c.post(
            "/api/tools/call",
            headers=agent,
            json={
                "session_id": s["session_id"],
                "tool": "fs.read",
                "arguments": {"path": "README.md"},
            },
        )
        assert read.status_code == 200 and read.json()["status"] == "succeeded"
        assert c.get("/api/traces/" + s["trace_id"], headers=agent).status_code == 200


@pytest.mark.case("TC-34")
def test_evidence_no_html_execution_and_policy_update(rt):
    with TestClient(create_app(runtime=rt, settings=rt.settings)) as c:
        h = {"Authorization": "Bearer " + rt.operator_token}
        s = c.post(
            "/api/sessions", headers=h, json={"task": "<script>alert(1)</script>"}
        ).json()
        response = c.get("/api/traces/" + s["trace_id"] + "/export", headers=h)
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers["content-disposition"]
        assert "script-src 'self'" in response.headers["content-security-policy"]
        policy = c.get("/api/policy", headers=h).json()
        result = c.put(
            "/api/policy",
            headers=h,
            json={
                "text": policy["text"].replace(
                    'then BLOCK("SECRET_EGRESS")', 'then ALLOW("SECRET_EGRESS")'
                ),
                "expected_version": policy["version"],
            },
        )
        assert result.status_code == 409
        assert (
            c.post("/api/sessions", headers=h, content="x" * 524289).status_code == 413
        )


@pytest.mark.linux
@pytest.mark.case("TC-23")
@pytest.mark.case("TC-27")
def test_actual_code_sandbox_blocks_host_and_network(rt):
    if not rt.sandbox.available():
        pytest.skip("Linux root + chroot + seccomp required")
    s = rt.create_session("run tests")
    code = """import os, socket
assert os.getuid() == 65534
for path in ['/etc/shadow', '/root/.ssh/id_rsa', '/proc/1/environ', '/root/autodl-tmp/AgentSentry/runtime-data/operator.token']:
    try: open(path).read()
    except (FileNotFoundError, PermissionError): pass
    else: raise AssertionError('host read bypass')
try: socket.socket()
except PermissionError: pass
else: raise AssertionError('network bypass')
try: os.fork()
except PermissionError: pass
else: raise AssertionError('fork bypass')
print('isolation verified')"""
    r = rt.call(
        ToolCall(session_id=s.session_id, tool="exec.python", arguments={"code": code})
    )
    assert r.status == "succeeded" and r.output["stdout"] == "isolation verified\n", (
        r.model_dump()
    )
    assert not list(rt.sandbox.jobs.iterdir())


@pytest.mark.linux
@pytest.mark.case("TC-31")
def test_sandbox_cpu_budget(rt):
    if not rt.sandbox.available():
        pytest.skip("Linux sandbox required")
    r = rt.sandbox.run("while True: pass")
    assert r["exit_code"] != 0


@pytest.mark.case("TC-01")
@pytest.mark.case("TC-31")
@pytest.mark.case("TC-28")
def test_batch_scan_and_failed_scan_stops_session(rt):
    with TestClient(create_app(settings=rt.settings, runtime=rt)) as c:
        headers = {"Authorization": "Bearer " + rt.operator_token}
        s = rt.create_session("send report")
        chunks = [
            {
                "session_id": s.session_id,
                "source_type": source,
                "source_id": "test",
                "text": "public text",
            }
            for source in ["WEB", "DOCUMENT", "ISSUE", "MCP_RESPONSE"]
        ]
        batch = c.post(
            "/api/context/scan-batch", headers=headers, json={"chunks": chunks}
        )
        assert len(batch.json()["results"]) == 4 and all(
            r["status"] == "ok" for r in batch.json()["results"]
        )
        failed = c.post(
            "/api/context/scan",
            headers=headers,
            json={**chunks[0], "text": "CANARY_SECRET_MALFORMED" + ("x" * 65537)},
        )
        assert failed.status_code == 422 and "CANARY_SECRET" not in failed.text
        result = c.post(
            "/api/tools/call",
            headers=headers,
            json={
                "session_id": s.session_id,
                "tool": "http.request",
                "arguments": {"url": "https://corp.example.test/", "body": "public"},
            },
        )
        assert result.json()["status"] == "blocked" and rt.store.execution_count() == 0


@pytest.mark.case("TC-28")
def test_sdk_validation_logs_are_redacted(rt, caplog):
    secret = "CANARY_SECRET_BAD_MCP_ARGUMENT"
    with TestClient(
        create_app(settings=rt.settings, runtime=rt), base_url="http://127.0.0.1:8080"
    ) as c:
        headers = {
            "Authorization": "Bearer " + rt.agent_token,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        c.post(
            "/mcp/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "guarded_tool_call",
                    "arguments": {
                        "session_id": {"token": secret},
                        "tool": "fs.read",
                        "arguments": {"path": "README.md"},
                        "idempotency_key": "invalid",
                    },
                },
            },
        )
    assert secret not in caplog.text and rt.store.execution_count() == 0


@pytest.mark.case("TC-28")
def test_formatter_redacts_exception_text():
    import logging
    from agentsentry.trace.logging import RedactingFormatter

    record = logging.LogRecord(
        "fixture",
        40,
        "fixture",
        1,
        "Validation failed: %s",
        ("CANARY_SECRET_LOG_TEST",),
        None,
    )
    assert "CANARY_SECRET_LOG_TEST" not in RedactingFormatter(
        logging.Formatter()
    ).format(record)
