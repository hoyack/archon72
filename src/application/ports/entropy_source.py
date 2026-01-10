"""External entropy source port definition (FR61, NFR22, NFR57).

Defines the abstract interface for external entropy source operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR61: System SHALL use external entropy source for witness selection
- NFR22: Witness selection randomness SHALL include external entropy source
- NFR57: If all entropy fails, witness selection halts (not weak randomness)
"""

from abc import ABC, abstractmethod


class EntropySourceProtocol(ABC):
    """Abstract protocol for external entropy source operations.

    All entropy source implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific entropy source implementations.

    Constitutional Constraints:
    - FR61: External entropy source required for witness selection
    - NFR22: Witness selection randomness SHALL include external entropy
    - NFR57: If all entropy fails, witness selection halts rather than using
      weak randomness - CRITICAL safety requirement

    Production implementations may include:
    - CloudflareEntropySource: drand.cloudflare.com
    - RandomOrgEntropySource: api.random.org
    - HardwareEntropySource: Hardware RNG device

    Development/Testing:
    - EntropySourceStub: Deterministic entropy for testing
    """

    @abstractmethod
    async def get_entropy(self) -> bytes:
        """Get external entropy bytes.

        Returns at least 32 bytes of external entropy from an
        independent source for use in witness selection.

        Returns:
            At least 32 bytes of external entropy.

        Raises:
            EntropyUnavailableError: If entropy cannot be obtained.
                CRITICAL: Caller MUST halt operations, not use weak
                randomness (NFR57). This is a constitutional requirement.
        """
        ...

    @abstractmethod
    async def get_source_identifier(self) -> str:
        """Get identifier for entropy source.

        Returns a human-readable identifier for the entropy source,
        used in audit trails and selection records for verifiability.

        Returns:
            Human-readable source identifier for audit trail.
            E.g., "drand.cloudflare.com", "random.org/v2", "dev-stub"
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the entropy source is currently available.

        Used for health checks and pre-operation validation.
        Does not guarantee success of get_entropy() but indicates
        the source is reachable.

        Returns:
            True if the entropy source appears available, False otherwise.
        """
        ...
