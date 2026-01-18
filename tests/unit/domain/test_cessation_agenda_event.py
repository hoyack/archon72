"""Unit tests for CessationAgendaPlacementEvent domain event (Story 7.1).

This module tests the domain event payload for automatic agenda placement
triggers, including consecutive failures, rolling window, and anti-success sustained.

Constitutional Constraints:
- FR37: 3 consecutive integrity failures in 30 days triggers agenda placement
- FR38: Anti-success alert sustained 90 days triggers agenda placement
- RT-4: 5 non-consecutive failures in 90-day rolling window triggers agenda placement
- CT-12: Witnessing creates accountability -> signable_content() required
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.cessation_agenda import (
    CESSATION_AGENDA_PLACEMENT_EVENT_TYPE,
    AgendaTriggerType,
    CessationAgendaPlacementEventPayload,
)


class TestAgendaTriggerType:
    """Tests for AgendaTriggerType enum."""

    def test_consecutive_failures_value(self) -> None:
        """AgendaTriggerType.CONSECUTIVE_FAILURES has correct value."""
        assert AgendaTriggerType.CONSECUTIVE_FAILURES.value == "consecutive_failures"

    def test_rolling_window_value(self) -> None:
        """AgendaTriggerType.ROLLING_WINDOW has correct value."""
        assert AgendaTriggerType.ROLLING_WINDOW.value == "rolling_window"

    def test_anti_success_sustained_value(self) -> None:
        """AgendaTriggerType.ANTI_SUCCESS_SUSTAINED has correct value."""
        assert (
            AgendaTriggerType.ANTI_SUCCESS_SUSTAINED.value == "anti_success_sustained"
        )

    def test_all_trigger_types_exist(self) -> None:
        """All three trigger types are defined."""
        assert len(AgendaTriggerType) == 3


class TestCessationAgendaPlacementEventPayload:
    """Tests for CessationAgendaPlacementEventPayload."""

    @pytest.fixture
    def consecutive_failure_payload(self) -> CessationAgendaPlacementEventPayload:
        """Create a consecutive failure trigger payload."""
        return CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=(uuid4(), uuid4(), uuid4()),
            agenda_placement_reason="FR37: 3 consecutive integrity failures in 30 days",
        )

    @pytest.fixture
    def rolling_window_payload(self) -> CessationAgendaPlacementEventPayload:
        """Create a rolling window trigger payload (RT-4)."""
        return CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.ROLLING_WINDOW,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=5,
            window_days=90,
            consecutive=False,
            failure_event_ids=(uuid4(), uuid4(), uuid4(), uuid4(), uuid4()),
            agenda_placement_reason="RT-4: 5 integrity failures in 90-day rolling window",
        )

    @pytest.fixture
    def anti_success_payload(self) -> CessationAgendaPlacementEventPayload:
        """Create an anti-success sustained trigger payload."""
        return CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.ANTI_SUCCESS_SUSTAINED,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=0,
            window_days=90,
            consecutive=False,
            failure_event_ids=(),
            agenda_placement_reason="FR38: Anti-success alert sustained 90 days",
            sustained_days=90,
            first_alert_date=datetime(2025, 10, 1, tzinfo=timezone.utc),
            alert_event_ids=(uuid4(), uuid4()),
        )

    def test_event_type_constant(self) -> None:
        """Event type constant has correct value."""
        assert CESSATION_AGENDA_PLACEMENT_EVENT_TYPE == "cessation.agenda_placement"

    def test_payload_is_frozen(
        self, consecutive_failure_payload: CessationAgendaPlacementEventPayload
    ) -> None:
        """Payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            consecutive_failure_payload.failure_count = 5  # type: ignore[misc]

    def test_consecutive_failure_payload_attributes(self) -> None:
        """Consecutive failure payload has all required attributes."""
        placement_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        failure_ids = (uuid4(), uuid4(), uuid4())

        payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=timestamp,
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=failure_ids,
            agenda_placement_reason="FR37: 3 consecutive integrity failures in 30 days",
        )

        assert payload.placement_id == placement_id
        assert payload.trigger_type == AgendaTriggerType.CONSECUTIVE_FAILURES
        assert payload.trigger_timestamp == timestamp
        assert payload.failure_count == 3
        assert payload.window_days == 30
        assert payload.consecutive is True
        assert payload.failure_event_ids == failure_ids
        assert "FR37" in payload.agenda_placement_reason

    def test_rolling_window_payload_attributes(self) -> None:
        """Rolling window (RT-4) payload has all required attributes."""
        placement_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        failure_ids = tuple(uuid4() for _ in range(5))

        payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.ROLLING_WINDOW,
            trigger_timestamp=timestamp,
            failure_count=5,
            window_days=90,
            consecutive=False,
            failure_event_ids=failure_ids,
            agenda_placement_reason="RT-4: 5 integrity failures in 90-day rolling window",
        )

        assert payload.placement_id == placement_id
        assert payload.trigger_type == AgendaTriggerType.ROLLING_WINDOW
        assert payload.failure_count == 5
        assert payload.window_days == 90
        assert payload.consecutive is False
        assert len(payload.failure_event_ids) == 5
        assert "RT-4" in payload.agenda_placement_reason

    def test_anti_success_payload_attributes(self) -> None:
        """Anti-success sustained payload has all required attributes."""
        placement_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        first_alert = datetime(2025, 10, 1, tzinfo=timezone.utc)
        alert_ids = (uuid4(), uuid4())

        payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.ANTI_SUCCESS_SUSTAINED,
            trigger_timestamp=timestamp,
            failure_count=0,
            window_days=90,
            consecutive=False,
            failure_event_ids=(),
            agenda_placement_reason="FR38: Anti-success alert sustained 90 days",
            sustained_days=90,
            first_alert_date=first_alert,
            alert_event_ids=alert_ids,
        )

        assert payload.trigger_type == AgendaTriggerType.ANTI_SUCCESS_SUSTAINED
        assert payload.sustained_days == 90
        assert payload.first_alert_date == first_alert
        assert payload.alert_event_ids == alert_ids
        assert "FR38" in payload.agenda_placement_reason


