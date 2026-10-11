"""Web Search Tool for AI Agent with Tavily API & Ultra-Fast Sub-Second Fallback Search Engine."""

import html
import logging
import re
from datetime import datetime
import httpx

from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.utils.paths import load_environment

logger = logging.getLogger(__name__)
load_environment()


class WebSearchTool(BaseTool):
    """Tool enabling AI Agent to perform sub-second live real-time web search."""

    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for current news, weather, facts, live information, and real-time data.",
            permission_level=PermissionLevel.READ_ONLY,
            version="1.2.0",
            supported_file_types=[],
            capabilities=["web_search", "news", "weather", "realtime_facts", "online_search"],
            input_schema={"query": "string"},
            output_schema={"answer": "string", "results": "list"},
        )
        self._tavily_client = None
        self._tavily_key = ""
        # Persistent HTTP client with connection pooling and fast 4.0s timeout
        self._http_client = httpx.Client(
            timeout=4.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

    @staticmethod
    def _get_configured_key(provider_id: str, environment_name: str) -> str:
        """Read a key from Settings first, while preserving .env compatibility."""
        try:
            from app.settings.settings_manager import SettingsManager

            key = SettingsManager.instance().get_api_key(provider_id)
            if key:
                return key.strip()
        except Exception as exc:
            logger.debug("[WebSearchTool] Settings key lookup failed for %s: %s", provider_id, exc)

        import os
        return os.getenv(environment_name, "").strip()

    def _get_tavily_client(self):
        """Create or refresh the Tavily client after a Settings API-key change."""
        api_key = self._get_configured_key("tavily", "TAVILY_API_KEY")
        if not api_key:
            self._tavily_client = None
            self._tavily_key = ""
            return None

        if self._tavily_client is None or self._tavily_key != api_key:
            try:
                from tavily import TavilyClient
                self._tavily_client = TavilyClient(api_key=api_key)
                self._tavily_key = api_key
            except Exception as exc:
                logger.warning("[WebSearchTool] Could not initialize Tavily client: %s", exc)
                self._tavily_client = None
        return self._tavily_client

    def execute(self, query: str = "", **kwargs) -> ToolResult:
        if not query or not query.strip():
            return ToolResult(success=False, output="", error="Query parameter is required.")

        clean_query = query.strip()
        current_year = str(datetime.now().year)

        # Enhance query with current year if searching for latest news/weather without explicit year
        if any(kw in clean_query.lower() for kw in ["latest", "news", "today", "recent", "current", "weather"]) and not re.search(r"\b20\d{2}\b", clean_query):
            search_query = f"{clean_query} {current_year}"
        else:
            search_query = clean_query

        # Prefer Tavily, then Brave Search, with DuckDuckGo as a no-key fallback.
        tavily_client = self._get_tavily_client()
        if tavily_client is not None:
            try:
                res = tavily_client.search(
                    query=search_query,
                    search_depth="advanced",
                    include_answer=True,
                    max_results=5,
                )
                ans = res.get("answer", "")
                results = res.get("results", [])
                formatted_output = ans if ans else self._format_tavily_results(results)
                if formatted_output:
                    return ToolResult(success=True, output=formatted_output, data=res)
            except Exception as exc:
                logger.warning("[WebSearchTool] Tavily search failed, trying Brave Search: %s", exc)

        brave_key = self._get_configured_key("brave_search", "BRAVE_SEARCH_API_KEY")
        if brave_key:
            try:
                brave_output = self._search_brave(search_query, brave_key)
                if brave_output:
                    return ToolResult(success=True, output=brave_output, data={"query": search_query, "engine": "brave"})
            except Exception as exc:
                logger.warning("[WebSearchTool] Brave Search failed, falling back to DuckDuckGo: %s", exc)

        # Fast direct Live Search engine (Sub-second execution)
        try:
            ddg_output = self._search_duckduckgo(search_query)
            if ddg_output:
                return ToolResult(success=True, output=ddg_output, data={"query": search_query, "engine": "duckduckgo"})
            return ToolResult(success=False, output="", error="No web search results returned.")
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Web search failed: {exc}")

    def _search_brave(self, query: str, api_key: str, max_results: int = 5) -> str:
        """Fetch current web results from Brave's official Search API."""
        response = self._http_client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("web", {}).get("results", [])
        formatted = []
        for item in results[:max_results]:
            title = str(item.get("title", "")).strip()
            description = str(item.get("description", "")).strip()
            url = str(item.get("url", "")).strip()
            if title or description or url:
                formatted.append(f"Title: {title}\nSnippet: {description}\nSource: {url}")
        return "\n\n".join(formatted)

    def _format_tavily_results(self, results: list) -> str:
        formatted = []
        for item in results[:5]:
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            formatted.append(f"Title: {title}\nSnippet: {content}\nSource: {url}")
        return "\n\n".join(formatted)

    def _search_duckduckgo(self, query: str, max_results: int = 5) -> str:
        try:
            r = self._http_client.post("https://lite.duckduckgo.com/lite/", data={"q": query})
            if r.status_code != 200:
                r = self._http_client.get("https://html.duckduckgo.com/html/", params={"q": query})

            titles = re.findall(r"class='result-link'[^>]*>(.*?)</a>", r.text, re.DOTALL)
            snippets = re.findall(r"class='result-snippet'[^>]*>(.*?)</td>", r.text, re.DOTALL)
            links = re.findall(r"class='link-text'[^>]*>(.*?)</span>", r.text, re.DOTALL)

            results = []
            for i in range(min(len(titles), len(snippets), max_results)):
                t = html.unescape(re.sub(r"<.*?>", "", titles[i])).strip()
                s = html.unescape(re.sub(r"<.*?>", "", snippets[i])).strip()
                l = html.unescape(re.sub(r"<.*?>", "", links[i])).strip() if i < len(links) else ""
                results.append(f"Title: {t}\nSnippet: {s}\nSource: {l}")

            return "\n\n".join(results) if results else "No live search results found."
        except Exception as exc:
            logger.error("[WebSearchTool] Sub-second search exception: %s", exc)
            return f"Search error: {exc}"
