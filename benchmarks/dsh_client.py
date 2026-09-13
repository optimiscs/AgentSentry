"""Bounded official DeepSeek Harness session over a benchmark-owned MCP service."""

import json
import os
import secrets
import signal
import subprocess
from pathlib import Path

from deepseek_proxy import DeepSeekProxy
from native_memory import bearer_app, codex_environment, local_server


def run_session(directory, sdk_python, mcp_app, key, *, system_prompt, user_query,
                tool_names, max_requests=15, max_tokens=4096, quota_state=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    model_token, mcp_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    proxy = DeepSeekProxy(key, model_token, directory / "provider", allowed_tools=tool_names,
                         max_requests=max_requests, max_tokens=max_tokens, quota_state=quota_state)
    worker = directory / "native"
    worker.mkdir()
    with local_server(proxy.app) as model_url, local_server(bearer_app(mcp_app, mcp_token)) as mcp_url:
        config = {"model_url": model_url, "mcp_url": mcp_url + "/", "system_prompt": system_prompt,
                  "user_query": user_query, "max_tokens": max_tokens}
        config_path = worker / "config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        environment = codex_environment(mcp_token)
        environment["AGENTSENTRY_NATIVE_MODEL_KEY"] = model_token
        script = Path(__file__).resolve().parents[1] / "scripts/dsh_session.py"
        command = [str(sdk_python), str(script), "--config", str(config_path)]
        (worker / "launch.json").write_text(json.dumps({"command": command,
            "environment_keys": sorted(environment)}, indent=2) + "\n")
        with (worker / "stdout.log").open("w") as out, (worker / "stderr.log").open("w") as err:
            process = subprocess.Popen(command, cwd=worker, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=err, start_new_session=True)
            try:
                returncode = process.wait(timeout=360)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                returncode = "TIMEOUT"
    result_path = worker / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {"status": "error", "error": "NO_DSH_RESULT"}
    result.update(returncode=returncode, model_calls=len(proxy.records), relay_rejections=proxy.rejections,
                  provider_statuses=[r["status"] for r in proxy.records],
                  provider_http_statuses=[r.get("http_status") for r in proxy.records])
    if returncode != 0 or proxy.rejections or any(r["status"] != "ok" for r in proxy.records):
        result["status"] = "error"
    (directory / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result, proxy.records
