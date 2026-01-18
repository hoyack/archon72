"""Unit tests for RecoveryWaitingPeriodStartedEvent payload (Story 3.6, FR21).

Tests that the event payload:
- Contains all required fields for AC1
- Is immutable (frozen dataclass)
- Provides signable content for witnessing
"""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.recovery_waiting_period_started import (
    RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE,
    RecoveryWaitingPeriodStartedPayload,
)


class TestEventTypeConstant:
    """Tests for RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE constant."""

    def test_event_type_follows_naming_convention(self) -> None:
        """Event type follows project naming convention."""
        assert (
            RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE
            == "recovery.waiting_period_started"
        )


class TestRecoveryWaitingPeriodStartedPayload:
    """Tests for RecoveryWaitingPeriodStartedPayload dataclass."""

    def test_payload_has_required_fields(self) -> None:
        """Payload contains all fields required by AC1."""
        crisis_id = uuid4()
        started = datetime.now(timezone.utc)
        ends = started + timedelta(hours=48)
        keepers = ("keeper-001", "keeper-002")

        payload = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=crisis_id,
            started_at=started,
            ends_at=ends,
            initiated_by_keepers=keepers,
            public_notification_sent=True,
        )

        assert payload.crisis_event_id == crisis_id
        assert payload.started_at == started
        assert payload.ends_at == ends
        assert payload.initiated_by_keepers == keepers
        assert payload.public_notification_sent is True

    def test_payload_is_frozen(self) -> None:
        """Payload is immutable (frozen dataclass)."""
        payload = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=48),
            initiated_by_keepers=("keeper-001",),
            public_notification_sent=False,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            payload.crisis_event_id = uuid4()  # type: ignore

    def test_keepers_converted_to_tuple(self) -> None:
        """List of keepers is converted to tuple."""
        keepers_list = ["keeper-001", "keeper-002"]  # type: ignore
        payload = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=48),
            initiated_by_keepers=keepers_list,  # type: ignore
            public_notification_sent=True,
        )

        assert isinstance(payload.initiated_by_keepers, tuple)


class TestSignableContent:
    """Tests for signable_content() method."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content returns UTF-8 encoded bytes."""
        payload = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=48),
            initiated_by_keepers=("keeper-001",),
            public_notification_sent=True,
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_valid_json(self) -> None:
        """signable_content is valid JSON when decoded."""
        payload = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=48),
            initiated_by_keepers=("keeper-001", "keeper-002"),
            public_notification_sent=True,
        )

        content = payload.signable_content()
        decoded = json.loads(content.decode("utf-8"))

        assert decoded["event_type"] == "RecoveryWaitingPeriodStartedEvent"
        assert "crisis_event_id" in decoded
        assert "started_at" in decoded
        assert "ends_at" in decoded
        assert "initiated_by_keepers" in decoded
        assert "public_notification_sent" in decoded

    def test_signable_content_is_deterministic(self) -> None:
        """Same payload produces same signable content."""
        crisis_id = uuid4()
        started = datetime(2025, 12, 27, 10, 0, 0, tzinfo=timezone.utc)
        ends = started + timedelta(hours=48)

        payload1 = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=crisis_id,
            started_at=started,
            ends_at=ends,
            initiated_by_keepers=("keeper-001", "keeper-002"),
            public_notification_sent=True,
        )

        payload2 = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=crisis_id,
            started_at=started,
            ends_at=ends,
            initiated_by_keepers=("keeper-001", "keeper-002"),
            public_notification_sent=True,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_differs_with_different_values(self) -> None:
        """Different payloads produce different signable content."""
        started = datetime.now(timezone.utc)
        ends = started + timedelta(hours=48)

        payload1 = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=uuid4(),
            started_at=started,
            ends_at=ends,
            initiated_by_keepers=("keeper-001",),
            public_notification_sent=True,
        )

        payload2 = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=uuid4(),  # Different crisis_event_id
            started_at=started,
            ends_at=ends,
            initiated_by_keepers=("keeper-001",),
            public_notification_sent=True,
        )

        assert payload1.signable_content() != payload2.signable_content()
