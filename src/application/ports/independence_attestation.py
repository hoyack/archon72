"""Independence Attestation protocol definition (FR98, FR133).

Defines the abstract interface for annual Keeper independence attestation
operations. Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR133: Keepers SHALL annually attest independence from each other and operators
- FR76: Historical attestations must be preserved (no deletion)
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.independence_attestation import IndependenceAttestation


class IndependenceAttestationProtocol(ABC):
    """Abstract protocol for Keeper independence attestation operations.

    All independence attestation repository implementations must implement
    this interface. This enables dependency inversion and allows the
    application layer to remain independent of specific storage implementations.

    Constitutional Requirements:
    - FR133: Track annual independence attestations
    - FR76: Historical attestations must never be deleted
    - CT-12: Support witnessing via event system integration
    """

    @abstractmethod
    async def get_attestation(
        self, keeper_id: str, year: int
    ) -> IndependenceAttestation | None:
        """Get independence attestation for a Keeper for a specific year.

        Args:
            keeper_id: The Keeper identifier (e.g., "KEEPER:alice").
            year: The attestation year to look up.

        Returns:
            IndependenceAttestation if found, None otherwise.
        """
        ...

    @abstractmethod
    async def record_attestation(self, attestation: IndependenceAttestation) -> None:
        """Record a new Keeper independence attestation.

        Args:
            attestation: The IndependenceAttestation to record.

        Raises:
            DuplicateIndependenceAttestationError: If attestation already exists for year.
        """
        ...

    @abstractmethod
    async def get_attestation_history(
        self, keeper_id: str
    ) -> list[IndependenceAttestation]:
        """Get all independence attestations for a Keeper.

        Returns attestations in chronological order (oldest first).

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            List of IndependenceAttestations, possibly empty.
        """
        ...

    @abstractmethod
    async def get_latest_attestation(
        self, keeper_id: str
    ) -> IndependenceAttestation | None:
        """Get the most recent independence attestation for a Keeper.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Most recent IndependenceAttestation if any, None otherwise.
        """
        ...

    @abstractmethod
    async def get_keepers_overdue_attestation(self) -> list[str]:
        """Get list of Keepers with overdue independence attestations.

        Returns Keepers who have passed their attestation deadline
        plus grace period without submitting a new attestation.

        Returns:
            List of Keeper IDs with overdue attestations.
        """
        ...

    @abstractmethod
    async def mark_keeper_suspended(self, keeper_id: str, reason: str) -> None:
        """Mark a Keeper's capabilities as suspended (FR133).

        Called when a Keeper misses their independence attestation deadline.
        The Keeper remains in the system but override capability is suspended.

        Args:
            keeper_id: The Keeper identifier.
            reason: Why the Keeper is being suspended.
        """
        ...

    @abstractmethod
    async def is_keeper_suspended(self, keeper_id: str) -> bool:
        """Check if a Keeper's capabilities are suspended.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            True if suspended, False otherwise.
        """
        ...

    @abstractmethod
    async def clear_suspension(self, keeper_id: str) -> None:
        """Clear a Keeper's suspension after attestation is submitted.

        Called when a suspended Keeper successfully submits their
        independence attestation.

        Args:
            keeper_id: The Keeper identifier.
        """
        ...

    @abstractmethod
    async def get_all_active_keepers(self) -> list[str]:
        """Get list of all active Keeper IDs.

        Active Keepers are those who have not been removed from the system.

        Returns:
            List of active Keeper IDs.
        """
        ...
