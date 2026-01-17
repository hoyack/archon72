"""Unit tests for obligation release domain models.

Story: consent-gov-7.2: Obligation Release

Tests for:
- ReleaseType enum
- ObligationRelease frozen dataclass
- ReleaseResult frozen dataclass
- Structural absence of penalty fields (Golden Rule)

Constitutional Truths Tested:
- Golden Rule: No penalties exist
- FR44: All obligations released on exit
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.exit.release_type import ReleaseType
from src.domain.governance.exit.obligation_release import (
    ObligationRelease,
    ReleaseResult,
)
from src.domain.governance.task.task_state import TaskStatus


class TestReleaseType:
    """Unit tests for ReleaseType enum."""

    def test_has_nullified_on_exit_value(self) -> None:
        """NULLIFIED_ON_EXIT is for pre-consent tasks."""
        assert ReleaseType.NULLIFIED_ON_EXIT.value == "nullified_on_exit"

    def test_has_released_on_exit_value(self) -> None:
        """RELEASED_ON_EXIT is for post-consent tasks."""
        assert ReleaseType.RELEASED_ON_EXIT.value == "released_on_exit"

    def test_exactly_two_release_types(self) -> None:
        """Only two release types exist."""
        assert len(ReleaseType) == 2

    def test_is_string_enum(self) -> None:
        """ReleaseType is a string enum."""
        assert isinstance(ReleaseType.NULLIFIED_ON_EXIT, str)
        assert isinstance(ReleaseType.RELEASED_ON_EXIT, str)


class TestObligationRelease:
    """Unit tests for ObligationRelease domain model."""

    def test_creates_valid_nullified_release(self) -> None:
        """Can create valid nullified release."""
        now = datetime.now(timezone.utc)
        release = ObligationRelease(
            release_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            previous_state=TaskStatus.ROUTED,
            release_type=ReleaseType.NULLIFIED_ON_EXIT,
            released_at=now,
            work_preserved=False,
        )
        assert release.release_type == ReleaseType.NULLIFIED_ON_EXIT
        assert release.work_preserved is False

    def test_creates_valid_released_release(self) -> None:
        """Can create valid released release."""
        now = datetime.now(timezone.utc)
        release = ObligationRelease(
            release_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            previous_state=TaskStatus.IN_PROGRESS,
            release_type=ReleaseType.RELEASED_ON_EXIT,
            released_at=now,
            work_preserved=True,
        )
        assert release.release_type == ReleaseType.RELEASED_ON_EXIT
        assert release.work_preserved is True

    def test_is_frozen_dataclass(self) -> None:
        """ObligationRelease is immutable."""
        now = datetime.now(timezone.utc)
        release = ObligationRelease(
            release_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            previous_state=TaskStatus.ROUTED,
            release_type=ReleaseType.NULLIFIED_ON_EXIT,
            released_at=now,
            work_preserved=False,
        )
        with pytest.raises(AttributeError):
            release.work_preserved = True  # type: ignore

    def test_nullified_cannot_preserve_work(self) -> None:
        """Nullified releases cannot have work preserved."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="work_preserved must be False"):
            ObligationRelease(
                release_id=uuid4(),
                cluster_id=uuid4(),
                task_id=uuid4(),
                previous_state=TaskStatus.ROUTED,
                release_type=ReleaseType.NULLIFIED_ON_EXIT,
                released_at=now,
                work_preserved=True,  # Invalid for nullified
            )

    def test_released_can_preserve_work(self) -> None:
        """Released releases can have work preserved."""
        now = datetime.now(timezone.utc)
        release = ObligationRelease(
            release_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            previous_state=TaskStatus.IN_PROGRESS,
            release_type=ReleaseType.RELEASED_ON_EXIT,
            released_at=now,
            work_preserved=True,
        )
        assert release.work_preserved is True

    def test_released_can_also_not_preserve_work(self) -> None:
        """Released releases can optionally not preserve work."""
        now = datetime.now(timezone.utc)
        release = ObligationRelease(
            release_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            previous_state=TaskStatus.ACCEPTED,
            release_type=ReleaseType.RELEASED_ON_EXIT,
            released_at=now,
            work_preserved=False,  # Valid - no work done yet
        )
        assert release.work_preserved is False

    def test_captures_previous_state(self) -> None:
        """ObligationRelease captures previous state."""
        now = datetime.now(timezone.utc)
        release = ObligationRelease(
            release_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            previous_state=TaskStatus.ACTIVATED,
            release_type=ReleaseType.NULLIFIED_ON_EXIT,
            released_at=now,
            work_preserved=False,
        )
        assert release.previous_state == TaskStatus.ACTIVATED


