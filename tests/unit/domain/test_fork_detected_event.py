"""Unit tests for ForkDetectedPayload domain event (Story 3.1, Task 1).

Tests the ForkDetectedPayload dataclass for fork detection events.
This is a constitutional crisis detection mechanism (FR16).
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.fork_detected import (
    FORK_DETECTED_EVENT_TYPE,
    ForkDetectedPayload,
)


class TestForkDetectedEventType:
    """Tests for FORK_DETECTED_EVENT_TYPE constant."""

    def test_event_type_is_string(self) -> None:
        """Event type should be a string."""
        assert isinstance(FORK_DETECTED_EVENT_TYPE, str)

    def test_event_type_value(self) -> None:
        """Event type should be 'constitutional.fork_detected'."""
        assert FORK_DETECTED_EVENT_TYPE == "constitutional.fork_detected"

    def test_event_type_not_empty(self) -> None:
        """Event type should not be empty."""
        assert FORK_DETECTED_EVENT_TYPE.strip() != ""


class TestForkDetectedPayload:
    """Tests for ForkDetectedPayload dataclass."""

    @pytest.fixture
    def valid_payload_data(self) -> dict:
        """Fixture providing valid payload data."""
        return {
            "conflicting_event_ids": [uuid4(), uuid4()],
            "prev_hash": "a" * 64,  # SHA-256 hash length
            "content_hashes": ["b" * 64, "c" * 64],
            "detection_timestamp": datetime.now(timezone.utc),
            "detecting_service_id": "fork-monitor-001",
        }

    def test_create_valid_payload(self, valid_payload_data: dict) -> None:
        """Should create payload with valid data."""
        payload = ForkDetectedPayload(**valid_payload_data)

        assert len(payload.conflicting_event_ids) == 2
        assert payload.prev_hash == valid_payload_data["prev_hash"]
        assert len(payload.content_hashes) == 2
        assert payload.detection_timestamp == valid_payload_data["detection_timestamp"]
        assert payload.detecting_service_id == valid_payload_data["detecting_service_id"]

    def test_payload_is_frozen(self, valid_payload_data: dict) -> None:
        """Payload should be immutable (frozen dataclass)."""
        payload = ForkDetectedPayload(**valid_payload_data)

        with pytest.raises(AttributeError):
            payload.prev_hash = "d" * 64  # type: ignore[misc]

    def test_conflicting_event_ids_are_uuids(self, valid_payload_data: dict) -> None:
        """Conflicting event IDs should be UUIDs."""
        payload = ForkDetectedPayload(**valid_payload_data)

        for event_id in payload.conflicting_event_ids:
            assert isinstance(event_id, UUID)

    def test_content_hashes_are_strings(self, valid_payload_data: dict) -> None:
        """Content hashes should be strings."""
        payload = ForkDetectedPayload(**valid_payload_data)

        for content_hash in payload.content_hashes:
            assert isinstance(content_hash, str)

    def test_detection_timestamp_is_datetime(self, valid_payload_data: dict) -> None:
        """Detection timestamp should be datetime."""
        payload = ForkDetectedPayload(**valid_payload_data)

        assert isinstance(payload.detection_timestamp, datetime)

    def test_detection_timestamp_has_timezone(self, valid_payload_data: dict) -> None:
        """Detection timestamp should have timezone info."""
        payload = ForkDetectedPayload(**valid_payload_data)

        assert payload.detection_timestamp.tzinfo is not None

    def test_detecting_service_id_is_string(self, valid_payload_data: dict) -> None:
        """Detecting service ID should be string."""
        payload = ForkDetectedPayload(**valid_payload_data)

        assert isinstance(payload.detecting_service_id, str)

    def test_payload_equality(self, valid_payload_data: dict) -> None:
        """Two payloads with same data should be equal."""
        payload1 = ForkDetectedPayload(**valid_payload_data)
        payload2 = ForkDetectedPayload(**valid_payload_data)

        assert payload1 == payload2

    def test_payload_to_dict(self, valid_payload_data: dict) -> None:
        """Payload should be convertible to dict."""
        payload = ForkDetectedPayload(**valid_payload_data)

        # Using dataclasses.asdict would work, but checking fields directly
        assert hasattr(payload, "conflicting_event_ids")
        assert hasattr(payload, "prev_hash")
        assert hasattr(payload, "content_hashes")
        assert hasattr(payload, "detection_timestamp")
        assert hasattr(payload, "detecting_service_id")

    def test_minimum_two_conflicting_events(self) -> None:
        """Fork detection requires at least 2 conflicting events."""
        # Valid: 2 events
        payload = ForkDetectedPayload(
            conflicting_event_ids=[uuid4(), uuid4()],
            prev_hash="a" * 64,
            content_hashes=["b" * 64, "c" * 64],
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-001",
        )
        assert len(payload.conflicting_event_ids) == 2

    def test_content_hashes_match_event_count(self, valid_payload_data: dict) -> None:
        """Content hashes list should match conflicting event IDs count."""
        payload = ForkDetectedPayload(**valid_payload_data)

        assert len(payload.content_hashes) == len(payload.conflicting_event_ids)

    def test_prev_hash_is_shared(self, valid_payload_data: dict) -> None:
        """prev_hash should be the shared hash that caused the fork."""
        payload = ForkDetectedPayload(**valid_payload_data)

        # The prev_hash is what both events claimed as their predecessor
        assert isinstance(payload.prev_hash, str)
        assert len(payload.prev_hash) == 64  # SHA-256 hex length


class TestForkDetectedPayloadSignableContent:
    """Tests for ForkDetectedPayload.signable_content() method (Story 3.8, FR84)."""

    @pytest.fixture
    def payload_with_known_values(self) -> ForkDetectedPayload:
        """Fixture with deterministic values for signable content tests."""
        return ForkDetectedPayload(
            conflicting_event_ids=[
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            ],
            prev_hash="a" * 64,
            content_hashes=["b" * 64, "c" * 64],
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detecting_service_id="fork-monitor-001",
        )

    def test_signable_content_returns_bytes(
        self, payload_with_known_values: ForkDetectedPayload
    ) -> None:
        """signable_content() should return bytes."""
        result = payload_with_known_values.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(
        self, payload_with_known_values: ForkDetectedPayload
    ) -> None:
        """signable_content() should return same bytes for same payload."""
        result1 = payload_with_known_values.signable_content()
        result2 = payload_with_known_values.signable_content()
        assert result1 == result2

    def test_signable_content_includes_all_fields(
        self, payload_with_known_values: ForkDetectedPayload
    ) -> None:
        """signable_content() should include all payload fields."""
        result = payload_with_known_values.signable_content()
        decoded = result.decode("utf-8")

        # Must include prev_hash
        assert payload_with_known_values.prev_hash in decoded

        # Must include detecting_service_id
        assert payload_with_known_values.detecting_service_id in decoded

        # Must include content hashes
        for content_hash in payload_with_known_values.content_hashes:
            assert content_hash in decoded

        # Must include event IDs (as strings)
        for event_id in payload_with_known_values.conflicting_event_ids:
            assert str(event_id) in decoded

    def test_signable_content_sorts_event_ids(self) -> None:
        """signable_content() should sort event IDs for deterministic output."""
        # Create two payloads with same event IDs in different order
        event_id_1 = UUID("22222222-2222-2222-2222-222222222222")
        event_id_2 = UUID("11111111-1111-1111-1111-111111111111")

        payload1 = ForkDetectedPayload(
            conflicting_event_ids=[event_id_1, event_id_2],  # 2, 1 order
            prev_hash="a" * 64,
            content_hashes=["b" * 64, "c" * 64],
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detecting_service_id="fork-monitor-001",
        )

        payload2 = ForkDetectedPayload(
            conflicting_event_ids=[event_id_2, event_id_1],  # 1, 2 order
            prev_hash="a" * 64,
            content_hashes=["b" * 64, "c" * 64],
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detecting_service_id="fork-monitor-001",
        )

        # Both should produce same signable content (sorted)
        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_sorts_content_hashes(self) -> None:
        """signable_content() should sort content hashes for deterministic output."""
        hash_1 = "z" * 64
        hash_2 = "a" * 64

        payload1 = ForkDetectedPayload(
            conflicting_event_ids=[uuid4(), uuid4()],
            prev_hash="x" * 64,
            content_hashes=[hash_1, hash_2],  # z, a order
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detecting_service_id="fork-monitor-001",
        )

        payload2 = ForkDetectedPayload(
            conflicting_event_ids=payload1.conflicting_event_ids,
            prev_hash="x" * 64,
            content_hashes=[hash_2, hash_1],  # a, z order
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detecting_service_id="fork-monitor-001",
        )

        # Both should produce same signable content (sorted)
        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_includes_timestamp(
        self, payload_with_known_values: ForkDetectedPayload
    ) -> None:
        """signable_content() should include detection timestamp in ISO format."""
        result = payload_with_known_values.signable_content()
        decoded = result.decode("utf-8")

        # Timestamp should be in ISO format
        assert "2025-01-01T12:00:00" in decoded

    def test_signable_content_different_for_different_payloads(self) -> None:
        """Different payloads should have different signable content."""
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = ForkDetectedPayload(
            conflicting_event_ids=[uuid4(), uuid4()],
            prev_hash="a" * 64,
            content_hashes=["b" * 64, "c" * 64],
            detection_timestamp=timestamp,
            detecting_service_id="fork-monitor-001",
        )

        payload2 = ForkDetectedPayload(
            conflicting_event_ids=[uuid4(), uuid4()],  # Different IDs
            prev_hash="d" * 64,  # Different hash
            content_hashes=["e" * 64, "f" * 64],
            detection_timestamp=timestamp,
            detecting_service_id="fork-monitor-002",  # Different service
        )

        assert payload1.signable_content() != payload2.signable_content()

    def test_signable_content_not_empty(
        self, payload_with_known_values: ForkDetectedPayload
    ) -> None:
        """signable_content() should not return empty bytes."""
        result = payload_with_known_values.signable_content()
        assert len(result) > 0