class TestSignableContent:
    """Tests for signable_content() method (CT-12 compliance)."""

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content() returns bytes."""
        payload = CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=(uuid4(), uuid4(), uuid4()),
            agenda_placement_reason="FR37: test",
        )

        result = payload.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_deterministic(self) -> None:
        """signable_content() is deterministic for same payload."""
        placement_id = uuid4()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        failure_ids = (
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
            UUID("00000000-0000-0000-0000-000000000003"),
        )

        payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=timestamp,
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=failure_ids,
            agenda_placement_reason="FR37: test",
        )

        # Call multiple times
        result1 = payload.signable_content()
        result2 = payload.signable_content()
        result3 = payload.signable_content()

        assert result1 == result2 == result3

    def test_signable_content_includes_all_fields(self) -> None:
        """signable_content() includes all required fields."""
        placement_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        failure_ids = (uuid4(), uuid4(), uuid4())

        payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=timestamp,
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=failure_ids,
            agenda_placement_reason="FR37: test",
        )

        content = payload.signable_content()
        content_dict = json.loads(content.decode("utf-8"))

        # All critical fields must be present
        assert "placement_id" in content_dict
        assert "trigger_type" in content_dict
        assert "trigger_timestamp" in content_dict
        assert "failure_count" in content_dict
        assert "window_days" in content_dict
        assert "consecutive" in content_dict
        assert "failure_event_ids" in content_dict
        assert "agenda_placement_reason" in content_dict

    def test_signable_content_sorted_keys(self) -> None:
        """signable_content() uses sorted keys for determinism."""
        payload = CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=(uuid4(), uuid4(), uuid4()),
            agenda_placement_reason="FR37: test",
        )

        content = payload.signable_content()
        content_str = content.decode("utf-8")

        # Verify sorted order by checking key positions
        keys = list(json.loads(content_str).keys())
        assert keys == sorted(keys)

    def test_signable_content_different_payloads_differ(self) -> None:
        """Different payloads produce different signable content."""
        base_params = {
            "placement_id": uuid4(),
            "trigger_timestamp": datetime.now(timezone.utc),
            "failure_count": 3,
            "window_days": 30,
            "consecutive": True,
            "failure_event_ids": (uuid4(), uuid4(), uuid4()),
            "agenda_placement_reason": "FR37: test",
        }

        payload1 = CessationAgendaPlacementEventPayload(
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            **base_params,
        )

        payload2 = CessationAgendaPlacementEventPayload(
            trigger_type=AgendaTriggerType.ROLLING_WINDOW,
            **base_params,
        )

        assert payload1.signable_content() != payload2.signable_content()


class TestToDict:
    """Tests for to_dict() method."""

    def test_to_dict_returns_dict(self) -> None:
        """to_dict() returns a dictionary."""
        payload = CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=(uuid4(), uuid4(), uuid4()),
            agenda_placement_reason="FR37: test",
        )

        result = payload.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict() includes all required fields."""
        placement_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        failure_ids = (uuid4(), uuid4(), uuid4())

        payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=timestamp,
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=failure_ids,
            agenda_placement_reason="FR37: test",
        )

        result = payload.to_dict()

        assert result["placement_id"] == str(placement_id)
        assert result["trigger_type"] == "consecutive_failures"
        assert result["trigger_timestamp"] == timestamp.isoformat()
        assert result["failure_count"] == 3
        assert result["window_days"] == 30
        assert result["consecutive"] is True
        assert result["failure_event_ids"] == [str(fid) for fid in failure_ids]
        assert result["agenda_placement_reason"] == "FR37: test"

    def test_to_dict_with_anti_success_fields(self) -> None:
        """to_dict() includes anti-success specific fields when present."""
        first_alert = datetime(2025, 10, 1, tzinfo=timezone.utc)
        alert_ids = (uuid4(), uuid4())

        payload = CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.ANTI_SUCCESS_SUSTAINED,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=0,
            window_days=90,
            consecutive=False,
            failure_event_ids=(),
            agenda_placement_reason="FR38: test",
            sustained_days=90,
            first_alert_date=first_alert,
            alert_event_ids=alert_ids,
        )

        result = payload.to_dict()

        assert result["sustained_days"] == 90
        assert result["first_alert_date"] == first_alert.isoformat()
        assert result["alert_event_ids"] == [str(aid) for aid in alert_ids]

    def test_to_dict_serializable(self) -> None:
        """to_dict() result is JSON serializable."""
        payload = CessationAgendaPlacementEventPayload(
            placement_id=uuid4(),
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=datetime.now(timezone.utc),
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=(uuid4(), uuid4(), uuid4()),
            agenda_placement_reason="FR37: test",
        )

        result = payload.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)


