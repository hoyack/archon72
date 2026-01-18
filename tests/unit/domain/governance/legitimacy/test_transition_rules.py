"""Unit tests for band transition rules.

Tests AC2: State machine enforces valid transitions only
Tests AC5: Downward transitions allowed automatically
Tests AC6: Upward transitions require explicit acknowledgment
"""

import pytest

from src.domain.governance.legitimacy.band_transition_rules import (
    BandTransitionRules,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.transition_type import TransitionType


class TestAutomaticDownwardTransitions:
    """Tests for automatic (decay) transitions (AC5)."""

    def test_automatic_downward_valid(self) -> None:
        """Automatic downward transitions are valid."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.STABLE,
            target=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
        )
        assert result.is_valid

    def test_automatic_skip_bands_allowed(self) -> None:
        """Automatic transitions can skip multiple bands."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.STABLE,
            target=LegitimacyBand.FAILED,
            transition_type=TransitionType.AUTOMATIC,
        )
        assert result.is_valid

    def test_automatic_to_failed_valid(self) -> None:
        """Any band can automatically transition to FAILED."""
        for band in [
            LegitimacyBand.STABLE,
            LegitimacyBand.STRAINED,
            LegitimacyBand.ERODING,
            LegitimacyBand.COMPROMISED,
        ]:
            result = BandTransitionRules.validate_transition(
                current=band,
                target=LegitimacyBand.FAILED,
                transition_type=TransitionType.AUTOMATIC,
            )
            assert result.is_valid, f"Transition from {band} to FAILED should be valid"


class TestAutomaticUpwardTransitions:
    """Tests for automatic upward transitions (should fail) (AC6)."""

    def test_automatic_upward_invalid(self) -> None:
        """Automatic upward transitions are invalid."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.STRAINED,
            target=LegitimacyBand.STABLE,
            transition_type=TransitionType.AUTOMATIC,
        )
        assert not result.is_valid
        assert "acknowledgment" in result.reason.lower()

    def test_automatic_upward_all_bands_invalid(self) -> None:
        """All automatic upward transitions are invalid."""
        test_cases = [
            (LegitimacyBand.STRAINED, LegitimacyBand.STABLE),
            (LegitimacyBand.ERODING, LegitimacyBand.STRAINED),
            (LegitimacyBand.COMPROMISED, LegitimacyBand.ERODING),
        ]

        for current, target in test_cases:
            result = BandTransitionRules.validate_transition(
                current=current,
                target=target,
                transition_type=TransitionType.AUTOMATIC,
            )
            assert not result.is_valid, (
                f"Automatic upward from {current} to {target} should be invalid"
            )


class TestAcknowledgedUpwardTransitions:
    """Tests for acknowledged (restoration) transitions (AC6)."""

    def test_acknowledged_upward_one_step_valid(self) -> None:
        """Acknowledged upward transitions one step are valid."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.STRAINED,
            target=LegitimacyBand.STABLE,
            transition_type=TransitionType.ACKNOWLEDGED,
        )
        assert result.is_valid

    def test_acknowledged_upward_all_valid_steps(self) -> None:
        """All valid one-step restorations are valid when acknowledged."""
        test_cases = [
            (LegitimacyBand.STRAINED, LegitimacyBand.STABLE),
            (LegitimacyBand.ERODING, LegitimacyBand.STRAINED),
            (LegitimacyBand.COMPROMISED, LegitimacyBand.ERODING),
        ]

        for current, target in test_cases:
            result = BandTransitionRules.validate_transition(
                current=current,
                target=target,
                transition_type=TransitionType.ACKNOWLEDGED,
            )
            assert result.is_valid, (
                f"Acknowledged upward from {current} to {target} should be valid"
            )

    def test_acknowledged_skip_bands_invalid(self) -> None:
        """Acknowledged upward transitions cannot skip bands."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.ERODING,
            target=LegitimacyBand.STABLE,
            transition_type=TransitionType.ACKNOWLEDGED,
        )
        assert not result.is_valid
        assert "one step" in result.reason.lower()

    def test_acknowledged_skip_two_bands_invalid(self) -> None:
        """Acknowledged upward cannot skip two bands."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.COMPROMISED,
            target=LegitimacyBand.STRAINED,
            transition_type=TransitionType.ACKNOWLEDGED,
        )
        assert not result.is_valid


class TestTerminalFailedState:
    """Tests for FAILED as terminal state."""

    def test_failed_cannot_transition(self) -> None:
        """FAILED state cannot transition to any band."""
        for target in LegitimacyBand:
            for transition_type in TransitionType:
                result = BandTransitionRules.validate_transition(
                    current=LegitimacyBand.FAILED,
                    target=target,
                    transition_type=transition_type,
                )
                assert not result.is_valid, (
                    f"FAILED should not transition to {target} ({transition_type})"
                )

    def test_failed_terminal_message(self) -> None:
        """FAILED terminal state has proper error message."""
        result = BandTransitionRules.validate_transition(
            current=LegitimacyBand.FAILED,
            target=LegitimacyBand.COMPROMISED,
            transition_type=TransitionType.ACKNOWLEDGED,
        )
        assert "terminal" in result.reason.lower()
        assert "reconstitution" in result.reason.lower()


