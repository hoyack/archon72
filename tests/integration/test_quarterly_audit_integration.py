"""Integration tests for quarterly audit (Story 9.3, FR57).

Tests end-to-end quarterly audit workflow with real stubs.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations (Golden Rule #1)
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from src.application.ports.material_repository import Material
from src.application.services.quarterly_audit_service import QuarterlyAuditService
from src.domain.errors.audit import (
    AuditFailedError,
    AuditInProgressError,
    AuditNotDueError,
    AuditNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.audit import (
    AUDIT_COMPLETED_EVENT_TYPE,
    AUDIT_STARTED_EVENT_TYPE,
    AUDIT_SYSTEM_AGENT_ID,
    MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE,
)
from src.domain.models.material_audit import (
    REMEDIATION_DEADLINE_DAYS,
    AuditQuarter,
    AuditStatus,
    MaterialAudit,
    RemediationStatus,
)
from src.infrastructure.stubs import (
    AuditRepositoryStub,
    ConfigurableAuditRepositoryStub,
    ConfigurableMaterialRepositoryStub,
    ConfigurablePublicationScannerStub,
    HaltCheckerStub,
    MaterialRepositoryStub,
    ProhibitedLanguageScannerStub,
)


@pytest.fixture
def material_repository() -> MaterialRepositoryStub:
    """Create material repository stub."""
    return MaterialRepositoryStub()


@pytest.fixture
def audit_repository() -> AuditRepositoryStub:
    """Create audit repository stub."""
    return AuditRepositoryStub()


@pytest.fixture
def scanner() -> ProhibitedLanguageScannerStub:
    """Create prohibited language scanner stub."""
    return ProhibitedLanguageScannerStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def event_writer() -> AsyncMock:
    """Create mock event writer for integration tests."""
    mock = AsyncMock()
    mock.write_event = AsyncMock()
    return mock


@pytest.fixture
def service(
    material_repository: MaterialRepositoryStub,
    audit_repository: AuditRepositoryStub,
    scanner: ProhibitedLanguageScannerStub,
    event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> QuarterlyAuditService:
    """Create service with real stubs."""
    return QuarterlyAuditService(
        material_repository=material_repository,
        audit_repository=audit_repository,
        scanner=scanner,
        event_writer=event_writer,
        halt_checker=halt_checker,
    )


class TestEndToEndQuarterlyAuditWorkflow:
    """Tests for end-to-end quarterly audit workflow."""

    @pytest.mark.asyncio
    async def test_complete_clean_audit_workflow(
        self,
        service: QuarterlyAuditService,
        material_repository: MaterialRepositoryStub,
        audit_repository: AuditRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test complete audit workflow with no violations."""
        # Setup clean materials
        now = datetime.now(timezone.utc)
        material_repository.add_material(
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Clean Publication",
                content="This is a clean publication with no issues.",
                published_at=now,
            )
        )
        material_repository.add_material(
            Material(
                material_id="mat-002",
                material_type="document",
                title="Another Clean Doc",
                content="Also clean content here.",
                published_at=now,
            )
        )

        # Run audit
        result = await service.run_quarterly_audit()

        # Verify result
        assert result.is_complete
        assert result.materials_scanned == 2
        assert result.violations_found == 0
        assert not result.has_violations
        assert result.remediation_deadline is None

        # Verify events written
        assert event_writer.write_event.call_count == 2  # Started + completed
        calls = event_writer.write_event.call_args_list
        assert calls[0].kwargs["event_type"] == AUDIT_STARTED_EVENT_TYPE
        assert calls[1].kwargs["event_type"] == AUDIT_COMPLETED_EVENT_TYPE

        # Verify audit saved to repository
        saved_audit = await audit_repository.get_audit(result.audit_id)
        assert saved_audit is not None
        assert saved_audit.status == AuditStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_complete_audit_with_violations_workflow(
        self,
        service: QuarterlyAuditService,
        material_repository: MaterialRepositoryStub,
        audit_repository: AuditRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test complete audit workflow with violations found."""
        now = datetime.now(timezone.utc)
        # Add material that contains prohibited language
        material_repository.add_material(
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Bad Publication",
                content="This system exhibits genuine consciousness and is sentient.",
                published_at=now,
            )
        )

        # Run audit
        result = await service.run_quarterly_audit()

        # Verify result
        assert result.is_complete
        assert result.materials_scanned == 1
        assert result.violations_found == 1
        assert result.has_violations
        assert result.remediation_deadline is not None

        # Verify violation details
        assert len(result.violation_details) == 1
        violation = result.violation_details[0]
        assert violation.material_id == "mat-001"
        assert violation.remediation_status == RemediationStatus.PENDING
        assert len(violation.matched_terms) > 0

        # Verify events (started, violation, completed)
        assert event_writer.write_event.call_count == 3
        event_types = [c.kwargs["event_type"] for c in event_writer.write_event.call_args_list]
        assert AUDIT_STARTED_EVENT_TYPE in event_types
        assert MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE in event_types
        assert AUDIT_COMPLETED_EVENT_TYPE in event_types

    @pytest.mark.asyncio
    async def test_audit_respects_halt_state(
        self,
        service: QuarterlyAuditService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that audit respects halt state per CT-11."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError, match="FR57"):
            await service.run_quarterly_audit()

    @pytest.mark.asyncio
    async def test_audit_workflow_with_empty_materials(
        self,
        service: QuarterlyAuditService,
        event_writer: AsyncMock,
    ) -> None:
        """Test audit workflow when no materials exist."""
        # No materials added
        result = await service.run_quarterly_audit()

        assert result.is_complete
        assert result.materials_scanned == 0
        assert result.violations_found == 0

    @pytest.mark.asyncio
    async def test_audit_workflow_with_multiple_violation_materials(
        self,
        service: QuarterlyAuditService,
        material_repository: MaterialRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test audit with multiple violating materials."""
        now = datetime.now(timezone.utc)
        material_repository.add_material(
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Bad Publication 1",
                content="This claims emergence of new capabilities.",
                published_at=now,
            )
        )
        material_repository.add_material(
            Material(
                material_id="mat-002",
                material_type="publication",
                title="Bad Publication 2",
                content="This claims consciousness in the system.",
                published_at=now,
            )
        )
        material_repository.add_material(
            Material(
                material_id="mat-003",
                material_type="publication",
                title="Clean Publication",
                content="This is clean content.",
                published_at=now,
            )
        )

        result = await service.run_quarterly_audit()

        assert result.materials_scanned == 3
        assert result.violations_found == 2
        assert len(result.violation_details) == 2
        # 4 events: started + 2 violations + completed
        assert event_writer.write_event.call_count == 4


