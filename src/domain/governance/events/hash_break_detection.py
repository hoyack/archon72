"""Hash break detection for governance event ledger.

Story: consent-gov-1.3: Hash Chain Implementation

This module provides hash break detection functionality, emitting
constitutional violation events when integrity issues are detected.

Detection Types:
- Hash mismatch: Event's stored hash doesn't match computed hash
- Chain break: Event's prev_hash doesn't match previous event's hash
- Sequence gap: Missing events in the sequence

Constitutional Constraints:
- NFR-CONST-02: Event integrity verification
- AD-6: Hash chain integrity
- FR2: Tampering detection

Event Type: ledger.integrity.hash_break_detected

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Hash Chain Implementation (Locked)]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.domain.governance.events.event_types import GovernanceEventType
from src.domain.governance.events.hash_chain import (
    HashVerificationResult,
    verify_chain_link,
    verify_event_hash,
)

if TYPE_CHECKING:
    from src.domain.governance.events.event_envelope import GovernanceEvent


class HashBreakType(str, Enum):
    """Types of hash chain integrity violations."""

    HASH_MISMATCH = "hash_mismatch"
    """Event's stored hash doesn't match computed hash."""

    CHAIN_BREAK = "chain_break"
    """Event's prev_hash doesn't match previous event's hash."""

    SEQUENCE_GAP = "sequence_gap"
    """Missing events detected in sequence."""


@dataclass(frozen=True)
class HashBreakInfo:
    """Information about a detected hash break.

    Attributes:
        break_type: Type of integrity violation.
        sequence: Sequence number where break was detected.
        event_id: UUID of the event with the issue.
        expected_hash: What the hash should be.
        actual_hash: What the hash actually is.
        detected_at: When the break was detected.
        detector_id: ID of the service/component that detected the break.
        details: Additional context about the break.
    """

    break_type: HashBreakType
    sequence: int
    event_id: UUID
    expected_hash: str
    actual_hash: str
    detected_at: datetime
    detector_id: str
    details: str = ""


@dataclass(frozen=True)
class HashBreakDetectionResult:
    """Result of hash break detection.

    Attributes:
        has_break: Whether a break was detected.
        break_info: Details about the break (if detected).
        events_verified: Number of events verified.
    """

    has_break: bool
    break_info: HashBreakInfo | None = None
    events_verified: int = 0


class HashBreakDetector:
    """Detects hash chain integrity violations.

    This class verifies hash chain integrity and reports breaks
    as constitutional violations.

    Usage:
        detector = HashBreakDetector(detector_id="ledger-service")
        result = detector.check_event(event, previous_event)
        if result.has_break:
            # Handle break - emit event, trigger halt, etc.
            break_event = detector.create_break_event(result, now)
    """

    def __init__(self, detector_id: str) -> None:
        """Initialize detector with identifier.

        Args:
            detector_id: ID of the service/component running detection.
        """
        self._detector_id = detector_id

    @property
    def detector_id(self) -> str:
        """Return detector identifier."""
        return self._detector_id

    def check_event(
        self,
        event: "GovernanceEvent",
        previous_event: "GovernanceEvent | None",
        detected_at: datetime,
    ) -> HashBreakDetectionResult:
        """Check a single event for hash integrity.

        Args:
            event: The event to verify.
            previous_event: The previous event in chain (None for genesis).
            detected_at: Timestamp for detection record.

        Returns:
            HashBreakDetectionResult with break details if found.
        """
        # Check event's own hash
        hash_result = verify_event_hash(event)
        if not hash_result.is_valid:
            return HashBreakDetectionResult(
                has_break=True,
                break_info=HashBreakInfo(
                    break_type=HashBreakType.HASH_MISMATCH,
                    sequence=0,  # Sequence assigned by ledger, we don't have it here
                    event_id=event.event_id,
                    expected_hash=hash_result.expected_hash,
                    actual_hash=hash_result.actual_hash,
                    detected_at=detected_at,
                    detector_id=self._detector_id,
                    details=hash_result.error_message,
                ),
                events_verified=1,
            )

        # Check chain link
        link_result = verify_chain_link(event, previous_event)
        if not link_result.is_valid:
            return HashBreakDetectionResult(
                has_break=True,
                break_info=HashBreakInfo(
                    break_type=HashBreakType.CHAIN_BREAK,
                    sequence=0,
                    event_id=event.event_id,
                    expected_hash=link_result.expected_hash,
                    actual_hash=link_result.actual_hash,
                    detected_at=detected_at,
                    detector_id=self._detector_id,
                    details=link_result.error_message,
                ),
                events_verified=1,
            )

        return HashBreakDetectionResult(
            has_break=False,
            events_verified=1,
        )

    def check_sequence(
        self,
        events: list["GovernanceEvent"],
        detected_at: datetime,
    ) -> HashBreakDetectionResult:
        """Check a sequence of events for hash chain integrity.

        Verifies each event's hash and chain links in order.

        Args:
            events: Ordered list of events to verify.
            detected_at: Timestamp for detection record.

        Returns:
            HashBreakDetectionResult with first break found, if any.
        """
        if not events:
            return HashBreakDetectionResult(has_break=False, events_verified=0)

        previous_event: GovernanceEvent | None = None

        for event in events:
            result = self.check_event(event, previous_event, detected_at)
            if result.has_break:
                return result
            previous_event = event

        return HashBreakDetectionResult(
            has_break=False,
            events_verified=len(events),
        )

    def create_break_event_payload(
        self,
        detection_result: HashBreakDetectionResult,
    ) -> dict[str, object]:
        """Create payload for a hash break detection event.

        Args:
            detection_result: The detection result with break info.

        Returns:
            Payload dict for GovernanceEvent.

        Raises:
            ValueError: If detection_result has no break.
        """
        if not detection_result.has_break or not detection_result.break_info:
            raise ValueError("Cannot create break event for result with no break")

        info = detection_result.break_info

        return {
            "break_type": info.break_type.value,
            "broken_at_sequence": info.sequence,
            "affected_event_id": str(info.event_id),
            "expected_hash": info.expected_hash,
            "actual_hash": info.actual_hash,
            "detected_at": info.detected_at.isoformat(),
            "detector_id": info.detector_id,
            "details": info.details,
        }


# Convenience constant for the event type
HASH_BREAK_EVENT_TYPE = GovernanceEventType.LEDGER_INTEGRITY_HASH_BREAK_DETECTED.value
