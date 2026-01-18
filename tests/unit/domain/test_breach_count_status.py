"""Unit tests for BreachCountStatus model (Story 6.3, FR32).

Tests cover:
- BreachCountStatus dataclass
- Threshold calculations (10 = trigger, 8 = warning)
- Trajectory calculation (INCREASING, STABLE, DECREASING)
- from_breaches() factory method
- is_above_threshold, is_at_warning, urgency_level properties
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.breach import BreachEventPayload, BreachSeverity, BreachType
from src.domain.models.breach_count_status import (
    CESSATION_THRESHOLD,
    CESSATION_WINDOW_DAYS,
    WARNING_THRESHOLD,
    BreachCountStatus,
    BreachTrajectory,
)


class TestBreachTrajectoryEnum:
    """Tests for BreachTrajectory enum."""

    def test_increasing_value(self) -> None:
        """Test INCREASING has correct string value."""
        assert BreachTrajectory.INCREASING.value == "increasing"

    def test_stable_value(self) -> None:
        """Test STABLE has correct string value."""
        assert BreachTrajectory.STABLE.value == "stable"

    def test_decreasing_value(self) -> None:
        """Test DECREASING has correct string value."""
        assert BreachTrajectory.DECREASING.value == "decreasing"

    def test_is_string_subclass(self) -> None:
        """Test enum values are string subclass."""
        assert isinstance(BreachTrajectory.INCREASING, str)


class TestThresholdConstants:
    """Tests for threshold constants."""

    def test_cessation_threshold(self) -> None:
        """Test cessation threshold is 10 (FR32: >10 triggers)."""
        assert CESSATION_THRESHOLD == 10

    def test_warning_threshold(self) -> None:
        """Test warning threshold is 8."""
        assert WARNING_THRESHOLD == 8

    def test_window_days(self) -> None:
        """Test window is 90 days (FR32)."""
        assert CESSATION_WINDOW_DAYS == 90


class TestBreachCountStatus:
    """Tests for BreachCountStatus dataclass."""

    @pytest.fixture
    def sample_status(self) -> BreachCountStatus:
        """Create a sample status for testing."""
        return BreachCountStatus(
            current_count=5,
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=(uuid4(), uuid4()),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )

    def test_creation(self, sample_status: BreachCountStatus) -> None:
        """Test BreachCountStatus can be created."""
        assert sample_status.current_count == 5
        assert sample_status.window_days == 90
        assert sample_status.threshold == 10
        assert sample_status.warning_threshold == 8
        assert sample_status.trajectory == BreachTrajectory.STABLE

    def test_is_above_threshold_false_at_5(
        self, sample_status: BreachCountStatus
    ) -> None:
        """Test is_above_threshold is False when count is 5."""
        assert sample_status.is_above_threshold is False

    def test_is_above_threshold_false_at_10(self) -> None:
        """Test is_above_threshold is False at exactly 10 (FR32: >10 triggers)."""
        status = BreachCountStatus(
            current_count=10,  # Exactly at threshold, not above
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(10)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        assert status.is_above_threshold is False

    def test_is_above_threshold_true_at_11(self) -> None:
        """Test is_above_threshold is True at 11 (FR32: >10 triggers)."""
        status = BreachCountStatus(
            current_count=11,  # Above threshold
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(11)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        assert status.is_above_threshold is True

    def test_is_at_warning_false_at_7(self) -> None:
        """Test is_at_warning is False at 7."""
        status = BreachCountStatus(
            current_count=7,
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(7)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        assert status.is_at_warning is False

    def test_is_at_warning_true_at_8(self) -> None:
        """Test is_at_warning is True at exactly 8."""
        status = BreachCountStatus(
            current_count=8,
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(8)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        assert status.is_at_warning is True

    def test_urgency_level_normal(self, sample_status: BreachCountStatus) -> None:
        """Test urgency_level is NORMAL below warning threshold."""
        assert sample_status.urgency_level == "NORMAL"

    def test_urgency_level_warning(self) -> None:
        """Test urgency_level is WARNING at/above 8 but <= 10."""
        status = BreachCountStatus(
            current_count=9,
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(9)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        assert status.urgency_level == "WARNING"

    def test_urgency_level_critical(self) -> None:
        """Test urgency_level is CRITICAL when above threshold."""
        status = BreachCountStatus(
            current_count=12,
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(12)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        assert status.urgency_level == "CRITICAL"

    def test_breaches_until_threshold_at_5(
        self, sample_status: BreachCountStatus
    ) -> None:
        """Test breaches_until_threshold when at 5."""
        # Need 6 more breaches to exceed 10 (i.e., reach 11)
        assert sample_status.breaches_until_threshold == 6

    def test_breaches_until_threshold_at_10(self) -> None:
        """Test breaches_until_threshold when at 10."""
        status = BreachCountStatus(
            current_count=10,
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(10)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        # Need 1 more breach to exceed 10
        assert status.breaches_until_threshold == 1

    def test_breaches_until_threshold_at_11(self) -> None:
        """Test breaches_until_threshold when already above threshold."""
        status = BreachCountStatus(
            current_count=11,
            window_days=90,
            threshold=10,
            warning_threshold=8,
            breach_ids=tuple(uuid4() for _ in range(11)),
            trajectory=BreachTrajectory.STABLE,
            calculated_at=datetime.now(timezone.utc),
        )
        assert status.breaches_until_threshold == 0


class TestBreachCountStatusFromBreaches:
    """Tests for from_breaches factory method."""

    def _create_breach(
        self,
        detection_time: datetime,
    ) -> BreachEventPayload:
        """Helper to create a breach payload."""
        from types import MappingProxyType

        return BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            violated_requirement="FR32",
            severity=BreachSeverity.MEDIUM,
            detection_timestamp=detection_time,
            details=MappingProxyType({"description": "Test breach"}),
        )

    def test_from_empty_breaches(self) -> None:
        """Test from_breaches with empty list."""
        status = BreachCountStatus.from_breaches([])
        assert status.current_count == 0
        assert status.trajectory == BreachTrajectory.STABLE
        assert status.is_above_threshold is False
        assert status.is_at_warning is False

    def test_from_breaches_count(self) -> None:
        """Test from_breaches counts correctly."""
        now = datetime.now(timezone.utc)
        breaches = [self._create_breach(now) for _ in range(5)]

        status = BreachCountStatus.from_breaches(breaches)
        assert status.current_count == 5
        assert len(status.breach_ids) == 5

    def test_trajectory_increasing(self) -> None:
        """Test trajectory is INCREASING when recent > older + 2."""
        now = datetime.now(timezone.utc)
        midpoint = now - timedelta(days=45)

        # 5 recent breaches (in last 45 days)
        recent = [self._create_breach(now - timedelta(days=i)) for i in range(5)]
        # 1 older breach (before midpoint)
        older = [self._create_breach(midpoint - timedelta(days=10))]

        breaches = recent + older
        status = BreachCountStatus.from_breaches(breaches, now=now)

        assert status.trajectory == BreachTrajectory.INCREASING

    def test_trajectory_decreasing(self) -> None:
        """Test trajectory is DECREASING when recent < older - 2."""
        now = datetime.now(timezone.utc)
        midpoint = now - timedelta(days=45)

        # 1 recent breach (in last 45 days)
        recent = [self._create_breach(now - timedelta(days=10))]
        # 5 older breaches (before midpoint)
        older = [self._create_breach(midpoint - timedelta(days=i)) for i in range(1, 6)]

        breaches = recent + older
        status = BreachCountStatus.from_breaches(breaches, now=now)

        assert status.trajectory == BreachTrajectory.DECREASING

    def test_trajectory_stable(self) -> None:
        """Test trajectory is STABLE when counts are similar."""
        now = datetime.now(timezone.utc)
        midpoint = now - timedelta(days=45)

        # 3 recent breaches (in last 45 days)
        recent = [self._create_breach(now - timedelta(days=i)) for i in range(3)]
        # 3 older breaches (before midpoint)
        older = [self._create_breach(midpoint - timedelta(days=i)) for i in range(1, 4)]

        breaches = recent + older
        status = BreachCountStatus.from_breaches(breaches, now=now)

        assert status.trajectory == BreachTrajectory.STABLE

    def test_uses_default_thresholds(self) -> None:
        """Test from_breaches uses correct default thresholds."""
        status = BreachCountStatus.from_breaches([])
        assert status.threshold == CESSATION_THRESHOLD
        assert status.warning_threshold == WARNING_THRESHOLD
        assert status.window_days == CESSATION_WINDOW_DAYS

    def test_custom_now_parameter(self) -> None:
        """Test from_breaches accepts custom now parameter."""
        custom_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        status = BreachCountStatus.from_breaches([], now=custom_now)
        assert status.calculated_at == custom_now
