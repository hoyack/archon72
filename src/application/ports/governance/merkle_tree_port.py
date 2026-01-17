"""Merkle Tree Port - Interface for Merkle tree proof operations.

Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion

This port defines the interface for Merkle tree proof operations,
enabling light verification and independent audit without full
ledger access.

Constitutional Constraints:
- AD-7: Merkle tree proof-of-inclusion
- NFR-CONST-02: Proof-of-inclusion for any entry
- NFR-AUDIT-06: External verification possible
- FR57: Cryptographic proof of completeness

Architectural Notes:
- Epoch roots are persisted to enable historical proof generation
- verify_proof() is sync (pure computation, no I/O)
- All other methods are async (database access)

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Proof-of-Inclusion (Locked)]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.events.hash_algorithms import DEFAULT_ALGORITHM
from src.domain.governance.events.merkle_tree import (
    MerkleProof,
    MerkleVerificationResult,
)


@dataclass(frozen=True)
class EpochInfo:
    """Information about a Merkle tree epoch.

    Attributes:
        epoch_id: Unique identifier for the epoch.
        root_hash: Merkle root hash for this epoch.
        algorithm: Hash algorithm used.
        start_sequence: First event sequence in this epoch.
        end_sequence: Last event sequence in this epoch.
        event_count: Number of events in this epoch.
        created_at: When the epoch root was computed.
        root_event_id: UUID of the ledger event recording this root.
    """

    epoch_id: int
    root_hash: str
    algorithm: str
    start_sequence: int
    end_sequence: int
    event_count: int
    created_at: datetime
    root_event_id: UUID | None = None


@dataclass(frozen=True)
class EpochConfig:
    """Configuration for Merkle tree epochs.

    Attributes:
        events_per_epoch: Number of events per epoch (default 1000).
        time_based: Whether to use time-based epochs instead.
        epoch_duration_seconds: Duration in seconds (if time-based).
    """

    events_per_epoch: int = 1000
    time_based: bool = False
    epoch_duration_seconds: int = 3600


@runtime_checkable
class MerkleTreePort(Protocol):
    """Port for Merkle tree proof operations.

    Constitutional Guarantee:
    - Any event can have proof generated
    - Proofs are independently verifiable (no ledger access)
    - Epoch roots are published to ledger

    Implementation Notes:
    - PostgreSQL adapter stores epoch roots in ledger.merkle_epochs
    - Epoch boundaries are configurable (events or time-based)
    - Proof generation requires building tree from epoch events
    """

    async def build_epoch(
        self,
        epoch_id: int,
        start_sequence: int,
        end_sequence: int,
        algorithm: str = DEFAULT_ALGORITHM,
    ) -> EpochInfo:
        """Build Merkle tree for an epoch and persist the root.

        Reads events from the ledger for the given sequence range,
        builds the Merkle tree, and persists the root.

        Args:
            epoch_id: Identifier for this epoch.
            start_sequence: First event sequence to include.
            end_sequence: Last event sequence to include.
            algorithm: Hash algorithm for tree construction.

        Returns:
            EpochInfo with the computed root and metadata.

        Raises:
            ValueError: If sequence range is invalid.
            ConstitutionalViolationError: If events are missing in range.
        """
        ...

    async def generate_proof(
        self,
        event_id: UUID,
    ) -> MerkleProof:
        """Generate inclusion proof for a specific event.

        Looks up the event, determines its epoch, and generates
        the Merkle proof.

        Args:
            event_id: UUID of the event to prove.

        Returns:
            MerkleProof that can be verified independently.

        Raises:
            ValueError: If event not found.
            ValueError: If event's epoch has not been built yet.
        """
        ...

    async def generate_proof_by_sequence(
        self,
        sequence: int,
    ) -> MerkleProof:
        """Generate inclusion proof for an event by sequence number.

        Args:
            sequence: Ledger sequence number of the event.

        Returns:
            MerkleProof that can be verified independently.

        Raises:
            ValueError: If sequence not found.
            ValueError: If event's epoch has not been built yet.
        """
        ...

    async def get_epoch_root(
        self,
        epoch_id: int,
    ) -> str | None:
        """Get published Merkle root for an epoch.

        Args:
            epoch_id: Identifier for the epoch.

        Returns:
            Algorithm-prefixed root hash, or None if epoch not built.
        """
        ...

    async def get_epoch_info(
        self,
        epoch_id: int,
    ) -> EpochInfo | None:
        """Get full information about an epoch.

        Args:
            epoch_id: Identifier for the epoch.

        Returns:
            EpochInfo with root and metadata, or None if not built.
        """
        ...

    async def get_epoch_for_sequence(
        self,
        sequence: int,
    ) -> int | None:
        """Determine which epoch contains a given sequence number.

        Args:
            sequence: Ledger sequence number.

        Returns:
            Epoch ID containing this sequence, or None if not in any epoch.
        """
        ...

    async def list_epochs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EpochInfo]:
        """List all built epochs.

        Args:
            limit: Maximum number of epochs to return.
            offset: Number of epochs to skip.

        Returns:
            List of EpochInfo ordered by epoch_id ascending.
        """
        ...

    async def get_latest_epoch(self) -> EpochInfo | None:
        """Get the most recently built epoch.

        Returns:
            EpochInfo for the latest epoch, or None if no epochs exist.
        """
        ...

    def verify_proof(
        self,
        proof: MerkleProof,
    ) -> MerkleVerificationResult:
        """Verify a Merkle proof (no async - pure computation).

        This method requires no database access and can be used by
        external verifiers directly.

        Args:
            proof: The MerkleProof to verify.

        Returns:
            MerkleVerificationResult with verification details.
        """
        ...


@runtime_checkable
class EpochManagerPort(Protocol):
    """Port for epoch lifecycle management.

    Handles automatic epoch creation at boundaries and
    publishing root events to the ledger.
    """

    async def check_epoch_boundary(
        self,
        current_sequence: int,
    ) -> bool:
        """Check if current sequence triggers epoch boundary.

        Args:
            current_sequence: The latest sequence number.

        Returns:
            True if a new epoch should be built.
        """
        ...

    async def create_epoch_if_needed(
        self,
        current_sequence: int,
    ) -> EpochInfo | None:
        """Create a new epoch if boundary is reached.

        If the current sequence triggers an epoch boundary,
        builds the epoch and publishes the root to the ledger.

        Args:
            current_sequence: The latest sequence number.

        Returns:
            EpochInfo if a new epoch was created, None otherwise.
        """
        ...

    async def get_config(self) -> EpochConfig:
        """Get current epoch configuration.

        Returns:
            EpochConfig with current settings.
        """
        ...

    async def update_config(
        self,
        config: EpochConfig,
    ) -> None:
        """Update epoch configuration.

        Note: Changes only affect future epochs, not existing ones.

        Args:
            config: New configuration settings.
        """
        ...
