#!/usr/bin/env python3
"""Drive the official DSH SDK in an isolated process with only benchmark MCP tools."""

import argparse
import dataclasses
import json
import os
from pathlib import Path

from deepseek_harness import DeepSeekHarness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    root = args.config.parent.resolve()
    workspace, home = root / "workspace", root / "dsh-home"
    workspace.mkdir(exist_ok=False)
    home.mkdir(exist_ok=False)
    # Published sdk-minimal remains the kernel; only its shell tool rows are disabled.
    patches = [{"id": name, "disabled": True} for name in ("persistent-bash", "persistent-pwsh")]
    patches += [{"id": "llm-deepseek", "config": {
        "apiKeyEnv": "DEEPSEEK_API_KEY", "baseURL": config["model_url"],
        "thinking": "disabled", "reasoningEffort": "off", "streamIdleTimeoutMs": 120000}},
        {"id": "system-prompt", "config": {"includeHarnessIdentity": False,
         "includeRuntimeContext": False, "personaPrefix": config["system_prompt"]}},
        {"insert": [{"id": "agentsentry-mcp", "name": "@deepseek-ai/dsh-mcp-client", "config": {
            "serverName": "benchmark", "transport": "streamable-http", "url": config["mcp_url"],
            "headers": {"Authorization": "Bearer " + os.environ["AGENTSENTRY_NATIVE_MCP_TOKEN"]},
            "failOnStartupError": True, "reconnect": {"enabled": False}, "toolCallTimeoutMs": 30000}}]}]
    patch_path = root / "profile.patch.json"
    patch_path.write_text(json.dumps(patches, indent=2) + "\n")
    patch_path.chmod(0o600)
    report = {"status": "error", "client": "official-deepseek-harness-sdk", "model": "deepseek-flash",
              "reasoning_effort": "off", "profile": "sdk-minimal-with-benchmark-mcp"}
    try:
        with DeepSeekHarness(provider="deepseek-official", model="deepseek-flash", reasoning_effort="off",
            max_tokens=config["max_tokens"], cwd=str(workspace), runtime_cwd=str(workspace),
            dsh_home=str(home), profile="sdk-minimal", patches=(str(patch_path),),
            api_key=os.environ["AGENTSENTRY_NATIVE_MODEL_KEY"], base_url=config["model_url"],
            request_timeout_seconds=300, shutdown_timeout_seconds=10) as harness:
            result = harness.run(config["user_query"], session_id="benchmark-session")
        report.update(status="ok" if result.finish_reason == "completed" else "error",
                      result=dataclasses.asdict(result))
    except Exception as error:
        report["error"] = str(error)
    finally:
        patch_path.unlink()  # The per-process MCP capability expires with its server.
        (root / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
