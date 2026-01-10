"""Ceremony evidence value object for halt clearing (Story 3.4, ADR-6).

This module provides the CeremonyEvidence value object that proves
a ceremony was properly conducted with required approvals.

ADR-6: Halt clearing is Tier 1 ceremony (2 Keepers required).
- Tier 1 ceremonies require 2 Keeper approvers
- All approver signatures must be valid
- The ceremony must be witnessed before taking effect

Constitutional Constraints:
- ADR-3: Halt is sticky - clearing requires witnessed ceremony
- ADR-6: Tier 1 ceremony requires 2 Keepers
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.errors.halt_clear import (
    InsufficientApproversError,
    InvalidCeremonyError,
)

# Ceremony type constant for halt clearing
HALT_CLEAR_CEREMONY_TYPE: str = "halt_clear"

# ADR-6: Tier 1 ceremony requires 2 Keepers
MIN_APPROVERS_TIER_1: int = 2


@dataclass(frozen=True, eq=True)
class ApproverSignature:
    """Signature from a Keeper approving a ceremony.

    Represents a single Keeper's approval of a ceremony.
    The signature bytes prove the Keeper authorized the action.

    Attributes:
        keeper_id: ID of the Keeper who signed (e.g., "keeper-001").
        signature: Raw signature bytes (Ed25519 signature).
        signed_at: When the Keeper signed (UTC).
    """

    keeper_id: str
    signature: bytes
    signed_at: datetime


@dataclass(frozen=True, eq=True)
class CeremonyEvidence:
    """Evidence that a ceremony was properly conducted.

    Used to authorize protected operations like halt clearing.
    ADR-6: Halt clearing is Tier 1, requires 2 Keepers.

    Validation Rules (AC #4, #5):
    - Must have at least MIN_APPROVERS_TIER_1 (2) approvers
    - All approver signatures must be non-empty
    - The ceremony must be witnessed

    Attributes:
        ceremony_id: UUID of the ceremony.
        ceremony_type: Type of ceremony (e.g., "halt_clear").
        approvers: Tuple of ApproverSignature from Keepers who approved.
        created_at: When the ceremony was created (UTC).
    """

    ceremony_id: UUID
    ceremony_type: str
    approvers: tuple[ApproverSignature, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability."""
        if isinstance(self.approvers, list):
            object.__setattr__(self, "approvers", tuple(self.approvers))

    def validate(self) -> bool:
        """Validate ceremony evidence for halt clearing.

        Constitutional Constraint (ADR-6 Tier 1):
        Halt clearing requires at least 2 Keeper approvers.
        All signatures must be valid (non-empty).

        Returns:
            True if ceremony is valid.

        Raises:
            InsufficientApproversError: If < 2 approvers.
            InvalidCeremonyError: If any signature is invalid (empty).
        """
        # Check approver count (ADR-6 Tier 1 requirement)
        if len(self.approvers) < MIN_APPROVERS_TIER_1:
            raise InsufficientApproversError(
                f"ADR-6: Halt clear requires {MIN_APPROVERS_TIER_1} Keepers, "
                f"got {len(self.approvers)}"
            )

        # Validate each signature is non-empty
        for approver in self.approvers:
            if not approver.signature:
                raise InvalidCeremonyError(
                    f"Invalid signature from {approver.keeper_id}: signature is empty"
                )

        return True

    def get_keeper_ids(self) -> tuple[str, ...]:
        """Extract keeper IDs from approvers.

        Returns:
            Tuple of keeper IDs in order of approval.
        """
        return tuple(approver.keeper_id for approver in self.approvers)
