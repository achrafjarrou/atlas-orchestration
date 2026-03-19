# atlas/mcp/registry.py — Central MCP tool registry
# Pattern: tools register at startup, agents call via registry.call("tool_id", **kwargs)

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MCPTool:
    id: str
    name: str
    description: str
    category: str
    handler: Callable[..., Awaitable[Any]]
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    requires_auth: bool = False


class MCPRegistry:
    def __init__(self): self._tools: dict[str, MCPTool] = {}

    def register(self, tool: MCPTool) -> None:
        self._tools[tool.id] = tool
        logger.info("tool_registered", id=tool.id, category=tool.category)

    def get_tool(self, tool_id: str) -> MCPTool:
        if tool_id not in self._tools:
            raise KeyError(f"Tool not found: {tool_id}. Available: {list(self._tools)}")
        return self._tools[tool_id]

    def list_tools(self, category: str | None = None) -> list[MCPTool]:
        tools = list(self._tools.values())
        return sorted([t for t in tools if not category or t.category == category], key=lambda t: t.name)

    async def call(self, tool_id: str, **kwargs: Any) -> Any:
        tool = self.get_tool(tool_id)
        logger.info("tool_call", id=tool_id, args=list(kwargs))
        try:
            return await tool.handler(**kwargs)
        except Exception as e:
            logger.error("tool_error", id=tool_id, error=str(e)); raise

    def to_langchain_tools(self) -> list[Any]:
        from langchain_core.tools import StructuredTool
        return [StructuredTool.from_function(func=None, coroutine=t.handler, name=t.id, description=t.description)
                for t in self._tools.values()]

    def describe_all(self) -> str:
        if not self._tools: return "No tools registered."
        return "Available tools:\n" + "\n".join(f"- {t.id}: {t.description}" for t in self.list_tools())


mcp_registry = MCPRegistry()