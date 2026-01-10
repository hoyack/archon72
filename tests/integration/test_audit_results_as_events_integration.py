"""Integration tests for audit results as events (Story 9.5, FR108).

Tests end-to-end audit event query workflow with real stubs.

Constitutional Constraints:
- FR108: Audit results logged as events, audit history queryable
- CT-11: HALT CHECK FIRST on all operations (Golden Rule #1)
- CT-12: Read operations respect witnessed event structure
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from src.application.services.audit_event_query_service import (
    AUDIT_EVENT_QUERY_SYSTEM_AGENT_ID,
    AuditEventQueryService,
)
from src.domain.errors.audit_event import (
    InsufficientAuditDataError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.audit_event import (
    AUDIT_EVENT_TYPE_PREFIX,
    AuditCompletionStatus,
    AuditEventType,
)
from src.infrastructure.stubs import (
    EventQueryStub,
    HaltCheckerStub,
)


@pytest.fixture
def event_query_stub() -> EventQueryStub:
    """Create event query stub for testing."""
    return EventQueryStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def service(
    event_query_stub: EventQueryStub,
    halt_checker: HaltCheckerStub,
) -> AuditEventQueryService:
    """Create service with real stubs."""
    return AuditEventQueryService(
        event_query=event_query_stub,
        halt_checker=halt_checker,
    )


class TestEndToEndAuditEventQueryWorkflow:
    """Tests for end-to-end audit event query workflow."""

    @pytest.mark.asyncio
    async def test_query_audit_events_complete_workflow(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test complete audit event query workflow (FR108)."""
        # Setup: Configure audit events for multiple quarters
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            status="clean",
            violations_found=0,
            materials_scanned=50,
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q2",
            quarter="2026-Q2",
            status="violations_found",
            violations_found=3,
            materials_scanned=75,
        )

        # Query all audit events
        events = await service.get_audit_events()

        # Verify events returned
        assert len(events) == 4  # 2 started + 2 completed
        event_types = {e.event_type for e in events}
        assert "audit.started" in event_types
        assert "audit.completed" in event_types

    @pytest.mark.asyncio
    async def test_query_audit_events_by_quarter_workflow(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test querying audit events filtered by quarter (FR108)."""
        # Setup multiple quarters
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q2",
            quarter="2026-Q2",
            status="violations_found",
            violations_found=2,
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q3",
            quarter="2026-Q3",
            status="clean",
        )

        # Query specific quarter
        q2_events = await service.get_audit_events_by_quarter("2026-Q2")

        # Verify only Q2 events returned
        assert len(q2_events) == 1
        assert q2_events[0].quarter == "2026-Q2"
        assert q2_events[0].payload.get("violations_found") == 2

    @pytest.mark.asyncio
    async def test_audit_trend_analysis_workflow(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test audit trend analysis across quarters (FR108)."""
        # Setup: Create audit history over 4 quarters
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            status="clean",
            violations_found=0,
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q2",
            quarter="2026-Q2",
            status="violations_found",
            violations_found=2,
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q3",
            quarter="2026-Q3",
            status="violations_found",
            violations_found=1,
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q4",
            quarter="2026-Q4",
            status="clean",
            violations_found=0,
        )

        # Get trend analysis
        trend = await service.get_audit_trend(quarters=4)

        # Verify trend aggregation
        assert trend.total_audits == 4
        assert trend.total_violations == 3
        assert trend.clean_audits == 2
        assert trend.violation_audits == 2
        assert trend.quarters_count == 4
        assert trend.average_violations_per_audit == 0.75

        # Verify quarter breakdown
        assert len(trend.quarter_breakdown) == 4
        quarters = {q.quarter for q in trend.quarter_breakdown}
        assert "2026-Q1" in quarters
        assert "2026-Q2" in quarters
        assert "2026-Q3" in quarters
        assert "2026-Q4" in quarters

    @pytest.mark.asyncio
    async def test_get_available_quarters_workflow(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test listing available quarters with audit data (FR108)."""
        # Setup multiple quarters
        event_query_stub.configure_audit_events(
            audit_id="audit-2025-Q4",
            quarter="2025-Q4",
            status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q1",
            quarter="2026-Q1",
            status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2026-Q2",
            quarter="2026-Q2",
            status="violations_found",
            violations_found=1,
        )

        # Get available quarters
        quarters = await service.get_available_quarters()

        # Verify quarters sorted chronologically
        assert len(quarters) == 3
        assert quarters == ["2025-Q4", "2026-Q1", "2026-Q2"]

    @pytest.mark.asyncio
    async def test_get_audit_count_workflow(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test counting completed audits (FR108)."""
        # Setup audits
        event_query_stub.configure_audit_events(
            audit_id="audit-1",
            quarter="2026-Q1",
            status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2",
            quarter="2026-Q2",
            status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-3",
            quarter="2026-Q3",
            status="violations_found",
            violations_found=1,
        )

        # Count audits
        count = await service.get_audit_count()

        # Verify count matches completed events
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_violation_events_workflow(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test querying violation events (FR108)."""
        # Setup: Add violation flagged events manually
        now = datetime.now(timezone.utc).isoformat() + "Z"
        event_query_stub.add_event({
            "event_id": "viol-1",
            "event_type": "audit.violation.flagged",
            "timestamp": now,
            "payload": {
                "audit_id": "audit-2026-Q2",
                "material_id": "mat-001",
                "matched_terms": ["consciousness", "sentient"],
            },
        })
        event_query_stub.add_event({
            "event_id": "viol-2",
            "event_type": "audit.violation.flagged",
            "timestamp": now,
            "payload": {
                "audit_id": "audit-2026-Q2",
                "material_id": "mat-002",
                "matched_terms": ["genuine understanding"],
            },
        })

        # Query violation events
        violations = await service.get_violation_events()

        # Verify violations returned
        assert len(violations) == 2
        material_ids = {v.payload.get("material_id") for v in violations}
        assert "mat-001" in material_ids
        assert "mat-002" in material_ids

    @pytest.mark.asyncio
    async def test_get_violation_events_filtered_by_audit(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test filtering violation events by audit ID (FR108)."""
        now = datetime.now(timezone.utc).isoformat() + "Z"
        event_query_stub.add_event({
            "event_id": "viol-1",
            "event_type": "audit.violation.flagged",
            "timestamp": now,
            "payload": {
                "audit_id": "audit-Q2",
                "material_id": "mat-001",
            },
        })
        event_query_stub.add_event({
            "event_id": "viol-2",
            "event_type": "audit.violation.flagged",
            "timestamp": now,
            "payload": {
                "audit_id": "audit-Q3",
                "material_id": "mat-002",
            },
        })

        # Filter by specific audit
        q2_violations = await service.get_violation_events(audit_id="audit-Q2")

        # Verify only Q2 violations
        assert len(q2_violations) == 1
        assert q2_violations[0].payload.get("audit_id") == "audit-Q2"


class TestHaltCheckFirst:
    """Tests for CT-11: HALT CHECK FIRST compliance."""

    @pytest.mark.asyncio
    async def test_get_audit_events_blocked_when_halted(
        self,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test get_audit_events blocked when system is halted (CT-11)."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_events()

    @pytest.mark.asyncio
    async def test_get_audit_events_by_type_blocked_when_halted(
        self,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test get_audit_events_by_type blocked when system is halted (CT-11)."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_events_by_type("audit.completed")

    @pytest.mark.asyncio
    async def test_get_audit_events_by_quarter_blocked_when_halted(
        self,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test get_audit_events_by_quarter blocked when system is halted (CT-11)."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_events_by_quarter("2026-Q1")

    @pytest.mark.asyncio
    async def test_get_audit_trend_blocked_when_halted(
        self,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test get_audit_trend blocked when system is halted (CT-11)."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_trend()

    @pytest.mark.asyncio
    async def test_get_available_quarters_blocked_when_halted(
        self,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test get_available_quarters blocked when system is halted (CT-11)."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_available_quarters()

    @pytest.mark.asyncio
    async def test_get_audit_count_blocked_when_halted(
        self,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test get_audit_count blocked when system is halted (CT-11)."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_count()

    @pytest.mark.asyncio
    async def test_get_violation_events_blocked_when_halted(
        self,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test get_violation_events blocked when system is halted (CT-11)."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_violation_events()


class TestTrendAnalysisEdgeCases:
    """Tests for audit trend analysis edge cases."""

    @pytest.mark.asyncio
    async def test_trend_with_no_audit_data_raises_error(
        self,
        service: AuditEventQueryService,
    ) -> None:
        """Test trend analysis raises error when no data (FR108)."""
        with pytest.raises(InsufficientAuditDataError):
            await service.get_audit_trend()

    @pytest.mark.asyncio
    async def test_trend_limits_to_requested_quarters(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test trend analysis respects quarters parameter (FR108)."""
        # Setup 6 quarters of data
        for i in range(1, 7):
            quarter = f"2025-Q{i}" if i <= 4 else f"2026-Q{i-4}"
            event_query_stub.configure_audit_events(
                audit_id=f"audit-{quarter}",
                quarter=quarter,
                status="clean",
            )

        # Request only last 2 quarters
        trend = await service.get_audit_trend(quarters=2)

        # Verify only 2 quarters in breakdown
        assert trend.quarters_count == 2

    @pytest.mark.asyncio
    async def test_trend_with_failed_audits(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test trend analysis counts failed audits correctly (FR108)."""
        event_query_stub.configure_audit_events(
            audit_id="audit-1",
            quarter="2026-Q1",
            status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2",
            quarter="2026-Q2",
            status="failed",  # Scanner error
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-3",
            quarter="2026-Q3",
            status="violations_found",
            violations_found=2,
        )

        trend = await service.get_audit_trend()

        assert trend.total_audits == 3
        assert trend.clean_audits == 1
        assert trend.failed_audits == 1
        assert trend.violation_audits == 1

    @pytest.mark.asyncio
    async def test_trend_violation_rate_calculation(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test violation rate is calculated correctly (FR108)."""
        # 2 clean, 2 with violations
        event_query_stub.configure_audit_events(
            audit_id="audit-1", quarter="2026-Q1", status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-2", quarter="2026-Q2", status="violations_found", violations_found=1,
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-3", quarter="2026-Q3", status="clean",
        )
        event_query_stub.configure_audit_events(
            audit_id="audit-4", quarter="2026-Q4", status="violations_found", violations_found=1,
        )

        trend = await service.get_audit_trend()

        # 50% had violations (violation_rate returns percentage 0-100)
        assert trend.violation_rate == 50.0


class TestQueryByEventType:
    """Tests for querying by specific event types."""

    @pytest.mark.asyncio
    async def test_query_only_started_events(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test filtering to only audit.started events (FR108)."""
        event_query_stub.configure_audit_events(
            audit_id="audit-1",
            quarter="2026-Q1",
            status="clean",
        )

        events = await service.get_audit_events_by_type(AuditEventType.STARTED.value)

        assert len(events) == 1
        assert events[0].is_started

    @pytest.mark.asyncio
    async def test_query_only_completed_events(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test filtering to only audit.completed events (FR108)."""
        event_query_stub.configure_audit_events(
            audit_id="audit-1",
            quarter="2026-Q1",
            status="clean",
        )

        events = await service.get_audit_events_by_type(AuditEventType.COMPLETED.value)

        assert len(events) == 1
        assert events[0].is_completed

    @pytest.mark.asyncio
    async def test_query_only_violation_events(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test filtering to only audit.violation.flagged events (FR108)."""
        now = datetime.now(timezone.utc).isoformat() + "Z"
        event_query_stub.add_event({
            "event_id": "viol-1",
            "event_type": "audit.violation.flagged",
            "timestamp": now,
            "payload": {
                "audit_id": "audit-1",
                "material_id": "mat-001",
            },
        })

        events = await service.get_audit_events_by_type(
            AuditEventType.VIOLATION_FLAGGED.value
        )

        assert len(events) == 1
        assert events[0].is_violation_flagged


class TestSystemAgentIdentification:
    """Tests for system agent identification."""

    def test_system_agent_id_format(self) -> None:
        """Test system agent ID follows naming convention."""
        assert AUDIT_EVENT_QUERY_SYSTEM_AGENT_ID.startswith("system:")
        assert "audit_event_query" in AUDIT_EVENT_QUERY_SYSTEM_AGENT_ID


class TestEventPrefixFiltering:
    """Tests for event prefix filtering (all audit events)."""

    @pytest.mark.asyncio
    async def test_audit_prefix_captures_all_event_types(
        self,
        service: AuditEventQueryService,
        event_query_stub: EventQueryStub,
    ) -> None:
        """Test audit. prefix captures started, completed, and violation events (FR108)."""
        now = datetime.now(timezone.utc).isoformat() + "Z"

        # Add all event types
        event_query_stub.add_event({
            "event_id": "evt-1",
            "event_type": "audit.started",
            "timestamp": now,
            "payload": {"audit_id": "audit-1"},
        })
        event_query_stub.add_event({
            "event_id": "evt-2",
            "event_type": "audit.completed",
            "timestamp": now,
            "payload": {"audit_id": "audit-1", "status": "clean"},
        })
        event_query_stub.add_event({
            "event_id": "evt-3",
            "event_type": "audit.violation.flagged",
            "timestamp": now,
            "payload": {"audit_id": "audit-1"},
        })
        # Add non-audit event that should be excluded
        event_query_stub.add_event({
            "event_id": "evt-4",
            "event_type": "other.event",
            "timestamp": now,
            "payload": {},
        })

        events = await service.get_audit_events()

        # Should capture all 3 audit events but not the other event
        assert len(events) == 3
        types = {e.event_type for e in events}
        assert "audit.started" in types
        assert "audit.completed" in types
        assert "audit.violation.flagged" in types
        assert "other.event" not in types
