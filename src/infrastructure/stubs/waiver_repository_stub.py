"""Waiver repository stub for testing (Story 9.8, SC-4, SR-10).

This module provides an in-memory stub implementation of WaiverRepositoryProtocol
for unit and integration testing.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
"""

from __future__ import annotations

from typing import Optional

from src.application.ports.waiver_repository import (
    WaiverRecord,
    WaiverRepositoryProtocol,
)
from src.domain.events.waiver import WaiverStatus


class WaiverRepositoryStub(WaiverRepositoryProtocol):
    """In-memory stub for WaiverRepositoryProtocol (Story 9.8, SC-4, SR-10).

    This stub provides an in-memory implementation for testing.
    It supports all standard repository operations and test isolation via clear().

    Example:
        stub = WaiverRepositoryStub()
        await stub.save_waiver(waiver)
        retrieved = await stub.get_waiver(waiver.waiver_id)
        stub.clear()  # Reset for next test
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._waivers: dict[str, WaiverRecord] = {}

    async def get_waiver(self, waiver_id: str) -> Optional[WaiverRecord]:
        """Retrieve a waiver by its ID.

        Args:
            waiver_id: Unique waiver identifier.

        Returns:
            WaiverRecord if found, None otherwise.
        """
        return self._waivers.get(waiver_id)

    async def get_all_waivers(self) -> tuple[WaiverRecord, ...]:
        """Retrieve all documented waivers.

        Returns:
            Tuple of all WaiverRecords (empty tuple if none exist).
        """
        return tuple(self._waivers.values())

    async def get_active_waivers(self) -> tuple[WaiverRecord, ...]:
        """Retrieve only active waivers.

        Returns:
            Tuple of active WaiverRecords (empty tuple if none exist).
        """
        return tuple(
            waiver
            for waiver in self._waivers.values()
            if waiver.status == WaiverStatus.ACTIVE
        )

    async def save_waiver(self, waiver: WaiverRecord) -> None:
        """Save a waiver record.

        If a waiver with the same ID exists, it will be updated.
        Otherwise, a new waiver will be created.

        Args:
            waiver: The waiver record to save.
        """
        self._waivers[waiver.waiver_id] = waiver

    async def exists(self, waiver_id: str) -> bool:
        """Check if a waiver exists.

        Args:
            waiver_id: Unique waiver identifier.

        Returns:
            True if the waiver exists, False otherwise.
        """
        return waiver_id in self._waivers

    def clear(self) -> None:
        """Clear all waivers for test isolation."""
        self._waivers.clear()

    def get_waiver_count(self) -> int:
        """Get the number of stored waivers (for testing).

        Returns:
            Number of waivers currently stored.
        """
        return len(self._waivers)
