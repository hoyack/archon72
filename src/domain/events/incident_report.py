"""Incident Report event payloads (Story 8.4, FR54, FR145, FR147).

This module defines the event payloads for incident reporting capability:
- IncidentReportCreatedPayload: When an incident report is created
- IncidentReportPublishedPayload: When an incident report is published publicly

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable by external parties
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
- CT-11: Silent failure destroys legitimacy → All incident events must be logged
- CT-12: Witnessing creates accountability → All events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating incident events (writes)
2. WITNESS EVERYTHING - All incident events require attribution
3. FAIL LOUD - Never silently swallow event creation errors
4. READS DURING HALT - Incident queries work during halt (CT-13)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.incident_report import IncidentType

# Event type constants for incident report events
INCIDENT_REPORT_CREATED_EVENT_TYPE: str = "incident.report.created"
INCIDENT_REPORT_PUBLISHED_EVENT_TYPE: str = "incident.report.published"

# System agent ID for incident events (automated system, not human agent)
INCIDENT_SYSTEM_AGENT_ID: str = "system.incident_reporting"


@dataclass(frozen=True, eq=True)
class IncidentReportCreatedPayload:
    """Payload for incident report creation events (FR145, AC: 1,2,3).

    An IncidentReportCreatedPayload is created when an incident report
    is created for halt, fork, or >3 overrides/day.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR145: Following halt, fork, or >3 overrides/day: incident report required
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        incident_id: Unique identifier for this incident.
        incident_type: Type of incident (halt, fork, override_threshold).
        title: Human-readable title for the incident.
        cause: Initial root cause description.
        impact: Initial impact assessment.
        related_event_ids: Constitutional event IDs related to this incident.
        created_at: When the incident was created (UTC).
    """

    incident_id: UUID
    incident_type: IncidentType
    title: str
    cause: str
    impact: str
    related_event_ids: list[UUID]
    created_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "cause": self.cause,
            "created_at": self.created_at.isoformat(),
            "impact": self.impact,
            "incident_id": str(self.incident_id),
            "incident_type": self.incident_type.value,
            "related_event_ids": [str(eid) for eid in self.related_event_ids],
            "title": self.title,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "incident_id": str(self.incident_id),
            "incident_type": self.incident_type.value,
            "title": self.title,
            "cause": self.cause,
            "impact": self.impact,
            "related_event_ids": [str(eid) for eid in self.related_event_ids],
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class IncidentReportPublishedPayload:
    """Payload for incident report publication events (FR147, AC: 4).

    An IncidentReportPublishedPayload is created when an incident report
    is published publicly (7+ days after resolution per FR147).

    This event MUST be witnessed (CT-12) and is immutable after creation.
    The content_hash ensures the published content is verifiable.

    Constitutional Constraints:
    - FR147: Incident reports SHALL be publicly available within 7 days
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        incident_id: Reference to the incident being published.
        incident_type: Type of incident (halt, fork, override_threshold).
        content_hash: SHA-256 hash of the incident content.
        redacted_fields: List of fields that were redacted for security.
        published_at: When the incident was published (UTC).
        resolution_at: When the incident was resolved (UTC).
    """

    incident_id: UUID
    incident_type: IncidentType
    content_hash: str
    redacted_fields: list[str]
    published_at: datetime
    resolution_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "content_hash": self.content_hash,
            "incident_id": str(self.incident_id),
            "incident_type": self.incident_type.value,
            "published_at": self.published_at.isoformat(),
            "redacted_fields": self.redacted_fields,
            "resolution_at": self.resolution_at.isoformat(),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "incident_id": str(self.incident_id),
            "incident_type": self.incident_type.value,
            "content_hash": self.content_hash,
            "redacted_fields": self.redacted_fields,
            "published_at": self.published_at.isoformat(),
            "resolution_at": self.resolution_at.isoformat(),
        }
