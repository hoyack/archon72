"""Witness Pool adapter implementations (FR4, FR5).

Provides infrastructure adapters for the witness pool protocol.

Available adapters:
- InMemoryWitnessPool: In-memory storage for testing/development

Constitutional Constraints:
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.ports.witness_pool import WitnessPoolProtocol
from src.domain.errors.witness import NoWitnessAvailableError, WitnessNotFoundError
from src.domain.models.witness import Witness


class InMemoryWitnessPool(WitnessPoolProtocol):
    """In-memory witness pool for testing and development.

    NOT FOR PRODUCTION USE. Witnesses are stored in memory and will be
    lost when the process exits.

    Constitutional Constraints:
    - FR5: No unwitnessed events can exist - raises NoWitnessAvailableError
    - CT-12: Witnessing creates accountability

    Selection Strategy:
    - Round-robin selection among active witnesses
    - Returns first available active witness
    """

    def __init__(self) -> None:
        """Initialize the in-memory witness pool."""
        self._witnesses: dict[str, Witness] = {}  # witness_id -> Witness
        self._selection_index: int = 0

    async def get_available_witness(self) -> Witness:
        """Get an available witness for event attestation.

        Selection Strategy: Round-robin among active witnesses.

        Returns:
            An active Witness ready to attest.

        Raises:
            NoWitnessAvailableError: If no witnesses are available (RT-1).
        """
        now = datetime.now(timezone.utc)
        active_witnesses = [w for w in self._witnesses.values() if w.is_active(at=now)]

        if not active_witnesses:
            raise NoWitnessAvailableError()

        # Round-robin selection
        self._selection_index = self._selection_index % len(active_witnesses)
        selected = active_witnesses[self._selection_index]
        self._selection_index += 1

        return selected

    async def get_witness_by_id(self, witness_id: str) -> Witness | None:
        """Lookup witness by ID for signature verification.

        Args:
            witness_id: The witness ID to look up (format: "WITNESS:{uuid}").

        Returns:
            The Witness if found, None otherwise.
        """
        return self._witnesses.get(witness_id)

    async def register_witness(self, witness: Witness) -> None:
        """Register a new witness in the pool.

        Args:
            witness: The Witness entity to register.

        Note:
            If a witness with the same ID already exists, it will be replaced.
            This allows for key rotation.
        """
        self._witnesses[witness.witness_id] = witness

    async def deactivate_witness(self, witness_id: str) -> None:
        """Deactivate a witness, preventing future attestations.

        Sets the witness's active_until to current time, preventing
        it from being selected for new attestations.

        Args:
            witness_id: The witness ID to deactivate.

        Raises:
            WitnessNotFoundError: If witness does not exist.
        """
        if witness_id not in self._witnesses:
            raise WitnessNotFoundError(witness_id)

        old_witness = self._witnesses[witness_id]
        now = datetime.now(timezone.utc)

        # Create new witness with active_until set
        new_witness = Witness(
            witness_id=old_witness.witness_id,
            public_key=old_witness.public_key,
            active_from=old_witness.active_from,
            active_until=now,
        )

        self._witnesses[witness_id] = new_witness

    async def count_active_witnesses(self) -> int:
        """Count the number of currently active witnesses.

        Returns:
            The count of active witnesses in the pool.
        """
        now = datetime.now(timezone.utc)
        return sum(1 for w in self._witnesses.values() if w.is_active(at=now))

    async def get_ordered_active_witnesses(self) -> tuple[str, ...]:
        """Get ordered list of active witness IDs.

        Returns:
            Tuple of active witness IDs, sorted alphabetically for determinism.
        """
        now = datetime.now(timezone.utc)
        active_ids = [
            w.witness_id
            for w in self._witnesses.values()
            if w.is_active(at=now)
        ]
        return tuple(sorted(active_ids))

    def clear(self) -> None:
        """Clear all witnesses (for testing only).

        WARNING: This should only be used in test fixtures.
        """
        self._witnesses.clear()
        self._selection_index = 0

    def register_witness_sync(self, witness: Witness) -> None:
        """Synchronous version of register_witness for test setup.

        Args:
            witness: The Witness entity to register.
        """
        self._witnesses[witness.witness_id] = witness
