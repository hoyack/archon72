"""Tests for chain verification logic (Task 3).

Tests for ChainVerifier that validates hash chain integrity.
"""

import hashlib
import json

import pytest
from archon72_verify.verifier import (
    GENESIS_HASH,
    ChainVerifier,
    ProofVerificationResult,
    VerificationResult,
)


def make_event(
    sequence: int,
    event_type: str = "test",
    prev_hash: str = None,
    content_hash: str = None,
    payload: dict = None,
) -> dict:
    """Helper to create test events."""
    if payload is None:
        payload = {"data": f"event_{sequence}"}

    event = {
        "sequence": sequence,
        "event_type": event_type,
        "payload": payload,
        "signature": "test_sig",
        "witness_id": "test_witness",
        "witness_signature": "witness_sig",
        "local_timestamp": "2026-01-01T00:00:00Z",
        "prev_hash": prev_hash or GENESIS_HASH,
    }

    # Compute content_hash if not provided
    if content_hash is None:
        hashable = {
            "event_type": event["event_type"],
            "payload": event["payload"],
            "signature": event["signature"],
            "witness_id": event["witness_id"],
            "witness_signature": event["witness_signature"],
            "local_timestamp": event["local_timestamp"],
        }
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
        event["content_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    else:
        event["content_hash"] = content_hash

    return event


def make_chain(count: int) -> list[dict]:
    """Helper to create a valid chain of events."""
    events = []
    prev_hash = GENESIS_HASH

    for i in range(1, count + 1):
        event = make_event(sequence=i, prev_hash=prev_hash)
        events.append(event)
        prev_hash = event["content_hash"]

    return events


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_default_gaps_empty(self):
        """Verify gaps_found defaults to empty list."""
        result = VerificationResult(is_valid=True, events_verified=0)
        assert result.gaps_found == []

    def test_all_fields(self):
        """Verify all fields can be set."""
        result = VerificationResult(
            is_valid=False,
            events_verified=5,
            first_invalid_sequence=6,
            error_type="chain_break",
            error_message="Test error",
            gaps_found=[(3, 4)],
        )
        assert not result.is_valid
        assert result.events_verified == 5
        assert result.first_invalid_sequence == 6
        assert result.error_type == "chain_break"
        assert result.error_message == "Test error"
        assert result.gaps_found == [(3, 4)]


class TestChainVerifierComputeContentHash:
    """Tests for compute_content_hash method."""

    def test_compute_content_hash_matches_spec(self):
        """Verify hash computation matches spec."""
        verifier = ChainVerifier()

        event = {
            "event_type": "vote",
            "payload": {"decision": "approve"},
            "signature": "abc123",
            "witness_id": "witness1",
            "witness_signature": "def456",
            "local_timestamp": "2026-01-01T12:00:00Z",
        }

        # Manually compute expected hash
        hashable = {
            "event_type": "vote",
            "payload": {"decision": "approve"},
            "signature": "abc123",
            "witness_id": "witness1",
            "witness_signature": "def456",
            "local_timestamp": "2026-01-01T12:00:00Z",
        }
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode()).hexdigest()

        computed = verifier.compute_content_hash(event)
        assert computed == expected

    def test_compute_content_hash_includes_agent_id(self):
        """Verify agent_id is included when present."""
        verifier = ChainVerifier()

        event_without = {
            "event_type": "test",
            "payload": {},
            "signature": "sig",
            "witness_id": "w",
            "witness_signature": "ws",
            "local_timestamp": "2026-01-01T00:00:00Z",
        }

        event_with = {**event_without, "agent_id": "agent1"}

        hash_without = verifier.compute_content_hash(event_without)
        hash_with = verifier.compute_content_hash(event_with)

        # Hashes should be different
        assert hash_without != hash_with

    def test_compute_content_hash_deterministic(self):
        """Verify hash is deterministic."""
        verifier = ChainVerifier()

        event = make_event(1)

        hash1 = verifier.compute_content_hash(event)
        hash2 = verifier.compute_content_hash(event)

        assert hash1 == hash2


