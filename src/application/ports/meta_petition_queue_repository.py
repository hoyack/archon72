"""META petition queue repository port (Story 8.5, FR-10.4).

This module defines the abstract interface for META petition queue operations.
META petitions bypass normal deliberation and route directly to High Archon.

Constitutional Constraints:
- FR-10.4: META petitions SHALL route to High Archon [P2]
- META-1: Prevents deadlock from system-about-system petitions
- CT-11: Silent failure destroys legitimacy -> All operations must be logged
- CT-12: Witnessing creates accountability -> All writes are witnessed
- CT-13: No writes during halt -> Service layer checks halt, not repository

Developer Golden Rules:
1. HALT CHECK FIRST - Service layer checks halt, not repository
2. WITNESS EVERYTHING - Repository stores, service witnesses
3. FAIL LOUD - Repository raises on errors
4. READS DURING HALT - Repository reads work during halt (CT-13)
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.models.meta_petition import (
    MetaDisposition,
    MetaPetitionQueueItem,
    MetaPetitionStatus,
)


class MetaPetitionQueueRepositoryProtocol(Protocol):
    """Protocol for META petition queue storage operations (Story 8.5, AC3).

    Defines the contract for META petition queue persistence. The queue
    holds META petitions awaiting High Archon review.

    Constitutional Constraints:
    - AC3: Queue returns sorted by received_at (FIFO)
    - FR-10.4: META petitions route to High Archon queue

    Methods:
        enqueue: Add a META petition to the High Archon queue
        get_pending: List pending META petitions (FIFO order)
        get_by_petition_id: Retrieve queue item by petition ID
        mark_resolved: Mark a META petition as resolved with disposition
    """

    async def enqueue(
        self,
        petition_id: UUID,
        submitter_id: UUID | None,
        petition_text: str,
    ) -> MetaPetitionQueueItem:
        """Enqueue a META petition for High Archon review (AC2).

        Creates a new queue entry with status=PENDING. The petition
        bypasses normal deliberation and awaits High Archon action.

        Args:
            petition_id: UUID of the META petition.
            submitter_id: UUID of the petition submitter (optional).
            petition_text: Full text of the petition.

        Returns:
            The created MetaPetitionQueueItem.

        Raises:
            PetitionAlreadyInQueueError: If petition_id already in queue.
        """
        ...

    async def get_pending(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MetaPetitionQueueItem], int]:
        """List pending META petitions for High Archon review (AC3).

        Returns petitions with status=PENDING, ordered by enqueued_at ASC
        (oldest first for FIFO processing).

        Args:
            limit: Maximum number of items to return (default 50, max 100).
            offset: Number of items to skip for pagination.

        Returns:
            Tuple of (list of queue items, total pending count).
        """
        ...

    async def get_by_petition_id(
        self,
        petition_id: UUID,
    ) -> MetaPetitionQueueItem | None:
        """Retrieve queue item by petition ID.

        Args:
            petition_id: UUID of the META petition.

        Returns:
            The MetaPetitionQueueItem if found, None otherwise.
        """
        ...

    async def mark_resolved(
        self,
        petition_id: UUID,
        high_archon_id: UUID,
        disposition: MetaDisposition,
        rationale: str,
        forward_target: str | None = None,
    ) -> MetaPetitionQueueItem:
        """Mark a META petition as resolved by High Archon (AC4).

        Updates the queue entry with resolution details:
        - status = RESOLVED
        - resolved_at = now()
        - resolved_by = high_archon_id
        - disposition, rationale, forward_target

        Constitutional Constraints:
        - CT-13: High Archon explicit consent through disposition
        - CT-12: Resolution witnessed through resolved_by attribution

        Args:
            petition_id: UUID of the META petition to resolve.
            high_archon_id: UUID of the High Archon resolving.
            disposition: ACKNOWLEDGE, CREATE_ACTION, or FORWARD.
            rationale: High Archon's rationale (required).
            forward_target: Target governance body if disposition=FORWARD.

        Returns:
            The updated MetaPetitionQueueItem with resolution details.

        Raises:
            MetaPetitionNotFoundError: If petition not in queue.
            MetaPetitionAlreadyResolvedError: If petition already resolved.
            ValidationError: If FORWARD without forward_target.
        """
        ...

    async def get_resolved(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MetaPetitionQueueItem], int]:
        """List resolved META petitions (for audit/history).

        Returns petitions with status=RESOLVED, ordered by resolved_at DESC
        (most recent first).

        Args:
            limit: Maximum number of items to return (default 50, max 100).
            offset: Number of items to skip for pagination.

        Returns:
            Tuple of (list of resolved queue items, total resolved count).
        """
        ...

    async def count_pending(self) -> int:
        """Count pending META petitions (for metrics).

        Returns:
            Number of petitions with status=PENDING.
        """
        ...


class MetaPetitionNotFoundError(Exception):
    """Raised when a META petition is not found in the queue."""

    def __init__(self, petition_id: UUID) -> None:
        self.petition_id = petition_id
        super().__init__(f"META petition not found in queue: {petition_id}")


class MetaPetitionAlreadyResolvedError(Exception):
    """Raised when attempting to resolve an already-resolved META petition."""

    def __init__(self, petition_id: UUID) -> None:
        self.petition_id = petition_id
        super().__init__(f"META petition already resolved: {petition_id}")


class PetitionAlreadyInQueueError(Exception):
    """Raised when attempting to enqueue a petition that's already in queue."""

    def __init__(self, petition_id: UUID) -> None:
        self.petition_id = petition_id
        super().__init__(f"Petition already in META queue: {petition_id}")
