"""Witness anomaly domain errors (Story 6.6, FR116-FR117).

Provides specific exception classes for witness anomaly detection failures.
All exceptions inherit from ConstitutionalViolationError as they
represent violations of constitutional requirements.

Constitutional Constraints:
- FR116: System SHALL detect patterns of witness unavailability affecting
         same witnesses repeatedly; pattern triggers security review
- FR117: If witness pool <12, continue only for low-stakes events;
         high-stakes events pause until restored
"""

from datetime import datetime

from src.domain.errors.constitutional import ConstitutionalViolationError


class WitnessAnomalyError(ConstitutionalViolationError):
    """Base class for witness anomaly errors.

    All witness anomaly errors represent constitutional violations
    related to FR116 or FR117.
    """

    pass


class WitnessCollusionSuspectedError(WitnessAnomalyError):
    """Raised when witness collusion patterns are detected (FR116).

    Constitutional Constraint (FR116):
    System SHALL detect patterns of witness unavailability affecting
    same witnesses repeatedly; pattern triggers security review.

    This error indicates that statistical analysis has detected
    anomalous co-occurrence patterns suggesting potential collusion.

    Attributes:
        witnesses: Tuple of witness IDs involved in the suspected collusion
        confidence: Confidence score (0.0 to 1.0) of the collusion detection
    """

    def __init__(
        self,
        witnesses: tuple[str, ...],
        confidence: float,
    ) -> None:
        """Initialize collusion suspected error.

        Args:
            witnesses: Tuple of witness IDs involved
            confidence: Confidence score of detection (0.0 to 1.0)
        """
        self.witnesses = witnesses
        self.confidence = confidence

        witness_list = ", ".join(witnesses)
        message = (
            f"FR116: Witness collusion suspected - pair excluded from selection "
            f"(witnesses: [{witness_list}], confidence: {confidence:.2f})"
        )
        super().__init__(message)


class WitnessPairExcludedError(WitnessAnomalyError):
    """Raised when attempting to use an excluded witness pair (FR116).

    This error indicates that a witness pair has been temporarily
    excluded from selection due to anomaly detection, pending human review.

    Attributes:
        pair_key: The canonical pair key (e.g., "WITNESS:abc:WITNESS:xyz")
        excluded_until: When the exclusion expires
    """

    def __init__(
        self,
        pair_key: str,
        excluded_until: datetime,
    ) -> None:
        """Initialize pair excluded error.

        Args:
            pair_key: The canonical pair key
            excluded_until: When the exclusion expires
        """
        self.pair_key = pair_key
        self.excluded_until = excluded_until

        message = (
            f"FR116: Witness pair {pair_key} temporarily excluded due to anomaly "
            f"(until: {excluded_until.isoformat()})"
        )
        super().__init__(message)


class WitnessUnavailabilityPatternError(WitnessAnomalyError):
    """Raised when unavailability patterns are detected (FR116).

    Constitutional Constraint (FR116):
    System SHALL detect patterns of witness unavailability affecting
    same witnesses repeatedly; pattern triggers security review.

    This error indicates that the same witnesses have been repeatedly
    unavailable, which may indicate targeted DoS or manipulation.

    Attributes:
        witness_ids: Tuple of witness IDs showing the pattern
        unavailable_count: Number of unavailability events detected
    """

    def __init__(
        self,
        witness_ids: tuple[str, ...],
        unavailable_count: int,
    ) -> None:
        """Initialize unavailability pattern error.

        Args:
            witness_ids: Tuple of witness IDs affected
            unavailable_count: Number of unavailability events
        """
        self.witness_ids = witness_ids
        self.unavailable_count = unavailable_count

        witness_list = ", ".join(witness_ids)
        message = (
            f"FR116: Unavailability pattern detected - security review triggered "
            f"(witnesses: [{witness_list}], unavailable_count: {unavailable_count})"
        )
        super().__init__(message)


class WitnessPoolDegradedError(WitnessAnomalyError):
    """Raised when witness pool is degraded (FR117).

    Constitutional Constraint (FR117):
    If witness pool <12, continue only for low-stakes events;
    high-stakes events pause until restored. Degraded mode publicly surfaced.

    Attributes:
        available: Number of available witnesses (excluding excluded)
        minimum_required: Minimum required for the operation
        excluded_count: Number of witnesses excluded due to anomalies
        operation_type: Type of operation blocked
    """

    def __init__(
        self,
        available: int,
        minimum_required: int,
        excluded_count: int = 0,
        operation_type: str = "high_stakes",
    ) -> None:
        """Initialize pool degraded error.

        Args:
            available: Number of available witnesses
            minimum_required: Minimum required for the operation
            excluded_count: Number of witnesses excluded due to anomalies
            operation_type: Type of operation blocked
        """
        self.available = available
        self.minimum_required = minimum_required
        self.excluded_count = excluded_count
        self.operation_type = operation_type

        message = (
            f"FR117: Witness pool degraded - {operation_type} operations blocked "
            f"({available} available, {minimum_required} required, {excluded_count} excluded)"
        )
        super().__init__(message)


class AnomalyScanError(WitnessAnomalyError):
    """Raised when anomaly scan fails.

    This error indicates that the anomaly scan process itself failed,
    not that an anomaly was detected.

    Attributes:
        reason: Reason for scan failure
        scan_type: Type of scan that failed (e.g., "co_occurrence", "unavailability")
    """

    def __init__(
        self,
        reason: str,
        scan_type: str | None = None,
    ) -> None:
        """Initialize scan error.

        Args:
            reason: Reason for scan failure
            scan_type: Type of scan that failed
        """
        self.reason = reason
        self.scan_type = scan_type

        if scan_type:
            message = f"Anomaly scan failed ({scan_type}): {reason}"
        else:
            message = f"Anomaly scan failed: {reason}"
        super().__init__(message)
