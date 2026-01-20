"""Decision package builder service implementation (Story 4.3, FR-4.3).

This module implements the DecisionPackageBuilderProtocol for assembling
decision packages that Knights need to review referred petitions.

Constitutional Constraints:
- FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
- STK-4: Knight: "I receive referrals with sufficient context" [P1]
- NFR-5.2: Authorization: Only assigned Knight can access package
- CT-13: Read-only operations work during halt

Developer Golden Rules:
1. READS DURING HALT - Decision package is read-only, works during halt (CT-13)
2. AUTHORIZATION FIRST - Verify Knight assignment before building package
3. FAIL LOUD - Raise appropriate errors for invalid access
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from structlog import get_logger

from src.domain.errors.decision_package import (
    DecisionPackageNotFoundError,
    ReferralNotAssignedError,
    UnauthorizedPackageAccessError,
)
from src.domain.models.decision_package import DecisionPackage
from src.domain.models.referral import ReferralStatus

if TYPE_CHECKING:
    from src.application.ports.petition_submission_repository import (
        PetitionSubmissionRepositoryProtocol,
    )
    from src.application.ports.referral_execution import ReferralRepositoryProtocol

logger = get_logger(__name__)


class DecisionPackageBuilderService:
    """Service for building Knight decision packages (Story 4.3).

    Implements the DecisionPackageBuilderProtocol for assembling all
    context a Knight needs to review a referred petition.

    The service ensures:
    1. Requester is the assigned Knight (NFR-5.2)
    2. Referral is in ASSIGNED or IN_REVIEW state
    3. All context is assembled from repositories
    4. Package is returned as immutable dataclass

    Example:
        >>> service = DecisionPackageBuilderService(
        ...     referral_repo=referral_repo,
        ...     petition_repo=petition_repo,
        ... )
        >>> package = await service.build(
        ...     referral_id=referral.referral_id,
        ...     requester_id=knight_id,
        ... )
    """

    def __init__(
        self,
        referral_repo: ReferralRepositoryProtocol,
        petition_repo: PetitionSubmissionRepositoryProtocol,
    ) -> None:
        """Initialize the decision package builder service.

        Args:
            referral_repo: Repository for referral access.
            petition_repo: Repository for petition access.
        """
        self._referral_repo = referral_repo
        self._petition_repo = petition_repo

    async def build(
        self,
        referral_id: UUID,
        requester_id: UUID,
    ) -> DecisionPackage:
        """Build a decision package for a referral.

        Performs authorization checks and assembles all context
        the Knight needs for their review.

        Authorization Requirements (NFR-5.2):
        - requester_id MUST match the assigned_knight_id on the referral
        - Referral MUST be in ASSIGNED or IN_REVIEW state

        Args:
            referral_id: The referral to build a package for.
            requester_id: The UUID of the requester (must be assigned Knight).

        Returns:
            The assembled DecisionPackage with all context.

        Raises:
            DecisionPackageNotFoundError: Referral or petition doesn't exist.
            UnauthorizedPackageAccessError: Requester is not the assigned Knight.
            ReferralNotAssignedError: Referral is not in ASSIGNED or IN_REVIEW state.
        """
        log = logger.bind(
            referral_id=str(referral_id),
            requester_id=str(requester_id),
        )
        log.info("Building decision package")

        # Step 1: Retrieve the referral
        referral = await self._referral_repo.get_by_id(referral_id)
        if referral is None:
            log.warning("Referral not found")
            raise DecisionPackageNotFoundError(referral_id=referral_id)

        # Step 2: Validate referral state
        if referral.status not in (ReferralStatus.ASSIGNED, ReferralStatus.IN_REVIEW):
            log.warning(
                "Referral not in valid state for package access",
                current_status=referral.status.value,
            )
            raise ReferralNotAssignedError(
                referral_id=referral_id,
                current_status=referral.status.value,
            )

        # Step 3: Authorization check (NFR-5.2)
        if referral.assigned_knight_id is None:
            log.warning("Referral has no assigned Knight")
            raise UnauthorizedPackageAccessError(
                referral_id=referral_id,
                requester_id=requester_id,
                reason="Referral has no assigned Knight",
            )

        if requester_id != referral.assigned_knight_id:
            log.warning(
                "Unauthorized access attempt",
                assigned_knight_id=str(referral.assigned_knight_id),
            )
            raise UnauthorizedPackageAccessError(
                referral_id=referral_id,
                requester_id=requester_id,
                assigned_knight_id=referral.assigned_knight_id,
            )

        # Step 4: Retrieve the petition
        petition = await self._petition_repo.get(referral.petition_id)
        if petition is None:
            log.error(
                "Petition not found - data consistency issue",
                petition_id=str(referral.petition_id),
            )
            raise DecisionPackageNotFoundError(
                referral_id=referral_id,
                petition_id=referral.petition_id,
                reason="Associated petition not found (data consistency issue)",
            )

        # Step 5: Build the decision package
        now = datetime.now(timezone.utc)
        package = DecisionPackage(
            referral_id=referral.referral_id,
            petition_id=referral.petition_id,
            realm_id=referral.realm_id,
            assigned_knight_id=referral.assigned_knight_id,
            deadline=referral.deadline,
            status=referral.status,
            extensions_granted=referral.extensions_granted,
            can_extend=referral.can_extend(),
            petition_text=petition.text,
            petition_type=petition.type,
            petition_created_at=petition.created_at,
            submitter_id=petition.submitter_id,
            co_signer_count=petition.co_signer_count,
            built_at=now,
        )

        log.info(
            "Decision package built successfully",
            petition_type=petition.type.value,
            deadline=referral.deadline.isoformat(),
        )

        return package
