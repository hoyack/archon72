"""Checkpoint generation worker stub (Story 4.6, Task 8).

Stub implementation for periodic checkpoint generation.
Per FR138: Weekly checkpoint anchors SHALL be published at consistent intervals.

This stub provides the interface for checkpoint generation but does not
implement actual periodic scheduling. Production implementation would:
1. Run on a schedule (weekly)
2. Build Merkle tree from events since last checkpoint
3. Store checkpoint with Merkle root
4. Optionally anchor to external timestamp authority

STUB: This is a placeholder for future production implementation.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from src.application.ports.checkpoint_repository import CheckpointRepository
    from src.application.ports.event_store import EventStorePort
    from src.application.services.merkle_tree_service import MerkleTreeService
    from src.domain.models.checkpoint import Checkpoint


class CheckpointWorkerStub:
    """Stub for periodic checkpoint generation (FR138).

    This stub provides the interface for checkpoint generation
    but does not implement actual scheduling.

    Usage:
        worker = CheckpointWorkerStub(
            event_store=event_store,
            checkpoint_repo=checkpoint_repo,
            merkle_service=merkle_service,
        )
        # Manual trigger for testing:
        checkpoint = await worker.generate_checkpoint()
    """

    def __init__(
        self,
        event_store: "EventStorePort",
        checkpoint_repo: "CheckpointRepository",
        merkle_service: "MerkleTreeService",
        checkpoint_interval_days: int = 7,  # Weekly per FR138
    ) -> None:
        """Initialize checkpoint worker stub.

        Args:
            event_store: Port for reading events.
            checkpoint_repo: Port for storing checkpoints.
            merkle_service: Service for building Merkle trees.
            checkpoint_interval_days: Days between checkpoints (default 7).
        """
        self._event_store = event_store
        self._checkpoint_repo = checkpoint_repo
        self._merkle_service = merkle_service
        self._checkpoint_interval_days = checkpoint_interval_days

    async def generate_checkpoint(self) -> "Checkpoint":
        """Generate a new checkpoint from current events.

        Creates a checkpoint containing all events up to the current
        head sequence, with a Merkle root computed from event hashes.

        Per FR138: Checkpoint anchors at consistent intervals.

        Returns:
            The newly created Checkpoint.

        Raises:
            ValueError: If no events exist to checkpoint.
        """
        from src.domain.models.checkpoint import Checkpoint

        # Get current head sequence
        max_sequence = await self._event_store.get_max_sequence()
        if max_sequence == 0:
            raise ValueError("No events to checkpoint")

        # Get all events up to head
        events = await self._event_store.get_events_by_sequence_range(
            start=1,
            end=max_sequence,
        )

        if not events:
            raise ValueError("No events found in range")

        # Build Merkle tree
        leaves = [e.content_hash for e in events]
        merkle_root, _ = self._merkle_service.build_tree(leaves)

        # Create checkpoint
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=max_sequence,
            timestamp=datetime.now(timezone.utc),
            anchor_hash=merkle_root,
            anchor_type="periodic",
            creator_id="checkpoint_worker",
        )

        # Store checkpoint
        await self._checkpoint_repo.save_checkpoint(checkpoint)

        return checkpoint

    async def get_last_checkpoint(self) -> "Checkpoint | None":
        """Get the most recent checkpoint.

        Returns:
            The most recent Checkpoint, or None if no checkpoints exist.
        """
        checkpoints, _ = await self._checkpoint_repo.list_checkpoints(limit=1, offset=0)
        return checkpoints[0] if checkpoints else None

    async def should_generate_checkpoint(self) -> bool:
        """Check if a new checkpoint should be generated.

        Returns True if:
        - No checkpoints exist
        - Last checkpoint is older than checkpoint_interval_days

        Returns:
            True if checkpoint should be generated.
        """
        last = await self.get_last_checkpoint()
        if last is None:
            return True

        age = datetime.now(timezone.utc) - last.timestamp
        return age.days >= self._checkpoint_interval_days
