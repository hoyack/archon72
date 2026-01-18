"""Hash verification event payloads (Story 6.8, FR125).

This module defines event payloads for continuous hash verification:
- HashVerificationBreachEventPayload: When a hash mismatch is detected
- HashVerificationCompletedEventPayload: When a verification scan completes

Constitutional Constraints:
- FR125: Witness selection algorithm SHALL be published; statistical deviation
         from expected distribution flagged (Selection Audit)
- CT-11: Silent failure destroys legitimacy -> Hash mismatches must be logged
- CT-12: Witnessing creates accountability -> All verification events MUST be witnessed
- CT-13: Integrity outranks availability -> Hash mismatch MUST trigger halt

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before verification operations
2. WITNESS EVERYTHING - All verification events must be witnessed
3. FAIL LOUD - Hash mismatch = immediate halt (CT-13)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# Event type constants for hash verification
HASH_VERIFICATION_BREACH_EVENT_TYPE: str = "hash.verification_breach"
HASH_VERIFICATION_COMPLETED_EVENT_TYPE: str = "hash.verification_completed"


class HashVerificationResult(Enum):
    """Results of hash verification scans (FR125).

    Each result indicates the outcome of a verification scan.
    """

    PASSED = "passed"
    """All verified hashes match their expected values."""

    FAILED = "failed"
    """One or more hashes do not match their expected values."""


@dataclass(frozen=True, eq=True)
class HashVerificationBreachEventPayload:
    """Payload for hash verification breach events (FR125, CT-13).

    A HashVerificationBreachEventPayload is created when continuous
    verification detects a hash mismatch, indicating potential tampering
    or data corruption. This is an existential threat that triggers
    immediate system halt.

    Constitutional Constraints:
    - FR125: Statistical deviation flagging (Selection Audit)
    - CT-11: Silent failure destroys legitimacy -> Breach must be logged
    - CT-12: Witnessing creates accountability
    - CT-13: Integrity outranks availability -> MUST trigger halt

    CRITICAL: This event signals chain integrity compromise.
    The system MUST halt immediately after this event is created.

    Attributes:
        breach_id: Unique breach identifier.
        affected_event_id: Event ID with hash mismatch.
        expected_hash: Hash that should be there.
        actual_hash: Hash that was found.
        event_sequence_num: Position in event chain.
        detected_at: When the mismatch was detected (UTC).
    """

    breach_id: str
    affected_event_id: str
    expected_hash: str
    actual_hash: str
    event_sequence_num: int
    detected_at: datetime

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.breach_id:
            raise ValueError("breach_id cannot be empty")
        if not self.affected_event_id:
            raise ValueError("affected_event_id cannot be empty")
        if not self.expected_hash:
            raise ValueError("expected_hash cannot be empty")
        if not self.actual_hash:
            raise ValueError("actual_hash cannot be empty")
        if self.expected_hash == self.actual_hash:
            raise ValueError(
                "expected_hash and actual_hash cannot be equal in a breach event"
            )
        if self.event_sequence_num < 0:
            raise ValueError(
                f"event_sequence_num must be non-negative, got {self.event_sequence_num}"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": HASH_VERIFICATION_BREACH_EVENT_TYPE,
                "breach_id": self.breach_id,
                "affected_event_id": self.affected_event_id,
                "expected_hash": self.expected_hash,
                "actual_hash": self.actual_hash,
                "event_sequence_num": self.event_sequence_num,
                "detected_at": self.detected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "breach_id": self.breach_id,
            "affected_event_id": self.affected_event_id,
            "expected_hash": self.expected_hash,
            "actual_hash": self.actual_hash,
            "event_sequence_num": self.event_sequence_num,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class HashVerificationCompletedEventPayload:
    """Payload for hash verification completion events (FR125).

    A HashVerificationCompletedEventPayload is created when a
    verification scan completes. This provides audit trail for
    observers to query verification status.

    Constitutional Constraints:
    - FR125: Selection Audit - verification must be observable
    - CT-11: Silent failure destroys legitimacy -> Completion must be logged
    - CT-12: Witnessing creates accountability

    Attributes:
        scan_id: Unique scan identifier.
        events_scanned: Number of events verified in this scan.
        sequence_range: (start, end) sequence numbers covered.
        duration_seconds: Time taken for the scan.
        result: PASSED or FAILED.
        completed_at: When the scan completed (UTC).
    """

    scan_id: str
    events_scanned: int
    sequence_range: tuple[int, int]
    duration_seconds: float
    result: HashVerificationResult
    completed_at: datetime

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.scan_id:
            raise ValueError("scan_id cannot be empty")
        if self.events_scanned < 0:
            raise ValueError(
                f"events_scanned must be non-negative, got {self.events_scanned}"
            )
        if self.duration_seconds < 0.0:
            raise ValueError(
                f"duration_seconds must be non-negative, got {self.duration_seconds}"
            )
        if len(self.sequence_range) != 2:
            raise ValueError(
                f"sequence_range must have exactly 2 elements, got {len(self.sequence_range)}"
            )
        start, end = self.sequence_range
        if start < 0 or end < 0:
            raise ValueError(
                f"sequence_range values must be non-negative, got {self.sequence_range}"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": HASH_VERIFICATION_COMPLETED_EVENT_TYPE,
                "scan_id": self.scan_id,
                "events_scanned": self.events_scanned,
                "sequence_range": list(self.sequence_range),
                "duration_seconds": self.duration_seconds,
                "result": self.result.value,
                "completed_at": self.completed_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "scan_id": self.scan_id,
            "events_scanned": self.events_scanned,
            "sequence_range": list(self.sequence_range),
            "duration_seconds": self.duration_seconds,
            "result": self.result.value,
            "completed_at": self.completed_at.isoformat(),
        }

    @property
    def is_success(self) -> bool:
        """Check if scan passed verification.

        Returns:
            True if result is PASSED, False otherwise.
        """
        return self.result == HashVerificationResult.PASSED
