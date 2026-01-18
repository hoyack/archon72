"""Unit tests for AuditEventQueryService (Story 9.5, FR108).

Tests for querying and analyzing audit events from the constitutional record.
"""

from __future__ import annotations

import pytest

from src.application.services.audit_event_query_service import (
    AUDIT_EVENT_QUERY_SYSTEM_AGENT_ID,
    AuditEventQueryService,
)
from src.domain.errors.audit_event import InsufficientAuditDataError
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.audit_event import AuditEventType
from src.infrastructure.stubs.event_query_stub import EventQueryStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


class TestAuditEventQueryServiceConstants:
    """Test service constants."""

    def test_system_agent_id(self) -> None:
        """Test system agent ID constant."""
        assert AUDIT_EVENT_QUERY_SYSTEM_AGENT_ID == "system:audit_event_query"


class TestAuditEventQueryServiceHaltCheck:
    """Test HALT CHECK FIRST pattern (CT-11) - 4 tests."""

    @pytest.fixture
    def event_query_stub(self) -> EventQueryStub:
        """Create event query stub."""
        return EventQueryStub()

    @pytest.fixture
    def halted_checker(self) -> HaltCheckerStub:
        """Create halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(True)
        return checker

    @pytest.fixture
    def not_halted_checker(self) -> HaltCheckerStub:
        """Create not halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.mark.asyncio
    async def test_get_audit_events_halted(
        self, event_query_stub: EventQueryStub, halted_checker: HaltCheckerStub
    ) -> None:
        """Test get_audit_events raises SystemHaltedError when halted."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError, match="audit event query blocked"):
            await service.get_audit_events()

    @pytest.mark.asyncio
    async def test_get_audit_events_by_type_halted(
        self, event_query_stub: EventQueryStub, halted_checker: HaltCheckerStub
    ) -> None:
        """Test get_audit_events_by_type raises SystemHaltedError when halted."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_events_by_type("audit.completed")

    @pytest.mark.asyncio
    async def test_get_audit_events_by_quarter_halted(
        self, event_query_stub: EventQueryStub, halted_checker: HaltCheckerStub
    ) -> None:
        """Test get_audit_events_by_quarter raises SystemHaltedError when halted."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_events_by_quarter("2026-Q1")

    @pytest.mark.asyncio
    async def test_get_audit_trend_halted(
        self, event_query_stub: EventQueryStub, halted_checker: HaltCheckerStub
    ) -> None:
        """Test get_audit_trend raises SystemHaltedError when halted."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_audit_trend()


