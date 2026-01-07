"""Unit tests for RecoveryWaitingPeriod domain model (Story 3.6, FR21).

Tests that the RecoveryWaitingPeriod value object:
- Enforces 48-hour waiting period (NFR41 constitutional floor)
- Correctly calculates elapsed/remaining time
- Is immutable (frozen dataclass)
- Has factory method for creating with proper timestamps
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.errors.recovery import RecoveryWaitingPeriodNotElapsedError
from src.domain.models.recovery_waiting_period import (
    WAITING_PERIOD_HOURS,
    RecoveryWaitingPeriod,
)


class TestWaitingPeriodConstant:
    """Tests for WAITING_PERIOD_HOURS constant."""

    def test_waiting_period_is_48_hours(self) -> None:
        """Constitutional floor is exactly 48 hours (NFR41)."""
        assert WAITING_PERIOD_HOURS == 48


class TestRecoveryWaitingPeriodStart:
    """Tests for RecoveryWaitingPeriod.start() factory method."""

    def test_start_creates_48_hour_window(self) -> None:
        """Factory creates 48-hour window from start time."""
        crisis_id = uuid4()
        keepers = ("keeper-001", "keeper-002")
        now = datetime.now(timezone.utc)

        period = RecoveryWaitingPeriod.start(
            crisis_event_id=crisis_id,
            initiated_by=keepers,
            started_at=now,
        )

        assert period.started_at == now
        assert period.ends_at == now + timedelta(hours=48)
        assert period.crisis_event_id == crisis_id
        assert period.initiated_by == keepers

    def test_start_with_default_time(self) -> None:
        """Factory uses current time if not provided."""
        crisis_id = uuid4()
        keepers = ("keeper-001",)
        before = datetime.now(timezone.utc)

        period = RecoveryWaitingPeriod.start(
            crisis_event_id=crisis_id,
            initiated_by=keepers,
        )

        after = datetime.now(timezone.utc)
        assert before <= period.started_at <= after
        expected_end = period.started_at + timedelta(hours=48)
        assert period.ends_at == expected_end

    def test_start_preserves_keeper_order(self) -> None:
        """Keeper IDs are preserved in order."""
        keepers = ("keeper-003", "keeper-001", "keeper-002")
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=keepers,
        )
        assert period.initiated_by == keepers


class TestRecoveryWaitingPeriodIsElapsed:
    """Tests for RecoveryWaitingPeriod.is_elapsed() method."""

    def test_not_elapsed_immediately_after_start(self) -> None:
        """Period is not elapsed immediately after creation."""
        now = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=now,
        )

        assert period.is_elapsed(current_time=now) is False

    def test_not_elapsed_at_47_hours(self) -> None:
        """Period is not elapsed at 47 hours (still 1 hour remaining)."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        at_47_hours = start + timedelta(hours=47)
        assert period.is_elapsed(current_time=at_47_hours) is False

    def test_elapsed_at_exactly_48_hours(self) -> None:
        """Period is elapsed at exactly 48 hours."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        at_48_hours = start + timedelta(hours=48)
        assert period.is_elapsed(current_time=at_48_hours) is True

    def test_elapsed_after_48_hours(self) -> None:
        """Period is elapsed after 48 hours."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        at_72_hours = start + timedelta(hours=72)
        assert period.is_elapsed(current_time=at_72_hours) is True


class TestRecoveryWaitingPeriodRemainingTime:
    """Tests for RecoveryWaitingPeriod.remaining_time() method."""

    def test_remaining_time_at_start(self) -> None:
        """Remaining time is 48 hours at start."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        remaining = period.remaining_time(current_time=start)
        assert remaining == timedelta(hours=48)

    def test_remaining_time_at_24_hours(self) -> None:
        """Remaining time is 24 hours at halfway point."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        at_24_hours = start + timedelta(hours=24)
        remaining = period.remaining_time(current_time=at_24_hours)
        assert remaining == timedelta(hours=24)

    def test_remaining_time_returns_zero_when_elapsed(self) -> None:
        """Remaining time is 0 when period has elapsed."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        at_72_hours = start + timedelta(hours=72)
        remaining = period.remaining_time(current_time=at_72_hours)
        assert remaining == timedelta(0)

    def test_remaining_time_never_negative(self) -> None:
        """Remaining time is never negative."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        far_future = start + timedelta(days=365)
        remaining = period.remaining_time(current_time=far_future)
        assert remaining >= timedelta(0)


class TestRecoveryWaitingPeriodCheckElapsed:
    """Tests for RecoveryWaitingPeriod.check_elapsed() method."""

    def test_check_elapsed_raises_when_not_elapsed(self) -> None:
        """check_elapsed raises error when period not elapsed."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        with pytest.raises(RecoveryWaitingPeriodNotElapsedError) as exc_info:
            period.check_elapsed(current_time=start)

        assert "FR21" in str(exc_info.value)
        assert "48" in str(exc_info.value) or "Remaining" in str(exc_info.value)

    def test_check_elapsed_returns_none_when_elapsed(self) -> None:
        """check_elapsed returns None when period has elapsed."""
        start = datetime.now(timezone.utc)
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
            started_at=start,
        )

        at_48_hours = start + timedelta(hours=48)
        result = period.check_elapsed(current_time=at_48_hours)
        assert result is None


class TestRecoveryWaitingPeriodImmutability:
    """Tests for RecoveryWaitingPeriod immutability."""

    def test_is_frozen_dataclass(self) -> None:
        """RecoveryWaitingPeriod is a frozen (immutable) dataclass."""
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001",),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            period.started_at = datetime.now(timezone.utc)  # type: ignore

    def test_initiated_by_is_tuple_not_list(self) -> None:
        """initiated_by is tuple for immutability."""
        period = RecoveryWaitingPeriod.start(
            crisis_event_id=uuid4(),
            initiated_by=("keeper-001", "keeper-002"),
        )
        assert isinstance(period.initiated_by, tuple)