class TestAuditViolationTriggersEvents:
    """Tests for violations triggering proper events (CT-12)."""

    @pytest.mark.asyncio
    async def test_violation_event_contains_material_details(
        self,
        service: QuarterlyAuditService,
        material_repository: MaterialRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test that violation events contain full material details."""
        now = datetime.now(timezone.utc)
        material_repository.add_material(
            Material(
                material_id="mat-violation",
                material_type="report",
                title="Violating Report",
                content="Claims of genuine consciousness.",
                published_at=now,
            )
        )

        await service.run_quarterly_audit()

        # Find violation event
        violation_calls = [
            c for c in event_writer.write_event.call_args_list
            if c.kwargs["event_type"] == MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE
        ]
        assert len(violation_calls) == 1
        payload = violation_calls[0].kwargs["payload"]
        assert payload["material_id"] == "mat-violation"
        assert payload["material_type"] == "report"
        assert payload["title"] == "Violating Report"
        assert "matched_terms" in payload
        assert len(payload["matched_terms"]) > 0

    @pytest.mark.asyncio
    async def test_audit_started_event_has_correct_agent_id(
        self,
        service: QuarterlyAuditService,
        event_writer: AsyncMock,
    ) -> None:
        """Test that audit events use correct system agent ID."""
        await service.run_quarterly_audit()

        # All events should use AUDIT_SYSTEM_AGENT_ID
        for call in event_writer.write_event.call_args_list:
            assert call.kwargs["agent_id"] == AUDIT_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_completed_event_includes_audit_statistics(
        self,
        service: QuarterlyAuditService,
        material_repository: MaterialRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test that completed event includes full statistics."""
        now = datetime.now(timezone.utc)
        material_repository.add_material(
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Clean",
                content="Clean content.",
                published_at=now,
            )
        )
        material_repository.add_material(
            Material(
                material_id="mat-002",
                material_type="publication",
                title="Violating",
                content="Claims of achieved consciousness.",
                published_at=now,
            )
        )

        await service.run_quarterly_audit()

        # Find completed event
        completed_calls = [
            c for c in event_writer.write_event.call_args_list
            if c.kwargs["event_type"] == AUDIT_COMPLETED_EVENT_TYPE
        ]
        assert len(completed_calls) == 1
        payload = completed_calls[0].kwargs["payload"]
        assert payload["materials_scanned"] == 2
        assert payload["violations_found"] == 1
        assert payload["status"] == "violations_found"

    @pytest.mark.asyncio
    async def test_clean_audit_completed_event_status(
        self,
        service: QuarterlyAuditService,
        event_writer: AsyncMock,
    ) -> None:
        """Test that clean audit has correct status."""
        await service.run_quarterly_audit()

        completed_calls = [
            c for c in event_writer.write_event.call_args_list
            if c.kwargs["event_type"] == AUDIT_COMPLETED_EVENT_TYPE
        ]
        payload = completed_calls[0].kwargs["payload"]
        assert payload["status"] == "clean"


