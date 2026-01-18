"""Cessation domain errors (Story 6.3, FR32).

This module provides exception classes for cessation consideration operations.
All errors include FR32 reference for traceability.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → Errors must be logged
- CT-13: Integrity outranks availability → Fail loud, not silent
"""

from __future__ import annotations

from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


class CessationError(ConstitutionalViolationError):
    """Base error for cessation consideration operations (FR32).

    All cessation errors inherit from this class, enabling:
    - Unified exception handling for cessation operations
    - Constitutional violation tracking
    - FR32 compliance traceability
    """

    pass


class CessationAlreadyTriggeredError(CessationError):
    """Raised when cessation consideration is already active (FR32).

    This error indicates an attempt to create a duplicate cessation
    consideration when one is already pending a Conclave decision.

    Note: This error is intentionally NOT raised by CessationConsiderationService.
    The service uses idempotent design - returning None instead of raising errors
    when a consideration already exists. This error class is retained for:
    - API layer validation where explicit errors are preferred
    - Future use cases requiring strict duplicate detection
    - Alternative service implementations with different error semantics

    Attributes:
        consideration_id: The ID of the already-active consideration.
    """

    def __init__(self, consideration_id: UUID) -> None:
        """Initialize error with the active consideration ID.

        Args:
            consideration_id: The ID of the existing active consideration.
        """
        self.consideration_id = consideration_id
        super().__init__(
            f"FR32: Cessation consideration already triggered. "
            f"Active consideration: {consideration_id}"
        )


class CessationConsiderationNotFoundError(CessationError):
    """Raised when a cessation consideration cannot be found (FR32).

    This error indicates an attempt to access or decide on a
    consideration that does not exist.

    Attributes:
        consideration_id: The ID that was not found.
    """

    def __init__(self, consideration_id: UUID) -> None:
        """Initialize error with the missing consideration ID.

        Args:
            consideration_id: The ID that could not be found.
        """
        self.consideration_id = consideration_id
        super().__init__(f"FR32: Cessation consideration not found: {consideration_id}")


class InvalidCessationDecisionError(CessationError):
    """Raised when a cessation decision operation is invalid (FR32).

    This error indicates an attempt to record a decision that cannot
    be processed, such as:
    - Decision already recorded for consideration
    - Invalid decision state transition
    - Unauthorized decision attempt

    Attributes:
        consideration_id: The ID of the consideration.
        reason: The reason the decision is invalid.
    """

    def __init__(self, consideration_id: UUID, reason: str) -> None:
        """Initialize error with consideration ID and reason.

        Args:
            consideration_id: The ID of the consideration.
            reason: The reason the decision is invalid.
        """
        self.consideration_id = consideration_id
        self.reason = reason
        super().__init__(
            f"FR32: Invalid cessation decision for {consideration_id}: {reason}"
        )


class BelowThresholdError(CessationError):
    """Raised when breach count is below cessation threshold (FR32).

    This error indicates an attempt to trigger cessation consideration
    when the breach count has not exceeded the required threshold.

    Per FR32: >10 unacknowledged breaches in 90 days triggers cessation.
    This error is raised when count <= 10.

    Note: This error is intentionally NOT raised by CessationConsiderationService.
    The service uses idempotent design - returning None instead of raising errors
    when the threshold is not met. This error class is retained for:
    - API layer validation where explicit errors are preferred
    - Manual cessation trigger attempts requiring threshold validation
    - Alternative service implementations with different error semantics

    Attributes:
        current_count: The current breach count.
        threshold: The threshold that must be exceeded (10).
    """

    def __init__(self, current_count: int, threshold: int) -> None:
        """Initialize error with counts.

        Args:
            current_count: The current unacknowledged breach count.
            threshold: The threshold that must be exceeded (10).
        """
        self.current_count = current_count
        self.threshold = threshold
        super().__init__(
            f"FR32: Breach count ({current_count}) does not exceed "
            f"cessation threshold ({threshold}). "
            f"Cessation requires >{threshold} unacknowledged breaches in 90 days."
        )
