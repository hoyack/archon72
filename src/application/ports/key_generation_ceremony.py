"""Key Generation Ceremony protocol definition (FR69, ADR-4).

Defines the abstract interface for key generation ceremony operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- CT-12: Witnessing creates accountability
- CM-5: Single ceremony at a time per Keeper
- VAL-2: Ceremony timeout enforcement
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.models.ceremony_witness import CeremonyWitness
from src.domain.models.key_generation_ceremony import (
    CeremonyState,
    CeremonyType,
    KeyGenerationCeremony,
)


class KeyGenerationCeremonyProtocol(ABC):
    """Abstract protocol for key generation ceremony operations.

    All key generation ceremony implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific storage implementations.

    Constitutional Requirements:
    - FR69: Must track witnessed ceremonies for key generation
    - CT-12: Must track all witness attestations
    - CM-5: Must enforce single active ceremony per Keeper
    """

    @abstractmethod
    async def get_ceremony(self, ceremony_id: str) -> KeyGenerationCeremony | None:
        """Get a ceremony by its ID.

        Args:
            ceremony_id: The ceremony UUID as string.

        Returns:
            KeyGenerationCeremony if found, None otherwise.
        """
        ...

    @abstractmethod
    async def create_ceremony(
        self,
        keeper_id: str,
        ceremony_type: CeremonyType,
        old_key_id: str | None = None,
    ) -> KeyGenerationCeremony:
        """Create a new key generation ceremony.

        Creates a ceremony in PENDING state, ready for witnesses.

        Args:
            keeper_id: ID of Keeper receiving the new key.
            ceremony_type: NEW_KEEPER_KEY or KEY_ROTATION.
            old_key_id: HSM key ID being rotated (for rotations).

        Returns:
            The newly created KeyGenerationCeremony.

        Raises:
            CeremonyConflictError: If active ceremony exists for Keeper (CM-5).
        """
        ...

    @abstractmethod
    async def add_witness(
        self,
        ceremony_id: str,
        witness: CeremonyWitness,
    ) -> None:
        """Add a witness attestation to a ceremony.

        Args:
            ceremony_id: The ceremony UUID as string.
            witness: The CeremonyWitness to add.

        Raises:
            CeremonyNotFoundError: If ceremony doesn't exist.
            DuplicateWitnessError: If witness has already signed.
            InvalidCeremonyStateError: If ceremony not in PENDING state.
        """
        ...

    @abstractmethod
    async def update_state(
        self,
        ceremony_id: str,
        new_state: CeremonyState,
        failure_reason: str | None = None,
    ) -> None:
        """Update the state of a ceremony (FP-4 state machine).

        Args:
            ceremony_id: The ceremony UUID as string.
            new_state: The target state.
            failure_reason: Reason for failure (if transitioning to FAILED).

        Raises:
            CeremonyNotFoundError: If ceremony doesn't exist.
            InvalidCeremonyStateError: If transition is invalid.
        """
        ...

    @abstractmethod
    async def get_active_ceremonies(self) -> list[KeyGenerationCeremony]:
        """Get all active (non-terminal) ceremonies.

        Returns ceremonies in PENDING, APPROVED, or EXECUTING states.
        Used for conflict detection (CM-5) and timeout checking (VAL-2).

        Returns:
            List of active KeyGenerationCeremony objects.
        """
        ...

    @abstractmethod
    async def get_active_ceremony_for_keeper(
        self,
        keeper_id: str,
    ) -> KeyGenerationCeremony | None:
        """Get the active ceremony for a specific Keeper (CM-5).

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            KeyGenerationCeremony if active ceremony exists, None otherwise.
        """
        ...

    @abstractmethod
    async def mark_completed(
        self,
        ceremony_id: str,
        new_key_id: str,
        transition_end_at: datetime | None = None,
    ) -> None:
        """Mark a ceremony as completed with the new key ID.

        Transitions ceremony to COMPLETED state and records the
        new key ID and transition period.

        Args:
            ceremony_id: The ceremony UUID as string.
            new_key_id: HSM key ID of the newly generated key.
            transition_end_at: When transition period ends (for rotations).

        Raises:
            CeremonyNotFoundError: If ceremony doesn't exist.
            InvalidCeremonyStateError: If not in EXECUTING state.
        """
        ...

    @abstractmethod
    async def get_timed_out_ceremonies(
        self,
        timeout_threshold: datetime,
    ) -> list[KeyGenerationCeremony]:
        """Get ceremonies that have exceeded the timeout threshold (VAL-2).

        Args:
            timeout_threshold: Ceremonies created before this time are timed out.

        Returns:
            List of active ceremonies that have timed out.
        """
        ...
