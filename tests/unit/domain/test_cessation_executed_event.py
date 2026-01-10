"""Unit tests for CessationExecutedEventPayload (Story 7.3, FR40, NFR40).

Tests for:
- Event payload creation and immutability
- is_terminal always True enforcement
- signable_content() determinism
- to_dict() serialization
- Factory method behavior
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.cessation_executed import (
    CESSATION_EXECUTED_EVENT_TYPE,
    CessationExecutedEventPayload,
)


class TestCessationExecutedEventType:
    """Tests for the event type constant."""

    def test_event_type_is_cessation_executed(self) -> None:
        """Event type should be 'cessation.executed'."""
        assert CESSATION_EXECUTED_EVENT_TYPE == "cessation.executed"

    def test_event_type_is_string(self) -> None:
        """Event type should be a string."""
        assert isinstance(CESSATION_EXECUTED_EVENT_TYPE, str)


class TestCessationExecutedEventPayloadCreation:
    """Tests for payload creation."""

    def test_create_valid_payload(self) -> None:
        """Should create payload with all required fields."""
        cessation_id = uuid4()
        execution_timestamp = datetime.now(timezone.utc)
        triggering_event_id = uuid4()

        payload = CessationExecutedEventPayload(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            is_terminal=True,
            final_sequence_number=42,
            final_hash="abc123" * 10 + "abcd",
            reason="Constitutional threshold exceeded (FR37)",
            triggering_event_id=triggering_event_id,
        )

        assert payload.cessation_id == cessation_id
        assert payload.execution_timestamp == execution_timestamp
        assert payload.is_terminal is True
        assert payload.final_sequence_number == 42
        assert payload.final_hash == "abc123" * 10 + "abcd"
        assert payload.reason == "Constitutional threshold exceeded (FR37)"
        assert payload.triggering_event_id == triggering_event_id

    def test_create_via_factory_method(self) -> None:
        """Factory method should create payload with is_terminal=True."""
        cessation_id = uuid4()
        execution_timestamp = datetime.now(timezone.utc)
        triggering_event_id = uuid4()

        payload = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            final_sequence_number=100,
            final_hash="deadbeef" * 8,
            reason="External observer petition (FR39)",
            triggering_event_id=triggering_event_id,
        )

        assert payload.is_terminal is True
        assert payload.cessation_id == cessation_id

    def test_factory_method_does_not_expose_is_terminal_param(self) -> None:
        """Factory method signature should not include is_terminal."""
        # Verify by checking the method works without is_terminal
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="a" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )
        assert payload.is_terminal is True


class TestIsTerminalEnforcement:
    """Tests for NFR40 is_terminal enforcement."""

    def test_is_terminal_must_be_true(self) -> None:
        """Creating payload with is_terminal=False should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CessationExecutedEventPayload(
                cessation_id=uuid4(),
                execution_timestamp=datetime.now(timezone.utc),
                is_terminal=False,  # INVALID - NFR40 violation
                final_sequence_number=1,
                final_hash="a" * 64,
                reason="Test",
                triggering_event_id=uuid4(),
            )

        assert "NFR40" in str(exc_info.value)
        assert "is_terminal must be True" in str(exc_info.value)

    def test_is_terminal_always_true_via_factory(self) -> None:
        """Factory method always sets is_terminal=True."""
        for _ in range(10):  # Multiple creations
            payload = CessationExecutedEventPayload.create(
                cessation_id=uuid4(),
                execution_timestamp=datetime.now(timezone.utc),
                final_sequence_number=1,
                final_hash="b" * 64,
                reason="Test",
                triggering_event_id=uuid4(),
            )
            assert payload.is_terminal is True