class TestPayloadEquality:
    """Tests for payload equality (frozen dataclass)."""

    def test_equal_payloads(self) -> None:
        """Equal payloads are equal."""
        placement_id = uuid4()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        failure_ids = (uuid4(), uuid4(), uuid4())

        payload1 = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=timestamp,
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=failure_ids,
            agenda_placement_reason="FR37: test",
        )

        payload2 = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            trigger_timestamp=timestamp,
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=failure_ids,
            agenda_placement_reason="FR37: test",
        )

        assert payload1 == payload2

    def test_different_payloads_not_equal(self) -> None:
        """Different payloads are not equal."""
        base_params = {
            "placement_id": uuid4(),
            "trigger_timestamp": datetime.now(timezone.utc),
            "failure_count": 3,
            "window_days": 30,
            "consecutive": True,
            "failure_event_ids": (uuid4(), uuid4(), uuid4()),
            "agenda_placement_reason": "FR37: test",
        }

        payload1 = CessationAgendaPlacementEventPayload(
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            **base_params,
        )

        # Different placement_id
        payload2 = CessationAgendaPlacementEventPayload(
            trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
            placement_id=uuid4(),  # Different
            trigger_timestamp=base_params["trigger_timestamp"],
            failure_count=3,
            window_days=30,
            consecutive=True,
            failure_event_ids=base_params["failure_event_ids"],
            agenda_placement_reason="FR37: test",
        )

        assert payload1 != payload2
