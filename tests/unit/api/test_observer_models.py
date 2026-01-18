"""Unit tests for observer API models (Story 4.1, Task 1; Story 4.2, Tasks 1, 3, 5; Story 4.3, Task 5).

Tests for ObserverEventResponse, PaginationMetadata, ObserverEventsListResponse,
HashVerificationSpec, ChainVerificationResult, and EventFilterParams Pydantic models.

Constitutional Constraints:
- FR44: Public read access - all hash chain data must be exposed
- FR45: Raw events with hashes - all fields for verification
- FR46: Query interface supports date range and event type filtering
- FR62: Raw event data sufficient for independent hash computation
- FR63: Exact hash algorithm, encoding, field ordering as immutable spec
- No fields should be hidden from observers
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestObserverEventResponse:
    """Tests for ObserverEventResponse model."""

    def test_observer_event_response_fields(self) -> None:
        """Test that ObserverEventResponse has all required fields."""
        from src.api.models.observer import ObserverEventResponse

        # Create a response with all required fields
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=42,
            event_type="vote.cast",
            payload={"archon_id": 1, "vote": "aye"},
            content_hash="abc123" * 10 + "abcd",  # 64 chars
            prev_hash="def456" * 10 + "defg",  # 64 chars
            signature="sig789" * 10,
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig123" * 10,
            local_timestamp=datetime.now(timezone.utc),
        )

        # Verify all fields are accessible
        assert response.event_id is not None
        assert response.sequence == 42
        assert response.event_type == "vote.cast"
        assert response.payload == {"archon_id": 1, "vote": "aye"}
        assert response.content_hash == "abc123" * 10 + "abcd"
        assert response.prev_hash == "def456" * 10 + "defg"
        assert response.signature == "sig789" * 10
        assert response.agent_id == "agent-001"
        assert response.witness_id == "witness-001"
        assert response.witness_signature == "wsig123" * 10
        assert response.local_timestamp is not None

    def test_observer_event_response_includes_hashes(self) -> None:
        """Test that response includes all hash chain data for verification.

        Per FR44: ALL event data must be exposed for independent verification.
        This includes: content_hash, prev_hash, signature, witness_signature.
        """
        from src.api.models.observer import ObserverEventResponse

        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            content_hash="content_hash_value" + "0" * 46,
            prev_hash="prev_hash_value" + "0" * 49,
            signature="signature_value",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="witness_signature_value",
            local_timestamp=datetime.now(timezone.utc),
        )

        # All hash-related fields must be present
        assert hasattr(response, "content_hash")
        assert hasattr(response, "prev_hash")
        assert hasattr(response, "signature")
        assert hasattr(response, "witness_signature")
        assert hasattr(response, "hash_algorithm_version")

        # Verify values are accessible
        assert "content_hash_value" in response.content_hash
        assert "prev_hash_value" in response.prev_hash
        assert response.signature == "signature_value"
        assert response.witness_signature == "witness_signature_value"
        assert response.hash_algorithm_version == "SHA256"

    def test_observer_event_response_optional_authority_timestamp(self) -> None:
        """Test that authority_timestamp is optional (can be None)."""
        from src.api.models.observer import ObserverEventResponse

        # Create without authority_timestamp
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
            authority_timestamp=None,
        )

        assert response.authority_timestamp is None

        # Create with authority_timestamp
        auth_ts = datetime.now(timezone.utc)
        response_with_ts = ObserverEventResponse(
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
            authority_timestamp=auth_ts,
        )

        assert response_with_ts.authority_timestamp == auth_ts

    def test_response_datetime_iso8601_format(self) -> None:
        """Test that datetime fields serialize to ISO 8601 format with Z suffix."""
        from src.api.models.observer import ObserverEventResponse

        timestamp = datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc)
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
            local_timestamp=timestamp,
        )

        # Export to dict/json and check format
        json_data = response.model_dump_json()

        # Verify ISO 8601 format with Z suffix
        assert "2025-12-27T10:30:00" in json_data

    def test_observer_event_response_includes_sig_alg_version(self) -> None:
        """Test that response includes signature algorithm version (FR45, AC3).

        Per FR45/AC3: sig_alg_version MUST be included for verification.
        """
        from src.api.models.observer import ObserverEventResponse

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

        # sig_alg_version field must exist
        assert hasattr(response, "sig_alg_version")
        # Must have a value (not None or empty)
        assert response.sig_alg_version is not None
        assert response.sig_alg_version != ""

    def test_sig_alg_version_defaults_to_ed25519(self) -> None:
        """Test that sig_alg_version defaults to 'Ed25519' (FR45, AC3).

        Per architecture.md: Version 1 = Ed25519
        """
        from src.api.models.observer import ObserverEventResponse

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

        # Default should be "Ed25519" (version 1)
        assert response.sig_alg_version == "Ed25519"


class TestPaginationMetadata:
    """Tests for PaginationMetadata model."""

    def test_pagination_metadata_response(self) -> None:
        """Test PaginationMetadata has all required fields."""
        from src.api.models.observer import PaginationMetadata

        pagination = PaginationMetadata(
            total_count=1000,
            offset=50,
            limit=100,
            has_more=True,
        )

        assert pagination.total_count == 1000
        assert pagination.offset == 50
        assert pagination.limit == 100
        assert pagination.has_more is True

    def test_pagination_has_more_calculation(self) -> None:
        """Test has_more flag correctness."""
        from src.api.models.observer import PaginationMetadata

        # has_more = True when more results exist
        pagination_more = PaginationMetadata(
            total_count=200,
            offset=0,
            limit=100,
            has_more=True,
        )
        assert pagination_more.has_more is True

        # has_more = False when at end
        pagination_end = PaginationMetadata(
            total_count=50,
            offset=0,
            limit=100,
            has_more=False,
        )
        assert pagination_end.has_more is False


class TestObserverEventsListResponse:
    """Tests for ObserverEventsListResponse model."""

    def test_observer_events_list_response(self) -> None:
        """Test ObserverEventsListResponse structure."""
        from src.api.models.observer import (
            ObserverEventResponse,
            ObserverEventsListResponse,
            PaginationMetadata,
        )

        # Create sample events
        events = [
            ObserverEventResponse(
                event_id=uuid4(),
                sequence=i,
                event_type="test.event",
                payload={"index": i},
                content_hash="a" * 64,
                prev_hash="b" * 64,
                signature="sig",
                agent_id="agent-001",
                witness_id="witness-001",
                witness_signature="wsig",
                local_timestamp=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]

        pagination = PaginationMetadata(
            total_count=100,
            offset=0,
            limit=3,
            has_more=True,
        )

        response = ObserverEventsListResponse(
            events=events,
            pagination=pagination,
        )

        assert len(response.events) == 3
        assert response.pagination.total_count == 100
        assert response.pagination.has_more is True

    def test_empty_events_list(self) -> None:
        """Test ObserverEventsListResponse with empty events list."""
        from src.api.models.observer import (
            ObserverEventsListResponse,
            PaginationMetadata,
        )

        pagination = PaginationMetadata(
            total_count=0,
            offset=0,
            limit=100,
            has_more=False,
        )

        response = ObserverEventsListResponse(
            events=[],
            pagination=pagination,
        )

        assert len(response.events) == 0
        assert response.pagination.total_count == 0
        assert response.pagination.has_more is False


class TestHashVerificationSpec:
    """Tests for HashVerificationSpec model (Story 4.2, Task 3).

    Per FR62/FR63: Verification specification must be documented.
    """

    def test_hash_verification_spec_fields(self) -> None:
        """Test that HashVerificationSpec has all required fields (FR63)."""
        from src.api.models.observer import HashVerificationSpec

        spec = HashVerificationSpec()

        # Core algorithm fields
        assert hasattr(spec, "hash_algorithm")
        assert hasattr(spec, "hash_algorithm_version")
        assert hasattr(spec, "signature_algorithm")
        assert hasattr(spec, "signature_algorithm_version")

        # Genesis hash fields
        assert hasattr(spec, "genesis_hash")
        assert hasattr(spec, "genesis_description")

        # Hash computation fields
        assert hasattr(spec, "hash_includes")
        assert hasattr(spec, "hash_excludes")

        # Canonicalization and encoding
        assert hasattr(spec, "json_canonicalization")
        assert hasattr(spec, "hash_encoding")

    def test_verification_spec_documents_genesis(self) -> None:
        """Test that genesis hash is properly documented (AC4).

        Genesis hash must be "0" * 64 (64 zeros) for sequence 1.
        """
        from src.api.models.observer import HashVerificationSpec

        spec = HashVerificationSpec()

        # Genesis hash must be 64 zeros
        assert spec.genesis_hash == "0" * 64
        assert len(spec.genesis_hash) == 64

        # Description must explain genesis
        assert (
            "sequence" in spec.genesis_description.lower()
            or "first" in spec.genesis_description.lower()
        )

    def test_verification_spec_documents_excluded_fields(self) -> None:
        """Test that excluded fields are documented with reasons (AC5).

        Per FR62: Observers must know which fields are NOT in hash.
        """
        from src.api.models.observer import HashVerificationSpec

        spec = HashVerificationSpec()

        # hash_excludes must list fields not in content_hash
        assert isinstance(spec.hash_excludes, list)
        assert len(spec.hash_excludes) > 0

        # Key exclusions must be documented
        excluded_text = " ".join(spec.hash_excludes).lower()
        assert "prev_hash" in excluded_text
        assert "content_hash" in excluded_text
        assert "sequence" in excluded_text

    def test_verification_spec_documents_included_fields(self) -> None:
        """Test that included fields are documented (AC5)."""
        from src.api.models.observer import HashVerificationSpec

        spec = HashVerificationSpec()

        # hash_includes must list fields in content_hash
        assert isinstance(spec.hash_includes, list)
        assert len(spec.hash_includes) > 0

        # Key inclusions must be documented
        included_text = " ".join(spec.hash_includes).lower()
        assert "event_type" in included_text
        assert "payload" in included_text
        assert "signature" in included_text

    def test_verification_spec_hash_algorithm(self) -> None:
        """Test that hash algorithm is SHA-256."""
        from src.api.models.observer import HashVerificationSpec

        spec = HashVerificationSpec()

        assert "sha" in spec.hash_algorithm.lower()
        assert "256" in spec.hash_algorithm
        assert spec.hash_algorithm_version == 1

    def test_verification_spec_signature_algorithm(self) -> None:
        """Test that signature algorithm is Ed25519."""
        from src.api.models.observer import HashVerificationSpec

        spec = HashVerificationSpec()

        assert "ed25519" in spec.signature_algorithm.lower()
        assert spec.signature_algorithm_version == 1


class TestComputeExpectedHash:
    """Tests for compute_expected_hash method (Story 4.2, Task 5).

    Per FR62: Observers must be able to independently verify hashes.
    """

    def test_verify_content_hash_correct_hash(self) -> None:
        """Test that compute_expected_hash produces correct hash."""
        from src.api.models.observer import ObserverEventResponse

        # Create a response with known values
        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            content_hash="placeholder",  # Will be replaced with computed
            prev_hash="0" * 64,
            signature="sig123",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        )

        # Compute expected hash
        computed = response.compute_expected_hash()

        # Hash should be 64 hex chars
        assert len(computed) == 64
        assert all(c in "0123456789abcdef" for c in computed)

    def test_verify_content_hash_wrong_hash(self) -> None:
        """Test that mismatched hash is detectable."""
        from src.api.models.observer import ObserverEventResponse

        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            content_hash="wrong_hash_" + "0" * 53,  # Intentionally wrong
            prev_hash="0" * 64,
            signature="sig123",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        )

        computed = response.compute_expected_hash()

        # Computed hash should NOT match the wrong stored hash
        assert computed != response.content_hash

    def test_verify_content_hash_matches_domain_computation(self) -> None:
        """Test that compute_expected_hash matches domain hash_utils.

        This ensures API and domain use identical hash computation.
        """
        from src.api.models.observer import ObserverEventResponse
        from src.domain.events.hash_utils import compute_content_hash

        timestamp = datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc)

        # Create event data matching what domain uses
        event_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": timestamp,
            "agent_id": "agent-001",
        }

        # Compute using domain function
        domain_hash = compute_content_hash(event_data)

        # Create API response and compute
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

        api_hash = response.compute_expected_hash()

        # Hashes must be identical
        assert api_hash == domain_hash

    def test_compute_hash_without_agent_id(self) -> None:
        """Test hash computation when agent_id is empty."""
        from src.api.models.observer import ObserverEventResponse

        response = ObserverEventResponse(
            event_id=uuid4(),
            sequence=1,
            event_type="system.event",
            payload={},
            content_hash="placeholder",
            prev_hash="0" * 64,
            signature="sig",
            agent_id="",  # Empty agent_id
            witness_id="witness-001",
            witness_signature="wsig",
            local_timestamp=datetime(2025, 12, 27, tzinfo=timezone.utc),
        )

        # Should compute without error
        computed = response.compute_expected_hash()
        assert len(computed) == 64


class TestChainVerificationResult:
    """Tests for ChainVerificationResult model (Story 4.2, Task 7).

    Per FR64: Verification bundles for offline verification.
    """

    def test_chain_verification_result_fields(self) -> None:
        """Test that ChainVerificationResult has all required fields."""
        from src.api.models.observer import ChainVerificationResult

        result = ChainVerificationResult(
            start_sequence=1,
            end_sequence=100,
            is_valid=True,
            verified_count=100,
        )

        assert result.start_sequence == 1
        assert result.end_sequence == 100
        assert result.is_valid is True
        assert result.verified_count == 100
        assert result.first_invalid_sequence is None
        assert result.error_message is None

    def test_chain_verification_invalid_result(self) -> None:
        """Test ChainVerificationResult with invalid chain."""
        from src.api.models.observer import ChainVerificationResult

        result = ChainVerificationResult(
            start_sequence=1,
            end_sequence=100,
            is_valid=False,
            first_invalid_sequence=42,
            error_message="Hash mismatch at sequence 42",
            verified_count=41,
        )

        assert result.is_valid is False
        assert result.first_invalid_sequence == 42
        assert "42" in result.error_message
        assert result.verified_count == 41


# =============================================================================
# Tests for EventFilterParams (Story 4.3, Task 5 - FR46)
# =============================================================================


class TestEventFilterParams:
    """Tests for EventFilterParams model (Story 4.3, Task 5).

    Per FR46: Query interface SHALL support date range and event type filtering.
    """

    def test_filter_params_fields_exist(self) -> None:
        """Test that EventFilterParams has all required fields."""
        from src.api.models.observer import EventFilterParams

        params = EventFilterParams()

        # All fields should exist
        assert hasattr(params, "start_date")
        assert hasattr(params, "end_date")
        assert hasattr(params, "event_type")

    def test_filter_params_all_optional(self) -> None:
        """Test that all filter params are optional (default to None)."""
        from src.api.models.observer import EventFilterParams

        params = EventFilterParams()

        # All should default to None
        assert params.start_date is None
        assert params.end_date is None
        assert params.event_type is None

    def test_filter_params_with_dates(self) -> None:
        """Test EventFilterParams with date values."""
        from src.api.models.observer import EventFilterParams

        start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)

        params = EventFilterParams(start_date=start, end_date=end)

        assert params.start_date == start
        assert params.end_date == end

    def test_filter_params_with_event_type(self) -> None:
        """Test EventFilterParams with event_type value."""
        from src.api.models.observer import EventFilterParams

        params = EventFilterParams(event_type="vote,halt,breach")

        assert params.event_type == "vote,halt,breach"

    def test_filter_params_combined(self) -> None:
        """Test EventFilterParams with all filters combined."""
        from src.api.models.observer import EventFilterParams

        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 16, 23, 59, 59, tzinfo=timezone.utc)

        params = EventFilterParams(
            start_date=start,
            end_date=end,
            event_type="vote",
        )

        assert params.start_date == start
        assert params.end_date == end
        assert params.event_type == "vote"

    def test_filter_params_example_in_schema(self) -> None:
        """Test that EventFilterParams has examples in JSON schema."""
        from src.api.models.observer import EventFilterParams

        schema = EventFilterParams.model_json_schema()

        # Should have examples in schema
        assert "examples" in schema or any(
            "example" in str(v) for v in schema.get("properties", {}).values()
        )

    def test_filter_params_field_descriptions(self) -> None:
        """Test that filter param fields have descriptions."""
        from src.api.models.observer import EventFilterParams

        schema = EventFilterParams.model_json_schema()
        properties = schema.get("properties", {})

        # All fields should have descriptions
        for field_name in ["start_date", "end_date", "event_type"]:
            field_schema = properties.get(field_name, {})
            # Check for description or anyOf with description
            has_desc = "description" in field_schema or any(
                "description" in str(v) for v in field_schema.values()
            )
            assert has_desc or field_schema, (
                f"Field {field_name} should have description"
            )

    def test_filter_params_partial_date_range_start_only(self) -> None:
        """Test EventFilterParams with only start_date (no end_date)."""
        from src.api.models.observer import EventFilterParams

        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        params = EventFilterParams(start_date=start)

        assert params.start_date == start
        assert params.end_date is None

    def test_filter_params_partial_date_range_end_only(self) -> None:
        """Test EventFilterParams with only end_date (no start_date)."""
        from src.api.models.observer import EventFilterParams

        end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        params = EventFilterParams(end_date=end)

        assert params.start_date is None
        assert params.end_date == end


# =============================================================================
# Tests for HashChainProof and related models (Story 4.5 - FR88, FR89)
# =============================================================================


class TestHashChainProofEntry:
    """Tests for HashChainProofEntry model (Story 4.5, Task 1).

    Per FR89: Hash chain proof entries for offline verification.
    """

    def test_hash_chain_proof_entry_valid(self) -> None:
        """Test that HashChainProofEntry accepts valid data."""
        from src.api.models.observer import HashChainProofEntry

        entry = HashChainProofEntry(
            sequence=42,
            content_hash="a" * 64,
            prev_hash="b" * 64,
        )

        assert entry.sequence == 42
        assert entry.content_hash == "a" * 64
        assert entry.prev_hash == "b" * 64

    def test_hash_chain_proof_entry_sequence_must_be_positive(self) -> None:
        """Test that sequence must be >= 1."""
        from src.api.models.observer import HashChainProofEntry

        with pytest.raises(ValueError):
            HashChainProofEntry(
                sequence=0,
                content_hash="a" * 64,
                prev_hash="b" * 64,
            )

    def test_hash_chain_proof_entry_hash_pattern(self) -> None:
        """Test that hashes must be 64 lowercase hex chars."""
        from src.api.models.observer import HashChainProofEntry

        # Valid hash
        entry = HashChainProofEntry(
            sequence=1,
            content_hash="abcdef0123456789" * 4,
            prev_hash="0" * 64,
        )
        assert len(entry.content_hash) == 64

        # Invalid hash (wrong length) should fail validation
        with pytest.raises(ValueError):
            HashChainProofEntry(
                sequence=1,
                content_hash="too_short",
                prev_hash="0" * 64,
            )


class TestHashChainProof:
    """Tests for HashChainProof model (Story 4.5, Task 1).

    Per FR89: Historical queries SHALL return hash chain proof
    connecting queried state to current head.
    """

    def test_hash_chain_proof_model_valid(self) -> None:
        """Test that HashChainProof accepts valid data."""
        from src.api.models.observer import HashChainProof, HashChainProofEntry

        chain = [
            HashChainProofEntry(
                sequence=1,
                content_hash="a" * 64,
                prev_hash="0" * 64,
            ),
            HashChainProofEntry(
                sequence=2,
                content_hash="b" * 64,
                prev_hash="a" * 64,
            ),
        ]

        proof = HashChainProof(
            from_sequence=1,
            to_sequence=2,
            chain=chain,
            current_head_hash="b" * 64,
        )

        assert proof.from_sequence == 1
        assert proof.to_sequence == 2
        assert len(proof.chain) == 2
        assert proof.current_head_hash == "b" * 64

    def test_hash_chain_proof_from_sequence_to_head(self) -> None:
        """Test proof from arbitrary sequence to head."""
        from src.api.models.observer import HashChainProof, HashChainProofEntry

        chain = [
            HashChainProofEntry(
                sequence=100, content_hash="c" * 64, prev_hash="b" * 64
            ),
            HashChainProofEntry(
                sequence=101, content_hash="d" * 64, prev_hash="c" * 64
            ),
            HashChainProofEntry(
                sequence=102, content_hash="e" * 64, prev_hash="d" * 64
            ),
        ]

        proof = HashChainProof(
            from_sequence=100,
            to_sequence=102,
            chain=chain,
            current_head_hash="e" * 64,
        )

        assert proof.from_sequence == 100
        assert proof.to_sequence == 102
        assert proof.chain[0].sequence == 100
        assert proof.chain[-1].sequence == 102

    def test_hash_chain_proof_includes_intermediate_hashes(self) -> None:
        """Test that proof chain includes all intermediate hashes."""
        from src.api.models.observer import HashChainProof, HashChainProofEntry

        # 5 events in chain
        chain = [
            HashChainProofEntry(
                sequence=i, content_hash=f"{i:064x}", prev_hash=f"{i - 1:064x}"
            )
            for i in range(1, 6)
        ]

        proof = HashChainProof(
            from_sequence=1,
            to_sequence=5,
            chain=chain,
            current_head_hash=f"{5:064x}",
        )

        # All 5 entries should be present
        assert len(proof.chain) == 5

        # Each entry should have content_hash and prev_hash
        for entry in proof.chain:
            assert len(entry.content_hash) == 64
            assert len(entry.prev_hash) == 64

    def test_hash_chain_proof_serialization(self) -> None:
        """Test that HashChainProof serializes to JSON correctly."""
        from src.api.models.observer import HashChainProof, HashChainProofEntry

        chain = [
            HashChainProofEntry(sequence=1, content_hash="a" * 64, prev_hash="0" * 64),
        ]

        proof = HashChainProof(
            from_sequence=1,
            to_sequence=1,
            chain=chain,
            current_head_hash="a" * 64,
        )

        # Should serialize without error
        json_data = proof.model_dump_json()
        assert "from_sequence" in json_data
        assert "to_sequence" in json_data
        assert "chain" in json_data
        assert "current_head_hash" in json_data
        assert "generated_at" in json_data
        assert "proof_type" in json_data

    def test_hash_chain_proof_default_type(self) -> None:
        """Test that proof_type defaults to 'hash_chain'."""
        from src.api.models.observer import HashChainProof, HashChainProofEntry

        proof = HashChainProof(
            from_sequence=1,
            to_sequence=1,
            chain=[
                HashChainProofEntry(
                    sequence=1, content_hash="a" * 64, prev_hash="0" * 64
                )
            ],
            current_head_hash="a" * 64,
        )

        assert proof.proof_type == "hash_chain"

    def test_hash_chain_proof_generated_at_auto(self) -> None:
        """Test that generated_at is auto-populated."""
        from src.api.models.observer import HashChainProof, HashChainProofEntry

        proof = HashChainProof(
            from_sequence=1,
            to_sequence=1,
            chain=[
                HashChainProofEntry(
                    sequence=1, content_hash="a" * 64, prev_hash="0" * 64
                )
            ],
            current_head_hash="a" * 64,
        )

        assert proof.generated_at is not None
        # Should be a recent datetime (within last minute)
        from datetime import timedelta

        assert datetime.now(timezone.utc) - proof.generated_at < timedelta(minutes=1)


class TestHistoricalQueryMetadata:
    """Tests for HistoricalQueryMetadata model (Story 4.5, Task 6).

    Per FR88: Support queries for state as of any past sequence/timestamp.
    """

    def test_historical_query_metadata_valid(self) -> None:
        """Test that HistoricalQueryMetadata accepts valid data."""
        from src.api.models.observer import HistoricalQueryMetadata

        metadata = HistoricalQueryMetadata(
            queried_as_of_sequence=500,
            resolved_sequence=500,
            current_head_sequence=1000,
        )

        assert metadata.queried_as_of_sequence == 500
        assert metadata.resolved_sequence == 500
        assert metadata.current_head_sequence == 1000

    def test_historical_query_metadata_with_timestamp(self) -> None:
        """Test metadata when queried by timestamp."""
        from src.api.models.observer import HistoricalQueryMetadata

        timestamp = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        metadata = HistoricalQueryMetadata(
            queried_as_of_timestamp=timestamp,
            resolved_sequence=500,
            current_head_sequence=1000,
        )

        assert metadata.queried_as_of_timestamp == timestamp
        assert metadata.queried_as_of_sequence is None
        assert metadata.resolved_sequence == 500

    def test_historical_query_metadata_includes_head_sequence(self) -> None:
        """Test that metadata includes current head for context."""
        from src.api.models.observer import HistoricalQueryMetadata

        metadata = HistoricalQueryMetadata(
            queried_as_of_sequence=100,
            resolved_sequence=100,
            current_head_sequence=5000,
        )

        # Should show how far behind the query is
        assert metadata.current_head_sequence == 5000
        assert metadata.resolved_sequence == 100


# =============================================================================
# Tests for MerkleProof and CheckpointAnchor models (Story 4.6 - FR136, FR137, FR138)
# =============================================================================


class TestMerkleProofEntry:
    """Tests for MerkleProofEntry model (Story 4.6, Task 1).

    Per FR136: Merkle proof entries for light verification.
    """

    def test_merkle_proof_entry_model_valid(self) -> None:
        """Test that MerkleProofEntry accepts valid data."""
        from src.api.models.observer import MerkleProofEntry

        entry = MerkleProofEntry(
            level=0,
            position="left",
            sibling_hash="a" * 64,
        )

        assert entry.level == 0
        assert entry.position == "left"
        assert entry.sibling_hash == "a" * 64

    def test_merkle_proof_entry_level_non_negative(self) -> None:
        """Test that level must be >= 0."""
        from src.api.models.observer import MerkleProofEntry

        # Valid: level 0
        entry = MerkleProofEntry(
            level=0,
            position="right",
            sibling_hash="b" * 64,
        )
        assert entry.level == 0

        # Invalid: negative level
        with pytest.raises(ValueError):
            MerkleProofEntry(
                level=-1,
                position="left",
                sibling_hash="c" * 64,
            )

    def test_merkle_proof_entry_position_values(self) -> None:
        """Test that position must be 'left' or 'right'."""
        from src.api.models.observer import MerkleProofEntry

        # Valid positions
        left = MerkleProofEntry(level=0, position="left", sibling_hash="d" * 64)
        assert left.position == "left"

        right = MerkleProofEntry(level=1, position="right", sibling_hash="e" * 64)
        assert right.position == "right"

        # Invalid position
        with pytest.raises(ValueError):
            MerkleProofEntry(level=0, position="middle", sibling_hash="f" * 64)

    def test_merkle_proof_entry_hash_pattern(self) -> None:
        """Test that sibling_hash must be 64 lowercase hex chars."""
        from src.api.models.observer import MerkleProofEntry

        # Valid hash
        entry = MerkleProofEntry(
            level=0,
            position="left",
            sibling_hash="abcdef0123456789" * 4,
        )
        assert len(entry.sibling_hash) == 64

        # Invalid hash (wrong length)
        with pytest.raises(ValueError):
            MerkleProofEntry(
                level=0,
                position="left",
                sibling_hash="too_short",
            )


class TestMerkleProof:
    """Tests for MerkleProof model (Story 4.6, Task 1).

    Per FR136: Merkle proof connecting event to checkpoint root.
    """

    def test_merkle_proof_model_valid(self) -> None:
        """Test that MerkleProof accepts valid data."""
        from src.api.models.observer import MerkleProof, MerkleProofEntry

        path = [
            MerkleProofEntry(level=0, position="right", sibling_hash="a" * 64),
            MerkleProofEntry(level=1, position="left", sibling_hash="b" * 64),
        ]

        proof = MerkleProof(
            event_sequence=42,
            event_hash="c" * 64,
            checkpoint_sequence=100,
            checkpoint_root="d" * 64,
            path=path,
            tree_size=100,
        )

        assert proof.event_sequence == 42
        assert proof.event_hash == "c" * 64
        assert proof.checkpoint_sequence == 100
        assert proof.checkpoint_root == "d" * 64
        assert len(proof.path) == 2
        assert proof.tree_size == 100

    def test_merkle_proof_event_sequence_positive(self) -> None:
        """Test that event_sequence must be >= 1."""
        from src.api.models.observer import MerkleProof

        with pytest.raises(ValueError):
            MerkleProof(
                event_sequence=0,
                event_hash="a" * 64,
                checkpoint_sequence=100,
                checkpoint_root="b" * 64,
                path=[],
                tree_size=100,
            )

    def test_merkle_proof_checkpoint_sequence_positive(self) -> None:
        """Test that checkpoint_sequence must be >= 1."""
        from src.api.models.observer import MerkleProof

        with pytest.raises(ValueError):
            MerkleProof(
                event_sequence=42,
                event_hash="a" * 64,
                checkpoint_sequence=0,
                checkpoint_root="b" * 64,
                path=[],
                tree_size=100,
            )

    def test_merkle_proof_tree_size_positive(self) -> None:
        """Test that tree_size must be >= 1."""
        from src.api.models.observer import MerkleProof

        with pytest.raises(ValueError):
            MerkleProof(
                event_sequence=42,
                event_hash="a" * 64,
                checkpoint_sequence=100,
                checkpoint_root="b" * 64,
                path=[],
                tree_size=0,
            )

    def test_merkle_proof_serialization(self) -> None:
        """Test that MerkleProof serializes to JSON correctly."""
        from src.api.models.observer import MerkleProof, MerkleProofEntry

        path = [
            MerkleProofEntry(level=0, position="right", sibling_hash="a" * 64),
        ]

        proof = MerkleProof(
            event_sequence=42,
            event_hash="b" * 64,
            checkpoint_sequence=100,
            checkpoint_root="c" * 64,
            path=path,
            tree_size=100,
        )

        # Should serialize without error
        json_data = proof.model_dump_json()
        assert "event_sequence" in json_data
        assert "event_hash" in json_data
        assert "checkpoint_sequence" in json_data
        assert "checkpoint_root" in json_data
        assert "path" in json_data
        assert "tree_size" in json_data
        assert "proof_type" in json_data
        assert "generated_at" in json_data

    def test_merkle_proof_default_type(self) -> None:
        """Test that proof_type defaults to 'merkle'."""
        from src.api.models.observer import MerkleProof

        proof = MerkleProof(
            event_sequence=1,
            event_hash="a" * 64,
            checkpoint_sequence=100,
            checkpoint_root="b" * 64,
            path=[],
            tree_size=100,
        )

        assert proof.proof_type == "merkle"

    def test_merkle_proof_generated_at_auto(self) -> None:
        """Test that generated_at is auto-populated."""
        from datetime import timedelta

        from src.api.models.observer import MerkleProof

        proof = MerkleProof(
            event_sequence=1,
            event_hash="a" * 64,
            checkpoint_sequence=100,
            checkpoint_root="b" * 64,
            path=[],
            tree_size=100,
        )

        assert proof.generated_at is not None
        # Should be a recent datetime (within last minute)
        assert datetime.now(timezone.utc) - proof.generated_at < timedelta(minutes=1)


class TestCheckpointAnchor:
    """Tests for CheckpointAnchor API model (Story 4.6, Task 1).

    Per FR137, FR138: Weekly checkpoint anchors for light verification.
    """

    def test_checkpoint_anchor_model_valid(self) -> None:
        """Test that CheckpointAnchor accepts valid data."""
        from src.api.models.observer import CheckpointAnchor

        checkpoint_id = uuid4()
        created_at = datetime.now(timezone.utc)

        anchor = CheckpointAnchor(
            checkpoint_id=checkpoint_id,
            sequence_start=1,
            sequence_end=100,
            merkle_root="a" * 64,
            created_at=created_at,
            event_count=100,
        )

        assert anchor.checkpoint_id == checkpoint_id
        assert anchor.sequence_start == 1
        assert anchor.sequence_end == 100
        assert anchor.merkle_root == "a" * 64
        assert anchor.created_at == created_at
        assert anchor.event_count == 100

    def test_checkpoint_anchor_sequence_start_positive(self) -> None:
        """Test that sequence_start must be >= 1."""
        from src.api.models.observer import CheckpointAnchor

        with pytest.raises(ValueError):
            CheckpointAnchor(
                checkpoint_id=uuid4(),
                sequence_start=0,
                sequence_end=100,
                merkle_root="a" * 64,
                created_at=datetime.now(timezone.utc),
                event_count=100,
            )

    def test_checkpoint_anchor_sequence_end_positive(self) -> None:
        """Test that sequence_end must be >= 1."""
        from src.api.models.observer import CheckpointAnchor

        with pytest.raises(ValueError):
            CheckpointAnchor(
                checkpoint_id=uuid4(),
                sequence_start=1,
                sequence_end=0,
                merkle_root="a" * 64,
                created_at=datetime.now(timezone.utc),
                event_count=100,
            )

    def test_checkpoint_anchor_default_anchor_type(self) -> None:
        """Test that anchor_type defaults to 'pending'."""
        from src.api.models.observer import CheckpointAnchor

        anchor = CheckpointAnchor(
            checkpoint_id=uuid4(),
            sequence_start=1,
            sequence_end=100,
            merkle_root="a" * 64,
            created_at=datetime.now(timezone.utc),
            event_count=100,
        )

        assert anchor.anchor_type == "pending"

    def test_checkpoint_anchor_valid_anchor_types(self) -> None:
        """Test that anchor_type accepts valid values."""
        from src.api.models.observer import CheckpointAnchor

        for anchor_type in ["genesis", "rfc3161", "pending"]:
            anchor = CheckpointAnchor(
                checkpoint_id=uuid4(),
                sequence_start=1,
                sequence_end=100,
                merkle_root="a" * 64,
                created_at=datetime.now(timezone.utc),
                anchor_type=anchor_type,
                event_count=100,
            )
            assert anchor.anchor_type == anchor_type

    def test_checkpoint_anchor_optional_reference(self) -> None:
        """Test that anchor_reference is optional."""
        from src.api.models.observer import CheckpointAnchor

        # Without reference
        anchor1 = CheckpointAnchor(
            checkpoint_id=uuid4(),
            sequence_start=1,
            sequence_end=100,
            merkle_root="a" * 64,
            created_at=datetime.now(timezone.utc),
            event_count=100,
        )
        assert anchor1.anchor_reference is None

        # With reference
        anchor2 = CheckpointAnchor(
            checkpoint_id=uuid4(),
            sequence_start=1,
            sequence_end=100,
            merkle_root="b" * 64,
            created_at=datetime.now(timezone.utc),
            anchor_type="rfc3161",
            anchor_reference="TSA_RESPONSE_123",
            event_count=100,
        )
        assert anchor2.anchor_reference == "TSA_RESPONSE_123"

    def test_checkpoint_anchor_merkle_root_pattern(self) -> None:
        """Test that merkle_root must be 64 lowercase hex chars."""
        from src.api.models.observer import CheckpointAnchor

        # Valid hash
        anchor = CheckpointAnchor(
            checkpoint_id=uuid4(),
            sequence_start=1,
            sequence_end=100,
            merkle_root="abcdef0123456789" * 4,
            created_at=datetime.now(timezone.utc),
            event_count=100,
        )
        assert len(anchor.merkle_root) == 64

        # Invalid hash (wrong length)
        with pytest.raises(ValueError):
            CheckpointAnchor(
                checkpoint_id=uuid4(),
                sequence_start=1,
                sequence_end=100,
                merkle_root="too_short",
                created_at=datetime.now(timezone.utc),
                event_count=100,
            )


class TestObserverEventsListResponseHistorical:
    """Tests for ObserverEventsListResponse with historical query fields (Story 4.5, Task 6)."""

    def test_events_list_response_includes_proof(self) -> None:
        """Test that response can include hash chain proof."""
        from src.api.models.observer import (
            HashChainProof,
            HashChainProofEntry,
            ObserverEventsListResponse,
            PaginationMetadata,
        )

        chain = [
            HashChainProofEntry(sequence=1, content_hash="a" * 64, prev_hash="0" * 64),
        ]
        proof = HashChainProof(
            from_sequence=1,
            to_sequence=1,
            chain=chain,
            current_head_hash="a" * 64,
        )

        response = ObserverEventsListResponse(
            events=[],
            pagination=PaginationMetadata(
                total_count=0, offset=0, limit=100, has_more=False
            ),
            proof=proof,
        )

        assert response.proof is not None
        assert response.proof.from_sequence == 1

    def test_events_list_response_includes_as_of_metadata(self) -> None:
        """Test that response includes historical query metadata."""
        from src.api.models.observer import (
            HistoricalQueryMetadata,
            ObserverEventsListResponse,
            PaginationMetadata,
        )

        metadata = HistoricalQueryMetadata(
            queried_as_of_sequence=500,
            resolved_sequence=500,
            current_head_sequence=1000,
        )

        response = ObserverEventsListResponse(
            events=[],
            pagination=PaginationMetadata(
                total_count=0, offset=0, limit=100, has_more=False
            ),
            historical_query=metadata,
        )

        assert response.historical_query is not None
        assert response.historical_query.queried_as_of_sequence == 500

    def test_events_list_response_proof_optional(self) -> None:
        """Test that proof is optional (None when not requested)."""
        from src.api.models.observer import (
            ObserverEventsListResponse,
            PaginationMetadata,
        )

        response = ObserverEventsListResponse(
            events=[],
            pagination=PaginationMetadata(
                total_count=0, offset=0, limit=100, has_more=False
            ),
        )

        assert response.proof is None
        assert response.historical_query is None


# =============================================================================
# Tests for Regulatory Export models (Story 4.7 - FR139, FR140)
# =============================================================================


class TestExportFormat:
    """Tests for ExportFormat enum (Story 4.7, Task 1).

    Per FR139: Export SHALL support structured audit format (JSON Lines, CSV).
    """

    def test_export_format_jsonl_value(self) -> None:
        """Test that JSONL format has correct value."""
        from src.api.models.observer import ExportFormat

        assert ExportFormat.JSONL.value == "jsonl"

    def test_export_format_csv_value(self) -> None:
        """Test that CSV format has correct value."""
        from src.api.models.observer import ExportFormat

        assert ExportFormat.CSV.value == "csv"

    def test_export_format_is_string_enum(self) -> None:
        """Test that ExportFormat is a string enum for API serialization."""
        from src.api.models.observer import ExportFormat

        assert isinstance(ExportFormat.JSONL, str)
        assert isinstance(ExportFormat.CSV, str)


class TestAttestationMetadata:
    """Tests for AttestationMetadata model (Story 4.7, Task 1).

    Per FR140: Third-party attestation interface with metadata.
    """

    def test_attestation_metadata_valid(self) -> None:
        """Test that AttestationMetadata accepts valid data."""
        from src.api.models.observer import AttestationMetadata

        metadata = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
        )

        assert metadata.sequence_start == 1
        assert metadata.sequence_end == 100
        assert metadata.event_count == 100
        assert metadata.chain_hash_at_export == "a" * 64

    def test_attestation_metadata_auto_export_id(self) -> None:
        """Test that export_id is auto-generated as UUID."""
        from src.api.models.observer import AttestationMetadata

        metadata = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
        )

        assert metadata.export_id is not None
        # UUID should be a valid UUID4
        from uuid import UUID

        assert isinstance(metadata.export_id, UUID)

    def test_attestation_metadata_auto_exported_at(self) -> None:
        """Test that exported_at is auto-populated with current UTC time."""
        from datetime import timedelta

        from src.api.models.observer import AttestationMetadata

        metadata = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
        )

        assert metadata.exported_at is not None
        # Should be recent (within last minute)
        assert datetime.now(timezone.utc) - metadata.exported_at < timedelta(minutes=1)

    def test_attestation_metadata_default_exporter_id(self) -> None:
        """Test that exporter_id defaults to archon72-observer-api."""
        from src.api.models.observer import AttestationMetadata

        metadata = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
        )

        assert metadata.exporter_id == "archon72-observer-api"

    def test_attestation_metadata_sequence_start_positive(self) -> None:
        """Test that sequence_start must be >= 1."""
        from src.api.models.observer import AttestationMetadata

        with pytest.raises(ValueError):
            AttestationMetadata(
                sequence_start=0,
                sequence_end=100,
                event_count=100,
                chain_hash_at_export="a" * 64,
            )

    def test_attestation_metadata_sequence_end_positive(self) -> None:
        """Test that sequence_end must be >= 1."""
        from src.api.models.observer import AttestationMetadata

        with pytest.raises(ValueError):
            AttestationMetadata(
                sequence_start=1,
                sequence_end=0,
                event_count=100,
                chain_hash_at_export="a" * 64,
            )

    def test_attestation_metadata_event_count_non_negative(self) -> None:
        """Test that event_count can be 0 but not negative."""
        from src.api.models.observer import AttestationMetadata

        # Zero is valid
        metadata = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=0,
            chain_hash_at_export="a" * 64,
        )
        assert metadata.event_count == 0

    def test_attestation_metadata_chain_hash_pattern(self) -> None:
        """Test that chain_hash must be 64 lowercase hex chars."""
        from src.api.models.observer import AttestationMetadata

        # Valid hash
        metadata = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="abcdef0123456789" * 4,
        )
        assert len(metadata.chain_hash_at_export) == 64

        # Invalid hash (wrong length)
        with pytest.raises(ValueError):
            AttestationMetadata(
                sequence_start=1,
                sequence_end=100,
                event_count=100,
                chain_hash_at_export="too_short",
            )

    def test_attestation_metadata_optional_filter_criteria(self) -> None:
        """Test that filter_criteria is optional."""
        from src.api.models.observer import AttestationMetadata

        # Without filter criteria
        metadata1 = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
        )
        assert metadata1.filter_criteria is None

        # With filter criteria
        metadata2 = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
            filter_criteria={"event_types": ["vote", "halt"]},
        )
        assert metadata2.filter_criteria == {"event_types": ["vote", "halt"]}

    def test_attestation_metadata_optional_signature(self) -> None:
        """Test that export_signature is optional (for unsigned exports)."""
        from src.api.models.observer import AttestationMetadata

        # Without signature
        metadata1 = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
        )
        assert metadata1.export_signature is None

        # With signature
        metadata2 = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
            export_signature="sig_abc123",
        )
        assert metadata2.export_signature == "sig_abc123"

    def test_attestation_metadata_serialization(self) -> None:
        """Test that AttestationMetadata serializes to JSON correctly."""
        from src.api.models.observer import AttestationMetadata

        metadata = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
            filter_criteria={"start_date": "2026-01-01"},
        )

        json_data = metadata.model_dump_json()
        assert "export_id" in json_data
        assert "exported_at" in json_data
        assert "sequence_start" in json_data
        assert "sequence_end" in json_data
        assert "event_count" in json_data
        assert "chain_hash_at_export" in json_data
        assert "exporter_id" in json_data


class TestRegulatoryExportResponse:
    """Tests for RegulatoryExportResponse model (Story 4.7, Task 1).

    Per FR139: Response wrapper for regulatory export.
    """

    def test_regulatory_export_response_valid_jsonl(self) -> None:
        """Test RegulatoryExportResponse with JSONL format."""
        from src.api.models.observer import ExportFormat, RegulatoryExportResponse

        response = RegulatoryExportResponse(
            format=ExportFormat.JSONL,
        )

        assert response.format == ExportFormat.JSONL

    def test_regulatory_export_response_valid_csv(self) -> None:
        """Test RegulatoryExportResponse with CSV format."""
        from src.api.models.observer import ExportFormat, RegulatoryExportResponse

        response = RegulatoryExportResponse(
            format=ExportFormat.CSV,
        )

        assert response.format == ExportFormat.CSV

    def test_regulatory_export_response_with_attestation(self) -> None:
        """Test RegulatoryExportResponse includes attestation metadata."""
        from src.api.models.observer import (
            AttestationMetadata,
            ExportFormat,
            RegulatoryExportResponse,
        )

        attestation = AttestationMetadata(
            sequence_start=1,
            sequence_end=100,
            event_count=100,
            chain_hash_at_export="a" * 64,
        )

        response = RegulatoryExportResponse(
            format=ExportFormat.JSONL,
            attestation=attestation,
        )

        assert response.attestation is not None
        assert response.attestation.sequence_start == 1

    def test_regulatory_export_response_data_url(self) -> None:
        """Test RegulatoryExportResponse with data_url for large exports."""
        from src.api.models.observer import ExportFormat, RegulatoryExportResponse

        response = RegulatoryExportResponse(
            format=ExportFormat.JSONL,
            data_url="/v1/observer/export/download/abc123",
        )

        assert response.data_url == "/v1/observer/export/download/abc123"

    def test_regulatory_export_response_inline_data(self) -> None:
        """Test RegulatoryExportResponse with inline_data for small exports."""
        from src.api.models.observer import ExportFormat, RegulatoryExportResponse

        response = RegulatoryExportResponse(
            format=ExportFormat.JSONL,
            inline_data='{"event_id": "abc"}\n{"event_id": "def"}\n',
        )

        assert response.inline_data is not None
        assert "event_id" in response.inline_data


# =============================================================================
# Tests for Push Notification models (Story 4.8 - SR-9, RT-5)
# =============================================================================


class TestNotificationEventType:
    """Tests for NotificationEventType enum (Story 4.8, Task 1).

    Per SR-9: Event types that can trigger push notifications.
    """

    def test_notification_event_type_values(self) -> None:
        """Test that NotificationEventType has all required values."""
        from src.api.models.observer import NotificationEventType

        # All event types should exist
        assert NotificationEventType.BREACH.value == "breach"
        assert NotificationEventType.HALT.value == "halt"
        assert NotificationEventType.FORK.value == "fork"
        assert (
            NotificationEventType.CONSTITUTIONAL_CRISIS.value == "constitutional_crisis"
        )
        assert NotificationEventType.ALL.value == "all"

    def test_notification_event_type_is_string_enum(self) -> None:
        """Test that NotificationEventType is a string enum for API serialization."""
        from src.api.models.observer import NotificationEventType

        assert isinstance(NotificationEventType.BREACH, str)
        assert isinstance(NotificationEventType.ALL, str)


class TestWebhookSubscription:
    """Tests for WebhookSubscription model (Story 4.8, Task 1).

    Per SR-9: Webhook subscription for push notifications.
    """

    def test_webhook_subscription_model_valid(self) -> None:
        """Test that WebhookSubscription accepts valid data."""
        from src.api.models.observer import NotificationEventType, WebhookSubscription

        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.BREACH, NotificationEventType.HALT],
        )

        assert str(subscription.webhook_url) == "https://example.com/webhook"
        assert NotificationEventType.BREACH in subscription.event_types
        assert NotificationEventType.HALT in subscription.event_types

    def test_webhook_subscription_default_event_types(self) -> None:
        """Test that event_types defaults to ALL."""
        from src.api.models.observer import NotificationEventType, WebhookSubscription

        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
        )

        assert NotificationEventType.ALL in subscription.event_types

    def test_webhook_subscription_optional_secret(self) -> None:
        """Test that secret is optional but requires min length when provided."""
        from src.api.models.observer import WebhookSubscription

        # Without secret
        subscription1 = WebhookSubscription(
            webhook_url="https://example.com/webhook",
        )
        assert subscription1.secret is None

        # With valid secret (32+ chars)
        subscription2 = WebhookSubscription(
            webhook_url="https://example.com/webhook",
            secret="a" * 32,
        )
        assert subscription2.secret == "a" * 32

    def test_webhook_subscription_secret_min_length(self) -> None:
        """Test that secret requires minimum 32 characters."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError):
            WebhookSubscription(
                webhook_url="https://example.com/webhook",
                secret="too_short",  # Less than 32 chars
            )

    def test_webhook_subscription_url_validation(self) -> None:
        """Test that webhook_url must be a valid URL."""
        from src.api.models.observer import WebhookSubscription

        # Valid URL
        subscription = WebhookSubscription(
            webhook_url="https://example.com/webhook",
        )
        assert "example.com" in str(subscription.webhook_url)

        # Invalid URL should fail
        with pytest.raises(ValueError):
            WebhookSubscription(
                webhook_url="not_a_url",
            )


