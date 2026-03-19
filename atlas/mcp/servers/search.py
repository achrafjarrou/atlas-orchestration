# atlas/mcp/servers/search.py — DuckDuckGo search (free, no API key)
import asyncio
from typing import Any
import structlog
from duckduckgo_search import DDGS
from atlas.mcp.registry import MCPTool, mcp_registry

logger = structlog.get_logger(__name__)


async def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web with DuckDuckGo. Free, no API key needed."""
    def _search():
        with DDGS() as d: return list(d.text(query, max_results=max_results))
    try:
        results = await asyncio.to_thread(_search)
        return [{"title": r.get("title",""), "url": r.get("href",""), "snippet": r.get("body",""), "published": r.get("published","")} for r in results]
    except Exception as e:
        logger.error("search_error", query=query, error=str(e))
        return [{"error": str(e)}]


async def news_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search recent news articles."""
    def _search():
        with DDGS() as d: return list(d.news(query, max_results=max_results))
    try:
        return await asyncio.to_thread(_search)
    except Exception as e:
        return [{"error": str(e)}]


def register_search_tools():
    mcp_registry.register(MCPTool(id="web_search", name="Web Search",
        description="Search the web for current information, facts, documentation, news.",
        category="search", handler=web_search, tags=["search", "web", "information"]))
    mcp_registry.register(MCPTool(id="news_search", name="News Search",
        description="Search recent news articles about a topic.",
        category="search", handler=news_search, tags=["news", "current-events"]))
    logger.info("search_tools_ready")