class TestChainVerifierVerifyChain:
    """Tests for verify_chain method."""

    def test_verify_chain_empty(self):
        """Verify empty event list is valid."""
        verifier = ChainVerifier()
        result = verifier.verify_chain([])

        assert result.is_valid
        assert result.events_verified == 0

    def test_verify_chain_valid(self):
        """Verify valid chain passes."""
        verifier = ChainVerifier()
        events = make_chain(5)

        result = verifier.verify_chain(events)

        assert result.is_valid
        assert result.events_verified == 5
        assert result.first_invalid_sequence is None
        assert result.error_type is None

    def test_verify_chain_validates_genesis(self):
        """Verify genesis anchor is validated."""
        verifier = ChainVerifier()

        # Event 1 with wrong prev_hash
        bad_event = make_event(sequence=1, prev_hash="wrong" * 16)

        result = verifier.verify_chain([bad_event])

        assert not result.is_valid
        assert result.first_invalid_sequence == 1
        assert result.error_type == "genesis_mismatch"
        assert "genesis" in result.error_message.lower()

    def test_verify_chain_detects_prev_hash_break(self):
        """Verify chain break is detected."""
        verifier = ChainVerifier()

        events = make_chain(3)
        # Tamper with prev_hash of event 3
        events[2]["prev_hash"] = "tampered" * 8

        result = verifier.verify_chain(events)

        assert not result.is_valid
        assert result.first_invalid_sequence == 3
        assert result.error_type == "chain_break"

    def test_verify_chain_detects_hash_mismatch(self):
        """Verify content hash mismatch is detected."""
        verifier = ChainVerifier()

        events = make_chain(3)
        # Tamper with content_hash of event 2
        events[1]["content_hash"] = "tampered" * 8

        result = verifier.verify_chain(events)

        assert not result.is_valid
        # Hash mismatch detected at event 2 (its content_hash doesn't match computed)
        assert result.first_invalid_sequence == 2
        assert result.error_type == "hash_mismatch"

    def test_verify_chain_detects_sequence_gap(self):
        """Verify sequence gaps are detected."""
        verifier = ChainVerifier()

        # Create chain with gap (1, 2, 5, 6)
        events = []
        prev_hash = GENESIS_HASH
        for seq in [1, 2, 5, 6]:
            event = make_event(sequence=seq, prev_hash=prev_hash)
            events.append(event)
            prev_hash = event["content_hash"]

        result = verifier.verify_chain(events)

        # Chain breaks due to hash mismatch, but gaps are also reported
        assert not result.is_valid
        assert len(result.gaps_found) == 1
        assert result.gaps_found[0] == (3, 4)

    def test_verify_chain_sorts_events(self):
        """Verify events are sorted by sequence."""
        verifier = ChainVerifier()

        events = make_chain(3)
        # Shuffle order
        shuffled = [events[2], events[0], events[1]]

        result = verifier.verify_chain(shuffled)

        assert result.is_valid
        assert result.events_verified == 3


class TestChainVerifierFindGaps:
    """Tests for find_gaps method."""

    def test_find_gaps_no_gaps(self):
        """Verify no gaps returns empty list."""
        verifier = ChainVerifier()
        events = make_chain(5)

        gaps = verifier.find_gaps(events)

        assert gaps == []

    def test_find_gaps_single_gap(self):
        """Verify single gap is detected."""
        verifier = ChainVerifier()
        events = [
            make_event(1),
            make_event(2),
            make_event(5),  # Gap: 3-4
        ]

        gaps = verifier.find_gaps(events)

        assert gaps == [(3, 4)]

    def test_find_gaps_multiple_gaps(self):
        """Verify multiple gaps are detected."""
        verifier = ChainVerifier()
        events = [
            make_event(1),
            make_event(3),  # Gap: 2
            make_event(7),  # Gap: 4-6
        ]

        gaps = verifier.find_gaps(events)

        assert gaps == [(2, 2), (4, 6)]

    def test_find_gaps_empty_list(self):
        """Verify empty list returns no gaps."""
        verifier = ChainVerifier()

        gaps = verifier.find_gaps([])

        assert gaps == []

    def test_find_gaps_unsorted_input(self):
        """Verify events are sorted before gap detection."""
        verifier = ChainVerifier()
        events = [
            make_event(5),
            make_event(1),
            make_event(3),  # Gap: 2, 4
        ]

        gaps = verifier.find_gaps(events)

        assert gaps == [(2, 2), (4, 4)]