class TestReleaseResult:
    """Unit tests for ReleaseResult domain model."""

    def test_creates_valid_result(self) -> None:
        """Can create valid release result."""
        now = datetime.now(timezone.utc)
        result = ReleaseResult(
            cluster_id=uuid4(),
            nullified_count=2,
            released_count=3,
            pending_cancelled=1,
            total_obligations=5,
            released_at=now,
        )
        assert result.nullified_count == 2
        assert result.released_count == 3
        assert result.pending_cancelled == 1
        assert result.total_obligations == 5

    def test_is_frozen_dataclass(self) -> None:
        """ReleaseResult is immutable."""
        now = datetime.now(timezone.utc)
        result = ReleaseResult(
            cluster_id=uuid4(),
            nullified_count=2,
            released_count=3,
            pending_cancelled=1,
            total_obligations=5,
            released_at=now,
        )
        with pytest.raises(AttributeError):
            result.nullified_count = 0  # type: ignore

    def test_validates_counts_are_non_negative(self) -> None:
        """Counts must be non-negative."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="nullified_count must be non-negative"):
            ReleaseResult(
                cluster_id=uuid4(),
                nullified_count=-1,
                released_count=3,
                pending_cancelled=1,
                total_obligations=2,
                released_at=now,
            )

        with pytest.raises(ValueError, match="released_count must be non-negative"):
            ReleaseResult(
                cluster_id=uuid4(),
                nullified_count=2,
                released_count=-1,
                pending_cancelled=1,
                total_obligations=1,
                released_at=now,
            )

        with pytest.raises(ValueError, match="pending_cancelled must be non-negative"):
            ReleaseResult(
                cluster_id=uuid4(),
                nullified_count=2,
                released_count=3,
                pending_cancelled=-1,
                total_obligations=5,
                released_at=now,
            )

    def test_validates_total_equals_sum(self) -> None:
        """Total must equal sum of nullified and released."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="total_obligations.*must equal"):
            ReleaseResult(
                cluster_id=uuid4(),
                nullified_count=2,
                released_count=3,
                pending_cancelled=1,
                total_obligations=10,  # Wrong total
                released_at=now,
            )

    def test_allows_zero_obligations(self) -> None:
        """Zero obligations is valid (nothing to release)."""
        now = datetime.now(timezone.utc)
        result = ReleaseResult(
            cluster_id=uuid4(),
            nullified_count=0,
            released_count=0,
            pending_cancelled=0,
            total_obligations=0,
            released_at=now,
        )
        assert result.total_obligations == 0


class TestNoPenaltyFields:
    """Tests ensuring no penalty-related fields exist.

    Per Golden Rule: Refusal is penalty-free.
    These tests ensure structural absence of penalty mechanisms.
    """

    def test_release_result_has_no_penalty_applied_field(self) -> None:
        """ReleaseResult has no penalty_applied field."""
        assert "penalty_applied" not in ReleaseResult.__dataclass_fields__

    def test_release_result_has_no_reputation_impact_field(self) -> None:
        """ReleaseResult has no reputation_impact field."""
        assert "reputation_impact" not in ReleaseResult.__dataclass_fields__

    def test_release_result_has_no_standing_reduction_field(self) -> None:
        """ReleaseResult has no standing_reduction field."""
        assert "standing_reduction" not in ReleaseResult.__dataclass_fields__

    def test_release_result_has_no_early_exit_mark_field(self) -> None:
        """ReleaseResult has no early_exit_mark field."""
        assert "early_exit_mark" not in ReleaseResult.__dataclass_fields__

    def test_obligation_release_has_no_penalty_field(self) -> None:
        """ObligationRelease has no penalty field."""
        assert "penalty" not in ObligationRelease.__dataclass_fields__
        assert "penalty_amount" not in ObligationRelease.__dataclass_fields__

    def test_obligation_release_has_no_reputation_field(self) -> None:
        """ObligationRelease has no reputation field."""
        assert "reputation" not in ObligationRelease.__dataclass_fields__
        assert "reputation_change" not in ObligationRelease.__dataclass_fields__

    def test_only_expected_fields_exist_on_release_result(self) -> None:
        """ReleaseResult has only expected fields (whitelist)."""
        expected_fields = {
            "cluster_id",
            "nullified_count",
            "released_count",
            "pending_cancelled",
            "total_obligations",
            "released_at",
        }
        actual_fields = set(ReleaseResult.__dataclass_fields__.keys())
        assert actual_fields == expected_fields

    def test_only_expected_fields_exist_on_obligation_release(self) -> None:
        """ObligationRelease has only expected fields (whitelist)."""
        expected_fields = {
            "release_id",
            "cluster_id",
            "task_id",
            "previous_state",
            "release_type",
            "released_at",
            "work_preserved",
        }
        actual_fields = set(ObligationRelease.__dataclass_fields__.keys())
        assert actual_fields == expected_fields
