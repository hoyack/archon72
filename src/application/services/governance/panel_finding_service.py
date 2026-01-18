"""Panel Finding Service - Service for preserving panel findings.

Story: consent-gov-6-5: Panel Finding Preservation

This service coordinates finding preservation, event emission, and
queries. It ensures all findings are recorded immutably with full
context (dissent, voting record, statement linkage).

Key Features:
- Preserves findings in append-only ledger (FR40)
- Emits judicial.panel.finding_issued event (AC4)
- Preserves dissent with finding (FR39, AC3)
- Maintains statement linkage (AC6)
- Supports historical queries (AC7)

Constitutional Constraints:
- NFR-CONST-06: Findings cannot be deleted or modified
- All operations witnessed via event emission

References:
    - FR40: System can record all panel findings in append-only ledger
    - NFR-CONST-06: Panel findings cannot be deleted or modified
    - FR39: Prince Panel can record dissent in finding
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from src.application.ports.governance.panel_finding_port import PanelFindingPort
from src.domain.governance.panel import (
    Determination,
    FindingRecord,
    PanelFinding,
)

if TYPE_CHECKING:
    pass


class TimeAuthorityProtocol(Protocol):
    """Protocol for time authority dependency."""

    def now(self) -> datetime:
        """Get current timestamp."""
        ...


class EventEmitterProtocol(Protocol):
    """Protocol for event emission dependency."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Emit a governance event."""
        ...


# Event types for finding operations
FINDING_ISSUED_EVENT = "judicial.panel.finding_issued"
DISSENT_RECORDED_EVENT = "judicial.panel.dissent_recorded"


