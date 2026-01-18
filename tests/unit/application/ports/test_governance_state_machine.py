"""Unit tests for Governance State Machine port (Epic 8, Story 8.1).

Tests:
- GovernanceState enum values (7-step canonical flow)
- Valid transitions per FR-GOV-23
- Terminal state identification
- StateTransition immutability
- MotionStateRecord properties
- TransitionRejection creation
- Transition validation functions

Constitutional Constraints:
- FR-GOV-23: Governance Flow - 7 canonical steps, no skipping
- PRD §2.1: Separation of Powers
- CT-11: Silent failure destroys legitimacy -> rejection recorded
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestGovernanceStateEnum:
    """Test GovernanceState enum values."""

    def test_all_states_defined(self) -> None:
        """All 9 governance states are defined."""
        from src.application.ports.governance_state_machine import GovernanceState

        expected_states = {
            "introduced",
            "deliberating",
            "ratified",
            "rejected",
            "tabled",
            "planning",
            "executing",
            "judging",
            "witnessing",
            "acknowledged",
        }

        actual_states = {s.value for s in GovernanceState}
        assert actual_states == expected_states

    def test_state_values_are_lowercase(self) -> None:
        """All state values are lowercase strings."""
        from src.application.ports.governance_state_machine import GovernanceState

        for state in GovernanceState:
            assert state.value == state.value.lower()
            assert isinstance(state.value, str)


class TestTerminalStates:
    """Test terminal state identification."""

    def test_rejected_is_terminal(self) -> None:
        """REJECTED is a terminal state."""
        from src.application.ports.governance_state_machine import (
            TERMINAL_STATES,
            GovernanceState,
            is_terminal_state,
        )

        assert GovernanceState.REJECTED in TERMINAL_STATES
        assert is_terminal_state(GovernanceState.REJECTED)

    def test_acknowledged_is_terminal(self) -> None:
        """ACKNOWLEDGED is a terminal state."""
        from src.application.ports.governance_state_machine import (
            TERMINAL_STATES,
            GovernanceState,
            is_terminal_state,
        )

        assert GovernanceState.ACKNOWLEDGED in TERMINAL_STATES
        assert is_terminal_state(GovernanceState.ACKNOWLEDGED)

    def test_non_terminal_states(self) -> None:
        """Non-terminal states return False."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_terminal_state,
        )

        non_terminal = [
            GovernanceState.INTRODUCED,
            GovernanceState.DELIBERATING,
            GovernanceState.RATIFIED,
            GovernanceState.TABLED,
            GovernanceState.PLANNING,
            GovernanceState.EXECUTING,
            GovernanceState.JUDGING,
            GovernanceState.WITNESSING,
        ]

        for state in non_terminal:
            assert not is_terminal_state(state)

    def test_exactly_two_terminal_states(self) -> None:
        """Only REJECTED and ACKNOWLEDGED are terminal."""
        from src.application.ports.governance_state_machine import TERMINAL_STATES

        assert len(TERMINAL_STATES) == 2


