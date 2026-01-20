"""Recommendation submission protocol (Story 4.4, FR-4.6, NFR-5.2).

This module defines the protocol for submitting Knight recommendations.
Follows hexagonal architecture with port/adapter pattern.

Constitutional Constraints:
- FR-4.6: Knight SHALL submit recommendation with mandatory rationale [P0]
- NFR-5.2: Authorization: Only assigned Knight can submit recommendation
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
- CT-12: Every action that affects an Archon must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before writes
2. AUTHORIZATION FIRST - Verify Knight assignment before submission
3. WITNESS EVERYTHING - All submissions require witness hash
4. FAIL LOUD - Raise appropriate errors for invalid submissions
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.domain.models.referral import Referral, ReferralRecommendation


class RecommendationSubmissionProtocol(Protocol):
    """Protocol for submitting Knight recommendations (FR-4.6).

    This protocol defines the contract for submitting a Knight's recommendation
    on a referred petition. The recommendation determines the next step:
    - ACKNOWLEDGE: Routes to Epic 3 acknowledgment execution
    - ESCALATE: Routes to Epic 6 King escalation queue

    The submitter must:
    1. Validate requester authorization (NFR-5.2)
    2. Verify referral is in IN_REVIEW state
    3. Validate rationale meets minimum requirements (10 chars)
    4. Record recommendation with witness hash (CT-12)
    5. Cancel deadline job
    6. Route petition based on recommendation

    Constitutional Constraints:
    - FR-4.6: Knight SHALL submit recommendation with mandatory rationale [P0]
    - NFR-5.2: Authorization: Only assigned Knight can submit recommendation
    - NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
    - CT-12: Every action that affects an Archon must be witnessed

    From PRD Section 8.3 - Recommendation:
    - Knight's formal response: ACKNOWLEDGE or ESCALATE
    - Mandatory rationale required for all recommendations
    - Routes petition to next step based on recommendation

    From PRD Section 15.4 - The Knight Journey:
    ```
    Review petition + related context → Formulate recommendation
        → Submit recommendation with rationale → Petition proceeds to next fate
    ```
    """

    @abstractmethod
    async def submit(
        self,
        referral_id: UUID,
        requester_id: UUID,
        recommendation: ReferralRecommendation,
        rationale: str,
    ) -> Referral:
        """Submit a Knight's recommendation for a referral.

        This is the main entry point for recommendation submission.
        The method performs authorization checks, validates the rationale,
        records the recommendation with witness hash, cancels the deadline job,
        and routes the petition based on the recommendation.

        Authorization Requirements (NFR-5.2):
        - requester_id MUST match the assigned_knight_id on the referral
        - Referral MUST be in IN_REVIEW state

        Rationale Requirements (FR-4.6):
        - rationale MUST NOT be empty
        - rationale MUST be at least 10 characters

        Args:
            referral_id: The referral to submit recommendation for.
            requester_id: The UUID of the requester (must be assigned Knight).
            recommendation: The Knight's recommendation (ACKNOWLEDGE or ESCALATE).
            rationale: The Knight's rationale explaining the decision.

        Returns:
            The updated Referral with recommendation recorded and status COMPLETED.

        Raises:
            ReferralNotFoundError: Referral doesn't exist.
            UnauthorizedRecommendationError: Requester is not the assigned Knight.
            ReferralNotInReviewError: Referral is not in IN_REVIEW state.
            RationaleRequiredError: Rationale is empty or too short.
            RecommendationAlreadySubmittedError: Referral already has recommendation.
            SystemHaltedError: System is in halt state.
        """
        ...
