"""Recovery completed event payload (Story 3.6, FR21, FR22).

This module defines the RecoveryCompletedPayload for events created
when recovery is successfully completed after the 48-hour waiting period.

Constitutional Constraints:
- FR21: 48-hour waiting period must have elapsed
- FR22: Unanimous Keeper agreement required for recovery
- CT-11: Silent failure destroys legitimacy -> Event must be witnessed
- CT-12: Witnessing creates accountability -> Creates audit trail

Developer Golden Rules:
1. WITNESS EVERYTHING - Event witnessed as part of completion
2. CEREMONY IS KING - Recovery requires unanimous Keepers (FR22)
3. TIME IS CONSTITUTIONAL - Can only complete after 48 hours
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Event type constant following project naming convention
RECOVERY_COMPLETED_EVENT_TYPE: str = "recovery.completed"


@dataclass(frozen=True, eq=True)
class RecoveryCompletedPayload:
    """Payload for recovery completed events - immutable.

    Created when Keepers successfully complete recovery after the 48-hour
    waiting period (AC4). This event references the unanimous Keeper
    ceremony that authorized recovery (FR22).

    Constitutional Constraints:
    - FR21: 48-hour waiting period must have elapsed
    - FR22: Unanimous Keeper agreement required
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        crisis_event_id: Reference to the triggering crisis/fork event.
        waiting_period_started_at: When the 48-hour period began (UTC).
        recovery_completed_at: When recovery was completed (UTC).
        keeper_ceremony_id: Reference to the unanimous Keeper ceremony (FR22).
        approving_keepers: Tuple of Keeper IDs who approved recovery.

    Note:
        This event creates the audit trail for recovery completion.
        The keeper_ceremony_id links to the ceremony evidence for verification.
    """

    # Reference to the crisis/fork that triggered recovery
    crisis_event_id: UUID

    # When the 48-hour waiting period began (UTC)
    waiting_period_started_at: datetime

    # When recovery was completed (UTC)
    recovery_completed_at: datetime

    # Reference to the unanimous Keeper ceremony (FR22)
    keeper_ceremony_id: UUID

    # Keeper IDs who approved the recovery
    approving_keepers: tuple[str, ...]

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability."""
        if isinstance(self.approving_keepers, list):
            object.__setattr__(self, "approving_keepers", tuple(self.approving_keepers))

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
                "event_type": "RecoveryCompletedEvent",
                "crisis_event_id": str(self.crisis_event_id),
                "waiting_period_started_at": self.waiting_period_started_at.isoformat(),
                "recovery_completed_at": self.recovery_completed_at.isoformat(),
                "keeper_ceremony_id": str(self.keeper_ceremony_id),
                "approving_keepers": list(self.approving_keepers),
            },
            sort_keys=True,
        ).encode("utf-8")
