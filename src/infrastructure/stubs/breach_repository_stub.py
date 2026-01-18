"""Breach repository stub implementation (Story 6.1, FR30).

This module provides an in-memory stub implementation of BreachRepositoryProtocol
for testing and development purposes.

Constitutional Constraints:
- FR30: Breach history shall be filterable by type and date
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.application.ports.breach_repository import BreachRepositoryProtocol
from src.domain.events.breach import BreachEventPayload, BreachType


class BreachRepositoryStub(BreachRepositoryProtocol):
    """In-memory stub for breach event storage (testing only).

    This stub provides an in-memory implementation of BreachRepositoryProtocol
    suitable for unit and integration tests.

    The stub stores breach events in a dictionary keyed by breach_id.
    All query operations iterate over the stored breaches.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._breaches: dict[UUID, BreachEventPayload] = {}
        self._acknowledged: set[UUID] = set()
        self._pair_breaches: dict[str, list[BreachEventPayload]] = {}

    def clear(self) -> None:
        """Clear all stored breaches (for test cleanup)."""
        self._breaches.clear()
        self._acknowledged.clear()
        self._pair_breaches.clear()

    async def save(self, breach: BreachEventPayload) -> None:
        """Save a breach event to storage.

        Args:
            breach: The breach event payload to save.
        """
        self._breaches[breach.breach_id] = breach

    async def get_by_id(self, breach_id: UUID) -> BreachEventPayload | None:
        """Retrieve a specific breach event by ID.

        Args:
            breach_id: The unique identifier of the breach event.

        Returns:
            The breach event payload if found, None otherwise.
        """
        return self._breaches.get(breach_id)

    async def list_all(self) -> list[BreachEventPayload]:
        """Retrieve all breach events.

        Returns:
            List of all stored breach events, ordered by detection_timestamp.
        """
        breaches = list(self._breaches.values())
        return sorted(breaches, key=lambda b: b.detection_timestamp)

    async def filter_by_type(self, breach_type: BreachType) -> list[BreachEventPayload]:
        """Retrieve breach events filtered by type (FR30).

        Args:
            breach_type: The type of breach to filter by.

        Returns:
            List of breach events matching the type, ordered by detection_timestamp.
        """
        filtered = [b for b in self._breaches.values() if b.breach_type == breach_type]
        return sorted(filtered, key=lambda b: b.detection_timestamp)

    async def filter_by_date_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[BreachEventPayload]:
        """Retrieve breach events within a date range (FR30).

        Args:
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).

        Returns:
            List of breach events within the date range, ordered by detection_timestamp.
        """
        filtered = [
            b for b in self._breaches.values() if start <= b.detection_timestamp <= end
        ]
        return sorted(filtered, key=lambda b: b.detection_timestamp)

    async def filter_by_type_and_date(
        self,
        breach_type: BreachType,
        start: datetime,
        end: datetime,
    ) -> list[BreachEventPayload]:
        """Retrieve breach events filtered by both type and date range (FR30).

        Args:
            breach_type: The type of breach to filter by.
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).

        Returns:
            List of breach events matching type within the date range,
            ordered by detection_timestamp.
        """
        filtered = [
            b
            for b in self._breaches.values()
            if b.breach_type == breach_type and start <= b.detection_timestamp <= end
        ]
        return sorted(filtered, key=lambda b: b.detection_timestamp)

    async def count_unacknowledged_in_window(self, window_days: int) -> int:
        """Count unacknowledged breaches within a rolling window.

        Args:
            window_days: The rolling window in days (e.g., 90).

        Returns:
            Count of unacknowledged breaches in the window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        count = sum(
            1
            for b in self._breaches.values()
            if b.detection_timestamp >= cutoff and b.breach_id not in self._acknowledged
        )
        return count

    async def get_unacknowledged_in_window(
        self, window_days: int
    ) -> list[BreachEventPayload]:
        """Get all unacknowledged breaches within a rolling window.

        Args:
            window_days: The rolling window in days (e.g., 90).

        Returns:
            List of unacknowledged breach events in the window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        breaches = [
            b
            for b in self._breaches.values()
            if b.detection_timestamp >= cutoff and b.breach_id not in self._acknowledged
        ]
        return sorted(breaches, key=lambda b: b.detection_timestamp)

    async def get_breaches_by_witness_pair(
        self, pair_key: str
    ) -> list[BreachEventPayload]:
        """Get all breaches involving a specific witness pair (Story 6.8, FR124).

        This stub implementation returns breaches where the witness pair
        appears in the breach data. Since BreachEventPayload doesn't have
        a witness_pair field, this returns an empty list by default.

        For testing, use add_breach_for_pair() to associate breaches with pairs.

        Args:
            pair_key: Canonical key of the witness pair.

        Returns:
            List of breach events involving the pair.
        """
        return list(self._pair_breaches.get(pair_key, []))

    # Test helper methods (not part of protocol)

    def add_breach_for_pair(self, pair_key: str, breach: BreachEventPayload) -> None:
        """Associate a breach with a witness pair (for testing)."""
        if pair_key not in self._pair_breaches:
            self._pair_breaches[pair_key] = []
        self._pair_breaches[pair_key].append(breach)
        self._breaches[breach.breach_id] = breach

    def acknowledge_breach(self, breach_id: UUID) -> None:
        """Mark a breach as acknowledged (for testing)."""
        self._acknowledged.add(breach_id)

    def get_breach_count(self) -> int:
        """Get total number of stored breaches."""
        return len(self._breaches)

    def get_acknowledged_count(self) -> int:
        """Get number of acknowledged breaches."""
        return len(self._acknowledged)
