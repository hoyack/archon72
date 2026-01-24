"""Status token registry protocol (Story 7.1, Task 5).

Application port for tracking petition state versions and notifying
long-poll waiters of changes.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class StatusTokenRegistryProtocol(Protocol):
    """Protocol for status token registry operations."""

    async def get_current_version(self, petition_id: UUID) -> int | None:
        """Get the current state version for a petition."""
        ...

    async def register_petition(self, petition_id: UUID, version: int) -> None:
        """Register a petition for change tracking."""
        ...

    async def update_version(self, petition_id: UUID, new_version: int) -> None:
        """Update the state version for a petition and notify waiters."""
        ...

    async def wait_for_change(
        self, petition_id: UUID, current_version: int, timeout_seconds: float
    ) -> bool:
        """Wait for a state change or timeout."""
        ...

    def get_active_waiter_count(self) -> int:
        """Get the number of active waiters."""
        ...