class TestValidTransitions:
    """Test valid state transitions per FR-GOV-23."""

    def test_introduced_to_deliberating(self) -> None:
        """Step 1→2: INTRODUCED can transition to DELIBERATING."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(
            GovernanceState.INTRODUCED, GovernanceState.DELIBERATING
        )

    def test_deliberating_to_ratified(self) -> None:
        """Step 2→2b: DELIBERATING can transition to RATIFIED."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(
            GovernanceState.DELIBERATING, GovernanceState.RATIFIED
        )

    def test_deliberating_to_rejected(self) -> None:
        """Step 2→terminal: DELIBERATING can transition to REJECTED."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(
            GovernanceState.DELIBERATING, GovernanceState.REJECTED
        )

    def test_deliberating_to_tabled(self) -> None:
        """Step 2→tabled: DELIBERATING can transition to TABLED."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(GovernanceState.DELIBERATING, GovernanceState.TABLED)

    def test_tabled_back_to_deliberating(self) -> None:
        """Tabled motions can return to DELIBERATING."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(GovernanceState.TABLED, GovernanceState.DELIBERATING)

    def test_ratified_to_planning(self) -> None:
        """Step 2b→3: RATIFIED can transition to PLANNING."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(GovernanceState.RATIFIED, GovernanceState.PLANNING)

    def test_planning_to_executing(self) -> None:
        """Step 3→4: PLANNING can transition to EXECUTING."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(GovernanceState.PLANNING, GovernanceState.EXECUTING)

    def test_executing_to_judging(self) -> None:
        """Step 4→5: EXECUTING can transition to JUDGING."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(GovernanceState.EXECUTING, GovernanceState.JUDGING)

    def test_judging_to_witnessing(self) -> None:
        """Step 5→6: JUDGING can transition to WITNESSING."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(GovernanceState.JUDGING, GovernanceState.WITNESSING)

    def test_witnessing_to_acknowledged(self) -> None:
        """Step 6→7: WITNESSING can transition to ACKNOWLEDGED."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert is_valid_transition(
            GovernanceState.WITNESSING, GovernanceState.ACKNOWLEDGED
        )

    def test_skip_not_allowed(self) -> None:
        """Per FR-GOV-23: No step may be skipped."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        # Cannot skip DELIBERATING
        assert not is_valid_transition(
            GovernanceState.INTRODUCED, GovernanceState.RATIFIED
        )

        # Cannot skip PLANNING
        assert not is_valid_transition(
            GovernanceState.RATIFIED, GovernanceState.EXECUTING
        )

        # Cannot skip JUDGING
        assert not is_valid_transition(
            GovernanceState.EXECUTING, GovernanceState.WITNESSING
        )

    def test_invalid_backwards_transition(self) -> None:
        """Cannot go backwards in flow (except TABLED)."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            is_valid_transition,
        )

        assert not is_valid_transition(
            GovernanceState.PLANNING, GovernanceState.RATIFIED
        )
        assert not is_valid_transition(
            GovernanceState.EXECUTING, GovernanceState.PLANNING
        )


class TestGetValidNextStates:
    """Test get_valid_next_states function."""

    def test_introduced_next_states(self) -> None:
        """INTRODUCED can only go to DELIBERATING."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            get_valid_next_states,
        )

        next_states = get_valid_next_states(GovernanceState.INTRODUCED)
        assert next_states == [GovernanceState.DELIBERATING]

    def test_deliberating_next_states(self) -> None:
        """DELIBERATING has three possible outcomes."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            get_valid_next_states,
        )

        next_states = get_valid_next_states(GovernanceState.DELIBERATING)
        assert set(next_states) == {
            GovernanceState.RATIFIED,
            GovernanceState.REJECTED,
            GovernanceState.TABLED,
        }

    def test_terminal_state_no_next_states(self) -> None:
        """Terminal states have no valid next states."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            get_valid_next_states,
        )

        assert get_valid_next_states(GovernanceState.REJECTED) == []
        assert get_valid_next_states(GovernanceState.ACKNOWLEDGED) == []


class TestStateTransition:
    """Test StateTransition dataclass."""

    def test_create_transition(self) -> None:
        """StateTransition.create() produces valid transition."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            StateTransition,
        )

        motion_id = uuid4()
        transition = StateTransition.create(
            motion_id=motion_id,
            from_state=GovernanceState.INTRODUCED,
            to_state=GovernanceState.DELIBERATING,
            triggered_by="king-archon-001",
            timestamp=datetime.now(timezone.utc),
        )

        assert transition.motion_id == motion_id
        assert transition.from_state == GovernanceState.INTRODUCED
        assert transition.to_state == GovernanceState.DELIBERATING
        assert transition.triggered_by == "king-archon-001"
        assert transition.transition_id is not None
        assert transition.transitioned_at is not None

    def test_transition_is_frozen(self) -> None:
        """StateTransition is immutable."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            StateTransition,
        )

        transition = StateTransition.create(
            motion_id=uuid4(),
            from_state=GovernanceState.INTRODUCED,
            to_state=GovernanceState.DELIBERATING,
            triggered_by="king-archon-001",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            transition.triggered_by = "another-archon"  # type: ignore

    def test_transition_to_dict(self) -> None:
        """StateTransition serializes to dictionary."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            StateTransition,
        )

        motion_id = uuid4()
        transition = StateTransition.create(
            motion_id=motion_id,
            from_state=GovernanceState.INTRODUCED,
            to_state=GovernanceState.DELIBERATING,
            triggered_by="king-archon-001",
            reason="King introduced motion",
            timestamp=datetime.now(timezone.utc),
        )

        d = transition.to_dict()

        assert d["motion_id"] == str(motion_id)
        assert d["from_state"] == "introduced"
        assert d["to_state"] == "deliberating"
        assert d["triggered_by"] == "king-archon-001"
        assert d["reason"] == "King introduced motion"


