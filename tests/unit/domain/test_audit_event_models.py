"""Unit tests for audit event domain models (Story 9.5, FR108).

Tests for AuditEvent, AuditTrend, QuarterStats, and AuditEventType.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.domain.models.audit_event import (
    AUDIT_COMPLETED_EVENT_TYPE,
    AUDIT_EVENT_TYPE_PREFIX,
    AUDIT_STARTED_EVENT_TYPE,
    AUDIT_VIOLATION_FLAGGED_EVENT_TYPE,
    AuditEvent,
    AuditEventType,
    AuditTrend,
    QuarterStats,
)


class TestAuditEventType:
    """Test AuditEventType enum (3 tests)."""

    def test_started_value(self) -> None:
        """Test STARTED event type value."""
        assert AuditEventType.STARTED.value == "audit.started"

    def test_completed_value(self) -> None:
        """Test COMPLETED event type value."""
        assert AuditEventType.COMPLETED.value == "audit.completed"

    def test_violation_flagged_value(self) -> None:
        """Test VIOLATION_FLAGGED event type value."""
        assert AuditEventType.VIOLATION_FLAGGED.value == "audit.violation.flagged"


class TestAuditEventConstants:
    """Test module-level constants."""

    def test_audit_event_type_prefix(self) -> None:
        """Test event type prefix constant."""
        assert AUDIT_EVENT_TYPE_PREFIX == "audit."

    def test_audit_started_constant(self) -> None:
        """Test started event constant."""
        assert AUDIT_STARTED_EVENT_TYPE == "audit.started"

    def test_audit_completed_constant(self) -> None:
        """Test completed event constant."""
        assert AUDIT_COMPLETED_EVENT_TYPE == "audit.completed"

    def test_audit_violation_flagged_constant(self) -> None:
        """Test violation flagged event constant."""
        assert AUDIT_VIOLATION_FLAGGED_EVENT_TYPE == "audit.violation.flagged"


class TestAuditEvent:
    """Test AuditEvent dataclass (5 tests)."""

    def test_create_valid_audit_event(self) -> None:
        """Test creating a valid audit event."""
        event = AuditEvent(
            event_id="evt-123",
            event_type="audit.completed",
            audit_id="audit-456",
            quarter="2026-Q1",
            timestamp=datetime.now(),
            payload={"status": "clean", "materials_scanned": 10},
        )
        assert event.event_id == "evt-123"
        assert event.audit_id == "audit-456"
        assert event.quarter == "2026-Q1"

    def test_audit_event_is_started_property(self) -> None:
        """Test is_started property."""
        event = AuditEvent(
            event_id="evt-1",
            event_type=AuditEventType.STARTED.value,
            audit_id="audit-1",
            quarter="2026-Q1",
            timestamp=datetime.now(),
            payload={},
        )
        assert event.is_started is True
        assert event.is_completed is False
        assert event.is_violation_flagged is False

    def test_audit_event_is_completed_property(self) -> None:
        """Test is_completed property."""
        event = AuditEvent(
            event_id="evt-1",
            event_type=AuditEventType.COMPLETED.value,
            audit_id="audit-1",
            quarter="2026-Q1",
            timestamp=datetime.now(),
            payload={"status": "clean"},
        )
        assert event.is_completed is True
        assert event.is_started is False

    def test_audit_event_completion_status(self) -> None:
        """Test completion_status property."""
        event = AuditEvent(
            event_id="evt-1",
            event_type=AuditEventType.COMPLETED.value,
            audit_id="audit-1",
            quarter="2026-Q1",
            timestamp=datetime.now(),
            payload={"status": "violations_found", "violations_found": 3},
        )
        assert event.completion_status == "violations_found"
        assert event.violations_found == 3

    def test_audit_event_requires_event_id(self) -> None:
        """Test that event_id is required."""
        with pytest.raises(ValueError, match="FR108: event_id is required"):
            AuditEvent(
                event_id="",
                event_type="audit.completed",
                audit_id="audit-1",
                quarter="2026-Q1",
                timestamp=datetime.now(),
                payload={},
            )

    def test_audit_event_requires_audit_id(self) -> None:
        """Test that audit_id is required."""
        with pytest.raises(ValueError, match="FR108: audit_id is required"):
            AuditEvent(
                event_id="evt-1",
                event_type="audit.completed",
                audit_id="",
                quarter="2026-Q1",
                timestamp=datetime.now(),
                payload={},
            )

    def test_audit_event_violations_found_default(self) -> None:
        """Test violations_found returns 0 when not in payload."""
        event = AuditEvent(
            event_id="evt-1",
            event_type=AuditEventType.COMPLETED.value,
            audit_id="audit-1",
            quarter="2026-Q1",
            timestamp=datetime.now(),
            payload={"status": "clean"},
        )
        assert event.violations_found == 0

    def test_audit_event_materials_scanned(self) -> None:
        """Test materials_scanned property."""
        event = AuditEvent(
            event_id="evt-1",
            event_type=AuditEventType.COMPLETED.value,
            audit_id="audit-1",
            quarter="2026-Q1",
            timestamp=datetime.now(),
            payload={"materials_scanned": 25},
        )
        assert event.materials_scanned == 25


class TestQuarterStats:
    """Test QuarterStats dataclass (4 tests)."""

    def test_create_valid_quarter_stats(self) -> None:
        """Test creating valid quarter stats."""
        stats = QuarterStats(
            quarter="2026-Q1",
            audits=5,
            violations=3,
            status="violations_found",
        )
        assert stats.quarter == "2026-Q1"
        assert stats.audits == 5
        assert stats.violations == 3
        assert stats.status == "violations_found"

    def test_quarter_stats_requires_quarter(self) -> None:
        """Test that quarter is required."""
        with pytest.raises(ValueError, match="FR108: quarter is required"):
            QuarterStats(
                quarter="",
                audits=5,
                violations=0,
                status="clean",
            )

    def test_quarter_stats_audits_non_negative(self) -> None:
        """Test that audits cannot be negative."""
        with pytest.raises(ValueError, match="FR108: audits cannot be negative"):
            QuarterStats(
                quarter="2026-Q1",
                audits=-1,
                violations=0,
                status="clean",
            )

    def test_quarter_stats_violations_non_negative(self) -> None:
        """Test that violations cannot be negative."""
        with pytest.raises(ValueError, match="FR108: violations cannot be negative"):
            QuarterStats(
                quarter="2026-Q1",
                audits=5,
                violations=-1,
                status="clean",
            )


class TestAuditTrend:
    """Test AuditTrend dataclass (8 tests)."""

    def test_create_valid_audit_trend(self) -> None:
        """Test creating a valid audit trend."""
        trend = AuditTrend(
            quarters=("2026-Q1", "2026-Q2"),
            total_audits=10,
            total_violations=5,
            clean_audits=7,
            violation_audits=2,
            failed_audits=1,
            average_violations_per_audit=0.5,
            quarter_breakdown=(
                QuarterStats(
                    quarter="2026-Q1",
                    audits=5,
                    violations=2,
                    status="violations_found",
                ),
                QuarterStats(
                    quarter="2026-Q2",
                    audits=5,
                    violations=3,
                    status="violations_found",
                ),
            ),
        )
        assert trend.total_audits == 10
        assert trend.total_violations == 5
        assert trend.quarters_count == 2

    def test_audit_trend_has_violations_property(self) -> None:
        """Test has_violations property."""
        trend = AuditTrend(
            quarters=("2026-Q1",),
            total_audits=5,
            total_violations=3,
            clean_audits=2,
            violation_audits=3,
            failed_audits=0,
            average_violations_per_audit=0.6,
            quarter_breakdown=(),
        )
        assert trend.has_violations is True

    def test_audit_trend_no_violations(self) -> None:
        """Test has_violations when no violations."""
        trend = AuditTrend(
            quarters=("2026-Q1",),
            total_audits=5,
            total_violations=0,
            clean_audits=5,
            violation_audits=0,
            failed_audits=0,
            average_violations_per_audit=0.0,
            quarter_breakdown=(),
        )
        assert trend.has_violations is False

    def test_audit_trend_violation_rate(self) -> None:
        """Test violation_rate property."""
        trend = AuditTrend(
            quarters=("2026-Q1",),
            total_audits=10,
            total_violations=5,
            clean_audits=5,
            violation_audits=5,
            failed_audits=0,
            average_violations_per_audit=0.5,
            quarter_breakdown=(),
        )
        assert trend.violation_rate == 50.0

    def test_audit_trend_violation_rate_zero_audits(self) -> None:
        """Test violation_rate when no audits."""
        trend = AuditTrend.empty()
        assert trend.violation_rate == 0.0

    def test_audit_trend_empty_factory(self) -> None:
        """Test empty factory method."""
        trend = AuditTrend.empty()
        assert trend.total_audits == 0
        assert trend.total_violations == 0
        assert trend.quarters == ()
        assert trend.quarter_breakdown == ()

    def test_audit_trend_validates_consistency(self) -> None:
        """Test that audit counts must be consistent."""
        with pytest.raises(ValueError, match="FR108: audit counts inconsistent"):
            AuditTrend(
                quarters=("2026-Q1",),
                total_audits=10,
                total_violations=0,
                clean_audits=5,  # 5 + 2 + 1 = 8 != 10
                violation_audits=2,
                failed_audits=1,
                average_violations_per_audit=0.0,
                quarter_breakdown=(),
            )

    def test_audit_trend_non_negative_values(self) -> None:
        """Test that negative values are rejected."""
        with pytest.raises(ValueError, match="FR108: total_audits cannot be negative"):
            AuditTrend(
                quarters=(),
                total_audits=-1,
                total_violations=0,
                clean_audits=0,
                violation_audits=0,
                failed_audits=0,
                average_violations_per_audit=0.0,
                quarter_breakdown=(),
            )
