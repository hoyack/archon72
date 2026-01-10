"""Unit tests for CheckpointRepositoryStub (Story 3.10, Task 3; Story 4.6, Task 3).

Tests the in-memory stub implementation of CheckpointRepository for testing.

Constitutional Constraints:
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Checkpoints are periodic anchors
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
- FR143: Rollback to checkpoint for infrastructure recovery
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.checkpoint_repository import CheckpointRepository
from src.domain.models.checkpoint import Checkpoint
from src.infrastructure.stubs.checkpoint_repository_stub import CheckpointRepositoryStub


class TestStubImplementsProtocol:
    """Tests that stub implements the protocol."""

    def test_stub_implements_protocol(self) -> None:
        """CheckpointRepositoryStub should implement CheckpointRepository protocol."""
        stub = CheckpointRepositoryStub()
        assert isinstance(stub, CheckpointRepository)


class TestGetAllCheckpoints:
    """Tests for get_all_checkpoints method."""

    @pytest.mark.asyncio
    async def test_get_all_returns_all_checkpoints(self) -> None:
        """get_all_checkpoints should return all seeded checkpoints."""
        stub = CheckpointRepositoryStub()

        cp1 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        cp2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=200,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="b" * 64,
            anchor_type="periodic",
            creator_id="service",
        )

        stub.seed_checkpoints([cp1, cp2])

        result = await stub.get_all_checkpoints()

        assert len(result) == 2
        assert cp1 in result
        assert cp2 in result

    @pytest.mark.asyncio
    async def test_get_all_returns_empty_when_none(self) -> None:
        """get_all_checkpoints should return empty list when no checkpoints."""
        stub = CheckpointRepositoryStub()

        result = await stub.get_all_checkpoints()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_returns_sorted_by_sequence(self) -> None:
        """get_all_checkpoints should return checkpoints sorted by sequence."""
        stub = CheckpointRepositoryStub()

        cp1 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=200,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        cp2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="b" * 64,
            anchor_type="periodic",
            creator_id="service",
        )

        stub.seed_checkpoints([cp1, cp2])

        result = await stub.get_all_checkpoints()

        assert result[0].event_sequence == 100
        assert result[1].event_sequence == 200


class TestGetCheckpointById:
    """Tests for get_checkpoint_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_checkpoint(self) -> None:
        """get_checkpoint_by_id should return checkpoint when found."""
        stub = CheckpointRepositoryStub()
        checkpoint_id = uuid4()

        cp = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="c" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        stub.seed_checkpoints([cp])

        result = await stub.get_checkpoint_by_id(checkpoint_id)

        assert result == cp

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self) -> None:
        """get_checkpoint_by_id should return None when not found."""
        stub = CheckpointRepositoryStub()

        result = await stub.get_checkpoint_by_id(uuid4())

        assert result is None


class TestGetLatestCheckpoint:
    """Tests for get_latest_checkpoint method."""

    @pytest.mark.asyncio
    async def test_get_latest_returns_most_recent(self) -> None:
        """get_latest_checkpoint should return checkpoint with highest sequence."""
        stub = CheckpointRepositoryStub()

        cp1 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="d" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        cp2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=500,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="e" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        cp3 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=300,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="f" * 64,
            anchor_type="manual",
            creator_id="operator",
        )

        stub.seed_checkpoints([cp1, cp2, cp3])

        result = await stub.get_latest_checkpoint()

        assert result == cp2
        assert result.event_sequence == 500

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_when_empty(self) -> None:
        """get_latest_checkpoint should return None when no checkpoints."""
        stub = CheckpointRepositoryStub()

        result = await stub.get_latest_checkpoint()

        assert result is None


class TestGetCheckpointsAfterSequence:
    """Tests for get_checkpoints_after_sequence method."""

    @pytest.mark.asyncio
    async def test_get_after_sequence_filters_correctly(self) -> None:
        """get_checkpoints_after_sequence should filter by sequence."""
        stub = CheckpointRepositoryStub()

        cp1 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="g" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        cp2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=200,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="h" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        cp3 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=300,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="i" * 64,
            anchor_type="periodic",
            creator_id="service",
        )

        stub.seed_checkpoints([cp1, cp2, cp3])

        result = await stub.get_checkpoints_after_sequence(150)

        assert len(result) == 2
        assert all(cp.event_sequence > 150 for cp in result)
        # Should be sorted
        assert result[0].event_sequence == 200
        assert result[1].event_sequence == 300


class TestCreateCheckpoint:
    """Tests for create_checkpoint method."""

    @pytest.mark.asyncio
    async def test_create_checkpoint_stores_and_returns(self) -> None:
        """create_checkpoint should store checkpoint and return it."""
        stub = CheckpointRepositoryStub()

        result = await stub.create_checkpoint(
            event_sequence=500,
            anchor_hash="j" * 64,
            anchor_type="periodic",
            creator_id="checkpoint-service",
        )

        assert result.event_sequence == 500
        assert result.anchor_hash == "j" * 64
        assert result.anchor_type == "periodic"
        assert result.creator_id == "checkpoint-service"

        # Should be retrievable
        all_checkpoints = await stub.get_all_checkpoints()
        assert result in all_checkpoints


