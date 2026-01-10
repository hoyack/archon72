"""CheckpointRepositoryStub for testing (Story 3.10, Task 3; Story 4.6, Task 3).

This module provides an in-memory stub implementation of CheckpointRepository
for unit and integration testing.

Constitutional Constraints:
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Checkpoints are periodic anchors (minimum weekly)
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
- FR143: Rollback to checkpoint for infrastructure recovery
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from src.application.ports.checkpoint_repository import CheckpointRepository
from src.domain.models.checkpoint import Checkpoint


class CheckpointRepositoryStub(CheckpointRepository):
    """In-memory stub implementation of CheckpointRepository for testing.

    This stub stores checkpoints in memory and provides all repository
    operations. Useful for unit tests and integration tests that don't
    require a real database.

    Example:
        >>> stub = CheckpointRepositoryStub()
        >>> stub.seed_checkpoints([checkpoint1, checkpoint2])
        >>> checkpoints = await stub.get_all_checkpoints()
    """

    def __init__(self) -> None:
        """Initialize empty checkpoint repository."""
        self._checkpoints: dict[UUID, Checkpoint] = {}
        self._anchor_references: dict[UUID, dict[str, str]] = {}

    def seed_checkpoints(self, checkpoints: list[Checkpoint]) -> None:
        """Seed the repository with test checkpoints.

        Args:
            checkpoints: List of Checkpoint objects to add.
        """
        for cp in checkpoints:
            self._checkpoints[cp.checkpoint_id] = cp

    def reset(self) -> None:
        """Clear all checkpoints from the repository."""
        self._checkpoints.clear()

    async def get_all_checkpoints(self) -> list[Checkpoint]:
        """Get all available checkpoints ordered by sequence.

        Returns:
            List of Checkpoint objects ordered by event_sequence (ascending).
        """
        return sorted(
            self._checkpoints.values(),
            key=lambda c: c.event_sequence,
        )

    async def get_checkpoint_by_id(
        self,
        checkpoint_id: UUID,
    ) -> Optional[Checkpoint]:
        """Get a specific checkpoint by its ID.

        Args:
            checkpoint_id: UUID of the checkpoint to retrieve.

        Returns:
            Checkpoint if found, None otherwise.
        """
        return self._checkpoints.get(checkpoint_id)

    async def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint.

        Returns:
            Most recent Checkpoint (highest event_sequence), or None.
        """
        if not self._checkpoints:
            return None

        return max(
            self._checkpoints.values(),
            key=lambda c: c.event_sequence,
        )

    async def get_checkpoints_after_sequence(
        self,
        sequence: int,
    ) -> list[Checkpoint]:
        """Get checkpoints with event_sequence greater than given sequence.

        Args:
            sequence: Event sequence number (exclusive lower bound).

        Returns:
            List of Checkpoints with event_sequence > sequence,
            ordered by event_sequence (ascending).
        """
        filtered = [
            cp for cp in self._checkpoints.values() if cp.event_sequence > sequence
        ]
        return sorted(filtered, key=lambda c: c.event_sequence)

    async def create_checkpoint(
        self,
        event_sequence: int,
        anchor_hash: str,
        anchor_type: str,
        creator_id: str,
    ) -> Checkpoint:
        """Create a new checkpoint anchor.

        Args:
            event_sequence: Event sequence number at checkpoint time.
            anchor_hash: Hash of the event chain at this point.
            anchor_type: Type of checkpoint ("genesis", "periodic", "manual").
            creator_id: ID of service/operator creating the checkpoint.

        Returns:
            Newly created Checkpoint with generated checkpoint_id and timestamp.
        """
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=event_sequence,
            timestamp=datetime.now(timezone.utc),
            anchor_hash=anchor_hash,
            anchor_type=anchor_type,
            creator_id=creator_id,
        )

        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        return checkpoint

    # ==========================================================================
    # Merkle-specific methods (Story 4.6 - FR136, FR137, FR138)
    # ==========================================================================

    async def get_checkpoint_for_sequence(
        self,
        sequence: int,
    ) -> Optional[Checkpoint]:
        """Get the checkpoint containing a given event sequence (FR136).

        Finds the checkpoint whose event_sequence is >= the given sequence.
        Returns None if sequence is beyond all checkpoints (pending interval).

        Args:
            sequence: Event sequence number.

        Returns:
            Checkpoint containing the sequence, or None if in pending interval.
        """
        if not self._checkpoints:
            return None

        # Sort checkpoints by sequence ascending
        sorted_checkpoints = sorted(
            self._checkpoints.values(),
            key=lambda c: c.event_sequence,
        )

        # Find first checkpoint whose sequence >= target
        for cp in sorted_checkpoints:
            if cp.event_sequence >= sequence:
                return cp

        # Sequence is beyond all checkpoints
        return None

    async def list_checkpoints(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[Checkpoint], int]:
        """List checkpoints with pagination (FR138).

        Returns checkpoints ordered by event_sequence descending (most recent first).

        Args:
            limit: Maximum checkpoints to return.
            offset: Number to skip.

        Returns:
            Tuple of (checkpoints, total_count).
        """
        total = len(self._checkpoints)

        # Sort by sequence descending
        sorted_checkpoints = sorted(
            self._checkpoints.values(),
            key=lambda c: c.event_sequence,
            reverse=True,
        )

        # Apply pagination
        paginated = sorted_checkpoints[offset : offset + limit]

        return paginated, total

    async def update_anchor_reference(
        self,
        checkpoint_id: UUID,
        anchor_type: str,
        anchor_reference: str,
    ) -> None:
        """Update checkpoint with external anchor reference (FR137).

        Since Checkpoint is immutable, this creates a new checkpoint with
        updated fields and replaces the old one.

        Args:
            checkpoint_id: ID of checkpoint to update.
            anchor_type: New anchor type (rfc3161, genesis).
            anchor_reference: External anchor reference.
        """
        old_cp = self._checkpoints.get(checkpoint_id)
        if old_cp is None:
            return

        # Create new checkpoint with updated fields
        # Note: We store the anchor_reference in a separate dict for the stub
        # since Checkpoint doesn't have anchor_reference field
        # In production, this would be a proper DB update
        self._anchor_references[checkpoint_id] = {
            "anchor_type": anchor_type,
            "anchor_reference": anchor_reference,
        }
