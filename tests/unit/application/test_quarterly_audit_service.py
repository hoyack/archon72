"""Unit tests for quarterly audit service (Story 9.3, FR57).

Tests QuarterlyAuditService for quarterly material audit operations.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations (Golden Rule #1)
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.material_repository import Material
from src.application.ports.prohibited_language_scanner import ScanResult
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
    MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE,
)
from src.domain.models.material_audit import (
    AuditQuarter,
    AuditStatus,
    MaterialAudit,
)


@pytest.fixture
def mock_material_repository() -> AsyncMock:
    """Create mock material repository."""
    mock = AsyncMock()
    mock.get_all_public_materials = AsyncMock(return_value=[])
    mock.get_material_count = AsyncMock(return_value=0)
    return mock


@pytest.fixture
def mock_audit_repository() -> AsyncMock:
    """Create mock audit repository."""
    mock = AsyncMock()
    mock.is_audit_due = AsyncMock(return_value=True)
    mock.get_in_progress_audit = AsyncMock(return_value=None)
    mock.get_latest_audit = AsyncMock(return_value=None)
    mock.get_audit = AsyncMock(return_value=None)
    mock.get_audit_history = AsyncMock(return_value=[])
    mock.get_audit_by_quarter = AsyncMock(return_value=None)
    mock.save_audit = AsyncMock()
    return mock


@pytest.fixture
def mock_scanner() -> MagicMock:
    """Create mock scanner."""
    mock = MagicMock()
    mock.scan_content = AsyncMock(return_value=ScanResult.no_violations())
    return mock


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer."""
    mock = AsyncMock()
    mock.write_event = AsyncMock()
    return mock


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker."""
    mock = AsyncMock()
    mock.is_halted = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def service(
    mock_material_repository: AsyncMock,
    mock_audit_repository: AsyncMock,
    mock_scanner: MagicMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
) -> QuarterlyAuditService:
    """Create service with mocked dependencies."""
    return QuarterlyAuditService(
        material_repository=mock_material_repository,
        audit_repository=mock_audit_repository,
        scanner=mock_scanner,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
    )


class TestHaltCheckFirst:
    """Tests for CT-11 HALT CHECK FIRST compliance."""

    @pytest.mark.asyncio
    async def test_check_audit_due_halted_raises(
        self,
        service: QuarterlyAuditService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test that check_audit_due raises when system halted."""
        mock_halt_checker.is_halted = AsyncMock(return_value=True)

        with pytest.raises(SystemHaltedError, match="FR57"):
            await service.check_audit_due()

    @pytest.mark.asyncio
    async def test_run_quarterly_audit_halted_raises(
        self,
        service: QuarterlyAuditService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test that run_quarterly_audit raises when system halted."""
        mock_halt_checker.is_halted = AsyncMock(return_value=True)

        with pytest.raises(SystemHaltedError, match="FR57"):
            await service.run_quarterly_audit()

    @pytest.mark.asyncio
    async def test_get_audit_status_halted_raises(
        self,
        service: QuarterlyAuditService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test that get_audit_status raises when system halted."""
        mock_halt_checker.is_halted = AsyncMock(return_value=True)

        with pytest.raises(SystemHaltedError, match="FR57"):
            await service.get_audit_status("audit-2026-Q1")

    @pytest.mark.asyncio
    async def test_get_audit_history_halted_raises(
        self,
        service: QuarterlyAuditService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test that get_audit_history raises when system halted."""
        mock_halt_checker.is_halted = AsyncMock(return_value=True)

        with pytest.raises(SystemHaltedError, match="FR57"):
            await service.get_audit_history()


class TestCheckAuditDue:
    """Tests for check_audit_due method."""

    @pytest.mark.asyncio
    async def test_audit_due_returns_true(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that check_audit_due returns True when due."""
        mock_audit_repository.is_audit_due = AsyncMock(return_value=True)

        result = await service.check_audit_due()

        assert result is True

    @pytest.mark.asyncio
    async def test_audit_not_due_returns_false(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that check_audit_due returns False when not due."""
        mock_audit_repository.is_audit_due = AsyncMock(return_value=False)

        result = await service.check_audit_due()

        assert result is False


class TestRunQuarterlyAudit:
    """Tests for run_quarterly_audit method."""

    @pytest.mark.asyncio
    async def test_audit_not_due_raises(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that run_quarterly_audit raises when audit not due."""
        mock_audit_repository.is_audit_due = AsyncMock(return_value=False)

        with pytest.raises(AuditNotDueError):
            await service.run_quarterly_audit()

    @pytest.mark.asyncio
    async def test_audit_in_progress_raises(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that run_quarterly_audit raises when audit in progress."""
        mock_audit_repository.is_audit_due = AsyncMock(return_value=True)
        mock_audit_repository.get_in_progress_audit = AsyncMock(
            return_value=MaterialAudit.create_in_progress(
                audit_id="audit-2026-Q1",
                quarter=AuditQuarter(year=2026, quarter=1),
                started_at=datetime.now(timezone.utc),
            )
        )

        with pytest.raises(AuditInProgressError, match="audit-2026-Q1"):
            await service.run_quarterly_audit()

    @pytest.mark.asyncio
    async def test_clean_audit_no_violations(
        self,
        service: QuarterlyAuditService,
        mock_material_repository: AsyncMock,
        mock_audit_repository: AsyncMock,
        mock_scanner: MagicMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test running audit with no violations."""
        # Setup materials
        materials = [
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Test Publication",
                content="Clean content here",
                published_at=datetime.now(timezone.utc),
            )
        ]
        mock_material_repository.get_all_public_materials = AsyncMock(return_value=materials)
        mock_scanner.scan_content = AsyncMock(return_value=ScanResult.no_violations())

        result = await service.run_quarterly_audit()

        assert result.is_complete
        assert result.materials_scanned == 1
        assert result.violations_found == 0
        assert not result.has_violations

        # Verify events written
        assert mock_event_writer.write_event.call_count == 2  # Started and completed
        calls = mock_event_writer.write_event.call_args_list
        assert calls[0].kwargs["event_type"] == AUDIT_STARTED_EVENT_TYPE
        assert calls[1].kwargs["event_type"] == AUDIT_COMPLETED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_audit_with_violations(
        self,
        service: QuarterlyAuditService,
        mock_material_repository: AsyncMock,
        mock_audit_repository: AsyncMock,
        mock_scanner: MagicMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test running audit that finds violations."""
        # Setup materials with one violating
        materials = [
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Clean Publication",
                content="Clean content",
                published_at=datetime.now(timezone.utc),
            ),
            Material(
                material_id="mat-002",
                material_type="publication",
                title="Bad Publication",
                content="Content with sentient claims",
                published_at=datetime.now(timezone.utc),
            ),
        ]
        mock_material_repository.get_all_public_materials = AsyncMock(return_value=materials)

        # First scan clean, second has violation
        mock_scanner.scan_content = AsyncMock(
            side_effect=[
                ScanResult.no_violations(),
                ScanResult.with_violations(("sentient",)),
            ]
        )

        result = await service.run_quarterly_audit()

        assert result.is_complete
        assert result.materials_scanned == 2
        assert result.violations_found == 1
        assert result.has_violations
        assert result.remediation_deadline is not None

        # Verify events written
        assert mock_event_writer.write_event.call_count == 3  # Started, violation, completed
        calls = mock_event_writer.write_event.call_args_list
        assert calls[0].kwargs["event_type"] == AUDIT_STARTED_EVENT_TYPE
        assert calls[1].kwargs["event_type"] == MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE
        assert calls[2].kwargs["event_type"] == AUDIT_COMPLETED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_audit_failure_marks_failed(
        self,
        service: QuarterlyAuditService,
        mock_material_repository: AsyncMock,
        mock_audit_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that audit failure marks audit as failed."""
        mock_material_repository.get_all_public_materials = AsyncMock(
            side_effect=RuntimeError("Database error")
        )

        with pytest.raises(AuditFailedError, match="Database error"):
            await service.run_quarterly_audit()

        # Verify failed event written
        calls = mock_event_writer.write_event.call_args_list
        # Should have started and failed completed events
        completed_calls = [c for c in calls if c.kwargs["event_type"] == AUDIT_COMPLETED_EVENT_TYPE]
        assert len(completed_calls) == 1
        assert completed_calls[0].kwargs["payload"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_remediation_deadline_calculation(
        self,
        service: QuarterlyAuditService,
        mock_material_repository: AsyncMock,
        mock_scanner: MagicMock,
    ) -> None:
        """Test that remediation deadline is calculated correctly."""
        materials = [
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Bad Publication",
                content="Sentient content",
                published_at=datetime.now(timezone.utc),
            )
        ]
        mock_material_repository.get_all_public_materials = AsyncMock(return_value=materials)
        mock_scanner.scan_content = AsyncMock(
            return_value=ScanResult.with_violations(("sentient",))
        )

        result = await service.run_quarterly_audit()

        # Deadline should be 7 days from completion
        assert result.remediation_deadline is not None
        delta = result.remediation_deadline - result.completed_at  # type: ignore
        assert delta.days == 7


class TestGetAuditStatus:
    """Tests for get_audit_status method."""

    @pytest.mark.asyncio
    async def test_audit_not_found_raises(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that get_audit_status raises when audit not found."""
        mock_audit_repository.get_audit = AsyncMock(return_value=None)

        with pytest.raises(AuditNotFoundError, match="audit-2026-Q1"):
            await service.get_audit_status("audit-2026-Q1")

    @pytest.mark.asyncio
    async def test_audit_found_returns_audit(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that get_audit_status returns audit when found."""
        audit = MaterialAudit.create_in_progress(
            audit_id="audit-2026-Q1",
            quarter=AuditQuarter(year=2026, quarter=1),
            started_at=datetime.now(timezone.utc),
        )
        mock_audit_repository.get_audit = AsyncMock(return_value=audit)

        result = await service.get_audit_status("audit-2026-Q1")

        assert result == audit


class TestGetAuditHistory:
    """Tests for get_audit_history method."""

    @pytest.mark.asyncio
    async def test_returns_history(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that get_audit_history returns audit history."""
        now = datetime.now(timezone.utc)
        audits = [
            MaterialAudit(
                audit_id="audit-2026-Q1",
                quarter=AuditQuarter(year=2026, quarter=1),
                status=AuditStatus.COMPLETED,
                materials_scanned=100,
                violations_found=0,
                violation_details=(),
                started_at=now,
                completed_at=now + timedelta(hours=1),
            ),
        ]
        mock_audit_repository.get_audit_history = AsyncMock(return_value=audits)

        result = await service.get_audit_history(limit=10)

        assert len(result) == 1
        assert result[0].audit_id == "audit-2026-Q1"

    @pytest.mark.asyncio
    async def test_passes_limit(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test that get_audit_history passes limit to repository."""
        mock_audit_repository.get_audit_history = AsyncMock(return_value=[])

        await service.get_audit_history(limit=5)

        mock_audit_repository.get_audit_history.assert_called_once_with(5)


class TestGetCurrentQuarterAudit:
    """Tests for get_current_quarter_audit method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_audit(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test returns None when no audit for current quarter."""
        mock_audit_repository.get_audit_by_quarter = AsyncMock(return_value=None)

        result = await service.get_current_quarter_audit()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_audit_when_exists(
        self,
        service: QuarterlyAuditService,
        mock_audit_repository: AsyncMock,
    ) -> None:
        """Test returns audit when exists for current quarter."""
        now = datetime.now(timezone.utc)
        audit = MaterialAudit.create_in_progress(
            audit_id="audit-2026-Q1",
            quarter=AuditQuarter.from_datetime(now),
            started_at=now,
        )
        mock_audit_repository.get_audit_by_quarter = AsyncMock(return_value=audit)

        result = await service.get_current_quarter_audit()

        assert result == audit


class TestEventWriting:
    """Tests for CT-12 event witnessing compliance."""

    @pytest.mark.asyncio
    async def test_writes_audit_started_event(
        self,
        service: QuarterlyAuditService,
        mock_material_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that audit started event is written."""
        mock_material_repository.get_all_public_materials = AsyncMock(return_value=[])

        await service.run_quarterly_audit()

        # First call should be audit started
        calls = mock_event_writer.write_event.call_args_list
        started_call = calls[0]
        assert started_call.kwargs["event_type"] == AUDIT_STARTED_EVENT_TYPE
        assert "audit_id" in started_call.kwargs["payload"]
        assert "quarter" in started_call.kwargs["payload"]

    @pytest.mark.asyncio
    async def test_writes_audit_completed_event(
        self,
        service: QuarterlyAuditService,
        mock_material_repository: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that audit completed event is written."""
        mock_material_repository.get_all_public_materials = AsyncMock(return_value=[])

        await service.run_quarterly_audit()

        # Last call should be audit completed
        calls = mock_event_writer.write_event.call_args_list
        completed_call = calls[-1]
        assert completed_call.kwargs["event_type"] == AUDIT_COMPLETED_EVENT_TYPE
        assert "status" in completed_call.kwargs["payload"]
        assert "materials_scanned" in completed_call.kwargs["payload"]

    @pytest.mark.asyncio
    async def test_writes_violation_flagged_event(
        self,
        service: QuarterlyAuditService,
        mock_material_repository: AsyncMock,
        mock_scanner: MagicMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that violation flagged event is written for each violation."""
        materials = [
            Material(
                material_id="mat-001",
                material_type="publication",
                title="Bad Publication",
                content="Sentient content",
                published_at=datetime.now(timezone.utc),
            )
        ]
        mock_material_repository.get_all_public_materials = AsyncMock(return_value=materials)
        mock_scanner.scan_content = AsyncMock(
            return_value=ScanResult.with_violations(("sentient",))
        )

        await service.run_quarterly_audit()

        # Should have violation event
        calls = mock_event_writer.write_event.call_args_list
        violation_calls = [c for c in calls if c.kwargs["event_type"] == MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE]
        assert len(violation_calls) == 1
        assert violation_calls[0].kwargs["payload"]["material_id"] == "mat-001"
        assert "matched_terms" in violation_calls[0].kwargs["payload"]
