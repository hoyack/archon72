"""Incident Report repository stub implementation (Story 8.4, FR54, FR145, FR147).

This module provides an in-memory stub implementation of IncidentReportRepositoryPort
for testing and development purposes.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable by external parties
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.incident_report_repository import (
    IncidentReportRepositoryPort,
)
from src.domain.models.incident_report import (
    IncidentReport,
    IncidentStatus,
    IncidentType,
)


class IncidentReportRepositoryStub(IncidentReportRepositoryPort):
    """In-memory stub for incident report storage (testing only).

    This stub provides an in-memory implementation of IncidentReportRepositoryPort
    suitable for unit and integration tests.

    The stub stores incident reports in a dictionary keyed by incident_id.
    All query operations iterate over the stored reports.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._reports: dict[UUID, IncidentReport] = {}
        self._event_index: dict[UUID, UUID] = {}  # event_id -> incident_id

    def clear(self) -> None:
        """Clear all stored reports (for test cleanup)."""
        self._reports.clear()
        self._event_index.clear()

    async def save(self, report: IncidentReport) -> None:
        """Save an incident report to storage.

        Args:
            report: The incident report to save.
        """
        self._reports[report.incident_id] = report
        # Index related events for fast lookup
        for event_id in report.related_event_ids:
            self._event_index[event_id] = report.incident_id

    async def get_by_id(self, incident_id: UUID) -> IncidentReport | None:
        """Retrieve a specific incident report by ID.

        Args:
            incident_id: The unique identifier of the incident.

        Returns:
            The incident report if found, None otherwise.
        """
        return self._reports.get(incident_id)

    async def get_by_type(self, incident_type: IncidentType) -> list[IncidentReport]:
        """Retrieve incident reports filtered by type (FR145).

        Args:
            incident_type: The type of incident (halt, fork, override_threshold).

        Returns:
            List of incident reports matching the type, ordered by created_at desc.
        """
        filtered = [
            r for r in self._reports.values() if r.incident_type == incident_type
        ]
        return sorted(filtered, key=lambda r: r.created_at, reverse=True)

    async def get_pending_publication(self) -> list[IncidentReport]:
        """Retrieve incident reports pending publication (FR147).

        Returns incidents that:
        - Have status PENDING_PUBLICATION
        - Have resolution_at set
        - 7+ days have passed since creation

        Returns:
            List of incident reports eligible for publication.
        """
        now = datetime.now(timezone.utc)
        filtered = [
            r
            for r in self._reports.values()
            if r.status == IncidentStatus.PENDING_PUBLICATION
            and r.resolution_at is not None
            and now >= r.publish_eligible_at
        ]
        return sorted(filtered, key=lambda r: r.created_at, reverse=True)

    async def get_published(self) -> list[IncidentReport]:
        """Retrieve all published incident reports (FR147).

        Returns:
            List of published incident reports, ordered by published_at desc.
        """
        filtered = [
            r for r in self._reports.values() if r.status == IncidentStatus.PUBLISHED
        ]
        return sorted(
            filtered,
            key=lambda r: r.published_at or r.created_at,
            reverse=True,
        )

    async def query(
        self,
        incident_type: IncidentType | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: IncidentStatus | None = None,
    ) -> list[IncidentReport]:
        """Query incident reports with optional filters (AC: 5).

        Args:
            incident_type: Optional filter by incident type.
            start_date: Optional filter by created_at >= start_date.
            end_date: Optional filter by created_at <= end_date.
            status: Optional filter by status.

        Returns:
            List of incident reports matching all provided filters,
            ordered by created_at desc.
        """
        results = list(self._reports.values())

        if incident_type is not None:
            results = [r for r in results if r.incident_type == incident_type]

        if start_date is not None:
            results = [r for r in results if r.created_at >= start_date]

        if end_date is not None:
            results = [r for r in results if r.created_at <= end_date]

        if status is not None:
            results = [r for r in results if r.status == status]

        return sorted(results, key=lambda r: r.created_at, reverse=True)

    async def get_by_related_event(self, event_id: UUID) -> IncidentReport | None:
        """Find incident report by related event ID.

        Prevents duplicate incidents for the same triggering event.

        Args:
            event_id: The ID of a related constitutional event.

        Returns:
            The incident report if found, None otherwise.
        """
        incident_id = self._event_index.get(event_id)
        if incident_id is None:
            return None
        return self._reports.get(incident_id)

    async def count_by_type_and_date(
        self,
        incident_type: IncidentType,
        date: datetime,
    ) -> int:
        """Count incidents of a type created on a specific date.

        Args:
            incident_type: The type of incident to count.
            date: The date to count (will use date portion only).

        Returns:
            Count of incidents of the type created on that date.
        """
        target_date = date.date()
        count = sum(
            1
            for r in self._reports.values()
            if r.incident_type == incident_type and r.created_at.date() == target_date
        )
        return count

    # Test helper methods (not part of protocol)

    def get_report_count(self) -> int:
        """Get total number of stored reports."""
        return len(self._reports)

    def get_all_reports(self) -> list[IncidentReport]:
        """Get all stored reports (for test verification)."""
        return list(self._reports.values())
