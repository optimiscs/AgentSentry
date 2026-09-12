#!/usr/bin/env python3
"""Bounded real Codex CLI read-only smoke with local model; no user config edits."""

import argparse
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from prepare_client_hooks import prepare


def toml(value):
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(json.dumps(k) + "=" + toml(v) for k, v in value.items())
            + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join(toml(v) for v in value) + "]"
    return json.dumps(value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--codex", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    workspace = root / "runtime-data/workspace"
    # Refuse to trust any unreviewed adjacent hook source via the one-off flag.
    for parent in [workspace, *workspace.parents]:
        if (parent / ".codex/hooks.json").exists():
            raise ValueError("UNREVIEWED_ADJACENT_HOOK_SOURCE")
        if parent != Path("/root") and (parent / ".codex/config.toml").exists():
            raise ValueError("UNREVIEWED_PROJECT_CONFIGURATION")
    if Path("/root/.codex/auth.json").exists():
        raise ValueError(
            "EXISTING_ACCOUNT_AUTH_MAY_AUTO_REFRESH: use an independently provisioned local-only test account"
        )
    a.output.mkdir(parents=True, exist_ok=False)
    token = (root / "runtime-data/operator.token").read_text().strip()
    with httpx.Client(
        base_url="http://127.0.0.1:8080",
        headers={"Authorization": "Bearer " + token},
        trust_env=False,
        timeout=10,
    ) as client:
        response = client.post(
            "/api/sessions",
            json={"task": "Read README.md only; do not modify files or use network"},
        )
        response.raise_for_status()
        session = response.json()
        bundle = a.output / "hook-bundle"
        prepare(
            "codex",
            bundle,
            session["session_id"],
            root / "runtime-data/agent.token",
            "http://127.0.0.1:8080",
            sys.executable,
        )
        hooks = json.loads((bundle / "hooks.json").read_text())["hooks"]
        args = [
            str(a.codex),
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--dangerously-bypass-hook-trust",
            "--json",
            "-C",
            str(workspace),
        ]
        for feature in [
            "apps",
            "plugins",
            "browser_use",
            "browser_use_external",
            "computer_use",
            "multi_agent",
            "memories",
            "image_generation",
            "workspace_dependencies",
            "shell_snapshot",
            "code_mode_host",
            "skill_search",
            "unbounded_connection_retries",
        ]:
            args.extend(["--disable", feature])
        args.extend(["--enable", "hooks", "--enable", "skip_host_skill_discovery"])
        overrides = {
            "model": "agentsentry-local-qwen",
            "model_provider": "agentsentry_local",
            "model_providers.agentsentry_local": {
                "name": "Local vLLM fixture",
                "base_url": "http://127.0.0.1:18080/v1",
                "wire_api": "responses",
                "env_key": "AGENTSENTRY_LOCAL_MODEL_DUMMY_KEY",
                "requires_openai_auth": False,
                "request_max_retries": 0,
                "stream_max_retries": 0,
            },
            "approval_policy": "never",
            "web_search": "disabled",
            "project_doc_max_bytes": 0,
            "model_context_window": 32768,
            "model_auto_compact_token_limit": 28000,
            "model_reasoning_effort": "low",
            "hooks": hooks,
        }
        for key, value in overrides.items():
            args.extend(["-c", key + "=" + toml(value)])
        args.append(
            "Use the shell tool exactly once to run cat README.md in the current directory. Report only the first line. Do not use any other tools. If permission is denied, stop."
        )
        env = dict(os.environ)
        env["AGENTSENTRY_LOCAL_MODEL_DUMMY_KEY"] = "local-no-secret"
        # Do not expose unrelated API key/proxy variables to the test client.
        for key in list(env):
            if key.endswith("_API_KEY") and key != "AGENTSENTRY_LOCAL_MODEL_DUMMY_KEY":
                env.pop(key)
        env["NO_PROXY"] = "127.0.0.1,localhost"
        proc = subprocess.Popen(
            args,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=90)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=10)
        (a.output / "events.jsonl").write_bytes(stdout)
        (a.output / "stderr.log").write_bytes(stderr)
        trace = client.get("/api/traces/" + session["trace_id"])
        trace.raise_for_status()
        (a.output / "trace.json").write_text(json.dumps(trace.json(), indent=2) + "\n")
        report = {
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "kind": "real_codex_cli_local_model_spike",
            "vendor_version": subprocess.check_output(
                [str(a.codex), "--version"], text=True
            ).strip(),
            "model": "agentsentry-local-qwen",
            "read_only_sandbox": True,
            "user_config_ignored": True,
            "paid_api_used": False,
            "one_off_hook_trust": "reviewed project bridge only; no persisted trust modification",
            "exit_code": proc.returncode,
            "timed_out": timed_out,
            "session_id": session["session_id"],
            "trace_id": session["trace_id"],
            "status": "REQUIRES_TRACE_REVIEW",
        }
        (a.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
