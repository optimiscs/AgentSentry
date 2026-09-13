"""Dynamic benchmark tool catalog on the official MCP transport."""
from contextlib import asynccontextmanager

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount


def tool_app(definitions, execute):
    server = Server("Benchmark tools")

    @server.list_tools()
    async def list_tools():
        return [types.Tool(name=d["name"], description=d["description"], inputSchema=d["parameters"])
                for d in definitions]

    @server.call_tool()
    async def call(name, arguments):
        return [types.TextContent(type="text", text=execute(name, arguments))]

    manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)

    async def endpoint(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    return Starlette(routes=[Mount("/", app=endpoint)], lifespan=lifespan)
