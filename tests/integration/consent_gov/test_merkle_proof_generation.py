"""Merkle proof generation tests using real Conclave event hashes.

These tests validate the Merkle tree proof-of-inclusion infrastructure
using hash chains built from real Conclave debate data.

Tests:
- Building Merkle tree from speech event hashes
- Generating proofs for individual events
- Verifying proofs independently
- Tree properties (root, leaf count)
- Edge cases (single event, power of two padding)

Constitutional References:
- AD-7: Merkle tree proof-of-inclusion
- NFR-CONST-02: Proof-of-inclusion for any entry
- NFR-AUDIT-06: External verification possible
- FR57: Cryptographic proof of completeness
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.domain.governance.events.hash_chain import chain_events
from src.domain.governance.events.merkle_tree import (
    MerkleTree,
    compute_merkle_root,
    verify_merkle_proof,
)

if TYPE_CHECKING:
    pass


class TestMerkleTreeWithSpeechHashes:
    """Tests for Merkle tree using real speech event hashes."""

    @pytest.mark.asyncio
    async def test_build_tree_from_speech_hashes(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Merkle tree can be built from speech event hashes."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        # Create and chain events (using SHA-256 for test portability)
        events = [make_governance_event(e) for e in debate_entries[:5]]
        chained = chain_events(events, algorithm="sha256")

        # Extract hashes for Merkle tree
        event_hashes = [e.hash for e in chained]

        # Build tree
        tree = MerkleTree(event_hashes, algorithm="sha256")

        assert tree.leaf_count == len(event_hashes)
        assert tree.root.startswith("sha256:")

    @pytest.mark.asyncio
    async def test_generate_proof_for_speech(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Proof can be generated for a specific speech event."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        # Build chain and tree (using SHA-256 for test portability)
        events = [make_governance_event(e) for e in debate_entries[:5]]
        chained = chain_events(events, algorithm="sha256")
        event_hashes = [e.hash for e in chained]

        tree = MerkleTree(event_hashes, algorithm="sha256")

        # Generate proof for first event
        proof = tree.generate_proof(
            leaf_index=0,
            event_id=chained[0].event_id,
            epoch=1,
        )

        assert proof.event_hash == chained[0].hash
        assert proof.merkle_root == tree.root
        assert proof.epoch == 1
        assert proof.leaf_index == 0

    @pytest.mark.asyncio
    async def test_verify_proof_independently(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Proof can be verified without accessing the tree."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:5]]
        chained = chain_events(events, algorithm="sha256")
        event_hashes = [e.hash for e in chained]

        tree = MerkleTree(event_hashes, algorithm="sha256")

        # Generate proof for middle event
        middle_idx = len(chained) // 2
        proof = tree.generate_proof(
            leaf_index=middle_idx,
            event_id=chained[middle_idx].event_id,
            epoch=1,
        )

        # Verify independently (no tree access needed)
        result = verify_merkle_proof(proof)

        assert result.is_valid
        assert result.reconstructed_root == tree.root

    @pytest.mark.asyncio
    async def test_proof_verification_fails_for_tampered_hash(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Tampered event hash fails proof verification."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:5]]
        chained = chain_events(events, algorithm="sha256")
        event_hashes = [e.hash for e in chained]

        tree = MerkleTree(event_hashes, algorithm="sha256")

        # Generate valid proof
        proof = tree.generate_proof(
            leaf_index=0,
            event_id=chained[0].event_id,
            epoch=1,
        )

        # Create tampered proof with modified event_hash
        from dataclasses import replace

        tampered_proof = replace(proof, event_hash="sha256:tampered_hash_000000")

        # Verification should fail
        result = verify_merkle_proof(tampered_proof)

        assert not result.is_valid


class TestMerkleTreeProperties:
    """Tests for Merkle tree properties."""

    @pytest.mark.asyncio
    async def test_consistent_root_for_same_hashes(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Same event hashes always produce same Merkle root."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:5]]
        chained = chain_events(events, algorithm="sha256")
        event_hashes = [e.hash for e in chained]

        # Build tree twice
        tree1 = MerkleTree(event_hashes, algorithm="sha256")
        tree2 = MerkleTree(event_hashes, algorithm="sha256")

        assert tree1.root == tree2.root

    @pytest.mark.asyncio
    async def test_different_order_different_root(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Different event order produces different root."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:4]]
        chained = chain_events(events, algorithm="sha256")
        hashes = [e.hash for e in chained]

        # Create trees with different order
        tree1 = MerkleTree(hashes, algorithm="sha256")
        tree2 = MerkleTree(list(reversed(hashes)), algorithm="sha256")

        # Roots should be different
        assert tree1.root != tree2.root

    @pytest.mark.asyncio
    async def test_tree_pads_to_power_of_two(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Tree properly handles non-power-of-two counts."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        # Use 3 events (not a power of 2)
        events = [make_governance_event(e) for e in debate_entries[:3]]
        chained = chain_events(events, algorithm="sha256")
        hashes = [e.hash for e in chained]

        tree = MerkleTree(hashes, algorithm="sha256")

        # Should report original count (not padded)
        assert tree.leaf_count == 3
        # Root should still be valid
        assert tree.root.startswith("sha256:")


class TestMerkleProofForAllEvents:
    """Tests for generating proofs for all events in a chain."""

    @pytest.mark.asyncio
    async def test_all_events_have_valid_proofs(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Every event in the chain has a valid proof."""
        if len(debate_entries) < 5:
            pytest.skip("Need at least 5 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:8]]
        chained = chain_events(events, algorithm="sha256")
        hashes = [e.hash for e in chained]

        tree = MerkleTree(hashes, algorithm="sha256")

        # Generate and verify proof for each event
        for i, event in enumerate(chained):
            proof = tree.generate_proof(
                leaf_index=i,
                event_id=event.event_id,
                epoch=1,
            )
            result = verify_merkle_proof(proof)

            assert result.is_valid, (
                f"Event {i} failed proof verification: {result.error_message}"
            )

    @pytest.mark.asyncio
    async def test_proof_paths_differ_by_position(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Different events have different proof paths."""
        if len(debate_entries) < 4:
            pytest.skip("Need at least 4 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:4]]
        chained = chain_events(events, algorithm="sha256")
        hashes = [e.hash for e in chained]

        tree = MerkleTree(hashes, algorithm="sha256")

        # Get proofs for different positions
        proof0 = tree.generate_proof(
            leaf_index=0, event_id=chained[0].event_id, epoch=1
        )
        proof1 = tree.generate_proof(
            leaf_index=1, event_id=chained[1].event_id, epoch=1
        )

        # Proof paths should differ
        assert proof0.merkle_path != proof1.merkle_path
        # But same root
        assert proof0.merkle_root == proof1.merkle_root


class TestComputeMerkleRoot:
    """Tests for convenience function compute_merkle_root."""

    @pytest.mark.asyncio
    async def test_compute_root_matches_tree_root(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """compute_merkle_root matches MerkleTree.root."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:5]]
        chained = chain_events(events, algorithm="sha256")
        hashes = [e.hash for e in chained]

        # Full tree
        tree = MerkleTree(hashes, algorithm="sha256")

        # Convenience function
        root = compute_merkle_root(hashes, algorithm="sha256")

        assert root == tree.root


class TestMerkleTreeEdgeCases:
    """Tests for edge cases in Merkle tree."""

    @pytest.mark.asyncio
    async def test_single_event_tree(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Single event produces valid tree and proof."""
        if not debate_entries:
            pytest.skip("No debate entries")

        event = make_governance_event(debate_entries[0])
        chained = chain_events([event], algorithm="sha256")
        hashes = [chained[0].hash]

        tree = MerkleTree(hashes, algorithm="sha256")

        assert tree.leaf_count == 1
        assert tree.root.startswith("sha256:")

        # Proof should work
        proof = tree.generate_proof(
            leaf_index=0,
            event_id=chained[0].event_id,
            epoch=1,
        )
        result = verify_merkle_proof(proof)
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_power_of_two_events(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Power of two event count (no padding needed)."""
        if len(debate_entries) < 8:
            pytest.skip("Need at least 8 debate entries")

        # Exactly 8 events (power of 2)
        events = [make_governance_event(e) for e in debate_entries[:8]]
        chained = chain_events(events, algorithm="sha256")
        hashes = [e.hash for e in chained]

        tree = MerkleTree(hashes, algorithm="sha256")

        assert tree.leaf_count == 8

        # All proofs should verify
        for i in range(8):
            proof = tree.generate_proof(
                leaf_index=i,
                event_id=chained[i].event_id,
                epoch=1,
            )
            assert verify_merkle_proof(proof).is_valid


class TestMerkleTreeWithSHA256:
    """Tests for Merkle tree with SHA-256 algorithm."""

    @pytest.mark.asyncio
    async def test_sha256_tree_and_proofs(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Merkle tree works with SHA-256 hashed events."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries")

        events = [make_governance_event(e) for e in debate_entries[:5]]
        chained = chain_events(events, algorithm="sha256")
        hashes = [e.hash for e in chained]

        # All hashes should be sha256
        for h in hashes:
            assert h.startswith("sha256:")

        tree = MerkleTree(hashes, algorithm="sha256")

        assert tree.root.startswith("sha256:")
        assert tree.algorithm == "sha256"

        # Proof should verify
        proof = tree.generate_proof(
            leaf_index=0,
            event_id=chained[0].event_id,
            epoch=1,
        )
        result = verify_merkle_proof(proof)
        assert result.is_valid
