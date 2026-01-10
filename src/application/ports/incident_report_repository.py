"""Incident Report repository port (Story 8.4, FR54, FR145, FR147).

This module defines the repository interface for storing and querying
incident reports.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable by external parties
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
- CT-11: Silent failure destroys legitimacy -> Query failures must not be silent
- CT-12: Witnessing creates accountability -> All stored incidents were witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Implementations must check halt state before writes
2. WITNESS EVERYTHING - All incident modifications require events
3. FAIL LOUD - Never silently swallow errors
4. READS DURING HALT - Query operations work during halt (CT-13)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from src.domain.models.incident_report import (
    IncidentReport,
    IncidentStatus,
    IncidentType,
)


class IncidentReportRepositoryPort(Protocol):
    """Protocol for incident report storage and retrieval (FR145, FR147).

    This protocol defines the interface for storing incident reports
    and querying with filtering capabilities.

    All implementations must support filtering by:
    - Incident type (halt, fork, override_threshold)
    - Date range
    - Status (draft, pending_publication, published, redacted)
    - Combined filters

    Constitutional Constraints:
    - FR145: Incident reports required for halt, fork, >3 overrides/day
    - FR147: Incident reports SHALL be publicly available within 7 days
    - CT-13: Reads continue during halt (integrity > availability)
    """

    async def save(self, report: IncidentReport) -> None:
        """Save an incident report to storage.

        Constitutional Constraint:
        The incident report creation/modification should be witnessed
        via the EventWriterService before being saved here.

        Args:
            report: The incident report to save.

        Raises:
            IncidentReportSaveError: If save fails.
        """
        ...

    async def get_by_id(self, incident_id: UUID) -> Optional[IncidentReport]:
        """Retrieve a specific incident report by ID.

        Works during halt (CT-13 read access).

        Args:
            incident_id: The unique identifier of the incident.

        Returns:
            The incident report if found, None otherwise.

        Raises:
            IncidentReportQueryError: If query fails.
        """
        ...

    async def get_by_type(self, incident_type: IncidentType) -> list[IncidentReport]:
        """Retrieve incident reports filtered by type (FR145).

        Works during halt (CT-13 read access).

        Args:
            incident_type: The type of incident (halt, fork, override_threshold).

        Returns:
            List of incident reports matching the type, ordered by created_at desc.

        Raises:
            IncidentReportQueryError: If query fails.
        """
        ...

    async def get_pending_publication(self) -> list[IncidentReport]:
        """Retrieve incident reports pending publication (FR147).

        Returns incidents that:
        - Have status PENDING_PUBLICATION
        - Have resolution_at >= 7 days ago

        Works during halt (CT-13 read access).

        Returns:
            List of incident reports eligible for publication.

        Raises:
            IncidentReportQueryError: If query fails.
        """
        ...

    async def get_published(self) -> list[IncidentReport]:
        """Retrieve all published incident reports (FR147).

        Used for public access to incident reports.
        Works during halt (CT-13 read access).

        Returns:
            List of published incident reports, ordered by published_at desc.

        Raises:
            IncidentReportQueryError: If query fails.
        """
        ...

    async def query(
        self,
        incident_type: Optional[IncidentType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[IncidentStatus] = None,
    ) -> list[IncidentReport]:
        """Query incident reports with optional filters (AC: 5).

        Supports flexible querying for incident management.
        Works during halt (CT-13 read access).

        Args:
            incident_type: Optional filter by incident type.
            start_date: Optional filter by created_at >= start_date.
            end_date: Optional filter by created_at <= end_date.
            status: Optional filter by status.

        Returns:
            List of incident reports matching all provided filters,
            ordered by created_at desc.

        Raises:
            IncidentReportQueryError: If query fails.
        """
        ...

    async def get_by_related_event(
        self, event_id: UUID
    ) -> Optional[IncidentReport]:
        """Find incident report by related event ID.

        Prevents duplicate incidents for the same triggering event.
        Works during halt (CT-13 read access).

        Args:
            event_id: The ID of a related constitutional event.

        Returns:
            The incident report if found, None otherwise.

        Raises:
            IncidentReportQueryError: If query fails.
        """
        ...

    async def count_by_type_and_date(
        self,
        incident_type: IncidentType,
        date: datetime,
    ) -> int:
        """Count incidents of a type created on a specific date.

        Useful for checking daily incident limits or patterns.
        Works during halt (CT-13 read access).

        Args:
            incident_type: The type of incident to count.
            date: The date to count (will use date portion only).

        Returns:
            Count of incidents of the type created on that date.

        Raises:
            IncidentReportQueryError: If query fails.
        """
        ...