class TestAuditHistoryTracking:
    """Tests for audit history tracking."""

    @pytest.mark.asyncio
    async def test_audit_history_returns_completed_audits(
        self,
        service: QuarterlyAuditService,
        audit_repository: AuditRepositoryStub,
    ) -> None:
        """Test that audit history returns completed audits."""
        # Run an audit first
        await service.run_quarterly_audit()

        # Check history
        history = await service.get_audit_history(limit=10)

        assert len(history) == 1
        assert history[0].status == AuditStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_current_quarter_audit_returns_audit(
        self,
        service: QuarterlyAuditService,
    ) -> None:
        """Test getting current quarter audit."""
        # Run audit
        result = await service.run_quarterly_audit()

        # Get current quarter
        current = await service.get_current_quarter_audit()

        assert current is not None
        assert current.audit_id == result.audit_id

    @pytest.mark.asyncio
    async def test_get_audit_status_by_id(
        self,
        service: QuarterlyAuditService,
    ) -> None:
        """Test getting audit status by ID."""
        result = await service.run_quarterly_audit()

        status = await service.get_audit_status(result.audit_id)

        assert status.audit_id == result.audit_id
        assert status.is_complete


class TestRemediationDeadlineCalculation:
    """Tests for remediation deadline calculation (FR57)."""

    @pytest.mark.asyncio
    async def test_deadline_is_7_days_from_completion(
        self,
        service: QuarterlyAuditService,
        material_repository: MaterialRepositoryStub,
    ) -> None:
        """Test that deadline is exactly 7 days from completion."""
        now = datetime.now(timezone.utc)
        material_repository.add_material(
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Violating",
                content="Claims of genuine consciousness in the system.",
                published_at=now,
            )
        )

        result = await service.run_quarterly_audit()

        assert result.remediation_deadline is not None
        delta = result.remediation_deadline - result.completed_at  # type: ignore
        assert delta.days == REMEDIATION_DEADLINE_DAYS

    @pytest.mark.asyncio
    async def test_no_deadline_for_clean_audit(
        self,
        service: QuarterlyAuditService,
    ) -> None:
        """Test that clean audits have no remediation deadline."""
        result = await service.run_quarterly_audit()

        assert result.remediation_deadline is None

    @pytest.mark.asyncio
    async def test_deadline_stored_in_repository(
        self,
        service: QuarterlyAuditService,
        material_repository: MaterialRepositoryStub,
        audit_repository: AuditRepositoryStub,
    ) -> None:
        """Test that deadline is persisted to repository."""
        now = datetime.now(timezone.utc)
        material_repository.add_material(
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Violating",
                content="Claims consciousness.",
                published_at=now,
            )
        )

        result = await service.run_quarterly_audit()
        saved = await audit_repository.get_audit(result.audit_id)

        assert saved is not None
        assert saved.remediation_deadline == result.remediation_deadline


