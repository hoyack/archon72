"""Checkpoint domain model for operational recovery (Story 3.10, FR143).

This module provides the Checkpoint value object representing a checkpoint
anchor in the event store. Checkpoints enable operational rollback without
deleting constitutional history (PREVENT_DELETE).

Constitutional Constraints:
- FR137: Checkpoints are periodic anchors (minimum weekly)
- FR143: Rollback to checkpoint for infrastructure recovery
- FR143: Rollback is logged, does not undo canonical events
- CT-11: Silent failure destroys legitimacy
- PREVENT_DELETE: Events after rollback are marked orphaned, never deleted

Usage:
    checkpoint = Checkpoint(
        checkpoint_id=uuid4(),
        event_sequence=1000,
        timestamp=datetime.now(timezone.utc),
        anchor_hash="abc123...",
        anchor_type="periodic",
        creator_id="checkpoint-service",
    )

    # Get canonical bytes for signing
    content = checkpoint.signable_content()
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass


@dataclass(frozen=True, eq=True)
class Checkpoint:
    """Checkpoint anchor for recovery and verification (FR137, FR143).

    Checkpoints are periodic anchors that provide trusted points for:
    1. Operational recovery (rollback to known-good state)
    2. Observer verification (light verification via Merkle paths)
    3. Audit/compliance snapshots

    Per FR143: Rollback to checkpoint restores infrastructure state,
    not constitutional history. Events after rollback are marked as
    "orphaned" (PREVENT_DELETE), not deleted.

    This is a pure domain value object with no I/O dependencies.
    The model is immutable (frozen dataclass).

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint.
        event_sequence: Event sequence number at checkpoint time.
        timestamp: When checkpoint was created (UTC).
        anchor_hash: Hash of the event chain at this point (SHA-256, 64 chars hex).
        anchor_type: Type of checkpoint ("genesis", "periodic", "manual").
        creator_id: ID of service/operator that created this checkpoint.
    """

    checkpoint_id: UUID
    event_sequence: int
    timestamp: datetime
    anchor_hash: str
    anchor_type: str  # "genesis" | "periodic" | "manual"
    creator_id: str

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing.

        Creates deterministic byte representation of the checkpoint
        for cryptographic signing. The content includes all fields
        that define the checkpoint's identity.

        Returns:
            Canonical JSON bytes suitable for signing.
        """
        # Ensure timestamp is in ISO format with UTC
        if self.timestamp.tzinfo is None:
            ts_str = self.timestamp.replace(tzinfo=timezone.utc).isoformat()
        else:
            ts_str = self.timestamp.isoformat()

        # Canonical JSON with sorted keys for deterministic output
        canonical = {
            "checkpoint_id": str(self.checkpoint_id),
            "event_sequence": self.event_sequence,
            "timestamp": ts_str,
            "anchor_hash": self.anchor_hash,
            "anchor_type": self.anchor_type,
            "creator_id": self.creator_id,
        }

        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
