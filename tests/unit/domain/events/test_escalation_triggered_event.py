"""Unit tests for PetitionEscalationTriggeredEvent (Story 5.6, FR-5.1, FR-5.3).

Tests the petition escalation event payload used when co-signer thresholds
are reached and auto-escalation occurs.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- CT-12: All outputs through witnessing pipeline
- D2: Use to_dict() not asdict(), include schema_version
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.petition_escalation import (
    PETITION_ESCALATION_SCHEMA_VERSION,
    PETITION_ESCALATION_TRIGGERED_EVENT_TYPE,
    PetitionEscalationTriggeredEvent,
)


class TestPetitionEscalationTriggeredEventConstants:
    """Test module constants."""

    def test_event_type_constant(self) -> None:
        """Event type constant is correctly defined."""
        assert (
            PETITION_ESCALATION_TRIGGERED_EVENT_TYPE == "petition.escalation.triggered"
        )

    def test_schema_version_constant(self) -> None:
        """Schema version is 1 per D2 compliance."""
        assert PETITION_ESCALATION_SCHEMA_VERSION == 1


class TestPetitionEscalationTriggeredEventCreation:
    """Test event creation and field values."""

    def test_create_with_required_fields(self) -> None:
        """Event can be created with required fields only."""
        escalation_id = uuid4()
        petition_id = uuid4()
        triggered_at = datetime.now(timezone.utc)

        event = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )

        assert event.escalation_id == escalation_id
        assert event.petition_id == petition_id
        assert event.trigger_type == "CO_SIGNER_THRESHOLD"
        assert event.co_signer_count == 100
        assert event.threshold == 100
        assert event.triggered_at == triggered_at

    def test_default_values(self) -> None:
        """Event has correct default values."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
        )

        assert event.triggered_by is None
        assert event.petition_type is None
        assert event.escalation_source == "CO_SIGNER_THRESHOLD"
        assert event.realm_id == "default"
        assert event.schema_version == 1

    def test_create_with_all_fields(self) -> None:
        """Event can be created with all optional fields."""
        escalation_id = uuid4()
        petition_id = uuid4()
        triggered_by = uuid4()
        triggered_at = datetime.now(timezone.utc)

        event = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
            triggered_by=triggered_by,
            petition_type="CESSATION",
            escalation_source="CO_SIGNER_THRESHOLD",
            realm_id="custom-realm",
        )

        assert event.triggered_by == triggered_by
        assert event.petition_type == "CESSATION"
        assert event.escalation_source == "CO_SIGNER_THRESHOLD"
        assert event.realm_id == "custom-realm"


class TestPetitionEscalationTriggeredEventImmutability:
    """Test event immutability (frozen dataclass)."""

    def test_frozen(self) -> None:
        """Event is immutable (frozen dataclass)."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            event.co_signer_count = 200  # type: ignore[misc]


class TestPetitionEscalationTriggeredEventEquality:
    """Test event equality comparison."""

    def test_equality(self) -> None:
        """Events with same fields are equal."""
        escalation_id = uuid4()
        petition_id = uuid4()
        triggered_at = datetime.now(timezone.utc)

        event1 = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )
        event2 = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )

        assert event1 == event2

    def test_inequality_different_escalation_id(self) -> None:
        """Events with different escalation_id are not equal."""
        petition_id = uuid4()
        triggered_at = datetime.now(timezone.utc)

        event1 = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )
        event2 = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )

        assert event1 != event2


class TestPetitionEscalationTriggeredEventSignableContent:
    """Test signable_content method for CT-12 witnessing."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content returns UTF-8 encoded bytes."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
        )

        content = event.signable_content()

        assert isinstance(content, bytes)

    def test_signable_content_is_valid_json(self) -> None:
        """signable_content produces valid JSON."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert isinstance(parsed, dict)

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content produces deterministic output (CT-12)."""
        escalation_id = uuid4()
        petition_id = uuid4()
        triggered_at = datetime.now(timezone.utc)

        event1 = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )
        event2 = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )

        assert event1.signable_content() == event2.signable_content()

    def test_signable_content_includes_all_fields(self) -> None:
        """signable_content includes all event fields."""
        escalation_id = uuid4()
        petition_id = uuid4()
        triggered_by = uuid4()
        triggered_at = datetime.now(timezone.utc)

        event = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
            triggered_by=triggered_by,
            petition_type="CESSATION",
            escalation_source="CO_SIGNER_THRESHOLD",
            realm_id="test-realm",
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["escalation_id"] == str(escalation_id)
        assert parsed["petition_id"] == str(petition_id)
        assert parsed["trigger_type"] == "CO_SIGNER_THRESHOLD"
        assert parsed["co_signer_count"] == 100
        assert parsed["threshold"] == 100
        assert parsed["triggered_at"] == triggered_at.isoformat()
        assert parsed["triggered_by"] == str(triggered_by)
        assert parsed["petition_type"] == "CESSATION"
        assert parsed["escalation_source"] == "CO_SIGNER_THRESHOLD"
        assert parsed["realm_id"] == "test-realm"
        assert parsed["schema_version"] == 1

    def test_signable_content_handles_none_triggered_by(self) -> None:
        """signable_content handles None triggered_by correctly."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
            triggered_by=None,
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["triggered_by"] is None

    def test_signable_content_sorted_keys(self) -> None:
        """signable_content JSON has sorted keys for determinism."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
        )

        content = event.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())

        assert keys == sorted(keys)


