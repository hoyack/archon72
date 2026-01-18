"""Unit tests for EventToObserverAdapter (Story 4.1, Task 4; Story 4.2, Task 2).

Tests for adapter that transforms domain Event to API response.

Constitutional Constraints:
- FR44: ALL event data must be exposed to observers
- FR45: Raw events with hashes for verification
- No fields hidden or transformed
"""

from datetime import datetime, timezone
from uuid import uuid4


class TestEventToObserverAdapter:
    """Tests for EventToObserverAdapter class."""

    def _create_sample_event(
        self,
        *,
        event_id=None,
        sequence: int = 1,
        event_type: str = "test.event",
        payload: dict = None,
        authority_timestamp: datetime = None,
    ):
        """Create a sample Event for testing."""
        from src.domain.events import Event

        return Event(
            event_id=event_id or uuid4(),
            sequence=sequence,
            event_type=event_type,
            payload=payload or {"key": "value"},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            hash_alg_version=1,
            sig_alg_version=1,
            signing_key_id="key-001",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
            authority_timestamp=authority_timestamp,
        )

    def test_adapter_exists(self) -> None:
        """Test that EventToObserverAdapter exists."""
        from src.api.adapters.observer import EventToObserverAdapter

        assert EventToObserverAdapter is not None

    def test_adapt_event_to_response(self) -> None:
        """Test converting domain Event to ObserverEventResponse."""
        from src.api.adapters.observer import EventToObserverAdapter
        from src.api.models.observer import ObserverEventResponse

        event = self._create_sample_event()

        response = EventToObserverAdapter.to_response(event)

        assert isinstance(response, ObserverEventResponse)
        assert response.event_id == event.event_id
        assert response.sequence == event.sequence
        assert response.event_type == event.event_type
        assert response.agent_id == event.agent_id
        assert response.witness_id == event.witness_id

    def test_adapter_includes_all_hashes(self) -> None:
        """Test that adapter exposes all hash chain data.

        Per FR44: ALL event data must be exposed for verification.
        """
        from src.api.adapters.observer import EventToObserverAdapter

        event = self._create_sample_event()

        response = EventToObserverAdapter.to_response(event)

        # All hash-related fields must be present
        assert response.content_hash == event.content_hash
        assert response.prev_hash == event.prev_hash
        assert response.signature == event.signature
        assert response.witness_signature == event.witness_signature

    def test_adapter_formats_datetime_correctly(self) -> None:
        """Test datetime formatting in response."""
        from src.api.adapters.observer import EventToObserverAdapter

        timestamp = datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc)
        event = self._create_sample_event()
        # Manually set timestamp by creating new event
        from src.domain.events import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=timestamp,
        )

        response = EventToObserverAdapter.to_response(event)

        assert response.local_timestamp == timestamp

    def test_adapter_handles_null_authority_timestamp(self) -> None:
        """Test that None authority_timestamp is handled correctly."""
        from src.api.adapters.observer import EventToObserverAdapter

        event = self._create_sample_event(authority_timestamp=None)

        response = EventToObserverAdapter.to_response(event)

        assert response.authority_timestamp is None

    def test_adapter_handles_present_authority_timestamp(self) -> None:
        """Test that present authority_timestamp is preserved."""
        from src.api.adapters.observer import EventToObserverAdapter

        auth_ts = datetime(2025, 12, 27, 10, 30, 0, tzinfo=timezone.utc)
        event = self._create_sample_event(authority_timestamp=auth_ts)

        response = EventToObserverAdapter.to_response(event)

        assert response.authority_timestamp == auth_ts

    def test_adapt_list_of_events(self) -> None:
        """Test converting a list of Events to responses."""
        from src.api.adapters.observer import EventToObserverAdapter
        from src.api.models.observer import ObserverEventResponse

        events = [self._create_sample_event(sequence=i) for i in range(1, 4)]

        responses = EventToObserverAdapter.to_response_list(events)

        assert len(responses) == 3
        assert all(isinstance(r, ObserverEventResponse) for r in responses)
        assert [r.sequence for r in responses] == [1, 2, 3]

    def test_adapt_empty_list(self) -> None:
        """Test converting empty list returns empty list."""
        from src.api.adapters.observer import EventToObserverAdapter

        responses = EventToObserverAdapter.to_response_list([])

        assert responses == []

    def test_payload_conversion_from_mapping_proxy(self) -> None:
        """Test that MappingProxyType payload is converted to dict."""
        from src.api.adapters.observer import EventToObserverAdapter

        # Event stores payload as MappingProxyType
        event = self._create_sample_event(payload={"nested": {"value": 42}})

        response = EventToObserverAdapter.to_response(event)

        # Response should have regular dict
        assert isinstance(response.payload, dict)
        assert response.payload == {"nested": {"value": 42}}

    def test_adapter_maps_sig_alg_version(self) -> None:
        """Test that adapter maps sig_alg_version from domain Event (FR45, AC3).

        Per FR45/AC3: sig_alg_version MUST be included for verification.
        """
        from src.api.adapters.observer import EventToObserverAdapter

        event = self._create_sample_event()

        response = EventToObserverAdapter.to_response(event)

        # sig_alg_version must be present in response
        assert hasattr(response, "sig_alg_version")
        assert response.sig_alg_version is not None
        # Version 1 should map to "Ed25519"
        assert response.sig_alg_version == "Ed25519"

    def test_adapter_converts_sig_alg_version_to_string(self) -> None:
        """Test that numeric sig_alg_version is converted to human-readable string.

        Domain Event stores sig_alg_version as int (1 = Ed25519).
        API response should use human-readable string.
        """
        from src.api.adapters.observer import EventToObserverAdapter
        from src.domain.events import Event

        # Create event with explicit sig_alg_version = 1
        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            hash_alg_version=1,
            sig_alg_version=1,  # numeric version
            signing_key_id="key-001",
            agent_id="agent-001",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
        )

        response = EventToObserverAdapter.to_response(event)

        # Response should have string "Ed25519", not int 1
        assert isinstance(response.sig_alg_version, str)
        assert response.sig_alg_version == "Ed25519"

    def test_payload_not_transformed_unicode(self) -> None:
        """Test that unicode characters in payload are preserved (FR45, AC1).

        Per FR45: Raw payload must be included, not transformed.
        """
        from src.api.adapters.observer import EventToObserverAdapter

        # Payload with various unicode characters
        unicode_payload = {
            "japanese": "日本語テキスト",
            "emoji": "🎉🚀💻",
            "arabic": "مرحبا بالعالم",
            "math": "∑∏∫≈≠≤≥",
        }
        event = self._create_sample_event(payload=unicode_payload)

        response = EventToObserverAdapter.to_response(event)

        # All unicode should be preserved exactly
        assert response.payload["japanese"] == "日本語テキスト"
        assert response.payload["emoji"] == "🎉🚀💻"
        assert response.payload["arabic"] == "مرحبا بالعالم"
        assert response.payload["math"] == "∑∏∫≈≠≤≥"

    def test_payload_preserves_nested_structure(self) -> None:
        """Test that deeply nested structures are preserved (FR45, AC1)."""
        from src.api.adapters.observer import EventToObserverAdapter

        nested_payload = {
            "level1": {"level2": {"level3": {"level4": {"deep_value": "found"}}}},
            "array_nested": [{"id": 1, "data": [1, 2, [3, 4, {"x": "y"}]]}],
        }
        event = self._create_sample_event(payload=nested_payload)

        response = EventToObserverAdapter.to_response(event)

        # Deep nesting preserved
        assert (
            response.payload["level1"]["level2"]["level3"]["level4"]["deep_value"]
            == "found"
        )
        # Array nesting preserved
        assert response.payload["array_nested"][0]["data"][2][2]["x"] == "y"

    def test_payload_preserves_special_characters(self) -> None:
        """Test that special characters in payload are preserved (FR45, AC1)."""
        from src.api.adapters.observer import EventToObserverAdapter

        special_payload = {
            "quotes": 'He said "Hello"',
            "backslash": "path\\to\\file",
            "newlines": "line1\nline2\nline3",
            "tabs": "col1\tcol2\tcol3",
            "null_in_string": "before\x00after",  # Null char
        }
        event = self._create_sample_event(payload=special_payload)

        response = EventToObserverAdapter.to_response(event)

        assert response.payload["quotes"] == 'He said "Hello"'
        assert response.payload["backslash"] == "path\\to\\file"
        assert response.payload["newlines"] == "line1\nline2\nline3"
        assert response.payload["tabs"] == "col1\tcol2\tcol3"

    def test_payload_preserves_numeric_precision(self) -> None:
        """Test that numeric precision is preserved (FR45, AC1)."""
        from src.api.adapters.observer import EventToObserverAdapter

        numeric_payload = {
            "integer": 9007199254740993,  # Beyond JS safe integer
            "float_precise": 3.141592653589793,
            "very_small": 0.0000000001,
            "negative": -12345678901234,
            "zero": 0,
            "scientific": 1e-10,
        }
        event = self._create_sample_event(payload=numeric_payload)

        response = EventToObserverAdapter.to_response(event)

        assert response.payload["integer"] == 9007199254740993
        assert response.payload["float_precise"] == 3.141592653589793
        assert response.payload["very_small"] == 0.0000000001
        assert response.payload["negative"] == -12345678901234
        assert response.payload["zero"] == 0
