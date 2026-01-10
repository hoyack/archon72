"""Cessation event payloads (Story 6.3, FR32).

This module defines event payloads for automatic cessation consideration:
- CessationConsiderationEventPayload: When >10 unacknowledged breaches in 90 days
- CessationDecisionEventPayload: Conclave decision on cessation consideration
- CessationDecision: Decision choices enum

Constitutional Constraints:
- FR32: >10 unacknowledged breaches in 90 days SHALL trigger cessation consideration
- CT-11: Silent failure destroys legitimacy -> All cessation events must be logged
- CT-12: Witnessing creates accountability -> All cessation events MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating cessation events
2. WITNESS EVERYTHING - All cessation events must be witnessed
3. FAIL LOUD - Never silently swallow cessation detection
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

# Event type constants for cessation
CESSATION_CONSIDERATION_EVENT_TYPE: str = "cessation.consideration"
CESSATION_DECISION_EVENT_TYPE: str = "cessation.decision"


class CessationDecision(str, Enum):
    """Decision choices for cessation consideration review (FR32).

    After the Conclave reviews a cessation consideration, one of these
    decisions must be recorded.

    Constitutional Constraint (FR32):
    Each decision must be witnessed and logged with attribution.
    """

    PROCEED_TO_VOTE = "proceed_to_vote"
    """Move to formal cessation vote - situation is severe enough to warrant vote."""

    DISMISS_CONSIDERATION = "dismiss"
    """Dismiss consideration - breaches addressed or false positives identified."""

    DEFER_REVIEW = "defer"
    """Defer to next Conclave session for further deliberation."""


@dataclass(frozen=True, eq=True)
class CessationConsiderationEventPayload:
    """Payload for cessation consideration trigger (FR32).

    A CessationConsiderationEventPayload is created when >10 unacknowledged
    breaches occur in a 90-day rolling window. This automatically places
    cessation on the Conclave agenda.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR32: >10 unacknowledged breaches in 90 days SHALL trigger cessation consideration
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: Integrity outranks availability

    Attributes:
        consideration_id: Unique identifier for this consideration event.
        trigger_timestamp: When the consideration was triggered (UTC).
        breach_count: Number of unacknowledged breaches that triggered consideration.
        window_days: Rolling window size (always 90 per FR32).
        unacknowledged_breach_ids: References to specific breaches in the window.
        agenda_placement_reason: Reason for placing on agenda.
    """

    consideration_id: UUID
    trigger_timestamp: datetime
    breach_count: int
    window_days: int
    unacknowledged_breach_ids: tuple[UUID, ...]
    agenda_placement_reason: str

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
            "breach_count": self.breach_count,
            "consideration_id": str(self.consideration_id),
            "trigger_timestamp": self.trigger_timestamp.isoformat(),
            "unacknowledged_breach_ids": [
                str(bid) for bid in self.unacknowledged_breach_ids
            ],
            "window_days": self.window_days,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "consideration_id": str(self.consideration_id),
            "trigger_timestamp": self.trigger_timestamp.isoformat(),
            "breach_count": self.breach_count,
            "window_days": self.window_days,
            "unacknowledged_breach_ids": [
                str(bid) for bid in self.unacknowledged_breach_ids
            ],
            "agenda_placement_reason": self.agenda_placement_reason,
        }


@dataclass(frozen=True, eq=True)
class CessationDecisionEventPayload:
    """Payload for cessation decision events (FR32).

    A CessationDecisionEventPayload is created when the Conclave makes
    a decision on a cessation consideration.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR32: Decision must be recorded for every consideration
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        decision_id: Unique identifier for this decision event.
        consideration_id: Reference to the consideration being decided.
        decision: The decision choice (PROCEED_TO_VOTE, DISMISS, DEFER).
        decision_timestamp: When the decision was made (UTC).
        decided_by: Attribution of decision maker (e.g., "Conclave Session 42").
        rationale: Reason for the decision.
    """

    decision_id: UUID
    consideration_id: UUID
    decision: CessationDecision
    decision_timestamp: datetime
    decided_by: str
    rationale: str

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
            "consideration_id": str(self.consideration_id),
            "decided_by": self.decided_by,
            "decision": self.decision.value,
            "decision_id": str(self.decision_id),
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "rationale": self.rationale,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "decision_id": str(self.decision_id),
            "consideration_id": str(self.consideration_id),
            "decision": self.decision.value,
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "decided_by": self.decided_by,
            "rationale": self.rationale,
        }