class PanelFindingService:
    """Service for preserving panel findings.

    This service is responsible for:
    - Recording findings to the append-only ledger
    - Emitting finding events for observability
    - Computing integrity hashes
    - Coordinating queries

    The service enforces immutability by using the PanelFindingPort
    which has no update/delete methods.

    Example:
        >>> service = PanelFindingService(
        ...     finding_port=finding_adapter,
        ...     event_emitter=event_emitter,
        ...     time_authority=time_authority,
        ... )
        >>> record = await service.preserve_finding(finding)
        >>> assert record.finding == finding
    """

    def __init__(
        self,
        finding_port: PanelFindingPort,
        event_emitter: EventEmitterProtocol,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the service with dependencies.

        Args:
            finding_port: Port for finding persistence.
            event_emitter: Protocol for emitting events.
            time_authority: Protocol for timestamps.
        """
        self._findings = finding_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def preserve_finding(
        self,
        finding: PanelFinding,
    ) -> FindingRecord:
        """Preserve a finding in the append-only ledger.

        Records the finding immutably and emits events for observability.
        Dissent, if present, is preserved as part of the finding (FR39).

        Args:
            finding: The PanelFinding to preserve.

        Returns:
            FindingRecord with ledger metadata.

        Constitutional Reference:
            - FR40: Record in append-only ledger
            - NFR-CONST-06: Immutable once recorded
            - FR39: Preserve dissent with finding
        """
        # Record to ledger
        record = await self._findings.record_finding(finding)

        # Emit finding issued event (AC4)
        await self._emit_finding_issued_event(finding, record)

        # Emit dissent event if present (FR39)
        if finding.dissent is not None:
            await self._emit_dissent_recorded_event(finding)

        return record

    async def get_finding(
        self,
        finding_id: UUID,
    ) -> FindingRecord | None:
        """Get a finding by ID.

        Args:
            finding_id: UUID of the finding.

        Returns:
            FindingRecord if found, None otherwise.
        """
        return await self._findings.get_finding(finding_id)

    async def get_findings_for_statement(
        self,
        statement_id: UUID,
    ) -> list[FindingRecord]:
        """Get all findings for a witness statement (AC6).

        Args:
            statement_id: UUID of the witness statement.

        Returns:
            List of findings for this statement.
        """
        return await self._findings.get_findings_for_statement(statement_id)

    async def get_findings_by_panel(
        self,
        panel_id: UUID,
    ) -> list[FindingRecord]:
        """Get all findings from a panel.

        Args:
            panel_id: UUID of the panel.

        Returns:
            List of findings from this panel.
        """
        return await self._findings.get_findings_by_panel(panel_id)

    async def get_findings_by_determination(
        self,
        determination: Determination,
        since: datetime | None = None,
    ) -> list[FindingRecord]:
        """Get findings by determination type (AC7).

        Args:
            determination: The determination type.
            since: Optional start date.

        Returns:
            List of findings with this determination.
        """
        return await self._findings.get_findings_by_determination(determination, since)

    async def get_findings_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[FindingRecord]:
        """Get findings in a date range (AC7).

        Args:
            start: Start of range (inclusive).
            end: End of range (inclusive).

        Returns:
            List of findings in this range.
        """
        return await self._findings.get_findings_in_range(start, end)

    async def get_findings_with_dissent(
        self,
        since: datetime | None = None,
    ) -> list[FindingRecord]:
        """Get all findings that have dissent recorded.

        Useful for analyzing close decisions and patterns.

        Args:
            since: Optional start date filter.

        Returns:
            List of findings with dissent.
        """
        if since is None:
            # Use a very old date to get all (timezone-aware)
            since = datetime.min.replace(tzinfo=timezone.utc)

        all_findings = await self._findings.get_findings_in_range(
            start=since,
            end=self._time.now(),
        )

        return [f for f in all_findings if f.has_dissent]

    async def count_findings(
        self,
        determination: Determination | None = None,
        since: datetime | None = None,
    ) -> int:
        """Count findings matching criteria.

        Args:
            determination: Optional filter by determination.
            since: Optional filter by date.

        Returns:
            Count of matching findings.
        """
        return await self._findings.count_findings(determination, since)

    async def get_latest_finding(self) -> FindingRecord | None:
        """Get the most recently recorded finding.

        Returns:
            Latest FindingRecord or None if no findings exist.
        """
        return await self._findings.get_latest_finding()

    # =========================================================================
    # Private helpers
    # =========================================================================

    async def _emit_finding_issued_event(
        self,
        finding: PanelFinding,
        record: FindingRecord,
    ) -> None:
        """Emit the judicial.panel.finding_issued event.

        Event includes key finding data for Knight observability.
        """
        await self._event_emitter.emit(
            event_type=FINDING_ISSUED_EVENT,
            actor="panel",
            payload={
                "finding_id": str(finding.finding_id),
                "panel_id": str(finding.panel_id),
                "statement_id": str(finding.statement_id),
                "determination": finding.determination.value,
                "remedy": finding.remedy.value if finding.remedy else None,
                "has_dissent": finding.dissent is not None,
                "dissenting_count": (
                    len(finding.dissent.dissenting_member_ids) if finding.dissent else 0
                ),
                "voting_record_count": len(finding.voting_record),
                "issued_at": finding.issued_at.isoformat(),
                "recorded_at": record.recorded_at.isoformat(),
                "ledger_position": record.ledger_position,
                "integrity_hash": record.integrity_hash,
            },
        )

    async def _emit_dissent_recorded_event(
        self,
        finding: PanelFinding,
    ) -> None:
        """Emit the judicial.panel.dissent_recorded event.

        Separate event for dissent tracking per FR39.
        """
        if finding.dissent is None:
            return

        await self._event_emitter.emit(
            event_type=DISSENT_RECORDED_EVENT,
            actor="panel",
            payload={
                "finding_id": str(finding.finding_id),
                "panel_id": str(finding.panel_id),
                "dissenting_members": [
                    str(m) for m in finding.dissent.dissenting_member_ids
                ],
                "dissenting_count": len(finding.dissent.dissenting_member_ids),
                "rationale_length": len(finding.dissent.rationale),
            },
        )


def compute_finding_hash(finding: PanelFinding) -> str:
    """Compute SHA-256 hash for finding integrity verification.

    Used by adapters to generate integrity_hash for FindingRecord.

    Args:
        finding: The PanelFinding to hash.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    finding_data = {
        "finding_id": str(finding.finding_id),
        "panel_id": str(finding.panel_id),
        "statement_id": str(finding.statement_id),
        "determination": finding.determination.value,
        "remedy": finding.remedy.value if finding.remedy else None,
        "majority_rationale": finding.majority_rationale,
        "dissent": (
            {
                "members": [str(m) for m in finding.dissent.dissenting_member_ids],
                "rationale": finding.dissent.rationale,
            }
            if finding.dissent
            else None
        ),
        "voting_record": {str(k): v for k, v in finding.voting_record.items()},
        "issued_at": finding.issued_at.isoformat(),
    }

    return hashlib.sha256(json.dumps(finding_data, sort_keys=True).encode()).hexdigest()
