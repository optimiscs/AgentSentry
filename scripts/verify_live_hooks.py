#!/usr/bin/env python3
"""Native event fixture smoke against the running service; NOT vendor CLI E2E."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from prepare_client_hooks import prepare


def main():
    root = Path(__file__).resolve().parents[1]
    operator = (root / "runtime-data/operator.token").read_text().strip()
    report = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "kind": "native_event_fixture_real_http",
        "vendor_cli_executed": False,
        "clients": {},
    }
    with httpx.Client(
        base_url="http://127.0.0.1:8080",
        headers={"Authorization": "Bearer " + operator},
        trust_env=False,
        timeout=10,
    ) as client:
        for name in ["codex", "claude-code"]:
            reply = client.post(
                "/api/sessions", json={"task": "Review synthetic repository"}
            )
            reply.raise_for_status()
            session = reply.json()
            bundle = root / "artifacts/native-clients" / (name + "-" + uuid4().hex[:8])
            prepare(
                name,
                bundle,
                session["session_id"],
                root / "runtime-data/agent.token",
                "http://127.0.0.1:8080",
                sys.executable,
            )
            config = json.loads((bundle / "client.json").read_text())
            config["approval_wait_seconds"] = 0
            (bundle / "client.json").write_text(json.dumps(config))
            command = [
                sys.executable,
                str(bundle / "hook_client.py"),
                "--config",
                str(bundle / "client.json"),
            ]
            file = (
                root
                / "runtime-data/workspace"
                / ("hook-fixture-" + uuid4().hex + ".txt")
            )
            event = {
                "session_id": "fixture-" + uuid4().hex,
                "cwd": str(file.parent),
                "tool_use_id": "write-once",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": file.name,
                    "content": "AgentSentry native hook fixture\n",
                },
            }

            def invoke(kind, **updates):
                return subprocess.run(
                    command,
                    input=json.dumps({**event, "hook_event_name": kind, **updates}),
                    text=True,
                    capture_output=True,
                    timeout=10,
                )

            count = client.get("/api/status").json()["executions"]
            first = invoke("PreToolUse")
            assert first.returncode == 2 and not file.exists()
            pending = client.get("/api/approvals").json()
            approval = next(
                r
                for r in pending
                if r["result"]["action"]["session_id"] == session["session_id"]
            )
            grant = client.post(
                "/api/approvals",
                json={"approval_id": approval["approval_id"], "approve": True},
            )
            grant.raise_for_status()
            assert grant.json()["status"] == "ready" and not file.exists()
            assert invoke("PreToolUse").returncode == 0
            # The fixture acts as the external executor after the claim, exactly once.
            with file.open("x") as f:
                f.write(event["tool_input"]["content"])
            assert (
                invoke(
                    "PostToolUse", tool_response="file written by fixture"
                ).returncode
                == 0
            )
            assert invoke("PreToolUse").returncode == 2
            assert file.read_text() == event["tool_input"]["content"]
            pipeline = "cat " + file.name + " | head -n 1"
            pipeline_event = {
                "tool_use_id": "read-pipeline",
                "tool_name": "Bash",
                "tool_input": {"command": pipeline},
            }
            assert invoke("PreToolUse", **pipeline_event).returncode == 0
            read = subprocess.run(
                ["/bin/sh", "-c", pipeline],
                cwd=file.parent,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            assert read.stdout == event["tool_input"]["content"]
            assert (
                invoke(
                    "PostToolUse", **pipeline_event, tool_response=read.stdout
                ).returncode
                == 0
            )
            blocked = invoke(
                "PreToolUse",
                tool_use_id="sensitive-read",
                tool_name="Read",
                tool_input={"file_path": ".ssh/id_rsa"},
            )
            assert blocked.returncode == 2
            assert client.get("/api/status").json()["executions"] == count
            file.unlink()
            report["clients"][name] = {
                "bridge": "PASS",
                "approval_did_not_execute": True,
                "fixture_native_write_count": 1,
                "fixture_native_read_pipeline_count": 1,
                "gateway_execution_delta": 0,
                "duplicate_pre_denied": True,
                "credential_read_denied": True,
                "bundle": str(bundle),
            }
    (root / "artifacts/live-hooks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
