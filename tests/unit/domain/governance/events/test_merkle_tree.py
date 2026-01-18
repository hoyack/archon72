"""Unit tests for Merkle tree implementation.

Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion

Tests cover:
- Merkle tree construction (power-of-two and non-power-of-two)
- Proof generation for all leaf positions
- Proof verification (valid and tampered)
- Both BLAKE3 and SHA-256 algorithms
- Edge cases (single event, empty tree)
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.governance.events.merkle_tree import (
    MerkleProof,
    MerkleTree,
    MerkleVerificationResult,
    _compute_internal_hash,
    _compute_leaf_hash,
    _next_power_of_two,
    compute_merkle_root,
    verify_merkle_proof,
)


class TestNextPowerOfTwo:
    """Tests for _next_power_of_two helper."""

    def test_zero_returns_one(self) -> None:
        """Zero should return 1."""
        assert _next_power_of_two(0) == 1

    def test_negative_returns_one(self) -> None:
        """Negative should return 1."""
        assert _next_power_of_two(-5) == 1

    def test_one_returns_one(self) -> None:
        """1 is already a power of two."""
        assert _next_power_of_two(1) == 1

    def test_power_of_two_returns_same(self) -> None:
        """Powers of two return themselves."""
        assert _next_power_of_two(2) == 2
        assert _next_power_of_two(4) == 4
        assert _next_power_of_two(8) == 8
        assert _next_power_of_two(16) == 16
        assert _next_power_of_two(1024) == 1024

    def test_non_power_of_two_returns_next(self) -> None:
        """Non-powers of two return the next power."""
        assert _next_power_of_two(3) == 4
        assert _next_power_of_two(5) == 8
        assert _next_power_of_two(6) == 8
        assert _next_power_of_two(7) == 8
        assert _next_power_of_two(9) == 16
        assert _next_power_of_two(100) == 128


class TestLeafHash:
    """Tests for _compute_leaf_hash."""

    def test_leaf_hash_blake3(self) -> None:
        """Leaf hash with BLAKE3 has correct prefix."""
        event_hash = (
            "blake3:abc123def456789012345678901234567890123456789012345678901234"
        )
        result = _compute_leaf_hash(event_hash, "blake3")
        assert result.startswith("blake3:")
        assert len(result) == 7 + 64  # prefix + 64 hex chars

    def test_leaf_hash_sha256(self) -> None:
        """Leaf hash with SHA-256 has correct prefix."""
        event_hash = (
            "sha256:abc123def456789012345678901234567890123456789012345678901234"
        )
        result = _compute_leaf_hash(event_hash, "sha256")
        assert result.startswith("sha256:")
        assert len(result) == 7 + 64  # prefix + 64 hex chars

    def test_different_inputs_different_hashes(self) -> None:
        """Different inputs produce different hashes."""
        hash1 = _compute_leaf_hash("blake3:aaa", "blake3")
        hash2 = _compute_leaf_hash("blake3:bbb", "blake3")
        assert hash1 != hash2

    def test_same_input_same_hash(self) -> None:
        """Same input produces same hash (deterministic)."""
        event_hash = "blake3:abc123"
        hash1 = _compute_leaf_hash(event_hash, "blake3")
        hash2 = _compute_leaf_hash(event_hash, "blake3")
        assert hash1 == hash2


class TestInternalHash:
    """Tests for _compute_internal_hash."""

    def test_internal_hash_blake3(self) -> None:
        """Internal hash with BLAKE3 has correct prefix."""
        left = "blake3:aaa"
        right = "blake3:bbb"
        result = _compute_internal_hash(left, right, "blake3")
        assert result.startswith("blake3:")
        assert len(result) == 7 + 64

    def test_internal_hash_order_matters(self) -> None:
        """Order matters for internal hashes (security property)."""
        left = "blake3:aaa"
        right = "blake3:bbb"
        result1 = _compute_internal_hash(left, right, "blake3")
        result2 = _compute_internal_hash(right, left, "blake3")
        # H(left || right) != H(right || left)
        assert result1 != result2

    def test_different_children_different_hash(self) -> None:
        """Different children produce different hashes."""
        hash1 = _compute_internal_hash("blake3:aaa", "blake3:bbb", "blake3")
        hash2 = _compute_internal_hash("blake3:aaa", "blake3:ccc", "blake3")
        assert hash1 != hash2


class TestMerkleTreeConstruction:
    """Tests for MerkleTree construction."""

    def test_empty_tree(self) -> None:
        """Empty tree has empty root."""
        tree = MerkleTree([])
        assert tree.root == "blake3:empty"
        assert tree.leaf_count == 0

    def test_single_event_tree(self) -> None:
        """Tree with one event has non-empty root."""
        hashes = ["blake3:abc123def456789012345678901234567890123456789012345678901234"]
        tree = MerkleTree(hashes)
        assert tree.root != "blake3:empty"
        assert tree.root.startswith("blake3:")
        assert tree.leaf_count == 1

    def test_two_events_tree(self) -> None:
        """Tree with two events (power of two)."""
        hashes = [
            "blake3:abc123def456789012345678901234567890123456789012345678901234",
            "blake3:def456abc789012345678901234567890123456789012345678901234567",
        ]
        tree = MerkleTree(hashes)
        assert tree.root.startswith("blake3:")
        assert tree.leaf_count == 2

    def test_four_events_tree(self) -> None:
        """Tree with four events (power of two)."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        assert tree.root.startswith("blake3:")
        assert tree.leaf_count == 4

    def test_three_events_tree_pads_to_four(self) -> None:
        """Tree with three events pads to four (power of two)."""
        hashes = [f"blake3:hash{i:060d}" for i in range(3)]
        tree = MerkleTree(hashes)
        assert tree.root.startswith("blake3:")
        assert tree.leaf_count == 3

    def test_five_events_tree_pads_to_eight(self) -> None:
        """Tree with five events pads to eight."""
        hashes = [f"blake3:hash{i:060d}" for i in range(5)]
        tree = MerkleTree(hashes)
        assert tree.root.startswith("blake3:")
        assert tree.leaf_count == 5

    def test_seven_events_tree(self) -> None:
        """Tree with seven events pads to eight."""
        hashes = [f"blake3:hash{i:060d}" for i in range(7)]
        tree = MerkleTree(hashes)
        assert tree.root.startswith("blake3:")
        assert tree.leaf_count == 7

    def test_sha256_algorithm(self) -> None:
        """Tree construction works with SHA-256."""
        hashes = [f"sha256:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes, algorithm="sha256")
        assert tree.root.startswith("sha256:")
        assert tree.algorithm == "sha256"

    def test_invalid_algorithm_raises(self) -> None:
        """Invalid algorithm raises ValueError."""
        hashes = ["blake3:abc123"]
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            MerkleTree(hashes, algorithm="md5")

    def test_deterministic_root(self) -> None:
        """Same input produces same root (deterministic)."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree1 = MerkleTree(hashes)
        tree2 = MerkleTree(hashes)
        assert tree1.root == tree2.root

    def test_different_input_different_root(self) -> None:
        """Different input produces different root."""
        hashes1 = [f"blake3:hash{i:060d}" for i in range(4)]
        hashes2 = [f"blake3:hash{i + 10:060d}" for i in range(4)]
        tree1 = MerkleTree(hashes1)
        tree2 = MerkleTree(hashes2)
        assert tree1.root != tree2.root


class TestMerkleProofGeneration:
    """Tests for Merkle proof generation."""

    def test_proof_for_first_leaf(self) -> None:
        """Generate proof for first leaf (index 0)."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=42)

        assert proof.event_id == event_id
        assert proof.event_hash == hashes[0]
        assert proof.merkle_root == tree.root
        assert proof.epoch == 42
        assert proof.leaf_index == 0
        assert proof.algorithm == "blake3"
        assert len(proof.merkle_path) == 2  # log2(4) = 2

    def test_proof_for_last_leaf(self) -> None:
        """Generate proof for last leaf."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(3, event_id, epoch=1)

        assert proof.leaf_index == 3
        assert proof.merkle_root == tree.root
        assert len(proof.merkle_path) == 2

    def test_proof_for_middle_leaf(self) -> None:
        """Generate proof for middle leaf."""
        hashes = [f"blake3:hash{i:060d}" for i in range(8)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(3, event_id, epoch=5)

        assert proof.leaf_index == 3
        assert len(proof.merkle_path) == 3  # log2(8) = 3

    def test_proof_for_single_event_tree(self) -> None:
        """Generate proof for single event tree."""
        hashes = ["blake3:abc123def456789012345678901234567890123456789012345678901234"]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=0)

        assert proof.leaf_index == 0
        assert proof.merkle_root == tree.root
        # Single event: leaf hash IS the root, no siblings needed
        # _next_power_of_two(1) = 1, so no padding occurs
        assert len(proof.merkle_path) == 0

    def test_proof_index_out_of_range_raises(self) -> None:
        """Proof for index out of range raises IndexError."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)

        with pytest.raises(IndexError, match="out of range"):
            tree.generate_proof(4, uuid4(), epoch=0)

        with pytest.raises(IndexError, match="out of range"):
            tree.generate_proof(-1, uuid4(), epoch=0)

    def test_proof_from_empty_tree_raises(self) -> None:
        """Proof from empty tree raises ValueError."""
        tree = MerkleTree([])

        with pytest.raises(ValueError, match="empty tree"):
            tree.generate_proof(0, uuid4(), epoch=0)

    def test_all_proofs_for_power_of_two(self) -> None:
        """Generate valid proofs for all leaves in power-of-two tree."""
        hashes = [f"blake3:hash{i:060d}" for i in range(8)]
        tree = MerkleTree(hashes)

        for i in range(8):
            proof = tree.generate_proof(i, uuid4(), epoch=0)
            assert proof.leaf_index == i
            assert proof.merkle_root == tree.root
            result = verify_merkle_proof(proof)
            assert result.is_valid, (
                f"Proof for index {i} failed: {result.error_message}"
            )

    def test_all_proofs_for_non_power_of_two(self) -> None:
        """Generate valid proofs for all leaves in non-power-of-two tree."""
        hashes = [f"blake3:hash{i:060d}" for i in range(5)]
        tree = MerkleTree(hashes)

        for i in range(5):
            proof = tree.generate_proof(i, uuid4(), epoch=0)
            assert proof.leaf_index == i
            result = verify_merkle_proof(proof)
            assert result.is_valid, (
                f"Proof for index {i} failed: {result.error_message}"
            )


class TestMerkleProofVerification:
    """Tests for Merkle proof verification."""

    def test_valid_proof_verifies(self) -> None:
        """Valid proof passes verification."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=0)
        result = verify_merkle_proof(proof)

        assert result.is_valid
        assert result.reconstructed_root == tree.root
        assert result.error_message == ""

    def test_tampered_event_hash_fails(self) -> None:
        """Proof with tampered event hash fails verification."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=0)

        # Create tampered proof
        tampered = MerkleProof(
            event_id=proof.event_id,
            event_hash="blake3:tampered_hash_value_that_is_64_characters_long_12345678",
            merkle_path=proof.merkle_path,
            merkle_root=proof.merkle_root,
            epoch=proof.epoch,
            leaf_index=proof.leaf_index,
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(tampered)
        assert not result.is_valid
        assert "does not match" in result.error_message

    def test_tampered_merkle_path_fails(self) -> None:
        """Proof with tampered merkle path fails verification."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=0)

        # Create tampered path
        tampered_path = list(proof.merkle_path)
        tampered_path[0] = "blake3:tampered_sibling_hash_that_is_64_characters_long_"

        tampered = MerkleProof(
            event_id=proof.event_id,
            event_hash=proof.event_hash,
            merkle_path=tuple(tampered_path),
            merkle_root=proof.merkle_root,
            epoch=proof.epoch,
            leaf_index=proof.leaf_index,
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(tampered)
        assert not result.is_valid

    def test_tampered_merkle_root_fails(self) -> None:
        """Proof with tampered merkle root fails verification."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=0)

        tampered = MerkleProof(
            event_id=proof.event_id,
            event_hash=proof.event_hash,
            merkle_path=proof.merkle_path,
            merkle_root="blake3:fake_root_hash_that_is_exactly_64_characters_long_abc",
            epoch=proof.epoch,
            leaf_index=proof.leaf_index,
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(tampered)
        assert not result.is_valid

    def test_wrong_leaf_index_fails(self) -> None:
        """Proof with wrong leaf index fails verification."""
        hashes = [f"blake3:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes)
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=0)

        # Use wrong index
        tampered = MerkleProof(
            event_id=proof.event_id,
            event_hash=proof.event_hash,
            merkle_path=proof.merkle_path,
            merkle_root=proof.merkle_root,
            epoch=proof.epoch,
            leaf_index=1,  # Wrong index
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(tampered)
        assert not result.is_valid

    def test_invalid_algorithm_fails(self) -> None:
        """Proof with unsupported algorithm fails verification."""
        proof = MerkleProof(
            event_id=uuid4(),
            event_hash="md5:abc123",
            merkle_path=(),
            merkle_root="md5:root",
            epoch=0,
            leaf_index=0,
            algorithm="md5",
        )

        result = verify_merkle_proof(proof)
        assert not result.is_valid
        assert "Unsupported algorithm" in result.error_message


class TestMerkleProofWithSha256:
    """Tests for Merkle proof with SHA-256 algorithm."""

    def test_sha256_tree_and_proof(self) -> None:
        """SHA-256 tree generates valid proofs."""
        hashes = [f"sha256:hash{i:060d}" for i in range(4)]
        tree = MerkleTree(hashes, algorithm="sha256")
        event_id = uuid4()

        proof = tree.generate_proof(0, event_id, epoch=0)

        assert proof.algorithm == "sha256"
        assert proof.merkle_root.startswith("sha256:")

        result = verify_merkle_proof(proof)
        assert result.is_valid

    def test_all_sha256_proofs_valid(self) -> None:
        """All proofs in SHA-256 tree are valid."""
        hashes = [f"sha256:hash{i:060d}" for i in range(8)]
        tree = MerkleTree(hashes, algorithm="sha256")

        for i in range(8):
            proof = tree.generate_proof(i, uuid4(), epoch=0)
            result = verify_merkle_proof(proof)
            assert result.is_valid


class TestMerkleProofToDict:
    """Tests for MerkleProof.to_dict() serialization."""

    def test_to_dict_format(self) -> None:
        """to_dict() returns correct format."""
        event_id = uuid4()
        proof = MerkleProof(
            event_id=event_id,
            event_hash="blake3:abc123",
            merkle_path=("blake3:sibling1", "blake3:sibling2"),
            merkle_root="blake3:root",
            epoch=42,
            leaf_index=3,
            algorithm="blake3",
        )

        d = proof.to_dict()

        assert d["event_id"] == str(event_id)
        assert d["event_hash"] == "blake3:abc123"
        assert d["merkle_path"] == ["blake3:sibling1", "blake3:sibling2"]
        assert d["merkle_root"] == "blake3:root"
        assert d["epoch"] == 42
        assert d["leaf_index"] == 3
        assert d["algorithm"] == "blake3"


class TestComputeMerkleRoot:
    """Tests for compute_merkle_root convenience function."""

    def test_compute_root_matches_tree(self) -> None:
        """compute_merkle_root returns same as MerkleTree.root."""
        hashes = [f"blake3:hash{i:060d}" for i in range(5)]

        tree = MerkleTree(hashes)
        root = compute_merkle_root(hashes)

        assert root == tree.root

    def test_compute_root_empty(self) -> None:
        """compute_merkle_root handles empty list."""
        root = compute_merkle_root([])
        assert root == "blake3:empty"


class TestMerkleVerificationResult:
    """Tests for MerkleVerificationResult dataclass."""

    def test_valid_result(self) -> None:
        """Valid result has correct fields."""
        result = MerkleVerificationResult(
            is_valid=True,
            reconstructed_root="blake3:abc123",
            error_message="",
        )
        assert result.is_valid
        assert result.reconstructed_root == "blake3:abc123"
        assert result.error_message == ""

    def test_invalid_result(self) -> None:
        """Invalid result has error message."""
        result = MerkleVerificationResult(
            is_valid=False,
            reconstructed_root="blake3:different",
            error_message="Tampered proof",
        )
        assert not result.is_valid
        assert result.error_message == "Tampered proof"
