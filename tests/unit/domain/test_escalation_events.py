"""Unit tests for escalation event payloads (Story 6.2, FR31).

Tests:
- EscalationEventPayload creation with required fields
- BreachAcknowledgedEventPayload creation
- ResponseChoice enum values
- signable_content() determinism
- Payload immutability (frozen dataclass)

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-12: Witnessing creates accountability -> signable_content() is critical
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.breach import BreachType
from src.domain.events.escalation import (
    BREACH_ACKNOWLEDGED_EVENT_TYPE,
    ESCALATION_EVENT_TYPE,
    BreachAcknowledgedEventPayload,
    EscalationEventPayload,
    ResponseChoice,
)


class TestEscalationEventType:
    """Tests for escalation event type constant."""

    def test_escalation_event_type_value(self) -> None:
        """Verify escalation event type constant value."""
        assert ESCALATION_EVENT_TYPE == "breach.escalated"

    def test_breach_acknowledged_event_type_value(self) -> None:
        """Verify breach acknowledged event type constant value."""
        assert BREACH_ACKNOWLEDGED_EVENT_TYPE == "breach.acknowledged"


class TestResponseChoice:
    """Tests for ResponseChoice enum."""

    def test_response_choice_corrective_value(self) -> None:
        """Verify CORRECTIVE value."""
        assert ResponseChoice.CORRECTIVE.value == "corrective"

    def test_response_choice_dismiss_value(self) -> None:
        """Verify DISMISS value."""
        assert ResponseChoice.DISMISS.value == "dismiss"

    def test_response_choice_defer_value(self) -> None:
        """Verify DEFER value."""
        assert ResponseChoice.DEFER.value == "defer"

    def test_response_choice_accept_value(self) -> None:
        """Verify ACCEPT value."""
        assert ResponseChoice.ACCEPT.value == "accept"

    def test_response_choice_is_string_enum(self) -> None:
        """Verify ResponseChoice inherits from str."""
        assert isinstance(ResponseChoice.CORRECTIVE, str)
        assert ResponseChoice.CORRECTIVE == "corrective"

    def test_all_response_choices_defined(self) -> None:
        """Verify all expected response choices exist."""
        choices = {choice.value for choice in ResponseChoice}
        expected = {"corrective", "dismiss", "defer", "accept"}
        assert choices == expected


class TestEscalationEventPayload:
    """Tests for EscalationEventPayload dataclass."""

    @pytest.fixture
    def sample_escalation(self) -> EscalationEventPayload:
        """Create a sample escalation event payload for testing."""
        return EscalationEventPayload(
            escalation_id=UUID("12345678-1234-5678-1234-567812345678"),
            breach_id=UUID("87654321-4321-8765-4321-876543218765"),
            breach_type=BreachType.THRESHOLD_VIOLATION,
            escalation_timestamp=datetime(2025, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            days_since_breach=7,
            agenda_placement_reason="7-day unacknowledged breach per FR31",
        )

    def test_escalation_event_creation(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test creating an escalation event payload with all required fields."""
        assert sample_escalation.escalation_id == UUID(
            "12345678-1234-5678-1234-567812345678"
        )
        assert sample_escalation.breach_id == UUID(
            "87654321-4321-8765-4321-876543218765"
        )
        assert sample_escalation.breach_type == BreachType.THRESHOLD_VIOLATION
        assert sample_escalation.escalation_timestamp == datetime(
            2025, 1, 8, 12, 0, 0, tzinfo=timezone.utc
        )
        assert sample_escalation.days_since_breach == 7
        assert (
            sample_escalation.agenda_placement_reason
            == "7-day unacknowledged breach per FR31"
        )

    def test_escalation_event_is_frozen(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test that escalation event payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_escalation.days_since_breach = 8  # type: ignore[misc]

    def test_escalation_event_equality(self) -> None:
        """Test equality comparison between escalation events."""
        timestamp = datetime(2025, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        escalation_id = uuid4()
        breach_id = uuid4()

        event1 = EscalationEventPayload(
            escalation_id=escalation_id,
            breach_id=breach_id,
            breach_type=BreachType.THRESHOLD_VIOLATION,
            escalation_timestamp=timestamp,
            days_since_breach=7,
            agenda_placement_reason="FR31",
        )

        event2 = EscalationEventPayload(
            escalation_id=escalation_id,
            breach_id=breach_id,
            breach_type=BreachType.THRESHOLD_VIOLATION,
            escalation_timestamp=timestamp,
            days_since_breach=7,
            agenda_placement_reason="FR31",
        )

        assert event1 == event2

    def test_signable_content_returns_bytes(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test that signable_content() returns bytes (CT-12)."""
        content = sample_escalation.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_valid_json(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test that signable_content() is valid JSON."""
        content = sample_escalation.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_signable_content_deterministic(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test that signable_content() produces identical output on repeated calls (CT-12)."""
        content1 = sample_escalation.signable_content()
        content2 = sample_escalation.signable_content()
        assert content1 == content2

    def test_signable_content_sorted_keys(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test that signable_content() uses sorted keys for determinism."""
        content = sample_escalation.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_signable_content_contains_all_fields(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test that signable_content() includes all required fields."""
        content = sample_escalation.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert "escalation_id" in parsed
        assert "breach_id" in parsed
        assert "breach_type" in parsed
        assert "escalation_timestamp" in parsed
        assert "days_since_breach" in parsed
        assert "agenda_placement_reason" in parsed

    def test_signable_content_breach_type_as_value(
        self, sample_escalation: EscalationEventPayload
    ) -> None:
        """Test that breach_type is serialized as its value, not enum name."""
        content = sample_escalation.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert parsed["breach_type"] == "THRESHOLD_VIOLATION"

    def test_different_breach_types(self) -> None:
        """Test escalation events with different breach types."""
        base_args = {
            "escalation_id": uuid4(),
            "breach_id": uuid4(),
            "escalation_timestamp": datetime.now(timezone.utc),
            "days_since_breach": 7,
            "agenda_placement_reason": "FR31",
        }

        for breach_type in BreachType:
            event = EscalationEventPayload(breach_type=breach_type, **base_args)
            assert event.breach_type == breach_type


class TestBreachAcknowledgedEventPayload:
    """Tests for BreachAcknowledgedEventPayload dataclass."""

    @pytest.fixture
    def sample_acknowledgment(self) -> BreachAcknowledgedEventPayload:
        """Create a sample breach acknowledged event payload for testing."""
        return BreachAcknowledgedEventPayload(
            acknowledgment_id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            breach_id=UUID("87654321-4321-8765-4321-876543218765"),
            acknowledged_by="keeper:alice@archon72.io",
            acknowledgment_timestamp=datetime(2025, 1, 7, 12, 0, 0, tzinfo=timezone.utc),
            response_choice=ResponseChoice.CORRECTIVE,
        )

    def test_acknowledgment_event_creation(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test creating an acknowledgment event payload with all required fields."""
        assert sample_acknowledgment.acknowledgment_id == UUID(
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        )
        assert sample_acknowledgment.breach_id == UUID(
            "87654321-4321-8765-4321-876543218765"
        )
        assert sample_acknowledgment.acknowledged_by == "keeper:alice@archon72.io"
        assert sample_acknowledgment.acknowledgment_timestamp == datetime(
            2025, 1, 7, 12, 0, 0, tzinfo=timezone.utc
        )
        assert sample_acknowledgment.response_choice == ResponseChoice.CORRECTIVE

    def test_acknowledgment_event_is_frozen(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test that acknowledgment event payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_acknowledgment.acknowledged_by = "other"  # type: ignore[misc]

    def test_acknowledgment_event_equality(self) -> None:
        """Test equality comparison between acknowledgment events."""
        timestamp = datetime(2025, 1, 7, 12, 0, 0, tzinfo=timezone.utc)
        ack_id = uuid4()
        breach_id = uuid4()

        event1 = BreachAcknowledgedEventPayload(
            acknowledgment_id=ack_id,
            breach_id=breach_id,
            acknowledged_by="keeper:bob",
            acknowledgment_timestamp=timestamp,
            response_choice=ResponseChoice.DISMISS,
        )

        event2 = BreachAcknowledgedEventPayload(
            acknowledgment_id=ack_id,
            breach_id=breach_id,
            acknowledged_by="keeper:bob",
            acknowledgment_timestamp=timestamp,
            response_choice=ResponseChoice.DISMISS,
        )

        assert event1 == event2

    def test_signable_content_returns_bytes(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test that signable_content() returns bytes (CT-12)."""
        content = sample_acknowledgment.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_valid_json(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test that signable_content() is valid JSON."""
        content = sample_acknowledgment.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_signable_content_deterministic(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test that signable_content() produces identical output on repeated calls (CT-12)."""
        content1 = sample_acknowledgment.signable_content()
        content2 = sample_acknowledgment.signable_content()
        assert content1 == content2

    def test_signable_content_sorted_keys(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test that signable_content() uses sorted keys for determinism."""
        content = sample_acknowledgment.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_signable_content_contains_all_fields(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test that signable_content() includes all required fields."""
        content = sample_acknowledgment.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert "acknowledgment_id" in parsed
        assert "breach_id" in parsed
        assert "acknowledged_by" in parsed
        assert "acknowledgment_timestamp" in parsed
        assert "response_choice" in parsed

    def test_signable_content_response_choice_as_value(
        self, sample_acknowledgment: BreachAcknowledgedEventPayload
    ) -> None:
        """Test that response_choice is serialized as its value."""
        content = sample_acknowledgment.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert parsed["response_choice"] == "corrective"

    def test_all_response_choices(self) -> None:
        """Test acknowledgment events with all response choices."""
        base_args = {
            "acknowledgment_id": uuid4(),
            "breach_id": uuid4(),
            "acknowledged_by": "keeper:test",
            "acknowledgment_timestamp": datetime.now(timezone.utc),
        }

        for choice in ResponseChoice:
            event = BreachAcknowledgedEventPayload(response_choice=choice, **base_args)
            assert event.response_choice == choice

            # Verify serialization works
            content = event.signable_content()
            parsed = json.loads(content.decode("utf-8"))
            assert parsed["response_choice"] == choice.value
