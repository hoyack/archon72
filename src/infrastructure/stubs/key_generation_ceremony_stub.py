"""Key Generation Ceremony Stub for testing (FR69, ADR-4).

In-memory implementation of KeyGenerationCeremonyProtocol for use in tests.

Constitutional Constraints:
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- CT-12: Witnessing creates accountability
- CM-5: Single ceremony at a time per Keeper
- VAL-2: Ceremony timeout enforcement
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.application.ports.key_generation_ceremony import KeyGenerationCeremonyProtocol
from src.domain.errors.key_generation_ceremony import (
    CeremonyConflictError,
    CeremonyNotFoundError,
    DuplicateWitnessError,
    InvalidCeremonyStateError,
)
from src.domain.models.ceremony_witness import CeremonyWitness
from src.domain.models.key_generation_ceremony import (
    CeremonyState,
    CeremonyType,
    KeyGenerationCeremony,
)


class KeyGenerationCeremonyStub(KeyGenerationCeremonyProtocol):
    """In-memory stub implementation of KeyGenerationCeremonyProtocol.

    Used for testing purposes. Stores ceremonies in memory and provides
    all protocol methods with proper state machine enforcement.

    Note: Ceremonies are NEVER deleted to preserve audit trail.
    """

    def __init__(self) -> None:
        """Initialize empty ceremony store."""
        self._ceremonies: dict[str, KeyGenerationCeremony] = {}  # ceremony_id -> Ceremony

    async def get_ceremony(self, ceremony_id: str) -> KeyGenerationCeremony | None:
        """Get a ceremony by its ID.

        Args:
            ceremony_id: The ceremony UUID as string.

        Returns:
            KeyGenerationCeremony if found, None otherwise.
        """
        return self._ceremonies.get(ceremony_id)

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
        # CM-5: Check for conflicting ceremony
        existing = await self.get_active_ceremony_for_keeper(keeper_id)
        if existing:
            raise CeremonyConflictError(
                f"CM-5: Conflicting ceremony already active for {keeper_id}: {existing.id}"
            )

        ceremony_id = uuid4()
        ceremony = KeyGenerationCeremony(
            id=ceremony_id,
            keeper_id=keeper_id,
            ceremony_type=ceremony_type,
            state=CeremonyState.PENDING,
            witnesses=[],
            old_key_id=old_key_id,
        )

        self._ceremonies[str(ceremony_id)] = ceremony
        return ceremony

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
        ceremony = self._ceremonies.get(ceremony_id)
        if ceremony is None:
            raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

        if ceremony.state != CeremonyState.PENDING:
            raise InvalidCeremonyStateError(
                f"FP-4: Cannot add witness in {ceremony.state.value} state"
            )

        if ceremony.has_witness(witness.witness_id):
            raise DuplicateWitnessError(
                f"CT-12: Witness {witness.witness_id} has already signed"
            )

        ceremony.witnesses.append(witness)

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
        ceremony = self._ceremonies.get(ceremony_id)
        if ceremony is None:
            raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

        if not ceremony.can_transition_to(new_state):
            raise InvalidCeremonyStateError(
                f"FP-4: Invalid state transition {ceremony.state.value} -> {new_state.value}"
            )

        ceremony.state = new_state
        if failure_reason:
            ceremony.failure_reason = failure_reason

    async def get_active_ceremonies(self) -> list[KeyGenerationCeremony]:
        """Get all active (non-terminal) ceremonies.

        Returns ceremonies in PENDING, APPROVED, or EXECUTING states.

        Returns:
            List of active KeyGenerationCeremony objects.
        """
        return [c for c in self._ceremonies.values() if c.is_active()]

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
        for ceremony in self._ceremonies.values():
            if ceremony.keeper_id == keeper_id and ceremony.is_active():
                return ceremony
        return None

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
        ceremony = self._ceremonies.get(ceremony_id)
        if ceremony is None:
            raise CeremonyNotFoundError(f"FR69: Ceremony not found: {ceremony_id}")

        if ceremony.state != CeremonyState.EXECUTING:
            raise InvalidCeremonyStateError(
                f"FP-4: Cannot complete from {ceremony.state.value} state"
            )

        ceremony.state = CeremonyState.COMPLETED
        ceremony.new_key_id = new_key_id
        ceremony.transition_end_at = transition_end_at
        ceremony.completed_at = datetime.now(timezone.utc)

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
        return [
            c for c in self._ceremonies.values()
            if c.is_active() and c.created_at < timeout_threshold
        ]

    # Test helper methods

    def add_ceremony(self, ceremony: KeyGenerationCeremony) -> None:
        """Synchronous helper to add a ceremony for test setup.

        Args:
            ceremony: The KeyGenerationCeremony to add.
        """
        self._ceremonies[str(ceremony.id)] = ceremony

    def clear(self) -> None:
        """Clear all ceremonies from the store for test cleanup."""
        self._ceremonies.clear()

    def get_ceremony_count(self) -> int:
        """Get the number of ceremonies in the store.

        Returns:
            Number of ceremonies stored.
        """
        return len(self._ceremonies)

    def get_all_ceremonies(self) -> list[KeyGenerationCeremony]:
        """Get all ceremonies (for testing).

        Returns:
            List of all ceremonies.
        """
        return list(self._ceremonies.values())
