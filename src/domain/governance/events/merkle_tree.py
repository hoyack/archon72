r"""Merkle tree implementation for governance event proof-of-inclusion.

Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion

This module provides Merkle tree functionality for the consent-based
governance event ledger, enabling light verification and independent audit
without requiring full ledger access.

Merkle Tree Properties:
- Each event hash becomes a leaf node (prefixed with 0x00)
- Internal nodes are computed from children (prefixed with 0x01)
- Tree is padded to power of two by duplicating last leaf
- Root per epoch enables compact proofs

Proof-of-Inclusion (Locked per governance-architecture.md)::

                    [Merkle Root]
                    /           \
             [Branch A]      [Branch B]
              /     \          /     \
         [Leaf1]  [Leaf2]  [Leaf3]  [Leaf4]

Proof Format (Locked)::

    {
      "event_id": "uuid",
      "event_hash": "blake3:...",
      "merkle_path": ["hash1", "hash2", "hash3"],
      "merkle_root": "blake3:...",
      "epoch": 42
    }

Security:
- Prefix bytes prevent second-preimage attacks
- 0x00 = leaf node, 0x01 = internal node
- Order-dependent internal hashes for verification integrity

Constitutional Constraints:
- AD-7: Merkle tree proof-of-inclusion
- NFR-CONST-02: Proof-of-inclusion for any entry
- NFR-AUDIT-06: External verification possible
- FR57: Cryptographic proof of completeness

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Proof-of-Inclusion (Locked)]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.governance.events.hash_algorithms import (
    DEFAULT_ALGORITHM,
    SUPPORTED_ALGORITHMS,
    get_hasher,
)

if TYPE_CHECKING:
    pass


# Prefix bytes for domain separation (prevents second-preimage attacks)
_LEAF_PREFIX = b"\x00"
_INTERNAL_PREFIX = b"\x01"


@dataclass(frozen=True)
class MerkleProof:
    """Proof that an event is included in a Merkle tree.

    This proof can be verified independently without accessing the full ledger.
    External verifiers can use verify_merkle_proof() directly.

    Attributes:
        event_id: UUID of the event being proven.
        event_hash: The event's hash (from ledger).
        merkle_path: Sibling hashes from leaf to root.
        merkle_root: Root hash of the Merkle tree.
        epoch: Epoch identifier containing this event.
        leaf_index: Position of event in tree (for verification).
        algorithm: Hash algorithm used ('blake3' or 'sha256').
    """

    event_id: UUID
    event_hash: str
    merkle_path: tuple[str, ...]  # Immutable for frozen dataclass
    merkle_root: str
    epoch: int
    leaf_index: int
    algorithm: str = DEFAULT_ALGORITHM

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation matching locked proof format.
        """
        return {
            "event_id": str(self.event_id),
            "event_hash": self.event_hash,
            "merkle_path": list(self.merkle_path),
            "merkle_root": self.merkle_root,
            "epoch": self.epoch,
            "leaf_index": self.leaf_index,
            "algorithm": self.algorithm,
        }


@dataclass(frozen=True)
class MerkleVerificationResult:
    """Result of Merkle proof verification.

    Attributes:
        is_valid: Whether the proof verification passed.
        reconstructed_root: Root hash computed from proof.
        error_message: Description of failure (if any).
    """

    is_valid: bool
    reconstructed_root: str
    error_message: str = ""


def _compute_leaf_hash(event_hash: str, algorithm: str = DEFAULT_ALGORITHM) -> str:
    """Compute leaf node hash from event hash.

    Prefixes with 0x00 to distinguish leaf nodes from internal nodes,
    preventing second-preimage attacks.

    Args:
        event_hash: The event's hash (algorithm-prefixed).
        algorithm: Hash algorithm to use.

    Returns:
        Algorithm-prefixed leaf hash.
    """
    hasher = get_hasher(algorithm)
    content = _LEAF_PREFIX + event_hash.encode()
    digest = hasher.hash(content)
    return f"{algorithm}:{digest.hex()}"


