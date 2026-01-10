"""Hash verifier stub (Story 6.8, FR125).

In-memory stub implementation for testing and development.

Constitutional Constraints:
- FR125: Witness selection algorithm SHALL be published; statistical
         deviation from expected distribution flagged (Selection Audit)
- CT-13: Integrity outranks availability -> Hash mismatch MUST trigger halt
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from src.application.ports.hash_verifier import (
    HashScanResult,
    HashScanStatus,
    HashVerifierProtocol,
)
from src.domain.events.hash_verification import HashVerificationResult


@dataclass
class MockEvent:
    """Mock event for testing hash verification.

    Attributes:
        event_id: Unique event identifier.
        sequence_num: Position in event chain.
        content_hash: Hash of event content.
        prev_hash: Hash of previous event.
    """

    event_id: str
    sequence_num: int
    content_hash: str
    prev_hash: str


class HashVerifierStub(HashVerifierProtocol):
    """In-memory stub for HashVerifierProtocol.

    Provides a simple implementation for testing that uses
    mock events. Can be configured to fail for specific events.

    Example:
        stub = HashVerifierStub()

        # Add mock events
        stub.add_event("event-1", 0, "hash_a", "000...")
        stub.add_event("event-2", 1, "hash_b", "hash_a")

        # Configure failure
        stub.set_expected_hash("event-2", "wrong_hash")

        # Verify will fail
        result = await stub.verify_event_hash("event-2")
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._events: dict[str, MockEvent] = {}
        self._events_by_sequence: dict[int, MockEvent] = {}
        self._expected_hashes: dict[str, str] = {}  # Override hashes for testing
        self._last_scan_id: Optional[str] = None
        self._last_scan_at: Optional[datetime] = None
        self._last_scan_passed: Optional[bool] = None
        self._events_verified_total: int = 0
        self._verification_interval_seconds: int = 3600
        self._scan_in_progress: bool = False
        self._halt_triggered: bool = False

    def add_event(
        self,
        event_id: str,
        sequence_num: int,
        content_hash: str,
        prev_hash: str,
    ) -> None:
        """Add a mock event for verification testing.

        Args:
            event_id: Unique event identifier.
            sequence_num: Position in event chain.
            content_hash: Hash of event content.
            prev_hash: Hash of previous event.
        """
        event = MockEvent(
            event_id=event_id,
            sequence_num=sequence_num,
            content_hash=content_hash,
            prev_hash=prev_hash,
        )
        self._events[event_id] = event
        self._events_by_sequence[sequence_num] = event

    def set_expected_hash(self, event_id: str, expected_hash: str) -> None:
        """Set expected hash override for testing failures.

        When verify_event_hash is called for this event, it will
        compare against this expected hash instead of recalculating.

        Args:
            event_id: Event to configure.
            expected_hash: Hash that should be expected (will fail if different).
        """
        self._expected_hashes[event_id] = expected_hash

    async def verify_event_hash(
        self,
        event_id: str,
    ) -> HashVerificationResult:
        """Verify a single event's hash.

        Args:
            event_id: ID of the event to verify.

        Returns:
            PASSED if hash matches, FAILED if mismatch.
        """
        event = self._events.get(event_id)
        if event is None:
            from src.domain.errors.event_store import EventNotFoundError

            raise EventNotFoundError(event_id)

        # Check for override
        expected = self._expected_hashes.get(event_id, event.content_hash)

        if expected != event.content_hash:
            self._halt_triggered = True
            return HashVerificationResult.FAILED

        return HashVerificationResult.PASSED

    async def run_full_scan(
        self,
        max_events: Optional[int] = None,
    ) -> HashScanResult:
        """Run full hash chain verification.

        Args:
            max_events: Optional limit on events to verify.

        Returns:
            HashScanResult with scan outcome.
        """
        scan_id = str(uuid4())
        start_time = time.monotonic()
        now = datetime.now(timezone.utc)

        # Get events sorted by sequence
        events = sorted(
            self._events.values(),
            key=lambda e: e.sequence_num,
        )

        if max_events is not None:
            events = events[:max_events]

        if not events:
            return self._complete_scan(
                scan_id=scan_id,
                events_scanned=0,
                passed=True,
                start_time=start_time,
            )

        prev_hash = None
        for event in events:
            # Check for override failure
            expected = self._expected_hashes.get(event.event_id, event.content_hash)
            if expected != event.content_hash:
                self._halt_triggered = True
                return self._complete_scan(
                    scan_id=scan_id,
                    events_scanned=event.sequence_num,
                    passed=False,
                    start_time=start_time,
                    failed_event_id=event.event_id,
                    expected_hash=expected,
                    actual_hash=event.content_hash,
                )

            # Check chain link
            if prev_hash is not None and event.prev_hash != prev_hash:
                self._halt_triggered = True
                return self._complete_scan(
                    scan_id=scan_id,
                    events_scanned=event.sequence_num,
                    passed=False,
                    start_time=start_time,
                    failed_event_id=event.event_id,
                    expected_hash=prev_hash,
                    actual_hash=event.prev_hash,
                )

            prev_hash = event.content_hash

        return self._complete_scan(
            scan_id=scan_id,
            events_scanned=len(events),
            passed=True,
            start_time=start_time,
        )

    def _complete_scan(
        self,
        scan_id: str,
        events_scanned: int,
        passed: bool,
        start_time: float,
        failed_event_id: Optional[str] = None,
        expected_hash: Optional[str] = None,
        actual_hash: Optional[str] = None,
    ) -> HashScanResult:
        """Complete a scan and update state.

        Args:
            scan_id: ID of the scan.
            events_scanned: Number of events verified.
            passed: True if all hashes match.
            start_time: When the scan started.
            failed_event_id: ID of failed event (if failed).
            expected_hash: Expected hash (if failed).
            actual_hash: Actual hash (if failed).

        Returns:
            HashScanResult with scan outcome.
        """
        now = datetime.now(timezone.utc)
        duration = time.monotonic() - start_time

        result = HashScanResult(
            scan_id=scan_id,
            events_scanned=events_scanned,
            passed=passed,
            completed_at=now,
            duration_seconds=duration,
            failed_event_id=failed_event_id,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
        )

        self._last_scan_id = scan_id
        self._last_scan_at = now
        self._last_scan_passed = passed
        self._events_verified_total += events_scanned

        return result

    async def get_last_scan_status(self) -> HashScanStatus:
        """Get the status of the last verification scan.

        Returns:
            HashScanStatus with last scan details.
        """
        next_scan_at = None
        if self._last_scan_at and self._verification_interval_seconds:
            next_scan_at = (
                self._last_scan_at
                + timedelta(seconds=self._verification_interval_seconds)
            )

        return HashScanStatus(
            last_scan_id=self._last_scan_id,
            last_scan_at=self._last_scan_at,
            next_scan_at=next_scan_at,
            last_scan_passed=self._last_scan_passed,
            events_verified_total=self._events_verified_total,
            verification_interval_seconds=self._verification_interval_seconds,
        )

    async def schedule_continuous_verification(
        self,
        interval_seconds: int = 3600,
    ) -> None:
        """Configure continuous verification interval.

        Args:
            interval_seconds: Seconds between scans.

        Raises:
            ValueError: If interval_seconds <= 0.
        """
        if interval_seconds <= 0:
            raise ValueError(
                f"interval_seconds must be positive, got {interval_seconds}"
            )
        self._verification_interval_seconds = interval_seconds

    async def get_verification_interval(self) -> int:
        """Get the configured verification interval.

        Returns:
            Interval between scans in seconds.
        """
        return self._verification_interval_seconds

    async def verify_hash_chain_link(
        self,
        event_sequence: int,
    ) -> HashVerificationResult:
        """Verify the hash chain link at a specific sequence.

        Args:
            event_sequence: Sequence number to verify.

        Returns:
            PASSED if chain link is valid, FAILED if broken.
        """
        if event_sequence < 1:
            return HashVerificationResult.PASSED

        current = self._events_by_sequence.get(event_sequence)
        if current is None:
            from src.domain.errors.event_store import EventNotFoundError

            raise EventNotFoundError(f"sequence:{event_sequence}")

        prev = self._events_by_sequence.get(event_sequence - 1)
        if prev is None:
            from src.domain.errors.event_store import EventNotFoundError

            raise EventNotFoundError(f"sequence:{event_sequence - 1}")

        if current.prev_hash != prev.content_hash:
            self._halt_triggered = True
            return HashVerificationResult.FAILED

        return HashVerificationResult.PASSED

    @property
    def halt_triggered(self) -> bool:
        """Check if halt was triggered due to verification failure."""
        return self._halt_triggered

    def clear(self) -> None:
        """Clear all data (for testing)."""
        self._events.clear()
        self._events_by_sequence.clear()
        self._expected_hashes.clear()
        self._last_scan_id = None
        self._last_scan_at = None
        self._last_scan_passed = None
        self._events_verified_total = 0
        self._halt_triggered = False
