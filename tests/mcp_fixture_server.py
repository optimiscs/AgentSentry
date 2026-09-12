"""Trusted synthetic MCP server; its untrusted metadata may be poisoned in tests."""

import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

server = FastMCP("synthetic-fixture")


@server.tool(description=Path(sys.argv[2]).read_text())
def echo(text: str) -> str:
    with Path(sys.argv[1]).open("a") as f:
        f.write("executed\n")
    return text


if __name__ == "__main__":
    server.run("stdio")
