"""Decision package domain model (Story 4.3, FR-4.3).

This module defines the decision package model that bundles all context
a Knight needs to review a referred petition and make a recommendation.

Constitutional Constraints:
- FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
- STK-4: Knight: "I receive referrals with sufficient context" [P1]
- NFR-5.2: Authorization: Only assigned Knight can access package
- CT-12: Frozen dataclass ensures immutability
- CT-13: Read-only operations work during halt

Developer Golden Rules:
1. READS DURING HALT - Decision package queries work during halt (CT-13)
2. WITNESS EVERYTHING - Package assembly is a read operation, no witnessing needed
3. AUTHORIZATION FIRST - Verify Knight assignment before building package
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.petition_submission import PetitionType
from src.domain.models.referral import ReferralStatus


@dataclass(frozen=True, eq=True)
class DecisionPackage:
    """A bundled decision package for Knight review (FR-4.3).

    Contains all context needed for a Knight to review a referred petition
    and formulate a recommendation (ACKNOWLEDGE or ESCALATE).

    From PRD Section 8.3 - Decision Package:
    - Bundled context for Knight/King review
    - Includes: petition text, co-signer count, related petitions, submitter history

    From PRD Section 15.4 - The Knight Journey:
    - Receive referral notification → Access decision package
    - Review petition + related context → Formulate recommendation

    Constitutional Constraints:
    - FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
    - STK-4: Knight: "I receive referrals with sufficient context" [P1]
    - NFR-5.2: Authorization: Only assigned Knight can access package
    - CT-12: Frozen dataclass for immutability

    Attributes:
        referral_id: UUID of the referral this package is for.
        petition_id: UUID of the petition being reviewed.
        realm_id: UUID of the realm the referral is routed to.
        assigned_knight_id: UUID of the Knight assigned to review.
        deadline: When the referral must be completed (UTC).
        status: Current referral status (ASSIGNED or IN_REVIEW).
        extensions_granted: Number of extensions granted (0-2).
        can_extend: Whether an extension can be requested.
        petition_text: Full petition content.
        petition_type: Type of petition (GENERAL, CESSATION, etc.).
        petition_created_at: When the petition was submitted (UTC).
        submitter_id: UUID of submitter (optional for anonymous).
        co_signer_count: Number of co-signers (placeholder until Epic 5).
        built_at: When this package was assembled (UTC).
    """

    # Referral information
    referral_id: UUID
    petition_id: UUID
    realm_id: UUID
    assigned_knight_id: UUID
    deadline: datetime
    status: ReferralStatus
    extensions_granted: int = field(default=0)
    can_extend: bool = field(default=True)

    # Petition information
    petition_text: str = field(default="")
    petition_type: PetitionType = field(default=PetitionType.GENERAL)
    petition_created_at: datetime | None = field(default=None)
    submitter_id: UUID | None = field(default=None)

    # Co-signer information (placeholder until Epic 5)
    co_signer_count: int = field(default=0)

    # Package metadata
    built_at: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate decision package fields after initialization.

        Raises:
            ValueError: If any field validation fails.
        """
        # Validate deadline is timezone-aware
        if self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware (UTC)")

        # Validate status is appropriate for package access
        if self.status not in (ReferralStatus.ASSIGNED, ReferralStatus.IN_REVIEW):
            raise ValueError(
                f"Decision package only available for ASSIGNED or IN_REVIEW "
                f"referrals, got {self.status.value}"
            )

        # Validate extensions_granted range
        if not 0 <= self.extensions_granted <= 2:
            raise ValueError(
                f"extensions_granted must be 0-2, got {self.extensions_granted}"
            )

        # Validate petition_created_at is timezone-aware if set
        if (
            self.petition_created_at is not None
            and self.petition_created_at.tzinfo is None
        ):
            raise ValueError("petition_created_at must be timezone-aware (UTC)")

        # Validate built_at is timezone-aware if set
        if self.built_at is not None and self.built_at.tzinfo is None:
            raise ValueError("built_at must be timezone-aware (UTC)")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision package to a dictionary.

        Returns a dictionary suitable for JSON serialization per D2 rules:
        - UUIDs are converted to strings
        - Datetimes are converted to ISO 8601 format
        - Enums are converted to their values

        Returns:
            Dictionary representation of the decision package.
        """
        return {
            "referral_id": str(self.referral_id),
            "petition_id": str(self.petition_id),
            "realm_id": str(self.realm_id),
            "assigned_knight_id": str(self.assigned_knight_id),
            "deadline": self.deadline.isoformat(),
            "status": self.status.value,
            "extensions_granted": self.extensions_granted,
            "can_extend": self.can_extend,
            "petition": {
                "text": self.petition_text,
                "type": self.petition_type.value,
                "created_at": (
                    self.petition_created_at.isoformat()
                    if self.petition_created_at
                    else None
                ),
                "submitter_id": str(self.submitter_id) if self.submitter_id else None,
                "co_signer_count": self.co_signer_count,
            },
            "built_at": self.built_at.isoformat() if self.built_at else None,
        }
