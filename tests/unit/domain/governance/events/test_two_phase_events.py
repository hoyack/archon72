"""Unit tests for two-phase event domain models.

Story: consent-gov-1.6: Two-Phase Event Emission

Tests the IntentEmittedEvent, CommitConfirmedEvent, and FailureRecordedEvent
domain models that enable Knight observability of all governance operations.

Constitutional Reference:
- AD-3: Two-phase event emission
- NFR-CONST-07: Witness statements cannot be suppressed
"""

from uuid import UUID, uuid4

import pytest

from src.domain.governance.events.two_phase_events import (
    CommitConfirmedEvent,
    FailureRecordedEvent,
    IntentEmittedEvent,
    TwoPhaseEventTypeError,
)


class TestIntentEmittedEvent:
    """Tests for IntentEmittedEvent domain model."""

    def test_create_valid_intent_event(self) -> None:
        """Should create a valid IntentEmittedEvent with all required fields."""
        correlation_id = uuid4()
        event = IntentEmittedEvent(
            correlation_id=correlation_id,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        )

        assert event.correlation_id == correlation_id
        assert event.operation_type == "executive.task.accept"
        assert event.actor_id == "archon-42"
        assert event.target_entity_id == "task-001"
        assert event.intent_payload == {"earl_id": "earl-1"}

    def test_intent_event_is_frozen(self) -> None:
        """IntentEmittedEvent should be immutable (frozen)."""
        event = IntentEmittedEvent(
            correlation_id=uuid4(),
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        with pytest.raises(AttributeError):
            event.operation_type = "modified"  # type: ignore

    def test_intent_event_correlation_id_must_be_uuid(self) -> None:
        """correlation_id must be a UUID."""
        with pytest.raises(TwoPhaseEventTypeError):
            IntentEmittedEvent(
                correlation_id="not-a-uuid",  # type: ignore
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            )

    def test_intent_event_actor_id_must_be_non_empty(self) -> None:
        """actor_id must be a non-empty string."""
        with pytest.raises(TwoPhaseEventTypeError):
            IntentEmittedEvent(
                correlation_id=uuid4(),
                operation_type="executive.task.accept",
                actor_id="",
                target_entity_id="task-001",
                intent_payload={},
            )

    def test_intent_event_operation_type_must_be_non_empty(self) -> None:
        """operation_type must be a non-empty string."""
        with pytest.raises(TwoPhaseEventTypeError):
            IntentEmittedEvent(
                correlation_id=uuid4(),
                operation_type="",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            )

    def test_intent_event_target_entity_id_must_be_non_empty(self) -> None:
        """target_entity_id must be a non-empty string."""
        with pytest.raises(TwoPhaseEventTypeError):
            IntentEmittedEvent(
                correlation_id=uuid4(),
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="",
                intent_payload={},
            )

    def test_intent_event_generates_event_type(self) -> None:
        """Should generate correct event type based on branch from operation_type."""
        event = IntentEmittedEvent(
            correlation_id=uuid4(),
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        assert event.event_type == "executive.intent.emitted"

    def test_intent_event_judicial_branch_event_type(self) -> None:
        """Should generate judicial branch event type."""
        event = IntentEmittedEvent(
            correlation_id=uuid4(),
            operation_type="judicial.panel.convene",
            actor_id="archon-42",
            target_entity_id="panel-001",
            intent_payload={},
        )

        assert event.event_type == "judicial.intent.emitted"


class TestCommitConfirmedEvent:
    """Tests for CommitConfirmedEvent domain model."""

    def test_create_valid_commit_event(self) -> None:
        """Should create a valid CommitConfirmedEvent with all required fields."""
        correlation_id = uuid4()
        intent_event_id = uuid4()
        event = CommitConfirmedEvent(
            correlation_id=correlation_id,
            intent_event_id=intent_event_id,
            operation_type="executive.task.accept",
            result_payload={"new_state": "accepted"},
        )

        assert event.correlation_id == correlation_id
        assert event.intent_event_id == intent_event_id
        assert event.operation_type == "executive.task.accept"
        assert event.result_payload == {"new_state": "accepted"}

    def test_commit_event_is_frozen(self) -> None:
        """CommitConfirmedEvent should be immutable (frozen)."""
        event = CommitConfirmedEvent(
            correlation_id=uuid4(),
            intent_event_id=uuid4(),
            operation_type="executive.task.accept",
            result_payload={},
        )

        with pytest.raises(AttributeError):
            event.operation_type = "modified"  # type: ignore

    def test_commit_event_correlation_id_must_be_uuid(self) -> None:
        """correlation_id must be a UUID."""
        with pytest.raises(TwoPhaseEventTypeError):
            CommitConfirmedEvent(
                correlation_id="not-a-uuid",  # type: ignore
                intent_event_id=uuid4(),
                operation_type="executive.task.accept",
                result_payload={},
            )

    def test_commit_event_intent_event_id_must_be_uuid(self) -> None:
        """intent_event_id must be a UUID."""
        with pytest.raises(TwoPhaseEventTypeError):
            CommitConfirmedEvent(
                correlation_id=uuid4(),
                intent_event_id="not-a-uuid",  # type: ignore
                operation_type="executive.task.accept",
                result_payload={},
            )

    def test_commit_event_generates_event_type(self) -> None:
        """Should generate correct event type based on branch from operation_type."""
        event = CommitConfirmedEvent(
            correlation_id=uuid4(),
            intent_event_id=uuid4(),
            operation_type="executive.task.accept",
            result_payload={},
        )

        assert event.event_type == "executive.commit.confirmed"


class TestFailureRecordedEvent:
    """Tests for FailureRecordedEvent domain model."""

    def test_create_valid_failure_event(self) -> None:
        """Should create a valid FailureRecordedEvent with all required fields."""
        correlation_id = uuid4()
        intent_event_id = uuid4()
        event = FailureRecordedEvent(
            correlation_id=correlation_id,
            intent_event_id=intent_event_id,
            operation_type="executive.task.accept",
            failure_reason="VALIDATION_FAILED",
            failure_details={"error": "Invalid state transition"},
        )

        assert event.correlation_id == correlation_id
        assert event.intent_event_id == intent_event_id
        assert event.operation_type == "executive.task.accept"
        assert event.failure_reason == "VALIDATION_FAILED"
        assert event.failure_details == {"error": "Invalid state transition"}
        assert event.was_orphan is False

    def test_failure_event_was_orphan_flag(self) -> None:
        """Should support was_orphan flag for auto-resolved orphans."""
        event = FailureRecordedEvent(
            correlation_id=uuid4(),
            intent_event_id=uuid4(),
            operation_type="executive.task.accept",
            failure_reason="ORPHAN_TIMEOUT",
            failure_details={"timeout_seconds": 300},
            was_orphan=True,
        )

        assert event.was_orphan is True

    def test_failure_event_is_frozen(self) -> None:
        """FailureRecordedEvent should be immutable (frozen)."""
        event = FailureRecordedEvent(
            correlation_id=uuid4(),
            intent_event_id=uuid4(),
            operation_type="executive.task.accept",
            failure_reason="ERROR",
            failure_details={},
        )

        with pytest.raises(AttributeError):
            event.failure_reason = "modified"  # type: ignore

    def test_failure_event_correlation_id_must_be_uuid(self) -> None:
        """correlation_id must be a UUID."""
        with pytest.raises(TwoPhaseEventTypeError):
            FailureRecordedEvent(
                correlation_id="not-a-uuid",  # type: ignore
                intent_event_id=uuid4(),
                operation_type="executive.task.accept",
                failure_reason="ERROR",
                failure_details={},
            )

    def test_failure_event_failure_reason_must_be_non_empty(self) -> None:
        """failure_reason must be a non-empty string."""
        with pytest.raises(TwoPhaseEventTypeError):
            FailureRecordedEvent(
                correlation_id=uuid4(),
                intent_event_id=uuid4(),
                operation_type="executive.task.accept",
                failure_reason="",
                failure_details={},
            )

    def test_failure_event_generates_event_type(self) -> None:
        """Should generate correct event type based on branch from operation_type."""
        event = FailureRecordedEvent(
            correlation_id=uuid4(),
            intent_event_id=uuid4(),
            operation_type="judicial.panel.convene",
            failure_reason="ERROR",
            failure_details={},
        )

        assert event.event_type == "judicial.failure.recorded"


class TestCorrelationIdLinking:
    """Tests for correlation ID linking between intent and outcome events (AC4)."""

    def test_commit_links_to_intent_via_correlation_id(self) -> None:
        """CommitConfirmedEvent should link to intent via matching correlation_id."""
        correlation_id = uuid4()
        intent_event_id = uuid4()

        intent = IntentEmittedEvent(
            correlation_id=correlation_id,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        )

        commit = CommitConfirmedEvent(
            correlation_id=correlation_id,
            intent_event_id=intent_event_id,
            operation_type="executive.task.accept",
            result_payload={"new_state": "accepted"},
        )

        # Same correlation_id links intent to commit
        assert intent.correlation_id == commit.correlation_id
        # commit also has reference to intent's event_id in ledger
        assert commit.intent_event_id == intent_event_id

    def test_failure_links_to_intent_via_correlation_id(self) -> None:
        """FailureRecordedEvent should link to intent via matching correlation_id."""
        correlation_id = uuid4()
        intent_event_id = uuid4()

        intent = IntentEmittedEvent(
            correlation_id=correlation_id,
            operation_type="judicial.panel.convene",
            actor_id="archon-42",
            target_entity_id="panel-001",
            intent_payload={},
        )

        failure = FailureRecordedEvent(
            correlation_id=correlation_id,
            intent_event_id=intent_event_id,
            operation_type="judicial.panel.convene",
            failure_reason="QUORUM_NOT_MET",
            failure_details={"required": 5, "present": 3},
        )

        # Same correlation_id links intent to failure
        assert intent.correlation_id == failure.correlation_id
        # failure also has reference to intent's event_id in ledger
        assert failure.intent_event_id == intent_event_id

    def test_correlation_id_is_uuid_v4_format(self) -> None:
        """correlation_id should be a valid UUID."""
        correlation_id = uuid4()
        intent = IntentEmittedEvent(
            correlation_id=correlation_id,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        # Verify it's a proper UUID
        assert isinstance(intent.correlation_id, UUID)
        assert str(intent.correlation_id) == str(correlation_id)

    def test_outcome_references_valid_intent_event_id(self) -> None:
        """Outcome events should reference intent_event_id as UUID."""
        commit = CommitConfirmedEvent(
            correlation_id=uuid4(),
            intent_event_id=uuid4(),
            operation_type="executive.task.accept",
            result_payload={},
        )

        assert isinstance(commit.intent_event_id, UUID)

        failure = FailureRecordedEvent(
            correlation_id=uuid4(),
            intent_event_id=uuid4(),
            operation_type="executive.task.accept",
            failure_reason="ERROR",
            failure_details={},
        )

        assert isinstance(failure.intent_event_id, UUID)


class TestTwoPhaseEventEquality:
    """Tests for two-phase event equality and hashing."""

    def test_intent_events_equal_by_correlation_id(self) -> None:
        """Two IntentEmittedEvents with same correlation_id should be equal."""
        correlation_id = uuid4()
        event1 = IntentEmittedEvent(
            correlation_id=correlation_id,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )
        event2 = IntentEmittedEvent(
            correlation_id=correlation_id,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        assert event1 == event2
        assert hash(event1) == hash(event2)

    def test_intent_events_not_equal_with_different_correlation_id(self) -> None:
        """IntentEmittedEvents with different correlation_ids should not be equal."""
        event1 = IntentEmittedEvent(
            correlation_id=uuid4(),
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )
        event2 = IntentEmittedEvent(
            correlation_id=uuid4(),
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        )

        assert event1 != event2
