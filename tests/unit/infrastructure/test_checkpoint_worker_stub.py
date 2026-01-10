"""Tests for checkpoint worker stub (Story 4.6, Task 8).

Tests the stub implementation for periodic checkpoint generation.
Per FR138: Weekly checkpoint anchors SHALL be published at consistent intervals.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.infrastructure.stubs.checkpoint_worker_stub import CheckpointWorkerStub


class TestCheckpointWorkerStub:
    """Tests for CheckpointWorkerStub."""

    def _create_mock_event(
        self,
        sequence: int,
        content_hash: str | None = None,
    ):
        """Create a mock event."""
        from src.domain.events import Event

        return Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type="test.event",
            payload={"key": "value"},
            prev_hash="0" * 64 if sequence == 1 else "a" * 64,
            content_hash=content_hash or f"{sequence:064x}",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
            authority_timestamp=datetime.now(timezone.utc),
        )

    def _create_worker(
        self,
        max_sequence: int = 100,
        events: list | None = None,
        existing_checkpoint=None,
    ):
        """Create worker with mocked dependencies."""
        from src.application.services.merkle_tree_service import MerkleTreeService
        from src.domain.models.checkpoint import Checkpoint

        event_store = AsyncMock()
        event_store.get_max_sequence.return_value = max_sequence

        if events is None:
            events = [
                self._create_mock_event(i, content_hash=f"{i:064x}")
                for i in range(1, max_sequence + 1)
            ]
        event_store.get_events_by_sequence_range.return_value = events

        checkpoint_repo = AsyncMock()
        if existing_checkpoint:
            checkpoint_repo.list_checkpoints.return_value = ([existing_checkpoint], 1)
        else:
            checkpoint_repo.list_checkpoints.return_value = ([], 0)

        merkle_service = MerkleTreeService()

        return CheckpointWorkerStub(
            event_store=event_store,
            checkpoint_repo=checkpoint_repo,
            merkle_service=merkle_service,
        )

    @pytest.mark.asyncio
    async def test_generate_checkpoint_creates_checkpoint(self) -> None:
        """Test generate_checkpoint creates valid checkpoint."""
        worker = self._create_worker(max_sequence=100)

        checkpoint = await worker.generate_checkpoint()

        assert checkpoint is not None
        assert checkpoint.event_sequence == 100
        assert checkpoint.anchor_type == "periodic"
        assert len(checkpoint.anchor_hash) == 64  # Valid hex hash

    @pytest.mark.asyncio
    async def test_generate_checkpoint_stores_checkpoint(self) -> None:
        """Test generate_checkpoint stores in repository."""
        worker = self._create_worker(max_sequence=50)

        checkpoint = await worker.generate_checkpoint()

        worker._checkpoint_repo.save_checkpoint.assert_called_once_with(checkpoint)

    @pytest.mark.asyncio
    async def test_generate_checkpoint_empty_store_raises(self) -> None:
        """Test generate_checkpoint raises if no events."""
        worker = self._create_worker(max_sequence=0, events=[])

        with pytest.raises(ValueError, match="No events to checkpoint"):
            await worker.generate_checkpoint()

    @pytest.mark.asyncio
    async def test_generate_checkpoint_computes_merkle_root(self) -> None:
        """Test checkpoint anchor_hash is valid Merkle root."""
        events = [
            self._create_mock_event(i, content_hash=f"{i:064x}")
            for i in range(1, 11)
        ]
        worker = self._create_worker(max_sequence=10, events=events)

        checkpoint = await worker.generate_checkpoint()

        # Verify manually computing root matches
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()
        leaves = [e.content_hash for e in events]
        expected_root, _ = service.build_tree(leaves)

        assert checkpoint.anchor_hash == expected_root

    @pytest.mark.asyncio
    async def test_get_last_checkpoint_returns_latest(self) -> None:
        """Test get_last_checkpoint returns most recent."""
        from src.domain.models.checkpoint import Checkpoint

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="system",
        )
        worker = self._create_worker(existing_checkpoint=checkpoint)

        result = await worker.get_last_checkpoint()

        assert result == checkpoint

    @pytest.mark.asyncio
    async def test_get_last_checkpoint_returns_none_if_empty(self) -> None:
        """Test get_last_checkpoint returns None if no checkpoints."""
        worker = self._create_worker()

        result = await worker.get_last_checkpoint()

        assert result is None

    @pytest.mark.asyncio
    async def test_should_generate_checkpoint_true_if_none_exist(self) -> None:
        """Test should_generate_checkpoint returns True if no checkpoints."""
        worker = self._create_worker()

        result = await worker.should_generate_checkpoint()

        assert result is True

    @pytest.mark.asyncio
    async def test_should_generate_checkpoint_true_if_old(self) -> None:
        """Test should_generate_checkpoint returns True if last is old."""
        from src.domain.models.checkpoint import Checkpoint

        old_checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc) - timedelta(days=8),  # 8 days ago
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="system",
        )
        worker = self._create_worker(existing_checkpoint=old_checkpoint)

        result = await worker.should_generate_checkpoint()

        assert result is True

    @pytest.mark.asyncio
    async def test_should_generate_checkpoint_false_if_recent(self) -> None:
        """Test should_generate_checkpoint returns False if last is recent."""
        from src.domain.models.checkpoint import Checkpoint

        recent_checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc) - timedelta(days=3),  # 3 days ago
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="system",
        )
        worker = self._create_worker(existing_checkpoint=recent_checkpoint)

        result = await worker.should_generate_checkpoint()

        assert result is False

    @pytest.mark.asyncio
    async def test_checkpoint_interval_configurable(self) -> None:
        """Test checkpoint interval is configurable."""
        from src.domain.models.checkpoint import Checkpoint

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc) - timedelta(days=2),  # 2 days ago
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="system",
        )
        # Create worker with 1-day interval
        worker = self._create_worker(existing_checkpoint=checkpoint)
        worker._checkpoint_interval_days = 1

        result = await worker.should_generate_checkpoint()

        assert result is True  # 2 days > 1 day interval