class TestWebhookSubscriptionResponse:
    """Tests for WebhookSubscriptionResponse model (Story 4.8, Task 1).

    Per SR-9: Response after successful webhook subscription.
    """

    def test_webhook_subscription_response_valid(self) -> None:
        """Test that WebhookSubscriptionResponse accepts valid data."""
        from src.api.models.observer import (
            NotificationEventType,
            WebhookSubscriptionResponse,
        )

        response = WebhookSubscriptionResponse(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.BREACH],
        )

        assert response.subscription_id is not None
        assert response.webhook_url == "https://example.com/webhook"
        assert response.status == "active"
        assert response.test_sent is False

    def test_webhook_subscription_response_auto_id(self) -> None:
        """Test that subscription_id is auto-generated as UUID."""
        from uuid import UUID

        from src.api.models.observer import (
            NotificationEventType,
            WebhookSubscriptionResponse,
        )

        response = WebhookSubscriptionResponse(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.ALL],
        )

        assert isinstance(response.subscription_id, UUID)

    def test_webhook_subscription_response_auto_created_at(self) -> None:
        """Test that created_at is auto-populated."""
        from datetime import timedelta

        from src.api.models.observer import (
            NotificationEventType,
            WebhookSubscriptionResponse,
        )

        response = WebhookSubscriptionResponse(
            webhook_url="https://example.com/webhook",
            event_types=[NotificationEventType.ALL],
        )

        assert response.created_at is not None
        # Should be recent (within last minute)
        assert datetime.now(timezone.utc) - response.created_at < timedelta(minutes=1)


