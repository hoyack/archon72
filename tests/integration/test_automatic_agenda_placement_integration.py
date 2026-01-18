"""Integration tests for automatic agenda placement (Story 7.1, FR37-FR38, RT-4).

This module tests end-to-end automatic agenda placement scenarios:
- FR37: 3 consecutive integrity failures → agenda placement
- RT-4: 5 failures in 90-day rolling window → agenda placement (timing attack prevention)
- FR38: Anti-success alert sustained 90 days → agenda placement
- Full event flow with witnessing (CT-12)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.automatic_agenda_placement_service import (
    AGENDA_PLACEMENT_SYSTEM_AGENT_ID,
    AutomaticAgendaPlacementService,
)
from src.domain.events.cessation_agenda import (
    CESSATION_AGENDA_PLACEMENT_EVENT_TYPE,
    AgendaTriggerType,
)
from src.infrastructure.stubs.anti_success_alert_repository_stub import (
    AntiSuccessAlertRepositoryStub,
)
from src.infrastructure.stubs.cessation_agenda_repository_stub import (
    CessationAgendaRepositoryStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.integrity_failure_repository_stub import (
    IntegrityFailureRepositoryStub,
)


@pytest.fixture
def integration_setup() -> dict:
    """Set up all components for integration testing."""
    integrity_failure_repo = IntegrityFailureRepositoryStub()
    anti_success_repo = AntiSuccessAlertRepositoryStub()
    cessation_agenda_repo = CessationAgendaRepositoryStub()
    halt_checker = HaltCheckerStub()

    event_writer = AsyncMock()
    event_writer.write_event = AsyncMock(return_value=None)

    service = AutomaticAgendaPlacementService(
        integrity_failure_repo=integrity_failure_repo,
        anti_success_repo=anti_success_repo,
        cessation_agenda_repo=cessation_agenda_repo,
        event_writer=event_writer,
        halt_checker=halt_checker,
    )

    return {
        "service": service,
        "integrity_failure_repo": integrity_failure_repo,
        "anti_success_repo": anti_success_repo,
        "cessation_agenda_repo": cessation_agenda_repo,
        "event_writer": event_writer,
        "halt_checker": halt_checker,
    }


class TestConsecutiveFailureFlow:
    """End-to-end tests for FR37 consecutive failure trigger."""

    @pytest.mark.asyncio
    async def test_end_to_end_consecutive_failure_agenda_placement(
        self, integration_setup: dict
    ) -> None:
        """FR37: 3 consecutive failures in 30 days places cessation on agenda."""
        service = integration_setup["service"]
        integrity_repo = integration_setup["integrity_failure_repo"]
        agenda_repo = integration_setup["cessation_agenda_repo"]
        event_writer = integration_setup["event_writer"]

        now = datetime.now(timezone.utc)

        # Simulate 3 consecutive integrity failures
        integrity_repo.add_failure(
            uuid4(),
            now - timedelta(days=20),
            "hash_chain_verification_failed",
            "First hash chain mismatch detected",
        )
        integrity_repo.add_failure(
            uuid4(),
            now - timedelta(days=12),
            "signature_verification_failed",
            "Second signature verification failure",
        )
        integrity_repo.add_failure(
            uuid4(),
            now - timedelta(days=5),
            "witness_attestation_failed",
            "Third witness attestation failure",
        )

        # Trigger evaluation
        result = await service.check_consecutive_failures()

        # Verify trigger fired
        assert result.triggered is True
        assert result.trigger_type == AgendaTriggerType.CONSECUTIVE_FAILURES
        assert result.was_idempotent is False

        # Verify agenda placement was persisted
        placement = await agenda_repo.get_by_id(result.placement_id)
        assert placement is not None
        assert placement.trigger_type == AgendaTriggerType.CONSECUTIVE_FAILURES
        assert placement.failure_count == 3
        assert placement.window_days == 30
        assert placement.consecutive is True
        assert "FR37" in placement.agenda_placement_reason

        # Verify event was witnessed (CT-12)
        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == CESSATION_AGENDA_PLACEMENT_EVENT_TYPE
        assert call_kwargs["agent_id"] == AGENDA_PLACEMENT_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_successful_check_prevents_trigger(
        self, integration_setup: dict
    ) -> None:
        """A successful integrity check prevents consecutive failure trigger."""
        service = integration_setup["service"]
        integrity_repo = integration_setup["integrity_failure_repo"]

        now = datetime.now(timezone.utc)

        # 2 failures, successful check, 2 more failures
        integrity_repo.add_failure(uuid4(), now - timedelta(days=25))
        integrity_repo.add_failure(uuid4(), now - timedelta(days=20))

        # Successful check breaks sequence
        await integrity_repo.record_successful_check(now - timedelta(days=15))

        integrity_repo.add_failure(uuid4(), now - timedelta(days=10))
        integrity_repo.add_failure(uuid4(), now - timedelta(days=5))

        # Trigger evaluation
        result = await service.check_consecutive_failures()

        # Should not trigger - only 2 consecutive after successful check
        assert result.triggered is False


class TestRollingWindowFlow:
    """End-to-end tests for RT-4 rolling window trigger."""

    @pytest.mark.asyncio
    async def test_end_to_end_rolling_window_agenda_placement(
        self, integration_setup: dict
    ) -> None:
        """RT-4: 5 failures in 90-day window places cessation on agenda."""
        service = integration_setup["service"]
        integrity_repo = integration_setup["integrity_failure_repo"]
        agenda_repo = integration_setup["cessation_agenda_repo"]
        event_writer = integration_setup["event_writer"]

        now = datetime.now(timezone.utc)

        # Simulate 5 non-consecutive failures across 90 days
        # (with successful checks between them)
        integrity_repo.add_failure(uuid4(), now - timedelta(days=85))
        await integrity_repo.record_successful_check(now - timedelta(days=80))

        integrity_repo.add_failure(uuid4(), now - timedelta(days=70))
        await integrity_repo.record_successful_check(now - timedelta(days=65))

        integrity_repo.add_failure(uuid4(), now - timedelta(days=50))
        await integrity_repo.record_successful_check(now - timedelta(days=45))

        integrity_repo.add_failure(uuid4(), now - timedelta(days=30))
        await integrity_repo.record_successful_check(now - timedelta(days=25))

        integrity_repo.add_failure(uuid4(), now - timedelta(days=10))

        # Trigger evaluation
        result = await service.check_rolling_window_failures()

        # Verify trigger fired
        assert result.triggered is True
        assert result.trigger_type == AgendaTriggerType.ROLLING_WINDOW
        assert result.was_idempotent is False

        # Verify agenda placement was persisted
        placement = await agenda_repo.get_by_id(result.placement_id)
        assert placement is not None
        assert placement.trigger_type == AgendaTriggerType.ROLLING_WINDOW
        assert placement.failure_count >= 5
        assert placement.window_days == 90
        assert placement.consecutive is False
        assert "RT-4" in placement.agenda_placement_reason

        # Verify event was witnessed
        event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_timing_attack_prevention_scenario(
        self, integration_setup: dict
    ) -> None:
        """RT-4 prevents 'wait and reset' timing attacks.

        An attacker cannot manipulate by spacing failures just outside
        the consecutive window but within the rolling window.
        """
        service = integration_setup["service"]
        integrity_repo = integration_setup["integrity_failure_repo"]

        now = datetime.now(timezone.utc)

        # Attacker tries to space failures to avoid consecutive trigger
        # but RT-4 catches them anyway
        for i in range(5):
            integrity_repo.add_failure(uuid4(), now - timedelta(days=i * 18 + 1))
            # Add successful check after each to break consecutive
            if i < 4:  # Don't add after last failure
                await integrity_repo.record_successful_check(
                    now - timedelta(days=i * 18 + 8)
                )

        # Consecutive check should NOT trigger (failures not consecutive)
        consecutive_result = await service.check_consecutive_failures()
        assert consecutive_result.triggered is False

        # But rolling window SHOULD trigger (RT-4 catches the pattern)
        rolling_result = await service.check_rolling_window_failures()
        assert rolling_result.triggered is True
        assert rolling_result.trigger_type == AgendaTriggerType.ROLLING_WINDOW


class TestAntiSuccessFlow:
    """End-to-end tests for FR38 anti-success sustained trigger."""

    @pytest.mark.asyncio
    async def test_end_to_end_anti_success_agenda_placement(
        self, integration_setup: dict
    ) -> None:
        """FR38: Anti-success alert sustained 90 days places cessation on agenda."""
        service = integration_setup["service"]
        anti_success_repo = integration_setup["anti_success_repo"]
        agenda_repo = integration_setup["cessation_agenda_repo"]
        event_writer = integration_setup["event_writer"]

        now = datetime.now(timezone.utc)

        # Record initial alert that starts the sustained period
        await anti_success_repo.record_alert(
            uuid4(),
            now - timedelta(days=95),
            uuid4(),
        )

        # Record additional alerts during the sustained period
        await anti_success_repo.record_alert(
            uuid4(),
            now - timedelta(days=60),
            uuid4(),
        )
        await anti_success_repo.record_alert(
            uuid4(),
            now - timedelta(days=30),
            uuid4(),
        )

        # Trigger evaluation
        result = await service.check_anti_success_sustained()

        # Verify trigger fired
        assert result.triggered is True
        assert result.trigger_type == AgendaTriggerType.ANTI_SUCCESS_SUSTAINED
        assert result.was_idempotent is False

        # Verify agenda placement was persisted
        placement = await agenda_repo.get_by_id(result.placement_id)
        assert placement is not None
        assert placement.trigger_type == AgendaTriggerType.ANTI_SUCCESS_SUSTAINED
        assert "FR38" in placement.agenda_placement_reason
        assert placement.sustained_days >= 90
        assert placement.first_alert_date is not None

        # Verify event was witnessed
        event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolved_alerts_prevent_trigger(
        self, integration_setup: dict
    ) -> None:
        """Resolved anti-success alerts prevent FR38 trigger."""
        service = integration_setup["service"]
        anti_success_repo = integration_setup["anti_success_repo"]

        now = datetime.now(timezone.utc)

        # Start sustained period
        await anti_success_repo.record_alert(
            uuid4(),
            now - timedelta(days=100),
            uuid4(),
        )

        # Resolve the alerts
        await anti_success_repo.record_resolution(now - timedelta(days=5))

        # Trigger evaluation
        result = await service.check_anti_success_sustained()

        # Should NOT trigger - alerts were resolved
        assert result.triggered is False


class TestEvaluateAllTriggersFlow:
    """End-to-end tests for full evaluation flow."""

    @pytest.mark.asyncio
    async def test_all_triggers_evaluated_and_multiple_can_fire(
        self, integration_setup: dict
    ) -> None:
        """evaluate_all_triggers checks all triggers and multiple can fire."""
        service = integration_setup["service"]
        integrity_repo = integration_setup["integrity_failure_repo"]
        anti_success_repo = integration_setup["anti_success_repo"]
        agenda_repo = integration_setup["cessation_agenda_repo"]

        now = datetime.now(timezone.utc)

        # Set up conditions for all three triggers to fire
        # 5 consecutive failures (triggers both FR37 and RT-4)
        for i in range(5):
            integrity_repo.add_failure(uuid4(), now - timedelta(days=i * 5))

        # Anti-success sustained
        await anti_success_repo.record_alert(
            uuid4(),
            now - timedelta(days=100),
            uuid4(),
        )

        # Evaluate all
        results = await service.evaluate_all_triggers()

        # All three should trigger
        assert len(results) == 3
        assert all(r.triggered for r in results)

        triggered_types = {r.trigger_type for r in results}
        assert triggered_types == {
            AgendaTriggerType.CONSECUTIVE_FAILURES,
            AgendaTriggerType.ROLLING_WINDOW,
            AgendaTriggerType.ANTI_SUCCESS_SUSTAINED,
        }

        # All three placements should be persisted
        all_placements = await agenda_repo.list_all_placements()
        assert len(all_placements) == 3


class TestIdempotencyFlow:
    """End-to-end tests for idempotent behavior (AC4)."""

    @pytest.mark.asyncio
    async def test_repeated_evaluation_is_idempotent(
        self, integration_setup: dict
    ) -> None:
        """Repeated trigger evaluation returns existing placement, no duplicate."""
        service = integration_setup["service"]
        integrity_repo = integration_setup["integrity_failure_repo"]
        agenda_repo = integration_setup["cessation_agenda_repo"]
        event_writer = integration_setup["event_writer"]

        now = datetime.now(timezone.utc)

        # Set up trigger condition
        for i in range(3):
            integrity_repo.add_failure(uuid4(), now - timedelta(days=i * 5))

        # First evaluation creates placement
        result1 = await service.check_consecutive_failures()
        assert result1.triggered is True
        assert result1.was_idempotent is False

        # Verify one event written
        assert event_writer.write_event.call_count == 1

        # Second evaluation returns same placement
        result2 = await service.check_consecutive_failures()
        assert result2.triggered is True
        assert result2.was_idempotent is True
        assert result2.placement_id == result1.placement_id

        # No new event written
        assert event_writer.write_event.call_count == 1

        # Third evaluation also idempotent
        result3 = await service.check_consecutive_failures()
        assert result3.triggered is True
        assert result3.was_idempotent is True
        assert result3.placement_id == result1.placement_id

        # Still only one placement in repository
        all_placements = await agenda_repo.list_all_placements()
        assert len(all_placements) == 1


class TestEventPayloadIntegrity:
    """Tests for event payload completeness and integrity."""

    @pytest.mark.asyncio
    async def test_consecutive_failure_event_payload_complete(
        self, integration_setup: dict
    ) -> None:
        """Consecutive failure event contains all required fields."""
        service = integration_setup["service"]
        integrity_repo = integration_setup["integrity_failure_repo"]
        event_writer = integration_setup["event_writer"]

        now = datetime.now(timezone.utc)

        for i in range(3):
            integrity_repo.add_failure(uuid4(), now - timedelta(days=i * 5))

        await service.check_consecutive_failures()

        # Get the payload from the event writer call
        call_kwargs = event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify all required fields
        assert "placement_id" in payload
        assert "trigger_type" in payload
        assert payload["trigger_type"] == "consecutive_failures"
        assert "trigger_timestamp" in payload
        assert "failure_count" in payload
        assert payload["failure_count"] == 3
        assert "window_days" in payload
        assert payload["window_days"] == 30
        assert "consecutive" in payload
        assert payload["consecutive"] is True
        assert "failure_event_ids" in payload
        assert len(payload["failure_event_ids"]) == 3
        assert "agenda_placement_reason" in payload
        assert "FR37" in payload["agenda_placement_reason"]

    @pytest.mark.asyncio
    async def test_anti_success_event_payload_complete(
        self, integration_setup: dict
    ) -> None:
        """Anti-success event contains all required fields including history."""
        service = integration_setup["service"]
        anti_success_repo = integration_setup["anti_success_repo"]
        event_writer = integration_setup["event_writer"]

        now = datetime.now(timezone.utc)

        # Record multiple alerts
        for i in range(3):
            await anti_success_repo.record_alert(
                uuid4(),
                now - timedelta(days=95 - i * 10),
                uuid4(),
            )

        await service.check_anti_success_sustained()

        # Get the payload from the event writer call
        call_kwargs = event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify anti-success specific fields
        assert payload["trigger_type"] == "anti_success_sustained"
        assert "sustained_days" in payload
        assert payload["sustained_days"] >= 90
        assert "first_alert_date" in payload
        assert "alert_event_ids" in payload
        assert len(payload["alert_event_ids"]) == 3
        assert "FR38" in payload["agenda_placement_reason"]
