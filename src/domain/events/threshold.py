"""Threshold events for Archon 72 (Story 6.4, FR33-FR34).

This module provides event payloads for threshold-related events.

Constitutional Constraints:
- CT-12: Witnessing creates accountability → Threshold changes must be witnessed
- FR34: Threshold changes SHALL NOT reset active counters
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

THRESHOLD_UPDATED_EVENT_TYPE = "threshold.updated"
"""Event type constant for threshold updates."""


@dataclass(frozen=True)
class ThresholdUpdatedEventPayload:
    """Payload for threshold update events.

    Records when a constitutional threshold is modified, providing
    full audit trail for accountability (CT-12).

    Attributes:
        threshold_name: Name of the threshold that was updated.
        previous_value: The value before the update.
        new_value: The value after the update.
        constitutional_floor: The floor that was enforced.
        fr_reference: FR reference for the threshold.
        updated_at: When the update occurred.
        updated_by: Agent/Keeper ID who made the update.
    """

    threshold_name: str
    previous_value: int | float
    new_value: int | float
    constitutional_floor: int | float
    fr_reference: str
    updated_at: datetime
    updated_by: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for event writing.

        Returns:
            Dictionary with all payload fields.
            Note: Returns dict, not bytes.
        """
        return {
            "threshold_name": self.threshold_name,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "constitutional_floor": self.constitutional_floor,
            "fr_reference": self.fr_reference,
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
        }

    def signable_content(self) -> bytes:
        """Generate deterministic signable content for witnessing (CT-12).

        Returns:
            Bytes representation suitable for cryptographic signing.
            Content is deterministic for the same payload values.
        """
        # Create deterministic JSON representation
        content = {
            "threshold_name": self.threshold_name,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "constitutional_floor": self.constitutional_floor,
            "fr_reference": self.fr_reference,
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
        }
        # Sort keys for determinism
        json_bytes = json.dumps(content, sort_keys=True).encode("utf-8")
        return json_bytes

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex string of the SHA-256 hash.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()