class TestGetAuditEvents:
    """Test get_audit_events method (5 tests)."""

    @pytest.fixture
    def event_query_stub(self) -> EventQueryStub:
        """Create event query stub."""
        return EventQueryStub()

    @pytest.fixture
    def not_halted_checker(self) -> HaltCheckerStub:
        """Create not halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_events(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test returns empty list when no audit events exist."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_audit_events(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test returns audit events from store."""
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "clean",
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events()
        assert len(result) == 1
        assert result[0].event_id == "evt-1"
        assert result[0].audit_id == "audit-1"

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test limit parameter restricts results."""
        for i in range(5):
            event_query_stub.add_event(
                {
                    "event_id": f"evt-{i}",
                    "event_type": "audit.completed",
                    "timestamp": f"2026-01-0{i + 1}T00:00:00Z",
                    "payload": {
                        "audit_id": f"audit-{i}",
                        "quarter": "2026-Q1",
                        "status": "clean",
                    },
                }
            )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events(limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_transforms_to_domain_model(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test events are transformed to AuditEvent domain models."""
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T10:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "violations_found",
                    "violations_found": 3,
                    "materials_scanned": 10,
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events()
        event = result[0]

        assert event.is_completed is True
        assert event.completion_status == "violations_found"
        assert event.violations_found == 3
        assert event.materials_scanned == 10

    @pytest.mark.asyncio
    async def test_orders_by_timestamp(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test events are ordered chronologically."""
        event_query_stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-01-02T00:00:00Z",
                "payload": {"audit_id": "audit-2", "quarter": "2026-Q1"},
            }
        )
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.started",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"audit_id": "audit-1", "quarter": "2026-Q1"},
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events()
        assert result[0].event_id == "evt-1"  # Earlier timestamp first
        assert result[1].event_id == "evt-2"


class TestGetAuditEventsByType:
    """Test get_audit_events_by_type method (4 tests)."""

    @pytest.fixture
    def event_query_stub(self) -> EventQueryStub:
        """Create event query stub with mixed events."""
        stub = EventQueryStub()
        stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.started",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"audit_id": "audit-1", "quarter": "2026-Q1"},
            }
        )
        stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T01:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "clean",
                },
            }
        )
        stub.add_event(
            {
                "event_id": "evt-3",
                "event_type": "audit.violation.flagged",
                "timestamp": "2026-01-02T00:00:00Z",
                "payload": {"audit_id": "audit-2", "quarter": "2026-Q1"},
            }
        )
        return stub

    @pytest.fixture
    def not_halted_checker(self) -> HaltCheckerStub:
        """Create not halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.mark.asyncio
    async def test_filters_by_started_type(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test filtering by started event type."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_type(AuditEventType.STARTED.value)
        assert len(result) == 1
        assert result[0].is_started is True

    @pytest.mark.asyncio
    async def test_filters_by_completed_type(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test filtering by completed event type."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_type(AuditEventType.COMPLETED.value)
        assert len(result) == 1
        assert result[0].is_completed is True

    @pytest.mark.asyncio
    async def test_filters_by_violation_flagged_type(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test filtering by violation flagged event type."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_type(
            AuditEventType.VIOLATION_FLAGGED.value
        )
        assert len(result) == 1
        assert result[0].is_violation_flagged is True

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_type(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test returns empty list for unknown event type."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_type("audit.unknown")
        assert result == []


class TestGetAuditEventsByQuarter:
    """Test get_audit_events_by_quarter method (4 tests)."""

    @pytest.fixture
    def event_query_stub(self) -> EventQueryStub:
        """Create event query stub with multiple quarters."""
        stub = EventQueryStub()
        stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "clean",
                },
            }
        )
        stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-04-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-2",
                    "quarter": "2026-Q2",
                    "status": "clean",
                },
            }
        )
        stub.add_event(
            {
                "event_id": "evt-3",
                "event_type": "audit.completed",
                "timestamp": "2026-02-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-3",
                    "quarter": "2026-Q1",
                    "status": "violations_found",
                    "violations_found": 2,
                },
            }
        )
        return stub

    @pytest.fixture
    def not_halted_checker(self) -> HaltCheckerStub:
        """Create not halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.mark.asyncio
    async def test_filters_by_quarter(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test filtering by quarter."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_quarter("2026-Q1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_single_quarter_audit(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test returns audit for specific quarter."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_quarter("2026-Q2")
        assert len(result) == 1
        assert result[0].quarter == "2026-Q2"

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_quarter(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test returns empty for quarter with no audits."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_quarter("2025-Q4")
        assert result == []

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(
        self, event_query_stub: EventQueryStub, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test limit parameter works with quarter filter."""
        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events_by_quarter("2026-Q1", limit=1)
        assert len(result) == 1


