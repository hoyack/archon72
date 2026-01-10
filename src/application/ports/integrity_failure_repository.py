"""Integrity failure repository port (Story 7.1, FR37, RT-4).

This module defines the repository interface for tracking and querying
integrity failure events that can trigger cessation agenda placement.

Constitutional Constraints:
- FR37: 3 consecutive integrity failures in 30 days triggers cessation
- RT-4: 5 failures in 90-day rolling window prevents timing attacks
- CT-11: Silent failure destroys legitimacy -> Query failures must not be silent
- CT-12: Witnessing creates accountability -> All stored failures were witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class IntegrityFailure:
    """An integrity failure event record.

    Represents a recorded integrity failure that can contribute to
    triggering cessation agenda placement.

    Attributes:
        failure_id: Unique identifier for this failure.
        failure_timestamp: When the failure occurred (UTC).
        failure_type: Category of integrity failure.
        description: Human-readable description of the failure.
        event_id: Reference to the original event that reported this failure.
    """

    failure_id: UUID
    failure_timestamp: datetime
    failure_type: str
    description: str
    event_id: UUID


class IntegrityFailureRepositoryProtocol(Protocol):
    """Protocol for integrity failure tracking and retrieval (FR37, RT-4).

    This protocol defines the interface for tracking integrity failures
    that can trigger automatic cessation agenda placement:
    - FR37: 3 consecutive failures in 30 days
    - RT-4: 5 failures in any 90-day rolling window

    Constitutional Constraint (CT-11):
    Query failures must not be silent - raise specific errors.

    Constitutional Constraint (CT-12):
    All stored failures are assumed to have been witnessed
    before being recorded.
    """

    async def save(self, failure: IntegrityFailure) -> None:
        """Save an integrity failure to storage.

        Constitutional Constraint:
        The failure event is assumed to have already been witnessed
        via the EventWriterService before being saved here.

        Args:
            failure: The integrity failure to save.

        Raises:
            IntegrityFailureRepositoryError: If save fails.
        """
        ...

    async def get_by_id(self, failure_id: UUID) -> IntegrityFailure | None:
        """Retrieve a specific integrity failure by ID.

        Args:
            failure_id: The unique identifier of the failure.

        Returns:
            The failure record if found, None otherwise.

        Raises:
            IntegrityFailureRepositoryError: If query fails.
        """
        ...

    async def count_consecutive_in_window(
        self,
        window_days: int,
    ) -> int:
        """Count consecutive integrity failures within a time window (FR37).

        This supports FR37's trigger: 3 consecutive failures in 30 days.
        "Consecutive" means no successful integrity check between failures.

        Args:
            window_days: The rolling window in days (e.g., 30).

        Returns:
            Count of consecutive failures in the window.

        Raises:
            IntegrityFailureRepositoryError: If query fails.
        """
        ...

    async def count_in_rolling_window(
        self,
        window_days: int,
    ) -> int:
        """Count all integrity failures within a rolling window (RT-4).

        This supports RT-4's alternative trigger: 5 failures in 90 days.
        Non-consecutive failures count toward this threshold.

        Args:
            window_days: The rolling window in days (e.g., 90).

        Returns:
            Total count of failures in the window.

        Raises:
            IntegrityFailureRepositoryError: If query fails.
        """
        ...

    async def get_failures_in_window(
        self,
        window_days: int,
    ) -> list[IntegrityFailure]:
        """Get all integrity failures within a rolling window.

        Args:
            window_days: The rolling window in days.

        Returns:
            List of failures within the window, ordered by timestamp.

        Raises:
            IntegrityFailureRepositoryError: If query fails.
        """
        ...

    async def get_consecutive_failures_in_window(
        self,
        window_days: int,
    ) -> list[IntegrityFailure]:
        """Get consecutive integrity failures within a time window (FR37).

        Returns only the sequence of consecutive failures (no successful
        checks between them) that occurred in the window.

        Args:
            window_days: The rolling window in days (e.g., 30).

        Returns:
            List of consecutive failures, ordered by timestamp.

        Raises:
            IntegrityFailureRepositoryError: If query fails.
        """
        ...

    async def record_successful_check(self, check_timestamp: datetime) -> None:
        """Record a successful integrity check (breaks consecutive sequence).

        This resets the consecutive failure counter per FR37 requirements.

        Args:
            check_timestamp: When the successful check occurred (UTC).

        Raises:
            IntegrityFailureRepositoryError: If recording fails.
        """
        ...
