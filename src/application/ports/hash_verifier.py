"""Hash verifier port (Story 6.8, FR125).

Defines the protocol for continuous hash verification, supporting
chain integrity monitoring.

Constitutional Constraints:
- FR125: Witness selection algorithm SHALL be published; statistical
         deviation from expected distribution flagged (Selection Audit)
- CT-11: Silent failure destroys legitimacy -> Verification must be logged
- CT-13: Integrity outranks availability -> Hash mismatch MUST trigger halt

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before verification operations
2. WITNESS EVERYTHING - All verification events must be witnessed
3. FAIL LOUD - Hash mismatch = immediate halt (CT-13)
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.domain.events.hash_verification import HashVerificationResult


@dataclass(frozen=True)
class HashScanResult:
    """Result of a full hash chain verification scan.

    Constitutional Constraint (FR125):
    Represents the outcome of verifying all stored hashes
    against recalculated values.

    Attributes:
        scan_id: Unique identifier for this scan.
        events_scanned: Number of events verified.
        passed: True if all hashes match, False if any mismatch.
        failed_event_id: ID of first event with hash mismatch (if failed).
        expected_hash: Expected hash of failed event (if failed).
        actual_hash: Actual hash found for failed event (if failed).
        completed_at: When the scan completed.
        duration_seconds: Time taken for the scan.
    """

    scan_id: str
    events_scanned: int
    passed: bool
    completed_at: datetime
    duration_seconds: float
    failed_event_id: str | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None

    def __post_init__(self) -> None:
        """Validate consistency of failed scan data."""
        if not self.passed:
            if not self.failed_event_id:
                raise ValueError("failed_event_id required when passed=False")
            if not self.expected_hash:
                raise ValueError("expected_hash required when passed=False")
            if not self.actual_hash:
                raise ValueError("actual_hash required when passed=False")
        if self.events_scanned < 0:
            raise ValueError(
                f"events_scanned must be non-negative, got {self.events_scanned}"
            )
        if self.duration_seconds < 0.0:
            raise ValueError(
                f"duration_seconds must be non-negative, got {self.duration_seconds}"
            )


@dataclass(frozen=True)
class HashScanStatus:
    """Status of hash verification for observer queries.

    Provides observability into continuous verification state.

    Attributes:
        last_scan_id: ID of the most recent scan (if any).
        last_scan_at: When the last scan completed (if any).
        next_scan_at: When the next scan is scheduled (if configured).
        last_scan_passed: Result of the last scan (if any).
        events_verified_total: Total events verified across all scans.
        verification_interval_seconds: Configured interval between scans.
    """

    last_scan_id: str | None = None
    last_scan_at: datetime | None = None
    next_scan_at: datetime | None = None
    last_scan_passed: bool | None = None
    events_verified_total: int = 0
    verification_interval_seconds: int = 3600  # Default 1 hour

    @property
    def is_healthy(self) -> bool:
        """Check if verification is healthy.

        Healthy means either no scans have run yet,
        or the last scan passed.
        """
        if self.last_scan_passed is None:
            return True  # No scans yet is okay
        return self.last_scan_passed


@runtime_checkable
class HashVerifierProtocol(Protocol):
    """Protocol for hash verification (FR125, CT-13).

    Constitutional Constraints:
    - FR125: Selection Audit - verification must be observable
    - CT-13: Integrity outranks availability - mismatch MUST halt

    Implementations must:
    1. Verify individual event hashes
    2. Run full chain verification scans
    3. Report verification status for observers
    4. Support continuous verification with configurable interval
    5. Trigger immediate halt on any mismatch

    CRITICAL: Hash mismatch is an existential threat.
    Any mismatch MUST result in immediate system halt per CT-13.

    Example:
        verifier: HashVerifierProtocol = ...

        # Verify single event
        result = await verifier.verify_event_hash("event-123")
        if result == HashVerificationResult.FAILED:
            # System should already be halting
            ...

        # Run full scan
        scan_result = await verifier.run_full_scan()
        if not scan_result.passed:
            # System should already be halting
            ...

        # Configure continuous verification
        await verifier.schedule_continuous_verification(3600)  # Every hour

        # Check status (for observers)
        status = await verifier.get_last_scan_status()
        if status.is_healthy:
            print("Hash verification passing")
    """

    @abstractmethod
    async def verify_event_hash(
        self,
        event_id: str,
    ) -> HashVerificationResult:
        """Verify a single event's hash.

        Recalculates the content hash and compares it to the
        stored hash. Any mismatch is a critical failure.

        Args:
            event_id: ID of the event to verify.

        Returns:
            PASSED if hash matches, FAILED if mismatch.

        Raises:
            HashMismatchError: If hash does not match (CT-13).
            EventNotFoundError: If event does not exist.
        """
        ...

    @abstractmethod
    async def run_full_scan(
        self,
        max_events: int | None = None,
    ) -> HashScanResult:
        """Run full hash chain verification.

        Verifies all events in the chain, checking:
        1. Each event's content_hash matches recalculated hash
        2. Each event's prev_hash matches previous event's content_hash

        Constitutional Constraint (CT-13):
        Any mismatch MUST trigger immediate system halt.

        Args:
            max_events: Optional limit on events to verify.
                        If None, verifies all events.

        Returns:
            HashScanResult with scan outcome.

        Note:
            If a mismatch is found, this method should trigger
            system halt before returning.
        """
        ...

    @abstractmethod
    async def get_last_scan_status(self) -> HashScanStatus:
        """Get the status of the last verification scan.

        Provides observability for external monitors and observers.

        Returns:
            HashScanStatus with last scan details.
        """
        ...

    @abstractmethod
    async def schedule_continuous_verification(
        self,
        interval_seconds: int = 3600,
    ) -> None:
        """Configure continuous verification interval.

        Sets up periodic hash verification scans at the
        specified interval.

        Constitutional Constraint (FR125):
        Observers should be able to query verification status.

        Args:
            interval_seconds: Seconds between scans. Default 3600 (1 hour).

        Raises:
            ValueError: If interval_seconds is <= 0.
        """
        ...

    @abstractmethod
    async def get_verification_interval(self) -> int:
        """Get the configured verification interval.

        Returns:
            Interval between scans in seconds.
        """
        ...

    @abstractmethod
    async def verify_hash_chain_link(
        self,
        event_sequence: int,
    ) -> HashVerificationResult:
        """Verify the hash chain link at a specific sequence.

        Checks that the prev_hash of event at sequence N matches
        the content_hash of event at sequence N-1.

        Args:
            event_sequence: Sequence number to verify.

        Returns:
            PASSED if chain link is valid, FAILED if broken.

        Raises:
            HashChainBrokenError: If chain link is broken (CT-13).
            EventNotFoundError: If sequence does not exist.
        """
        ...
