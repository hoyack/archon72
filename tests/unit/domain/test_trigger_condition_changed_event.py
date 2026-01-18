"""Unit tests for TriggerConditionChangedEventPayload (Story 7.7, FR134 AC4).

Tests the event payload for trigger condition changes.

Constitutional Constraints Tested:
- FR134 AC4: TriggerConditionChangedEvent with old_value, new_value, changed_by, change_reason
- CT-12: Witnessing creates accountability -> signable_content for witnessing
- FR33: Threshold definitions SHALL be constitutional, not operational
"""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.trigger_condition_changed import (
    TRIGGER_CONDITION_CHANGED_EVENT_TYPE,
    TriggerConditionChangedEventPayload,
)


class TestTriggerConditionChangedEventPayload:
    """Tests for TriggerConditionChangedEventPayload."""

    def test_create_payload_with_required_fields(self) -> None:
        """Test creating a payload with all required fields (FR134 AC4)."""
        change_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        payload = TriggerConditionChangedEventPayload(
            change_id=change_id,
            trigger_type="breach_threshold",
            old_value=10,
            new_value=12,
            changed_by="keeper-001",
            change_reason="Constitutional amendment approved",
            change_timestamp=timestamp,
        )

        assert payload.change_id == change_id
        assert payload.trigger_type == "breach_threshold"
        assert payload.old_value == 10
        assert payload.new_value == 12
        assert payload.changed_by == "keeper-001"
        assert payload.change_reason == "Constitutional amendment approved"
        assert payload.change_timestamp == timestamp

    def test_create_payload_with_optional_fields(self) -> None:
        """Test creating a payload with optional fields."""
        payload = TriggerConditionChangedEventPayload(
            change_id=uuid4(),
            trigger_type="breach_threshold",
            old_value=10,
            new_value=12,
            changed_by="keeper-001",
            change_reason="Amendment",
            change_timestamp=datetime.now(timezone.utc),
            fr_reference="FR32",
            constitutional_floor=10,
        )

        assert payload.fr_reference == "FR32"
        assert payload.constitutional_floor == 10

    def test_payload_validation_rejects_below_floor(self) -> None:
        """Test that new_value below constitutional_floor raises error (FR33)."""
        with pytest.raises(ValueError, match="cannot be below constitutional_floor"):
            TriggerConditionChangedEventPayload(
                change_id=uuid4(),
                trigger_type="breach_threshold",
                old_value=10,
                new_value=5,  # Below floor of 10
                changed_by="keeper-001",
                change_reason="Invalid change",
                change_timestamp=datetime.now(timezone.utc),
                constitutional_floor=10,
            )

    def test_payload_allows_value_equal_to_floor(self) -> None:
        """Test that new_value equal to constitutional_floor is valid."""
        payload = TriggerConditionChangedEventPayload(
            change_id=uuid4(),
            trigger_type="breach_threshold",
            old_value=12,
            new_value=10,  # Equal to floor - valid
            changed_by="keeper-001",
            change_reason="Reduced to floor",
            change_timestamp=datetime.now(timezone.utc),
            constitutional_floor=10,
        )

        assert payload.new_value == 10

    def test_payload_allows_no_floor_validation(self) -> None:
        """Test that payload without floor allows any value."""
        payload = TriggerConditionChangedEventPayload(
            change_id=uuid4(),
            trigger_type="test_trigger",
            old_value=5,
            new_value=1,  # Would be below any floor, but no floor specified
            changed_by="system",
            change_reason="Test change",
            change_timestamp=datetime.now(timezone.utc),
            constitutional_floor=None,  # No floor
        )

        assert payload.new_value == 1

    def test_payload_is_immutable(self) -> None:
        """Test that payload is immutable (frozen dataclass)."""
        payload = TriggerConditionChangedEventPayload(
            change_id=uuid4(),
            trigger_type="test",
            old_value=10,
            new_value=12,
            changed_by="system",
            change_reason="Test",
            change_timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            payload.new_value = 15  # type: ignore[misc]

    def test_signable_content_is_deterministic(self) -> None:
        """Test that signable_content produces deterministic bytes (CT-12)."""
        change_id = UUID("12345678-1234-5678-1234-567812345678")
        timestamp = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)

        payload = TriggerConditionChangedEventPayload(
            change_id=change_id,
            trigger_type="breach_threshold",
            old_value=10,
            new_value=12,
            changed_by="keeper-001",
            change_reason="Amendment",
            change_timestamp=timestamp,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_includes_required_fields(self) -> None:
        """Test that signable_content includes all required fields (CT-12)."""
        change_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        payload = TriggerConditionChangedEventPayload(
            change_id=change_id,
            trigger_type="breach_threshold",
            old_value=10,
            new_value=12,
            changed_by="keeper-001",
            change_reason="Amendment",
            change_timestamp=timestamp,
        )

        content = payload.signable_content()
        decoded = json.loads(content.decode("utf-8"))

        assert decoded["change_id"] == str(change_id)
        assert decoded["trigger_type"] == "breach_threshold"
        assert decoded["old_value"] == 10
        assert decoded["new_value"] == 12
        assert decoded["changed_by"] == "keeper-001"
        assert decoded["change_reason"] == "Amendment"
        assert "change_timestamp" in decoded

    def test_signable_content_includes_optional_fields_when_present(self) -> None:
        """Test that signable_content includes optional fields when set."""
        payload = TriggerConditionChangedEventPayload(
            change_id=uuid4(),
            trigger_type="breach_threshold",
            old_value=10,
            new_value=12,
            changed_by="keeper-001",
            change_reason="Amendment",
            change_timestamp=datetime.now(timezone.utc),
            fr_reference="FR32",
            constitutional_floor=10,
        )

        content = payload.signable_content()
        decoded = json.loads(content.decode("utf-8"))

        assert decoded["fr_reference"] == "FR32"
        assert decoded["constitutional_floor"] == 10

    def test_to_dict_returns_serializable_dict(self) -> None:
        """Test that to_dict returns a JSON-serializable dictionary."""
        change_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        payload = TriggerConditionChangedEventPayload(
            change_id=change_id,
            trigger_type="breach_threshold",
            old_value=10,
            new_value=12,
            changed_by="keeper-001",
            change_reason="Amendment",
            change_timestamp=timestamp,
            fr_reference="FR32",
            constitutional_floor=10,
        )

        result = payload.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str  # Non-empty

        # Check values
        assert result["change_id"] == str(change_id)
        assert result["trigger_type"] == "breach_threshold"
        assert result["old_value"] == 10
        assert result["new_value"] == 12
        assert result["changed_by"] == "keeper-001"
        assert result["change_reason"] == "Amendment"
        assert result["fr_reference"] == "FR32"
        assert result["constitutional_floor"] == 10

    def test_from_dict_creates_payload(self) -> None:
        """Test that from_dict can recreate a payload from dict."""
        change_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        original = TriggerConditionChangedEventPayload(
            change_id=change_id,
            trigger_type="breach_threshold",
            old_value=10,
            new_value=12,
            changed_by="keeper-001",
            change_reason="Amendment",
            change_timestamp=timestamp,
            fr_reference="FR32",
            constitutional_floor=10,
        )

        data = original.to_dict()
        restored = TriggerConditionChangedEventPayload.from_dict(data)

        assert restored.change_id == original.change_id
        assert restored.trigger_type == original.trigger_type
        assert restored.old_value == original.old_value
        assert restored.new_value == original.new_value
        assert restored.changed_by == original.changed_by
        assert restored.change_reason == original.change_reason
        assert restored.fr_reference == original.fr_reference
        assert restored.constitutional_floor == original.constitutional_floor

    def test_from_dict_handles_iso_timestamp_with_z(self) -> None:
        """Test that from_dict handles ISO timestamps with Z suffix."""
        data = {
            "change_id": str(uuid4()),
            "trigger_type": "test",
            "old_value": 10,
            "new_value": 12,
            "changed_by": "system",
            "change_reason": "Test",
            "change_timestamp": "2026-01-08T12:00:00Z",
        }

        payload = TriggerConditionChangedEventPayload.from_dict(data)

        assert payload.change_timestamp.tzinfo is not None


class TestTriggerConditionChangedEventType:
    """Tests for event type constant."""

    def test_event_type_constant_is_valid(self) -> None:
        """Test that event type constant follows naming convention."""
        assert (
            TRIGGER_CONDITION_CHANGED_EVENT_TYPE
            == "cessation.trigger_condition_changed"
        )
        assert "." in TRIGGER_CONDITION_CHANGED_EVENT_TYPE
        assert TRIGGER_CONDITION_CHANGED_EVENT_TYPE.islower()
