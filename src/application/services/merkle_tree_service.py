"""Merkle tree builder and verifier service (Story 4.6, Task 2).

Service for building Merkle trees from event hashes and generating
proofs for light verification.

Constitutional Constraints:
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Observers SHALL be able to verify event inclusion without downloading full chain

Usage:
    service = MerkleTreeService()
    root, levels = service.build_tree(leaf_hashes)
    proof = service.get_proof(event_index, levels)
    is_valid = service.verify_proof(leaf_hash, proof, expected_root)

Architecture Note:
This service uses MerkleProofEntryDTO from application DTOs to avoid
importing from the API layer. API routes convert to Pydantic models.
"""

import hashlib

from src.application.dtos.observer import MerkleProofEntryDTO


def hash_pair(left: str, right: str) -> str:
    """Compute parent hash from two child hashes.

    Uses sorted concatenation to ensure deterministic ordering.
    This means hash_pair(a, b) == hash_pair(b, a).

    Args:
        left: Left child hash (64-char hex).
        right: Right child hash (64-char hex).

    Returns:
        Parent hash (64-char lowercase hex).
    """
    combined = "".join(sorted([left, right]))
    return hashlib.sha256(combined.encode()).hexdigest()


class MerkleTreeService:
    """Service for building and verifying Merkle trees (FR136, FR137).

    Builds binary Merkle trees from event hashes and generates
    inclusion proofs for light verification without full chain download.

    Tree Structure:
    - Leaves are event content_hashes in sequence order
    - Non-power-of-2 inputs are padded by duplicating the last leaf
    - Parent hash is sorted_concat(left, right) to ensure determinism

    Example:
        For 4 leaves [A, B, C, D]:

                    Root
                   /    \\
               H(A,B)   H(C,D)
               /  \\     /  \\
              A    B   C    D

        Proof for C: [(D, right), (H(A,B), left)]
    """

    def build_tree(self, leaf_hashes: list[str]) -> tuple[str, list[list[str]]]:
        """Build Merkle tree from leaf hashes.

        Pads to next power of 2 if necessary (duplicating last hash).

        Args:
            leaf_hashes: List of content_hash values from events.

        Returns:
            Tuple of (root_hash, tree_levels).
            tree_levels[0] = leaves, tree_levels[-1] = [root].

        Raises:
            ValueError: If leaf_hashes is empty.
        """
        if not leaf_hashes:
            raise ValueError("Cannot build tree from empty list")

        # Pad to power of 2
        leaves = list(leaf_hashes)
        while len(leaves) & (len(leaves) - 1):  # Not power of 2
            leaves.append(leaves[-1])  # Duplicate last

        levels: list[list[str]] = [leaves]
        current = leaves

        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                parent = hash_pair(current[i], current[i + 1])
                next_level.append(parent)
            levels.append(next_level)
            current = next_level

        return current[0], levels

    def get_proof(
        self,
        leaf_index: int,
        tree_levels: list[list[str]],
    ) -> list[MerkleProofEntryDTO]:
        """Generate Merkle proof for a leaf at given index.

        Args:
            leaf_index: Index of leaf in tree (0-based).
            tree_levels: Tree levels from build_tree().

        Returns:
            List of MerkleProofEntryDTO from leaf to root.
        """
        path = []
        idx = leaf_index

        for level in range(len(tree_levels) - 1):
            is_right = idx % 2 == 1
            sibling_idx = idx - 1 if is_right else idx + 1

            if sibling_idx < len(tree_levels[level]):
                sibling_hash = tree_levels[level][sibling_idx]
                path.append(
                    MerkleProofEntryDTO(
                        level=level,
                        position="left" if is_right else "right",
                        sibling_hash=sibling_hash,
                    )
                )

            idx //= 2

        return path

    def verify_proof(
        self,
        leaf_hash: str,
        proof: list[MerkleProofEntryDTO],
        expected_root: str,
    ) -> bool:
        """Verify a Merkle proof.

        Args:
            leaf_hash: Content hash of the event.
            proof: List of sibling hashes.
            expected_root: Expected Merkle root to match.

        Returns:
            True if proof is valid, False otherwise.
        """
        current = leaf_hash

        for entry in proof:
            if entry.position == "left":
                current = hash_pair(entry.sibling_hash, current)
            else:
                current = hash_pair(current, entry.sibling_hash)

        return current == expected_root

    def generate_proof(
        self,
        leaves: list[str],
        index: int,
    ) -> list[MerkleProofEntryDTO]:
        """Convenience method to build tree and generate proof in one call.

        Builds the Merkle tree from leaves and returns the proof path
        for the leaf at the given index.

        Args:
            leaves: List of content_hash values from events.
            index: Index of leaf to generate proof for (0-based).

        Returns:
            List of MerkleProofEntryDTO from leaf to root.

        Raises:
            ValueError: If leaves is empty or index is out of range.
        """
        if not leaves:
            raise ValueError("Cannot generate proof from empty list")
        if index < 0 or index >= len(leaves):
            raise ValueError(f"Index {index} out of range for {len(leaves)} leaves")

        _, tree_levels = self.build_tree(leaves)
        return self.get_proof(index, tree_levels)
