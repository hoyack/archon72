"""Dashboard caching for application layer (Story 8.4, NFR-5.6).

Simple in-memory cache with TTL for legitimacy dashboard data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL (NFR-5.6)."""

    data: Any
    cached_at: datetime
    ttl_seconds: int = 300

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        now = datetime.now(timezone.utc)
        expiry = self.cached_at + timedelta(seconds=self.ttl_seconds)
        return now >= expiry


class DashboardCache:
    """Simple in-memory cache for dashboard data (Story 8.4, NFR-5.6)."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        """Initialize dashboard cache."""
        self._cache: dict[str, CacheEntry] = {}
        self._ttl_seconds = ttl_seconds
        self._log = logger.bind(component="dashboard_cache")

    def get(self, cycle_id: str) -> Any | None:
        """Get cached dashboard data for cycle."""
        cache_key = f"dashboard:{cycle_id}"

        if cache_key not in self._cache:
            self._log.debug("cache_miss", cycle_id=cycle_id)
            return None

        entry = self._cache[cache_key]

        if entry.is_expired():
            self._log.debug("cache_expired", cycle_id=cycle_id)
            del self._cache[cache_key]
            return None

        self._log.debug("cache_hit", cycle_id=cycle_id)
        return entry.data

    def set(self, cycle_id: str, data: Any) -> None:
        """Cache dashboard data for cycle."""
        cache_key = f"dashboard:{cycle_id}"

        entry = CacheEntry(
            data=data,
            cached_at=datetime.now(timezone.utc),
            ttl_seconds=self._ttl_seconds,
        )

        self._cache[cache_key] = entry
        self._log.debug(
            "cache_set",
            cycle_id=cycle_id,
            ttl_seconds=self._ttl_seconds,
        )

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self._log.info("cache_cleared", entries_cleared=count)

    def clear_cycle(self, cycle_id: str) -> None:
        """Clear cache entry for specific cycle."""
        cache_key = f"dashboard:{cycle_id}"

        if cache_key in self._cache:
            del self._cache[cache_key]
            self._log.debug("cache_entry_cleared", cycle_id=cycle_id)
