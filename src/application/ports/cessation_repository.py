"""Cessation repository port (Story 6.3, FR32).

This module defines the protocol for cessation consideration persistence.

Constitutional Constraints:
- FR32: Cessation considerations and decisions must be persisted
- CT-12: All cessation events are witnessed via EventWriterService
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.events.cessation import (
    CessationConsiderationEventPayload,
    CessationDecisionEventPayload,
)


@runtime_checkable
class CessationRepositoryProtocol(Protocol):
    """Protocol for cessation consideration persistence (FR32).

    This protocol defines storage operations for:
    - Cessation considerations (when triggered)
    - Cessation decisions (when Conclave decides)

    Note: The actual witnessed events are written via EventWriterService.
    This repository tracks the operational state for querying.
    """

    async def save_consideration(
        self,
        consideration: CessationConsiderationEventPayload,
    ) -> None:
        """Save a cessation consideration.

        Args:
            consideration: The consideration payload to save.
        """
        ...

    async def save_decision(
        self,
        decision: CessationDecisionEventPayload,
    ) -> None:
        """Save a cessation decision.

        Args:
            decision: The decision payload to save.
        """
        ...

    async def get_active_consideration(
        self,
    ) -> CessationConsiderationEventPayload | None:
        """Get the currently active cessation consideration, if any.

        A consideration is active if it exists and has no decision recorded.

        Returns:
            The active consideration or None if no active consideration.
        """
        ...

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
        ...

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
        ...

    async def list_considerations(
        self,
    ) -> list[CessationConsiderationEventPayload]:
        """List all cessation considerations.

        Returns:
            List of all considerations, ordered by trigger timestamp.
        """
        ...
