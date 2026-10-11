"""Lightweight Tool Cache with TTL Expiration for Read-Only Operations (Part 4)."""

import time
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    result: ToolResult
    expires_at: float


class ToolCache:
    """Lightweight in-memory cache supporting TTL automatic expiration for safe read-only tools."""

    def __init__(self, default_ttl_sec: float = 300.0):
        self.default_ttl_sec = default_ttl_sec
        self._cache: Dict[str, CacheEntry] = {}

    def _make_cache_key(self, tool_name: str, kwargs: Dict[str, Any]) -> str:
        try:
            sorted_params = json.dumps(kwargs, sort_keys=True)
        except Exception:
            sorted_params = str(kwargs)
        return f"{tool_name}:{sorted_params}"

    def get(self, tool: BaseTool, **kwargs: Any) -> Optional[ToolResult]:
        """Return cached ToolResult if present and unexpired (Cache Hit), else None (Cache Miss)."""
        # Safety Enforcement: Never cache unsafe tools or write operations
        if tool.permission_level != PermissionLevel.READ_ONLY or "write" in tool.name.lower():
            return None

        key = self._make_cache_key(tool.name, kwargs)
        entry = self._cache.get(key)
        if not entry:
            logger.debug("[ToolCache] Cache MISS for '%s'", tool.name)
            return None

        if time.time() > entry.expires_at:
            logger.debug("[ToolCache] Cache EXPIRED for '%s'", tool.name)
            del self._cache[key]
            return None

        logger.info("[ToolCache] Cache HIT for tool '%s'", tool.name)
        cached_result = entry.result
        # Preserve original output but return indicated cache hit status
        return ToolResult(
            success=cached_result.success,
            output=cached_result.output,
            error=cached_result.error,
            data=cached_result.data,
            execution_time_ms=0.0,
        )

    def set(
        self,
        tool: BaseTool,
        kwargs: Dict[str, Any],
        result: ToolResult,
        ttl_sec: Optional[float] = None,
    ) -> None:
        """Store successful read-only tool results in cache."""
        # Safety Enforcement: Reject caching unsafe tools or write operations
        if tool.permission_level != PermissionLevel.READ_ONLY or "write" in tool.name.lower():
            return

        if not result.success:
            return

        key = self._make_cache_key(tool.name, kwargs)
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl_sec
        expires_at = time.time() + ttl
        self._cache[key] = CacheEntry(result=result, expires_at=expires_at)
        logger.debug("[ToolCache] Cached result for '%s' (TTL: %.0fs)", tool.name, ttl)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
