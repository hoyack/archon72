"""Hash verification errors (Story 6.8, FR125).

Provides specific exception classes for hash verification scenarios.
All exceptions inherit from ConstitutionalViolationError.

Constitutional Constraints:
- FR125: Witness selection algorithm SHALL be published; statistical
         deviation from expected distribution flagged (Selection Audit)
- CT-11: Silent failure destroys legitimacy
- CT-13: Integrity outranks availability
"""

from __future__ import annotations

from typing import Optional

from src.domain.errors.constitutional import ConstitutionalViolationError


class HashVerificationError(ConstitutionalViolationError):
    """Base class for hash verification errors (FR125).

    All hash verification errors inherit from this class.
    """

    pass


class HashMismatchError(HashVerificationError):
    """Error when hash verification detects a mismatch (FR125, CT-13).

    Raised when continuous verification detects that a stored hash
    does not match the recalculated hash. This is an existential
    threat indicating tampering or data corruption.

    Constitutional Constraints:
    - FR125: Selection Audit - mismatches must be flagged
    - CT-13: Integrity outranks availability - MUST trigger halt

    CRITICAL: This error indicates chain integrity compromise.
    The system MUST halt immediately when this error is raised.

    Attributes:
        event_id: ID of the event with hash mismatch.
        expected_hash: Hash that should be there.
        actual_hash: Hash that was found.
    """

    def __init__(
        self,
        event_id: str,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        """Initialize the error.

        Args:
            event_id: ID of the event with hash mismatch.
            expected_hash: Hash that should be there.
            actual_hash: Hash that was found.
        """
        self.event_id = event_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"FR125: Hash mismatch detected for event {event_id} - "
            "chain integrity compromised"
        )


class HashVerificationTimeoutError(HashVerificationError):
    """Error when hash verification scan times out.

    Raised when a verification scan exceeds the configured timeout.
    This may indicate performance issues or an extremely large
    event chain.

    Attributes:
        scan_id: ID of the timed-out scan.
        timeout_seconds: The timeout that was exceeded.
    """

    def __init__(
        self,
        scan_id: str,
        timeout_seconds: float,
    ) -> None:
        """Initialize the error.

        Args:
            scan_id: ID of the timed-out scan.
            timeout_seconds: The timeout that was exceeded.
        """
        self.scan_id = scan_id
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Hash verification scan {scan_id} timed out after {timeout_seconds}s"
        )


class HashVerificationScanInProgressError(HashVerificationError):
    """Error when scan is already in progress.

    Raised when attempting to start a new scan while another
    scan is still running.

    Attributes:
        active_scan_id: ID of the scan already in progress.
    """

    def __init__(self, active_scan_id: str) -> None:
        """Initialize the error.

        Args:
            active_scan_id: ID of the scan already in progress.
        """
        self.active_scan_id = active_scan_id
        super().__init__(
            f"Hash verification scan already in progress: {active_scan_id}"
        )


class HashChainBrokenError(HashVerificationError):
    """Error when hash chain is broken (CT-13).

    Raised when the prev_hash of an event does not match the
    content_hash of the previous event. This is a critical
    integrity failure.

    Constitutional Constraint (CT-13):
    Integrity outranks availability - broken chain MUST trigger halt.

    Attributes:
        event_sequence: Sequence number of the broken link.
        expected_prev_hash: What prev_hash should be.
        actual_prev_hash: What prev_hash actually is.
    """

    def __init__(
        self,
        event_sequence: int,
        expected_prev_hash: str,
        actual_prev_hash: str,
    ) -> None:
        """Initialize the error.

        Args:
            event_sequence: Sequence number of the broken link.
            expected_prev_hash: What prev_hash should be.
            actual_prev_hash: What prev_hash actually is.
        """
        self.event_sequence = event_sequence
        self.expected_prev_hash = expected_prev_hash
        self.actual_prev_hash = actual_prev_hash
        super().__init__(
            f"FR125: Hash chain broken at sequence {event_sequence} - "
            "chain integrity compromised"
        )