def _compute_internal_hash(
    left: str, right: str, algorithm: str = DEFAULT_ALGORITHM
) -> str:
    """Compute internal node hash from children.

    Prefixes with 0x01 to distinguish internal nodes from leaf nodes.
    Order matters: H(left || right) != H(right || left).
    This is critical for proof security - wrong index must fail verification.

    Args:
        left: Left child hash (algorithm-prefixed).
        right: Right child hash (algorithm-prefixed).
        algorithm: Hash algorithm to use.

    Returns:
        Algorithm-prefixed internal node hash.
    """
    hasher = get_hasher(algorithm)
    # Order matters! Do NOT sort - left must come before right
    content = _INTERNAL_PREFIX + left.encode() + right.encode()
    digest = hasher.hash(content)
    return f"{algorithm}:{digest.hex()}"


def _next_power_of_two(n: int) -> int:
    """Calculate next power of two >= n.

    Args:
        n: Input number.

    Returns:
        Smallest power of two >= n.
    """
    if n <= 0:
        return 1
    if n & (n - 1) == 0:
        return n  # Already a power of two
    power = 1
    while power < n:
        power *= 2
    return power


class MerkleTree:
    """Merkle tree for event inclusion proofs.

    Constitutional Guarantee:
    - Proofs are verifiable without full ledger access
    - Tampered events produce different root
    - External observers can verify independently

    The tree pads to power of two by duplicating the last leaf,
    which is a standard approach for non-power-of-two inputs.

    Example:
        >>> event_hashes = ["blake3:abc...", "blake3:def...", "blake3:ghi..."]
        >>> tree = MerkleTree(event_hashes)
        >>> proof = tree.generate_proof(0, uuid, event_hashes[0])
        >>> verify_merkle_proof(proof)
        True
    """

    def __init__(
        self,
        event_hashes: list[str],
        algorithm: str = DEFAULT_ALGORITHM,
    ) -> None:
        """Initialize Merkle tree from event hashes.

        Args:
            event_hashes: List of event hashes (algorithm-prefixed).
            algorithm: Hash algorithm for tree construction.

        Raises:
            ValueError: If algorithm is not supported.
        """
        if algorithm not in SUPPORTED_ALGORITHMS:
            raise ValueError(
                f"Unsupported hash algorithm: {algorithm!r}. "
                f"Supported: {', '.join(sorted(SUPPORTED_ALGORITHMS))}"
            )

        self._algorithm = algorithm
        self._original_leaf_count = len(event_hashes)
        self._event_hashes = event_hashes.copy()

        # Compute leaf hashes with prefix
        self._leaves = [_compute_leaf_hash(h, algorithm) for h in event_hashes]

        # Build tree structure
        self._tree = self._build_tree()

    def _build_tree(self) -> list[list[str]]:
        """Build complete Merkle tree from leaves.

        Returns:
            List of tree levels, from leaves (index 0) to root (last index).
        """
        if not self._leaves:
            return [[]]

        # Pad to power of two if needed
        padded_leaves = self._pad_to_power_of_two(self._leaves)

        # Build tree level by level
        tree: list[list[str]] = [padded_leaves]
        current_level = padded_leaves

        while len(current_level) > 1:
            next_level: list[str] = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1]
                parent = _compute_internal_hash(left, right, self._algorithm)
                next_level.append(parent)
            tree.append(next_level)
            current_level = next_level

        return tree

    def _pad_to_power_of_two(self, leaves: list[str]) -> list[str]:
        """Pad leaves to next power of two by duplicating last leaf.

        Args:
            leaves: Original leaf hashes.

        Returns:
            Padded list with length as power of two.
        """
        if not leaves:
            return []

        target = _next_power_of_two(len(leaves))
        if len(leaves) == target:
            return leaves

        # Duplicate last leaf to fill to power of two
        return leaves + [leaves[-1]] * (target - len(leaves))

    @property
    def root(self) -> str:
        """Get Merkle root hash.

        Returns:
            Algorithm-prefixed root hash, or empty hash for empty tree.
        """
        if not self._tree or not self._tree[-1]:
            return f"{self._algorithm}:empty"
        return self._tree[-1][0]

    @property
    def leaf_count(self) -> int:
        """Get number of original leaves (before padding).

        Returns:
            Count of original event hashes.
        """
        return self._original_leaf_count

    @property
    def algorithm(self) -> str:
        """Get hash algorithm used for tree construction.

        Returns:
            Algorithm name (e.g., 'blake3', 'sha256').
        """
        return self._algorithm

    def generate_proof(
        self,
        leaf_index: int,
        event_id: UUID,
        epoch: int = 0,
    ) -> MerkleProof:
        """Generate inclusion proof for event at given index.

        Args:
            leaf_index: Position of event in original list (0-indexed).
            event_id: UUID of the event.
            epoch: Epoch identifier (set by caller).

        Returns:
            MerkleProof that can be verified independently.

        Raises:
            ValueError: If tree is empty.
            IndexError: If leaf_index is out of range.
        """
        # Check for empty tree FIRST
        if not self._tree or not self._event_hashes:
            raise ValueError("Cannot generate proof from empty tree")

        if leaf_index < 0 or leaf_index >= self._original_leaf_count:
            raise IndexError(
                f"Leaf index {leaf_index} out of range [0, {self._original_leaf_count})"
            )

        # Collect sibling hashes along path from leaf to root
        path: list[str] = []
        index = leaf_index

        for level in self._tree[:-1]:  # All levels except root
            sibling_index = index ^ 1  # XOR to get sibling index
            if sibling_index < len(level):
                path.append(level[sibling_index])
            index //= 2

        return MerkleProof(
            event_id=event_id,
            event_hash=self._event_hashes[leaf_index],
            merkle_path=tuple(path),
            merkle_root=self.root,
            epoch=epoch,
            leaf_index=leaf_index,
            algorithm=self._algorithm,
        )


