"""Proof Port - Interface for cryptographic proof operations.

Story: consent-gov-9.2: Cryptographic Proof Generation

This port defines the interface for generating and verifying cryptographic
proofs of ledger completeness and integrity.

Constitutional Constraints:
- FR57: System can provide cryptographic proof of ledger completeness
- NFR-AUDIT-06: External verification possible

Proof Types:
1. CompletenessProof: Combined hash chain + Merkle root proof
2. MerkleProof: Proof-of-inclusion for specific events (via MerkleTreePort)
3. HashChainProof: Proof of unbroken event chain

Verification Philosophy:
- Proofs contain all needed information for verification
- No external data or trusted party required
- Verification is pure computation (sync, no I/O)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.governance.audit.completeness_proof import (
        CompletenessProof,
        HashChainProof,
    )
    from src.domain.governance.events.merkle_tree import MerkleProof


@runtime_checkable
class ProofPort(Protocol):
    """Port for cryptographic proof operations.

    This port provides methods for generating proofs of ledger
    completeness and integrity. All proofs are independently
    verifiable without requiring access to the original ledger.

    Constitutional Guarantee:
    - Proofs demonstrate cryptographic certainty
    - External auditors can verify independently
    - No trusted party required

    Implementation Notes:
    - Completeness proofs combine hash chain and Merkle proofs
    - Hash chain proves integrity (no tampering)
    - Merkle root commits to all events (no omissions)
    - Verification methods are sync (pure computation)
    """

    async def generate_completeness_proof(
        self,
        requester_id: UUID,
    ) -> CompletenessProof:
        """Generate proof of ledger completeness.

        Creates a cryptographic proof that demonstrates:
        1. Hash chain is unbroken (integrity)
        2. All events are accounted for (completeness)
        3. Merkle root commits to exact ledger state

        The returned proof can be verified independently.

        Args:
            requester_id: UUID of the requester (for audit logging).

        Returns:
            CompletenessProof with all verification data.

        Raises:
            ProofGenerationError: If proof generation fails.

        Constitutional Reference:
            - FR57: Cryptographic proof of completeness
        """
        ...

    async def generate_hash_chain_proof(
        self,
    ) -> HashChainProof:
        """Generate proof of hash chain integrity.

        Verifies and returns proof that the hash chain from genesis
        to the latest event is unbroken and valid.

        Returns:
            HashChainProof with chain verification details.

        Raises:
            ProofGenerationError: If chain verification fails.
        """
        ...

    async def generate_merkle_proof_for_event(
        self,
        event_id: UUID,
    ) -> MerkleProof:
        """Generate Merkle proof-of-inclusion for specific event.

        Creates a proof that the specified event is included in
        the ledger's Merkle tree.

        Args:
            event_id: UUID of the event to prove inclusion for.

        Returns:
            MerkleProof with witness path for verification.

        Raises:
            ProofGenerationError: If event not found or epoch not built.

        Note:
            This delegates to MerkleTreePort.generate_proof().
        """
        ...

    async def generate_merkle_proof_for_sequence(
        self,
        sequence: int,
    ) -> MerkleProof:
        """Generate Merkle proof-of-inclusion by sequence number.

        Args:
            sequence: Ledger sequence number of the event.

        Returns:
            MerkleProof with witness path for verification.

        Raises:
            ProofGenerationError: If sequence not found or epoch not built.
        """
        ...

    def verify_completeness_proof(
        self,
        proof: CompletenessProof,
        events: list,
    ) -> bool:
        """Verify a completeness proof against event data.

        This method verifies that:
        1. Hash chain in proof matches computed chain
        2. Merkle root matches computed root from events
        3. Event counts match

        Args:
            proof: The CompletenessProof to verify.
            events: List of PersistedGovernanceEvent to verify against.

        Returns:
            True if proof is valid, False otherwise.

        Note:
            This is a sync method (pure computation, no I/O).
        """
        ...

    def verify_hash_chain(
        self,
        events: list,
    ) -> HashChainProof:
        """Verify hash chain for a list of events.

        Checks that each event correctly links to the previous
        via cryptographic hash.

        Args:
            events: List of PersistedGovernanceEvent to verify.

        Returns:
            HashChainProof with verification results.

        Note:
            This is a sync method (pure computation, no I/O).
        """
        ...


@runtime_checkable
class HashChainPort(Protocol):
    """Port for hash chain operations.

    This port provides methods for verifying and computing
    hash chains for governance events.
    """

    def verify_chain(
        self,
        events: list,
    ) -> bool:
        """Verify hash chain is valid.

        Checks that each event's hash correctly links to the
        previous event's hash.

        Args:
            events: List of PersistedGovernanceEvent in sequence order.

        Returns:
            True if chain is valid, False if broken.
        """
        ...

    def compute_hash(
        self,
        payload_json: str,
        prev_hash: str,
        algorithm: str,
    ) -> str:
        """Compute hash for an event.

        Args:
            payload_json: JSON-serialized event payload.
            prev_hash: Hash of the previous event (empty for genesis).
            algorithm: Hash algorithm to use.

        Returns:
            Algorithm-prefixed hash string.
        """
        ...

    def find_chain_break(
        self,
        events: list,
    ) -> tuple[int, str] | None:
        """Find where hash chain breaks, if anywhere.

        Useful for debugging chain issues.

        Args:
            events: List of PersistedGovernanceEvent in sequence order.

        Returns:
            Tuple of (position, error_message) if break found, None if valid.
        """
        ...