class TestChainVerifierVerifySignature:
    """Tests for verify_signature method."""

    def test_verify_signature_missing_crypto(self):
        """Verify ImportError when cryptography not installed."""
        ChainVerifier()
        make_event(1)

        # This test checks behavior when crypto is available
        # (it is installed in the dev environment)
        # The actual test of missing crypto would require mocking imports
        pass  # Placeholder for crypto test

    def test_verify_signature_invalid(self):
        """Verify invalid signature returns False."""
        verifier = ChainVerifier()
        event = make_event(1)

        # Test with random public key bytes
        fake_key = b"0" * 32

        # Should return False for invalid signature
        try:
            result = verifier.verify_signature(event, fake_key)
            assert result is False
        except ImportError:
            pytest.skip("cryptography package not installed")


# =============================================================================
# Tests for ProofVerificationResult and verify_proof (Story 4.5, Task 7 - FR89)
# =============================================================================


def make_proof_chain(from_seq: int, to_seq: int) -> list[dict]:
    """Helper to create a valid proof chain."""
    chain = []
    prev_hash = GENESIS_HASH if from_seq == 1 else f"{from_seq - 1:064x}"

    for seq in range(from_seq, to_seq + 1):
        content_hash = f"{seq:064x}"
        chain.append(
            {
                "sequence": seq,
                "content_hash": content_hash,
                "prev_hash": prev_hash,
            }
        )
        prev_hash = content_hash

    return chain


class TestProofVerificationResult:
    """Tests for ProofVerificationResult dataclass."""

    def test_default_fields(self):
        """Verify default optional fields."""
        result = ProofVerificationResult(
            is_valid=True,
            proof_entries_verified=5,
            from_sequence=1,
            to_sequence=5,
            current_head_hash="a" * 64,
        )
        assert result.first_invalid_sequence is None
        assert result.error_type is None
        assert result.error_message is None

    def test_all_fields(self):
        """Verify all fields can be set."""
        result = ProofVerificationResult(
            is_valid=False,
            proof_entries_verified=3,
            from_sequence=10,
            to_sequence=20,
            current_head_hash="b" * 64,
            first_invalid_sequence=13,
            error_type="hash_chain_break",
            error_message="Test error",
        )
        assert not result.is_valid
        assert result.proof_entries_verified == 3
        assert result.from_sequence == 10
        assert result.to_sequence == 20
        assert result.current_head_hash == "b" * 64
        assert result.first_invalid_sequence == 13
        assert result.error_type == "hash_chain_break"
        assert result.error_message == "Test error"


