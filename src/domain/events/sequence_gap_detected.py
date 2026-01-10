"""Sequence gap detected event payload (FR18-FR19, Story 3.7).

This module defines the SequenceGapDetectedPayload for gap detection events.
A sequence gap indicates potential integrity violation and requires investigation.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-3: Sequence is authoritative ordering
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability

Note:
    Sequence gaps may indicate:
    - Event suppression by attacker
    - Data loss or corruption
    - Replication failure
    - System failure during write

    Gaps are NEVER auto-filled. Manual investigation required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Event type constant for sequence gap detection
# Uses dot notation per project naming convention
SEQUENCE_GAP_DETECTED_EVENT_TYPE: str = "sequence.gap_detected"


@dataclass(frozen=True, eq=True)
class SequenceGapDetectedPayload:
    """Payload for sequence gap detection events (FR18-FR19).

    A sequence gap indicates potential integrity violation.
    This event is witnessed and triggers investigation.

    Constitutional Constraints:
    - FR18: Gap detection within 1 minute
    - FR19: Gap triggers investigation, not auto-fill
    - CT-3: Sequence is authoritative ordering
    - CT-12: Witnessing creates accountability

    Attributes:
        detection_timestamp: When the gap was detected (UTC).
        expected_sequence: The sequence number that was expected.
        actual_sequence: The sequence number that was found.
        gap_size: Number of missing sequences.
        missing_sequences: The actual missing sequence numbers.
        detection_service_id: ID of the detecting service.
        previous_check_timestamp: When last successful check occurred.

    Note:
        This event creates the audit trail for gap investigation.
        The missing_sequences provide forensic traceability.
    """

    # When the gap was detected (should be UTC)
    detection_timestamp: datetime

    # The sequence number that was expected
    expected_sequence: int

    # The sequence number that was found
    actual_sequence: int

    # Number of missing sequences
    gap_size: int

    # The actual missing sequence numbers
    missing_sequences: tuple[int, ...]

    # ID of the detecting service
    detection_service_id: str

    # When last successful check occurred (should be UTC)
    previous_check_timestamp: datetime

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing (witnessing support).

        Creates deterministic byte representation of this payload
        for cryptographic signing and verification.

        Returns:
            UTF-8 encoded bytes containing all payload fields
            in canonical format.

        Note:
            The format is deterministic - same payload always produces
            same bytes, enabling signature verification.
        """
        content = (
            f"gap_detected:{self.detection_timestamp.isoformat()}"
            f":expected:{self.expected_sequence}"
            f":actual:{self.actual_sequence}"
            f":gap_size:{self.gap_size}"
            f":missing:{','.join(str(s) for s in self.missing_sequences)}"
            f":service:{self.detection_service_id}"
            f":previous_check:{self.previous_check_timestamp.isoformat()}"
        )
        return content.encode("utf-8")
