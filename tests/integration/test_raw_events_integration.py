"""Integration tests for raw events with hashes (Story 4.2, Task 8).

Tests for FR45 compliance: Raw events returned with hashes.

Constitutional Constraints:
- FR45: Query interface SHALL return raw events with hashes
- FR62: Raw event data sufficient for independent hash computation
- FR63: Exact hash algorithm, encoding, field ordering as immutable spec
- FR64: Verification bundles for offline verification
"""

from datetime import datetime, timezone
from uuid import uuid4

from src.api.models.observer import (
    ChainVerificationResult,
    HashVerificationSpec,
    ObserverEventResponse,
)
from src.domain.events.hash_utils import GENESIS_HASH, compute_content_hash


class TestFR45RawEventsWithHashes:
    """Integration tests for FR45: Raw events with hashes."""

    def test_fr45_content_hash_present(self) -> None:
        """Test that content_hash is present in event response (FR45)."""
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            content_hash="a" * 64,
            prev_hash="0" * 64,
            signature="sig123",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert hasattr(response, "content_hash")
        assert response.content_hash is not None
        assert len(response.content_hash) == 64

    def test_fr45_prev_hash_present(self) -> None:
        """Test that prev_hash is present in event response (FR45)."""
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            content_hash="a" * 64,
            prev_hash="b" * 64,
            signature="sig",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert hasattr(response, "prev_hash")
        assert response.prev_hash is not None
        assert len(response.prev_hash) == 64

    def test_fr45_signature_present(self) -> None:
        """Test that signature is present in event response (FR45)."""
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            content_hash="a" * 64,
            prev_hash="0" * 64,
            signature="test_signature_value",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert hasattr(response, "signature")
        assert response.signature == "test_signature_value"

    def test_fr45_raw_payload_untransformed(self) -> None:
        """Test that payload is returned raw without transformation (FR45)."""
        original_payload = {
            "unicode": "日本語🎉",
            "nested": {"deep": {"value": 42}},
            "array": [1, 2, {"x": "y"}],
            "special": 'quotes "here"',
        }

        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload=original_payload,
            content_hash="a" * 64,
            prev_hash="0" * 64,
            signature="sig",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert response.payload == original_payload
        assert response.payload["unicode"] == "日本語🎉"
        assert response.payload["nested"]["deep"]["value"] == 42

    def test_fr45_hash_alg_version_present(self) -> None:
        """Test that hash_algorithm_version is present (FR45)."""
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            content_hash="a" * 64,
            prev_hash="0" * 64,
            signature="sig",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert hasattr(response, "hash_algorithm_version")
        assert response.hash_algorithm_version == "SHA256"

    def test_fr45_sig_alg_version_present(self) -> None:
        """Test that sig_alg_version is present (FR45, AC3)."""
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            content_hash="a" * 64,
            prev_hash="0" * 64,
            signature="sig",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert hasattr(response, "sig_alg_version")
        assert response.sig_alg_version == "Ed25519"


class TestFR62IndependentHashComputation:
    """Integration tests for FR62: Independent hash computation."""

    def test_fr62_sufficient_for_hash_computation(self) -> None:
        """Test that response contains all fields needed for hash computation (FR62)."""
        timestamp = datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc)

        # Create event data for domain hash computation
        event_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": timestamp,
            "agent_id": "agent-001",
        }

        # Compute hash using domain function
        domain_hash = compute_content_hash(event_data)

        # Create API response with same data
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            content_hash=domain_hash,
            prev_hash="0" * 64,
            signature="sig123",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=timestamp,
        )

        # Verify response has compute_expected_hash method
        assert hasattr(response, "compute_expected_hash")

        # Verify computed hash matches domain hash
        api_hash = response.compute_expected_hash()
        assert api_hash == domain_hash
        assert api_hash == response.content_hash


