"""Unit tests for CessationStatus.

Story: consent-gov-8.1: System Cessation Trigger
AC6: Cessation trigger is irreversible (no "undo")
"""

from src.domain.governance.cessation import CessationStatus


class TestCessationStatusValues:
    """Tests for CessationStatus enum values."""

    def test_active_status_exists(self) -> None:
        """ACTIVE status exists."""
        assert CessationStatus.ACTIVE == "active"

    def test_cessation_triggered_status_exists(self) -> None:
        """CESSATION_TRIGGERED status exists."""
        assert CessationStatus.CESSATION_TRIGGERED == "cessation_triggered"

    def test_ceased_status_exists(self) -> None:
        """CEASED status exists."""
        assert CessationStatus.CEASED == "ceased"

    def test_only_three_statuses(self) -> None:
        """Only three valid statuses exist (no cancelled, paused, etc.)."""
        assert len(CessationStatus) == 3


class TestCessationStatusProperties:
    """Tests for CessationStatus property methods."""

    def test_is_active_true_for_active(self) -> None:
        """is_active returns True for ACTIVE status."""
        assert CessationStatus.ACTIVE.is_active is True

    def test_is_active_false_for_triggered(self) -> None:
        """is_active returns False for CESSATION_TRIGGERED status."""
        assert CessationStatus.CESSATION_TRIGGERED.is_active is False

    def test_is_active_false_for_ceased(self) -> None:
        """is_active returns False for CEASED status."""
        assert CessationStatus.CEASED.is_active is False

    def test_is_ceasing_true_for_triggered(self) -> None:
        """is_ceasing returns True for CESSATION_TRIGGERED status."""
        assert CessationStatus.CESSATION_TRIGGERED.is_ceasing is True

    def test_is_ceasing_false_for_active(self) -> None:
        """is_ceasing returns False for ACTIVE status."""
        assert CessationStatus.ACTIVE.is_ceasing is False

    def test_is_ceasing_false_for_ceased(self) -> None:
        """is_ceasing returns False for CEASED status."""
        assert CessationStatus.CEASED.is_ceasing is False

    def test_is_ceased_true_for_ceased(self) -> None:
        """is_ceased returns True for CEASED status."""
        assert CessationStatus.CEASED.is_ceased is True

    def test_is_ceased_false_for_active(self) -> None:
        """is_ceased returns False for ACTIVE status."""
        assert CessationStatus.ACTIVE.is_ceased is False

    def test_is_ceased_false_for_triggered(self) -> None:
        """is_ceased returns False for CESSATION_TRIGGERED status."""
        assert CessationStatus.CESSATION_TRIGGERED.is_ceased is False

    def test_is_terminal_only_for_ceased(self) -> None:
        """Only CEASED status is terminal."""
        assert CessationStatus.ACTIVE.is_terminal is False
        assert CessationStatus.CESSATION_TRIGGERED.is_terminal is False
        assert CessationStatus.CEASED.is_terminal is True


class TestMotionBlocking:
    """Tests for allows_new_motions property."""

    def test_active_allows_new_motions(self) -> None:
        """ACTIVE status allows new Motion Seeds."""
        assert CessationStatus.ACTIVE.allows_new_motions is True

    def test_triggered_blocks_new_motions(self) -> None:
        """CESSATION_TRIGGERED status blocks new Motion Seeds."""
        assert CessationStatus.CESSATION_TRIGGERED.allows_new_motions is False

    def test_ceased_blocks_new_motions(self) -> None:
        """CEASED status blocks new Motion Seeds."""
        assert CessationStatus.CEASED.allows_new_motions is False


class TestExecutionBlocking:
    """Tests for allows_execution property."""

    def test_active_allows_execution(self) -> None:
        """ACTIVE status allows execution."""
        assert CessationStatus.ACTIVE.allows_execution is True

    def test_triggered_allows_execution(self) -> None:
        """CESSATION_TRIGGERED allows execution (existing operations)."""
        assert CessationStatus.CESSATION_TRIGGERED.allows_execution is True

    def test_ceased_blocks_execution(self) -> None:
        """CEASED status blocks execution."""
        assert CessationStatus.CEASED.allows_execution is False


class TestStateTransitions:
    """Tests for can_transition_to method (forward-only)."""

    def test_active_can_transition_to_triggered(self) -> None:
        """ACTIVE can transition to CESSATION_TRIGGERED."""
        assert CessationStatus.ACTIVE.can_transition_to(
            CessationStatus.CESSATION_TRIGGERED
        )

    def test_active_cannot_transition_to_ceased_directly(self) -> None:
        """ACTIVE cannot transition directly to CEASED."""
        assert not CessationStatus.ACTIVE.can_transition_to(CessationStatus.CEASED)

    def test_active_cannot_stay_active(self) -> None:
        """ACTIVE cannot 'transition' to ACTIVE (no-op not allowed)."""
        assert not CessationStatus.ACTIVE.can_transition_to(CessationStatus.ACTIVE)

    def test_triggered_can_transition_to_ceased(self) -> None:
        """CESSATION_TRIGGERED can transition to CEASED."""
        assert CessationStatus.CESSATION_TRIGGERED.can_transition_to(
            CessationStatus.CEASED
        )

    def test_triggered_cannot_transition_back_to_active(self) -> None:
        """CESSATION_TRIGGERED cannot transition back to ACTIVE (irreversible)."""
        assert not CessationStatus.CESSATION_TRIGGERED.can_transition_to(
            CessationStatus.ACTIVE
        )

    def test_ceased_cannot_transition_anywhere(self) -> None:
        """CEASED cannot transition to any state (terminal)."""
        assert not CessationStatus.CEASED.can_transition_to(CessationStatus.ACTIVE)
        assert not CessationStatus.CEASED.can_transition_to(
            CessationStatus.CESSATION_TRIGGERED
        )
        assert not CessationStatus.CEASED.can_transition_to(CessationStatus.CEASED)


class TestIrreversibility:
    """Tests ensuring cessation is forward-only (AC6)."""

    def test_no_reverse_transitions_from_triggered(self) -> None:
        """No reverse transitions allowed from CESSATION_TRIGGERED."""
        triggered = CessationStatus.CESSATION_TRIGGERED
        # Cannot go back to ACTIVE
        assert not triggered.can_transition_to(CessationStatus.ACTIVE)

    def test_no_transitions_from_ceased(self) -> None:
        """No transitions allowed from CEASED (terminal)."""
        ceased = CessationStatus.CEASED
        assert not ceased.can_transition_to(CessationStatus.ACTIVE)
        assert not ceased.can_transition_to(CessationStatus.CESSATION_TRIGGERED)

    def test_forward_only_path(self) -> None:
        """Only forward path exists: ACTIVE → TRIGGERED → CEASED."""
        # Valid path
        assert CessationStatus.ACTIVE.can_transition_to(
            CessationStatus.CESSATION_TRIGGERED
        )
        assert CessationStatus.CESSATION_TRIGGERED.can_transition_to(
            CessationStatus.CEASED
        )

        # No reverse path
        assert not CessationStatus.CEASED.can_transition_to(
            CessationStatus.CESSATION_TRIGGERED
        )
        assert not CessationStatus.CESSATION_TRIGGERED.can_transition_to(
            CessationStatus.ACTIVE
        )

    def test_no_skip_transitions(self) -> None:
        """Cannot skip states (must go through TRIGGERED)."""
        # Cannot skip CESSATION_TRIGGERED
        assert not CessationStatus.ACTIVE.can_transition_to(CessationStatus.CEASED)
