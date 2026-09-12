#!/usr/bin/env python3
"""Exercise both real MCP transports against the running local gateway."""

import asyncio, json, sys
from pathlib import Path
from datetime import datetime, timezone
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parents[1]


def value(result):
    if result.isError:
        raise AssertionError("MCP returned an error")
    return result.structuredContent or json.loads(result.content[0].text)


async def main():
    operator = (ROOT / "runtime-data/operator.token").read_text().strip()
    agent = (ROOT / "runtime-data/agent.token").read_text().strip()
    with httpx.Client(
        base_url="http://127.0.0.1:8080",
        headers={"Authorization": "Bearer " + operator},
        trust_env=False,
    ) as client:
        response = client.post(
            "/api/sessions", json={"task": "review synthetic repository"}
        )
        response.raise_for_status()
        session = response.json()
        start = client.get("/api/status").json()["executions"]
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agentsentry.cli", "mcp", "--session", session["session_id"]],
            env={"AGENTSENTRY_ROOT": str(ROOT), "PATH": "/usr/bin:/bin"},
        )
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as mcp:
                await mcp.initialize()
                blocked = value(
                    await mcp.call_tool(
                        "guarded_tool_call",
                        {
                            "tool": "fs.read",
                            "arguments": {"path": ".ssh/id_rsa"},
                            "idempotency_key": "live-stdio-block",
                        },
                    )
                )
                assert blocked["status"] == "blocked"
        async with streamablehttp_client(
            "http://127.0.0.1:8080/mcp/", headers={"Authorization": "Bearer " + agent}
        ) as (r, w, _):
            async with ClientSession(r, w) as mcp:
                await mcp.initialize()
                read = value(
                    await mcp.call_tool(
                        "guarded_tool_call",
                        {
                            "session_id": session["session_id"],
                            "tool": "fs.read",
                            "arguments": {"path": "README.md"},
                            "idempotency_key": "live-http-read",
                        },
                    )
                )
                assert read["status"] == "succeeded"
        assert client.get("/api/status").json()["executions"] - start == 1
        report = {
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "transports": {"stdio": "PASS", "streamable_http": "PASS"},
            "gateway": "http://127.0.0.1:8080",
            "execution_count_delta": 1,
            "blocked_forward_count": 0,
            "trace_id": session["trace_id"],
        }
        (ROOT / "artifacts/live-mcp.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    asyncio.run(main())