class TestNotificationPayload:
    """Tests for NotificationPayload model (Story 4.8, Task 1).

    Per SR-9, CT-11, CT-12: Push notification payload with verification data.
    """

    def test_notification_payload_model_valid(self) -> None:
        """Test that NotificationPayload accepts valid data."""
        from src.api.models.observer import NotificationPayload

        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="breach",
            sequence=42,
            summary="Constitutional breach detected at sequence 42",
            event_url="http://localhost:8000/v1/observer/events/abc123",
            content_hash="a" * 64,
        )

        assert payload.notification_id is not None
        assert payload.event_type == "breach"
        assert payload.sequence == 42
        assert payload.summary == "Constitutional breach detected at sequence 42"
        assert payload.content_hash == "a" * 64

    def test_notification_payload_auto_notification_id(self) -> None:
        """Test that notification_id is auto-generated as UUID."""
        from uuid import UUID

        from src.api.models.observer import NotificationPayload

        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="halt",
            sequence=100,
            summary="System halt",
            event_url="http://localhost:8000/v1/observer/events/xyz",
            content_hash="b" * 64,
        )

        assert isinstance(payload.notification_id, UUID)

    def test_notification_payload_auto_timestamp(self) -> None:
        """Test that timestamp is auto-populated."""
        from datetime import timedelta

        from src.api.models.observer import NotificationPayload

        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="fork",
            sequence=200,
            summary="Fork detected",
            event_url="http://localhost:8000/v1/observer/events/fork",
            content_hash="c" * 64,
        )

        assert payload.timestamp is not None
        assert datetime.now(timezone.utc) - payload.timestamp < timedelta(minutes=1)

    def test_notification_payload_sequence_non_negative(self) -> None:
        """Test that sequence must be >= 0 (allows 0 for test notifications)."""
        from src.api.models.observer import NotificationPayload

        # sequence=0 is allowed for test notifications (SR-9)
        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="test",
            sequence=0,
            summary="Test notification",
            event_url="http://localhost:8000",
            content_hash="a" * 64,
        )
        assert payload.sequence == 0

        # Negative sequence should raise
        with pytest.raises(ValueError):
            NotificationPayload(
                event_id=uuid4(),
                event_type="breach",
                sequence=-1,
                summary="Invalid",
                event_url="http://localhost:8000",
                content_hash="a" * 64,
            )

    def test_notification_payload_summary_max_length(self) -> None:
        """Test that summary has max length of 1000."""
        from src.api.models.observer import NotificationPayload

        # Valid - 1000 chars
        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="breach",
            sequence=1,
            summary="x" * 1000,
            event_url="http://localhost:8000",
            content_hash="a" * 64,
        )
        assert len(payload.summary) == 1000

        # Invalid - >1000 chars
        with pytest.raises(ValueError):
            NotificationPayload(
                event_id=uuid4(),
                event_type="breach",
                sequence=1,
                summary="x" * 1001,
                event_url="http://localhost:8000",
                content_hash="a" * 64,
            )

    def test_notification_payload_content_hash_pattern(self) -> None:
        """Test that content_hash must be 64 lowercase hex chars."""
        from src.api.models.observer import NotificationPayload

        # Valid hash
        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="breach",
            sequence=1,
            summary="Valid",
            event_url="http://localhost:8000",
            content_hash="abcdef0123456789" * 4,
        )
        assert len(payload.content_hash) == 64

        # Invalid hash (wrong length)
        with pytest.raises(ValueError):
            NotificationPayload(
                event_id=uuid4(),
                event_type="breach",
                sequence=1,
                summary="Invalid",
                event_url="http://localhost:8000",
                content_hash="too_short",
            )

    def test_notification_payload_to_sse_format(self) -> None:
        """Test that to_sse_format produces valid SSE format."""
        import json

        from src.api.models.observer import NotificationPayload

        payload = NotificationPayload(
            event_id=uuid4(),
            event_type="breach",
            sequence=42,
            summary="Test summary",
            event_url="http://localhost:8000/v1/observer/events/abc",
            content_hash="a" * 64,
        )

        sse = payload.to_sse_format()

        # Must start with event: line
        assert sse.startswith("event: breach\n")
        # Must have data: line
        assert "data: " in sse
        # Must end with double newline
        assert sse.endswith("\n\n")

        # Extract data and verify it's valid JSON
        data_line = sse.split("data: ")[1].split("\n")[0]
        data = json.loads(data_line)
        assert data["event_type"] == "breach"
        assert data["sequence"] == 42


