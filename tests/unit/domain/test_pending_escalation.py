"""Unit tests for PendingEscalation model (Story 6.2, FR31).

Tests:
- PendingEscalation dataclass creation
- Time remaining calculations
- Urgency level properties

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.breach import BreachType
from src.domain.models.pending_escalation import (
    ESCALATION_THRESHOLD_DAYS,
    PendingEscalation,
)


class TestEscalationThreshold:
    """Tests for escalation threshold constant."""

    def test_threshold_is_7_days(self) -> None:
        """Verify escalation threshold is 7 days per FR31."""
        assert ESCALATION_THRESHOLD_DAYS == 7


class TestPendingEscalation:
    """Tests for PendingEscalation dataclass."""

    @pytest.fixture
    def sample_pending(self) -> PendingEscalation:
        """Create a sample pending escalation for testing."""
        return PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5),
            days_remaining=2,
            hours_remaining=48,
        )

    def test_pending_escalation_creation(
        self, sample_pending: PendingEscalation
    ) -> None:
        """Test creating a pending escalation with all required fields."""
        assert sample_pending.breach_type == BreachType.THRESHOLD_VIOLATION
        assert sample_pending.days_remaining == 2
        assert sample_pending.hours_remaining == 48

    def test_pending_escalation_is_frozen(
        self, sample_pending: PendingEscalation
    ) -> None:
        """Test that pending escalation is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_pending.days_remaining = 1  # type: ignore[misc]


class TestPendingEscalationFromBreach:
    """Tests for PendingEscalation.from_breach() factory method."""

    def test_from_breach_recent(self) -> None:
        """Test creating pending escalation for a recent breach."""
        breach_id = uuid4()
        detection = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        current = datetime(2025, 1, 3, 12, 0, 0, tzinfo=timezone.utc)  # 2 days later

        pending = PendingEscalation.from_breach(
            breach_id=breach_id,
            breach_type=BreachType.SIGNATURE_INVALID,
            detection_timestamp=detection,
            current_time=current,
        )

        assert pending.breach_id == breach_id
        assert pending.breach_type == BreachType.SIGNATURE_INVALID
        assert pending.detection_timestamp == detection
        assert pending.days_remaining == 5  # 7 - 2 = 5
        assert pending.hours_remaining == 120  # 5 days * 24 = 120 hours

    def test_from_breach_at_threshold(self) -> None:
        """Test creating pending escalation at exactly 7 days."""
        breach_id = uuid4()
        detection = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        current = datetime(2025, 1, 8, 12, 0, 0, tzinfo=timezone.utc)  # 7 days later

        pending = PendingEscalation.from_breach(
            breach_id=breach_id,
            breach_type=BreachType.THRESHOLD_VIOLATION,
            detection_timestamp=detection,
            current_time=current,
        )

        assert pending.days_remaining == 0
        assert pending.hours_remaining == 0

    def test_from_breach_overdue(self) -> None:
        """Test creating pending escalation for overdue breach."""
        breach_id = uuid4()
        detection = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        current = datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc)  # 9 days later

        pending = PendingEscalation.from_breach(
            breach_id=breach_id,
            breach_type=BreachType.WITNESS_COLLUSION,
            detection_timestamp=detection,
            current_time=current,
        )

        assert pending.days_remaining < 0
        assert pending.hours_remaining < 0
        assert pending.is_overdue

    def test_from_breach_within_24_hours(self) -> None:
        """Test creating pending escalation within 24 hours of threshold."""
        breach_id = uuid4()
        detection = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        current = datetime(
            2025, 1, 7, 20, 0, 0, tzinfo=timezone.utc
        )  # 6 days 8 hours = 152 hours

        pending = PendingEscalation.from_breach(
            breach_id=breach_id,
            breach_type=BreachType.HASH_MISMATCH,
            detection_timestamp=detection,
            current_time=current,
        )

        # 168 hours (7 days) - 152 hours = 16 hours remaining
        assert pending.hours_remaining == 16
        assert pending.is_urgent

    def test_from_breach_uses_utc_now_by_default(self) -> None:
        """Test that from_breach uses UTC now when no current_time provided."""
        breach_id = uuid4()
        detection = datetime.now(timezone.utc) - timedelta(days=3)

        pending = PendingEscalation.from_breach(
            breach_id=breach_id,
            breach_type=BreachType.TIMING_VIOLATION,
            detection_timestamp=detection,
        )

        # Should be approximately 4 days remaining (7 - 3)
        assert 3 <= pending.days_remaining <= 4

    def test_from_breach_handles_naive_timestamps(self) -> None:
        """Test that from_breach handles naive timestamps by assuming UTC."""
        breach_id = uuid4()
        # Naive timestamp (no tzinfo)
        detection = datetime(2025, 1, 1, 12, 0, 0)
        current = datetime(2025, 1, 3, 12, 0, 0)  # 2 days later

        pending = PendingEscalation.from_breach(
            breach_id=breach_id,
            breach_type=BreachType.QUORUM_VIOLATION,
            detection_timestamp=detection,
            current_time=current,
        )

        # Should handle correctly
        assert pending.days_remaining == 5


