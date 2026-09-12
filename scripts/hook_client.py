#!/usr/bin/env python3
"""Codex/Claude Code command-hook bridge; stdlib-only, no model/API credentials.

Run with --config /protected/path/client.json. Input is the native hook event.
On missing config, malformed event, timeout or API error: exit 2 (deny).
The host client still needs its own fail-closed installation and OS boundary.
"""

import argparse
import hashlib
import json
import os
import stat
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def request(config, path, body):
    url = urllib.parse.urlsplit(config["url"])
    if (
        url.scheme != "http"
        or url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("HOOK_ENDPOINT_MUST_BE_LOCAL_OR_SSH_TUNNEL")
    token_path = Path(config["token_file"])
    if token_path.is_symlink() or stat.S_IMODE(token_path.stat().st_mode) & 0o077:
        raise ValueError("HOOK_TOKEN_PERMISSIONS")
    req = urllib.request.Request(
        config["url"].rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token_path.read_text().strip(),
        },
    )
    # Ignore proxy environment variables for this local secret-bearing connection.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
        req, timeout=5
    ) as response:
        raw = response.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise ValueError("HOOK_RESPONSE_BUDGET")
    return json.loads(raw)


def native_call(config, event):
    return {
        "session_id": config["session_id"],
        "client": config["client"],
        "client_session_id": event["session_id"],
        "tool_call_id": event.get("tool_use_id")
        or event.get("tool_call_id")
        or event.get("call_id")
        or "",
        "cwd": event["cwd"],
        "tool_name": event["tool_name"],
        "tool_input": event["tool_input"],
    }


def handle(config, event):
    kind = event["hook_event_name"]
    if kind == "UserPromptSubmit":
        request(
            config,
            "/api/context/scan",
            {
                "session_id": config["session_id"],
                "source_type": "USER",
                "source_id": "native-prompt:" + event["session_id"],
                "text": event["prompt"],
            },
        )
        return {}, 0
    if kind not in {"PreToolUse", "PostToolUse", "PostToolUseFailure"}:
        return {}, 0
    call = native_call(config, event)
    if not call["tool_call_id"]:
        raise ValueError("HOOK_TOOL_CALL_ID_REQUIRED")
    state = Path(config["state_dir"])
    if state.is_symlink():
        raise ValueError("HOOK_STATE_SYMLINK")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stat.S_IMODE(state.stat().st_mode) & 0o077:
        raise ValueError("HOOK_STATE_PERMISSIONS")
    key = hashlib.sha256(
        json.dumps(
            [call["client"], call["client_session_id"], call["tool_call_id"]]
        ).encode()
    ).hexdigest()
    path = state / (key + ".json")
    if kind == "PreToolUse":
        deadline = time.monotonic() + min(
            max(float(config.get("approval_wait_seconds", 0)), 0), 40
        )
        while True:
            result = request(config, "/api/hooks/evaluate", call)
            if result["status"] != "pending" or time.monotonic() >= deadline:
                break
            time.sleep(0.5)
        if result["decision"]["decision"] != "ALLOW" or result["status"] != "ready":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "AgentSentry: "
                    + result["decision"]["decision"]
                    + "; "
                    + ",".join(result["decision"]["reason_codes"])
                    + (
                        "; approval=" + result["decision"]["approval_id"]
                        if result["decision"].get("approval_id")
                        else ""
                    ),
                }
            }, 2
        claim = request(config, "/api/hooks/claim", call)
        # No replay after an uncertain claim or a duplicate pre hook.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"call": call, "receipt": claim["receipt"]}, f)
            f.flush()
            os.fsync(f.fileno())
        # An empty decision preserves the client's own permission checks; a
        # policy allow must not auto-approve the host's independent sandbox gate.
        return {}, 0
    if path.is_symlink():
        raise ValueError("HOOK_RECEIPT_SYMLINK")
    saved = json.loads(path.read_text())
    if saved["call"] != call:
        raise ValueError("HOOK_RESULT_CALL_MISMATCH")
    output = event.get(
        "tool_response", event.get("tool_result", event.get("error", ""))
    )
    if not isinstance(output, str):
        output = json.dumps(output, ensure_ascii=False)
    result = request(
        config,
        "/api/hooks/report",
        {
            "call": call,
            "receipt": saved["receipt"],
            "output": output,
            "failed": kind == "PostToolUseFailure",
        },
    )
    return {
        "systemMessage": "AgentSentry recorded native result; risk="
        + result["risk"]["risk"]
    }, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.config.is_symlink() or stat.S_IMODE(args.config.stat().st_mode) & 0o077:
            raise ValueError("HOOK_CONFIG_PERMISSIONS")
        config = json.loads(args.config.read_text())
        raw = sys.stdin.buffer.read(524289)
        if len(raw) > 524288:
            raise ValueError("HOOK_INPUT_BUDGET")
        result, code = handle(config, json.loads(raw))
    except Exception:
        # Do not print tokens, raw payloads, library errors or host paths.
        print(
            "AgentSentry hook unavailable or invalid input; tool denied.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False))
    if code:
        print(
            "AgentSentry requires a valid allow before native execution.",
            file=sys.stderr,
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
