"""Unit tests for ThresholdUpdatedEventPayload (Story 6.4, FR33-FR34).

Tests the threshold update event payload.
"""

from datetime import datetime, timezone

import pytest

from src.domain.events.threshold import (
    THRESHOLD_UPDATED_EVENT_TYPE,
    ThresholdUpdatedEventPayload,
)


class TestThresholdUpdatedEventPayload:
    """Tests for ThresholdUpdatedEventPayload."""

    def test_create_payload(self) -> None:
        """Test creating a payload with all fields."""
        now = datetime.now(timezone.utc)
        payload = ThresholdUpdatedEventPayload(
            threshold_name="test_threshold",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )

        assert payload.threshold_name == "test_threshold"
        assert payload.previous_value == 10
        assert payload.new_value == 15
        assert payload.constitutional_floor == 10
        assert payload.fr_reference == "FR33"
        assert payload.updated_at == now
        assert payload.updated_by == "keeper-001"

    def test_to_dict_returns_dict(self) -> None:
        """Test to_dict() returns a dict, not bytes (AC3)."""
        now = datetime.now(timezone.utc)
        payload = ThresholdUpdatedEventPayload(
            threshold_name="test_threshold",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )

        result = payload.to_dict()

        assert isinstance(result, dict)
        assert result["threshold_name"] == "test_threshold"
        assert result["previous_value"] == 10
        assert result["new_value"] == 15
        assert result["constitutional_floor"] == 10
        assert result["fr_reference"] == "FR33"
        assert result["updated_at"] == now.isoformat()
        assert result["updated_by"] == "keeper-001"

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content() returns bytes for signing."""
        now = datetime.now(timezone.utc)
        payload = ThresholdUpdatedEventPayload(
            threshold_name="test_threshold",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )

        result = payload.signable_content()

        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content() is deterministic for same payload."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = ThresholdUpdatedEventPayload(
            threshold_name="test",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )
        payload2 = ThresholdUpdatedEventPayload(
            threshold_name="test",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_content_hash_returns_hex_string(self) -> None:
        """Test content_hash() returns SHA-256 hex string."""
        now = datetime.now(timezone.utc)
        payload = ThresholdUpdatedEventPayload(
            threshold_name="test",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )

        result = payload.content_hash()

        # SHA-256 produces 64 hex characters
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_content_hash_is_deterministic(self) -> None:
        """Test content_hash() is deterministic for same payload."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = ThresholdUpdatedEventPayload(
            threshold_name="test",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )
        payload2 = ThresholdUpdatedEventPayload(
            threshold_name="test",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )

        assert payload1.content_hash() == payload2.content_hash()

    def test_payload_is_frozen_immutable(self) -> None:
        """Test payload is immutable (frozen dataclass)."""
        now = datetime.now(timezone.utc)
        payload = ThresholdUpdatedEventPayload(
            threshold_name="test",
            previous_value=10,
            new_value=15,
            constitutional_floor=10,
            fr_reference="FR33",
            updated_at=now,
            updated_by="keeper-001",
        )

        with pytest.raises(AttributeError):
            payload.new_value = 20  # type: ignore[misc]

    def test_event_type_constant(self) -> None:
        """Test event type constant is defined."""
        assert THRESHOLD_UPDATED_EVENT_TYPE == "threshold.updated"

    def test_with_float_values(self) -> None:
        """Test payload works with float values."""
        now = datetime.now(timezone.utc)
        payload = ThresholdUpdatedEventPayload(
            threshold_name="diversity",
            previous_value=0.30,
            new_value=0.35,
            constitutional_floor=0.30,
            fr_reference="FR73",
            updated_at=now,
            updated_by="keeper-001",
        )

        assert payload.previous_value == 0.30
        assert payload.new_value == 0.35
        assert "0.35" in str(payload.to_dict())
