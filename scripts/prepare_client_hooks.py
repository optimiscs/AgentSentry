#!/usr/bin/env python3
"""Prepare reviewed native client configuration without changing user settings.

The operator supplies a pre-authorized AgentSentry session. The generated bridge
gets only the agent token, never the approval token. Current scope is bounded native
file tools; the catch-all pre hook rejects unsupported tools (including MCP).
"""

import argparse
import hashlib
import json
import shlex
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit


def prepare(client, output, session_id, token_file, url, python):
    output = Path(output).absolute()
    token_file = Path(token_file).absolute()
    if token_file.is_symlink() or stat.S_IMODE(token_file.stat().st_mode) & 0o077:
        raise ValueError("TOKEN_FILE_MUST_BE_PRIVATE")
    parts = urlsplit(url)
    if (
        parts.scheme != "http"
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("ONLY_LOOPBACK_OR_SSH_TUNNEL_SUPPORTED")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    config = output / "client.json"
    # Copy the reviewed stdlib bridge into this protected configuration bundle.
    source = Path(__file__).with_name("hook_client.py")
    bridge = output / "hook_client.py"
    bridge.write_bytes(source.read_bytes())
    bridge.chmod(0o600)
    config.write_text(
        json.dumps(
            {
                "client": client,
                "url": url,
                "session_id": session_id,
                "token_file": str(token_file),
                "state_dir": str(output / "receipts"),
                "approval_wait_seconds": 30,
            },
            indent=2,
        )
        + "\n"
    )
    config.chmod(0o600)
    command = shlex.join(
        [str(Path(python).absolute()), str(bridge), "--config", str(config)]
    )
    events = ["UserPromptSubmit", "PreToolUse", "PostToolUse"]
    if client == "claude-code":
        events.append("PostToolUseFailure")
    hooks = {
        event: [
            {
                "matcher": "*",
                "hooks": [{"type": "command", "command": command, "timeout": 50}],
            }
        ]
        for event in events
    }
    # Vendor format is a JSON hooks container; Codex hooks.json / Claude settings.json.
    filename = "hooks.json" if client == "codex" else "settings.json"
    target = output / filename
    target.write_text(json.dumps({"hooks": hooks}, indent=2) + "\n")
    target.chmod(0o600)
    (output / "bundle-manifest.json").write_text(
        json.dumps(
            {
                "client": client,
                "installed": False,
                "scope": "bounded_native_file_workflow",
                "bridge_sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(),
                "configuration_file": filename,
                "review_required_by_vendor": client == "codex",
                "limitations": [
                    "Only matching, successfully invoked hooks are covered; vendor timeout/configuration failures can bypass.",
                    "Unknown native tools and MCP tools are denied by this catch-all pre hook; use gateway MCP through its separately tested client route.",
                    "Actual execution host cwd must exactly match gateway workspace; no remote/local filesystem remapping.",
                    "Client-reported outcomes are not trusted proof of execution; OS isolation and real vendor E2E remain required.",
                    "Approval wait is bounded; expired/missed original calls must use a new call id and approval.",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    return {"client": client, "output": str(output), "installed": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", choices=["codex", "claude-code"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--token-file", type=Path, required=True)
    p.add_argument("--url", default="http://127.0.0.1:8080")
    p.add_argument("--python", default=sys.executable)
    a = p.parse_args()
    print(
        json.dumps(
            prepare(a.client, a.output, a.session_id, a.token_file, a.url, a.python)
        )
    )


if __name__ == "__main__":
    main()
