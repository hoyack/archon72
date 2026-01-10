"""Halt cleared event payload for ceremony-based halt clearing (Story 3.4, ADR-3).

This module defines the HaltClearedPayload for halt clear events.
Halt clearing requires a witnessed ceremony with at least 2 Keeper approvers.

Constitutional Constraints:
- ADR-3: Halt is sticky - clearing requires witnessed ceremony
- ADR-6: Halt clearing is Tier 1 ceremony (2 Keepers required)
- CT-11: Silent failure destroys legitimacy -> Clear MUST be logged BEFORE taking effect
- CT-12: Witnessing creates accountability -> HaltClearedEvent must be witnessed

Developer Golden Rules:
1. CEREMONY IS KING - No backdoors, no exceptions
2. WITNESS EVERYTHING - Event witnessed BEFORE clear takes effect
3. FAIL LOUD - Unauthorized clear attempts raise immediately
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass

# Event type constant for halt cleared
HALT_CLEARED_EVENT_TYPE: str = "halt.cleared"


@dataclass(frozen=True, eq=True)
class HaltClearedPayload:
    """Payload for halt cleared events - immutable.

    A HaltClearedEvent is created when a halt clear ceremony completes
    successfully. This event MUST be witnessed and recorded BEFORE
    the halt is actually cleared (ADR-3 requirement).

    Constitutional Constraints:
    - ADR-3: Halt is sticky, clearing requires witnessed ceremony
    - ADR-6: Tier 1 ceremony requires 2 Keepers
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        ceremony_id: UUID of the clearing ceremony.
        clearing_authority: Who authorized the clear (e.g., "Keeper Council").
        reason: Human-readable reason for clearing halt.
        approvers: Tuple of Keeper IDs who approved the clear (>= 2 per ADR-6).
        cleared_at: When the clear was authorized (UTC).

    Note:
        This event creates the audit trail for halt clearing.
        The ceremony_id links back to the ceremony evidence.
    """

    # UUID of the clearing ceremony
    ceremony_id: UUID

    # Who authorized the clear
    clearing_authority: str

    # Human-readable reason for clearing halt
    reason: str

    # Keeper IDs who approved the clear (>= 2 per ADR-6 Tier 1)
    approvers: tuple[str, ...]

    # When the clear was authorized (should be UTC)
    cleared_at: datetime

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability."""
        # Convert lists to tuples if necessary (for frozen dataclass compatibility)
        if isinstance(self.approvers, list):
            object.__setattr__(self, "approvers", tuple(self.approvers))

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
                "event_type": "HaltClearedEvent",
                "ceremony_id": str(self.ceremony_id),
                "clearing_authority": self.clearing_authority,
                "reason": self.reason,
                "approvers": list(self.approvers),
                "cleared_at": self.cleared_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
