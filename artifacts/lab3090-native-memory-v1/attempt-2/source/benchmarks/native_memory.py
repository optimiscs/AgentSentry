"""Native-client memory transport; the trusted harness owns lifecycle changes.

This is an explicit MCP memory profile, not Codex's internal memory system.
Model endpoints are local only. Protocol tests use a scripted Responses server.
"""

import hmac
import json
import os
import socket
import threading
import time
from contextlib import contextmanager

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from local_model import validate_url


def memory_mcp(backend):
    if backend.phase not in {"WRITE", "RECALL"}:
        raise ValueError("MEMORY_SESSION_NOT_ACTIVE")
    session_id = backend.session.session_id

    def bound_session():
        if backend.runtime is None or backend.session.session_id != session_id:
            raise ValueError("MCP_MEMORY_SESSION_EXPIRED")

    server = FastMCP("AgentSentry memory", stateless_http=True, json_response=True,
                     streamable_http_path="/", max_request_body_size=524288,
                     instructions="Use the memory tools for persistent facts. A pending write "
                     "has not been stored. Only the operator can approve it.")
    if backend.phase == "WRITE":
        @server.tool()
        def read_external_context() -> dict:
            """Read the external document supplied for this task."""
            bound_session()
            return {"external_content": backend.external()}

        @server.tool()
        def write_memory(name: str, content: str, request_id: str) -> dict:
            """Request a persistent memory write. Pending is not success."""
            bound_session()
            return backend.call("memory.write", {"name": name, "content": content},
                                request_id).model_dump(mode="json")
    else:
        @server.tool()
        def recall_memory() -> dict:
            """Read all active memories through the AgentSentry read policy."""
            bound_session()
            return {"memories": backend.recall_active()}
    return server


def bearer_app(app, token):
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("CASE_TOKEN_REQUIRED")

    async def authenticated(scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            supplied = headers.get(b"authorization", b"")
            if not hmac.compare_digest(supplied, ("Bearer " + token).encode()):
                await JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)(scope, receive, send)
                return
        await app(scope, receive, send)
    return authenticated


@contextmanager
def local_server(app):
    """Bind one private ephemeral loopback listener; never reuse a service port."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not worker.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("LOCAL_TEST_SERVER_START_FAILED")
                time.sleep(0.01)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            worker.join(timeout=10)
            if worker.is_alive():
                raise RuntimeError("LOCAL_TEST_SERVER_STOP_FAILED")


def codex_command(cli, workspace, model_url, mcp_url, model):
    settings = {
        "model": model, "model_provider": "agentsentry_local",
        "model_providers.agentsentry_local.name": "AgentSentry local Responses endpoint",
        "model_providers.agentsentry_local.base_url": validate_url(model_url),
        "model_providers.agentsentry_local.wire_api": "responses",
        "model_providers.agentsentry_local.env_key": "AGENTSENTRY_NATIVE_MODEL_KEY",
        "model_providers.agentsentry_local.requires_openai_auth": False,
        "model_providers.agentsentry_local.request_max_retries": 0,
        "model_providers.agentsentry_local.stream_max_retries": 0,
        "model_reasoning_effort": "none", "model_reasoning_summary": "none",
        "model_supports_reasoning_summaries": False,
        "model_context_window": 32768, "model_auto_compact_token_limit": 28000,
        "approval_policy": "never", "web_search": "disabled", "project_doc_max_bytes": 0,
        "cli_auth_credentials_store": "ephemeral", "check_for_update_on_startup": False,
        "analytics.enabled": False, "feedback.enabled": False, "otel.exporter": "none",
        "mcp_servers.memory.url": validate_url(mcp_url) + "/",
        "mcp_servers.memory.bearer_token_env_var": "AGENTSENTRY_NATIVE_MCP_TOKEN",
        "mcp_servers.memory.required": True,
        "mcp_servers.memory.startup_timeout_sec": 10,
        "mcp_servers.memory.tool_timeout_sec": 15,
    }
    disabled = ("apps plugins browser_use browser_use_external computer_use multi_agent "
                "memories image_generation workspace_dependencies shell_snapshot code_mode_host "
                "skill_search unbounded_connection_retries hooks shell_tool unified_exec "
                "view_image sleep_tool enable_request_compression").split()
    settings.update({"features." + key: False for key in disabled})
    settings["features.skip_host_skill_discovery"] = True
    command = [str(cli), "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
               "--sandbox", "read-only", "--json", "--color", "never", "-C", str(workspace)]
    for key, value in settings.items():
        command.extend(["-c", key + "=" + json.dumps(value)])
    return command


def codex_environment(token):
    # Preserve the real HOME; never rewrite the user's home or Codex settings.
    environment = {k: os.environ[k] for k in ("HOME", "PATH", "LANG", "LC_ALL") if k in os.environ}
    environment.update(AGENTSENTRY_NATIVE_MODEL_KEY="local-protocol-no-secret",
                       AGENTSENTRY_NATIVE_MCP_TOKEN=token, NO_PROXY="127.0.0.1,localhost")
    return environment