class TestConcurrentAuditPrevention:
    """Tests for preventing concurrent audits."""

    @pytest.mark.asyncio
    async def test_cannot_start_audit_while_in_progress(
        self,
        material_repository: MaterialRepositoryStub,
        audit_repository: AuditRepositoryStub,
        scanner: ProhibitedLanguageScannerStub,
        halt_checker: HaltCheckerStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test that concurrent audits are prevented."""
        # Create in-progress audit manually
        now = datetime.now(timezone.utc)
        quarter = AuditQuarter.from_datetime(now)
        in_progress = MaterialAudit.create_in_progress(
            audit_id=f"audit-{quarter.year}-Q{quarter.quarter}",
            quarter=quarter,
            started_at=now,
        )
        await audit_repository.save_audit(in_progress)

        service = QuarterlyAuditService(
            material_repository=material_repository,
            audit_repository=audit_repository,
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        with pytest.raises(AuditInProgressError):
            await service.run_quarterly_audit()

    @pytest.mark.asyncio
    async def test_can_start_new_audit_after_previous_completes(
        self,
        material_repository: MaterialRepositoryStub,
        audit_repository: AuditRepositoryStub,
        scanner: ProhibitedLanguageScannerStub,
        halt_checker: HaltCheckerStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test that new audit can start after previous completes."""
        # Create completed audit from previous quarter
        now = datetime.now(timezone.utc)
        prev_quarter = AuditQuarter.from_datetime(now).previous_quarter()
        completed = MaterialAudit(
            audit_id=f"audit-{prev_quarter.year}-Q{prev_quarter.quarter}",
            quarter=prev_quarter,
            status=AuditStatus.COMPLETED,
            materials_scanned=10,
            violations_found=0,
            violation_details=(),
            started_at=now - timedelta(days=90),
            completed_at=now - timedelta(days=90),
        )
        await audit_repository.save_audit(completed)

        service = QuarterlyAuditService(
            material_repository=material_repository,
            audit_repository=audit_repository,
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Should be able to run new audit
        result = await service.run_quarterly_audit()
        assert result.is_complete


class TestAuditDueCheckAcrossQuarters:
    """Tests for audit due checking across quarters."""

    @pytest.mark.asyncio
    async def test_audit_due_when_no_previous_audit(
        self,
        service: QuarterlyAuditService,
    ) -> None:
        """Test that audit is due when no previous audit exists."""
        is_due = await service.check_audit_due()
        assert is_due is True

    @pytest.mark.asyncio
    async def test_audit_not_due_when_current_quarter_completed(
        self,
        material_repository: MaterialRepositoryStub,
        audit_repository: AuditRepositoryStub,
        scanner: ProhibitedLanguageScannerStub,
        halt_checker: HaltCheckerStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test that audit is not due when current quarter already audited."""
        # Complete an audit for current quarter
        now = datetime.now(timezone.utc)
        quarter = AuditQuarter.from_datetime(now)
        completed = MaterialAudit(
            audit_id=f"audit-{quarter.year}-Q{quarter.quarter}",
            quarter=quarter,
            status=AuditStatus.COMPLETED,
            materials_scanned=10,
            violations_found=0,
            violation_details=(),
            started_at=now - timedelta(hours=1),
            completed_at=now,
        )
        await audit_repository.save_audit(completed)

        service = QuarterlyAuditService(
            material_repository=material_repository,
            audit_repository=audit_repository,
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        is_due = await service.check_audit_due()
        assert is_due is False

    @pytest.mark.asyncio
    async def test_audit_due_check_respects_halt(
        self,
        service: QuarterlyAuditService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that due check respects halt state."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.check_audit_due()
