"""CheckpointRepository port for checkpoint anchor operations (Story 3.10, Task 2; Story 4.6, Task 3).

This module defines the port interface for checkpoint repository operations,
enabling operational rollback to checkpoint anchors (FR143) and Merkle-based
light verification (FR136, FR137, FR138).

Constitutional Constraints:
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Checkpoints are periodic anchors (minimum weekly)
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
- FR143: Rollback to checkpoint for infrastructure recovery
- FR143: Rollback is logged, does not undo canonical events
- PREVENT_DELETE: Events are never deleted, only marked orphaned

Usage:
    class PostgresCheckpointRepository(CheckpointRepository):
        async def get_all_checkpoints(self) -> list[Checkpoint]:
            ...

    # Type checking
    repo: CheckpointRepository = PostgresCheckpointRepository()
    checkpoints = await repo.get_all_checkpoints()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.checkpoint import Checkpoint


@runtime_checkable
class CheckpointRepository(Protocol):
    """Repository interface for checkpoint anchors (FR137, FR143).

    This port defines the contract for checkpoint storage and retrieval.
    Implementations may use PostgreSQL, in-memory storage, or other backends.

    Checkpoints enable:
    1. Operational recovery (rollback to known-good state)
    2. Observer verification (light verification via Merkle paths)
    3. Audit/compliance snapshots

    Constitutional Constraints:
    - FR137: Minimum weekly checkpoint creation
    - FR143: Rollback logged as constitutional event
    - CT-11: Operations must be witnessed and auditable
    """

    async def get_all_checkpoints(self) -> list["Checkpoint"]:
        """Get all available checkpoints ordered by sequence.

        Returns all checkpoint anchors in ascending order by event_sequence.
        Used for displaying rollback options to operators.

        Returns:
            List of Checkpoint objects ordered by event_sequence (ascending).
            Empty list if no checkpoints exist.
        """
        ...

    async def get_checkpoint_by_id(
        self,
        checkpoint_id: UUID,
    ) -> Optional["Checkpoint"]:
        """Get a specific checkpoint by its ID.

        Args:
            checkpoint_id: UUID of the checkpoint to retrieve.

        Returns:
            Checkpoint if found, None otherwise.
        """
        ...

    async def get_latest_checkpoint(self) -> Optional["Checkpoint"]:
        """Get the most recent checkpoint.

        Returns the checkpoint with the highest event_sequence.
        Useful for determining current anchor point.

        Returns:
            Most recent Checkpoint, or None if no checkpoints exist.
        """
        ...

    async def get_checkpoints_after_sequence(
        self,
        sequence: int,
    ) -> list["Checkpoint"]:
        """Get checkpoints with event_sequence greater than given sequence.

        Used to find valid rollback targets after a certain point.

        Args:
            sequence: Event sequence number (exclusive lower bound).

        Returns:
            List of Checkpoints with event_sequence > sequence,
            ordered by event_sequence (ascending).
        """
        ...

    async def create_checkpoint(
        self,
        event_sequence: int,
        anchor_hash: str,
        anchor_type: str,
        creator_id: str,
    ) -> "Checkpoint":
        """Create a new checkpoint anchor.

        Creates and persists a new checkpoint at the given event sequence.
        The checkpoint captures the current state of the event chain.

        Args:
            event_sequence: Event sequence number at checkpoint time.
            anchor_hash: Hash of the event chain at this point (SHA-256, 64 chars hex).
            anchor_type: Type of checkpoint ("genesis", "periodic", "manual").
            creator_id: ID of service/operator creating the checkpoint.

        Returns:
            Newly created Checkpoint with generated checkpoint_id and timestamp.

        Raises:
            ValueError: If event_sequence is negative or anchor_hash is invalid.
        """
        ...

    # ==========================================================================
    # Merkle-specific methods (Story 4.6 - FR136, FR137, FR138)
    # ==========================================================================

    async def get_checkpoint_for_sequence(
        self,
        sequence: int,
    ) -> Optional["Checkpoint"]:
        """Get the checkpoint containing a given event sequence (FR136).

        Finds the checkpoint whose event_sequence is >= the given sequence.
        This is used to find the Merkle root for an event.

        If the sequence is beyond all checkpoints (in the pending interval),
        returns None.

        Args:
            sequence: Event sequence number.

        Returns:
            Checkpoint containing the sequence, or None if in pending interval.
        """
        ...

    async def list_checkpoints(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list["Checkpoint"], int]:
        """List checkpoints with pagination (FR138).

        Returns checkpoints ordered by event_sequence descending (most recent first).

        Args:
            limit: Maximum checkpoints to return.
            offset: Number to skip.

        Returns:
            Tuple of (checkpoints, total_count).
        """
        ...

    async def update_anchor_reference(
        self,
        checkpoint_id: UUID,
        anchor_type: str,
        anchor_reference: str,
    ) -> None:
        """Update checkpoint with external anchor reference (FR137).

        Called after RFC 3161 timestamping or Bitcoin anchoring.

        Args:
            checkpoint_id: ID of checkpoint to update.
            anchor_type: New anchor type (rfc3161, genesis).
            anchor_reference: External anchor reference (TSA response, Bitcoin txid).
        """
        ...
