"""Keeper Availability protocol definition (FR77-FR79).

Defines the abstract interface for Keeper availability tracking operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR78: Keepers SHALL attest availability weekly
- FR79: If registered Keeper count falls below 3, system SHALL halt
- FR76: Historical attestations must be preserved (no deletion)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.models.keeper_attestation import KeeperAttestation


class KeeperAvailabilityProtocol(ABC):
    """Abstract protocol for Keeper availability tracking operations.

    All Keeper availability repository implementations must implement
    this interface. This enables dependency inversion and allows the
    application layer to remain independent of specific storage implementations.

    Constitutional Requirements:
    - FR78: Track weekly attestations and missed attestation counts
    - FR79: Track active Keeper count for quorum monitoring
    - FR76: Historical attestations must never be deleted
    """

    @abstractmethod
    async def get_attestation(
        self, keeper_id: str, period_start: datetime
    ) -> KeeperAttestation | None:
        """Get attestation for a Keeper at a specific period start.

        Args:
            keeper_id: The Keeper identifier (e.g., "KEEPER:alice").
            period_start: The start of the attestation period.

        Returns:
            KeeperAttestation if found, None otherwise.
        """
        ...

    @abstractmethod
    async def record_attestation(self, attestation: KeeperAttestation) -> None:
        """Record a new Keeper attestation.

        Args:
            attestation: The KeeperAttestation to record.

        Raises:
            DuplicateAttestationError: If attestation already exists for period.
        """
        ...

    @abstractmethod
    async def get_missed_attestations_count(self, keeper_id: str) -> int:
        """Get count of consecutive missed attestations for a Keeper.

        This count is used to determine if replacement should be triggered
        (FR78: 2 missed attestations trigger replacement).

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Number of consecutive missed attestations (0 if none).
        """
        ...

    @abstractmethod
    async def increment_missed_attestations(self, keeper_id: str) -> int:
        """Increment the missed attestations count for a Keeper.

        Returns the new count after incrementing.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            New count of consecutive missed attestations.
        """
        ...

    @abstractmethod
    async def reset_missed_attestations(self, keeper_id: str) -> None:
        """Reset missed attestations count for a Keeper to 0.

        Called when a Keeper successfully submits an attestation.

        Args:
            keeper_id: The Keeper identifier.
        """
        ...

    @abstractmethod
    async def get_all_active_keepers(self) -> list[str]:
        """Get list of all active Keeper IDs.

        Active Keepers are those who have not been marked for replacement
        and have not been removed from the system.

        Returns:
            List of active Keeper IDs.
        """
        ...

    @abstractmethod
    async def get_keepers_pending_replacement(self) -> list[str]:
        """Get list of Keepers marked for replacement.

        These are Keepers who have missed 2+ consecutive attestations
        and are awaiting replacement.

        Returns:
            List of Keeper IDs pending replacement.
        """
        ...

    @abstractmethod
    async def mark_keeper_for_replacement(
        self, keeper_id: str, reason: str
    ) -> None:
        """Mark a Keeper for replacement (FR78).

        Called when a Keeper misses 2 consecutive attestations.
        The Keeper remains in the system but is marked as needing replacement.

        Args:
            keeper_id: The Keeper identifier.
            reason: Why the Keeper is being replaced.
        """
        ...

    @abstractmethod
    async def get_current_keeper_count(self) -> int:
        """Get the current count of active Keepers.

        Used for quorum monitoring (FR79: minimum 3 Keepers).

        Returns:
            Number of active Keepers.
        """
        ...

    @abstractmethod
    async def add_keeper(self, keeper_id: str) -> None:
        """Add a new active Keeper.

        Args:
            keeper_id: The Keeper identifier to add.
        """
        ...

    @abstractmethod
    async def remove_keeper(self, keeper_id: str) -> None:
        """Remove a Keeper from the active list.

        Note: This should only be used for Keeper removal after
        replacement is complete. The Keeper's historical attestations
        are preserved (FR76).

        Args:
            keeper_id: The Keeper identifier to remove.
        """
        ...

    @abstractmethod
    async def get_last_attestation(
        self, keeper_id: str
    ) -> KeeperAttestation | None:
        """Get the most recent attestation for a Keeper.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Most recent KeeperAttestation if any, None otherwise.
        """
        ...
