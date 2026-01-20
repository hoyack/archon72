"""Unit tests for ArchonDeliberationMetrics domain model (Story 3.6, FR-3.6)."""

from uuid import uuid4

import pytest

from src.domain.models.archon_metrics import ArchonDeliberationMetrics


class TestArchonDeliberationMetrics:
    """Tests for ArchonDeliberationMetrics dataclass."""

    def test_create_empty_metrics(self) -> None:
        """Test creating metrics with default zero values."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        assert metrics.archon_id == archon_id
        assert metrics.total_participations == 0
        assert metrics.acknowledge_votes == 0
        assert metrics.refer_votes == 0
        assert metrics.escalate_votes == 0

    def test_create_with_values(self) -> None:
        """Test creating metrics with explicit values."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics(
            archon_id=archon_id,
            total_participations=10,
            acknowledge_votes=5,
            refer_votes=3,
            escalate_votes=2,
        )

        assert metrics.total_participations == 10
        assert metrics.acknowledge_votes == 5
        assert metrics.refer_votes == 3
        assert metrics.escalate_votes == 2

    def test_total_votes_property(self) -> None:
        """Test total_votes sums all vote types."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics(
            archon_id=archon_id,
            total_participations=10,
            acknowledge_votes=5,
            refer_votes=3,
            escalate_votes=2,
        )

        assert metrics.total_votes == 10

    def test_acknowledgment_rate_with_participations(self) -> None:
        """Test acknowledgment rate calculation (FR-3.6)."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics(
            archon_id=archon_id,
            total_participations=10,
            acknowledge_votes=7,
            refer_votes=2,
            escalate_votes=1,
        )

        assert metrics.acknowledgment_rate == 0.7

    def test_acknowledgment_rate_zero_participations(self) -> None:
        """Test acknowledgment rate returns 0.0 with no participations."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        assert metrics.acknowledgment_rate == 0.0

    def test_refer_rate_property(self) -> None:
        """Test refer rate calculation."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics(
            archon_id=archon_id,
            total_participations=10,
            acknowledge_votes=5,
            refer_votes=3,
            escalate_votes=2,
        )

        assert metrics.refer_rate == 0.3

    def test_escalate_rate_property(self) -> None:
        """Test escalate rate calculation."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics(
            archon_id=archon_id,
            total_participations=10,
            acknowledge_votes=5,
            refer_votes=3,
            escalate_votes=2,
        )

        assert metrics.escalate_rate == 0.2

    def test_with_participation_increments(self) -> None:
        """Test with_participation creates new metrics with incremented count."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        updated = metrics.with_participation()

        assert updated.total_participations == 1
        assert metrics.total_participations == 0  # Original unchanged

    def test_with_vote_acknowledge(self) -> None:
        """Test with_vote increments acknowledge votes."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        # Must have participation before voting
        updated = metrics.with_participation().with_vote("ACKNOWLEDGE")

        assert updated.acknowledge_votes == 1
        assert updated.refer_votes == 0
        assert updated.escalate_votes == 0

    def test_with_vote_refer(self) -> None:
        """Test with_vote increments refer votes."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        # Must have participation before voting
        updated = metrics.with_participation().with_vote("REFER")

        assert updated.acknowledge_votes == 0
        assert updated.refer_votes == 1
        assert updated.escalate_votes == 0

    def test_with_vote_escalate(self) -> None:
        """Test with_vote increments escalate votes."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        # Must have participation before voting
        updated = metrics.with_participation().with_vote("ESCALATE")

        assert updated.acknowledge_votes == 0
        assert updated.refer_votes == 0
        assert updated.escalate_votes == 1

    def test_with_vote_invalid_outcome_raises(self) -> None:
        """Test with_vote raises ValueError for invalid outcome."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        with pytest.raises(ValueError, match="Invalid outcome"):
            metrics.with_vote("INVALID")

    def test_negative_participations_raises(self) -> None:
        """Test negative participations raises ValueError."""
        with pytest.raises(
            ValueError, match="total_participations must be non-negative"
        ):
            ArchonDeliberationMetrics(
                archon_id=uuid4(),
                total_participations=-1,
            )

    def test_negative_acknowledge_votes_raises(self) -> None:
        """Test negative acknowledge votes raises ValueError."""
        with pytest.raises(ValueError, match="acknowledge_votes must be non-negative"):
            ArchonDeliberationMetrics(
                archon_id=uuid4(),
                acknowledge_votes=-1,
            )

    def test_negative_refer_votes_raises(self) -> None:
        """Test negative refer votes raises ValueError."""
        with pytest.raises(ValueError, match="refer_votes must be non-negative"):
            ArchonDeliberationMetrics(
                archon_id=uuid4(),
                refer_votes=-1,
            )

    def test_negative_escalate_votes_raises(self) -> None:
        """Test negative escalate votes raises ValueError."""
        with pytest.raises(ValueError, match="escalate_votes must be non-negative"):
            ArchonDeliberationMetrics(
                archon_id=uuid4(),
                escalate_votes=-1,
            )

    def test_votes_exceed_participations_raises(self) -> None:
        """Test total votes exceeding participations raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed participations"):
            ArchonDeliberationMetrics(
                archon_id=uuid4(),
                total_participations=5,
                acknowledge_votes=3,
                refer_votes=2,
                escalate_votes=1,  # Total = 6 > 5
            )

    def test_frozen_dataclass_immutable(self) -> None:
        """Test metrics dataclass is immutable."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        with pytest.raises(AttributeError):
            metrics.total_participations = 10  # type: ignore

    def test_chained_updates(self) -> None:
        """Test chaining participation and vote updates."""
        archon_id = uuid4()
        metrics = ArchonDeliberationMetrics.create(archon_id)

        # Chain multiple updates
        updated = (
            metrics.with_participation()
            .with_vote("ACKNOWLEDGE")
            .with_participation()
            .with_vote("REFER")
            .with_participation()
            .with_vote("ACKNOWLEDGE")
        )

        assert updated.total_participations == 3
        assert updated.acknowledge_votes == 2
        assert updated.refer_votes == 1
        assert updated.escalate_votes == 0
        assert updated.acknowledgment_rate == pytest.approx(2 / 3)