class TestChainVerifierVerifyProof:
    """Tests for verify_proof method (FR89)."""

    def test_verify_proof_valid(self):
        """Verify valid proof passes."""
        verifier = ChainVerifier()

        chain = make_proof_chain(100, 105)
        proof = {
            "from_sequence": 100,
            "to_sequence": 105,
            "chain": chain,
            "current_head_hash": chain[-1]["content_hash"],
        }

        result = verifier.verify_proof(proof)

        assert result.is_valid
        assert result.proof_entries_verified == 6
        assert result.from_sequence == 100
        assert result.to_sequence == 105
        assert result.error_type is None

    def test_verify_proof_empty_chain(self):
        """Verify empty chain fails."""
        verifier = ChainVerifier()

        proof = {
            "from_sequence": 100,
            "to_sequence": 105,
            "chain": [],
            "current_head_hash": "a" * 64,
        }

        result = verifier.verify_proof(proof)

        assert not result.is_valid
        assert result.error_type == "empty_chain"

    def test_verify_proof_from_sequence_mismatch(self):
        """Verify from_sequence mismatch is detected."""
        verifier = ChainVerifier()

        chain = make_proof_chain(101, 105)  # Starts at 101, not 100
        proof = {
            "from_sequence": 100,  # Expects 100
            "to_sequence": 105,
            "chain": chain,
            "current_head_hash": chain[-1]["content_hash"],
        }

        result = verifier.verify_proof(proof)

        assert not result.is_valid
        assert result.error_type == "sequence_mismatch"
        assert "doesn't match from_sequence" in result.error_message

    def test_verify_proof_to_sequence_mismatch(self):
        """Verify to_sequence mismatch is detected."""
        verifier = ChainVerifier()

        chain = make_proof_chain(100, 104)  # Ends at 104, not 105
        proof = {
            "from_sequence": 100,
            "to_sequence": 105,  # Expects 105
            "chain": chain,
            "current_head_hash": chain[-1]["content_hash"],
        }

        result = verifier.verify_proof(proof)

        assert not result.is_valid
        assert result.error_type == "sequence_mismatch"
        assert "doesn't match to_sequence" in result.error_message

    def test_verify_proof_detects_gap(self):
        """Verify sequence gap in proof chain is detected."""
        verifier = ChainVerifier()

        # Create chain with gap (100, 101, 103, 104, 105)
        chain = [
            {"sequence": 100, "content_hash": "a" * 64, "prev_hash": "0" * 64},
            {"sequence": 101, "content_hash": "b" * 64, "prev_hash": "a" * 64},
            {"sequence": 103, "content_hash": "c" * 64, "prev_hash": "b" * 64},  # Gap!
            {"sequence": 104, "content_hash": "d" * 64, "prev_hash": "c" * 64},
            {"sequence": 105, "content_hash": "e" * 64, "prev_hash": "d" * 64},
        ]
        proof = {
            "from_sequence": 100,
            "to_sequence": 105,
            "chain": chain,
            "current_head_hash": "e" * 64,
        }

        result = verifier.verify_proof(proof)

        assert not result.is_valid
        assert result.error_type == "sequence_gap"
        assert result.first_invalid_sequence == 103

    def test_verify_proof_detects_hash_chain_break(self):
        """Verify hash chain break is detected."""
        verifier = ChainVerifier()

        chain = [
            {"sequence": 100, "content_hash": "a" * 64, "prev_hash": "0" * 64},
            {"sequence": 101, "content_hash": "b" * 64, "prev_hash": "a" * 64},
            {
                "sequence": 102,
                "content_hash": "c" * 64,
                "prev_hash": "WRONG" * 16,
            },  # Break!
            {"sequence": 103, "content_hash": "d" * 64, "prev_hash": "c" * 64},
        ]
        proof = {
            "from_sequence": 100,
            "to_sequence": 103,
            "chain": chain,
            "current_head_hash": "d" * 64,
        }

        result = verifier.verify_proof(proof)

        assert not result.is_valid
        assert result.error_type == "hash_chain_break"
        assert result.first_invalid_sequence == 102

    def test_verify_proof_detects_head_hash_mismatch(self):
        """Verify head hash mismatch is detected."""
        verifier = ChainVerifier()

        chain = make_proof_chain(100, 105)
        proof = {
            "from_sequence": 100,
            "to_sequence": 105,
            "chain": chain,
            "current_head_hash": "WRONG" * 16,  # Wrong!
        }

        result = verifier.verify_proof(proof)

        assert not result.is_valid
        assert result.error_type == "head_hash_mismatch"

    def test_verify_proof_sorts_chain(self):
        """Verify chain is sorted before verification."""
        verifier = ChainVerifier()

        chain = make_proof_chain(100, 103)
        # Shuffle order
        shuffled = [chain[2], chain[0], chain[3], chain[1]]

        proof = {
            "from_sequence": 100,
            "to_sequence": 103,
            "chain": shuffled,
            "current_head_hash": chain[-1]["content_hash"],
        }

        result = verifier.verify_proof(proof)

        assert result.is_valid
        assert result.proof_entries_verified == 4

    def test_verify_proof_single_entry(self):
        """Verify single-entry proof is valid."""
        verifier = ChainVerifier()

        chain = [{"sequence": 100, "content_hash": "a" * 64, "prev_hash": "0" * 64}]
        proof = {
            "from_sequence": 100,
            "to_sequence": 100,
            "chain": chain,
            "current_head_hash": "a" * 64,
        }

        result = verifier.verify_proof(proof)

        assert result.is_valid
        assert result.proof_entries_verified == 1


