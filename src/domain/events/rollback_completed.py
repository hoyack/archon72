"""RollbackCompletedEvent payload (Story 3.10, Task 5, AC3).

This module provides the event payload for successful rollback completion.
The event records the outcome of a rollback operation.

Constitutional Constraints:
- FR143: Rollback logged as constitutional event
- CT-11: Rollback must be witnessed - this event provides the audit trail
- PREVENT_DELETE: Events are orphaned, not deleted - recorded in payload

Usage:
    payload = RollbackCompletedPayload(
        target_checkpoint_id=checkpoint.checkpoint_id,
        previous_head_sequence=1000,
        new_head_sequence=500,
        orphaned_event_count=500,
        orphaned_sequence_range=(501, 1001),
        rollback_timestamp=datetime.now(timezone.utc),
        ceremony_id=ceremony.id,
        approving_keepers=("keeper-001", "keeper-002"),
    )

    # Create constitutional event with this payload
    event = Event(
        event_type=ROLLBACK_COMPLETED_EVENT_TYPE,
        payload=payload.signable_content(),
        ...
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

ROLLBACK_COMPLETED_EVENT_TYPE = "rollback_completed"


@dataclass(frozen=True, eq=True)
class RollbackCompletedPayload:
    """Payload for RollbackCompletedEvent (AC3, FR143).

    Records successful rollback to a checkpoint. This event creates
    an audit trail of the rollback operation and its outcome.

    Per PREVENT_DELETE: Events after checkpoint are marked as orphaned,
    never deleted. The orphaned_event_count and orphaned_sequence_range
    record exactly which events were affected.

    Per CT-11: This event must be witnessed to maintain legitimacy.

    This is a pure domain value object with no I/O dependencies.
    The payload is immutable (frozen dataclass).

    Attributes:
        target_checkpoint_id: UUID of the checkpoint rolled back to.
        previous_head_sequence: HEAD sequence before rollback.
        new_head_sequence: HEAD sequence after rollback (= checkpoint sequence).
        orphaned_event_count: Number of events marked as orphaned.
        orphaned_sequence_range: (start, end) range of orphaned sequences (exclusive end).
        rollback_timestamp: When the rollback was executed (UTC).
        ceremony_id: UUID of the Keeper ceremony that authorized rollback.
        approving_keepers: Tuple of Keeper IDs who approved the rollback.
    """

    target_checkpoint_id: UUID
    previous_head_sequence: int
    new_head_sequence: int
    orphaned_event_count: int
    orphaned_sequence_range: tuple[int, int]  # (start, end) exclusive end
    rollback_timestamp: datetime
    ceremony_id: UUID
    approving_keepers: tuple[str, ...]

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing.

        Creates deterministic byte representation of the payload
        for cryptographic signing. Includes all fields that define
        the rollback outcome.

        Returns:
            Canonical JSON bytes suitable for signing.
        """
        # Ensure timestamp is in ISO format with UTC
        if self.rollback_timestamp.tzinfo is None:
            ts_str = self.rollback_timestamp.replace(tzinfo=timezone.utc).isoformat()
        else:
            ts_str = self.rollback_timestamp.isoformat()

        # Canonical JSON with sorted keys for deterministic output
        canonical = {
            "target_checkpoint_id": str(self.target_checkpoint_id),
            "previous_head_sequence": self.previous_head_sequence,
            "new_head_sequence": self.new_head_sequence,
            "orphaned_event_count": self.orphaned_event_count,
            "orphaned_sequence_range": list(self.orphaned_sequence_range),
            "rollback_timestamp": ts_str,
            "ceremony_id": str(self.ceremony_id),
            "approving_keepers": list(self.approving_keepers),
        }

        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
