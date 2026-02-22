from __future__ import annotations

from mcp.server.fastmcp import FastMCP

if __package__:
    from .registry import MCP_TOOL_REGISTRY
else:
    from registry import MCP_TOOL_REGISTRY


mcp = FastMCP("orthoassist")


def register_tools() -> None:
    for tool_spec in MCP_TOOL_REGISTRY:
        mcp.tool(name=tool_spec.name, description=tool_spec.description)(tool_spec.handler)


register_tools()


def _build_http_app():
    for factory_name in ("streamable_http_app", "sse_app", "http_app"):
        factory = getattr(mcp, factory_name, None)
        if callable(factory):
            return factory()
    return None


app = _build_http_app()


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()
