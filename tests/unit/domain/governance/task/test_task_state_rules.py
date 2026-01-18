"""Unit tests for TaskTransitionRules.

Story: consent-gov-2.1: Task State Machine Domain Model

Tests:
- AC7: Transition rules defined in separate TaskTransitionRules class
- AC8: Unit tests for all valid state transitions
- AC9: Unit tests for invalid transition rejection
"""

from src.domain.governance.task.task_state import TaskStatus
from src.domain.governance.task.task_state_rules import TaskTransitionRules


class TestValidTransitions:
    """AC8: Unit tests for all valid state transitions."""

    def test_authorized_can_transition_to_activated(self):
        """authorized → activated is valid."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.AUTHORIZED, TaskStatus.ACTIVATED
        )

    def test_authorized_can_transition_to_nullified(self):
        """authorized → nullified is valid (pre-consent halt per FR22-FR27)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.AUTHORIZED, TaskStatus.NULLIFIED
        )

    def test_activated_can_transition_to_routed(self):
        """activated → routed is valid."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ACTIVATED, TaskStatus.ROUTED
        )

    def test_activated_can_transition_to_nullified(self):
        """activated → nullified is valid (pre-consent halt)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ACTIVATED, TaskStatus.NULLIFIED
        )

    def test_routed_can_transition_to_accepted(self):
        """routed → accepted is valid (consent gate)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ROUTED, TaskStatus.ACCEPTED
        )

    def test_routed_can_transition_to_declined(self):
        """routed → declined is valid (explicit decline or TTL)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ROUTED, TaskStatus.DECLINED
        )

    def test_routed_can_transition_to_nullified(self):
        """routed → nullified is valid (pre-consent halt)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ROUTED, TaskStatus.NULLIFIED
        )

    def test_accepted_can_transition_to_in_progress(self):
        """accepted → in_progress is valid."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS
        )

    def test_accepted_can_transition_to_declined(self):
        """accepted → declined is valid (changed mind)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ACCEPTED, TaskStatus.DECLINED
        )

    def test_accepted_can_transition_to_quarantined(self):
        """accepted → quarantined is valid (post-consent halt)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.ACCEPTED, TaskStatus.QUARANTINED
        )

    def test_in_progress_can_transition_to_reported(self):
        """in_progress → reported is valid."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.IN_PROGRESS, TaskStatus.REPORTED
        )

    def test_in_progress_can_transition_to_quarantined(self):
        """in_progress → quarantined is valid (halt or timeout)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.IN_PROGRESS, TaskStatus.QUARANTINED
        )

    def test_reported_can_transition_to_aggregated(self):
        """reported → aggregated is valid (multi-cluster)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.REPORTED, TaskStatus.AGGREGATED
        )

    def test_reported_can_transition_to_completed(self):
        """reported → completed is valid (single-cluster)."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.REPORTED, TaskStatus.COMPLETED
        )

    def test_aggregated_can_transition_to_completed(self):
        """aggregated → completed is valid."""
        assert TaskTransitionRules.is_valid_transition(
            TaskStatus.AGGREGATED, TaskStatus.COMPLETED
        )