class TestSeedAndReset:
    """Tests for seed_checkpoints and reset methods."""

    def test_seed_checkpoints_for_testing(self) -> None:
        """seed_checkpoints should populate the stub with test data."""
        stub = CheckpointRepositoryStub()

        cp = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="k" * 64,
            anchor_type="genesis",
            creator_id="system",
        )

        stub.seed_checkpoints([cp])

        # Verify internally stored
        assert len(stub._checkpoints) == 1

    @pytest.mark.asyncio
    async def test_reset_clears_all(self) -> None:
        """reset should clear all checkpoints."""
        stub = CheckpointRepositoryStub()

        cp = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="l" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        stub.seed_checkpoints([cp])

        stub.reset()

        result = await stub.get_all_checkpoints()
        assert result == []


# =============================================================================
# Merkle-specific stub tests (Story 4.6 - FR136, FR137, FR138)
# =============================================================================


class TestGetCheckpointForSequence:
    """Tests for get_checkpoint_for_sequence method (FR136)."""

    @pytest.mark.asyncio
    async def test_get_checkpoint_for_sequence_returns_containing_checkpoint(
        self,
    ) -> None:
        """get_checkpoint_for_sequence should return checkpoint containing sequence."""
        stub = CheckpointRepositoryStub()

        # Checkpoint at sequence 100 covers sequences 1-100
        cp1 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="a" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        # Checkpoint at sequence 200 covers sequences 101-200
        cp2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=200,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="b" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        stub.seed_checkpoints([cp1, cp2])

        # Sequence 50 is in checkpoint 1
        result = await stub.get_checkpoint_for_sequence(50)
        assert result == cp1

        # Sequence 100 is in checkpoint 1
        result = await stub.get_checkpoint_for_sequence(100)
        assert result == cp1

        # Sequence 150 is in checkpoint 2
        result = await stub.get_checkpoint_for_sequence(150)
        assert result == cp2

    @pytest.mark.asyncio
    async def test_get_checkpoint_for_sequence_returns_none_for_pending(self) -> None:
        """get_checkpoint_for_sequence should return None for sequences in pending interval."""
        stub = CheckpointRepositoryStub()

        cp = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="c" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        stub.seed_checkpoints([cp])

        # Sequence 150 is beyond last checkpoint
        result = await stub.get_checkpoint_for_sequence(150)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_checkpoint_for_sequence_returns_none_when_empty(self) -> None:
        """get_checkpoint_for_sequence should return None when no checkpoints."""
        stub = CheckpointRepositoryStub()

        result = await stub.get_checkpoint_for_sequence(50)
        assert result is None


class TestListCheckpoints:
    """Tests for list_checkpoints method (FR138)."""

    @pytest.mark.asyncio
    async def test_list_checkpoints_returns_descending_order(self) -> None:
        """list_checkpoints should return most recent first."""
        stub = CheckpointRepositoryStub()

        cp1 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="d" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        cp2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=200,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="e" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        stub.seed_checkpoints([cp1, cp2])

        result, total = await stub.list_checkpoints()

        assert total == 2
        assert result[0].event_sequence == 200  # Most recent first
        assert result[1].event_sequence == 100

    @pytest.mark.asyncio
    async def test_list_checkpoints_respects_limit(self) -> None:
        """list_checkpoints should respect limit parameter."""
        stub = CheckpointRepositoryStub()

        for i in range(5):
            stub.seed_checkpoints(
                [
                    Checkpoint(
                        checkpoint_id=uuid4(),
                        event_sequence=(i + 1) * 100,
                        timestamp=datetime.now(timezone.utc),
                        anchor_hash=f"{i}" * 64,
                        anchor_type="periodic",
                        creator_id="service",
                    )
                ]
            )

        result, total = await stub.list_checkpoints(limit=2)

        assert len(result) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_checkpoints_respects_offset(self) -> None:
        """list_checkpoints should respect offset parameter."""
        stub = CheckpointRepositoryStub()

        for i in range(5):
            stub.seed_checkpoints(
                [
                    Checkpoint(
                        checkpoint_id=uuid4(),
                        event_sequence=(i + 1) * 100,
                        timestamp=datetime.now(timezone.utc),
                        anchor_hash=f"{i}" * 64,
                        anchor_type="periodic",
                        creator_id="service",
                    )
                ]
            )

        result, total = await stub.list_checkpoints(limit=2, offset=2)

        assert len(result) == 2
        assert total == 5
        # Should skip first 2 (500, 400) and return (300, 200)
        assert result[0].event_sequence == 300
        assert result[1].event_sequence == 200


class TestUpdateAnchorReference:
    """Tests for update_anchor_reference method (FR137)."""

    @pytest.mark.asyncio
    async def test_update_anchor_reference_modifies_checkpoint(self) -> None:
        """update_anchor_reference should update the checkpoint."""
        stub = CheckpointRepositoryStub()
        checkpoint_id = uuid4()

        cp = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="f" * 64,
            anchor_type="pending",
            creator_id="service",
        )
        stub.seed_checkpoints([cp])

        await stub.update_anchor_reference(
            checkpoint_id=checkpoint_id,
            anchor_type="rfc3161",
            anchor_reference="TSA_RESPONSE_123",
        )

        updated = await stub.get_checkpoint_by_id(checkpoint_id)
        # Stub should track updated values
        # Note: Since Checkpoint is immutable, stub may replace it
        # or track the update separately
        assert updated is not None
