"""In-memory stub implementation of RecommendationSubmissionProtocol (Story 4.4).

This module provides an in-memory implementation for testing purposes.
Not intended for production use.

Constitutional Constraints:
- FR-4.6: Knight SHALL submit recommendation with mandatory rationale [P0]
- NFR-5.2: Authorization: Only assigned Knight can submit recommendation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.domain.errors.recommendation import (
    RationaleRequiredError,
    RecommendationAlreadySubmittedError,
    ReferralNotInReviewError,
    UnauthorizedRecommendationError,
)
from src.domain.errors.referral import ReferralNotFoundError
from src.domain.models.referral import Referral, ReferralRecommendation, ReferralStatus

# Minimum rationale length (mirrored from service)
MIN_RATIONALE_LENGTH: int = 10


class RecommendationSubmissionStub:
    """In-memory stub implementation of RecommendationSubmissionProtocol.

    Provides configurable behavior for testing recommendation submission.
    Can be configured to return specific referrals or raise specific errors.

    Example:
        >>> stub = RecommendationSubmissionStub()
        >>> stub.set_referral(referral)
        >>> result = await stub.submit(
        ...     referral.referral_id,
        ...     knight_id,
        ...     ReferralRecommendation.ACKNOWLEDGE,
        ...     "Valid rationale text",
        ... )
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        # Maps referral_id -> Referral
        self._referrals: dict[UUID, Referral] = {}
        # Track submit calls for verification
        self._submit_calls: list[tuple[UUID, UUID, ReferralRecommendation, str]] = []
        # Track routing calls for verification
        self._acknowledgment_routes: list[UUID] = []
        self._escalation_routes: list[UUID] = []

    def set_referral(self, referral: Referral) -> None:
        """Configure a referral to be used for testing.

        Args:
            referral: The referral to store.
        """
        self._referrals[referral.referral_id] = referral

    def create_test_referral(
        self,
        referral_id: UUID | None = None,
        petition_id: UUID | None = None,
        realm_id: UUID | None = None,
        knight_id: UUID | None = None,
        status: ReferralStatus = ReferralStatus.IN_REVIEW,
    ) -> Referral:
        """Create and store a test referral with sensible defaults.

        Args:
            referral_id: Optional referral UUID.
            petition_id: Optional petition UUID.
            realm_id: Optional realm UUID.
            knight_id: Optional knight UUID.
            status: Referral status (default IN_REVIEW).

        Returns:
            The created Referral.
        """
        now = datetime.now(timezone.utc)
        referral = Referral(
            referral_id=referral_id or uuid4(),
            petition_id=petition_id or uuid4(),
            realm_id=realm_id or uuid4(),
            assigned_knight_id=knight_id,
            status=status,
            deadline=now + timedelta(weeks=3),
            extensions_granted=0,
            created_at=now,
        )
        self._referrals[referral.referral_id] = referral
        return referral

    async def submit(
        self,
        referral_id: UUID,
        requester_id: UUID,
        recommendation: ReferralRecommendation,
        rationale: str,
    ) -> Referral:
        """Submit a Knight's recommendation for a referral.

        Args:
            referral_id: The referral to submit recommendation for.
            requester_id: The UUID of the requester (must be assigned Knight).
            recommendation: The Knight's recommendation.
            rationale: The Knight's rationale.

        Returns:
            The updated Referral with recommendation recorded.

        Raises:
            ReferralNotFoundError: Referral doesn't exist.
            UnauthorizedRecommendationError: Requester is not the assigned Knight.
            ReferralNotInReviewError: Referral is not in IN_REVIEW state.
            RationaleRequiredError: Rationale is empty or too short.
            RecommendationAlreadySubmittedError: Referral already has recommendation.
        """
        self._submit_calls.append(
            (referral_id, requester_id, recommendation, rationale)
        )

        # Validate rationale
        trimmed_rationale = rationale.strip() if rationale else ""
        if len(trimmed_rationale) < MIN_RATIONALE_LENGTH:
            raise RationaleRequiredError(
                provided_length=len(trimmed_rationale),
                min_length=MIN_RATIONALE_LENGTH,
            )

        # Check if referral exists
        if referral_id not in self._referrals:
            raise ReferralNotFoundError(referral_id=referral_id)

        referral = self._referrals[referral_id]

        # Check for already submitted recommendation
        if referral.status == ReferralStatus.COMPLETED:
            raise RecommendationAlreadySubmittedError(
                referral_id=referral_id,
                existing_recommendation=referral.recommendation.value
                if referral.recommendation
                else None,
            )

        # Check referral status
        if referral.status != ReferralStatus.IN_REVIEW:
            raise ReferralNotInReviewError(
                referral_id=referral_id,
                current_status=referral.status.value,
            )

        # Check authorization
        if referral.assigned_knight_id is None:
            raise UnauthorizedRecommendationError(
                referral_id=referral_id,
                requester_id=requester_id,
            )

        if requester_id != referral.assigned_knight_id:
            raise UnauthorizedRecommendationError(
                referral_id=referral_id,
                requester_id=requester_id,
                assigned_knight_id=referral.assigned_knight_id,
            )

        # Update referral with recommendation
        completed_at = datetime.now(timezone.utc)
        updated_referral = referral.with_recommendation(
            recommendation=recommendation,
            rationale=trimmed_rationale,
            completed_at=completed_at,
        )

        # Update stored referral (not create new - it already exists)
        self._referrals[referral_id] = updated_referral

        # Track routing
        if recommendation == ReferralRecommendation.ACKNOWLEDGE:
            self._acknowledgment_routes.append(referral.petition_id)
        elif recommendation == ReferralRecommendation.ESCALATE:
            self._escalation_routes.append(referral.petition_id)

        return updated_referral

    def get_submit_calls(self) -> list[tuple[UUID, UUID, ReferralRecommendation, str]]:
        """Return list of submit calls made for verification."""
        return self._submit_calls.copy()

    def get_acknowledgment_routes(self) -> list[UUID]:
        """Return list of petition IDs routed to acknowledgment."""
        return self._acknowledgment_routes.copy()

    def get_escalation_routes(self) -> list[UUID]:
        """Return list of petition IDs routed to escalation."""
        return self._escalation_routes.copy()

    def get_referral(self, referral_id: UUID) -> Referral | None:
        """Get a referral by ID.

        Args:
            referral_id: The referral UUID.

        Returns:
            The Referral if found, None otherwise.
        """
        return self._referrals.get(referral_id)

    def clear(self) -> None:
        """Clear all stored data. For testing only."""
        self._referrals.clear()
        self._submit_calls.clear()
        self._acknowledgment_routes.clear()
        self._escalation_routes.clear()
