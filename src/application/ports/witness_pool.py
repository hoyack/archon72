"""Witness pool port definition (FR4, FR5).

Defines the abstract interface for witness pool operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist - pool must provide available witnesses
- CT-12: Witnessing creates accountability
"""

from abc import ABC, abstractmethod

from src.domain.models.witness import Witness


class WitnessPoolProtocol(ABC):
    """Abstract protocol for witness pool operations.

    All witness pool implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific witness pool implementations.

    Constitutional Constraints:
    - FR5: No unwitnessed events can exist - pool must provide available witnesses
    - CT-12: Witnessing creates accountability

    Implementations may include:
    - InMemoryWitnessPool: For testing
    - DatabaseWitnessPool: For production with Supabase
    """

    @abstractmethod
    async def get_available_witness(self) -> Witness:
        """Get an available witness for event attestation.

        Selects an active witness from the pool to attest an event.
        Selection strategy is implementation-defined (round-robin, random, etc.).

        Returns:
            An active Witness ready to attest.

        Raises:
            NoWitnessAvailableError: If no witnesses are available (RT-1).
                This MUST cause event write to be rejected.
        """
        ...

    @abstractmethod
    async def get_witness_by_id(self, witness_id: str) -> Witness | None:
        """Lookup witness by ID for signature verification.

        Used during signature verification to retrieve the witness's
        public key for cryptographic verification.

        Args:
            witness_id: The witness ID to look up (format: "WITNESS:{uuid}").

        Returns:
            The Witness if found, None otherwise.
        """
        ...

    @abstractmethod
    async def register_witness(self, witness: Witness) -> None:
        """Register a new witness in the pool.

        Adds a witness to the pool, making it available for attestation
        once its active_from time has passed.

        Args:
            witness: The Witness entity to register.

        Raises:
            ConstitutionalViolationError: If witness validation fails.
        """
        ...

    @abstractmethod
    async def deactivate_witness(self, witness_id: str) -> None:
        """Deactivate a witness, preventing future attestations.

        Sets the witness's active_until to current time, preventing
        it from being selected for new attestations. Historical
        verification still works with the stored public key.

        Args:
            witness_id: The witness ID to deactivate.

        Raises:
            WitnessNotFoundError: If witness does not exist.
        """
        ...

    @abstractmethod
    async def count_active_witnesses(self) -> int:
        """Count the number of currently active witnesses.

        Used for monitoring and health checks.

        Returns:
            The count of active witnesses in the pool.
        """
        ...

    @abstractmethod
    async def get_ordered_active_witnesses(self) -> tuple[str, ...]:
        """Get ordered list of active witness IDs.

        Returns a deterministically ordered list of all active witness IDs.
        The order is consistent (sorted by witness_id) to support
        verifiable witness selection (FR59).

        Used by VerifiableWitnessSelectionService to get a pool snapshot
        that external observers can use to verify selection.

        Returns:
            Tuple of witness IDs, sorted alphabetically.
        """
        ...