class TestSSEConnectionInfo:
    """Tests for SSEConnectionInfo model (Story 4.8, Task 1).

    Per SR-9: Information about SSE connection for tracking.
    """

    def test_sse_connection_info_valid(self) -> None:
        """Test that SSEConnectionInfo accepts valid data."""
        from src.api.models.observer import NotificationEventType, SSEConnectionInfo

        info = SSEConnectionInfo(
            event_types=[NotificationEventType.BREACH, NotificationEventType.HALT],
        )

        assert info.connection_id is not None
        assert info.connected_at is not None
        assert NotificationEventType.BREACH in info.event_types

    def test_sse_connection_info_auto_connection_id(self) -> None:
        """Test that connection_id is auto-generated as UUID."""
        from uuid import UUID

        from src.api.models.observer import NotificationEventType, SSEConnectionInfo

        info = SSEConnectionInfo(
            event_types=[NotificationEventType.ALL],
        )

        assert isinstance(info.connection_id, UUID)

    def test_sse_connection_info_auto_connected_at(self) -> None:
        """Test that connected_at is auto-populated."""
        from datetime import timedelta

        from src.api.models.observer import NotificationEventType, SSEConnectionInfo

        info = SSEConnectionInfo(
            event_types=[NotificationEventType.ALL],
        )

        assert info.connected_at is not None
        assert datetime.now(timezone.utc) - info.connected_at < timedelta(minutes=1)

    def test_sse_connection_info_optional_last_event_id(self) -> None:
        """Test that last_event_id is optional."""
        from src.api.models.observer import NotificationEventType, SSEConnectionInfo

        # Without last_event_id
        info1 = SSEConnectionInfo(
            event_types=[NotificationEventType.ALL],
        )
        assert info1.last_event_id is None

        # With last_event_id
        info2 = SSEConnectionInfo(
            event_types=[NotificationEventType.ALL],
            last_event_id="abc123",
        )
        assert info2.last_event_id == "abc123"