class TestMotionStateRecord:
    """Test MotionStateRecord dataclass."""

    def test_create_motion_state_record(self) -> None:
        """MotionStateRecord holds complete state info."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            MotionStateRecord,
        )

        motion_id = uuid4()
        record = MotionStateRecord(
            motion_id=motion_id,
            current_state=GovernanceState.DELIBERATING,
            history=(),
            entered_state_at=datetime.now(timezone.utc),
            is_terminal=False,
        )

        assert record.motion_id == motion_id
        assert record.current_state == GovernanceState.DELIBERATING
        assert not record.is_terminal

    def test_available_transitions_property(self) -> None:
        """available_transitions returns valid next states."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            MotionStateRecord,
        )

        record = MotionStateRecord(
            motion_id=uuid4(),
            current_state=GovernanceState.INTRODUCED,
            history=(),
            entered_state_at=datetime.now(timezone.utc),
            is_terminal=False,
        )

        assert record.available_transitions == [GovernanceState.DELIBERATING]

    def test_terminal_state_no_available_transitions(self) -> None:
        """Terminal states have no available transitions."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            MotionStateRecord,
        )

        record = MotionStateRecord(
            motion_id=uuid4(),
            current_state=GovernanceState.REJECTED,
            history=(),
            entered_state_at=datetime.now(timezone.utc),
            is_terminal=True,
        )

        assert record.available_transitions == []


class TestTransitionRejection:
    """Test TransitionRejection dataclass."""

    def test_create_rejection(self) -> None:
        """TransitionRejection.create() records rejection details."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            TransitionRejection,
        )

        motion_id = uuid4()
        rejection = TransitionRejection.create(
            motion_id=motion_id,
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.EXECUTING,
            reason="Skip not allowed per FR-GOV-23",
            skipped_states=[GovernanceState.DELIBERATING, GovernanceState.PLANNING],
            timestamp=datetime.now(timezone.utc),
        )

        assert rejection.motion_id == motion_id
        assert rejection.current_state == GovernanceState.INTRODUCED
        assert rejection.attempted_state == GovernanceState.EXECUTING
        assert rejection.prd_reference == "FR-GOV-23"
        assert rejection.rejected_by_system is True
        assert len(rejection.skipped_states) == 2

    def test_rejection_is_frozen(self) -> None:
        """TransitionRejection is immutable."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            TransitionRejection,
        )

        rejection = TransitionRejection.create(
            motion_id=uuid4(),
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.EXECUTING,
            reason="Skip not allowed",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            rejection.reason = "modified"  # type: ignore


class TestTransitionErrors:
    """Test transition error classes."""

    def test_invalid_transition_error(self) -> None:
        """InvalidTransitionError includes context."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            InvalidTransitionError,
        )

        motion_id = uuid4()
        error = InvalidTransitionError(
            motion_id=motion_id,
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.EXECUTING,
            reason="Skip not allowed",
            skipped_states=[GovernanceState.DELIBERATING],
        )

        assert error.motion_id == motion_id
        assert error.current_state == GovernanceState.INTRODUCED
        assert error.attempted_state == GovernanceState.EXECUTING
        assert "Skip not allowed" in str(error)

    def test_terminal_state_error(self) -> None:
        """TerminalStateError includes motion and state."""
        from src.application.ports.governance_state_machine import (
            GovernanceState,
            TerminalStateError,
        )

        motion_id = uuid4()
        error = TerminalStateError(
            motion_id=motion_id,
            current_state=GovernanceState.REJECTED,
        )

        assert error.motion_id == motion_id
        assert error.current_state == GovernanceState.REJECTED
        assert "terminal state" in str(error).lower()
