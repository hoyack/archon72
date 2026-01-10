"""Integrity failure repository stub implementation (Story 7.1, FR37, RT-4).

This module provides an in-memory stub implementation of IntegrityFailureRepositoryProtocol
for testing and development purposes.

Constitutional Constraints:
- FR37: 3 consecutive integrity failures in 30 days triggers cessation
- RT-4: 5 failures in 90-day rolling window prevents timing attacks
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from src.application.ports.integrity_failure_repository import (
    IntegrityFailure,
    IntegrityFailureRepositoryProtocol,
)


class IntegrityFailureRepositoryStub(IntegrityFailureRepositoryProtocol):
    """In-memory stub for integrity failure storage (testing only).

    This stub provides an in-memory implementation of IntegrityFailureRepositoryProtocol
    suitable for unit and integration tests.

    The stub stores failures in a list and tracks the last successful check time
    to determine consecutive failures.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._failures: dict[UUID, IntegrityFailure] = {}
        self._last_successful_check: Optional[datetime] = None

    def clear(self) -> None:
        """Clear all stored failures (for test cleanup)."""
        self._failures.clear()
        self._last_successful_check = None

    async def save(self, failure: IntegrityFailure) -> None:
        """Save an integrity failure to storage.

        Args:
            failure: The integrity failure to save.
        """
        self._failures[failure.failure_id] = failure

    async def get_by_id(self, failure_id: UUID) -> IntegrityFailure | None:
        """Retrieve a specific integrity failure by ID.

        Args:
            failure_id: The unique identifier of the failure.

        Returns:
            The failure record if found, None otherwise.
        """
        return self._failures.get(failure_id)

    async def count_consecutive_in_window(self, window_days: int) -> int:
        """Count consecutive integrity failures within a time window (FR37).

        This supports FR37's trigger: 3 consecutive failures in 30 days.
        "Consecutive" means no successful integrity check between failures.

        Args:
            window_days: The rolling window in days (e.g., 30).

        Returns:
            Count of consecutive failures in the window.
        """
        failures = await self.get_consecutive_failures_in_window(window_days)
        return len(failures)

    async def count_in_rolling_window(self, window_days: int) -> int:
        """Count all integrity failures within a rolling window (RT-4).

        This supports RT-4's alternative trigger: 5 failures in 90 days.
        Non-consecutive failures count toward this threshold.

        Args:
            window_days: The rolling window in days (e.g., 90).

        Returns:
            Total count of failures in the window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        count = sum(
            1 for f in self._failures.values()
            if f.failure_timestamp >= cutoff
        )
        return count

    async def get_failures_in_window(
        self, window_days: int
    ) -> list[IntegrityFailure]:
        """Get all integrity failures within a rolling window.

        Args:
            window_days: The rolling window in days.

        Returns:
            List of failures within the window, ordered by timestamp.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        failures = [
            f for f in self._failures.values()
            if f.failure_timestamp >= cutoff
        ]
        return sorted(failures, key=lambda f: f.failure_timestamp)

    async def get_consecutive_failures_in_window(
        self, window_days: int
    ) -> list[IntegrityFailure]:
        """Get consecutive integrity failures within a time window (FR37).

        Returns only the sequence of consecutive failures (no successful
        checks between them) that occurred in the window.

        Args:
            window_days: The rolling window in days (e.g., 30).

        Returns:
            List of consecutive failures, ordered by timestamp.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

        # Get all failures in window
        failures_in_window = [
            f for f in self._failures.values()
            if f.failure_timestamp >= cutoff
        ]
        failures_in_window.sort(key=lambda f: f.failure_timestamp)

        # If there's a successful check in the window, only count failures after it
        if self._last_successful_check and self._last_successful_check >= cutoff:
            failures_in_window = [
                f for f in failures_in_window
                if f.failure_timestamp > self._last_successful_check
            ]

        return failures_in_window

    async def record_successful_check(self, check_timestamp: datetime) -> None:
        """Record a successful integrity check (breaks consecutive sequence).

        This resets the consecutive failure counter per FR37 requirements.

        Args:
            check_timestamp: When the successful check occurred (UTC).
        """
        self._last_successful_check = check_timestamp

    # Test helper methods (not part of protocol)

    def add_failure(
        self,
        failure_id: UUID,
        failure_timestamp: datetime,
        failure_type: str = "integrity_check_failed",
        description: str = "Test failure",
        event_id: Optional[UUID] = None,
    ) -> IntegrityFailure:
        """Add a failure directly (for testing).

        Args:
            failure_id: Unique identifier for the failure.
            failure_timestamp: When the failure occurred.
            failure_type: Category of failure.
            description: Human-readable description.
            event_id: Reference to the event that reported this failure.

        Returns:
            The created IntegrityFailure.
        """
        from uuid import uuid4
        failure = IntegrityFailure(
            failure_id=failure_id,
            failure_timestamp=failure_timestamp,
            failure_type=failure_type,
            description=description,
            event_id=event_id or uuid4(),
        )
        self._failures[failure_id] = failure
        return failure

    def get_failure_count(self) -> int:
        """Get total number of stored failures."""
        return len(self._failures)

    def get_last_successful_check(self) -> Optional[datetime]:
        """Get timestamp of last successful check."""
        return self._last_successful_check
