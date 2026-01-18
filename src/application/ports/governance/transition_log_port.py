"""Transition Log Port - Interface for state transition logging.

Story: consent-gov-9.4: State Transition Logging

This port defines the interface for transition log operations.
It is intentionally APPEND-ONLY with no modification or deletion methods.

Constitutional Requirements:
- FR59: System can log all state transitions with timestamp and actor
- FR60: System can prevent ledger modification (append-only enforcement)

Design Decisions:
- Only `append()` for writing - no update/delete
- Only `query()` and `get_by_id()` for reading
- Intentionally missing: update(), delete(), modify()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.domain.governance.audit.transition_log import (
        TransitionLog,
        TransitionQuery,
    )


class TransitionLogPort(Protocol):
    """Port for transition log operations.

    This is an APPEND-ONLY interface. There are no methods to
    modify or delete transition logs once they are appended.

    This is a design decision per FR60 - the audit trail must
    be immutable once recorded.

    ┌────────────────────────────────────────────────────────────────┐
    │  Intentionally NOT defined (FR60 compliance):                  │
    │  - update() - no modification of logs                          │
    │  - delete() - no deletion of logs                              │
    │  - modify() - no modification of logs                          │
    │  - remove() - no removal of logs                               │
    └────────────────────────────────────────────────────────────────┘
    """

    async def append(self, log: TransitionLog) -> None:
        """Append a transition log entry.

        This is the ONLY write operation. Once appended, a log
        cannot be modified or deleted.

        Args:
            log: The transition log to append.

        Raises:
            TransitionLogError: If append fails (e.g., duplicate log_id).
        """
        ...

    async def query(
        self,
        query: TransitionQuery,
    ) -> list[TransitionLog]:
        """Query transition logs.

        Read-only operation to find logs matching the query criteria.

        Args:
            query: Query parameters for filtering.

        Returns:
            List of matching transition logs in chronological order.
        """
        ...

    async def get_by_id(self, log_id: UUID) -> TransitionLog | None:
        """Get a specific transition log by ID.

        Read-only operation.

        Args:
            log_id: The log ID to retrieve.

        Returns:
            The transition log if found, None otherwise.
        """
        ...

    async def count(self, query: TransitionQuery | None = None) -> int:
        """Count transition logs matching query.

        Args:
            query: Optional query parameters. If None, counts all logs.

        Returns:
            Number of matching logs.
        """
        ...

    async def get_entity_history(
        self,
        entity_type: EntityType,  # noqa: F821
        entity_id: UUID,
    ) -> list[TransitionLog]:
        """Get complete transition history for an entity.

        Convenience method for getting all transitions of a specific
        entity in chronological order.

        Args:
            entity_type: Type of entity.
            entity_id: ID of the entity.

        Returns:
            All transition logs for the entity, oldest first.
        """
        ...

    # The following methods are intentionally NOT defined:
    #
    # async def update(self, log_id: UUID, log: TransitionLog) -> None:
    #     """Update would violate FR60 - logs are immutable."""
    #     ...
    #
    # async def delete(self, log_id: UUID) -> None:
    #     """Delete would violate FR60 - logs are permanent."""
    #     ...
    #
    # async def modify(self, log_id: UUID, changes: dict) -> TransitionLog:
    #     """Modify would violate FR60 - logs cannot be changed."""
    #     ...
    #
    # async def remove(self, log_id: UUID) -> bool:
    #     """Remove would violate FR60 - logs cannot be removed."""
    #     ...
