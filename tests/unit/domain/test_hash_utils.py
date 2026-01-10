"""Unit tests for hash utilities (FR2, FR82-FR85).

Tests for canonical JSON serialization, content hash computation,
and hash chain linking logic.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestCanonicalJson:
    """Tests for canonical_json() function (AC6)."""

    def test_canonical_json_sorts_keys_alphabetically(self) -> None:
        """Keys should be sorted alphabetically."""
        from src.domain.events.hash_utils import canonical_json

        data = {"zebra": 1, "apple": 2, "mango": 3}
        result = canonical_json(data)
        assert result == '{"apple":2,"mango":3,"zebra":1}'

    def test_canonical_json_no_whitespace(self) -> None:
        """Output should have no whitespace between elements."""
        from src.domain.events.hash_utils import canonical_json

        data = {"key": "value", "number": 42}
        result = canonical_json(data)
        assert " " not in result
        assert "\n" not in result
        assert "\t" not in result

    def test_canonical_json_recursive_sorting(self) -> None:
        """Nested objects should have sorted keys."""
        from src.domain.events.hash_utils import canonical_json

        data = {"outer": {"zebra": 1, "apple": 2}, "inner": {"beta": 3, "alpha": 4}}
        result = canonical_json(data)
        assert result == '{"inner":{"alpha":4,"beta":3},"outer":{"apple":2,"zebra":1}}'

    def test_canonical_json_handles_arrays(self) -> None:
        """Arrays should preserve order (not sorted)."""
        from src.domain.events.hash_utils import canonical_json

        data = {"items": [3, 1, 2]}
        result = canonical_json(data)
        assert result == '{"items":[3,1,2]}'

    def test_canonical_json_handles_nested_arrays_with_objects(self) -> None:
        """Arrays of objects should sort keys within each object."""
        from src.domain.events.hash_utils import canonical_json

        data = {"items": [{"z": 1, "a": 2}, {"b": 3, "a": 4}]}
        result = canonical_json(data)
        assert result == '{"items":[{"a":2,"z":1},{"a":4,"b":3}]}'

    def test_canonical_json_handles_all_types(self) -> None:
        """Should handle string, number, boolean, null, array, object."""
        from src.domain.events.hash_utils import canonical_json

        data = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "bool_true": True,
            "bool_false": False,
            "null_val": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }
        result = canonical_json(data)
        # Keys should be sorted alphabetically
        assert result.startswith('{"array":[1,2,3],"bool_false":false,"bool_true":true,')
        assert '"null_val":null' in result
        assert '"string":"hello"' in result

    def test_canonical_json_handles_unicode(self) -> None:
        """Should handle unicode characters without escaping to ASCII."""
        from src.domain.events.hash_utils import canonical_json

        data = {"message": "Hello, 世界! 🌍"}
        result = canonical_json(data)
        assert "世界" in result
        assert "🌍" in result

    def test_canonical_json_handles_special_characters(self) -> None:
        """Should properly escape special characters in strings."""
        from src.domain.events.hash_utils import canonical_json

        data = {"text": 'quote: "hello"\nnewline\ttab'}
        result = canonical_json(data)
        assert '\\"' in result  # Escaped quote
        assert "\\n" in result  # Escaped newline
        assert "\\t" in result  # Escaped tab

    def test_canonical_json_empty_object(self) -> None:
        """Should handle empty objects."""
        from src.domain.events.hash_utils import canonical_json

        result = canonical_json({})
        assert result == "{}"

    def test_canonical_json_empty_array(self) -> None:
        """Should handle empty arrays."""
        from src.domain.events.hash_utils import canonical_json

        result = canonical_json({"items": []})
        assert result == '{"items":[]}'

    def test_canonical_json_deterministic(self) -> None:
        """Same input should always produce same output."""
        from src.domain.events.hash_utils import canonical_json

        data = {"b": 2, "a": 1, "c": {"z": 26, "y": 25}}
        result1 = canonical_json(data)
        result2 = canonical_json(data)
        result3 = canonical_json(data)
        assert result1 == result2 == result3


class TestComputeContentHash:
    """Tests for compute_content_hash() function (AC1)."""

    def test_compute_content_hash_returns_sha256_hex(self) -> None:
        """Should return lowercase hexadecimal SHA-256 hash."""
        from src.domain.events.hash_utils import compute_content_hash

        event_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        }
        result = compute_content_hash(event_data)

        # Should be 64 character hex string (256 bits / 4 bits per hex digit)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_content_hash_deterministic(self) -> None:
        """Same event data should always produce same hash."""
        from src.domain.events.hash_utils import compute_content_hash

        event_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        }
        hash1 = compute_content_hash(event_data)
        hash2 = compute_content_hash(event_data)
        hash3 = compute_content_hash(event_data)
        assert hash1 == hash2 == hash3

    def test_compute_content_hash_different_for_different_data(self) -> None:
        """Different event data should produce different hashes."""
        from src.domain.events.hash_utils import compute_content_hash

        base_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        }

        modified_data = base_data.copy()
        modified_data["event_type"] = "different.event"

        hash1 = compute_content_hash(base_data)
        hash2 = compute_content_hash(modified_data)
        assert hash1 != hash2

    def test_compute_content_hash_includes_agent_id_when_present(self) -> None:
        """agent_id should affect hash when present."""
        from src.domain.events.hash_utils import compute_content_hash

        base_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        }

        with_agent = base_data.copy()
        with_agent["agent_id"] = "agent-42"

        hash_without = compute_content_hash(base_data)
        hash_with = compute_content_hash(with_agent)
        assert hash_without != hash_with

    def test_compute_content_hash_excludes_prev_hash(self) -> None:
        """prev_hash should NOT affect content_hash (circular dependency)."""
        from src.domain.events.hash_utils import compute_content_hash

        base_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        }

        with_prev_hash = base_data.copy()
        with_prev_hash["prev_hash"] = "abc123"

        hash1 = compute_content_hash(base_data)
        hash2 = compute_content_hash(with_prev_hash)
        assert hash1 == hash2  # Same hash because prev_hash is excluded

    def test_compute_content_hash_excludes_sequence(self) -> None:
        """sequence should NOT affect content_hash (DB-assigned)."""
        from src.domain.events.hash_utils import compute_content_hash

        base_data = {
            "event_type": "test.event",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        }

        with_sequence = base_data.copy()
        with_sequence["sequence"] = 42

        hash1 = compute_content_hash(base_data)
        hash2 = compute_content_hash(with_sequence)
        assert hash1 == hash2  # Same hash because sequence is excluded

    def test_compute_content_hash_handles_empty_payload(self) -> None:
        """Should handle empty payload dict."""
        from src.domain.events.hash_utils import compute_content_hash

        event_data = {
            "event_type": "test.event",
            "payload": {},
            "signature": "sig123",
            "witness_id": "witness-001",
            "witness_signature": "wsig123",
            "local_timestamp": datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        }
        result = compute_content_hash(event_data)
        assert len(result) == 64


class TestGenesisHash:
    """Tests for GENESIS_HASH constant (AC2)."""

    def test_genesis_hash_is_64_zeros(self) -> None:
        """Genesis hash should be 64 zeros."""
        from src.domain.events.hash_utils import GENESIS_HASH

        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64
        assert all(c == "0" for c in GENESIS_HASH)

    def test_genesis_hash_is_valid_hex(self) -> None:
        """Genesis hash should be valid hexadecimal."""
        from src.domain.events.hash_utils import GENESIS_HASH

        # Should not raise
        int(GENESIS_HASH, 16)


class TestGetPrevHash:
    """Tests for get_prev_hash() function (AC2)."""

    def test_get_prev_hash_returns_genesis_for_first_event(self) -> None:
        """First event (sequence 1) should use genesis hash."""
        from src.domain.events.hash_utils import GENESIS_HASH, get_prev_hash

        result = get_prev_hash(sequence=1, previous_content_hash=None)
        assert result == GENESIS_HASH

    def test_get_prev_hash_returns_previous_hash_for_subsequent_events(self) -> None:
        """Subsequent events should use previous event's content_hash."""
        from src.domain.events.hash_utils import get_prev_hash

        prev_hash = "abc123def456" * 5 + "abcd"  # 64 chars
        result = get_prev_hash(sequence=2, previous_content_hash=prev_hash)
        assert result == prev_hash

    def test_get_prev_hash_raises_for_missing_previous_hash(self) -> None:
        """Should raise error if sequence > 1 but no previous hash provided."""
        from src.domain.events.hash_utils import get_prev_hash

        with pytest.raises(ValueError, match="previous_content_hash required"):
            get_prev_hash(sequence=2, previous_content_hash=None)

    def test_get_prev_hash_raises_for_invalid_sequence(self) -> None:
        """Should raise error for sequence < 1."""
        from src.domain.events.hash_utils import get_prev_hash

        with pytest.raises(ValueError, match="sequence must be >= 1"):
            get_prev_hash(sequence=0, previous_content_hash=None)

        with pytest.raises(ValueError, match="sequence must be >= 1"):
            get_prev_hash(sequence=-1, previous_content_hash=None)


