"""Unit tests for TransitionLog domain model.

Story: consent-gov-9.4: State Transition Logging

Tests the TransitionLog domain model including:
- Field validation
- Immutability (frozen dataclass)
- Query matching
- Entity type coverage
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.governance.audit.transition_log import (
    EntityType,
    TransitionLog,
    TransitionLogError,
    TransitionLogModificationError,
    TransitionLogNotFoundError,
    TransitionQuery,
)


class TestEntityType:
    """Tests for EntityType enum."""

    def test_all_entity_types_defined(self) -> None:
        """All expected entity types are defined."""
        expected_types = {
            "task",
            "legitimacy_band",
            "system",
            "cluster",
            "motion",
            "panel",
            "participant",
        }
        actual_types = {e.value for e in EntityType}
        assert actual_types == expected_types

    def test_task_entity_type(self) -> None:
        """Task entity type has correct value."""
        assert EntityType.TASK.value == "task"

    def test_legitimacy_band_entity_type(self) -> None:
        """Legitimacy band entity type has correct value."""
        assert EntityType.LEGITIMACY_BAND.value == "legitimacy_band"

    def test_system_entity_type(self) -> None:
        """System entity type has correct value."""
        assert EntityType.SYSTEM.value == "system"


class TestTransitionLog:
    """Tests for TransitionLog domain model."""

    @pytest.fixture
    def valid_log(self) -> TransitionLog:
        """Create a valid transition log for testing."""
        return TransitionLog(
            log_id=uuid4(),
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            timestamp=datetime.now(timezone.utc),
            actor=str(uuid4()),
            reason="Task activated by cluster",
            triggering_event_id=uuid4(),
        )

    def test_create_valid_transition_log(self, valid_log: TransitionLog) -> None:
        """Valid transition log can be created."""
        assert valid_log.log_id is not None
        assert valid_log.entity_type == EntityType.TASK
        assert valid_log.from_state == "pending"
        assert valid_log.to_state == "active"
        assert valid_log.timestamp is not None
        assert valid_log.actor is not None
        assert valid_log.reason == "Task activated by cluster"
        assert valid_log.triggering_event_id is not None

    def test_log_is_immutable(self, valid_log: TransitionLog) -> None:
        """Transition log cannot be modified after creation."""
        with pytest.raises(AttributeError):
            valid_log.from_state = "modified"  # type: ignore

        with pytest.raises(AttributeError):
            valid_log.to_state = "modified"  # type: ignore

        with pytest.raises(AttributeError):
            valid_log.reason = "modified reason"  # type: ignore

    def test_empty_from_state_rejected(self) -> None:
        """Empty from_state is rejected."""
        with pytest.raises(ValueError, match="from_state cannot be empty"):
            TransitionLog(
                log_id=uuid4(),
                entity_type=EntityType.TASK,
                entity_id=uuid4(),
                from_state="",
                to_state="active",
                timestamp=datetime.now(timezone.utc),
                actor="system",
                reason="Test",
            )

    def test_empty_to_state_rejected(self) -> None:
        """Empty to_state is rejected."""
        with pytest.raises(ValueError, match="to_state cannot be empty"):
            TransitionLog(
                log_id=uuid4(),
                entity_type=EntityType.TASK,
                entity_id=uuid4(),
                from_state="pending",
                to_state="",
                timestamp=datetime.now(timezone.utc),
                actor="system",
                reason="Test",
            )

    def test_empty_actor_rejected(self) -> None:
        """Empty actor is rejected."""
        with pytest.raises(ValueError, match="actor cannot be empty"):
            TransitionLog(
                log_id=uuid4(),
                entity_type=EntityType.TASK,
                entity_id=uuid4(),
                from_state="pending",
                to_state="active",
                timestamp=datetime.now(timezone.utc),
                actor="",
                reason="Test",
            )

    def test_empty_reason_rejected(self) -> None:
        """Empty reason is rejected."""
        with pytest.raises(ValueError, match="reason cannot be empty"):
            TransitionLog(
                log_id=uuid4(),
                entity_type=EntityType.TASK,
                entity_id=uuid4(),
                from_state="pending",
                to_state="active",
                timestamp=datetime.now(timezone.utc),
                actor="system",
                reason="",
            )

    def test_system_actor(self) -> None:
        """System actor is valid and detected correctly."""
        log = TransitionLog(
            log_id=uuid4(),
            entity_type=EntityType.SYSTEM,
            entity_id=uuid4(),
            from_state="running",
            to_state="halted",
            timestamp=datetime.now(timezone.utc),
            actor="system",
            reason="Automatic halt triggered",
        )
        assert log.is_system_initiated is True

    def test_uuid_actor(self, valid_log: TransitionLog) -> None:
        """UUID actor is not system-initiated."""
        assert valid_log.is_system_initiated is False

    def test_has_triggering_event(self, valid_log: TransitionLog) -> None:
        """Log with triggering event detected correctly."""
        assert valid_log.has_triggering_event is True

    def test_no_triggering_event(self) -> None:
        """Log without triggering event detected correctly."""
        log = TransitionLog(
            log_id=uuid4(),
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            timestamp=datetime.now(timezone.utc),
            actor="system",
            reason="Auto-transition",
            triggering_event_id=None,
        )
        assert log.has_triggering_event is False

    def test_timestamp_captured(self) -> None:
        """Timestamp is captured with sufficient precision."""
        now = datetime.now(timezone.utc)
        log = TransitionLog(
            log_id=uuid4(),
            entity_type=EntityType.TASK,
            entity_id=uuid4(),
            from_state="pending",
            to_state="active",
            timestamp=now,
            actor="system",
            reason="Test",
        )
        assert log.timestamp == now
        # Verify microsecond precision is preserved
        assert log.timestamp.microsecond == now.microsecond


class TestTransitionQuery:
    """Tests for TransitionQuery domain model."""

    @pytest.fixture
    def sample_logs(self) -> list[TransitionLog]:
        """Create sample logs for query testing."""
        entity_id_1 = uuid4()
        entity_id_2 = uuid4()
        actor_1 = str(uuid4())
        base_time = datetime.now(timezone.utc)

        return [
            TransitionLog(
                log_id=uuid4(),
                entity_type=EntityType.TASK,
                entity_id=entity_id_1,
                from_state="pending",
                to_state="active",
                timestamp=base_time,
                actor=actor_1,
                reason="Test 1",
            ),
            TransitionLog(
                log_id=uuid4(),
                entity_type=EntityType.LEGITIMACY_BAND,
                entity_id=entity_id_2,
                from_state="green",
                to_state="yellow",
                timestamp=base_time + timedelta(seconds=1),
                actor="system",
                reason="Test 2",
            ),
            TransitionLog(
                log_id=uuid4(),
                entity_type=EntityType.TASK,
                entity_id=entity_id_1,
                from_state="active",
                to_state="completed",
                timestamp=base_time + timedelta(seconds=2),
                actor=actor_1,
                reason="Test 3",
            ),
        ]

    def test_empty_query_matches_all(self, sample_logs: list[TransitionLog]) -> None:
        """Empty query matches all logs."""
        query = TransitionQuery()
        for log in sample_logs:
            assert query.matches(log) is True

    def test_filter_by_entity_type(self, sample_logs: list[TransitionLog]) -> None:
        """Query can filter by entity type."""
        query = TransitionQuery(entity_type=EntityType.TASK)
        matching = [log for log in sample_logs if query.matches(log)]
        assert len(matching) == 2
        for log in matching:
            assert log.entity_type == EntityType.TASK

    def test_filter_by_entity_id(self, sample_logs: list[TransitionLog]) -> None:
        """Query can filter by entity ID."""
        entity_id = sample_logs[0].entity_id
        query = TransitionQuery(entity_id=entity_id)
        matching = [log for log in sample_logs if query.matches(log)]
        assert len(matching) == 2
        for log in matching:
            assert log.entity_id == entity_id

    def test_filter_by_actor(self, sample_logs: list[TransitionLog]) -> None:
        """Query can filter by actor."""
        query = TransitionQuery(actor="system")
        matching = [log for log in sample_logs if query.matches(log)]
        assert len(matching) == 1
        assert matching[0].actor == "system"

    def test_filter_by_timestamp_range(self, sample_logs: list[TransitionLog]) -> None:
        """Query can filter by timestamp range."""
        from_time = sample_logs[1].timestamp
        to_time = sample_logs[2].timestamp
        query = TransitionQuery(from_timestamp=from_time, to_timestamp=to_time)
        matching = [log for log in sample_logs if query.matches(log)]
        assert len(matching) == 2

    def test_filter_by_from_state(self, sample_logs: list[TransitionLog]) -> None:
        """Query can filter by from_state."""
        query = TransitionQuery(from_state="pending")
        matching = [log for log in sample_logs if query.matches(log)]
        assert len(matching) == 1
        assert matching[0].from_state == "pending"

    def test_filter_by_to_state(self, sample_logs: list[TransitionLog]) -> None:
        """Query can filter by to_state."""
        query = TransitionQuery(to_state="completed")
        matching = [log for log in sample_logs if query.matches(log)]
        assert len(matching) == 1
        assert matching[0].to_state == "completed"

    def test_combined_filters(self, sample_logs: list[TransitionLog]) -> None:
        """Multiple filters are combined with AND logic."""
        entity_id = sample_logs[0].entity_id
        query = TransitionQuery(
            entity_type=EntityType.TASK,
            entity_id=entity_id,
            from_state="active",
        )
        matching = [log for log in sample_logs if query.matches(log)]
        assert len(matching) == 1
        assert matching[0].from_state == "active"
        assert matching[0].to_state == "completed"


class TestTransitionLogErrors:
    """Tests for transition log error classes."""

    def test_base_error_is_value_error(self) -> None:
        """TransitionLogError is a ValueError."""
        error = TransitionLogError("Test error")
        assert isinstance(error, ValueError)

    def test_modification_error_is_transition_log_error(self) -> None:
        """TransitionLogModificationError is a TransitionLogError."""
        error = TransitionLogModificationError("Cannot modify")
        assert isinstance(error, TransitionLogError)
        assert isinstance(error, ValueError)

    def test_not_found_error_is_transition_log_error(self) -> None:
        """TransitionLogNotFoundError is a TransitionLogError."""
        error = TransitionLogNotFoundError("Log not found")
        assert isinstance(error, TransitionLogError)


class TestAllEntityTypesConsistent:
    """Tests ensuring all entity types can be logged consistently."""

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
    def test_all_entity_types_can_be_logged(self, entity_type: EntityType) -> None:
        """All entity types can create valid transition logs."""
        log = TransitionLog(
            log_id=uuid4(),
            entity_type=entity_type,
            entity_id=uuid4(),
            from_state="state_a",
            to_state="state_b",
            timestamp=datetime.now(timezone.utc),
            actor="system",
            reason="Test transition",
        )
        assert log.entity_type == entity_type

    @pytest.mark.parametrize(
        "entity_type",
        list(EntityType),
    )
    def test_all_logs_have_same_structure(self, entity_type: EntityType) -> None:
        """All entity type logs have consistent structure."""
        log = TransitionLog(
            log_id=uuid4(),
            entity_type=entity_type,
            entity_id=uuid4(),
            from_state="state_a",
            to_state="state_b",
            timestamp=datetime.now(timezone.utc),
            actor="system",
            reason="Test transition",
        )

        # All logs have same fields
        assert hasattr(log, "log_id")
        assert hasattr(log, "entity_type")
        assert hasattr(log, "entity_id")
        assert hasattr(log, "from_state")
        assert hasattr(log, "to_state")
        assert hasattr(log, "timestamp")
        assert hasattr(log, "actor")
        assert hasattr(log, "reason")
        assert hasattr(log, "triggering_event_id")
