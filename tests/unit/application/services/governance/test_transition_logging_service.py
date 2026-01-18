"""Unit tests for TransitionLoggingService.

Story: consent-gov-9.4: State Transition Logging

Tests for the transition logging service including:
- Timestamp and actor capture
- Reason and triggering event capture
- Event emission
- Append-only enforcement (no modify/delete methods)
- Consistent logging across entity types
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.transition_logging_service import (
    TransitionLoggingService,
)
from src.domain.governance.audit.transition_log import (
    EntityType,
    TransitionLog,
    TransitionQuery,
)


class FakeTransitionLogPort:
    """Fake transition log port for testing."""

    def __init__(self) -> None:
        self.logs: list[TransitionLog] = []
        self.append_called = False
        self.last_appended: TransitionLog | None = None

    async def append(self, log: TransitionLog) -> None:
        """Append a transition log."""
        self.append_called = True
        self.last_appended = log
        self.logs.append(log)

    async def query(self, query: TransitionQuery) -> list[TransitionLog]:
        """Query transition logs."""
        return [log for log in self.logs if query.matches(log)]

    async def get_by_id(self, log_id: UUID) -> TransitionLog | None:
        """Get log by ID."""
        for log in self.logs:
            if log.log_id == log_id:
                return log
        return None

    async def count(self, query: TransitionQuery | None = None) -> int:
        """Count logs."""
        if query is None:
            return len(self.logs)
        return len([log for log in self.logs if query.matches(log)])

    async def get_entity_history(
        self,
        entity_type: EntityType,
        entity_id: UUID,
    ) -> list[TransitionLog]:
        """Get entity history."""
        return [
            log
            for log in self.logs
            if log.entity_type == entity_type and log.entity_id == entity_id
        ]


class FakeEventEmitter:
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.emit_called = False

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Record emitted event."""
        self.emit_called = True
        self.events.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )

    def get_last(self, event_type: str) -> dict[str, Any] | None:
        """Get last event of given type."""
        for event in reversed(self.events):
            if event["event_type"] == event_type:
                return event
        return None


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self) -> None:
        self._now = datetime.now(timezone.utc)

    def now(self) -> datetime:
        """Get current time."""
        return self._now

    def set_now(self, dt: datetime) -> None:
        """Set the current time for testing."""
        self._now = dt


@pytest.fixture
def log_port() -> FakeTransitionLogPort:
    """Create fake log port."""
    return FakeTransitionLogPort()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Create fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def service(
    log_port: FakeTransitionLogPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> TransitionLoggingService:
    """Create service under test."""
    return TransitionLoggingService(
        log_port=log_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


class TestTransitionLoggingService:
    """Tests for TransitionLoggingService."""

    async def test_log_transition_returns_log(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """log_transition returns a TransitionLog."""
        log = await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            actor=str(uuid4()),
            reason="Task activated",
        )

        assert isinstance(log, TransitionLog)

    async def test_timestamp_captured(
        self,
        service: TransitionLoggingService,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Timestamp is captured from TimeAuthority."""
        expected_time = datetime(2026, 1, 16, 12, 0, 0, 123456, tzinfo=timezone.utc)
        time_authority.set_now(expected_time)

        log = await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            actor="system",
            reason="Test",
        )

        assert log.timestamp == expected_time

    async def test_actor_captured(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """Actor is captured in log."""
        actor_id = str(uuid4())

        log = await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            actor=actor_id,
            reason="Test",
        )

        assert log.actor == actor_id

    async def test_system_actor_captured(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """System actor is captured for auto-transitions."""
        log = await service.log_transition(
            entity_type=EntityType.SYSTEM,
            entity_id=uuid4(),
            from_state="running",
            to_state="halted",
            actor="system",
            reason="Auto-halt triggered",
        )

        assert log.actor == "system"
        assert log.is_system_initiated is True

    async def test_reason_captured(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """Reason is captured in log."""
        reason = "Task completed successfully by cluster"

        log = await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="active",
            to_state="completed",
            actor=str(uuid4()),
            reason=reason,
        )

        assert log.reason == reason

    async def test_triggering_event_captured(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """Triggering event ID is captured in log."""
        triggering_event_id = uuid4()

        log = await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            actor=str(uuid4()),
            reason="Test",
            triggering_event_id=triggering_event_id,
        )

        assert log.triggering_event_id == triggering_event_id

    async def test_log_appended_to_port(
        self,
        service: TransitionLoggingService,
        log_port: FakeTransitionLogPort,
    ) -> None:
        """Log is appended to the port."""
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            actor="system",
            reason="Test",
        )

        assert log_port.append_called is True
        assert log_port.last_appended is not None

    async def test_event_emitted(
        self,
        service: TransitionLoggingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """audit.transition.logged event is emitted."""
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            actor="system",
            reason="Test",
        )

        assert event_emitter.emit_called is True
        event = event_emitter.get_last("audit.transition.logged")
        assert event is not None
        assert event["event_type"] == "audit.transition.logged"

    async def test_emitted_event_contains_log_details(
        self,
        service: TransitionLoggingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Emitted event contains all log details."""
        entity_id = uuid4()
        actor = str(uuid4())
        triggering_event_id = uuid4()

        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=entity_id,
            from_state="pending",
            to_state="active",
            actor=actor,
            reason="Task activated",
            triggering_event_id=triggering_event_id,
        )

        event = event_emitter.get_last("audit.transition.logged")
        assert event is not None
        payload = event["payload"]

        assert payload["entity_type"] == "task"
        assert payload["entity_id"] == str(entity_id)
        assert payload["from_state"] == "pending"
        assert payload["to_state"] == "active"
        assert payload["actor"] == actor
        assert payload["reason"] == "Task activated"
        assert payload["triggering_event_id"] == str(triggering_event_id)

    async def test_get_transitions_delegates_to_port(
        self,
        service: TransitionLoggingService,
        log_port: FakeTransitionLogPort,
    ) -> None:
        """get_transitions delegates to port."""
        # Add a log first
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            actor="system",
            reason="Test",
        )

        query = TransitionQuery(entity_type=EntityType.TASK)
        results = await service.get_transitions(query)

        assert len(results) == 1

    async def test_get_entity_history_returns_all_transitions(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """get_entity_history returns all transitions for entity."""
        entity_id = uuid4()

        # Log multiple transitions for same entity
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=entity_id,
            from_state="pending",
            to_state="active",
            actor="system",
            reason="Activated",
        )
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=entity_id,
            from_state="active",
            to_state="completed",
            actor="system",
            reason="Completed",
        )

        history = await service.get_entity_history(EntityType.TASK, entity_id)

        assert len(history) == 2


