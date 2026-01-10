"""Quarterly audit service (Story 9.3, FR57).

Application service for running quarterly material audits.
Orchestrates scanning of all public materials for prohibited
language and tracks audit results.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations (Golden Rule #1)
- CT-12: All audit events must be witnessed
- ADR-11: Emergence governance under complexity control
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.application.ports.audit_repository import AuditRepositoryProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.material_repository import (
    Material,
    MaterialRepositoryProtocol,
)
from src.application.ports.prohibited_language_scanner import (
    ProhibitedLanguageScannerProtocol,
)
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
    AuditCompletedEventPayload,
    AuditStartedEventPayload,
    ViolationFlaggedEventPayload,
)
from src.domain.models.material_audit import (
    REMEDIATION_DEADLINE_DAYS,
    AuditQuarter,
    AuditStatus,
    MaterialAudit,
    MaterialViolation,
    RemediationStatus,
    generate_audit_id,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService


class QuarterlyAuditService:
    """Service for running quarterly material audits (FR57).

    Orchestrates the quarterly audit process:
    1. Check if audit is due
    2. Scan all public materials for prohibited language
    3. Record violations and generate events
    4. Track remediation deadlines

    Constitutional Constraints:
    - CT-11: HALT CHECK FIRST on all public methods
    - CT-12: All audit events are witnessed via EventWriterService
    - FR57: Quarterly schedule enforcement
    """

    def __init__(
        self,
        material_repository: MaterialRepositoryProtocol,
        audit_repository: AuditRepositoryProtocol,
        scanner: ProhibitedLanguageScannerProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize QuarterlyAuditService.

        Args:
            material_repository: Repository for accessing public materials.
            audit_repository: Repository for tracking audit history.
            scanner: Scanner for detecting prohibited language.
            event_writer: Service for writing witnessed events.
            halt_checker: Checker for system halt state.
        """
        self._material_repository = material_repository
        self._audit_repository = audit_repository
        self._scanner = scanner
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def _check_halt(self) -> None:
        """Check halt state per CT-11 (Golden Rule #1).

        Raises:
            SystemHaltedError: If system is halted.
        """
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("FR57: Cannot run audit while system is halted")

    def _get_current_quarter(self) -> AuditQuarter:
        """Get the current quarter.

        Returns:
            AuditQuarter for the current date.
        """
        now = datetime.now(timezone.utc)
        return AuditQuarter.from_datetime(now)

    def _calculate_remediation_deadline(self, from_time: datetime) -> datetime:
        """Calculate remediation deadline per FR57.

        Args:
            from_time: When to calculate deadline from.

        Returns:
            Deadline datetime (7 days from from_time).
        """
        return from_time + timedelta(days=REMEDIATION_DEADLINE_DAYS)

    async def check_audit_due(self) -> bool:
        """Check if a quarterly audit is due.

        HALT CHECK FIRST (CT-11).

        Returns:
            True if an audit should be run, False otherwise.

        Raises:
            SystemHaltedError: If system is halted.
        """
        await self._check_halt()
        return await self._audit_repository.is_audit_due()

    async def run_quarterly_audit(self) -> MaterialAudit:
        """Run the quarterly audit per FR57.

        HALT CHECK FIRST (CT-11).

        Scans all public materials for prohibited language and
        records the results. Creates witnessed events for audit
        start, completion, and any violations found.

        Returns:
            The completed MaterialAudit record.

        Raises:
            SystemHaltedError: If system is halted.
            AuditNotDueError: If audit is not yet due.
            AuditInProgressError: If an audit is already running.
            AuditFailedError: If audit fails to complete.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        # Check if audit is due
        if not await self._audit_repository.is_audit_due():
            latest = await self._audit_repository.get_latest_audit()
            current_quarter = self._get_current_quarter()
            raise AuditNotDueError(
                last_audit_quarter=str(latest.quarter) if latest else None,
                current_quarter=str(current_quarter),
            )

        # Check for in-progress audit
        in_progress = await self._audit_repository.get_in_progress_audit()
        if in_progress:
            raise AuditInProgressError(in_progress.audit_id)

        # Start the audit
        now = datetime.now(timezone.utc)
        quarter = self._get_current_quarter()
        audit_id = generate_audit_id(quarter)

        audit = MaterialAudit.create_in_progress(
            audit_id=audit_id,
            quarter=quarter,
            started_at=now,
        )

        # Save initial audit state
        await self._audit_repository.save_audit(audit)

        # Write AuditStartedEvent (CT-12)
        started_payload = AuditStartedEventPayload(
            audit_id=audit_id,
            quarter=str(quarter),
            scheduled_at=now,
            started_at=now,
        )
        await self._event_writer.write_event(
            event_type=AUDIT_STARTED_EVENT_TYPE,
            payload=started_payload.to_dict(),
            agent_id=AUDIT_SYSTEM_AGENT_ID,
        )

        # Scan all materials
        try:
            materials = await self._material_repository.get_all_public_materials()
            violations: list[MaterialViolation] = []

            for material in materials:
                violation = await self._scan_material(audit_id, material, now)
                if violation:
                    violations.append(violation)

            # Complete the audit
            completed_at = datetime.now(timezone.utc)
            remediation_deadline = (
                self._calculate_remediation_deadline(completed_at)
                if violations
                else None
            )

            completed_audit = audit.complete(
                materials_scanned=len(materials),
                violation_details=tuple(violations),
                completed_at=completed_at,
                remediation_deadline=remediation_deadline,
            )

            # Save completed audit
            await self._audit_repository.save_audit(completed_audit)

            # Write AuditCompletedEvent (CT-12)
            if violations:
                completed_payload = AuditCompletedEventPayload.violations_audit(
                    audit_id=audit_id,
                    quarter=str(quarter),
                    materials_scanned=len(materials),
                    violations_found=len(violations),
                    started_at=audit.started_at,
                    completed_at=completed_at,
                    remediation_deadline=remediation_deadline,  # type: ignore
                )
            else:
                completed_payload = AuditCompletedEventPayload.clean_audit(
                    audit_id=audit_id,
                    quarter=str(quarter),
                    materials_scanned=len(materials),
                    started_at=audit.started_at,
                    completed_at=completed_at,
                )

            await self._event_writer.write_event(
                event_type=AUDIT_COMPLETED_EVENT_TYPE,
                payload=completed_payload.to_dict(),
                agent_id=AUDIT_SYSTEM_AGENT_ID,
            )

            return completed_audit

        except Exception as e:
            # Mark audit as failed
            failed_at = datetime.now(timezone.utc)
            failed_audit = audit.fail(completed_at=failed_at)
            await self._audit_repository.save_audit(failed_audit)

            # Write failed completion event
            failed_payload = AuditCompletedEventPayload.failed_audit(
                audit_id=audit_id,
                quarter=str(quarter),
                materials_scanned=0,
                started_at=audit.started_at,
                completed_at=failed_at,
            )
            await self._event_writer.write_event(
                event_type=AUDIT_COMPLETED_EVENT_TYPE,
                payload=failed_payload.to_dict(),
                agent_id=AUDIT_SYSTEM_AGENT_ID,
            )

            raise AuditFailedError(audit_id, str(e)) from e

    async def _scan_material(
        self,
        audit_id: str,
        material: Material,
        flagged_at: datetime,
    ) -> MaterialViolation | None:
        """Scan a single material for prohibited language.

        Args:
            audit_id: The current audit ID.
            material: The material to scan.
            flagged_at: Timestamp for flagging.

        Returns:
            MaterialViolation if prohibited content found, None otherwise.
        """
        scan_result = await self._scanner.scan_content(material.content)

        if scan_result.violations_found:
            # Create violation record
            violation = MaterialViolation(
                material_id=material.material_id,
                material_type=material.material_type,
                title=material.title,
                matched_terms=tuple(scan_result.matched_terms),
                flagged_at=flagged_at,
                remediation_status=RemediationStatus.PENDING,
            )

            # Write ViolationFlaggedEvent (CT-12)
            violation_payload = ViolationFlaggedEventPayload(
                audit_id=audit_id,
                material_id=material.material_id,
                material_type=material.material_type,
                title=material.title,
                matched_terms=tuple(scan_result.matched_terms),
                flagged_at=flagged_at,
            )
            await self._event_writer.write_event(
                event_type=MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE,
                payload=violation_payload.to_dict(),
                agent_id=AUDIT_SYSTEM_AGENT_ID,
            )

            return violation

        return None

    async def get_audit_status(self, audit_id: str) -> MaterialAudit:
        """Get the status of a specific audit.

        HALT CHECK FIRST (CT-11).

        Args:
            audit_id: The ID of the audit to retrieve.

        Returns:
            The MaterialAudit record.

        Raises:
            SystemHaltedError: If system is halted.
            AuditNotFoundError: If audit does not exist.
        """
        await self._check_halt()

        audit = await self._audit_repository.get_audit(audit_id)
        if audit is None:
            raise AuditNotFoundError(audit_id)
        return audit

    async def get_audit_history(self, limit: int = 10) -> list[MaterialAudit]:
        """Get recent audit history.

        HALT CHECK FIRST (CT-11).

        Args:
            limit: Maximum number of audits to return.

        Returns:
            List of recent audits, most recent first.

        Raises:
            SystemHaltedError: If system is halted.
        """
        await self._check_halt()
        return await self._audit_repository.get_audit_history(limit)

    async def get_current_quarter_audit(self) -> MaterialAudit | None:
        """Get the audit for the current quarter if it exists.

        HALT CHECK FIRST (CT-11).

        Returns:
            The current quarter's audit if exists, None otherwise.

        Raises:
            SystemHaltedError: If system is halted.
        """
        await self._check_halt()
        current_quarter = self._get_current_quarter()
        return await self._audit_repository.get_audit_by_quarter(current_quarter)