class TestInvalidTransitions:
    """AC9: Unit tests for invalid transition rejection."""

    def test_authorized_cannot_jump_to_completed(self):
        """authorized → completed is invalid."""
        assert not TaskTransitionRules.is_valid_transition(
            TaskStatus.AUTHORIZED, TaskStatus.COMPLETED
        )

    def test_authorized_cannot_jump_to_accepted(self):
        """authorized → accepted is invalid (must go through routed)."""
        assert not TaskTransitionRules.is_valid_transition(
            TaskStatus.AUTHORIZED, TaskStatus.ACCEPTED
        )

    def test_routed_cannot_jump_to_completed(self):
        """routed → completed is invalid (must go through accepted)."""
        assert not TaskTransitionRules.is_valid_transition(
            TaskStatus.ROUTED, TaskStatus.COMPLETED
        )

    def test_completed_cannot_transition_anywhere(self):
        """completed is terminal - no transitions allowed."""
        for status in TaskStatus:
            assert not TaskTransitionRules.is_valid_transition(
                TaskStatus.COMPLETED, status
            )

    def test_declined_cannot_transition_anywhere(self):
        """declined is terminal - no transitions allowed."""
        for status in TaskStatus:
            assert not TaskTransitionRules.is_valid_transition(
                TaskStatus.DECLINED, status
            )

    def test_quarantined_cannot_transition_anywhere(self):
        """quarantined is terminal - no transitions allowed."""
        for status in TaskStatus:
            assert not TaskTransitionRules.is_valid_transition(
                TaskStatus.QUARANTINED, status
            )

    def test_nullified_cannot_transition_anywhere(self):
        """nullified is terminal - no transitions allowed."""
        for status in TaskStatus:
            assert not TaskTransitionRules.is_valid_transition(
                TaskStatus.NULLIFIED, status
            )

    def test_backwards_transitions_invalid(self):
        """Cannot transition backwards in the state machine."""
        assert not TaskTransitionRules.is_valid_transition(
            TaskStatus.ACTIVATED, TaskStatus.AUTHORIZED
        )
        assert not TaskTransitionRules.is_valid_transition(
            TaskStatus.ACCEPTED, TaskStatus.ROUTED
        )
        assert not TaskTransitionRules.is_valid_transition(
            TaskStatus.IN_PROGRESS, TaskStatus.ACCEPTED
        )


class TestGetAllowedTransitions:
    """Tests for get_allowed_transitions() method."""

    def test_authorized_allowed_transitions(self):
        """authorized has correct allowed transitions (including halt)."""
        allowed = TaskTransitionRules.get_allowed_transitions(TaskStatus.AUTHORIZED)
        assert allowed == frozenset(
            {
                TaskStatus.ACTIVATED,
                TaskStatus.NULLIFIED,  # Halt (pre-consent) per FR22-FR27
            }
        )

    def test_routed_allowed_transitions(self):
        """routed has correct allowed transitions (consent gate)."""
        allowed = TaskTransitionRules.get_allowed_transitions(TaskStatus.ROUTED)
        assert allowed == frozenset(
            {
                TaskStatus.ACCEPTED,
                TaskStatus.DECLINED,
                TaskStatus.NULLIFIED,
            }
        )

    def test_terminal_states_have_empty_allowed(self):
        """Terminal states have no allowed transitions."""
        for terminal in [
            TaskStatus.COMPLETED,
            TaskStatus.DECLINED,
            TaskStatus.QUARANTINED,
            TaskStatus.NULLIFIED,
        ]:
            allowed = TaskTransitionRules.get_allowed_transitions(terminal)
            assert allowed == frozenset()


class TestConsentGates:
    """Tests for consent gate detection."""

    def test_routed_is_consent_gate(self):
        """routed is identified as consent gate."""
        assert TaskTransitionRules.is_consent_gate(TaskStatus.ROUTED)

    def test_authorized_is_not_consent_gate(self):
        """authorized is not a consent gate."""
        assert not TaskTransitionRules.is_consent_gate(TaskStatus.AUTHORIZED)

    def test_accepted_is_not_consent_gate(self):
        """accepted is not a consent gate (consent already given)."""
        assert not TaskTransitionRules.is_consent_gate(TaskStatus.ACCEPTED)


class TestHaltTargets:
    """Tests for halt target determination."""

    def test_pre_consent_halt_target_is_nullified(self):
        """Pre-consent states halt to nullified."""
        for status in [TaskStatus.AUTHORIZED, TaskStatus.ACTIVATED, TaskStatus.ROUTED]:
            target = TaskTransitionRules.get_halt_target(status)
            assert target == TaskStatus.NULLIFIED

    def test_post_consent_halt_target_is_quarantined(self):
        """Post-consent states halt to quarantined."""
        for status in [
            TaskStatus.ACCEPTED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.REPORTED,
            TaskStatus.AGGREGATED,
        ]:
            target = TaskTransitionRules.get_halt_target(status)
            assert target == TaskStatus.QUARANTINED

    def test_terminal_states_have_no_halt_target(self):
        """Terminal states have no halt target (already finished)."""
        for status in [
            TaskStatus.COMPLETED,
            TaskStatus.DECLINED,
            TaskStatus.QUARANTINED,
            TaskStatus.NULLIFIED,
        ]:
            target = TaskTransitionRules.get_halt_target(status)
            assert target is None


