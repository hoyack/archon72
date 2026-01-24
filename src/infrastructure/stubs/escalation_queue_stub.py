"""Escalation Queue Stub for testing (Story 6.1, FR-5.4).

This module provides a configurable stub implementation of EscalationQueueProtocol
for use in unit and integration tests.

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- CT-13: Halt check first pattern
- D8: Keyset pagination for efficient cursor-based navigation
- RULING-3: Realm-scoped data access
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.ports.escalation_queue import (
    EscalationQueueItem,
    EscalationQueueResult,
    EscalationSource,
)
from src.domain.models.petition_submission import PetitionType


@dataclass
class QueueQueryEntry:
    """Record of a queue query attempt (for test assertions).

    Attributes:
        king_id: UUID of the King requesting the queue.
        realm_id: Realm ID for the King's domain.
        cursor: Cursor used for pagination (if any).
        limit: Maximum number of items requested.
        timestamp: When the query was executed.
        result_count: Number of items returned.
    """

    king_id: UUID
    realm_id: str
    cursor: str | None
    limit: int
    timestamp: datetime
    result_count: int


class EscalationQueueStub:
    """Stub implementation of EscalationQueueProtocol for testing (Story 6.1).

    Provides full control over escalation queue behavior for testing
    different scenarios including:
    - Empty queue
    - Populated queue with pagination
    - Realm filtering
    - Cursor navigation
    - Failure simulation

    Attributes:
        _escalations: Dict mapping realm_id to list of escalation items.
        _query_history: List of all queue queries for assertions.
        _fail_next: Whether to simulate failure on next query.
    """

    def __init__(self) -> None:
        """Initialize escalation queue stub."""
        self._escalations: dict[str, list[EscalationQueueItem]] = {}
        self._query_history: list[QueueQueryEntry] = []
        self._fail_next: bool = False
        self._fail_exception: Exception | None = None

    async def get_queue(
        self,
        king_id: UUID,
        realm_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> EscalationQueueResult:
        """Get the escalation queue for a King's realm.

        Args:
            king_id: UUID of the King requesting the queue.
            realm_id: Realm ID for the King's domain (e.g., "governance").
            cursor: Optional cursor for pagination (keyset-based).
            limit: Maximum number of items to return (default 20, max 100).

        Returns:
            EscalationQueueResult with items, next_cursor, and has_more flag.

        Raises:
            Exception: If fail_next is set with an exception.
        """
        timestamp = datetime.now()

        # Check for configured failure
        if self._fail_next:
            self._fail_next = False
            if self._fail_exception is not None:
                exc = self._fail_exception
                self._fail_exception = None
                raise exc
            raise RuntimeError("Simulated queue query failure")

        # Get escalations for this realm
        realm_escalations = self._escalations.get(realm_id, [])

        # Apply cursor filtering (simplified - in real impl, use keyset)
        filtered_items = list(realm_escalations)
        if cursor:
            # In a real stub, decode cursor and filter
            # For simplicity, we just skip items based on cursor position
            try:
                cursor_index = int(cursor)
                filtered_items = filtered_items[cursor_index:]
            except (ValueError, IndexError):
                filtered_items = []

        # Apply limit and determine has_more
        has_more = len(filtered_items) > limit
        items = filtered_items[:limit]

        # Build next cursor if there are more items
        next_cursor = None
        if has_more:
            # In real impl, encode last item's (escalated_at, petition_id)
            # For simplicity, use position
            current_position = len(realm_escalations) - len(filtered_items)
            next_cursor = str(current_position + limit)

        # Record query for assertions
        self._query_history.append(
            QueueQueryEntry(
                king_id=king_id,
                realm_id=realm_id,
                cursor=cursor,
                limit=limit,
                timestamp=timestamp,
                result_count=len(items),
            )
        )

        return EscalationQueueResult(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    # Test helper methods

    def add_escalation(
        self,
        realm_id: str,
        petition_id: UUID,
        petition_type: PetitionType,
        escalation_source: EscalationSource,
        co_signer_count: int,
        escalated_at: datetime,
    ) -> None:
        """Add an escalation to the queue (test helper).

        Args:
            realm_id: Realm ID for the escalation.
            petition_id: UUID of the escalated petition.
            petition_type: Type of petition.
            escalation_source: What triggered the escalation.
            co_signer_count: Number of co-signers.
            escalated_at: When the petition was escalated.
        """
        if realm_id not in self._escalations:
            self._escalations[realm_id] = []

        item = EscalationQueueItem(
            petition_id=petition_id,
            petition_type=petition_type,
            escalation_source=escalation_source,
            co_signer_count=co_signer_count,
            escalated_at=escalated_at,
        )

        self._escalations[realm_id].append(item)

        # Sort by escalated_at (FIFO)
        self._escalations[realm_id].sort(key=lambda x: (x.escalated_at, x.petition_id))

    def add_escalation_item(self, realm_id: str, item: EscalationQueueItem) -> None:
        """Add an escalation item to the queue (test helper).

        Args:
            realm_id: Realm ID for the escalation.
            item: The escalation queue item to add.
        """
        if realm_id not in self._escalations:
            self._escalations[realm_id] = []

        self._escalations[realm_id].append(item)

        # Sort by escalated_at (FIFO)
        self._escalations[realm_id].sort(key=lambda x: (x.escalated_at, x.petition_id))

    def get_realm_escalations(self, realm_id: str) -> list[EscalationQueueItem]:
        """Get all escalations for a realm (test helper).

        Args:
            realm_id: Realm ID to query.

        Returns:
            List of escalation items for the realm.
        """
        return list(self._escalations.get(realm_id, []))

    def get_escalation_count(self, realm_id: str) -> int:
        """Get count of escalations for a realm (test helper).

        Args:
            realm_id: Realm ID to query.

        Returns:
            Number of escalations in the queue for the realm.
        """
        return len(self._escalations.get(realm_id, []))

    def fail_next(self, exception: Exception | None = None) -> None:
        """Configure next query to fail (test helper).

        Args:
            exception: Optional exception to raise. Defaults to RuntimeError.
        """
        self._fail_next = True
        self._fail_exception = exception

    def get_query_history(self) -> list[QueueQueryEntry]:
        """Get all queue queries (test helper).

        Returns:
            List of all queue query history entries.
        """
        return list(self._query_history)

    def get_queries_for_realm(self, realm_id: str) -> list[QueueQueryEntry]:
        """Get queue queries for a specific realm (test helper).

        Args:
            realm_id: Realm ID to filter by.

        Returns:
            List of queue query entries for the realm.
        """
        return [q for q in self._query_history if q.realm_id == realm_id]

    def reset(self) -> None:
        """Reset all state (test helper)."""
        self._escalations.clear()
        self._query_history.clear()
        self._fail_next = False
        self._fail_exception = None

    @classmethod
    def empty(cls) -> EscalationQueueStub:
        """Factory for stub with empty queue.

        Returns:
            EscalationQueueStub with no escalations.
        """
        return cls()

    @classmethod
    def with_escalations(
        cls,
        realm_id: str,
        *items: EscalationQueueItem,
    ) -> EscalationQueueStub:
        """Factory for stub with pre-populated escalations.

        Args:
            realm_id: Realm ID for the escalations.
            items: Escalation items to add.

        Returns:
            EscalationQueueStub with specified escalations.
        """
        stub = cls()
        for item in items:
            stub.add_escalation_item(realm_id, item)
        return stub

    @classmethod
    def failing(cls, exception: Exception | None = None) -> EscalationQueueStub:
        """Factory for stub that will fail on next query.

        Args:
            exception: Optional exception to raise.

        Returns:
            EscalationQueueStub configured to fail.
        """
        stub = cls()
        stub.fail_next(exception)
        return stub
