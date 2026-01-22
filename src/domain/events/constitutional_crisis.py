"""Constitutional crisis event payload for system halt (FR17, Story 3.2).

This module defines the ConstitutionalCrisisPayload for crisis events.
A constitutional crisis requires immediate system halt - no operations
continue on corrupted state.

Constitutional Constraints:
- FR17: System SHALL halt immediately when single fork detected
- CT-11: Silent failure destroys legitimacy -> Crisis MUST be logged BEFORE halt
- CT-12: Witnessing creates accountability -> ConstitutionalCrisisEvent must be witnessed
- CT-13: Integrity outranks availability -> Availability sacrificed for integrity

Red Team Hardening (RT-2):
- All halt signals must create witnessed halt event BEFORE system stops
- Phantom halts detectable via halt event mismatch analysis
- The crisis event provides audit trail for what triggered halt
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from src.domain._compat import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass

# Event type constant for constitutional crisis
CONSTITUTIONAL_CRISIS_EVENT_TYPE: str = "constitutional.crisis"


class CrisisType(StrEnum):
    """Types of constitutional crises that can trigger system halt.

    This enum is extensible for future crisis types while maintaining
    type safety and clear categorization.

    Constitutional Constraint:
    - Each crisis type maps to a specific constitutional violation
    - New types should be added as new constitutional failure modes are identified
    """

    # Fork detected - two events claiming same prev_hash (FR16, FR17)
    FORK_DETECTED = "fork_detected"

    # Sequence gap detected - missing events in sequence (FR18, FR19, Story 3.7)
    SEQUENCE_GAP_DETECTED = "sequence_gap_detected"

    # Future crisis types can be added here:
    # SIGNATURE_VERIFICATION_FAILED = "signature_verification_failed"
    # HASH_CHAIN_BROKEN = "hash_chain_broken"


@dataclass(frozen=True, eq=True)
class ConstitutionalCrisisPayload:
    """Payload for constitutional crisis events - immutable.

    A constitutional crisis is a critical integrity failure that requires
    immediate system halt. This event MUST be witnessed and recorded
    BEFORE the halt takes effect (RT-2 requirement).

    Constitutional Constraints:
    - FR17: System SHALL halt immediately when crisis detected
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability
    - RT-2: Crisis event recorded BEFORE halt

    Attributes:
        crisis_type: Type of constitutional crisis (e.g., FORK_DETECTED)
        detection_timestamp: When the crisis was detected (UTC)
        detection_details: Human-readable description of the crisis
        triggering_event_ids: UUIDs of events that triggered the crisis
        detecting_service_id: ID of the service that detected the crisis

    Note:
        This event creates the audit trail for halt analysis.
        The triggering_event_ids provide forensic traceability.
    """

    # Type of constitutional crisis
    crisis_type: CrisisType

    # When the crisis was detected (should be UTC)
    detection_timestamp: datetime

    # Human-readable description of the crisis
    detection_details: str

    # UUIDs of events that triggered this crisis
    triggering_event_ids: tuple[UUID, ...]

    # ID of the detecting service
    detecting_service_id: str

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability."""
        # Convert lists to tuples if necessary (for frozen dataclass compatibility)
        if isinstance(self.triggering_event_ids, list):
            object.__setattr__(
                self, "triggering_event_ids", tuple(self.triggering_event_ids)
            )

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing (witnessing support).

        Creates deterministic byte representation of this payload
        for cryptographic signing and verification. Required for
        CT-12 compliance (witnessing creates accountability).

        Returns:
            UTF-8 encoded bytes containing all payload fields
            in canonical format.

        Note:
            The format is deterministic - same payload always produces
            same bytes, enabling signature verification.
        """
        # Sort triggering event IDs for deterministic output
        sorted_event_ids = sorted(str(uid) for uid in self.triggering_event_ids)
        content = (
            f"constitutional_crisis:{self.crisis_type.value}"
            f":detected:{self.detection_timestamp.isoformat()}"
            f":details:{self.detection_details}"
            f":triggering_events:{','.join(sorted_event_ids)}"
            f":service:{self.detecting_service_id}"
        )
        return content.encode("utf-8")
