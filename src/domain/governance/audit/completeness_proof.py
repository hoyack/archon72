"""Completeness proof domain models for ledger verification.

Story: consent-gov-9.2: Cryptographic Proof Generation

Domain models for cryptographic proof of ledger completeness and integrity.
These models enable external verifiers to independently verify that the
ledger is complete and unmodified.

Proof Types:
1. HashChainProof: Proves each event links to previous (integrity)
2. MerkleProof: Proves specific event is included (inclusion)
3. CompletenessProof: Combined proof of both properties

Constitutional Constraints:
- FR57: System can provide cryptographic proof of ledger completeness
- NFR-AUDIT-06: External verification possible

Verification Philosophy:
- Proofs are self-contained (no external data required)
- Verification is pure computation (no database access)
- Math, not trust
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.events.hash_algorithms import DEFAULT_ALGORITHM


class ProofGenerationError(ValueError):
    """Raised when proof generation fails.

    This can occur when:
    - Ledger is empty
    - Hash chain is broken
    - Event not found
    - Epoch not built yet
    """

    pass


class InvalidProofError(ValueError):
    """Raised when proof verification fails.

    This indicates the proof is invalid:
    - Hash mismatch (tampering detected)
    - Chain broken (missing events)
    - Root mismatch (tree altered)
    """

    pass


class IncompleteChainError(InvalidProofError):
    """Raised when hash chain verification detects a gap.

    Attributes:
        expected_sequence: The sequence number that was expected.
        actual_sequence: The sequence number that was found.
        gap_position: Position in chain where gap was detected.
    """

    def __init__(
        self,
        expected_sequence: int,
        actual_sequence: int,
        gap_position: int,
    ) -> None:
        self.expected_sequence = expected_sequence
        self.actual_sequence = actual_sequence
        self.gap_position = gap_position
        super().__init__(
            f"Chain gap at position {gap_position}: "
            f"expected sequence {expected_sequence}, got {actual_sequence}"
        )


@dataclass(frozen=True)
class HashChainProof:
    """Proof that hash chain is complete and unbroken.

    Verifies that each event in the ledger correctly links to the
    previous event via cryptographic hash, proving:
    - No events were modified (hash would change)
    - No events were removed (chain would break)
    - No events were inserted (links would fail)
    - Sequence is unbroken from genesis

    Verification:
        For each event:
        1. Compute H(payload || prev_hash)
        2. Verify it matches event.event_hash
        3. Verify event.prev_hash matches previous event.event_hash

    Attributes:
        genesis_hash: Hash of the first event (or empty string if no events).
        latest_hash: Hash of the last event (or empty string if no events).
        total_events: Number of events in the verified chain.
        algorithm: Hash algorithm used ('blake3' or 'sha256').
        chain_valid: Whether the entire chain validates correctly.
        first_sequence: Sequence number of first event (or 0 if empty).
        last_sequence: Sequence number of last event (or 0 if empty).
    """

    genesis_hash: str
    latest_hash: str
    total_events: int
    algorithm: str
    chain_valid: bool
    first_sequence: int = 0
    last_sequence: int = 0

    def __post_init__(self) -> None:
        """Validate hash chain proof fields."""
        if self.total_events < 0:
            raise ValueError(
                f"total_events must be non-negative, got {self.total_events}"
            )

        if self.total_events == 0:
            # Empty chain should have empty hashes and zero sequences
            if self.genesis_hash or self.latest_hash:
                raise ValueError(
                    "genesis_hash and latest_hash must be empty for zero events"
                )
            if self.first_sequence != 0 or self.last_sequence != 0:
                raise ValueError(
                    "first_sequence and last_sequence must be 0 for zero events"
                )
        else:
            # Non-empty chain should have hashes and valid sequences
            if not self.genesis_hash or not self.latest_hash:
                raise ValueError(
                    "genesis_hash and latest_hash required for non-empty chain"
                )
            if self.first_sequence < 1:
                raise ValueError(
                    f"first_sequence must be >= 1 for non-empty chain, got {self.first_sequence}"
                )
            if self.last_sequence < self.first_sequence:
                raise ValueError(
                    f"last_sequence ({self.last_sequence}) must be >= "
                    f"first_sequence ({self.first_sequence})"
                )

    @property
    def is_empty(self) -> bool:
        """Check if this proof represents an empty ledger."""
        return self.total_events == 0


@dataclass(frozen=True)
class CompletenessProof:
    """Complete proof of ledger integrity.

    Combines hash chain verification and Merkle tree proofs to provide
    cryptographic evidence that:
    1. The ledger is complete (no missing events)
    2. The ledger is unmodified (no tampered events)
    3. All events are accounted for (Merkle root)

    This proof can be verified independently without any trusted party.
    The verification_instructions field provides step-by-step guidance
    for external auditors.

    Attributes:
        proof_id: Unique identifier for this proof.
        generated_at: When the proof was generated (UTC).
        hash_chain_proof: Proof of hash chain integrity.
        merkle_root: Merkle tree root hash (commits to all events).
        total_events: Number of events in the ledger.
        latest_sequence: Sequence number of the most recent event.
        algorithm: Hash algorithm used for all hashes.
        verification_instructions: Human-readable verification guide.
    """

    proof_id: UUID
    generated_at: datetime
    hash_chain_proof: HashChainProof
    merkle_root: str
    total_events: int
    latest_sequence: int
    algorithm: str = DEFAULT_ALGORITHM
    verification_instructions: str = ""

    def __post_init__(self) -> None:
        """Validate completeness proof consistency."""
        # Verify total_events matches hash chain proof
        if self.total_events != self.hash_chain_proof.total_events:
            raise ValueError(
                f"total_events mismatch: proof has {self.total_events}, "
                f"hash_chain_proof has {self.hash_chain_proof.total_events}"
            )

        # Verify algorithm matches
        if self.algorithm != self.hash_chain_proof.algorithm:
            raise ValueError(
                f"algorithm mismatch: proof has {self.algorithm!r}, "
                f"hash_chain_proof has {self.hash_chain_proof.algorithm!r}"
            )

    @property
    def is_valid(self) -> bool:
        """Check if the proof indicates a valid ledger.

        Returns True if the hash chain is valid. External verifiers should
        also verify the Merkle root matches their computed root.
        """
        return self.hash_chain_proof.chain_valid

    @property
    def is_empty(self) -> bool:
        """Check if this proof represents an empty ledger."""
        return self.total_events == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON export.
        """
        return {
            "proof_id": str(self.proof_id),
            "generated_at": self.generated_at.isoformat(),
            "hash_chain_proof": {
                "genesis_hash": self.hash_chain_proof.genesis_hash,
                "latest_hash": self.hash_chain_proof.latest_hash,
                "total_events": self.hash_chain_proof.total_events,
                "algorithm": self.hash_chain_proof.algorithm,
                "chain_valid": self.hash_chain_proof.chain_valid,
                "first_sequence": self.hash_chain_proof.first_sequence,
                "last_sequence": self.hash_chain_proof.last_sequence,
            },
            "merkle_root": self.merkle_root,
            "total_events": self.total_events,
            "latest_sequence": self.latest_sequence,
            "algorithm": self.algorithm,
            "verification_instructions": self.verification_instructions,
        }


