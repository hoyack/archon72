"""Petition Adoption Protocol (Story 6.3, FR-5.5).

This module defines the port (abstract protocol) for petition adoption,
where Kings adopt escalated petitions and create Motions.

Constitutional Constraints:
- FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
- FR-5.6: Adoption SHALL consume promotion budget (H1 compliance) [P0]
- FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
- CT-13: Halt check first pattern
- RULING-3: Realm-scoped data access (Kings only adopt from their realm)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass
class AdoptionRequest:
    """Request to adopt an escalated petition.

    Attributes:
        petition_id: UUID of the petition to adopt
        king_id: UUID of the King making the adoption
        realm_id: Realm ID of the King (for authorization)
        motion_title: Title for the new Motion
        motion_body: Body/intent text for the Motion
        adoption_rationale: King's rationale for adoption (min 50 chars)
    """

    petition_id: UUID
    king_id: UUID
    realm_id: str
    motion_title: str
    motion_body: str
    adoption_rationale: str


@dataclass
class AdoptionResult:
    """Result of a petition adoption attempt.

    Attributes:
        success: Whether the adoption succeeded
        motion_id: UUID of the created Motion (if successful)
        errors: List of error codes (if failed)
        budget_consumed: Amount of budget consumed (1 if successful, 0 if failed)
    """

    success: bool
    motion_id: UUID | None = None
    errors: list[str] = field(default_factory=list)
    budget_consumed: int = 0


class PetitionNotEscalatedException(Exception):
    """Raised when attempting to adopt a petition that is not in ESCALATED state.

    Per FR-2.2: Only petitions in terminal ESCALATED state can be adopted.
    """

    def __init__(self, petition_id: UUID, current_state: str):
        self.petition_id = petition_id
        self.current_state = current_state
        super().__init__(
            f"Petition {petition_id} is not escalated (current state: {current_state})"
        )


class RealmMismatchException(Exception):
    """Raised when King attempts to adopt petition from different realm.

    Per RULING-3: Kings can only adopt petitions escalated to their realm.
    """

    def __init__(self, king_realm: str, petition_realm: str):
        self.king_realm = king_realm
        self.petition_realm = petition_realm
        super().__init__(
            f"Realm mismatch: King realm is {king_realm}, petition realm is {petition_realm}"
        )


class InsufficientBudgetException(Exception):
    """Raised when King has insufficient promotion budget for adoption.

    Per FR-5.6: Adoption consumes promotion budget (H1 compliance).
    Per ADR-P4: Budget consumption prevents budget laundering.
    """

    def __init__(self, king_id: UUID, cycle_id: str, remaining: int):
        self.king_id = king_id
        self.cycle_id = cycle_id
        self.remaining = remaining
        super().__init__(
            f"Insufficient budget: King {king_id} has {remaining} remaining in cycle {cycle_id}"
        )


class PetitionAdoptionProtocol(Protocol):
    """Protocol for petition adoption operations.

    Implementations must:
    1. Check halt state first (CT-13)
    2. Validate petition exists and is ESCALATED
    3. Validate realm authorization (RULING-3)
    4. Check and consume promotion budget (FR-5.6)
    5. Create Motion with source_petition_ref (FR-5.7)
    6. Update petition with adoption back-reference (NFR-6.2)
    7. Emit PetitionAdopted event (CT-12)
    """

    def adopt_petition(self, request: AdoptionRequest) -> AdoptionResult:
        """Adopt an escalated petition and create a Motion.

        Args:
            request: Adoption request containing petition ID, King ID, and Motion details

        Returns:
            AdoptionResult with success status, motion_id, and budget consumed

        Raises:
            PetitionNotEscalatedException: If petition is not in ESCALATED state
            RealmMismatchException: If King's realm doesn't match petition's realm
            InsufficientBudgetException: If King has insufficient promotion budget
            SystemHaltedException: If system is in halted state
        """
        ...
