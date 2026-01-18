"""Unit tests for cessation event payloads (Story 6.3, FR32).

Tests cover:
- CessationConsiderationEventPayload creation and serialization
- CessationDecisionEventPayload creation and serialization
- CessationDecision enum values
- to_dict() and signable_content() methods
- Payload immutability (frozen dataclass)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.cessation import (
    CESSATION_CONSIDERATION_EVENT_TYPE,
    CESSATION_DECISION_EVENT_TYPE,
    CessationConsiderationEventPayload,
    CessationDecision,
    CessationDecisionEventPayload,
)


class TestCessationDecisionEnum:
    """Tests for CessationDecision enum."""

    def test_proceed_to_vote_value(self) -> None:
        """Test PROCEED_TO_VOTE has correct string value."""
        assert CessationDecision.PROCEED_TO_VOTE.value == "proceed_to_vote"

    def test_dismiss_consideration_value(self) -> None:
        """Test DISMISS_CONSIDERATION has correct string value."""
        assert CessationDecision.DISMISS_CONSIDERATION.value == "dismiss"

    def test_defer_review_value(self) -> None:
        """Test DEFER_REVIEW has correct string value."""
        assert CessationDecision.DEFER_REVIEW.value == "defer"

    def test_enum_is_string_subclass(self) -> None:
        """Test enum values can be used as strings."""
        assert isinstance(CessationDecision.PROCEED_TO_VOTE, str)
        assert CessationDecision.PROCEED_TO_VOTE == "proceed_to_vote"

    def test_all_expected_values_exist(self) -> None:
        """Test all expected decision choices are present."""
        expected = {"proceed_to_vote", "dismiss", "defer"}
        actual = {d.value for d in CessationDecision}
        assert actual == expected


class TestCessationConsiderationEventPayload:
    """Tests for CessationConsiderationEventPayload."""

    @pytest.fixture
    def sample_payload(self) -> CessationConsiderationEventPayload:
        """Create a sample payload for testing."""
        return CessationConsiderationEventPayload(
            consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
            trigger_timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            breach_count=11,
            window_days=90,
            unacknowledged_breach_ids=(
                UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            ),
            agenda_placement_reason="FR32: >10 unacknowledged breaches in 90 days",
        )

    def test_creation_with_required_fields(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test payload creation with all required fields."""
        assert sample_payload.consideration_id == UUID(
            "12345678-1234-5678-1234-567812345678"
        )
        assert sample_payload.trigger_timestamp == datetime(
            2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc
        )
        assert sample_payload.breach_count == 11
        assert sample_payload.window_days == 90
        assert len(sample_payload.unacknowledged_breach_ids) == 2
        assert sample_payload.agenda_placement_reason == (
            "FR32: >10 unacknowledged breaches in 90 days"
        )

    def test_to_dict_returns_dict(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test to_dict() returns a dict (not bytes)."""
        result = sample_payload.to_dict()
        assert isinstance(result, dict)
        assert not isinstance(result, bytes)

    def test_to_dict_contains_all_fields(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test to_dict() contains all expected fields."""
        result = sample_payload.to_dict()
        expected_keys = {
            "consideration_id",
            "trigger_timestamp",
            "breach_count",
            "window_days",
            "unacknowledged_breach_ids",
            "agenda_placement_reason",
        }
        assert set(result.keys()) == expected_keys

    def test_to_dict_serializes_uuids_as_strings(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test UUIDs are serialized as strings in to_dict()."""
        result = sample_payload.to_dict()
        assert result["consideration_id"] == "12345678-1234-5678-1234-567812345678"
        assert isinstance(result["unacknowledged_breach_ids"], list)
        assert all(isinstance(bid, str) for bid in result["unacknowledged_breach_ids"])

    def test_to_dict_serializes_datetime_as_isoformat(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test datetime is serialized as ISO format string."""
        result = sample_payload.to_dict()
        assert result["trigger_timestamp"] == "2026-01-08T12:00:00+00:00"

    def test_signable_content_returns_bytes(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test signable_content() returns bytes."""
        result = sample_payload.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test signable_content() returns same bytes for same data."""
        result1 = sample_payload.signable_content()
        result2 = sample_payload.signable_content()
        assert result1 == result2

    def test_signable_content_is_valid_json(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test signable_content() produces valid JSON."""
        result = sample_payload.signable_content()
        parsed = json.loads(result.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_payload_is_frozen(
        self, sample_payload: CessationConsiderationEventPayload
    ) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.breach_count = 15  # type: ignore[misc]

    def test_payload_equality(self) -> None:
        """Test payload equality based on content."""
        payload1 = CessationConsiderationEventPayload(
            consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
            trigger_timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            breach_count=11,
            window_days=90,
            unacknowledged_breach_ids=(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),),
            agenda_placement_reason="FR32: >10 unacknowledged breaches in 90 days",
        )
        payload2 = CessationConsiderationEventPayload(
            consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
            trigger_timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            breach_count=11,
            window_days=90,
            unacknowledged_breach_ids=(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),),
            agenda_placement_reason="FR32: >10 unacknowledged breaches in 90 days",
        )
        assert payload1 == payload2


class TestCessationDecisionEventPayload:
    """Tests for CessationDecisionEventPayload."""

    @pytest.fixture
    def sample_decision_payload(self) -> CessationDecisionEventPayload:
        """Create a sample decision payload for testing."""
        return CessationDecisionEventPayload(
            decision_id=UUID("99999999-9999-9999-9999-999999999999"),
            consideration_id=UUID("12345678-1234-5678-1234-567812345678"),
            decision=CessationDecision.DISMISS_CONSIDERATION,
            decision_timestamp=datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
            decided_by="Conclave Session 42",
            rationale="Breaches addressed through corrective actions",
        )

    def test_creation_with_required_fields(
        self, sample_decision_payload: CessationDecisionEventPayload
    ) -> None:
        """Test decision payload creation with all required fields."""
        assert sample_decision_payload.decision_id == UUID(
            "99999999-9999-9999-9999-999999999999"
        )
        assert sample_decision_payload.consideration_id == UUID(
            "12345678-1234-5678-1234-567812345678"
        )
        assert (
            sample_decision_payload.decision == CessationDecision.DISMISS_CONSIDERATION
        )
        assert sample_decision_payload.decided_by == "Conclave Session 42"
        assert (
            sample_decision_payload.rationale
            == "Breaches addressed through corrective actions"
        )

    def test_to_dict_returns_dict(
        self, sample_decision_payload: CessationDecisionEventPayload
    ) -> None:
        """Test to_dict() returns a dict."""
        result = sample_decision_payload.to_dict()
        assert isinstance(result, dict)
        assert not isinstance(result, bytes)

    def test_to_dict_contains_all_fields(
        self, sample_decision_payload: CessationDecisionEventPayload
    ) -> None:
        """Test to_dict() contains all expected fields."""
        result = sample_decision_payload.to_dict()
        expected_keys = {
            "decision_id",
            "consideration_id",
            "decision",
            "decision_timestamp",
            "decided_by",
            "rationale",
        }
        assert set(result.keys()) == expected_keys

    def test_to_dict_serializes_enum_as_string(
        self, sample_decision_payload: CessationDecisionEventPayload
    ) -> None:
        """Test decision enum is serialized as string value."""
        result = sample_decision_payload.to_dict()
        assert result["decision"] == "dismiss"

    def test_signable_content_returns_bytes(
        self, sample_decision_payload: CessationDecisionEventPayload
    ) -> None:
        """Test signable_content() returns bytes."""
        result = sample_decision_payload.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(
        self, sample_decision_payload: CessationDecisionEventPayload
    ) -> None:
        """Test signable_content() returns same bytes for same data."""
        result1 = sample_decision_payload.signable_content()
        result2 = sample_decision_payload.signable_content()
        assert result1 == result2

    def test_decision_payload_is_frozen(
        self, sample_decision_payload: CessationDecisionEventPayload
    ) -> None:
        """Test decision payload is immutable."""
        with pytest.raises(AttributeError):
            sample_decision_payload.rationale = "New rationale"  # type: ignore[misc]

    def test_all_decision_types_can_be_used(self) -> None:
        """Test all CessationDecision values work in payload."""
        for decision in CessationDecision:
            payload = CessationDecisionEventPayload(
                decision_id=uuid4(),
                consideration_id=uuid4(),
                decision=decision,
                decision_timestamp=datetime.now(timezone.utc),
                decided_by="Test",
                rationale="Test rationale",
            )
            assert payload.decision == decision
            assert payload.to_dict()["decision"] == decision.value


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_consideration_event_type(self) -> None:
        """Test cessation consideration event type constant."""
        assert CESSATION_CONSIDERATION_EVENT_TYPE == "cessation.consideration"

    def test_decision_event_type(self) -> None:
        """Test cessation decision event type constant."""
        assert CESSATION_DECISION_EVENT_TYPE == "cessation.decision"
