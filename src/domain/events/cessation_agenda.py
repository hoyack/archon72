"""Cessation agenda placement event payloads (Story 7.1, FR37-FR38, RT-4).

This module defines the event payload for automatic cessation agenda placement:
- CessationAgendaPlacementEventPayload: When integrity triggers are detected
- AgendaTriggerType: Types of triggers (consecutive failures, rolling window, anti-success)

Triggers:
1. FR37: 3 consecutive integrity failures in 30 days
2. RT-4: 5 non-consecutive failures in any 90-day rolling window (timing attack prevention)
3. FR38: Anti-success alert sustained 90 days

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> All agenda events must be logged
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating agenda events
2. WITNESS EVERYTHING - All agenda events must be witnessed
3. FAIL LOUD - Never silently swallow trigger detection
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

# Event type constant for cessation agenda placement
CESSATION_AGENDA_PLACEMENT_EVENT_TYPE: str = "cessation.agenda_placement"


class AgendaTriggerType(str, Enum):
    """Types of automatic agenda placement triggers (FR37-FR38, RT-4).

    Each trigger type represents a different pattern that causes
    cessation to be placed on the Conclave agenda.

    Constitutional Constraint:
    Each trigger type must be witnessed and logged with attribution.
    """

    CONSECUTIVE_FAILURES = "consecutive_failures"
    """FR37: 3 consecutive integrity failures in 30 days."""

    ROLLING_WINDOW = "rolling_window"
    """RT-4: 5 non-consecutive failures in any 90-day rolling window."""

    ANTI_SUCCESS_SUSTAINED = "anti_success_sustained"
    """FR38: Anti-success alert sustained for 90 days."""


@dataclass(frozen=True, eq=True)
class CessationAgendaPlacementEventPayload:
    """Payload for cessation agenda placement events (FR37-FR38, RT-4).

    A CessationAgendaPlacementEventPayload is created when any of these
    triggers are detected:
    - FR37: 3 consecutive integrity failures in 30 days
    - RT-4: 5 non-consecutive failures in 90-day rolling window
    - FR38: Anti-success alert sustained 90 days

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR37: 3 consecutive failures in 30 days SHALL trigger agenda placement
    - FR38: Anti-success alert sustained 90 days SHALL trigger agenda placement
    - RT-4: 5 failures in 90-day window prevents timing attack exploitation
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: Integrity outranks availability

    Attributes:
        placement_id: Unique identifier for this agenda placement event.
        trigger_type: The type of trigger that caused agenda placement.
        trigger_timestamp: When the trigger was detected (UTC).
        failure_count: Number of integrity failures (for failure-based triggers).
        window_days: Rolling window size in days.
        consecutive: Whether failures were consecutive (FR37 vs RT-4).
        failure_event_ids: References to triggering failure events.
        agenda_placement_reason: Human-readable reason for placement.
        sustained_days: Days the alert was sustained (for anti-success trigger).
        first_alert_date: When the sustained alert period began.
        alert_event_ids: References to alert events (for anti-success trigger).
    """

    placement_id: UUID
    trigger_type: AgendaTriggerType
    trigger_timestamp: datetime
    failure_count: int
    window_days: int
    consecutive: bool
    failure_event_ids: tuple[UUID, ...]
    agenda_placement_reason: str

    # Optional fields for anti-success sustained trigger (FR38)
    sustained_days: Optional[int] = field(default=None)
    first_alert_date: Optional[datetime] = field(default=None)
    alert_event_ids: tuple[UUID, ...] = field(default_factory=tuple)

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
            "agenda_placement_reason": self.agenda_placement_reason,
            "consecutive": self.consecutive,
            "failure_count": self.failure_count,
            "failure_event_ids": [str(fid) for fid in self.failure_event_ids],
            "placement_id": str(self.placement_id),
            "trigger_timestamp": self.trigger_timestamp.isoformat(),
            "trigger_type": self.trigger_type.value,
            "window_days": self.window_days,
        }

        # Include optional fields if present (for anti-success trigger)
        if self.sustained_days is not None:
            content["sustained_days"] = self.sustained_days
        if self.first_alert_date is not None:
            content["first_alert_date"] = self.first_alert_date.isoformat()
        if self.alert_event_ids:
            content["alert_event_ids"] = [str(aid) for aid in self.alert_event_ids]

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        result: dict[str, Any] = {
            "placement_id": str(self.placement_id),
            "trigger_type": self.trigger_type.value,
            "trigger_timestamp": self.trigger_timestamp.isoformat(),
            "failure_count": self.failure_count,
            "window_days": self.window_days,
            "consecutive": self.consecutive,
            "failure_event_ids": [str(fid) for fid in self.failure_event_ids],
            "agenda_placement_reason": self.agenda_placement_reason,
        }

        # Include optional fields if present (for anti-success trigger)
        if self.sustained_days is not None:
            result["sustained_days"] = self.sustained_days
        if self.first_alert_date is not None:
            result["first_alert_date"] = self.first_alert_date.isoformat()
        if self.alert_event_ids:
            result["alert_event_ids"] = [str(aid) for aid in self.alert_event_ids]

        return result
