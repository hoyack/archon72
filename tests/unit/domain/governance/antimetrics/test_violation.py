"""Tests for anti-metrics violation models.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

These tests verify that:
1. Violation records are immutable
2. Violation error contains correct information
3. Violation string representation is useful
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.antimetrics import (
    AntiMetricsViolation,
    AntiMetricsViolationError,
    ProhibitedPattern,
)


class TestAntiMetricsViolation:
    """Tests for AntiMetricsViolation dataclass."""

    def test_create_violation(self) -> None:
        """Can create a violation record."""
        violation_id = uuid4()
        now = datetime.now(timezone.utc)

        violation = AntiMetricsViolation(
            violation_id=violation_id,
            attempted_at=now,
            pattern=ProhibitedPattern.PARTICIPANT_PERFORMANCE,
            attempted_by="migration",
            description="Attempted to create metric table: cluster_metrics",
        )

        assert violation.violation_id == violation_id
        assert violation.attempted_at == now
        assert violation.pattern == ProhibitedPattern.PARTICIPANT_PERFORMANCE
        assert violation.attempted_by == "migration"
        assert "cluster_metrics" in violation.description

    def test_violation_is_immutable(self) -> None:
        """Violation record is immutable (frozen dataclass)."""
        violation = AntiMetricsViolation(
            violation_id=uuid4(),
            attempted_at=datetime.now(timezone.utc),
            pattern=ProhibitedPattern.ENGAGEMENT_TRACKING,
            attempted_by="migration",
            description="Test violation",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            violation.pattern = ProhibitedPattern.COMPLETION_RATE  # type: ignore

    def test_violation_str_representation(self) -> None:
        """Violation has useful string representation."""
        violation = AntiMetricsViolation(
            violation_id=uuid4(),
            attempted_at=datetime.now(timezone.utc),
            pattern=ProhibitedPattern.SESSION_TRACKING,
            attempted_by="schema",
            description="Session tracking table exists",
        )

        str_rep = str(violation)
        assert "AntiMetricsViolation" in str_rep
        assert "session_tracking" in str_rep
        assert "Session tracking table exists" in str_rep
        assert "schema" in str_rep

    def test_violation_equality(self) -> None:
        """Two violations with same fields are equal."""
        violation_id = uuid4()
        now = datetime.now(timezone.utc)

        violation1 = AntiMetricsViolation(
            violation_id=violation_id,
            attempted_at=now,
            pattern=ProhibitedPattern.COMPLETION_RATE,
            attempted_by="test",
            description="Test",
        )

        violation2 = AntiMetricsViolation(
            violation_id=violation_id,
            attempted_at=now,
            pattern=ProhibitedPattern.COMPLETION_RATE,
            attempted_by="test",
            description="Test",
        )

        assert violation1 == violation2

    def test_violation_hash(self) -> None:
        """Violation can be used in sets and as dict keys."""
        violation = AntiMetricsViolation(
            violation_id=uuid4(),
            attempted_at=datetime.now(timezone.utc),
            pattern=ProhibitedPattern.RETENTION_METRICS,
            attempted_by="test",
            description="Test",
        )

        violations_set = {violation}
        assert violation in violations_set

        violations_dict = {violation: "blocked"}
        assert violations_dict[violation] == "blocked"


class TestAntiMetricsViolationError:
    """Tests for AntiMetricsViolationError exception."""

    def test_error_with_message_only(self) -> None:
        """Can create error with just a message."""
        error = AntiMetricsViolationError("Cannot create metric table: cluster_metrics")

        assert "cluster_metrics" in str(error)
        assert error.violation is None

    def test_error_with_violation(self) -> None:
        """Can create error with violation record."""
        violation = AntiMetricsViolation(
            violation_id=uuid4(),
            attempted_at=datetime.now(timezone.utc),
            pattern=ProhibitedPattern.ENGAGEMENT_TRACKING,
            attempted_by="migration",
            description="Attempted engagement table",
        )

        error = AntiMetricsViolationError(
            "Cannot create metric table",
            violation=violation,
        )

        assert error.violation == violation
        assert "engagement_tracking" in str(error)

    def test_error_is_value_error(self) -> None:
        """Error is a ValueError subclass."""
        error = AntiMetricsViolationError("Test error")

        assert isinstance(error, ValueError)
        assert isinstance(error, AntiMetricsViolationError)

    def test_error_can_be_raised_and_caught(self) -> None:
        """Error can be raised and caught properly."""
        with pytest.raises(AntiMetricsViolationError) as exc_info:
            raise AntiMetricsViolationError("Cannot add metric column")

        assert "metric column" in str(exc_info.value)

    def test_error_str_with_violation(self) -> None:
        """Error string includes pattern when violation is present."""
        violation = AntiMetricsViolation(
            violation_id=uuid4(),
            attempted_at=datetime.now(timezone.utc),
            pattern=ProhibitedPattern.COMPLETION_RATE,
            attempted_by="test",
            description="Test",
        )

        error = AntiMetricsViolationError(
            "Cannot add completion_rate column",
            violation=violation,
        )

        error_str = str(error)
        assert "completion_rate" in error_str
