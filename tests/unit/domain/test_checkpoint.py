"""Unit tests for Checkpoint domain model (Story 3.10, Task 1).

Tests the immutable Checkpoint domain model representing checkpoint anchors
for operational recovery (FR143).

Constitutional Constraints:
- FR137: Checkpoints are periodic anchors (minimum weekly)
- FR143: Rollback to checkpoint for infrastructure recovery
- PREVENT_DELETE: Events are never deleted, only marked orphaned
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.models.checkpoint import Checkpoint


class TestCheckpointCreation:
    """Tests for Checkpoint creation with required fields."""

    def test_checkpoint_creation_with_required_fields(self) -> None:
        """Checkpoint should be created with all required fields."""
        checkpoint_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=100,
            timestamp=timestamp,
            anchor_hash="abc123def456" * 5 + "abcd",  # 64 chars
            anchor_type="periodic",
            creator_id="checkpoint-service",
        )

        assert checkpoint.checkpoint_id == checkpoint_id
        assert checkpoint.event_sequence == 100
        assert checkpoint.timestamp == timestamp
        assert checkpoint.anchor_hash == "abc123def456" * 5 + "abcd"
        assert checkpoint.anchor_type == "periodic"
        assert checkpoint.creator_id == "checkpoint-service"

    def test_checkpoint_id_is_uuid(self) -> None:
        """checkpoint_id must be a UUID."""
        checkpoint_id = uuid4()
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=50,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="a" * 64,
            anchor_type="genesis",
            creator_id="system",
        )

        assert isinstance(checkpoint.checkpoint_id, UUID)

    def test_checkpoint_event_sequence_positive(self) -> None:
        """event_sequence must be a non-negative integer."""
        # Valid: sequence 0 (genesis)
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=0,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="b" * 64,
            anchor_type="genesis",
            creator_id="system",
        )
        assert checkpoint.event_sequence == 0

        # Valid: positive sequence
        checkpoint2 = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=1000,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="c" * 64,
            anchor_type="periodic",
            creator_id="service",
        )
        assert checkpoint2.event_sequence == 1000


class TestCheckpointImmutability:
    """Tests for Checkpoint immutability (frozen dataclass)."""

    def test_checkpoint_immutable(self) -> None:
        """Checkpoint should be immutable (frozen dataclass)."""
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="d" * 64,
            anchor_type="periodic",
            creator_id="service",
        )

        with pytest.raises(AttributeError):
            checkpoint.event_sequence = 200  # type: ignore[misc]

        with pytest.raises(AttributeError):
            checkpoint.anchor_hash = "e" * 64  # type: ignore[misc]


class TestCheckpointAnchorHash:
    """Tests for anchor_hash format validation."""

    def test_checkpoint_anchor_hash_format(self) -> None:
        """anchor_hash should be stored as provided (64-char hex for SHA-256)."""
        valid_hash = "abcdef0123456789" * 4  # 64 chars

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash=valid_hash,
            anchor_type="periodic",
            creator_id="service",
        )

        assert checkpoint.anchor_hash == valid_hash
        assert len(checkpoint.anchor_hash) == 64


class TestCheckpointEquality:
    """Tests for Checkpoint equality comparison."""

    def test_checkpoint_equality(self) -> None:
        """Checkpoints with same fields should be equal."""
        checkpoint_id = uuid4()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        anchor_hash = "f" * 64

        cp1 = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=100,
            timestamp=timestamp,
            anchor_hash=anchor_hash,
            anchor_type="periodic",
            creator_id="service",
        )

        cp2 = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=100,
            timestamp=timestamp,
            anchor_hash=anchor_hash,
            anchor_type="periodic",
            creator_id="service",
        )

        assert cp1 == cp2

    def test_checkpoint_inequality_different_sequence(self) -> None:
        """Checkpoints with different event_sequence should not be equal."""
        checkpoint_id = uuid4()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        cp1 = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=100,
            timestamp=timestamp,
            anchor_hash="g" * 64,
            anchor_type="periodic",
            creator_id="service",
        )

        cp2 = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=200,  # Different
            timestamp=timestamp,
            anchor_hash="g" * 64,
            anchor_type="periodic",
            creator_id="service",
        )

        assert cp1 != cp2


class TestCheckpointSignableContent:
    """Tests for signable_content method."""

    def test_checkpoint_signable_content(self) -> None:
        """signable_content should return canonical bytes for signing."""
        checkpoint_id = uuid4()
        timestamp = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=500,
            timestamp=timestamp,
            anchor_hash="h" * 64,
            anchor_type="manual",
            creator_id="operator-001",
        )

        content = checkpoint.signable_content()

        # Should be bytes
        assert isinstance(content, bytes)

        # Should contain key fields
        assert str(checkpoint_id).encode() in content
        assert b"500" in content
        assert b"h" * 64 in content
        assert b"manual" in content

    def test_checkpoint_signable_content_deterministic(self) -> None:
        """signable_content should return same bytes for same checkpoint."""
        checkpoint_id = uuid4()
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            event_sequence=100,
            timestamp=timestamp,
            anchor_hash="i" * 64,
            anchor_type="periodic",
            creator_id="service",
        )

        content1 = checkpoint.signable_content()
        content2 = checkpoint.signable_content()

        assert content1 == content2


class TestCheckpointAnchorTypes:
    """Tests for different anchor_type values."""

    @pytest.mark.parametrize(
        "anchor_type",
        ["genesis", "periodic", "manual"],
    )
    def test_valid_anchor_types(self, anchor_type: str) -> None:
        """Should accept valid anchor types."""
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash="j" * 64,
            anchor_type=anchor_type,
            creator_id="service",
        )

        assert checkpoint.anchor_type == anchor_type
