"""Decision package builder protocol (Story 4.3, FR-4.3, NFR-5.2).

This module defines the protocol for building decision packages for Knights.
Follows hexagonal architecture with port/adapter pattern.

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

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.domain.models.decision_package import DecisionPackage


class DecisionPackageBuilderProtocol(Protocol):
    """Protocol for building Knight decision packages (FR-4.3).

    This protocol defines the contract for assembling decision packages
    that contain all context a Knight needs to review a referred petition.

    The builder must:
    1. Validate requester authorization (NFR-5.2)
    2. Verify referral exists and is in valid state
    3. Assemble context from multiple sources
    4. Return immutable DecisionPackage

    Constitutional Constraints:
    - FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
    - STK-4: Knight: "I receive referrals with sufficient context" [P1]
    - NFR-5.2: Authorization: Only assigned Knight can access package
    - CT-13: Read-only operations work during halt

    From PRD Section 8.3 - Decision Package:
    - Bundled context for Knight/King review
    - Includes: petition text, co-signer count, related petitions, submitter history

    From PRD Section 15.4 - The Knight Journey:
    - Receive referral notification → Access decision package
    - Review petition + related context → Formulate recommendation
    """

    @abstractmethod
    async def build(
        self,
        referral_id: UUID,
        requester_id: UUID,
    ) -> DecisionPackage:
        """Build a decision package for a referral.

        This is the main entry point for building decision packages.
        The method performs authorization checks and assembles all
        context the Knight needs for their review.

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
        ...
