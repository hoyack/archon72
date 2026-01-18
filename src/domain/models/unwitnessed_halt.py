"""UnwitnessedHaltRecord domain model (Story 3.9, Task 1).

When a constitutional crisis triggers a halt, we try to write a witnessed
event to the event store BEFORE halting. If that write fails, we still
proceed with halt (CT-13: integrity over availability) but create this
record for later reconciliation.

Constitutional Constraints:
- CT-13: Integrity outranks availability - halt proceeds even if write fails
- RT-2: Unwitnessed halts must be tracked for later reconciliation
- CT-11: Silent failure destroys legitimacy - all failures are recorded
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.constitutional_crisis import ConstitutionalCrisisPayload


@dataclass(frozen=True, eq=True)
class UnwitnessedHaltRecord:
    """Record of halt that couldn't be witnessed in event store.

    When event store write fails during halt, we still proceed with
    halt (CT-13: integrity over availability) but create this record
    for later reconciliation. This ensures no halt goes untracked.

    Constitutional Constraints:
    - CT-13: Integrity outranks availability -> halt proceeds regardless
    - RT-2: All halts must be auditable -> unwitnessed halts tracked here
    - CT-11: Silent failure destroys legitimacy -> failure reason captured

    Attributes:
        halt_id: Unique identifier for this halt event
        crisis_payload: Full ConstitutionalCrisisPayload for reconciliation
        failure_reason: Why the witnessed write failed
        fallback_timestamp: When the halt occurred (fallback ordering)

    Note:
        This record enables manual ceremony to reconcile unwitnessed halts
        into the event store after recovery. The crisis_payload contains
        all the original crisis details for full reconstruction.
    """

    # Unique identifier for this halt
    halt_id: UUID

    # Full crisis payload for later reconciliation
    crisis_payload: ConstitutionalCrisisPayload

    # Reason why witnessed write failed
    failure_reason: str

    # Timestamp when halt occurred (for ordering)
    fallback_timestamp: datetime

    def signable_content(self) -> bytes:
        """Return canonical bytes for later witnessing.

        Creates deterministic byte representation of this record
        for cryptographic signing during reconciliation ceremony.

        Returns:
            UTF-8 encoded bytes in canonical format.

        Note:
            This enables the unwitnessed halt to be witnessed later
            during recovery ceremony. The content includes all fields
            needed for full audit trail reconstruction.
        """
        # Get crisis payload signable content
        crisis_signable = self.crisis_payload.signable_content().decode("utf-8")

        content = (
            f"unwitnessed_halt:{self.halt_id}"
            f":crisis:{crisis_signable}"
            f":failure_reason:{self.failure_reason}"
            f":fallback_timestamp:{self.fallback_timestamp.isoformat()}"
        )
        return content.encode("utf-8")
