"""Incident Reporting Service (Story 8.4, FR54, FR145, FR147).

This service manages the creation, resolution, and publication of incident reports
for halt, fork, and override threshold events.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable by external parties
- FR145: Following halt, fork, or >3 overrides/day: incident report with
         timeline, root cause, contributing factors, prevention recommendations
- FR147: Incident reports SHALL be publicly available within 7 days of resolution;
         redaction only for active security vulnerabilities
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All incidents MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every write operation
2. WITNESS EVERYTHING - All incident events must be witnessed
3. FAIL LOUD - Never silently swallow incident creation errors
4. READS DURING HALT - Query operations work during halt (CT-13)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.incident_report_repository import (
    IncidentReportRepositoryPort,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.incident_report import (
    INCIDENT_REPORT_CREATED_EVENT_TYPE,
    INCIDENT_REPORT_PUBLISHED_EVENT_TYPE,
    INCIDENT_SYSTEM_AGENT_ID,
    IncidentReportCreatedPayload,
    IncidentReportPublishedPayload,
)
from src.domain.models.incident_report import (
    IncidentReport,
    IncidentStatus,
    IncidentType,
    TimelineEntry,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()


class IncidentNotFoundError(Exception):
    """Raised when an incident report is not found."""

    pass


class IncidentNotResolvedError(Exception):
    """Raised when trying to publish an unresolved incident."""

    pass


class PublicationNotEligibleError(Exception):
    """Raised when incident is not eligible for publication."""

    pass


class DuplicateIncidentError(Exception):
    """Raised when trying to create duplicate incident for same event."""

    pass


class IncidentReportingService:
    """Manages incident reports for halt, fork, and override threshold events (FR145, FR147).

    This service provides:
    1. Incident creation for halt, fork, and override threshold events (FR145)
    2. Timeline management for incident investigation
    3. Resolution tracking with prevention recommendations
    4. Publication flow with 7-day rule enforcement (FR147)
    5. Redaction support for security vulnerabilities

    Constitutional Constraints:
    - FR145: Incident reports required for halt, fork, >3 overrides/day
    - FR147: Incident reports SHALL be publicly available within 7 days
    - CT-11: HALT CHECK FIRST at every write operation
    - CT-12: All incident events MUST be witnessed
    - CT-13: Reads continue during halt (integrity > availability)

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every write operation checks halt state
    2. WITNESS EVERYTHING - All events are witnessed via EventWriterService
    3. FAIL LOUD - Raise specific errors for failures
    4. READS DURING HALT - Query operations bypass halt check
    """

    def __init__(
        self,
        repository: IncidentReportRepositoryPort,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Incident Reporting Service.

        Args:
            repository: Repository for incident report storage and queries.
            event_writer: Service for writing witnessed events (CT-12).
            halt_checker: Interface to check system halt state (CT-11).
        """
        self._repository = repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def create_halt_incident(
        self,
        halt_event_id: UUID,
        cause: str,
        impact: str,
        timeline: list[TimelineEntry] | None = None,
    ) -> IncidentReport:
        """Create an incident report for a halt event (FR145, AC1).

        Constitutional Constraints:
        - FR145: Incident report with timeline, root cause, contributing factors
        - CT-11: HALT CHECK FIRST
        - CT-12: Event is witnessed via EventWriterService

        Args:
            halt_event_id: ID of the halt event that triggered this incident.
            cause: Root cause description.
            impact: Impact assessment.
            timeline: Optional initial timeline entries.

        Returns:
            The created IncidentReport.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            DuplicateIncidentError: If incident already exists for this event.
        """
        return await self._create_incident(
            incident_type=IncidentType.HALT,
            title=f"System Halt - {cause[:50]}",
            cause=cause,
            impact=impact,
            related_event_ids=[halt_event_id],
            timeline=timeline,
        )

    async def create_fork_incident(
        self,
        fork_event_id: UUID,
        detection_details: str,
        affected_events: list[UUID],
        timeline: list[TimelineEntry] | None = None,
    ) -> IncidentReport:
        """Create an incident report for a fork detection (FR145, AC2).

        Constitutional Constraints:
        - FR145: Incident report with timeline, root cause, contributing factors
        - CT-11: HALT CHECK FIRST
        - CT-12: Event is witnessed via EventWriterService

        Args:
            fork_event_id: ID of the fork detection event.
            detection_details: Details about the fork detection.
            affected_events: IDs of events affected by the fork.
            timeline: Optional initial timeline entries.

        Returns:
            The created IncidentReport.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            DuplicateIncidentError: If incident already exists for this event.
        """
        all_event_ids = [fork_event_id] + affected_events
        return await self._create_incident(
            incident_type=IncidentType.FORK,
            title="Fork Detection - Hash Chain Conflict",
            cause=detection_details,
            impact="Constitutional crisis detected - system integrity compromised",
            related_event_ids=all_event_ids,
            timeline=timeline,
        )

    async def create_override_threshold_incident(
        self,
        override_event_ids: list[UUID],
        keeper_ids: list[str],
        timeline: list[TimelineEntry] | None = None,
    ) -> IncidentReport:
        """Create an incident report for override threshold exceeded (FR145, AC3).

        Constitutional Constraints:
        - FR145: >3 overrides/day triggers incident report
        - CT-11: HALT CHECK FIRST
        - CT-12: Event is witnessed via EventWriterService

        Args:
            override_event_ids: IDs of the override events.
            keeper_ids: IDs of the Keepers who performed overrides.
            timeline: Optional initial timeline entries.

        Returns:
            The created IncidentReport.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        override_count = len(override_event_ids)
        keepers_str = ", ".join(keeper_ids)

        return await self._create_incident(
            incident_type=IncidentType.OVERRIDE_THRESHOLD,
            title=f"Override Threshold Exceeded - {override_count} Overrides Today",
            cause=f">3 Keeper overrides in a single day by: {keepers_str}",
            impact="Potential keeper abuse pattern detected - requires investigation",
            related_event_ids=override_event_ids,
            timeline=timeline,
        )

    async def _create_incident(
        self,
        incident_type: IncidentType,
        title: str,
        cause: str,
        impact: str,
        related_event_ids: list[UUID],
        timeline: list[TimelineEntry] | None = None,
    ) -> IncidentReport:
        """Create an incident report (internal method).

        Args:
            incident_type: Type of incident.
            title: Human-readable title.
            cause: Root cause description.
            impact: Impact assessment.
            related_event_ids: IDs of related constitutional events.
            timeline: Optional initial timeline entries.

        Returns:
            The created IncidentReport.
        """
        log = logger.bind(
            operation="create_incident",
            incident_type=incident_type.value,
            related_events=len(related_event_ids),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "incident_creation_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # Check for duplicate incident (prevent creating multiple for same event)
        if related_event_ids:
            existing = await self._repository.get_by_related_event(related_event_ids[0])
            if existing is not None:
                log.warning(
                    "duplicate_incident_prevented",
                    existing_incident_id=str(existing.incident_id),
                )
                raise DuplicateIncidentError(
                    f"Incident already exists for event {related_event_ids[0]}: "
                    f"incident {existing.incident_id}"
                )

        # =====================================================================
        # Create incident report (FR145)
        # =====================================================================
        incident_id = uuid4()
        now = datetime.now(timezone.utc)

        report = IncidentReport(
            incident_id=incident_id,
            incident_type=incident_type,
            title=title,
            timeline=timeline or [],
            cause=cause,
            impact=impact,
            response="",
            prevention_recommendations=[],
            related_event_ids=related_event_ids,
            created_at=now,
        )

        log = log.bind(incident_id=str(incident_id))

        # =====================================================================
        # Write witnessed event (CT-12)
        # =====================================================================
        payload = IncidentReportCreatedPayload(
            incident_id=incident_id,
            incident_type=incident_type,
            title=title,
            cause=cause,
            impact=impact,
            related_event_ids=related_event_ids,
            created_at=now,
        )

        await self._event_writer.write_event(
            event_type=INCIDENT_REPORT_CREATED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=INCIDENT_SYSTEM_AGENT_ID,
            local_timestamp=now,
        )

        # =====================================================================
        # Save to repository for queries
        # =====================================================================
        await self._repository.save(report)

        log.info(
            "incident_created",
            message="Incident report created and witnessed",
        )

        return report

    async def add_timeline_entry(
        self,
        incident_id: UUID,
        entry: TimelineEntry,
    ) -> IncidentReport:
        """Add a timeline entry to an incident (FR145).

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST
        - FR145: Timeline entries document incident investigation

        Args:
            incident_id: ID of the incident to update.
            entry: The timeline entry to add.

        Returns:
            Updated IncidentReport.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            IncidentNotFoundError: If incident not found.
        """
        log = logger.bind(
            operation="add_timeline_entry",
            incident_id=str(incident_id),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "timeline_update_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        report = await self._repository.get_by_id(incident_id)
        if report is None:
            raise IncidentNotFoundError(f"Incident not found: {incident_id}")

        updated = report.add_timeline_entry(entry)
        await self._repository.save(updated)

        log.info(
            "timeline_entry_added",
            entry_count=len(updated.timeline),
        )

        return updated

    async def resolve_incident(
        self,
        incident_id: UUID,
        response: str,
        recommendations: list[str],
    ) -> IncidentReport:
        """Resolve an incident with response and prevention recommendations (FR145).

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST
        - FR145: Include prevention recommendations
        - FR147: Resolution starts the 7-day publication countdown

        Args:
            incident_id: ID of the incident to resolve.
            response: How the incident was resolved.
            recommendations: Steps to prevent recurrence.

        Returns:
            Updated IncidentReport with PENDING_PUBLICATION status.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            IncidentNotFoundError: If incident not found.
        """
        log = logger.bind(
            operation="resolve_incident",
            incident_id=str(incident_id),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "incident_resolution_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        report = await self._repository.get_by_id(incident_id)
        if report is None:
            raise IncidentNotFoundError(f"Incident not found: {incident_id}")

        resolved_at = datetime.now(timezone.utc)
        updated = report.with_resolution(
            response=response,
            recommendations=recommendations,
            resolved_at=resolved_at,
        )
        await self._repository.save(updated)

        log.info(
            "incident_resolved",
            recommendations_count=len(recommendations),
            publish_eligible_at=updated.publish_eligible_at.isoformat(),
        )

        return updated

    async def publish_incident(
        self,
        incident_id: UUID,
        redacted_fields: list[str] | None = None,
    ) -> IncidentReport:
        """Publish an incident report (FR147, AC4).

        Constitutional Constraints:
        - FR147: Available within 7 days of resolution; redaction only for
                 active security vulnerabilities
        - CT-11: HALT CHECK FIRST
        - CT-12: Publication creates a constitutional event

        Args:
            incident_id: ID of the incident to publish.
            redacted_fields: Optional list of fields to redact for security.

        Returns:
            Updated IncidentReport with PUBLISHED status.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            IncidentNotFoundError: If incident not found.
            IncidentNotResolvedError: If incident not yet resolved.
            PublicationNotEligibleError: If 7 days haven't passed.
        """
        log = logger.bind(
            operation="publish_incident",
            incident_id=str(incident_id),
            redacted_fields=redacted_fields or [],
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "incident_publication_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        report = await self._repository.get_by_id(incident_id)
        if report is None:
            raise IncidentNotFoundError(f"Incident not found: {incident_id}")

        # Check 7-day eligibility (FR147)
        if report.resolution_at is None:
            raise IncidentNotResolvedError(
                f"FR147: Cannot publish unresolved incident {incident_id}"
            )

        if not report.is_publish_eligible():
            raise PublicationNotEligibleError(
                f"FR147: Incident not eligible until {report.publish_eligible_at}"
            )

        now = datetime.now(timezone.utc)

        # Apply redactions if specified
        if redacted_fields:
            report = report.with_redactions(redacted_fields)

        # =====================================================================
        # Write witnessed publication event (CT-12)
        # =====================================================================
        payload = IncidentReportPublishedPayload(
            incident_id=report.incident_id,
            incident_type=report.incident_type,
            content_hash=report.content_hash(),
            redacted_fields=redacted_fields or [],
            published_at=now,
            resolution_at=report.resolution_at,
        )

        await self._event_writer.write_event(
            event_type=INCIDENT_REPORT_PUBLISHED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=INCIDENT_SYSTEM_AGENT_ID,
            local_timestamp=now,
        )

        # Update status to PUBLISHED
        updated = IncidentReport(
            incident_id=report.incident_id,
            incident_type=report.incident_type,
            title=report.title,
            timeline=report.timeline,
            cause=report.cause,
            impact=report.impact,
            response=report.response,
            prevention_recommendations=report.prevention_recommendations,
            related_event_ids=report.related_event_ids,
            created_at=report.created_at,
            resolution_at=report.resolution_at,
            published_at=now,
            redacted_fields=redacted_fields or [],
            status=IncidentStatus.PUBLISHED,
        )
        await self._repository.save(updated)

        log.info(
            "incident_published",
            content_hash=payload.content_hash,
            redacted_count=len(redacted_fields or []),
        )

        return updated

    async def get_incidents_eligible_for_publication(self) -> list[IncidentReport]:
        """Get all incidents eligible for publication (FR147).

        CT-13 compliant: Read operation works during halt.

        Returns:
            List of incidents that can be published (resolved, 7+ days).
        """
        return await self._repository.get_pending_publication()

    async def get_incident_by_id(self, incident_id: UUID) -> IncidentReport | None:
        """Get an incident by ID.

        CT-13 compliant: Read operation works during halt.

        Args:
            incident_id: The incident ID.

        Returns:
            The incident if found, None otherwise.
        """
        return await self._repository.get_by_id(incident_id)

    async def query_incidents(
        self,
        incident_type: IncidentType | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: IncidentStatus | None = None,
    ) -> list[IncidentReport]:
        """Query incidents with filters (AC5).

        CT-13 compliant: Read operation works during halt.

        Args:
            incident_type: Optional filter by type.
            start_date: Optional start date filter.
            end_date: Optional end date filter.
            status: Optional status filter.

        Returns:
            List of matching incidents.
        """
        return await self._repository.query(
            incident_type=incident_type,
            start_date=start_date,
            end_date=end_date,
            status=status,
        )

    async def get_published_incidents(self) -> list[IncidentReport]:
        """Get all published incidents (FR147).

        CT-13 compliant: Read operation works during halt.
        Used for public access to incident reports.

        Returns:
            List of published incidents.
        """
        return await self._repository.get_published()
