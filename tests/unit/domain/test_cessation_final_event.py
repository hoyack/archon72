"""Unit tests for CessationExecutedEventPayload FR43 compliance (Story 7.6).

Tests for:
- FR43 AC2: All required payload fields present
- is_terminal is always True
- signable_content() is deterministic
- Aliases for API-friendly field names
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.cessation_executed import (
    CESSATION_EXECUTED_EVENT_TYPE,
    CessationExecutedEventPayload,
)


class TestFR43RequiredFields:
    """Tests for FR43 AC2: Required payload fields."""

    def test_payload_includes_trigger_reason(self) -> None:
        """Payload should include trigger_reason (alias for reason)."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Constitutional threshold exceeded",
            triggering_event_id=uuid4(),
        )

        assert payload.trigger_reason == "Constitutional threshold exceeded"

    def test_payload_includes_trigger_source(self) -> None:
        """Payload should include trigger_source (alias for triggering_event_id)."""
        trigger_id = uuid4()
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test reason",
            triggering_event_id=trigger_id,
        )

        assert payload.trigger_source == trigger_id

    def test_payload_includes_final_sequence(self) -> None:
        """Payload should include final_sequence (alias for final_sequence_number)."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=42,
            final_hash="a" * 64,
            reason="Test reason",
            triggering_event_id=uuid4(),
        )

        assert payload.final_sequence == 42

    def test_payload_includes_final_hash(self) -> None:
        """Payload should include final_hash."""
        hash_value = "b" * 64
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash=hash_value,
            reason="Test reason",
            triggering_event_id=uuid4(),
        )

        assert payload.final_hash == hash_value

    def test_payload_includes_is_terminal(self) -> None:
        """Payload should include is_terminal (always True)."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test reason",
            triggering_event_id=uuid4(),
        )

        assert payload.is_terminal is True

    def test_payload_includes_cessation_id(self) -> None:
        """Payload should include cessation_id."""
        cessation_id = uuid4()
        payload = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test reason",
            triggering_event_id=uuid4(),
        )

        assert payload.cessation_id == cessation_id

    def test_payload_includes_execution_timestamp(self) -> None:
        """Payload should include execution_timestamp."""
        timestamp = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=timestamp,
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test reason",
            triggering_event_id=uuid4(),
        )

        assert payload.execution_timestamp == timestamp


class TestIsTerminalAlwaysTrue:
    """Tests for NFR40: is_terminal must always be True."""

    def test_is_terminal_true_via_factory(self) -> None:
        """Factory method should set is_terminal to True."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        assert payload.is_terminal is True

    def test_is_terminal_true_via_constructor(self) -> None:
        """Direct construction with is_terminal=True should succeed."""
        payload = CessationExecutedEventPayload(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            is_terminal=True,
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        assert payload.is_terminal is True

    def test_is_terminal_false_raises_error(self) -> None:
        """Creating with is_terminal=False should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CessationExecutedEventPayload(
                cessation_id=uuid4(),
                execution_timestamp=datetime.now(timezone.utc),
                is_terminal=False,  # Invalid!
                final_sequence_number=100,
                final_hash="a" * 64,
                reason="Test",
                triggering_event_id=uuid4(),
            )

        assert "NFR40" in str(exc_info.value)
        assert "is_terminal must be True" in str(exc_info.value)

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable (frozen dataclass)."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            payload.is_terminal = False  # type: ignore


class TestSignableContentDeterministic:
    """Tests for CT-12: signable_content() must be deterministic."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content() should return bytes."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        result = payload.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_valid_json(self) -> None:
        """signable_content() should produce valid JSON."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_signable_content_deterministic_same_payload(self) -> None:
        """Same payload should produce same signable_content()."""
        cessation_id = uuid4()
        timestamp = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        trigger_id = uuid4()

        payload = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=timestamp,
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=trigger_id,
        )

        # Call multiple times
        content1 = payload.signable_content()
        content2 = payload.signable_content()
        content3 = payload.signable_content()

        assert content1 == content2 == content3

    def test_signable_content_includes_is_terminal(self) -> None:
        """signable_content() should include is_terminal field."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert "is_terminal" in parsed
        assert parsed["is_terminal"] is True

    def test_signable_content_has_sorted_keys(self) -> None:
        """signable_content() should have sorted keys for determinism."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())

        assert keys == sorted(keys)


class TestToDictAliases:
    """Tests for to_dict() including FR43 AC2 aliases."""

    def test_to_dict_includes_trigger_reason_alias(self) -> None:
        """to_dict() should include trigger_reason alias."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Constitutional threshold exceeded",
            triggering_event_id=uuid4(),
        )

        result = payload.to_dict()

        assert "trigger_reason" in result
        assert result["trigger_reason"] == "Constitutional threshold exceeded"
        # Also has canonical name
        assert result["reason"] == result["trigger_reason"]

    def test_to_dict_includes_trigger_source_alias(self) -> None:
        """to_dict() should include trigger_source alias."""
        trigger_id = uuid4()
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=trigger_id,
        )

        result = payload.to_dict()

        assert "trigger_source" in result
        assert result["trigger_source"] == str(trigger_id)
        # Also has canonical name
        assert result["triggering_event_id"] == result["trigger_source"]

    def test_to_dict_includes_final_sequence_alias(self) -> None:
        """to_dict() should include final_sequence alias."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=42,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        result = payload.to_dict()

        assert "final_sequence" in result
        assert result["final_sequence"] == 42
        # Also has canonical name
        assert result["final_sequence_number"] == result["final_sequence"]

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict() result should be JSON serializable."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        result = payload.to_dict()
        serialized = json.dumps(result)
        deserialized = json.loads(serialized)

        assert deserialized["is_terminal"] is True
        assert deserialized["final_sequence"] == 100


class TestEventTypeConstant:
    """Tests for CESSATION_EXECUTED_EVENT_TYPE constant."""

    def test_event_type_value(self) -> None:
        """Event type should be 'cessation.executed'."""
        assert CESSATION_EXECUTED_EVENT_TYPE == "cessation.executed"

    def test_event_type_is_string(self) -> None:
        """Event type should be a string."""
        assert isinstance(CESSATION_EXECUTED_EVENT_TYPE, str)
