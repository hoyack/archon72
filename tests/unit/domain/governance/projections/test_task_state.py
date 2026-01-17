"""Unit tests for TaskStateRecord projection model.

Tests cover acceptance criteria for story consent-gov-1.5:
- AC4: Domain models for each projection record type
- Validation of immutability and field constraints
- State machine transition rules
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.projections.task_state import TaskStateRecord


class TestTaskStateRecordCreation:
    """Tests for TaskStateRecord creation and validation."""

    def test_valid_task_state_creation(self) -> None:
        """TaskStateRecord with valid data creates successfully."""
        now = datetime.now(timezone.utc)
        task_id = uuid4()
        record = TaskStateRecord(
            task_id=task_id,
            current_state="pending",
            earl_id="earl-42",
            cluster_id="cluster-alpha",
            task_type="code_review",
            created_at=now,
            state_entered_at=now,
            last_event_sequence=1,
            last_event_hash="abc123",
            updated_at=now,
        )

        assert record.task_id == task_id
        assert record.current_state == "pending"
        assert record.earl_id == "earl-42"
        assert record.cluster_id == "cluster-alpha"
        assert record.task_type == "code_review"
        assert record.last_event_sequence == 1
        assert record.last_event_hash == "abc123"

    def test_task_state_record_is_immutable(self) -> None:
        """TaskStateRecord fields cannot be modified after creation."""
        now = datetime.now(timezone.utc)
        record = TaskStateRecord(
            task_id=uuid4(),
            current_state="pending",
            earl_id="earl-42",
            cluster_id=None,
            task_type=None,
            created_at=now,
            state_entered_at=now,
            last_event_sequence=1,
            last_event_hash="abc123",
            updated_at=now,
        )

        with pytest.raises(AttributeError):
            record.current_state = "activated"  # type: ignore[misc]

    def test_invalid_state_raises_error(self) -> None:
        """Invalid current_state raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            TaskStateRecord(
                task_id=uuid4(),
                current_state="invalid_state",
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=1,
                last_event_hash="abc123",
                updated_at=now,
            )
        assert "Invalid task state" in str(exc_info.value)

    def test_negative_sequence_raises_error(self) -> None:
        """Negative last_event_sequence raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            TaskStateRecord(
                task_id=uuid4(),
                current_state="pending",
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=-1,
                last_event_hash="abc123",
                updated_at=now,
            )
        assert "non-negative" in str(exc_info.value)


class TestTaskStateRecordValidStates:
    """Tests for valid states enumeration."""

    def test_all_valid_states_can_be_created(self) -> None:
        """All VALID_STATES can be used to create records."""
        now = datetime.now(timezone.utc)
        for state in TaskStateRecord.VALID_STATES:
            record = TaskStateRecord(
                task_id=uuid4(),
                current_state=state,
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=1,
                last_event_hash="abc123",
                updated_at=now,
            )
            assert record.current_state == state

    def test_valid_states_contains_expected_values(self) -> None:
        """VALID_STATES contains all expected task states."""
        expected = {"pending", "authorized", "activated", "accepted", "completed", "declined", "expired"}
        assert TaskStateRecord.VALID_STATES == frozenset(expected)


class TestTaskStateRecordTransitions:
    """Tests for state transition logic."""

    def test_pending_can_transition_to_authorized(self) -> None:
        """Pending state can transition to authorized."""
        now = datetime.now(timezone.utc)
        record = TaskStateRecord(
            task_id=uuid4(),
            current_state="pending",
            earl_id="earl-42",
            cluster_id=None,
            task_type=None,
            created_at=now,
            state_entered_at=now,
            last_event_sequence=1,
            last_event_hash="abc123",
            updated_at=now,
        )

        assert record.can_transition_to("authorized")
        # pending can only transition to authorized per state machine
        assert not record.can_transition_to("expired")
        assert not record.can_transition_to("completed")

    def test_authorized_can_transition_to_activated(self) -> None:
        """Authorized state can transition to activated."""
        now = datetime.now(timezone.utc)
        record = TaskStateRecord(
            task_id=uuid4(),
            current_state="authorized",
            earl_id="earl-42",
            cluster_id=None,
            task_type=None,
            created_at=now,
            state_entered_at=now,
            last_event_sequence=1,
            last_event_hash="abc123",
            updated_at=now,
        )

        assert record.can_transition_to("activated")
        assert record.can_transition_to("expired")
        assert not record.can_transition_to("pending")

    def test_activated_can_transition_to_accepted_declined_expired(self) -> None:
        """Activated state can transition to accepted, declined, or expired."""
        now = datetime.now(timezone.utc)
        record = TaskStateRecord(
            task_id=uuid4(),
            current_state="activated",
            earl_id="earl-42",
            cluster_id=None,
            task_type=None,
            created_at=now,
            state_entered_at=now,
            last_event_sequence=1,
            last_event_hash="abc123",
            updated_at=now,
        )

        assert record.can_transition_to("accepted")
        assert record.can_transition_to("declined")
        assert record.can_transition_to("expired")
        assert not record.can_transition_to("pending")
        assert not record.can_transition_to("authorized")

    def test_accepted_can_transition_to_completed(self) -> None:
        """Accepted state can transition to completed."""
        now = datetime.now(timezone.utc)
        record = TaskStateRecord(
            task_id=uuid4(),
            current_state="accepted",
            earl_id="earl-42",
            cluster_id=None,
            task_type=None,
            created_at=now,
            state_entered_at=now,
            last_event_sequence=1,
            last_event_hash="abc123",
            updated_at=now,
        )

        assert record.can_transition_to("completed")
        # accepted can only transition to completed per state machine
        assert not record.can_transition_to("expired")
        assert not record.can_transition_to("pending")

    def test_terminal_states_cannot_transition(self) -> None:
        """Terminal states (completed, declined, expired) cannot transition."""
        now = datetime.now(timezone.utc)
        terminal_states = ["completed", "declined", "expired"]

        for state in terminal_states:
            record = TaskStateRecord(
                task_id=uuid4(),
                current_state=state,
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=1,
                last_event_hash="abc123",
                updated_at=now,
            )

            for target_state in TaskStateRecord.VALID_STATES:
                assert not record.can_transition_to(target_state)


class TestTaskStateRecordHelpers:
    """Tests for helper methods."""

    def test_is_terminal_for_terminal_states(self) -> None:
        """is_terminal returns True for terminal states."""
        now = datetime.now(timezone.utc)
        terminal_states = ["completed", "declined", "expired"]

        for state in terminal_states:
            record = TaskStateRecord(
                task_id=uuid4(),
                current_state=state,
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=1,
                last_event_hash="abc123",
                updated_at=now,
            )
            assert record.is_terminal()

    def test_is_terminal_for_non_terminal_states(self) -> None:
        """is_terminal returns False for non-terminal states."""
        now = datetime.now(timezone.utc)
        non_terminal_states = ["pending", "authorized", "activated", "accepted"]

        for state in non_terminal_states:
            record = TaskStateRecord(
                task_id=uuid4(),
                current_state=state,
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=1,
                last_event_hash="abc123",
                updated_at=now,
            )
            assert not record.is_terminal()

    def test_is_active_for_non_terminal_states(self) -> None:
        """is_active returns True for non-terminal states."""
        now = datetime.now(timezone.utc)
        # is_active is the opposite of is_terminal
        active_states = ["pending", "authorized", "activated", "accepted"]

        for state in active_states:
            record = TaskStateRecord(
                task_id=uuid4(),
                current_state=state,
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=1,
                last_event_hash="abc123",
                updated_at=now,
            )
            assert record.is_active()

    def test_is_active_for_terminal_states(self) -> None:
        """is_active returns False for terminal states."""
        now = datetime.now(timezone.utc)
        terminal_states = ["completed", "declined", "expired"]

        for state in terminal_states:
            record = TaskStateRecord(
                task_id=uuid4(),
                current_state=state,
                earl_id="earl-42",
                cluster_id=None,
                task_type=None,
                created_at=now,
                state_entered_at=now,
                last_event_sequence=1,
                last_event_hash="abc123",
                updated_at=now,
            )
            assert not record.is_active()
