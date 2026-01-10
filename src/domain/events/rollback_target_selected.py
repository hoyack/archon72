"""RollbackTargetSelectedEvent payload (Story 3.10, Task 4, AC2).

This module provides the event payload for when Keepers select a checkpoint
as the rollback target during recovery.

Constitutional Constraints:
- FR143: Rollback to checkpoint logged as constitutional event
- CT-11: Silent failure destroys legitimacy - selection must be witnessed
- CT-12: Witnessing creates accountability - Keeper IDs must be recorded

Usage:
    payload = RollbackTargetSelectedPayload(
        target_checkpoint_id=checkpoint.checkpoint_id,
        target_event_sequence=checkpoint.event_sequence,
        target_anchor_hash=checkpoint.anchor_hash,
        selecting_keepers=("keeper-001", "keeper-002"),
        selection_reason="Fork detected - rolling back to last known good state",
        selection_timestamp=datetime.now(timezone.utc),
    )

    # Create constitutional event with this payload
    event = Event(
        event_type=ROLLBACK_TARGET_SELECTED_EVENT_TYPE,
        payload=payload.signable_content(),
        ...
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

ROLLBACK_TARGET_SELECTED_EVENT_TYPE = "rollback_target_selected"


@dataclass(frozen=True, eq=True)
class RollbackTargetSelectedPayload:
    """Payload for RollbackTargetSelectedEvent (AC2, FR143).

    Records Keepers selecting a checkpoint for rollback. This event
    creates an audit trail of the rollback decision before execution.

    Per CT-11: Selection must be witnessed and logged - no silent decisions.
    Per CT-12: All selecting Keepers are recorded for accountability.

    This is a pure domain value object with no I/O dependencies.
    The payload is immutable (frozen dataclass).

    Attributes:
        target_checkpoint_id: UUID of the selected checkpoint.
        target_event_sequence: Event sequence number at the checkpoint.
        target_anchor_hash: Hash at the checkpoint (SHA-256, 64 chars hex).
        selecting_keepers: Tuple of Keeper IDs who selected this target.
        selection_reason: Human-readable reason for rollback.
        selection_timestamp: When the selection was made (UTC).
    """

    target_checkpoint_id: UUID
    target_event_sequence: int
    target_anchor_hash: str
    selecting_keepers: tuple[str, ...]
    selection_reason: str
    selection_timestamp: datetime

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing.

        Creates deterministic byte representation of the payload
        for cryptographic signing. Includes all fields that define
        the rollback target selection.

        Returns:
            Canonical JSON bytes suitable for signing.
        """
        # Ensure timestamp is in ISO format with UTC
        if self.selection_timestamp.tzinfo is None:
            ts_str = self.selection_timestamp.replace(tzinfo=timezone.utc).isoformat()
        else:
            ts_str = self.selection_timestamp.isoformat()

        # Canonical JSON with sorted keys for deterministic output
        canonical = {
            "target_checkpoint_id": str(self.target_checkpoint_id),
            "target_event_sequence": self.target_event_sequence,
            "target_anchor_hash": self.target_anchor_hash,
            "selecting_keepers": list(self.selecting_keepers),
            "selection_reason": self.selection_reason,
            "selection_timestamp": ts_str,
        }

        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
