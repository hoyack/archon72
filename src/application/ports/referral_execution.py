"""Referral execution protocol (Story 4.2, FR-4.1, FR-4.2).

This module defines the protocols for executing petition referrals.
Follows hexagonal architecture with port/adapter pattern.

Constitutional Constraints:
- FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
- FR-4.2: System SHALL assign referral deadline (3 cycles default)
- CT-12: Every action that affects an Archon must be witnessed
- NFR-3.4: Referral timeout reliability: 100% timeouts fire
- NFR-4.4: Referral deadline persistence: Survives scheduler restart
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.domain.models.referral import Referral


class ReferralExecutionProtocol(Protocol):
    """Protocol for executing petition referrals (FR-4.1, FR-4.2).

    This protocol defines the contract for executing referrals
    when deliberation reaches REFER consensus. Implementations
    must handle:

    1. Validation of petition state (must be DELIBERATING)
    2. Creation of Referral record with deadline
    3. Atomic state transition (DELIBERATING → REFERRED)
    4. Event emission and witnessing (CT-12)
    5. Deadline job scheduling (NFR-3.4, NFR-4.4)

    Constitutional Constraints:
    - FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
    - FR-4.2: System SHALL assign referral deadline (3 cycles default)
    - CT-12: Every action that affects an Archon must be witnessed
    - NFR-3.4: Referral timeout reliability: 100% timeouts fire
    - NFR-4.4: Referral deadline persistence: Survives scheduler restart
    """

    @abstractmethod
    async def execute(
        self,
        petition_id: UUID,
        realm_id: UUID,
        deadline_cycles: int | None = None,
    ) -> Referral:
        """Execute referral for a petition.

        This is the main entry point for referring a petition.
        The method must be atomic - either the referral completes
        fully (state transition + record + event + job) or not at all.

        Args:
            petition_id: The petition to refer
            realm_id: The realm to route the referral to
            deadline_cycles: Number of cycles for deadline (default 3)

        Returns:
            The created Referral record

        Raises:
            PetitionNotFoundError: Petition doesn't exist
            PetitionNotReferrableError: Petition not in DELIBERATING state
            ReferralAlreadyExistsError: Petition already referred (for idempotency)
            InvalidRealmError: realm_id is not valid
            ReferralWitnessHashError: Failed to generate witness hash
            ReferralJobSchedulingError: Failed to schedule deadline job
        """
        ...

    @abstractmethod
    async def get_referral(
        self,
        referral_id: UUID,
    ) -> Referral | None:
        """Retrieve a referral by ID.

        Args:
            referral_id: The referral UUID

        Returns:
            The Referral if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_referral_by_petition(
        self,
        petition_id: UUID,
    ) -> Referral | None:
        """Retrieve a referral by petition ID.

        Args:
            petition_id: The petition UUID

        Returns:
            The Referral if the petition was referred, None otherwise
        """
        ...


class ReferralRepositoryProtocol(Protocol):
    """Repository protocol for referral persistence.

    Separates persistence concerns from execution logic.
    """

    @abstractmethod
    async def save(self, referral: Referral) -> None:
        """Persist a referral record.

        Args:
            referral: The referral to save

        Raises:
            ReferralAlreadyExistsError: Referral for petition exists
        """
        ...

    @abstractmethod
    async def update(self, referral: Referral) -> None:
        """Update an existing referral record.

        Args:
            referral: The referral to update

        Raises:
            ReferralNotFoundError: Referral doesn't exist
        """
        ...

    @abstractmethod
    async def get_by_id(self, referral_id: UUID) -> Referral | None:
        """Retrieve referral by ID.

        Args:
            referral_id: The referral UUID

        Returns:
            The Referral if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_by_petition_id(self, petition_id: UUID) -> Referral | None:
        """Retrieve referral by petition ID.

        Args:
            petition_id: The petition UUID

        Returns:
            The Referral if petition was referred, None otherwise
        """
        ...

    @abstractmethod
    async def exists_for_petition(self, petition_id: UUID) -> bool:
        """Check if referral exists for a petition.

        Args:
            petition_id: The petition UUID

        Returns:
            True if a referral exists, False otherwise
        """
        ...

    @abstractmethod
    async def get_pending_by_realm(
        self,
        realm_id: UUID,
        limit: int = 10,
    ) -> list[Referral]:
        """Get pending referrals for a realm.

        Used for Knight assignment (Story 4.3).

        Args:
            realm_id: The realm UUID
            limit: Maximum number of referrals to return

        Returns:
            List of pending referrals in the realm
        """
        ...

    @abstractmethod
    async def get_active_by_knight(
        self,
        knight_id: UUID,
    ) -> list[Referral]:
        """Get active referrals assigned to a Knight.

        Used for concurrent referral limit enforcement (Story 4.7).

        Args:
            knight_id: The Knight's archon UUID

        Returns:
            List of active referrals assigned to the Knight
        """
        ...

    @abstractmethod
    async def count_active_by_knight(
        self,
        knight_id: UUID,
    ) -> int:
        """Count active referrals assigned to a Knight.

        Used for concurrent referral limit checking (Story 4.7).

        Args:
            knight_id: The Knight's archon UUID

        Returns:
            Number of active referrals assigned to the Knight
        """
        ...