class TestPetitionEscalationTriggeredEventToDict:
    """Test to_dict method for D2 compliance."""

    def test_to_dict_returns_dict(self) -> None:
        """to_dict returns a dictionary."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
        )

        result = event.to_dict()

        assert isinstance(result, dict)

    def test_to_dict_serializes_uuids_as_strings(self) -> None:
        """to_dict serializes UUIDs as strings (D2)."""
        escalation_id = uuid4()
        petition_id = uuid4()
        triggered_by = uuid4()

        event = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
            triggered_by=triggered_by,
        )

        result = event.to_dict()

        assert result["escalation_id"] == str(escalation_id)
        assert result["petition_id"] == str(petition_id)
        assert result["triggered_by"] == str(triggered_by)

    def test_to_dict_serializes_datetime_as_iso8601(self) -> None:
        """to_dict serializes datetime as ISO 8601 string (D2)."""
        triggered_at = datetime.now(timezone.utc)

        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
        )

        result = event.to_dict()

        assert result["triggered_at"] == triggered_at.isoformat()

    def test_to_dict_includes_schema_version(self) -> None:
        """to_dict includes schema_version for D2 compliance."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
        )

        result = event.to_dict()

        assert "schema_version" in result
        assert result["schema_version"] == 1

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all event fields."""
        escalation_id = uuid4()
        petition_id = uuid4()
        triggered_by = uuid4()
        triggered_at = datetime.now(timezone.utc)

        event = PetitionEscalationTriggeredEvent(
            escalation_id=escalation_id,
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=triggered_at,
            triggered_by=triggered_by,
            petition_type="CESSATION",
            escalation_source="CO_SIGNER_THRESHOLD",
            realm_id="test-realm",
        )

        result = event.to_dict()

        assert result["escalation_id"] == str(escalation_id)
        assert result["petition_id"] == str(petition_id)
        assert result["trigger_type"] == "CO_SIGNER_THRESHOLD"
        assert result["co_signer_count"] == 100
        assert result["threshold"] == 100
        assert result["triggered_at"] == triggered_at.isoformat()
        assert result["triggered_by"] == str(triggered_by)
        assert result["petition_type"] == "CESSATION"
        assert result["escalation_source"] == "CO_SIGNER_THRESHOLD"
        assert result["realm_id"] == "test-realm"
        assert result["schema_version"] == 1

    def test_to_dict_handles_none_triggered_by(self) -> None:
        """to_dict handles None triggered_by correctly."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
            triggered_by=None,
        )

        result = event.to_dict()

        assert result["triggered_by"] is None

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict result can be JSON serialized."""
        event = PetitionEscalationTriggeredEvent(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_at=datetime.now(timezone.utc),
            triggered_by=uuid4(),
            petition_type="CESSATION",
        )

        result = event.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
