"""Fork detected event payload for constitutional crisis detection (FR16, Story 3.1).

This module defines the ForkDetectedPayload for fork detection events.
A fork is a constitutional crisis - two events claiming the same prev_hash
but with different content_hashes.

Constitutional Constraints:
- FR16: System SHALL continuously monitor for conflicting hashes from same prior state
- CT-11: Silent failure destroys legitimacy -> Fork detection MUST be logged
- CT-12: Witnessing creates accountability -> ForkDetectedEvent must be witnessed
- CT-13: Integrity outranks availability -> Fork triggers halt (Story 3.2)

Note: This story (3.1) handles DETECTION only. Halt logic is in Story 3.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass

# Event type constant for fork detection
FORK_DETECTED_EVENT_TYPE: str = "constitutional.fork_detected"


@dataclass(frozen=True, eq=True)
class ForkDetectedPayload:
    """Payload for fork detection events - immutable.

    A fork occurs when two events claim the same prev_hash but have
    different content_hashes. This is a constitutional crisis that
    requires immediate halt (handled by Story 3.2).

    Constitutional Constraints:
    - FR16: System SHALL continuously monitor for conflicting hashes
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        conflicting_event_ids: UUIDs of the two (or more) conflicting events
        prev_hash: The shared prev_hash that both events claimed
        content_hashes: The different content_hashes of the conflicting events
        detection_timestamp: When the fork was detected (UTC)
        detecting_service_id: ID of the service that detected the fork

    Note:
        The number of content_hashes should match the number of conflicting_event_ids.
        Each content_hash corresponds to one conflicting event.
    """

    # UUIDs of the conflicting events
    conflicting_event_ids: tuple[UUID, ...]

    # The shared prev_hash that caused the fork
    prev_hash: str

    # The different content_hashes of conflicting events
    content_hashes: tuple[str, ...]

    # When the fork was detected (should be UTC)
    detection_timestamp: datetime

    # ID of the detecting service
    detecting_service_id: str

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability and validate."""
        # Convert lists to tuples if necessary (for frozen dataclass compatibility)
        if isinstance(self.conflicting_event_ids, list):
            object.__setattr__(
                self, "conflicting_event_ids", tuple(self.conflicting_event_ids)
            )
        if isinstance(self.content_hashes, list):
            object.__setattr__(self, "content_hashes", tuple(self.content_hashes))

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing (FR84 support).

        Creates deterministic byte representation for cryptographic
        signing and verification. All collections are sorted for
        consistent output regardless of input order.

        Constitutional Constraints:
        - FR84: Fork detection signals MUST be signed
        - CT-12: Witnessing creates accountability

        Returns:
            bytes: Canonical byte representation for signing
        """
        # Sort conflicting event IDs for deterministic output
        sorted_event_ids = sorted(str(uid) for uid in self.conflicting_event_ids)

        # Sort content hashes for deterministic output
        sorted_content_hashes = sorted(self.content_hashes)

        content = (
            f"fork_detected:{self.prev_hash}"
            f":conflicting_events:{','.join(sorted_event_ids)}"
            f":content_hashes:{','.join(sorted_content_hashes)}"
            f":detected:{self.detection_timestamp.isoformat()}"
            f":service:{self.detecting_service_id}"
        )
        return content.encode("utf-8")
