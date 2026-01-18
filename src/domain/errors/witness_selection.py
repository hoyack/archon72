"""Witness selection domain errors (FR59, FR60, FR61, FR117).

Provides specific exception classes for witness selection failures.
All exceptions inherit from ConstitutionalViolationError as they
represent violations of constitutional requirements.

Constitutional Constraints:
- FR59: Verifiable randomness requirement
- FR60: Witness pair rotation requirement
- FR61: External entropy requirement
- FR117: Witness pool minimum requirement
- NFR57: Halt on entropy failure (not weak randomness)
"""

from datetime import datetime

from src.domain.errors.constitutional import ConstitutionalViolationError


class WitnessSelectionError(ConstitutionalViolationError):
    """Base class for witness selection errors.

    All witness selection errors represent constitutional violations
    related to FR59, FR60, FR61, or FR117.
    """

    pass


class EntropyUnavailableError(WitnessSelectionError):
    """Raised when external entropy source is unavailable (FR61, NFR57).

    Constitutional Constraint (FR61):
    System SHALL use external entropy source for witness selection.

    Constitutional Constraint (NFR57):
    If all entropy fails, witness selection halts rather than using
    weak randomness.

    CRITICAL: When this error is raised, the system MUST halt witness
    selection operations. Using fallback/weak randomness is a constitutional
    violation that compromises the integrity of witness selection.

    Attributes:
        source_identifier: The entropy source that failed
        reason: Reason for failure (if known)
    """

    def __init__(
        self,
        source_identifier: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Initialize entropy unavailable error.

        Args:
            source_identifier: The entropy source that failed
            reason: Reason for failure (if known)
        """
        self.source_identifier = source_identifier
        self.reason = reason

        parts = ["FR61: External entropy unavailable - witness selection halted"]
        if source_identifier:
            parts.append(f"(source: {source_identifier})")
        if reason:
            parts.append(f"(reason: {reason})")

        message = " ".join(parts)
        super().__init__(message)


class WitnessPairRotationViolationError(WitnessSelectionError):
    """Raised when witness pair rotation constraint is violated (FR60).

    Constitutional Constraint (FR60):
    No witness pair SHALL appear consecutively more than once per 24-hour period.

    This error indicates that the requested witness pair has already
    appeared within the rotation window and cannot be used again.

    Attributes:
        pair_key: The canonical pair key (e.g., "WITNESS:abc:WITNESS:xyz")
        last_appearance: When the pair last appeared
    """

    def __init__(
        self,
        pair_key: str,
        last_appearance: datetime,
    ) -> None:
        """Initialize pair rotation violation error.

        Args:
            pair_key: The canonical pair key
            last_appearance: When the pair last appeared
        """
        self.pair_key = pair_key
        self.last_appearance = last_appearance

        message = (
            f"FR60: Witness pair {pair_key} appeared within 24 hours "
            f"(last: {last_appearance.isoformat()})"
        )
        super().__init__(message)


class WitnessSelectionVerificationError(WitnessSelectionError):
    """Raised when witness selection verification fails (FR59).

    Constitutional Constraint (FR59):
    System SHALL select witnesses using verifiable randomness seeded
    from previous hash chain state.

    This error indicates that re-running the selection algorithm
    with the recorded seed does not produce the same witness as
    was recorded. This may indicate:
    1. Tampering with the selection record
    2. Algorithm implementation mismatch
    3. Data corruption

    Attributes:
        expected_witness: The witness ID recorded in the selection
        computed_witness: The witness ID computed from the seed
    """

    def __init__(
        self,
        expected_witness: str,
        computed_witness: str,
    ) -> None:
        """Initialize verification error.

        Args:
            expected_witness: The witness ID that was recorded
            computed_witness: The witness ID computed by verification
        """
        self.expected_witness = expected_witness
        self.computed_witness = computed_witness

        message = (
            f"FR59: Witness selection verification failed - "
            f"expected {expected_witness}, computed {computed_witness}"
        )
        super().__init__(message)


class InsufficientWitnessPoolError(WitnessSelectionError):
    """Raised when witness pool is below minimum (FR117).

    Constitutional Constraint (FR117):
    If witness pool <12, continue only for low-stakes events;
    high-stakes events (override, dissolution, ceremonies) pause
    until restored. Degraded mode publicly surfaced.

    Attributes:
        available: Number of available witnesses
        minimum_required: Minimum required for the operation
        operation_type: Type of operation attempted (e.g., "high-stakes", "standard")
    """

    def __init__(
        self,
        available: int,
        minimum_required: int,
        operation_type: str = "standard",
    ) -> None:
        """Initialize insufficient pool error.

        Args:
            available: Number of available witnesses
            minimum_required: Minimum required for the operation
            operation_type: Type of operation attempted
        """
        self.available = available
        self.minimum_required = minimum_required
        self.operation_type = operation_type

        message = (
            f"FR117: Witness pool below minimum for {operation_type} operation "
            f"({available} < {minimum_required})"
        )
        super().__init__(message)


class AllWitnessesPairExhaustedError(WitnessSelectionError):
    """Raised when all witnesses would violate pair rotation (FR60).

    This error indicates that after attempting all witnesses in the pool,
    every possible selection would violate the FR60 pair rotation constraint.
    This is a rare edge case that indicates the pool may be too small or
    witness selection is happening too frequently.

    Attributes:
        pool_size: Number of witnesses in the pool
        attempts_made: Number of selection attempts made
    """

    def __init__(
        self,
        pool_size: int,
        attempts_made: int,
    ) -> None:
        """Initialize exhausted error.

        Args:
            pool_size: Number of witnesses in the pool
            attempts_made: Number of selection attempts made
        """
        self.pool_size = pool_size
        self.attempts_made = attempts_made

        message = (
            f"FR60: All {pool_size} witnesses would violate pair rotation "
            f"after {attempts_made} attempts - pool may be too small"
        )
        super().__init__(message)