def verify_merkle_proof(proof: MerkleProof) -> MerkleVerificationResult:
    """Verify Merkle proof without accessing ledger.

    This function can be used by external verifiers.
    No database access required - pure computation.

    The verification process:
    1. Compute leaf hash from event_hash
    2. Walk up the tree using merkle_path siblings
    3. Compare reconstructed root with provided merkle_root

    Args:
        proof: The MerkleProof to verify.

    Returns:
        MerkleVerificationResult with verification details.
    """
    try:
        # Verify algorithm is supported
        if proof.algorithm not in SUPPORTED_ALGORITHMS:
            return MerkleVerificationResult(
                is_valid=False,
                reconstructed_root="",
                error_message=f"Unsupported algorithm: {proof.algorithm}",
            )

        # Start with leaf hash of the event
        current = _compute_leaf_hash(proof.event_hash, proof.algorithm)
        index = proof.leaf_index

        # Walk up the tree using siblings from merkle_path
        for sibling in proof.merkle_path:
            if index % 2 == 0:
                # Current is left child
                current = _compute_internal_hash(current, sibling, proof.algorithm)
            else:
                # Current is right child
                current = _compute_internal_hash(sibling, current, proof.algorithm)
            index //= 2

        # Compare reconstructed root with provided root
        is_valid = current == proof.merkle_root

        return MerkleVerificationResult(
            is_valid=is_valid,
            reconstructed_root=current,
            error_message=""
            if is_valid
            else "Reconstructed root does not match provided merkle_root",
        )

    except Exception as e:
        return MerkleVerificationResult(
            is_valid=False,
            reconstructed_root="",
            error_message=f"Verification error: {e}",
        )


def compute_merkle_root(
    event_hashes: list[str],
    algorithm: str = DEFAULT_ALGORITHM,
) -> str:
    """Compute Merkle root for a list of event hashes.

    Convenience function when only the root is needed, not full tree.

    Args:
        event_hashes: List of event hashes (algorithm-prefixed).
        algorithm: Hash algorithm for tree construction.

    Returns:
        Algorithm-prefixed Merkle root hash.
    """
    tree = MerkleTree(event_hashes, algorithm)
    return tree.root
