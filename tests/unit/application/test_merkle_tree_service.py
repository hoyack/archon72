"""Unit tests for MerkleTreeService (Story 4.6, Task 2).

Tests the Merkle tree building and proof generation service for light verification.

Constitutional Constraints:
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Observers SHALL be able to verify event inclusion without downloading full chain
"""

import hashlib

import pytest


def hash_pair(left: str, right: str) -> str:
    """Compute parent hash from two child hashes.

    Uses sorted concatenation to ensure deterministic ordering.
    """
    combined = "".join(sorted([left, right]))
    return hashlib.sha256(combined.encode()).hexdigest()


class TestMerkleTreeServiceBuildTree:
    """Tests for MerkleTreeService.build_tree method."""

    def test_build_merkle_tree_single_event(self) -> None:
        """Test building Merkle tree with single event."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        # Single leaf hash
        leaf_hashes = ["a" * 64]

        root, levels = service.build_tree(leaf_hashes)

        # Root should be the single leaf
        assert root == "a" * 64
        # Single level (just the leaf)
        assert len(levels) == 1
        assert levels[0] == ["a" * 64]

    def test_build_merkle_tree_power_of_two(self) -> None:
        """Test building Merkle tree with power of 2 leaves (no padding)."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        # 4 leaves (power of 2)
        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]

        root, levels = service.build_tree(leaf_hashes)

        # Should have 3 levels: [leaves], [2 parents], [root]
        assert len(levels) == 3

        # Level 0: leaves
        assert len(levels[0]) == 4

        # Level 1: 2 parents
        assert len(levels[1]) == 2
        expected_left = hash_pair("a" * 64, "b" * 64)
        expected_right = hash_pair("c" * 64, "d" * 64)
        assert levels[1][0] == expected_left
        assert levels[1][1] == expected_right

        # Level 2: root
        assert len(levels[2]) == 1
        expected_root = hash_pair(expected_left, expected_right)
        assert root == expected_root

    def test_build_merkle_tree_non_power_of_two_pads(self) -> None:
        """Test building Merkle tree with non-power of 2 (should pad)."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        # 3 leaves (not power of 2)
        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64]

        root, levels = service.build_tree(leaf_hashes)

        # Should pad to 4 leaves
        assert len(levels[0]) == 4
        # Last leaf should be duplicated
        assert levels[0][3] == levels[0][2]

    def test_build_merkle_tree_empty_raises(self) -> None:
        """Test that empty list raises ValueError."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        with pytest.raises(ValueError, match="empty"):
            service.build_tree([])


class TestMerkleTreeServiceGetProof:
    """Tests for MerkleTreeService.get_proof method."""

    def test_get_merkle_proof_for_index_zero(self) -> None:
        """Test generating Merkle proof for first leaf."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
        root, levels = service.build_tree(leaf_hashes)

        # Get proof for leaf 0 (a)
        proof = service.get_proof(0, levels)

        # Should have 2 entries (tree height - 1)
        assert len(proof) == 2

        # First sibling should be 'b' at level 0
        assert proof[0].level == 0
        assert proof[0].sibling_hash == "b" * 64
        assert proof[0].position == "right"

    def test_get_merkle_proof_for_last_index(self) -> None:
        """Test generating Merkle proof for last leaf."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
        root, levels = service.build_tree(leaf_hashes)

        # Get proof for leaf 3 (d)
        proof = service.get_proof(3, levels)

        # Should have 2 entries
        assert len(proof) == 2

        # First sibling should be 'c' at level 0
        assert proof[0].level == 0
        assert proof[0].sibling_hash == "c" * 64
        assert proof[0].position == "left"

    def test_get_merkle_proof_middle_index(self) -> None:
        """Test generating Merkle proof for middle leaf."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
        root, levels = service.build_tree(leaf_hashes)

        # Get proof for leaf 1 (b)
        proof = service.get_proof(1, levels)

        # First sibling should be 'a' at level 0
        assert proof[0].level == 0
        assert proof[0].sibling_hash == "a" * 64
        assert proof[0].position == "left"


class TestMerkleTreeServiceVerifyProof:
    """Tests for MerkleTreeService.verify_proof method."""

    def test_verify_merkle_proof_valid(self) -> None:
        """Test verifying valid Merkle proof."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
        root, levels = service.build_tree(leaf_hashes)

        # Get proof for leaf 0
        proof = service.get_proof(0, levels)

        # Verify should pass
        is_valid = service.verify_proof("a" * 64, proof, root)
        assert is_valid is True

    def test_verify_merkle_proof_invalid_sibling(self) -> None:
        """Test verifying proof with wrong sibling hash."""
        from src.api.models.observer import MerkleProofEntry
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
        root, levels = service.build_tree(leaf_hashes)

        # Create fake proof with wrong sibling (valid hex but wrong value)
        bad_proof = [
            MerkleProofEntry(level=0, position="right", sibling_hash="0" * 64),
            MerkleProofEntry(level=1, position="right", sibling_hash=levels[1][1]),
        ]

        # Verify should fail
        is_valid = service.verify_proof("a" * 64, bad_proof, root)
        assert is_valid is False

    def test_verify_merkle_proof_wrong_leaf(self) -> None:
        """Test verifying proof with wrong leaf hash."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
        root, levels = service.build_tree(leaf_hashes)

        # Get proof for leaf 0
        proof = service.get_proof(0, levels)

        # Verify with wrong leaf should fail
        is_valid = service.verify_proof("x" * 64, proof, root)
        assert is_valid is False

    def test_compute_merkle_root_matches_tree(self) -> None:
        """Test that recomputing root from proof matches tree root."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        leaf_hashes = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
        root, levels = service.build_tree(leaf_hashes)

        # Get proof for each leaf and verify
        for idx, leaf_hash in enumerate(leaf_hashes):
            proof = service.get_proof(idx, levels)
            is_valid = service.verify_proof(leaf_hash, proof, root)
            assert is_valid is True, f"Proof for index {idx} failed"


class TestMerkleTreeServiceLargeTree:
    """Tests for MerkleTreeService with larger trees."""

    def test_build_and_verify_100_leaves(self) -> None:
        """Test building and verifying tree with 100 leaves."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        # 100 unique leaf hashes
        leaf_hashes = [
            hashlib.sha256(f"leaf_{i}".encode()).hexdigest() for i in range(100)
        ]

        root, levels = service.build_tree(leaf_hashes)

        # Tree should be padded to 128 (next power of 2)
        assert len(levels[0]) == 128

        # Verify proof for a random leaf
        for idx in [0, 50, 99]:
            proof = service.get_proof(idx, levels)
            is_valid = service.verify_proof(leaf_hashes[idx], proof, root)
            assert is_valid is True

    def test_proof_size_is_log_n(self) -> None:
        """Test that proof size is O(log n)."""
        from src.application.services.merkle_tree_service import MerkleTreeService

        service = MerkleTreeService()

        # 1024 leaves (2^10)
        leaf_hashes = [
            hashlib.sha256(f"leaf_{i}".encode()).hexdigest() for i in range(1024)
        ]

        root, levels = service.build_tree(leaf_hashes)

        # Proof should have 10 entries (log2(1024))
        proof = service.get_proof(0, levels)
        assert len(proof) == 10
