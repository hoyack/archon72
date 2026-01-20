"""Recommendation domain errors (Story 4.4, FR-4.6, NFR-5.2).

This module defines domain-specific exceptions for recommendation submission.

Constitutional Constraints:
- FR-4.6: Knight SHALL submit recommendation with mandatory rationale [P0]
- NFR-5.2: Authorization: Only assigned Knight can submit recommendation
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
- CT-12: Every action that affects an Archon must be witnessed
"""

from __future__ import annotations

from uuid import UUID


class RecommendationError(Exception):
    """Base exception for recommendation-related errors."""

    pass


class InvalidRecommendationError(RecommendationError):
    """Raised when an invalid recommendation value is provided.

    The recommendation must be a valid ReferralRecommendation enum value
    (ACKNOWLEDGE or ESCALATE).
    """

    def __init__(
        self,
        value: str,
        allowed_values: list[str] | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            value: The invalid recommendation value.
            allowed_values: Optional list of allowed values.
        """
        self.value = value
        self.allowed_values = allowed_values or ["acknowledge", "escalate"]
        msg = f"Invalid recommendation value: '{value}'. Must be one of: {self.allowed_values}"
        super().__init__(msg)


class RationaleRequiredError(RecommendationError):
    """Raised when rationale is missing or too short (FR-4.6).

    Per FR-4.6, Knight SHALL submit recommendation with mandatory rationale.
    The rationale must be at least 10 characters to ensure meaningful explanation.
    """

    MIN_RATIONALE_LENGTH = 10

    def __init__(
        self,
        provided_length: int,
        min_length: int | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            provided_length: The length of the provided rationale.
            min_length: The minimum required length (defaults to MIN_RATIONALE_LENGTH).
        """
        self.provided_length = provided_length
        self.min_length = min_length or self.MIN_RATIONALE_LENGTH
        if provided_length == 0:
            msg = (
                f"Rationale is required. Must be at least {self.min_length} characters."
            )
        else:
            msg = (
                f"Rationale too short: {provided_length} characters provided, "
                f"minimum {self.min_length} required."
            )
        super().__init__(msg)


class UnauthorizedRecommendationError(RecommendationError):
    """Raised when requester is not authorized to submit recommendation (NFR-5.2).

    Per NFR-5.2, only the assigned Knight can submit a recommendation
    for a referral.
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
            f"Unauthorized recommendation submission for referral {referral_id}: "
            f"requester {requester_id} is not the assigned Knight"
        )
        if assigned_knight_id:
            msg += f" (assigned: {assigned_knight_id})"
        super().__init__(msg)


class ReferralNotInReviewError(RecommendationError):
    """Raised when referral is not in IN_REVIEW status.

    Recommendations can only be submitted when the referral is actively
    being reviewed by the Knight.
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
            f"Cannot submit recommendation for referral {referral_id}: "
            f"status must be IN_REVIEW, got {current_status}"
        )


class RecommendationAlreadySubmittedError(RecommendationError):
    """Raised when attempting to submit recommendation for completed referral.

    Once a recommendation is submitted, the referral is in COMPLETED status
    and cannot accept another recommendation.
    """

    def __init__(
        self,
        referral_id: UUID,
        existing_recommendation: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            referral_id: The referral UUID.
            existing_recommendation: The existing recommendation if known.
        """
        self.referral_id = referral_id
        self.existing_recommendation = existing_recommendation
        msg = f"Recommendation already submitted for referral {referral_id}"
        if existing_recommendation:
            msg += f" (recommendation: {existing_recommendation})"
        super().__init__(msg)