class TestPayloadImmutability:
    """Tests for frozen dataclass immutability."""

    def test_payload_is_frozen(self) -> None:
        """Should not be able to modify payload after creation."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="c" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        with pytest.raises(AttributeError):
            payload.is_terminal = False  # type: ignore[misc]

    def test_cannot_modify_reason(self) -> None:
        """Should not be able to modify reason after creation."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="d" * 64,
            reason="Original",
            triggering_event_id=uuid4(),
        )

        with pytest.raises(AttributeError):
            payload.reason = "Modified"  # type: ignore[misc]

    def test_cannot_modify_final_sequence_number(self) -> None:
        """Should not be able to modify final_sequence_number after creation."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="e" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        with pytest.raises(AttributeError):
            payload.final_sequence_number = 999  # type: ignore[misc]


class TestSignableContent:
    """Tests for signable_content() method (CT-12)."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content() should return bytes."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="f" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        result = payload.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Same payload should produce same signable_content()."""
        cessation_id = UUID("12345678-1234-5678-1234-567812345678")
        execution_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        triggering_event_id = UUID("87654321-4321-8765-4321-876543218765")

        payload1 = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            final_sequence_number=42,
            final_hash="g" * 64,
            reason="Test reason",
            triggering_event_id=triggering_event_id,
        )

        payload2 = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            final_sequence_number=42,
            final_hash="g" * 64,
            reason="Test reason",
            triggering_event_id=triggering_event_id,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_includes_is_terminal(self) -> None:
        """signable_content() should include is_terminal field."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="h" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        content_str = payload.signable_content().decode("utf-8")
        content_dict = json.loads(content_str)

        assert "is_terminal" in content_dict
        assert content_dict["is_terminal"] is True

    def test_signable_content_has_sorted_keys(self) -> None:
        """signable_content() should have sorted keys for determinism."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="i" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        content_str = payload.signable_content().decode("utf-8")
        content_dict = json.loads(content_str)

        keys = list(content_dict.keys())
        assert keys == sorted(keys)

    def test_signable_content_includes_all_fields(self) -> None:
        """signable_content() should include all payload fields."""
        cessation_id = uuid4()
        triggering_event_id = uuid4()

        payload = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=42,
            final_hash="j" * 64,
            reason="Complete test",
            triggering_event_id=triggering_event_id,
        )

        content_str = payload.signable_content().decode("utf-8")
        content_dict = json.loads(content_str)

        expected_keys = {
            "cessation_id",
            "execution_timestamp",
            "is_terminal",
            "final_sequence_number",
            "final_hash",
            "reason",
            "triggering_event_id",
        }
        assert set(content_dict.keys()) == expected_keys


class TestToDict:
    """Tests for to_dict() serialization method."""

    def test_to_dict_returns_dict(self) -> None:
        """to_dict() should return a dictionary."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="k" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        result = payload.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict() should include all payload fields."""
        cessation_id = uuid4()
        execution_timestamp = datetime.now(timezone.utc)
        triggering_event_id = uuid4()

        payload = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            final_sequence_number=42,
            final_hash="l" * 64,
            reason="Dict test",
            triggering_event_id=triggering_event_id,
        )

        result = payload.to_dict()

        assert result["cessation_id"] == str(cessation_id)
        assert result["execution_timestamp"] == execution_timestamp.isoformat()
        assert result["is_terminal"] is True
        assert result["final_sequence_number"] == 42
        assert result["final_hash"] == "l" * 64
        assert result["reason"] == "Dict test"
        assert result["triggering_event_id"] == str(triggering_event_id)

    def test_to_dict_uuid_as_string(self) -> None:
        """to_dict() should convert UUIDs to strings."""
        cessation_id = uuid4()
        triggering_event_id = uuid4()

        payload = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="m" * 64,
            reason="Test",
            triggering_event_id=triggering_event_id,
        )

        result = payload.to_dict()

        assert isinstance(result["cessation_id"], str)
        assert isinstance(result["triggering_event_id"], str)

    def test_to_dict_timestamp_as_iso_string(self) -> None:
        """to_dict() should convert datetime to ISO format string."""
        execution_timestamp = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=execution_timestamp,
            final_sequence_number=1,
            final_hash="n" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        result = payload.to_dict()

        assert isinstance(result["execution_timestamp"], str)
        assert "2024-06-15" in result["execution_timestamp"]


class TestPayloadEquality:
    """Tests for payload equality (dataclass eq=True)."""

    def test_equal_payloads_are_equal(self) -> None:
        """Two payloads with same values should be equal."""
        cessation_id = uuid4()
        execution_timestamp = datetime.now(timezone.utc)
        triggering_event_id = uuid4()

        payload1 = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            final_sequence_number=42,
            final_hash="o" * 64,
            reason="Test",
            triggering_event_id=triggering_event_id,
        )

        payload2 = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            final_sequence_number=42,
            final_hash="o" * 64,
            reason="Test",
            triggering_event_id=triggering_event_id,
        )

        assert payload1 == payload2

    def test_different_payloads_are_not_equal(self) -> None:
        """Two payloads with different values should not be equal."""
        payload1 = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="p" * 64,
            reason="Test 1",
            triggering_event_id=uuid4(),
        )

        payload2 = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),  # Different ID
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="p" * 64,
            reason="Test 1",
            triggering_event_id=uuid4(),
        )

        assert payload1 != payload2

    def test_payload_hashable(self) -> None:
        """Frozen dataclass should be hashable."""
        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=1,
            final_hash="q" * 64,
            reason="Test",
            triggering_event_id=uuid4(),
        )

        # Should not raise
        _ = hash(payload)

        # Should work in sets
        payload_set = {payload}
        assert payload in payload_set