class TestPendingEscalationProperties:
    """Tests for PendingEscalation computed properties."""

    def test_is_overdue_when_negative(self) -> None:
        """Test is_overdue returns True for negative hours."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.OVERRIDE_ABUSE,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=10),
            days_remaining=-3,
            hours_remaining=-72,
        )

        assert pending.is_overdue is True

    def test_is_overdue_when_positive(self) -> None:
        """Test is_overdue returns False for positive hours."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=3),
            days_remaining=4,
            hours_remaining=96,
        )

        assert pending.is_overdue is False

    def test_is_urgent_within_24_hours(self) -> None:
        """Test is_urgent returns True for < 24 hours remaining."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            detection_timestamp=datetime.now(timezone.utc)
            - timedelta(days=6, hours=10),
            days_remaining=0,
            hours_remaining=14,
        )

        assert pending.is_urgent is True

    def test_is_urgent_false_beyond_24_hours(self) -> None:
        """Test is_urgent returns False for >= 24 hours remaining."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.WITNESS_COLLUSION,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5),
            days_remaining=2,
            hours_remaining=48,
        )

        assert pending.is_urgent is False

    def test_is_urgent_false_when_overdue(self) -> None:
        """Test is_urgent returns False when overdue (negative hours)."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=10),
            days_remaining=-3,
            hours_remaining=-72,
        )

        assert pending.is_urgent is False


class TestUrgencyLevel:
    """Tests for urgency_level property."""

    def test_urgency_level_overdue(self) -> None:
        """Test urgency level for overdue breach."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.OVERRIDE_ABUSE,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=10),
            days_remaining=-3,
            hours_remaining=-72,
        )

        assert pending.urgency_level == "OVERDUE"

    def test_urgency_level_urgent(self) -> None:
        """Test urgency level for < 24 hours."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            detection_timestamp=datetime.now(timezone.utc)
            - timedelta(days=6, hours=12),
            days_remaining=0,
            hours_remaining=12,
        )

        assert pending.urgency_level == "URGENT"

    def test_urgency_level_warning(self) -> None:
        """Test urgency level for < 72 hours (but > 24)."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=5),
            days_remaining=2,
            hours_remaining=48,
        )

        assert pending.urgency_level == "WARNING"

    def test_urgency_level_pending(self) -> None:
        """Test urgency level for >= 72 hours."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=2),
            days_remaining=5,
            hours_remaining=120,
        )

        assert pending.urgency_level == "PENDING"

    def test_urgency_level_at_boundary_24(self) -> None:
        """Test urgency level at exactly 24 hours."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.TIMING_VIOLATION,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=6),
            days_remaining=1,
            hours_remaining=24,
        )

        # 24 hours is >= 24, so should be WARNING not URGENT
        assert pending.urgency_level == "WARNING"

    def test_urgency_level_at_boundary_72(self) -> None:
        """Test urgency level at exactly 72 hours."""
        pending = PendingEscalation(
            breach_id=uuid4(),
            breach_type=BreachType.QUORUM_VIOLATION,
            detection_timestamp=datetime.now(timezone.utc) - timedelta(days=4),
            days_remaining=3,
            hours_remaining=72,
        )

        # 72 hours is >= 72, so should be PENDING not WARNING
        assert pending.urgency_level == "PENDING"
