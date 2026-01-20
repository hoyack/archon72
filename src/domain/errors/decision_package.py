"""Decision package domain errors (Story 4.3, FR-4.3, NFR-5.2).

This module defines domain-specific exceptions for decision package building.

Constitutional Constraints:
- FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
- NFR-5.2: Authorization: Only assigned Knight can access package
- CT-12: Every access attempt must be traceable for accountability
"""

from __future__ import annotations

from uuid import UUID


class DecisionPackageError(Exception):
    """Base exception for decision package-related errors."""

    pass


class UnauthorizedPackageAccessError(DecisionPackageError):
    """Raised when a requester is not authorized to access a decision package.

    Per NFR-5.2, only the assigned Knight can access the decision package.
    This error is raised when:
    - The requester_id does not match the assigned_knight_id
    - The referral is not in ASSIGNED or IN_REVIEW state

    Constitutional Constraints:
    - NFR-5.2: Authorization: Only assigned Knight can access package
    """

    def __init__(
        self,
        referral_id: UUID,
        requester_id: UUID,
        assigned_knight_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID being accessed.
            requester_id: The UUID of the requester.
            assigned_knight_id: The UUID of the assigned Knight (if known).
            reason: Optional additional reason for denial.
        """
        self.referral_id = referral_id
        self.requester_id = requester_id
        self.assigned_knight_id = assigned_knight_id
        self.reason = reason

        if assigned_knight_id:
            msg = (
                f"Unauthorized access to decision package for referral {referral_id}: "
                f"requester {requester_id} is not assigned Knight {assigned_knight_id}"
            )
        elif reason:
            msg = (
                f"Unauthorized access to decision package for referral {referral_id}: "
                f"{reason}"
            )
        else:
            msg = f"Unauthorized access to decision package for referral {referral_id}"

        super().__init__(msg)


class DecisionPackageNotFoundError(DecisionPackageError):
    """Raised when a decision package cannot be built due to missing data.

    This error is raised when:
    - The referral does not exist
    - The associated petition does not exist (data consistency issue)
    """

    def __init__(
        self,
        referral_id: UUID | None = None,
        petition_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID being looked up.
            petition_id: The petition UUID being looked up.
            reason: Optional reason why the package cannot be built.
        """
        self.referral_id = referral_id
        self.petition_id = petition_id
        self.reason = reason

        if referral_id and reason:
            msg = f"Cannot build decision package for referral {referral_id}: {reason}"
        elif referral_id:
            msg = f"Referral not found: {referral_id}"
        elif petition_id:
            msg = f"Petition not found for referral: {petition_id}"
        else:
            msg = "Cannot build decision package: missing data"

        super().__init__(msg)


class ReferralNotAssignedError(DecisionPackageError):
    """Raised when a referral is not in a state that allows package access.

    Per FR-4.3, decision packages are only available for referrals that
    are in ASSIGNED or IN_REVIEW state. This error is raised when:
    - Referral is still PENDING (not yet assigned to a Knight)
    - Referral is COMPLETED (already has a recommendation)
    - Referral is EXPIRED (deadline passed)
    """

    def __init__(
        self,
        referral_id: UUID,
        current_status: str,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            current_status: The current status of the referral.
        """
        self.referral_id = referral_id
        self.current_status = current_status
        super().__init__(
            f"Referral {referral_id} is not in a state that allows package access: "
            f"current status is {current_status}, expected ASSIGNED or IN_REVIEW"
        )
