"""Incident Report domain models (Story 8.4, FR54, FR145, FR147).

This module defines the domain models for incident reporting:
- IncidentReport: Main incident entity with timeline and resolution tracking
- IncidentType: Type of incident (halt, fork, override threshold)
- IncidentStatus: Status of the incident (draft, pending_publication, published, redacted)
- TimelineEntry: Individual event in an incident timeline

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable by external parties
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
- CT-11: Silent failure destroys legitimacy → All incidents must be tracked
- CT-12: Witnessing creates accountability → All significant events documented

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before modifying incidents (writes)
2. WITNESS EVERYTHING - All incident events require attribution
3. FAIL LOUD - Never silently swallow incident creation errors
4. READS DURING HALT - Incident queries work during halt (CT-13)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import UUID


# Constants per FR145 and FR147
PUBLICATION_DELAY_DAYS: int = 7  # FR147: 7 days before publication
DAILY_OVERRIDE_THRESHOLD: int = 3  # FR145: >3 overrides/day triggers incident


class IncidentType(Enum):
    """Types of incidents that trigger incident reports (FR145).

    Constitutional Constraint (FR145):
    Following halt, fork, or >3 overrides/day: incident report with timeline,
    root cause, contributing factors, prevention recommendations.
    """

    HALT = "halt"
    FORK = "fork"
    OVERRIDE_THRESHOLD = "override_threshold"


class IncidentStatus(Enum):
    """Status of an incident report (FR147).

    Constitutional Constraint (FR147):
    Incident reports SHALL be publicly available within 7 days of resolution;
    redaction only for active security vulnerabilities.
    """

    DRAFT = "draft"
    PENDING_PUBLICATION = "pending_publication"
    PUBLISHED = "published"
    REDACTED = "redacted"


@dataclass(frozen=True, eq=True)
class TimelineEntry:
    """A single entry in an incident timeline (FR145, AC: 1,2,3).

    Represents a significant event during an incident, with optional
    linkage to constitutional events.

    Constitutional Constraint (FR145):
    Incident report with timeline... root cause, contributing factors.

    Attributes:
        timestamp: When this event occurred (UTC).
        description: Human-readable description of the event.
        event_id: Optional link to a constitutional event ID.
        actor: Optional attribution (who/what triggered this event).
    """

    timestamp: datetime
    description: str
    event_id: Optional[UUID] = None
    actor: Optional[str] = None


@dataclass(frozen=True, eq=True)
class IncidentReport:
    """An incident report for halt, fork, or override threshold events (FR54, FR145, FR147).

    Incidents are OPERATIONAL artifacts (mutable, with status) that become
    CONSTITUTIONAL when published (immutable event with content hash).

    Constitutional Constraints:
    - FR54: No Silent Failures -> Incidents ensure significant events are documented
    - FR145: Following halt, fork, or >3 overrides/day: incident report required
    - FR147: Incident reports SHALL be publicly available within 7 days of resolution
    - CT-11: Silent failure destroys legitimacy -> Must track all incidents
    - CT-12: Witnessing creates accountability -> All significant events documented

    Attributes:
        incident_id: Unique identifier for this incident.
        incident_type: Type of incident (halt, fork, override_threshold).
        title: Human-readable title for the incident.
        timeline: Chronological list of events during the incident.
        cause: Root cause analysis.
        impact: Description of the impact.
        response: How the incident was resolved (empty until resolved).
        prevention_recommendations: Steps to prevent recurrence.
        related_event_ids: Links to constitutional events involved.
        created_at: When the incident was created (UTC).
        resolution_at: When the incident was resolved (UTC), or None.
        published_at: When the incident was published (UTC), or None.
        redacted_fields: List of field names that have been redacted.
        status: Current status of the incident.
    """

    incident_id: UUID
    incident_type: IncidentType
    title: str
    timeline: list[TimelineEntry]
    cause: str
    impact: str
    response: str
    prevention_recommendations: list[str]
    related_event_ids: list[UUID]
    created_at: datetime
    resolution_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    redacted_fields: list[str] = field(default_factory=list)
    status: IncidentStatus = IncidentStatus.DRAFT

    @property
    def publish_eligible_at(self) -> datetime:
        """Calculate when this incident is eligible for publication.

        Per FR147, incidents are eligible for publication 7 days after creation.

        Returns:
            Datetime when incident can be published.
        """
        return self.created_at + timedelta(days=PUBLICATION_DELAY_DAYS)

    def is_publish_eligible(self) -> bool:
        """Check if this incident is eligible for publication.

        Per FR147, incidents must be resolved AND 7 days must have passed.

        Returns:
            True if the incident can be published, False otherwise.
        """
        if self.resolution_at is None:
            return False

        now = datetime.now(timezone.utc)
        return now >= self.publish_eligible_at

    def with_status(self, status: IncidentStatus) -> IncidentReport:
        """Create a new IncidentReport with updated status.

        Since IncidentReport is frozen, this returns a new instance.

        Args:
            status: The new status.

        Returns:
            New IncidentReport instance with the updated status.
        """
        return IncidentReport(
            incident_id=self.incident_id,
            incident_type=self.incident_type,
            title=self.title,
            timeline=self.timeline,
            cause=self.cause,
            impact=self.impact,
            response=self.response,
            prevention_recommendations=self.prevention_recommendations,
            related_event_ids=self.related_event_ids,
            created_at=self.created_at,
            resolution_at=self.resolution_at,
            published_at=self.published_at,
            redacted_fields=self.redacted_fields,
            status=status,
        )

    def with_resolution(
        self,
        response: str,
        recommendations: list[str],
        resolved_at: datetime,
    ) -> IncidentReport:
        """Create a new IncidentReport marked as resolved.

        Since IncidentReport is frozen, this returns a new instance
        with resolution details and PENDING_PUBLICATION status.

        Args:
            response: How the incident was resolved.
            recommendations: Prevention recommendations.
            resolved_at: When the incident was resolved (UTC).

        Returns:
            New IncidentReport instance with resolution details.
        """
        return IncidentReport(
            incident_id=self.incident_id,
            incident_type=self.incident_type,
            title=self.title,
            timeline=self.timeline,
            cause=self.cause,
            impact=self.impact,
            response=response,
            prevention_recommendations=recommendations,
            related_event_ids=self.related_event_ids,
            created_at=self.created_at,
            resolution_at=resolved_at,
            published_at=self.published_at,
            redacted_fields=self.redacted_fields,
            status=IncidentStatus.PENDING_PUBLICATION,
        )

    def with_redactions(self, redacted_fields: list[str]) -> IncidentReport:
        """Create a new IncidentReport with specified field redactions.

        Per FR147, redaction only for active security vulnerabilities.

        Since IncidentReport is frozen, this returns a new instance.

        Args:
            redacted_fields: List of field names to mark as redacted.

        Returns:
            New IncidentReport instance with redacted fields noted.
        """
        return IncidentReport(
            incident_id=self.incident_id,
            incident_type=self.incident_type,
            title=self.title,
            timeline=self.timeline,
            cause=self.cause,
            impact=self.impact,
            response=self.response,
            prevention_recommendations=self.prevention_recommendations,
            related_event_ids=self.related_event_ids,
            created_at=self.created_at,
            resolution_at=self.resolution_at,
            published_at=self.published_at,
            redacted_fields=redacted_fields,
            status=self.status,
        )

    def add_timeline_entry(self, entry: TimelineEntry) -> IncidentReport:
        """Create a new IncidentReport with an additional timeline entry.

        Since IncidentReport is frozen, this returns a new instance
        with the timeline entry appended.

        Args:
            entry: The timeline entry to add.

        Returns:
            New IncidentReport instance with the entry added.
        """
        return IncidentReport(
            incident_id=self.incident_id,
            incident_type=self.incident_type,
            title=self.title,
            timeline=self.timeline + [entry],
            cause=self.cause,
            impact=self.impact,
            response=self.response,
            prevention_recommendations=self.prevention_recommendations,
            related_event_ids=self.related_event_ids,
            created_at=self.created_at,
            resolution_at=self.resolution_at,
            published_at=self.published_at,
            redacted_fields=self.redacted_fields,
            status=self.status,
        )

    def content_hash(self) -> str:
        """Generate SHA-256 hash of incident content for verification.

        Used when publishing incident reports to create an immutable
        record of the content (CT-12).

        Returns:
            Hex-encoded SHA-256 hash of the incident content.
        """
        # Create canonical JSON representation
        content = {
            "incident_id": str(self.incident_id),
            "incident_type": self.incident_type.value,
            "title": self.title,
            "timeline": [
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "description": entry.description,
                    "event_id": str(entry.event_id) if entry.event_id else None,
                    "actor": entry.actor,
                }
                for entry in self.timeline
            ],
            "cause": self.cause,
            "impact": self.impact,
            "response": self.response,
            "prevention_recommendations": self.prevention_recommendations,
            "related_event_ids": [str(eid) for eid in self.related_event_ids],
            "created_at": self.created_at.isoformat(),
            "resolution_at": self.resolution_at.isoformat() if self.resolution_at else None,
            "redacted_fields": self.redacted_fields,
        }
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
