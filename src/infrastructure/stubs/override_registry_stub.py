"""Override Registry stub adapter (Story 5.2, AC2).

In-memory implementation of the OverrideRegistryPort for testing and development.
Production systems would use a database-backed implementation.

Constitutional Constraints:
- FR24: Override duration must be bounded -> Registry enables expiration tracking
- CT-11: Silent failure destroys legitimacy -> Expirations detected and logged
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.override_registry import (
    ExpiredOverrideInfo,
    OverrideRegistryPort,
)


@dataclass
class _OverrideEntry:
    """Internal storage for override tracking."""

    override_id: UUID
    keeper_id: str
    scope: str
    expires_at: datetime
    reverted: bool = False


class OverrideRegistryStub(OverrideRegistryPort):
    """In-memory implementation of OverrideRegistryPort for testing.

    This stub provides a simple in-memory storage for tracking active
    overrides. It uses an asyncio Lock for thread-safe concurrent access.

    For production use, implement a database-backed version.
    """

    def __init__(self) -> None:
        """Initialize the in-memory override registry."""
        self._overrides: dict[UUID, _OverrideEntry] = {}
        self._lock = asyncio.Lock()

    async def register_active_override(
        self,
        override_id: UUID,
        keeper_id: str,
        scope: str,
        expires_at: datetime,
    ) -> None:
        """Register an active override for expiration tracking.

        Args:
            override_id: The override event ID.
            keeper_id: The Keeper who initiated the override.
            scope: What is being overridden.
            expires_at: When the override should expire (UTC).
        """
        async with self._lock:
            self._overrides[override_id] = _OverrideEntry(
                override_id=override_id,
                keeper_id=keeper_id,
                scope=scope,
                expires_at=expires_at,
                reverted=False,
            )

    async def get_expired_overrides(self) -> list[ExpiredOverrideInfo]:
        """Get all overrides that have exceeded their duration.

        Returns:
            List of expired override information for event creation.
        """
        now = datetime.now(timezone.utc)
        expired: list[ExpiredOverrideInfo] = []

        async with self._lock:
            for entry in self._overrides.values():
                if not entry.reverted and now >= entry.expires_at:
                    expired.append(
                        ExpiredOverrideInfo(
                            override_id=entry.override_id,
                            keeper_id=entry.keeper_id,
                            scope=entry.scope,
                            expires_at=entry.expires_at,
                        )
                    )

        return expired

    async def mark_override_reverted(self, override_id: UUID) -> None:
        """Mark an override as reverted after expiration event is written.

        Args:
            override_id: The override event ID that was reverted.
        """
        async with self._lock:
            if override_id in self._overrides:
                self._overrides[override_id].reverted = True

    async def is_override_active(self, override_id: UUID) -> bool:
        """Check if an override is currently active.

        Args:
            override_id: The override event ID to check.

        Returns:
            True if the override is active, False otherwise.
        """
        async with self._lock:
            entry = self._overrides.get(override_id)
            if entry is None:
                return False
            # Active = exists and not reverted and not expired
            now = datetime.now(timezone.utc)
            return not entry.reverted and now < entry.expires_at

    # Test helper methods (not part of port interface)

    def _get_override_count(self) -> int:
        """Test helper: Get total number of tracked overrides."""
        return len(self._overrides)

    def _clear_all(self) -> None:
        """Test helper: Clear all tracked overrides."""
        self._overrides.clear()

    def _get_entry(self, override_id: UUID) -> _OverrideEntry | None:
        """Test helper: Get internal entry for inspection."""
        return self._overrides.get(override_id)
