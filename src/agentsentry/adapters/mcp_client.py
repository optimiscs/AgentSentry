"""Explicitly registered, trusted stdio servers; metadata never defines permissions."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import jsonschema
from referencing import Registry as SchemaRegistry
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agentsentry.adapters.filesystem import BoundaryError
from agentsentry.schemas import canonical, digest


def validate_arguments(args, schema):
    try:
        # Never dereference tool-supplied schema URIs over HTTP or the local filesystem.
        jsonschema.validate(args, schema, registry=SchemaRegistry())
    except jsonschema.ValidationError as exc:
        raise BoundaryError("MCP_ARGUMENT_SCHEMA_INVALID") from exc
    except Exception as exc:
        raise BoundaryError("MCP_SCHEMA_REFERENCE_OR_DEFINITION_INVALID") from exc


@asynccontextmanager
async def connection(config):
    command = config["command"]
    if not Path(command).is_absolute():
        raise BoundaryError("MCP_COMMAND_MUST_BE_ABSOLUTE")
    parameters = StdioServerParameters(
        command=command,
        args=config.get("args", []),
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": "/nonexistent",
            "PYTHONPATH": "",
            "PYTHONNOUSERSITE": "1",
        },
    )
    with open(os.devnull, "w") as errlog:
        async with stdio_client(parameters, errlog=errlog) as (reader, writer):
            async with ClientSession(
                reader, writer, read_timeout_seconds=timedelta(seconds=5)
            ) as session:
                await session.initialize()
                yield session


class MCPBroker:
    def __init__(self, registrations):
        self.registrations = registrations

    def config(self, tool):
        parts = tool.split(".", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            raise BoundaryError("INVALID_MCP_TOOL")
        server, name = parts[1:]
        config = self.registrations.get(server)
        if not config or name not in config.get("tools", {}):
            raise BoundaryError("MCP_TOOL_NOT_REGISTERED")
        return server, name, config, config["tools"][name]

    async def _metadata(self, tool, args, execute=False, expected=None):
        _, name, config, registration = self.config(tool)
        async with asyncio.timeout(10):
            async with connection(config) as session:
                listing = await session.list_tools()
                if listing.nextCursor or len(listing.tools) > 128:
                    raise BoundaryError("MCP_CATALOG_BUDGET_EXCEEDED")
                metadata = next(
                    (
                        t.model_dump(mode="json", exclude_none=True)
                        for t in listing.tools
                        if t.name == name
                    ),
                    None,
                )
                if metadata is None:
                    raise BoundaryError("MCP_TOOL_REMOVED")
                if len(canonical(metadata)) > 32768:
                    raise BoundaryError("MCP_METADATA_BUDGET_EXCEEDED")
                version = digest(metadata)
                if version != registration.get("metadata_sha256") or (
                    expected and version != expected
                ):
                    raise BoundaryError("MCP_METADATA_CHANGED")
                validate_arguments(args, metadata["inputSchema"])
                if execute:
                    result = await session.call_tool(name, args)
                    data = result.model_dump(mode="json", exclude_none=True)
                    if len(canonical(data)) > 262144:
                        raise BoundaryError("MCP_RESPONSE_BUDGET_EXCEEDED")
                    return data
                return metadata, version

    def _run(self, coroutine):
        try:
            return asyncio.run(coroutine)
        except ExceptionGroup as group:

            def boundary(errors):
                for error in errors:
                    if isinstance(error, BoundaryError):
                        return error
                    if isinstance(error, BaseExceptionGroup):
                        found = boundary(error.exceptions)
                        if found:
                            return found
                return None

            error = boundary(group.exceptions)
            if error:
                raise error from group
            raise BoundaryError("MCP_TRANSPORT_UNAVAILABLE") from group

    def prepare(self, tool, args):
        return self._run(self._metadata(tool, args))

    def execute(self, tool, args, expected):
        return self._run(self._metadata(tool, args, True, expected))