# Default verification instructions for completeness proofs
DEFAULT_VERIFICATION_INSTRUCTIONS = """
LEDGER COMPLETENESS VERIFICATION GUIDE
======================================

This proof demonstrates that the governance ledger is complete and unmodified.
Follow these steps to verify independently.

STEP 1: HASH CHAIN VERIFICATION
-------------------------------
For each event from genesis (sequence 1) to latest:

1. Compute the event hash:
   hash = ALGORITHM(payload || prev_hash)

2. Verify the computed hash matches event.event_hash

3. Verify event.prev_hash equals the previous event's event_hash
   (Genesis event has prev_hash = empty or defined genesis marker)

4. Verify sequence numbers are continuous (1, 2, 3, ...)

If all verifications pass, the hash chain is valid.

STEP 2: MERKLE ROOT VERIFICATION
--------------------------------
1. Collect all event hashes from the ledger
2. Build a Merkle tree using the same algorithm
3. Compare your computed root with the proof's merkle_root

If roots match, all events are accounted for.

STEP 3: COMPLETENESS CHECK
--------------------------
Combine the results:
- Hash chain valid = no tampering
- Merkle root matches = no missing events
- Both pass = ledger is complete and authentic

ALGORITHM NOTES
---------------
- BLAKE3: Modern, fast cryptographic hash
- Hash format: "blake3:hexdigest" or "sha256:hexdigest"
- Merkle tree uses 0x00 prefix for leaves, 0x01 for internal nodes

EXTERNAL VERIFICATION
---------------------
This proof can be verified using:
- The exported ledger data
- Any implementation of the hash algorithms
- No database access or trusted party required

The math proves completeness - you don't need to trust anyone.
"""