class TestFR63ImmutableSpecification:
    """Integration tests for FR63: Immutable specification."""

    def test_fr63_verification_spec_immutable(self) -> None:
        """Test that verification spec has all immutable fields (FR63)."""
        spec = HashVerificationSpec()

        # Algorithm fields are set
        assert spec.hash_algorithm == "SHA-256"
        assert spec.hash_algorithm_version == 1
        assert spec.signature_algorithm == "Ed25519"
        assert spec.signature_algorithm_version == 1

        # Genesis is documented
        assert spec.genesis_hash == "0" * 64
        assert (
            "sequence" in spec.genesis_description.lower()
            or "first" in spec.genesis_description.lower()
        )

        # Field documentation is present
        assert len(spec.hash_includes) > 0
        assert len(spec.hash_excludes) > 0
        assert spec.json_canonicalization != ""
        assert spec.hash_encoding != ""


class TestGenesisAndChainVerification:
    """Integration tests for genesis hash and chain verification."""

    def test_genesis_prev_hash_is_64_zeros(self) -> None:
        """Test that genesis hash constant is 64 zeros (AC4)."""
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64

        spec = HashVerificationSpec()
        assert spec.genesis_hash == GENESIS_HASH

    def test_chain_verification_result_valid(self) -> None:
        """Test ChainVerificationResult for valid chain."""
        result = ChainVerificationResult(
            start_sequence=1,
            end_sequence=100,
            is_valid=True,
            verified_count=100,
        )

        assert result.is_valid is True
        assert result.verified_count == 100
        assert result.first_invalid_sequence is None
        assert result.error_message is None

    def test_chain_verification_result_invalid(self) -> None:
        """Test ChainVerificationResult for broken chain."""
        result = ChainVerificationResult(
            start_sequence=1,
            end_sequence=100,
            is_valid=False,
            first_invalid_sequence=42,
            error_message="Hash chain broken at sequence 42",
            verified_count=41,
        )

        assert result.is_valid is False
        assert result.first_invalid_sequence == 42
        assert "42" in result.error_message
        assert result.verified_count == 41


class TestAPIResponseContainsAllVerificationData:
    """Test that API response exposes all verification data."""

    def test_all_verification_fields_exposed(self) -> None:
        """Test that all fields needed for verification are in API response."""
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=42,
            event_type="vote.cast",
            payload={"vote": "aye"},
            content_hash="a" * 64,
            prev_hash="b" * 64,
            signature="sig_value",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig_value",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Required for chain verification
        assert hasattr(response, "sequence")
        assert hasattr(response, "content_hash")
        assert hasattr(response, "prev_hash")

        # Required for signature verification
        assert hasattr(response, "signature")
        assert hasattr(response, "witness_signature")
        assert hasattr(response, "sig_alg_version")

        # Required for hash recomputation
        assert hasattr(response, "event_type")
        assert hasattr(response, "payload")
        assert hasattr(response, "local_timestamp")
        assert hasattr(response, "agent_id")
        assert hasattr(response, "witness_id")

        # Algorithm metadata
        assert hasattr(response, "hash_algorithm_version")
        assert hasattr(response, "sig_alg_version")

    def test_json_serialization_preserves_data(self) -> None:
        """Test that JSON serialization preserves all data types."""
        import json

        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=42,
            event_type="test.event",
            payload={
                "integer": 9007199254740993,
                "float": 3.14159,
                "unicode": "日本語",
                "nested": {"value": True},
            },
            content_hash="a" * 64,
            prev_hash="b" * 64,
            signature="sig",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        )

        # Serialize to JSON
        json_str = response.model_dump_json()

        # Parse as dict (external observer would do this)
        parsed_dict = json.loads(json_str)

        # Verify data is preserved in JSON output
        assert parsed_dict["payload"]["integer"] == 9007199254740993
        assert parsed_dict["payload"]["unicode"] == "日本語"
        assert parsed_dict["payload"]["nested"]["value"] is True

        # Verify all required fields are in JSON
        assert "content_hash" in parsed_dict
        assert "prev_hash" in parsed_dict
        assert "signature" in parsed_dict
        assert "hash_algorithm_version" in parsed_dict
        assert "sig_alg_version" in parsed_dict

        # Verify timestamp has Z suffix (ISO 8601 UTC)
        assert "Z" in parsed_dict["local_timestamp"]
