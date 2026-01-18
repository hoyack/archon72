"""Breach repository port (Story 6.1, FR30).

This module defines the repository interface for storing and querying
breach events.

Constitutional Constraints:
- FR30: Breach history shall be filterable by type and date
- CT-11: Silent failure destroys legitimacy -> Query failures must not be silent
- CT-12: Witnessing creates accountability -> All stored breaches were witnessed
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.events.breach import BreachEventPayload, BreachType


class BreachRepositoryProtocol(Protocol):
    """Protocol for breach event storage and retrieval (FR30).

    This protocol defines the interface for storing breach events
    and querying breach history with filtering capabilities.

    All implementations must support filtering by:
    - Breach type
    - Date range
    - Both type and date range combined

    Constitutional Constraint (FR30):
    Breach history queries support filtering by type and date range.
    """

    async def save(self, breach: BreachEventPayload) -> None:
        """Save a breach event to storage.

        Constitutional Constraint:
        The breach event is assumed to have already been witnessed
        via the EventWriterService before being saved here.

        Args:
            breach: The breach event payload to save.

        Raises:
            BreachDeclarationError: If save fails.
        """
        ...

    async def get_by_id(self, breach_id: UUID) -> BreachEventPayload | None:
        """Retrieve a specific breach event by ID.

        Args:
            breach_id: The unique identifier of the breach event.

        Returns:
            The breach event payload if found, None otherwise.

        Raises:
            BreachQueryError: If query fails.
        """
        ...

    async def list_all(self) -> list[BreachEventPayload]:
        """Retrieve all breach events.

        Returns:
            List of all stored breach events, ordered by detection_timestamp.

        Raises:
            BreachQueryError: If query fails.
        """
        ...

    async def filter_by_type(self, breach_type: BreachType) -> list[BreachEventPayload]:
        """Retrieve breach events filtered by type (FR30).

        Args:
            breach_type: The type of breach to filter by.

        Returns:
            List of breach events matching the type.

        Raises:
            BreachQueryError: If query fails.
        """
        ...

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
            List of breach events within the date range.

        Raises:
            BreachQueryError: If query fails.
        """
        ...

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
            List of breach events matching type within the date range.

        Raises:
            BreachQueryError: If query fails.
        """
        ...

    async def count_unacknowledged_in_window(self, window_days: int) -> int:
        """Count unacknowledged breaches within a rolling window.

        This supports Story 6.3's cessation trigger: >10 unacknowledged
        breaches in 90 days triggers cessation consideration.

        Args:
            window_days: The rolling window in days (e.g., 90).

        Returns:
            Count of unacknowledged breaches in the window.

        Raises:
            BreachQueryError: If query fails.
        """
        ...

    async def get_unacknowledged_in_window(
        self, window_days: int
    ) -> list[BreachEventPayload]:
        """Get all unacknowledged breaches within a rolling window.

        This supports Story 6.3's cessation consideration: returns all
        breach events that need to be referenced in the cessation event.

        Args:
            window_days: The rolling window in days (e.g., 90).

        Returns:
            List of unacknowledged breach events in the window.

        Raises:
            BreachQueryError: If query fails.
        """
        ...

    async def get_breaches_by_witness_pair(
        self, pair_key: str
    ) -> list[BreachEventPayload]:
        """Get all breaches involving a specific witness pair (Story 6.8, FR124).

        This supports collusion detection by finding breaches that involved
        a particular witness pair, enabling correlation analysis.

        Args:
            pair_key: Canonical key of the witness pair (e.g., "witness_a:witness_b").

        Returns:
            List of breach events involving the pair.

        Raises:
            BreachQueryError: If query fails.
        """
        ...