class TestAppendOnlyEnforcement:
    """Tests ensuring append-only design."""

    def test_no_update_method(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """Service has no update method."""
        assert not hasattr(service, "update_log")
        assert not hasattr(service, "modify_log")

    def test_no_delete_method(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """Service has no delete method."""
        assert not hasattr(service, "delete_log")
        assert not hasattr(service, "remove_log")


class TestConsistentLoggingAcrossEntityTypes:
    """Tests for consistent logging across all entity types."""

    @pytest.mark.parametrize(
        "entity_type",
        [
            EntityType.TASK,
            EntityType.LEGITIMACY_BAND,
            EntityType.SYSTEM,
            EntityType.CLUSTER,
            EntityType.MOTION,
            EntityType.PANEL,
            EntityType.PARTICIPANT,
        ],
    )
    async def test_all_entity_types_can_be_logged(
        self,
        service: TransitionLoggingService,
        entity_type: EntityType,
    ) -> None:
        """All entity types can be logged through the service."""
        log = await service.log_transition(
            entity_type=entity_type,
            entity_id=uuid4(),
            from_state="state_a",
            to_state="state_b",
            actor="system",
            reason="Test transition",
        )

        assert log.entity_type == entity_type

    @pytest.mark.parametrize(
        "entity_type",
        list(EntityType),
    )
    async def test_all_entity_types_emit_same_event(
        self,
        service: TransitionLoggingService,
        event_emitter: FakeEventEmitter,
        entity_type: EntityType,
    ) -> None:
        """All entity types emit the same event type."""
        await service.log_transition(
            entity_type=entity_type,
            entity_id=uuid4(),
            from_state="state_a",
            to_state="state_b",
            actor="system",
            reason="Test transition",
        )

        event = event_emitter.get_last("audit.transition.logged")
        assert event is not None
        assert event["payload"]["entity_type"] == entity_type.value


class TestIntegrationWithTaskState:
    """Tests simulating integration with task state transitions."""

    async def test_task_state_machine_integration(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """Simulate task going through state machine."""
        task_id = uuid4()
        cluster_id = str(uuid4())

        # pending -> offered
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            from_state="pending",
            to_state="offered",
            actor="system",
            reason="Task offered to cluster",
        )

        # offered -> accepted
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            from_state="offered",
            to_state="accepted",
            actor=cluster_id,
            reason="Cluster accepted task",
        )

        # accepted -> in_progress
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            from_state="accepted",
            to_state="in_progress",
            actor=cluster_id,
            reason="Cluster started work",
        )

        # in_progress -> completed
        await service.log_transition(
            entity_type=EntityType.TASK,
            entity_id=task_id,
            from_state="in_progress",
            to_state="completed",
            actor=cluster_id,
            reason="Task completed successfully",
        )

        # Verify full history
        history = await service.get_entity_history(EntityType.TASK, task_id)

        assert len(history) == 4
        assert history[0].from_state == "pending"
        assert history[0].to_state == "offered"
        assert history[1].from_state == "offered"
        assert history[1].to_state == "accepted"
        assert history[2].from_state == "accepted"
        assert history[2].to_state == "in_progress"
        assert history[3].from_state == "in_progress"
        assert history[3].to_state == "completed"


class TestIntegrationWithLegitimacyBand:
    """Tests simulating integration with legitimacy band transitions."""

    async def test_legitimacy_band_decay(
        self,
        service: TransitionLoggingService,
    ) -> None:
        """Simulate legitimacy band decay."""
        system_id = uuid4()
        triggering_event = uuid4()

        log = await service.log_transition(
            entity_type=EntityType.LEGITIMACY_BAND,
            entity_id=system_id,
            from_state="green",
            to_state="yellow",
            actor="system",
            reason="Automated decay due to overdue tasks",
            triggering_event_id=triggering_event,
        )

        assert log.entity_type == EntityType.LEGITIMACY_BAND
        assert log.from_state == "green"
        assert log.to_state == "yellow"
        assert log.triggering_event_id == triggering_event


class TestPortProtocolCompliance:
    """Tests ensuring port has no forbidden methods."""

    def test_fake_port_has_no_update(
        self,
        log_port: FakeTransitionLogPort,
    ) -> None:
        """Fake port implements append-only design."""
        assert not hasattr(log_port, "update")
        assert not hasattr(log_port, "modify")

    def test_fake_port_has_no_delete(
        self,
        log_port: FakeTransitionLogPort,
    ) -> None:
        """Fake port has no delete methods."""
        assert not hasattr(log_port, "delete")
        assert not hasattr(log_port, "remove")
