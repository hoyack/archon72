"""Recovery waiting period started event payload (Story 3.6, FR21).

This module defines the RecoveryWaitingPeriodStartedPayload for events
created when Keepers initiate the 48-hour recovery waiting period.

Constitutional Constraints:
- FR21: 48-hour waiting period with public notification
- CT-11: Silent failure destroys legitimacy -> Process must be publicly visible
- CT-12: Witnessing creates accountability -> Event must be witnessed

Developer Golden Rules:
1. WITNESS EVERYTHING - Event witnessed BEFORE recovery proceeds
2. FAIL LOUD - All state changes are recorded as events
3. TIME IS CONSTITUTIONAL - 48 hours is a floor, not negotiable
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Event type constant following project naming convention
RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE: str = "recovery.waiting_period_started"


@dataclass(frozen=True, eq=True)
class RecoveryWaitingPeriodStartedPayload:
    """Payload for recovery waiting period started events - immutable.

    Created when Keepers initiate the fork recovery process (AC1).
    This event MUST be witnessed and recorded to ensure the 48-hour
    period is publicly verifiable (FR21).

    Constitutional Constraints:
    - FR21: Mandatory 48-hour waiting period with public notification
    - NFR41: Minimum 48 hours (constitutional floor)
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        crisis_event_id: Reference to the triggering crisis/fork event.
        started_at: When the 48-hour period began (UTC).
        ends_at: When the 48-hour period expires (UTC, always started_at + 48h).
        initiated_by_keepers: Tuple of Keeper IDs who initiated recovery.
        public_notification_sent: Whether observers were notified (FR21).

    Note:
        This event creates the audit trail for recovery initiation.
        The ends_at timestamp allows stakeholders to verify the 48-hour period.
    """

    # Reference to the crisis/fork that triggered recovery
    crisis_event_id: UUID

    # When the 48-hour period began (UTC)
    started_at: datetime

    # When the 48-hour period expires (UTC)
    ends_at: datetime

    # Keeper IDs who initiated the recovery process
    initiated_by_keepers: tuple[str, ...]

    # Whether observers were notified (FR21 requirement)
    public_notification_sent: bool

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability."""
        if isinstance(self.initiated_by_keepers, list):
            object.__setattr__(
                self, "initiated_by_keepers", tuple(self.initiated_by_keepers)
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing.

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": "RecoveryWaitingPeriodStartedEvent",
                "crisis_event_id": str(self.crisis_event_id),
                "started_at": self.started_at.isoformat(),
                "ends_at": self.ends_at.isoformat(),
                "initiated_by_keepers": list(self.initiated_by_keepers),
                "public_notification_sent": self.public_notification_sent,
            },
            sort_keys=True,
        ).encode("utf-8")
