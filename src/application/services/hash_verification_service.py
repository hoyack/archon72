"""Hash verification service (Story 6.8, FR125).

Implements continuous hash verification for chain integrity monitoring.

Constitutional Constraints:
- FR125: Witness selection algorithm SHALL be published; statistical
         deviation from expected distribution flagged (Selection Audit)
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability -> Hash mismatch MUST halt

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state at every operation boundary
2. WITNESS EVERYTHING - All verification events must be witnessed
3. FAIL LOUD - Hash mismatch = immediate halt (CT-13)
"""

from __future__ import annotations

import hmac
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.halt_trigger import HaltTrigger
from src.application.ports.hash_verifier import (
    HashScanResult,
    HashScanStatus,
    HashVerifierProtocol,
)
from src.domain.errors.hash_verification import (
    HashChainBrokenError,
    HashMismatchError,
    HashVerificationScanInProgressError,
    HashVerificationTimeoutError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.hash_utils import compute_content_hash
from src.domain.events.hash_verification import (
    HashVerificationBreachEventPayload,
    HashVerificationResult,
)

# System agent ID for hash verification operations
HASH_VERIFICATION_SYSTEM_AGENT_ID: str = "system:hash_verification"

# Default verification interval in seconds (1 hour)
DEFAULT_VERIFICATION_INTERVAL_SECONDS: int = 3600

# Default timeout for full scan in seconds (10 minutes)
DEFAULT_SCAN_TIMEOUT_SECONDS: float = 600.0


@dataclass
class HashVerificationState:
    """Mutable state for hash verification tracking.

    Attributes:
        last_scan_id: ID of the most recent scan.
        last_scan_at: When the last scan completed.
        last_scan_passed: Result of the last scan.
        events_verified_total: Total events verified across all scans.
        verification_interval_seconds: Configured interval between scans.
        scan_in_progress: Whether a scan is currently running.
        current_scan_id: ID of scan in progress (if any).
    """

    last_scan_id: str | None = None
    last_scan_at: datetime | None = None
    last_scan_passed: bool | None = None
    events_verified_total: int = 0
    verification_interval_seconds: int = DEFAULT_VERIFICATION_INTERVAL_SECONDS
    scan_in_progress: bool = False
    current_scan_id: str | None = None


class HashVerificationService(HashVerifierProtocol):
    """Service for continuous hash verification (FR125, CT-13).

    Constitutional Constraints:
    - FR125: Selection Audit - verification must be observable
    - CT-13: Integrity outranks availability - mismatch MUST halt

    This service implements:
    1. Individual event hash verification
    2. Full chain verification scans
    3. Hash chain link verification
    4. Continuous verification scheduling
    5. Immediate halt on any mismatch

    CRITICAL: Hash mismatch is an existential threat.
    Any mismatch MUST result in immediate system halt per CT-13.

    Example:
        service = HashVerificationService(
            halt_checker=halt_checker,
            halt_trigger=halt_trigger,
            event_store=event_store,
        )

        # Verify single event
        result = await service.verify_event_hash("event-123")

        # Run full scan
        scan_result = await service.run_full_scan()

        # Check status
        status = await service.get_last_scan_status()
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        halt_trigger: HaltTrigger,
        event_store: EventStorePort,
        event_writer: object | None = None,
        timeout_seconds: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the hash verification service.

        Args:
            halt_checker: For HALT CHECK FIRST pattern.
            halt_trigger: For triggering halt on mismatch.
            event_store: For reading events to verify.
            event_writer: Optional event writer for creating events.
            timeout_seconds: Timeout for full scan operations.
        """
        self._halt_checker = halt_checker
        self._halt_trigger = halt_trigger
        self._event_store = event_store
        self._event_writer = event_writer
        self._timeout_seconds = timeout_seconds
        self._state = HashVerificationState()

    async def verify_event_hash(
        self,
        event_id: str,
    ) -> HashVerificationResult:
        """Verify a single event's hash.

        HALT CHECK FIRST (CT-11).

        Args:
            event_id: ID of the event to verify.

        Returns:
            PASSED if hash matches, FAILED if mismatch.

        Raises:
            HashMismatchError: If hash does not match (CT-13).
            SystemHaltedError: If system is already halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        event = await self._event_store.get_by_id(event_id)
        if event is None:
            from src.domain.errors.event_store import EventNotFoundError

            raise EventNotFoundError(event_id)

        # Recalculate content hash - must reconstruct full event_data dict
        # compute_content_hash expects: event_type, payload, signature,
        # witness_id, witness_signature, local_timestamp, agent_id (optional)
        event_data = {
            "event_type": event.event_type,
            "payload": dict(event.payload),  # Convert MappingProxyType to dict
            "signature": event.signature,
            "witness_id": event.witness_id,
            "witness_signature": event.witness_signature,
            "local_timestamp": event.local_timestamp,
            "agent_id": event.agent_id,
        }
        recalculated_hash = compute_content_hash(event_data)

        # Use constant-time comparison to prevent timing attacks (H2 fix)
        if not hmac.compare_digest(recalculated_hash, event.content_hash):
            # CRITICAL: Hash mismatch (CT-13)
            await self._handle_hash_mismatch(
                event_id=event_id,
                event_sequence=event.sequence,
                expected_hash=recalculated_hash,
                actual_hash=event.content_hash,
            )
            return HashVerificationResult.FAILED

        return HashVerificationResult.PASSED

    async def run_full_scan(
        self,
        max_events: int | None = None,
    ) -> HashScanResult:
        """Run full hash chain verification.

        HALT CHECK FIRST (CT-11).

        Args:
            max_events: Optional limit on events to verify.

        Returns:
            HashScanResult with scan outcome.

        Raises:
            SystemHaltedError: If system is already halted.
            HashVerificationScanInProgressError: If scan already running.
            HashVerificationTimeoutError: If scan exceeds timeout.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        # Check for concurrent scan
        if self._state.scan_in_progress:
            raise HashVerificationScanInProgressError(
                active_scan_id=self._state.current_scan_id or "unknown",
            )

        # Start scan
        scan_id = str(uuid4())
        self._state.scan_in_progress = True
        self._state.current_scan_id = scan_id

        start_time = time.monotonic()
        datetime.now(timezone.utc)
        events_scanned = 0
        start_sequence = 0
        end_sequence = 0

        try:
            # Get all events
            events = await self._event_store.get_all(limit=max_events)

            if not events:
                # No events to verify
                return self._complete_scan(
                    scan_id=scan_id,
                    events_scanned=0,
                    sequence_range=(0, 0),
                    start_time=start_time,
                    passed=True,
                )

            start_sequence = events[0].sequence_num if events else 0
            end_sequence = events[-1].sequence_num if events else 0
            prev_content_hash = None

            for event in events:
                # Check timeout
                elapsed = time.monotonic() - start_time
                if elapsed > self._timeout_seconds:
                    self._state.scan_in_progress = False
                    self._state.current_scan_id = None
                    raise HashVerificationTimeoutError(
                        scan_id=scan_id,
                        timeout_seconds=self._timeout_seconds,
                    )

                # Verify content hash - must reconstruct full event_data dict
                event_data = {
                    "event_type": event.event_type,
                    "payload": dict(event.payload),
                    "signature": event.signature,
                    "witness_id": event.witness_id,
                    "witness_signature": event.witness_signature,
                    "local_timestamp": event.local_timestamp,
                    "agent_id": event.agent_id,
                }
                recalculated_hash = compute_content_hash(event_data)
                # Use constant-time comparison to prevent timing attacks (H2 fix)
                if not hmac.compare_digest(recalculated_hash, event.content_hash):
                    # CRITICAL: Hash mismatch (CT-13)
                    await self._handle_hash_mismatch(
                        event_id=str(event.event_id),
                        event_sequence=event.sequence,
                        expected_hash=recalculated_hash,
                        actual_hash=event.content_hash,
                    )
                    return self._complete_scan(
                        scan_id=scan_id,
                        events_scanned=events_scanned,
                        sequence_range=(start_sequence, end_sequence),
                        start_time=start_time,
                        passed=False,
                        failed_event_id=str(event.event_id),
                        expected_hash=recalculated_hash,
                        actual_hash=event.content_hash,
                    )

                # Verify hash chain link (if not first event)
                if prev_content_hash is not None:
                    # Use constant-time comparison to prevent timing attacks
                    if not hmac.compare_digest(event.prev_hash, prev_content_hash):
                        # CRITICAL: Chain broken (CT-13)
                        await self._handle_chain_break(
                            event_sequence=event.sequence,
                            expected_prev_hash=prev_content_hash,
                            actual_prev_hash=event.prev_hash,
                        )
                        return self._complete_scan(
                            scan_id=scan_id,
                            events_scanned=events_scanned,
                            sequence_range=(start_sequence, end_sequence),
                            start_time=start_time,
                            passed=False,
                            failed_event_id=str(event.event_id),
                            expected_hash=prev_content_hash,
                            actual_hash=event.prev_hash,
                        )

                prev_content_hash = event.content_hash
                events_scanned += 1

            # All verified
            return self._complete_scan(
                scan_id=scan_id,
                events_scanned=events_scanned,
                sequence_range=(start_sequence, end_sequence),
                start_time=start_time,
                passed=True,
            )

        finally:
            self._state.scan_in_progress = False
            self._state.current_scan_id = None

    def _complete_scan(
        self,
        scan_id: str,
        events_scanned: int,
        sequence_range: tuple[int, int],
        start_time: float,
        passed: bool,
        failed_event_id: str | None = None,
        expected_hash: str | None = None,
        actual_hash: str | None = None,
    ) -> HashScanResult:
        """Complete a scan and update state.

        Args:
            scan_id: ID of the scan.
            events_scanned: Number of events verified.
            sequence_range: (start, end) sequence numbers.
            start_time: When the scan started (monotonic).
            passed: True if all hashes match.
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

        # Update state
        self._state.last_scan_id = scan_id
        self._state.last_scan_at = now
        self._state.last_scan_passed = passed
        self._state.events_verified_total += events_scanned

        return result

    async def get_last_scan_status(self) -> HashScanStatus:
        """Get the status of the last verification scan.

        Returns:
            HashScanStatus with last scan details.
        """
        next_scan_at = None
        if self._state.last_scan_at and self._state.verification_interval_seconds:
            from datetime import timedelta

            next_scan_at = self._state.last_scan_at + timedelta(
                seconds=self._state.verification_interval_seconds
            )

        return HashScanStatus(
            last_scan_id=self._state.last_scan_id,
            last_scan_at=self._state.last_scan_at,
            next_scan_at=next_scan_at,
            last_scan_passed=self._state.last_scan_passed,
            events_verified_total=self._state.events_verified_total,
            verification_interval_seconds=self._state.verification_interval_seconds,
        )

    async def schedule_continuous_verification(
        self,
        interval_seconds: int = DEFAULT_VERIFICATION_INTERVAL_SECONDS,
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
        self._state.verification_interval_seconds = interval_seconds

    async def get_verification_interval(self) -> int:
        """Get the configured verification interval.

        Returns:
            Interval between scans in seconds.
        """
        return self._state.verification_interval_seconds

    async def verify_hash_chain_link(
        self,
        event_sequence: int,
    ) -> HashVerificationResult:
        """Verify the hash chain link at a specific sequence.

        HALT CHECK FIRST (CT-11).

        Args:
            event_sequence: Sequence number to verify.

        Returns:
            PASSED if chain link is valid, FAILED if broken.

        Raises:
            HashChainBrokenError: If chain link is broken (CT-13).
            SystemHaltedError: If system is already halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        if event_sequence < 1:
            # Sequence 0 has no previous event to check
            return HashVerificationResult.PASSED

        # Get current event
        current_event = await self._event_store.get_by_sequence(event_sequence)
        if current_event is None:
            from src.domain.errors.event_store import EventNotFoundError

            raise EventNotFoundError(f"sequence:{event_sequence}")

        # Get previous event
        prev_event = await self._event_store.get_by_sequence(event_sequence - 1)
        if prev_event is None:
            from src.domain.errors.event_store import EventNotFoundError

            raise EventNotFoundError(f"sequence:{event_sequence - 1}")

        # Verify link (constant-time comparison to prevent timing attacks)
        if not hmac.compare_digest(current_event.prev_hash, prev_event.content_hash):
            # CRITICAL: Chain broken (CT-13)
            await self._handle_chain_break(
                event_sequence=event_sequence,
                expected_prev_hash=prev_event.content_hash,
                actual_prev_hash=current_event.prev_hash,
            )
            return HashVerificationResult.FAILED

        return HashVerificationResult.PASSED

    async def _handle_hash_mismatch(
        self,
        event_id: str,
        event_sequence: int,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        """Handle hash mismatch - trigger halt and create breach event.

        CRITICAL: This is an existential threat (CT-13).

        Args:
            event_id: ID of the event with mismatch.
            event_sequence: Sequence number of the event.
            expected_hash: Expected hash value.
            actual_hash: Actual hash found.
        """
        now = datetime.now(timezone.utc)
        breach_id = str(uuid4())

        # Create breach event
        breach_event = HashVerificationBreachEventPayload(
            breach_id=breach_id,
            affected_event_id=event_id,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
            event_sequence_num=event_sequence,
            detected_at=now,
        )

        # Write event if writer available
        if self._event_writer is not None:
            await self._event_writer.write_event(breach_event)  # type: ignore

        # Trigger halt (CT-13)
        await self._halt_trigger.trigger_halt(
            reason=f"FR125: Hash mismatch detected at sequence {event_sequence} - "
            f"chain integrity compromised",
            triggered_by=HASH_VERIFICATION_SYSTEM_AGENT_ID,
        )

        # Raise error
        raise HashMismatchError(
            event_id=event_id,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
        )

    async def _handle_chain_break(
        self,
        event_sequence: int,
        expected_prev_hash: str,
        actual_prev_hash: str,
    ) -> None:
        """Handle hash chain break - trigger halt.

        CRITICAL: This is an existential threat (CT-13).

        Args:
            event_sequence: Sequence number where chain broke.
            expected_prev_hash: Expected prev_hash.
            actual_prev_hash: Actual prev_hash found.
        """
        # Trigger halt (CT-13)
        await self._halt_trigger.trigger_halt(
            reason=f"FR125: Hash chain broken at sequence {event_sequence} - "
            f"chain integrity compromised",
            triggered_by=HASH_VERIFICATION_SYSTEM_AGENT_ID,
        )

        # Raise error
        raise HashChainBrokenError(
            event_sequence=event_sequence,
            expected_prev_hash=expected_prev_hash,
            actual_prev_hash=actual_prev_hash,
        )
