"""Unit tests for ForkSignalRateLimitPayload domain event (Story 3.8, FR85).

Tests the ForkSignalRateLimitPayload dataclass for rate limit events.

Constitutional Constraints:
- FR85: More than 3 fork signals per hour triggers rate limiting
- CT-11: Silent failure destroys legitimacy - rate limits MUST be logged
"""

from datetime import datetime, timezone

import pytest

from src.domain.events.fork_signal_rate_limit import (
    FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE,
    ForkSignalRateLimitPayload,
)


class TestForkSignalRateLimitEventType:
    """Tests for FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE constant."""

    def test_event_type_is_string(self) -> None:
        """Event type should be a string."""
        assert isinstance(FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE, str)

    def test_event_type_value(self) -> None:
        """Event type should be 'fork.signal_rate_limit'."""
        assert FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE == "fork.signal_rate_limit"

    def test_event_type_not_empty(self) -> None:
        """Event type should not be empty."""
        assert FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE.strip() != ""


class TestForkSignalRateLimitPayload:
    """Tests for ForkSignalRateLimitPayload dataclass."""

    @pytest.fixture
    def valid_payload_data(self) -> dict:
        """Fixture providing valid payload data."""
        return {
            "source_service_id": "fork-monitor-001",
            "signal_count": 5,
            "window_start": datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            "window_hours": 1,
            "rate_limited_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        }

    def test_create_valid_payload(self, valid_payload_data: dict) -> None:
        """Should create payload with valid data."""
        payload = ForkSignalRateLimitPayload(**valid_payload_data)

        assert payload.source_service_id == valid_payload_data["source_service_id"]
        assert payload.signal_count == valid_payload_data["signal_count"]
        assert payload.window_start == valid_payload_data["window_start"]
        assert payload.window_hours == valid_payload_data["window_hours"]
        assert payload.rate_limited_at == valid_payload_data["rate_limited_at"]

    def test_payload_is_frozen(self, valid_payload_data: dict) -> None:
        """Payload should be immutable (frozen dataclass)."""
        payload = ForkSignalRateLimitPayload(**valid_payload_data)

        with pytest.raises(AttributeError):
            payload.source_service_id = "new-id"  # type: ignore[misc]

    def test_source_service_id_is_string(self, valid_payload_data: dict) -> None:
        """source_service_id should be a string."""
        payload = ForkSignalRateLimitPayload(**valid_payload_data)
        assert isinstance(payload.source_service_id, str)

    def test_signal_count_is_int(self, valid_payload_data: dict) -> None:
        """signal_count should be an integer."""
        payload = ForkSignalRateLimitPayload(**valid_payload_data)
        assert isinstance(payload.signal_count, int)

    def test_window_start_is_datetime(self, valid_payload_data: dict) -> None:
        """window_start should be datetime."""
        payload = ForkSignalRateLimitPayload(**valid_payload_data)
        assert isinstance(payload.window_start, datetime)

    def test_window_hours_is_int(self, valid_payload_data: dict) -> None:
        """window_hours should be an integer."""
        payload = ForkSignalRateLimitPayload(**valid_payload_data)
        assert isinstance(payload.window_hours, int)

    def test_rate_limited_at_is_datetime(self, valid_payload_data: dict) -> None:
        """rate_limited_at should be datetime."""
        payload = ForkSignalRateLimitPayload(**valid_payload_data)
        assert isinstance(payload.rate_limited_at, datetime)

    def test_payload_equality(self, valid_payload_data: dict) -> None:
        """Two payloads with same data should be equal."""
        payload1 = ForkSignalRateLimitPayload(**valid_payload_data)
        payload2 = ForkSignalRateLimitPayload(**valid_payload_data)

        assert payload1 == payload2

    def test_default_window_hours(self) -> None:
        """window_hours should default to 1 if not specified."""
        payload = ForkSignalRateLimitPayload(
            source_service_id="fork-monitor-001",
            signal_count=5,
            window_start=datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            rate_limited_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert payload.window_hours == 1


class TestForkSignalRateLimitPayloadSignableContent:
    """Tests for ForkSignalRateLimitPayload.signable_content() method."""

    @pytest.fixture
    def payload_with_known_values(self) -> ForkSignalRateLimitPayload:
        """Fixture with deterministic values for signable content tests."""
        return ForkSignalRateLimitPayload(
            source_service_id="fork-monitor-001",
            signal_count=5,
            window_start=datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            window_hours=1,
            rate_limited_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_signable_content_returns_bytes(
        self, payload_with_known_values: ForkSignalRateLimitPayload
    ) -> None:
        """signable_content() should return bytes."""
        result = payload_with_known_values.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(
        self, payload_with_known_values: ForkSignalRateLimitPayload
    ) -> None:
        """signable_content() should return same bytes for same payload."""
        result1 = payload_with_known_values.signable_content()
        result2 = payload_with_known_values.signable_content()
        assert result1 == result2

    def test_signable_content_includes_all_fields(
        self, payload_with_known_values: ForkSignalRateLimitPayload
    ) -> None:
        """signable_content() should include all payload fields."""
        result = payload_with_known_values.signable_content()
        decoded = result.decode("utf-8")

        assert payload_with_known_values.source_service_id in decoded
        assert str(payload_with_known_values.signal_count) in decoded
        assert str(payload_with_known_values.window_hours) in decoded
        # Timestamps should be in ISO format
        assert "2025-01-01T11:00:00" in decoded
        assert "2025-01-01T12:00:00" in decoded

    def test_signable_content_different_for_different_payloads(self) -> None:
        """Different payloads should have different signable content."""
        payload1 = ForkSignalRateLimitPayload(
            source_service_id="fork-monitor-001",
            signal_count=5,
            window_start=datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            window_hours=1,
            rate_limited_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        payload2 = ForkSignalRateLimitPayload(
            source_service_id="fork-monitor-002",  # Different source
            signal_count=10,  # Different count
            window_start=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            window_hours=2,
            rate_limited_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert payload1.signable_content() != payload2.signable_content()

    def test_signable_content_not_empty(
        self, payload_with_known_values: ForkSignalRateLimitPayload
    ) -> None:
        """signable_content() should not return empty bytes."""
        result = payload_with_known_values.signable_content()
        assert len(result) > 0
