"""Referral domain errors (Story 4.2, FR-4.1, FR-4.2).

This module defines domain-specific exceptions for referral execution.

Constitutional Constraints:
- FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
- FR-4.2: System SHALL assign referral deadline (3 cycles default)
- NFR-3.4: Referral timeout reliability: 100% timeouts fire
- CT-12: Every action that affects an Archon must be witnessed
"""

from __future__ import annotations

from uuid import UUID


class ReferralError(Exception):
    """Base exception for referral-related errors."""

    pass


class ReferralAlreadyExistsError(ReferralError):
    """Raised when a referral already exists for a petition.

    This is NOT an error in normal operation - it's used for idempotency.
    The caller should retrieve the existing referral.
    """

    def __init__(
        self,
        petition_id: UUID,
        existing_referral_id: UUID | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition UUID.
            existing_referral_id: The existing referral UUID if known.
        """
        self.petition_id = petition_id
        self.existing_referral_id = existing_referral_id
        msg = f"Referral already exists for petition {petition_id}"
        if existing_referral_id:
            msg += f" (referral_id={existing_referral_id})"
        super().__init__(msg)


class ReferralNotFoundError(ReferralError):
    """Raised when a referral is not found.

    This error is raised when attempting to access or modify
    a referral that does not exist.
    """

    def __init__(
        self,
        referral_id: UUID | None = None,
        petition_id: UUID | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID being looked up.
            petition_id: The petition UUID being looked up.
        """
        self.referral_id = referral_id
        self.petition_id = petition_id

        if referral_id:
            msg = f"Referral not found: {referral_id}"
        elif petition_id:
            msg = f"No referral found for petition: {petition_id}"
        else:
            msg = "Referral not found"
        super().__init__(msg)


class PetitionNotReferrableError(ReferralError):
    """Raised when a petition cannot be referred.

    A petition must be in DELIBERATING state to be referred.
    """

    def __init__(
        self,
        petition_id: UUID,
        current_state: str,
    ) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition UUID.
            current_state: The current state of the petition.
        """
        self.petition_id = petition_id
        self.current_state = current_state
        super().__init__(
            f"Petition {petition_id} cannot be referred: "
            f"current state is {current_state}, expected DELIBERATING"
        )


class InvalidRealmError(ReferralError):
    """Raised when a realm_id is invalid.

    The realm_id must be a valid UUID from the realm registry.
    """

    def __init__(
        self,
        realm_id: UUID,
        reason: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            realm_id: The invalid realm UUID.
            reason: Optional reason why it's invalid.
        """
        self.realm_id = realm_id
        self.reason = reason
        msg = f"Invalid realm_id: {realm_id}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class ReferralWitnessHashError(ReferralError):
    """Raised when witness hash generation fails.

    Per CT-12, every referral must be witnessed. If hash
    generation fails, the referral cannot be created.
    """

    def __init__(
        self,
        petition_id: UUID,
        reason: str,
    ) -> None:
        """Initialize the error.

        Args:
            petition_id: The petition UUID.
            reason: Why hash generation failed.
        """
        self.petition_id = petition_id
        self.reason = reason
        super().__init__(
            f"Failed to generate witness hash for referral "
            f"(petition_id={petition_id}): {reason}"
        )


class ReferralJobSchedulingError(ReferralError):
    """Raised when deadline job scheduling fails.

    Per HP-1 and NFR-3.4, referral deadline jobs must be scheduled
    reliably. If scheduling fails, the referral cannot be created.
    """

    def __init__(
        self,
        referral_id: UUID,
        reason: str,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            reason: Why scheduling failed.
        """
        self.referral_id = referral_id
        self.reason = reason
        super().__init__(
            f"Failed to schedule deadline job for referral {referral_id}: {reason}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Extension Request Errors (Story 4.5, FR-4.4)
# ═══════════════════════════════════════════════════════════════════════════════


class MaxExtensionsReachedError(ReferralError):
    """Raised when maximum extensions (2) have been used (FR-4.4).

    Per FR-4.4, Knights can request a maximum of 2 deadline extensions.
    Once both extensions are used, no further extensions are allowed.
    """

    MAX_EXTENSIONS = 2

    def __init__(
        self,
        referral_id: UUID,
        extensions_granted: int,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            extensions_granted: Current number of extensions granted.
        """
        self.referral_id = referral_id
        self.extensions_granted = extensions_granted
        super().__init__(
            f"Maximum extensions reached for referral {referral_id}: "
            f"{extensions_granted}/{self.MAX_EXTENSIONS} extensions used"
        )


class NotAssignedKnightError(ReferralError):
    """Raised when requester is not the assigned Knight (NFR-5.2).

    Per NFR-5.2, only the assigned Knight can request extensions
    or submit recommendations for a referral.
    """

    def __init__(
        self,
        referral_id: UUID,
        requester_id: UUID,
        assigned_knight_id: UUID | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            requester_id: The requester's UUID who attempted the action.
            assigned_knight_id: The actually assigned Knight's UUID.
        """
        self.referral_id = referral_id
        self.requester_id = requester_id
        self.assigned_knight_id = assigned_knight_id
        msg = (
            f"Not authorized for referral {referral_id}: "
            f"requester {requester_id} is not the assigned Knight"
        )
        if assigned_knight_id:
            msg += f" (assigned: {assigned_knight_id})"
        super().__init__(msg)


class InvalidReferralStateError(ReferralError):
    """Raised when referral is not in a valid state for the operation.

    Different operations require different referral states:
    - Extension request: ASSIGNED or IN_REVIEW
    - Recommendation submission: IN_REVIEW
    """

    def __init__(
        self,
        referral_id: UUID,
        current_status: str,
        required_statuses: list[str] | None = None,
        operation: str = "operation",
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            current_status: The current status of the referral.
            required_statuses: List of valid statuses for the operation.
            operation: Description of the attempted operation.
        """
        self.referral_id = referral_id
        self.current_status = current_status
        self.required_statuses = required_statuses or []
        self.operation = operation

        if required_statuses:
            required_str = " or ".join(required_statuses)
            msg = (
                f"Cannot perform {operation} on referral {referral_id}: "
                f"status must be {required_str}, got {current_status}"
            )
        else:
            msg = (
                f"Cannot perform {operation} on referral {referral_id}: "
                f"invalid state {current_status}"
            )
        super().__init__(msg)


class ExtensionReasonRequiredError(ReferralError):
    """Raised when extension reason is missing or too short.

    Extension requests must include a reason explaining why
    additional time is needed.
    """

    MIN_REASON_LENGTH = 10

    def __init__(
        self,
        referral_id: UUID,
        provided_length: int,
        min_length: int | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            provided_length: The length of the provided reason.
            min_length: The minimum required length.
        """
        self.referral_id = referral_id
        self.provided_length = provided_length
        self.min_length = min_length or self.MIN_REASON_LENGTH

        if provided_length == 0:
            msg = (
                f"Extension reason required for referral {referral_id}. "
                f"Must be at least {self.min_length} characters."
            )
        else:
            msg = (
                f"Extension reason too short for referral {referral_id}: "
                f"{provided_length} characters provided, minimum {self.min_length} required."
            )
        super().__init__(msg)
