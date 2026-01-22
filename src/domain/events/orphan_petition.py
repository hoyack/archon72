"""Orphan petition detection events (Story 8.3, FR-8.5).

This module defines events for orphan petition detection - petitions stuck
in RECEIVED state for >24 hours without progressing to deliberation.

Constitutional Constraints:
- FR-8.5: System SHALL identify petitions stuck in RECEIVED state
- NFR-7.1: 100% of orphans must be detected
- CT-12: Witnessing creates accountability -> Events must be witnessed
- CT-11: Silent failure destroys legitimacy -> Orphans must be logged

Developer Golden Rules:
1. WITNESS EVERYTHING - All orphan detection events require witnessing
2. FAIL LOUD - Never silently ignore stuck petitions
3. READS DURING HALT - Detection queries work during halt (CT-13)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Event type constants
ORPHAN_PETITIONS_DETECTED_EVENT_TYPE: str = "petition.monitoring.orphans_detected"
ORPHAN_PETITION_REPROCESSING_TRIGGERED_EVENT_TYPE: str = (
    "petition.monitoring.reprocessing_triggered"
)


@dataclass(frozen=True, eq=True)
class OrphanPetitionsDetectedEventPayload:
    """Payload for orphan petitions detected event (Story 8.3, FR-8.5).

    Emitted when the daily orphan detection job identifies petitions
    stuck in RECEIVED state for >24 hours.

    Constitutional Requirements:
    - FR-8.5: System SHALL identify petitions stuck in RECEIVED
    - NFR-7.1: 100% of orphans must be detected
    - CT-12: Event must be witnessed for accountability

    Attributes:
        detected_at: When the detection job ran (UTC)
        orphan_count: Number of orphaned petitions found
        orphan_petition_ids: List of petition IDs in orphan state
        oldest_orphan_age_hours: Age of the oldest orphan (hours)
        detection_threshold_hours: Threshold used for orphan detection (default: 24)
    """

    detected_at: datetime
    orphan_count: int
    orphan_petition_ids: list[UUID]
    oldest_orphan_age_hours: float
    detection_threshold_hours: float

    def to_json(self) -> str:
        """Serialize to JSON for event storage.

        Returns:
            JSON string representation of this payload.
        """
        return json.dumps(
            {
                "detected_at": self.detected_at.isoformat(),
                "orphan_count": self.orphan_count,
                "orphan_petition_ids": [str(pid) for pid in self.orphan_petition_ids],
                "oldest_orphan_age_hours": self.oldest_orphan_age_hours,
                "detection_threshold_hours": self.detection_threshold_hours,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> OrphanPetitionsDetectedEventPayload:
        """Deserialize from JSON.

        Args:
            json_str: JSON string to deserialize.

        Returns:
            OrphanPetitionsDetectedEventPayload instance.
        """
        data = json.loads(json_str)
        return cls(
            detected_at=datetime.fromisoformat(data["detected_at"]),
            orphan_count=data["orphan_count"],
            orphan_petition_ids=[UUID(pid) for pid in data["orphan_petition_ids"]],
            oldest_orphan_age_hours=data["oldest_orphan_age_hours"],
            detection_threshold_hours=data["detection_threshold_hours"],
        )

    def get_signable_content(self) -> bytes:
        """Get content that should be signed for witnessing (CT-12).

        Returns:
            UTF-8 encoded JSON representation for signing.
        """
        return self.to_json().encode("utf-8")


@dataclass(frozen=True, eq=True)
class OrphanPetitionReprocessingTriggeredEventPayload:
    """Payload for manual orphan reprocessing event (Story 8.3, FR-8.5).

    Emitted when an operator manually triggers re-processing for
    orphaned petitions.

    Constitutional Requirements:
    - CT-12: Event must be witnessed for accountability
    - CT-11: Manual interventions must be logged

    Attributes:
        triggered_at: When reprocessing was triggered (UTC)
        triggered_by: Operator/agent who triggered reprocessing
        petition_ids: List of petition IDs to reprocess
        reason: Reason for manual reprocessing trigger
    """

    triggered_at: datetime
    triggered_by: str
    petition_ids: list[UUID]
    reason: str

    def to_json(self) -> str:
        """Serialize to JSON for event storage.

        Returns:
            JSON string representation of this payload.
        """
        return json.dumps(
            {
                "triggered_at": self.triggered_at.isoformat(),
                "triggered_by": self.triggered_by,
                "petition_ids": [str(pid) for pid in self.petition_ids],
                "reason": self.reason,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> OrphanPetitionReprocessingTriggeredEventPayload:
        """Deserialize from JSON.

        Args:
            json_str: JSON string to deserialize.

        Returns:
            OrphanPetitionReprocessingTriggeredEventPayload instance.
        """
        data = json.loads(json_str)
        return cls(
            triggered_at=datetime.fromisoformat(data["triggered_at"]),
            triggered_by=data["triggered_by"],
            petition_ids=[UUID(pid) for pid in data["petition_ids"]],
            reason=data["reason"],
        )

    def get_signable_content(self) -> bytes:
        """Get content that should be signed for witnessing (CT-12).

        Returns:
            UTF-8 encoded JSON representation for signing.
        """
        return self.to_json().encode("utf-8")