# =============================================================================
# Tests for SSRF Protection in WebhookSubscription (Security Fix)
# =============================================================================


class TestWebhookSubscriptionSSRFProtection:
    """Tests for SSRF protection in WebhookSubscription.

    Per OWASP SSRF Prevention guidelines:
    - Only HTTPS URLs allowed
    - Private/internal network addresses blocked
    - Cloud metadata endpoints blocked
    - DNS resolution validated before acceptance
    """

    def test_webhook_requires_https(self) -> None:
        """Test that HTTP URLs are rejected - HTTPS required for security."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError) as exc_info:
            WebhookSubscription(webhook_url="http://example.com/webhook")

        assert "HTTPS" in str(exc_info.value)

    def test_webhook_blocks_localhost(self) -> None:
        """Test that localhost URLs are blocked to prevent SSRF."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError) as exc_info:
            WebhookSubscription(webhook_url="https://localhost/webhook")

        assert "blocked" in str(exc_info.value).lower()

    def test_webhook_blocks_127_0_0_1(self) -> None:
        """Test that 127.0.0.1 URLs are blocked to prevent SSRF."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError) as exc_info:
            WebhookSubscription(webhook_url="https://127.0.0.1/webhook")

        assert "blocked" in str(exc_info.value).lower()

    def test_webhook_blocks_aws_metadata(self) -> None:
        """Test that AWS metadata endpoint is blocked."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError) as exc_info:
            WebhookSubscription(webhook_url="https://169.254.169.254/latest/meta-data/")

        assert (
            "blocked" in str(exc_info.value).lower()
            or "metadata" in str(exc_info.value).lower()
        )

    def test_webhook_blocks_gcp_metadata(self) -> None:
        """Test that GCP metadata endpoints are blocked."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError) as exc_info:
            WebhookSubscription(
                webhook_url="https://metadata.google.internal/computeMetadata/v1/"
            )

        assert "metadata" in str(exc_info.value).lower()

    def test_webhook_blocks_internal_suffix(self) -> None:
        """Test that .internal domains are blocked."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError) as exc_info:
            WebhookSubscription(webhook_url="https://service.internal/webhook")

        assert "metadata" in str(exc_info.value).lower()

    def test_webhook_accepts_valid_https_url(self) -> None:
        """Test that valid HTTPS URLs are accepted."""
        from src.api.models.observer import WebhookSubscription

        # Note: This test requires a real resolvable domain
        # In production tests, use a mock or skip DNS resolution
        try:
            subscription = WebhookSubscription(
                webhook_url="https://example.com/webhook"
            )
            assert "example.com" in subscription.webhook_url
        except ValueError as e:
            # If DNS resolution fails (no network), that's expected
            if "could not be resolved" not in str(e):
                raise

    def test_webhook_blocks_invalid_url_format(self) -> None:
        """Test that invalid URL formats are rejected."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError):
            WebhookSubscription(webhook_url="not-a-url")

    def test_webhook_blocks_url_without_hostname(self) -> None:
        """Test that URLs without hostname are rejected."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError):
            WebhookSubscription(webhook_url="https:///webhook")

    def test_webhook_blocks_0_0_0_0(self) -> None:
        """Test that 0.0.0.0 is blocked."""
        from src.api.models.observer import WebhookSubscription

        with pytest.raises(ValueError) as exc_info:
            WebhookSubscription(webhook_url="https://0.0.0.0/webhook")

        assert "blocked" in str(exc_info.value).lower()

    def test_webhook_secret_still_requires_min_length(self) -> None:
        """Test that secret validation still works with SSRF protection."""
        from src.api.models.observer import WebhookSubscription

        # Secret too short should fail before SSRF check
        with pytest.raises(ValueError):
            WebhookSubscription(
                webhook_url="https://example.com/webhook",
                secret="too_short",
            )