class TestHashAlgorithmVersion:
    """Tests for hash algorithm version constant (AC3)."""

    def test_hash_alg_version_is_1(self) -> None:
        """SHA-256 is version 1."""
        from src.domain.events.hash_utils import HASH_ALG_VERSION

        assert HASH_ALG_VERSION == 1

    def test_hash_alg_name_is_sha256(self) -> None:
        """Algorithm name constant should be SHA-256."""
        from src.domain.events.hash_utils import HASH_ALG_NAME

        assert HASH_ALG_NAME == "SHA-256"


class TestEventCreateWithHash:
    """Tests for Event.create_with_hash() factory method (AC1, AC2, AC3)."""

    def test_create_first_event_uses_genesis_hash(self) -> None:
        """First event (sequence 1) should use genesis hash for prev_hash."""
        from src.domain.events.event import Event
        from src.domain.events.hash_utils import GENESIS_HASH

        event = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert event.prev_hash == GENESIS_HASH
        assert event.sequence == 1

    def test_create_subsequent_event_uses_previous_hash(self) -> None:
        """Subsequent events should use previous event's content_hash."""
        from src.domain.events.event import Event

        prev_content_hash = "a" * 64

        event = Event.create_with_hash(
            sequence=2,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
            previous_content_hash=prev_content_hash,
        )

        assert event.prev_hash == prev_content_hash
        assert event.sequence == 2

    def test_create_computes_valid_content_hash(self) -> None:
        """Factory should compute a valid SHA-256 content hash."""
        from src.domain.events.event import Event

        event = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        )

        # Content hash should be 64-character lowercase hex
        assert len(event.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in event.content_hash)

    def test_create_sets_hash_alg_version_to_1(self) -> None:
        """Factory should set hash_alg_version to 1 (SHA-256)."""
        from src.domain.events.event import Event

        event = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert event.hash_alg_version == 1

    def test_create_raises_for_missing_previous_hash(self) -> None:
        """Factory should raise ValueError for sequence > 1 without previous_content_hash."""
        from src.domain.events.event import Event

        with pytest.raises(ValueError, match="previous_content_hash required"):
            Event.create_with_hash(
                sequence=2,
                event_type="test.event",
                payload={"key": "value"},
                signature="sig123",
                witness_id="witness-001",
                witness_signature="wsig123",
                local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
                # previous_content_hash not provided!
            )

    def test_create_deterministic_content_hash(self) -> None:
        """Same inputs should produce same content_hash."""
        from uuid import UUID

        from src.domain.events.event import Event

        fixed_id = UUID("12345678-1234-5678-1234-567812345678")
        timestamp = datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc)

        event1 = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=timestamp,
            event_id=fixed_id,
        )

        event2 = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=timestamp,
            event_id=fixed_id,
        )

        assert event1.content_hash == event2.content_hash

    def test_create_includes_agent_id_in_hash(self) -> None:
        """agent_id should affect the content_hash when present."""
        from src.domain.events.event import Event

        timestamp = datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc)

        event_without_agent = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=timestamp,
        )

        event_with_agent = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=timestamp,
            agent_id="agent-42",
        )

        assert event_without_agent.content_hash != event_with_agent.content_hash

    def test_create_generates_uuid_if_not_provided(self) -> None:
        """Factory should generate a UUID if event_id is not provided."""
        from uuid import UUID

        from src.domain.events.event import Event

        event = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert isinstance(event.event_id, UUID)

    def test_create_uses_provided_uuid(self) -> None:
        """Factory should use the provided event_id if given."""
        from uuid import UUID

        from src.domain.events.event import Event

        fixed_id = UUID("12345678-1234-5678-1234-567812345678")

        event = Event.create_with_hash(
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc),
            event_id=fixed_id,
        )

        assert event.event_id == fixed_id
