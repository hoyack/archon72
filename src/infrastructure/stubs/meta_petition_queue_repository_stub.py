"""META petition queue repository stub implementation (Story 8.5, FR-10.4).

This module provides an in-memory stub implementation of
MetaPetitionQueueRepositoryProtocol for development and testing purposes.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> All operations logged
- CT-12: Witnessing creates accountability -> All writes tracked
- FR-10.4: META petitions SHALL route to High Archon [P2]
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.meta_petition_queue_repository import (
    MetaPetitionAlreadyResolvedError,
    MetaPetitionNotFoundError,
    MetaPetitionQueueRepositoryProtocol,
    PetitionAlreadyInQueueError,
)
from src.domain.models.meta_petition import (
    MetaDisposition,
    MetaPetitionQueueItem,
    MetaPetitionStatus,
)


class MetaPetitionQueueRepositoryStub(MetaPetitionQueueRepositoryProtocol):
    """In-memory stub implementation of MetaPetitionQueueRepositoryProtocol.

    This stub stores META petition queue items in memory for development
    and testing. It is NOT suitable for production use.

    Constitutional Compliance:
    - AC3: Queue returns sorted by received_at (FIFO)
    - FR-10.4: META petitions route to High Archon queue

    Attributes:
        _queue: Dictionary mapping petition_id to queue data.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        # Internal storage: petition_id -> (item, resolution_data)
        self._queue: dict[UUID, dict] = {}

    async def enqueue(
        self,
        petition_id: UUID,
        submitter_id: UUID | None,
        petition_text: str,
    ) -> MetaPetitionQueueItem:
        """Enqueue a META petition for High Archon review.

        Args:
            petition_id: UUID of the META petition.
            submitter_id: UUID of the petition submitter (optional).
            petition_text: Full text of the petition.

        Returns:
            The created MetaPetitionQueueItem.

        Raises:
            PetitionAlreadyInQueueError: If petition_id already in queue.
        """
        if petition_id in self._queue:
            raise PetitionAlreadyInQueueError(petition_id)

        now = datetime.now(timezone.utc)

        item = MetaPetitionQueueItem(
            petition_id=petition_id,
            submitter_id=submitter_id if submitter_id else UUID(int=0),
            petition_text=petition_text,
            received_at=now,
            status=MetaPetitionStatus.PENDING,
        )

        self._queue[petition_id] = {
            "item": item,
            "enqueued_at": now,
            "resolved_at": None,
            "resolved_by": None,
            "disposition": None,
            "rationale": None,
            "forward_target": None,
        }

        return item

    async def get_pending(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MetaPetitionQueueItem], int]:
        """List pending META petitions for High Archon review.

        Returns petitions with status=PENDING, ordered by enqueued_at ASC
        (oldest first for FIFO processing).

        Args:
            limit: Maximum number of items to return.
            offset: Number of items to skip for pagination.

        Returns:
            Tuple of (list of queue items, total pending count).
        """
        # Filter pending items
        pending = [
            data
            for data in self._queue.values()
            if data["item"].status == MetaPetitionStatus.PENDING
        ]

        # Sort by enqueued_at ASC (FIFO)
        pending.sort(key=lambda x: x["enqueued_at"])

        total = len(pending)

        # Apply pagination
        paginated = pending[offset : offset + limit]

        return [data["item"] for data in paginated], total

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
        data = self._queue.get(petition_id)
        return data["item"] if data else None

    async def mark_resolved(
        self,
        petition_id: UUID,
        high_archon_id: UUID,
        disposition: MetaDisposition,
        rationale: str,
        forward_target: str | None = None,
    ) -> MetaPetitionQueueItem:
        """Mark a META petition as resolved by High Archon.

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
            ValueError: If FORWARD without forward_target.
        """
        data = self._queue.get(petition_id)
        if not data:
            raise MetaPetitionNotFoundError(petition_id)

        current_item = data["item"]
        if current_item.status == MetaPetitionStatus.RESOLVED:
            raise MetaPetitionAlreadyResolvedError(petition_id)

        if disposition == MetaDisposition.FORWARD and not forward_target:
            raise ValueError("forward_target required for FORWARD disposition")

        now = datetime.now(timezone.utc)

        # Create updated item with RESOLVED status
        resolved_item = MetaPetitionQueueItem(
            petition_id=current_item.petition_id,
            submitter_id=current_item.submitter_id,
            petition_text=current_item.petition_text,
            received_at=current_item.received_at,
            status=MetaPetitionStatus.RESOLVED,
        )

        # Update storage
        self._queue[petition_id] = {
            "item": resolved_item,
            "enqueued_at": data["enqueued_at"],
            "resolved_at": now,
            "resolved_by": high_archon_id,
            "disposition": disposition,
            "rationale": rationale,
            "forward_target": forward_target,
        }

        return resolved_item

    async def get_resolved(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MetaPetitionQueueItem], int]:
        """List resolved META petitions (for audit/history).

        Returns petitions with status=RESOLVED, ordered by resolved_at DESC
        (most recent first).

        Args:
            limit: Maximum number of items to return.
            offset: Number of items to skip for pagination.

        Returns:
            Tuple of (list of resolved queue items, total resolved count).
        """
        # Filter resolved items
        resolved = [
            data
            for data in self._queue.values()
            if data["item"].status == MetaPetitionStatus.RESOLVED
        ]

        # Sort by resolved_at DESC (most recent first)
        resolved.sort(key=lambda x: x["resolved_at"] or datetime.min, reverse=True)

        total = len(resolved)

        # Apply pagination
        paginated = resolved[offset : offset + limit]

        return [data["item"] for data in paginated], total

    async def count_pending(self) -> int:
        """Count pending META petitions.

        Returns:
            Number of petitions with status=PENDING.
        """
        return sum(
            1
            for data in self._queue.values()
            if data["item"].status == MetaPetitionStatus.PENDING
        )

    # Test helper methods

    def clear(self) -> None:
        """Clear all queue items (test helper)."""
        self._queue.clear()

    def get_resolution_details(self, petition_id: UUID) -> dict | None:
        """Get resolution details for a petition (test helper).

        Returns dict with resolved_by, disposition, rationale, forward_target.
        """
        data = self._queue.get(petition_id)
        if not data:
            return None
        return {
            "resolved_at": data["resolved_at"],
            "resolved_by": data["resolved_by"],
            "disposition": data["disposition"],
            "rationale": data["rationale"],
            "forward_target": data["forward_target"],
        }