class TestDeclineCapability:
    """Tests for can_decline() method."""

    def test_routed_can_decline(self):
        """routed state can decline."""
        assert TaskTransitionRules.can_decline(TaskStatus.ROUTED)

    def test_accepted_can_decline(self):
        """accepted state can decline (changed mind)."""
        assert TaskTransitionRules.can_decline(TaskStatus.ACCEPTED)

    def test_authorized_cannot_decline(self):
        """authorized state cannot decline (not offered yet)."""
        assert not TaskTransitionRules.can_decline(TaskStatus.AUTHORIZED)

    def test_in_progress_cannot_decline(self):
        """in_progress state cannot decline (work started)."""
        assert not TaskTransitionRules.can_decline(TaskStatus.IN_PROGRESS)


class TestNormalFlowTransitions:
    """Tests for is_normal_flow_transition() method."""

    def test_happy_path_transitions_are_normal_flow(self):
        """Happy path transitions are identified as normal flow."""
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.AUTHORIZED, TaskStatus.ACTIVATED
        )
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.ACTIVATED, TaskStatus.ROUTED
        )
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.ROUTED, TaskStatus.ACCEPTED
        )
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS
        )
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.IN_PROGRESS, TaskStatus.REPORTED
        )
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.REPORTED, TaskStatus.AGGREGATED
        )
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.AGGREGATED, TaskStatus.COMPLETED
        )

    def test_direct_completion_is_normal_flow(self):
        """reported → completed is normal flow (single-cluster)."""
        assert TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.REPORTED, TaskStatus.COMPLETED
        )

    def test_decline_is_not_normal_flow(self):
        """Decline transitions are not normal flow."""
        assert not TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.ROUTED, TaskStatus.DECLINED
        )
        assert not TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.ACCEPTED, TaskStatus.DECLINED
        )

    def test_halt_is_not_normal_flow(self):
        """Halt transitions are not normal flow."""
        assert not TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.ACTIVATED, TaskStatus.NULLIFIED
        )
        assert not TaskTransitionRules.is_normal_flow_transition(
            TaskStatus.IN_PROGRESS, TaskStatus.QUARANTINED
        )


class TestAllValidTransitionsCovered:
    """Meta-test to ensure all valid transitions are covered."""

    def test_all_transitions_have_tests(self):
        """Every valid transition in VALID_TRANSITIONS is tested above."""
        # This test documents the complete transition matrix
        expected_transitions = {
            (TaskStatus.AUTHORIZED, TaskStatus.ACTIVATED),
            (
                TaskStatus.AUTHORIZED,
                TaskStatus.NULLIFIED,
            ),  # Halt (pre-consent) per FR22-FR27
            (TaskStatus.ACTIVATED, TaskStatus.ROUTED),
            (TaskStatus.ACTIVATED, TaskStatus.NULLIFIED),
            (TaskStatus.ROUTED, TaskStatus.ACCEPTED),
            (TaskStatus.ROUTED, TaskStatus.DECLINED),
            (TaskStatus.ROUTED, TaskStatus.NULLIFIED),
            (TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS),
            (TaskStatus.ACCEPTED, TaskStatus.DECLINED),
            (TaskStatus.ACCEPTED, TaskStatus.QUARANTINED),
            (TaskStatus.IN_PROGRESS, TaskStatus.REPORTED),
            (TaskStatus.IN_PROGRESS, TaskStatus.QUARANTINED),
            (TaskStatus.REPORTED, TaskStatus.AGGREGATED),
            (TaskStatus.REPORTED, TaskStatus.COMPLETED),
            (TaskStatus.AGGREGATED, TaskStatus.COMPLETED),
        }

        # Verify all expected transitions are valid
        for current, target in expected_transitions:
            assert TaskTransitionRules.is_valid_transition(current, target), (
                f"Expected {current.value} → {target.value} to be valid"
            )

        # Count total valid transitions from VALID_TRANSITIONS
        total_valid = sum(
            len(targets) for targets in TaskTransitionRules.VALID_TRANSITIONS.values()
        )
        assert total_valid == len(expected_transitions), (
            f"Expected {len(expected_transitions)} valid transitions, "
            f"found {total_valid}"
        )
