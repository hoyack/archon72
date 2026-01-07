"""Unit tests for RecoveryCompletedEvent payload (Story 3.6, FR21, FR22).

Tests that the event payload:
- Contains all required fields for AC4
- Is immutable (frozen dataclass)
- Provides signable content for witnessing
- References the unanimous Keeper ceremony (FR22)
"""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.recovery_completed import (
    RECOVERY_COMPLETED_EVENT_TYPE,
    RecoveryCompletedPayload,
)


class TestEventTypeConstant:
    """Tests for RECOVERY_COMPLETED_EVENT_TYPE constant."""

    def test_event_type_follows_naming_convention(self) -> None:
        """Event type follows project naming convention."""
        assert RECOVERY_COMPLETED_EVENT_TYPE == "recovery.completed"


class TestRecoveryCompletedPayload:
    """Tests for RecoveryCompletedPayload dataclass."""

    def test_payload_has_required_fields(self) -> None:
        """Payload contains all fields required by AC4."""
        crisis_id = uuid4()
        ceremony_id = uuid4()
        started = datetime.now(timezone.utc) - timedelta(hours=48)
        completed = datetime.now(timezone.utc)
        keepers = ("keeper-001", "keeper-002", "keeper-003")

        payload = RecoveryCompletedPayload(
            crisis_event_id=crisis_id,
            waiting_period_started_at=started,
            recovery_completed_at=completed,
            keeper_ceremony_id=ceremony_id,
            approving_keepers=keepers,
        )

        assert payload.crisis_event_id == crisis_id
        assert payload.waiting_period_started_at == started
        assert payload.recovery_completed_at == completed
        assert payload.keeper_ceremony_id == ceremony_id
        assert payload.approving_keepers == keepers

    def test_payload_is_frozen(self) -> None:
        """Payload is immutable (frozen dataclass)."""
        payload = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),
            waiting_period_started_at=datetime.now(timezone.utc) - timedelta(hours=48),
            recovery_completed_at=datetime.now(timezone.utc),
            keeper_ceremony_id=uuid4(),
            approving_keepers=("keeper-001", "keeper-002"),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            payload.crisis_event_id = uuid4()  # type: ignore

    def test_keepers_converted_to_tuple(self) -> None:
        """List of keepers is converted to tuple."""
        keepers_list = ["keeper-001", "keeper-002"]  # type: ignore
        payload = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),
            waiting_period_started_at=datetime.now(timezone.utc) - timedelta(hours=48),
            recovery_completed_at=datetime.now(timezone.utc),
            keeper_ceremony_id=uuid4(),
            approving_keepers=keepers_list,  # type: ignore
        )

        assert isinstance(payload.approving_keepers, tuple)


class TestSignableContent:
    """Tests for signable_content() method."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content returns UTF-8 encoded bytes."""
        payload = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),
            waiting_period_started_at=datetime.now(timezone.utc) - timedelta(hours=48),
            recovery_completed_at=datetime.now(timezone.utc),
            keeper_ceremony_id=uuid4(),
            approving_keepers=("keeper-001", "keeper-002"),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_valid_json(self) -> None:
        """signable_content is valid JSON when decoded."""
        payload = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),
            waiting_period_started_at=datetime.now(timezone.utc) - timedelta(hours=48),
            recovery_completed_at=datetime.now(timezone.utc),
            keeper_ceremony_id=uuid4(),
            approving_keepers=("keeper-001", "keeper-002"),
        )

        content = payload.signable_content()
        decoded = json.loads(content.decode("utf-8"))

        assert decoded["event_type"] == "RecoveryCompletedEvent"
        assert "crisis_event_id" in decoded
        assert "waiting_period_started_at" in decoded
        assert "recovery_completed_at" in decoded
        assert "keeper_ceremony_id" in decoded
        assert "approving_keepers" in decoded

    def test_signable_content_is_deterministic(self) -> None:
        """Same payload produces same signable content."""
        crisis_id = uuid4()
        ceremony_id = uuid4()
        started = datetime(2025, 12, 25, 10, 0, 0, tzinfo=timezone.utc)
        completed = datetime(2025, 12, 27, 10, 0, 0, tzinfo=timezone.utc)

        payload1 = RecoveryCompletedPayload(
            crisis_event_id=crisis_id,
            waiting_period_started_at=started,
            recovery_completed_at=completed,
            keeper_ceremony_id=ceremony_id,
            approving_keepers=("keeper-001", "keeper-002"),
        )

        payload2 = RecoveryCompletedPayload(
            crisis_event_id=crisis_id,
            waiting_period_started_at=started,
            recovery_completed_at=completed,
            keeper_ceremony_id=ceremony_id,
            approving_keepers=("keeper-001", "keeper-002"),
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_differs_with_different_values(self) -> None:
        """Different payloads produce different signable content."""
        started = datetime.now(timezone.utc) - timedelta(hours=48)
        completed = datetime.now(timezone.utc)

        payload1 = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),
            waiting_period_started_at=started,
            recovery_completed_at=completed,
            keeper_ceremony_id=uuid4(),
            approving_keepers=("keeper-001", "keeper-002"),
        )

        payload2 = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),  # Different crisis_event_id
            waiting_period_started_at=started,
            recovery_completed_at=completed,
            keeper_ceremony_id=uuid4(),  # Different ceremony_id
            approving_keepers=("keeper-001", "keeper-002"),
        )

        assert payload1.signable_content() != payload2.signable_content()


class TestCeremonyReference:
    """Tests verifying FR22 ceremony reference."""

    def test_payload_references_keeper_ceremony(self) -> None:
        """Payload must reference the unanimous Keeper ceremony (FR22)."""
        ceremony_id = uuid4()
        payload = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),
            waiting_period_started_at=datetime.now(timezone.utc) - timedelta(hours=48),
            recovery_completed_at=datetime.now(timezone.utc),
            keeper_ceremony_id=ceremony_id,
            approving_keepers=("keeper-001", "keeper-002"),
        )

        assert payload.keeper_ceremony_id == ceremony_id

    def test_payload_includes_approving_keepers(self) -> None:
        """Payload includes list of Keepers who approved recovery."""
        keepers = ("keeper-001", "keeper-002", "keeper-003")
        payload = RecoveryCompletedPayload(
            crisis_event_id=uuid4(),
            waiting_period_started_at=datetime.now(timezone.utc) - timedelta(hours=48),
            recovery_completed_at=datetime.now(timezone.utc),
            keeper_ceremony_id=uuid4(),
            approving_keepers=keepers,
        )

        assert len(payload.approving_keepers) == 3
        assert payload.approving_keepers == keepers