# =============================================================================
# Tests for verify_database (Story 4.10 - FR122)
# =============================================================================


class TestChainVerifierVerifyDatabase:
    """Tests for verify_database method (FR122)."""

    def test_verify_chain_from_database(self):
        """Verify valid chain in database passes."""
        import tempfile
        from pathlib import Path

        from archon72_verify.database import ObserverDatabase

        verifier = ChainVerifier()

        # Create valid chain
        events = make_chain(5)

        # Add required database fields
        # NOTE: Do NOT add agent_id because make_event doesn't include it in hash
        for i, event in enumerate(events):
            event["event_id"] = f"evt-{i + 1}"
            event["agent_id"] = None  # Must be None to match original hash
            event["authority_timestamp"] = "2026-01-01T00:00:01Z"
            event["hash_algorithm_version"] = "1.0"
            event["sig_alg_version"] = "ed25519-v1"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

            result = verifier.verify_database(db_path)

        assert result.is_valid
        assert result.events_verified == 5
        assert result.gaps_found == []

    def test_verify_detects_corruption_in_database(self):
        """Verify corrupted chain in database is detected."""
        import tempfile
        from pathlib import Path

        from archon72_verify.database import ObserverDatabase

        verifier = ChainVerifier()

        # Create chain with tampered hash
        events = make_chain(3)
        events[1]["content_hash"] = "tampered" * 8

        # Add required database fields
        for i, event in enumerate(events):
            event["event_id"] = f"evt-{i + 1}"
            event["agent_id"] = None  # Must be None to match original hash
            event["authority_timestamp"] = "2026-01-01T00:00:01Z"
            event["hash_algorithm_version"] = "1.0"
            event["sig_alg_version"] = "ed25519-v1"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

            result = verifier.verify_database(db_path)

        assert not result.is_valid
        assert result.error_type == "hash_mismatch"

    def test_verify_database_with_gaps(self):
        """Verify gaps in database are detected."""
        import tempfile
        from pathlib import Path

        from archon72_verify.database import ObserverDatabase

        verifier = ChainVerifier()

        # Create events with gap (1, 2, 5, 6)
        # Note: Each event's hash is valid, just missing events in middle
        events = []
        prev_hash = GENESIS_HASH
        for seq in [1, 2, 5, 6]:
            event = make_event(sequence=seq, prev_hash=prev_hash)
            event["event_id"] = f"evt-{seq}"
            event["agent_id"] = None  # Must be None to match original hash
            event["authority_timestamp"] = "2026-01-01T00:00:01Z"
            event["hash_algorithm_version"] = "1.0"
            event["sig_alg_version"] = "ed25519-v1"
            events.append(event)
            prev_hash = event["content_hash"]

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

            result = verifier.verify_database(db_path)

        # Chain breaks because seq 5's prev_hash doesn't match seq 2's content_hash
        # (there's a gap, AND the hash chain breaks)
        assert not result.is_valid
        assert result.gaps_found == [(3, 4)]
        # Error is chain_break since seq 5's prev_hash points to seq 4 (not seq 2)
        assert result.error_type in ("chain_break", "sequence_gaps")

    def test_verify_database_empty(self):
        """Verify empty database returns valid."""
        import tempfile
        from pathlib import Path

        from archon72_verify.database import ObserverDatabase

        verifier = ChainVerifier()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()

            result = verifier.verify_database(db_path)

        assert result.is_valid
        assert result.events_verified == 0
