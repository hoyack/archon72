"""Cessation repository stub (Story 6.3, FR32).

In-memory implementation of CessationRepositoryProtocol for testing.
"""

from __future__ import annotations

from uuid import UUID

from src.application.ports.cessation_repository import CessationRepositoryProtocol
from src.domain.events.cessation import (
    CessationConsiderationEventPayload,
    CessationDecisionEventPayload,
)


class CessationRepositoryStub(CessationRepositoryProtocol):
    """In-memory implementation of CessationRepositoryProtocol.

    This stub stores cessation considerations and decisions in memory
    for testing purposes. Only one consideration can be active (without
    a decision) at a time.
    """

    def __init__(self) -> None:
        """Initialize empty in-memory storage."""
        self._considerations: dict[UUID, CessationConsiderationEventPayload] = {}
        self._decisions: dict[UUID, CessationDecisionEventPayload] = {}

    async def save_consideration(
        self,
        consideration: CessationConsiderationEventPayload,
    ) -> None:
        """Save a cessation consideration.

        Args:
            consideration: The consideration payload to save.
        """
        self._considerations[consideration.consideration_id] = consideration

    async def save_decision(
        self,
        decision: CessationDecisionEventPayload,
    ) -> None:
        """Save a cessation decision.

        Args:
            decision: The decision payload to save.
        """
        self._decisions[decision.consideration_id] = decision

    async def get_active_consideration(
        self,
    ) -> CessationConsiderationEventPayload | None:
        """Get the currently active cessation consideration, if any.

        A consideration is active if it exists and has no decision recorded.
        Returns the most recent active consideration by trigger_timestamp.

        Returns:
            The active consideration or None if no active consideration.
        """
        active = [
            c
            for c in self._considerations.values()
            if c.consideration_id not in self._decisions
        ]
        if not active:
            return None
        # Return the most recent by trigger_timestamp
        active.sort(key=lambda c: c.trigger_timestamp, reverse=True)
        return active[0]

    async def get_consideration_by_id(
        self,
        consideration_id: UUID,
    ) -> CessationConsiderationEventPayload | None:
        """Get a cessation consideration by its ID.

        Args:
            consideration_id: The ID of the consideration to retrieve.

        Returns:
            The consideration or None if not found.
        """
        return self._considerations.get(consideration_id)

    async def get_decision_for_consideration(
        self,
        consideration_id: UUID,
    ) -> CessationDecisionEventPayload | None:
        """Get the decision for a cessation consideration, if any.

        Args:
            consideration_id: The ID of the consideration.

        Returns:
            The decision or None if no decision recorded.
        """
        return self._decisions.get(consideration_id)

    async def list_considerations(
        self,
    ) -> list[CessationConsiderationEventPayload]:
        """List all cessation considerations.

        Returns:
            List of all considerations, ordered by trigger timestamp.
        """
        considerations = list(self._considerations.values())
        considerations.sort(key=lambda c: c.trigger_timestamp)
        return considerations

    def clear(self) -> None:
        """Clear all stored data for test cleanup.

        Resets the in-memory storage to an empty state. Use this method
        between test cases to ensure test isolation.

        This is a synchronous method (not async) for convenience in test
        fixtures and teardown.
        """
        self._considerations.clear()
        self._decisions.clear()