class TestSameBandTransition:
    """Tests for transitions to the same band."""

    def test_same_band_invalid(self) -> None:
        """Transitioning to same band is invalid."""
        for band in LegitimacyBand:
            if band == LegitimacyBand.FAILED:
                continue  # FAILED has its own error

            result = BandTransitionRules.validate_transition(
                current=band,
                target=band,
                transition_type=TransitionType.AUTOMATIC,
            )
            assert not result.is_valid, f"Same band {band} should be invalid"
            assert "already" in result.reason.lower()


class TestHelperMethods:
    """Tests for helper methods."""

    def test_is_decay_true_for_downward(self) -> None:
        """is_decay returns True for downward transitions."""
        assert BandTransitionRules.is_decay(
            LegitimacyBand.STABLE, LegitimacyBand.STRAINED
        )
        assert BandTransitionRules.is_decay(
            LegitimacyBand.STABLE, LegitimacyBand.FAILED
        )
        assert BandTransitionRules.is_decay(
            LegitimacyBand.COMPROMISED, LegitimacyBand.FAILED
        )

    def test_is_decay_false_for_upward(self) -> None:
        """is_decay returns False for upward transitions."""
        assert not BandTransitionRules.is_decay(
            LegitimacyBand.STRAINED, LegitimacyBand.STABLE
        )
        assert not BandTransitionRules.is_decay(
            LegitimacyBand.FAILED, LegitimacyBand.STABLE
        )

    def test_is_restoration_true_for_upward(self) -> None:
        """is_restoration returns True for upward transitions."""
        assert BandTransitionRules.is_restoration(
            LegitimacyBand.STRAINED, LegitimacyBand.STABLE
        )
        assert BandTransitionRules.is_restoration(
            LegitimacyBand.COMPROMISED, LegitimacyBand.ERODING
        )

    def test_is_restoration_false_for_downward(self) -> None:
        """is_restoration returns False for downward transitions."""
        assert not BandTransitionRules.is_restoration(
            LegitimacyBand.STABLE, LegitimacyBand.STRAINED
        )

    def test_get_next_restoration_target_from_strained(self) -> None:
        """Next restoration target from STRAINED is STABLE."""
        target = BandTransitionRules.get_next_restoration_target(
            LegitimacyBand.STRAINED
        )
        assert target == LegitimacyBand.STABLE

    def test_get_next_restoration_target_from_compromised(self) -> None:
        """Next restoration target from COMPROMISED is ERODING."""
        target = BandTransitionRules.get_next_restoration_target(
            LegitimacyBand.COMPROMISED
        )
        assert target == LegitimacyBand.ERODING

    def test_get_next_restoration_target_from_stable_is_none(self) -> None:
        """No restoration target from STABLE."""
        target = BandTransitionRules.get_next_restoration_target(LegitimacyBand.STABLE)
        assert target is None

    def test_get_next_restoration_target_from_failed_is_none(self) -> None:
        """No restoration target from FAILED (terminal)."""
        target = BandTransitionRules.get_next_restoration_target(LegitimacyBand.FAILED)
        assert target is None

    def test_calculate_decay_target_one_step(self) -> None:
        """Calculate decay target one step down."""
        target = BandTransitionRules.calculate_decay_target(
            LegitimacyBand.STABLE, severity_increase=1
        )
        assert target == LegitimacyBand.STRAINED

    def test_calculate_decay_target_multiple_steps(self) -> None:
        """Calculate decay target multiple steps."""
        target = BandTransitionRules.calculate_decay_target(
            LegitimacyBand.STABLE, severity_increase=3
        )
        assert target == LegitimacyBand.COMPROMISED

    def test_calculate_decay_target_capped_at_failed(self) -> None:
        """Decay target is capped at FAILED."""
        target = BandTransitionRules.calculate_decay_target(
            LegitimacyBand.STABLE, severity_increase=10
        )
        assert target == LegitimacyBand.FAILED

    def test_calculate_decay_from_failed_raises(self) -> None:
        """Cannot calculate decay from FAILED."""
        with pytest.raises(ValueError, match="Cannot decay from FAILED"):
            BandTransitionRules.calculate_decay_target(LegitimacyBand.FAILED)

    def test_calculate_decay_invalid_severity_raises(self) -> None:
        """Invalid severity_increase raises ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            BandTransitionRules.calculate_decay_target(
                LegitimacyBand.STABLE, severity_increase=0
            )

        with pytest.raises(ValueError, match="at least 1"):
            BandTransitionRules.calculate_decay_target(
                LegitimacyBand.STABLE, severity_increase=-1
            )