class TestGetAuditTrend:
    """Test get_audit_trend method (8 tests)."""

    @pytest.fixture
    def not_halted_checker(self) -> HaltCheckerStub:
        """Create not halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.mark.asyncio
    async def test_raises_error_when_no_data(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test raises InsufficientAuditDataError when no audit data."""
        event_query_stub = EventQueryStub()

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        with pytest.raises(InsufficientAuditDataError, match="No completed audit"):
            await service.get_audit_trend()

    @pytest.mark.asyncio
    async def test_calculates_trend_for_single_quarter(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test calculates trend for single quarter."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "clean",
                    "violations_found": 0,
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_trend(quarters=1)
        assert result.total_audits == 1
        assert result.clean_audits == 1
        assert result.total_violations == 0

    @pytest.mark.asyncio
    async def test_aggregates_multiple_quarters(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test aggregates data from multiple quarters."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "clean",
                    "violations_found": 0,
                },
            }
        )
        event_query_stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-04-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-2",
                    "quarter": "2026-Q2",
                    "status": "violations_found",
                    "violations_found": 3,
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_trend(quarters=4)
        assert result.total_audits == 2
        assert result.total_violations == 3
        assert result.clean_audits == 1
        assert result.violation_audits == 1

    @pytest.mark.asyncio
    async def test_calculates_average_violations(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test calculates average violations per audit."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "violations_found",
                    "violations_found": 4,
                },
            }
        )
        event_query_stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-04-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-2",
                    "quarter": "2026-Q2",
                    "status": "violations_found",
                    "violations_found": 6,
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_trend(quarters=4)
        assert result.average_violations_per_audit == 5.0  # (4+6)/2

    @pytest.mark.asyncio
    async def test_counts_failed_audits(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test counts failed audits correctly."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "failed",
                    "violations_found": 0,
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_trend(quarters=1)
        assert result.failed_audits == 1

    @pytest.mark.asyncio
    async def test_builds_quarter_breakdown(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test builds quarter breakdown."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "clean",
                    "violations_found": 0,
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_trend(quarters=1)
        assert len(result.quarter_breakdown) == 1
        assert result.quarter_breakdown[0].quarter == "2026-Q1"
        assert result.quarter_breakdown[0].status == "clean"

    @pytest.mark.asyncio
    async def test_sorts_quarters_chronologically(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test quarters are sorted chronologically."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-04-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-2",
                    "quarter": "2026-Q2",
                    "status": "clean",
                    "violations_found": 0,
                },
            }
        )
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {
                    "audit_id": "audit-1",
                    "quarter": "2026-Q1",
                    "status": "clean",
                    "violations_found": 0,
                },
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_trend(quarters=4)
        assert result.quarters == ("2026-Q1", "2026-Q2")

    @pytest.mark.asyncio
    async def test_limits_to_requested_quarters(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test limits results to requested number of quarters."""
        event_query_stub = EventQueryStub()
        for i, quarter in enumerate(["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"]):
            event_query_stub.add_event(
                {
                    "event_id": f"evt-{i}",
                    "event_type": "audit.completed",
                    "timestamp": f"2026-0{i + 1}-01T00:00:00Z",
                    "payload": {
                        "audit_id": f"audit-{i}",
                        "quarter": quarter,
                        "status": "clean",
                        "violations_found": 0,
                    },
                }
            )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_trend(quarters=2)
        # Should only include 2 most recent quarters
        assert len(result.quarters) == 2
        assert "2026-Q1" in result.quarters
        assert "2026-Q2" in result.quarters


class TestEdgeCases:
    """Test edge cases (5 tests)."""

    @pytest.fixture
    def not_halted_checker(self) -> HaltCheckerStub:
        """Create not halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.mark.asyncio
    async def test_handles_empty_payload(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test handles events with empty payload."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {},
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events()
        assert len(result) == 1
        # Falls back to event_id when audit_id missing from payload
        assert result[0].audit_id == "evt-1"

    @pytest.mark.asyncio
    async def test_handles_missing_timestamp(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test handles events with missing timestamp."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "payload": {"audit_id": "audit-1"},
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_events()
        assert len(result) == 1
        # Should use current time when timestamp missing

    @pytest.mark.asyncio
    async def test_get_available_quarters(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test get_available_quarters returns sorted quarters."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-04-01T00:00:00Z",
                "payload": {"audit_id": "audit-1", "quarter": "2026-Q2"},
            }
        )
        event_query_stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"audit_id": "audit-2", "quarter": "2026-Q1"},
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_available_quarters()
        assert result == ["2026-Q1", "2026-Q2"]

    @pytest.mark.asyncio
    async def test_get_audit_count(self, not_halted_checker: HaltCheckerStub) -> None:
        """Test get_audit_count returns correct count."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"audit_id": "audit-1", "quarter": "2026-Q1"},
            }
        )
        event_query_stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-04-01T00:00:00Z",
                "payload": {"audit_id": "audit-2", "quarter": "2026-Q2"},
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_audit_count()
        assert result == 2

    @pytest.mark.asyncio
    async def test_get_violation_events(
        self, not_halted_checker: HaltCheckerStub
    ) -> None:
        """Test get_violation_events returns violation events."""
        event_query_stub = EventQueryStub()
        event_query_stub.add_event(
            {
                "event_id": "evt-1",
                "event_type": "audit.violation.flagged",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"audit_id": "audit-1", "material_id": "mat-1"},
            }
        )
        event_query_stub.add_event(
            {
                "event_id": "evt-2",
                "event_type": "audit.completed",
                "timestamp": "2026-01-01T01:00:00Z",
                "payload": {"audit_id": "audit-1", "quarter": "2026-Q1"},
            }
        )

        service = AuditEventQueryService(
            event_query=event_query_stub,
            halt_checker=not_halted_checker,
        )

        result = await service.get_violation_events()
        assert len(result) == 1
        assert result[0].is_violation_flagged is True
