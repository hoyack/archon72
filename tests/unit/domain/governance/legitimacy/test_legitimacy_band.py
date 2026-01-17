"""Unit tests for LegitimacyBand enum.

Tests AC1: Five bands defined
Tests AC8: Band definitions include severity and description
"""

import pytest

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand


class TestLegitimacyBandDefinitions:
    """Tests for band enum definitions."""

    def test_all_five_bands_exist(self) -> None:
        """All five bands are defined (AC1)."""
        assert len(LegitimacyBand) == 5

        bands = list(LegitimacyBand)
        assert LegitimacyBand.STABLE in bands
        assert LegitimacyBand.STRAINED in bands
        assert LegitimacyBand.ERODING in bands
        assert LegitimacyBand.COMPROMISED in bands
        assert LegitimacyBand.FAILED in bands

    def test_band_values_are_strings(self) -> None:
        """Band values are lowercase strings."""
        assert LegitimacyBand.STABLE.value == "stable"
        assert LegitimacyBand.STRAINED.value == "strained"
        assert LegitimacyBand.ERODING.value == "eroding"
        assert LegitimacyBand.COMPROMISED.value == "compromised"
        assert LegitimacyBand.FAILED.value == "failed"


class TestLegitimacyBandSeverity:
    """Tests for band severity levels (AC8)."""

    def test_severity_ordering(self) -> None:
        """Severity increases from STABLE (0) to FAILED (4)."""
        assert LegitimacyBand.STABLE.severity == 0
        assert LegitimacyBand.STRAINED.severity == 1
        assert LegitimacyBand.ERODING.severity == 2
        assert LegitimacyBand.COMPROMISED.severity == 3
        assert LegitimacyBand.FAILED.severity == 4

    def test_severity_is_monotonic(self) -> None:
        """Each band has a unique severity level."""
        severities = [band.severity for band in LegitimacyBand]
        assert severities == sorted(severities)
        assert len(set(severities)) == len(severities)

    def test_from_severity_returns_correct_band(self) -> None:
        """Can retrieve band by severity level."""
        assert LegitimacyBand.from_severity(0) == LegitimacyBand.STABLE
        assert LegitimacyBand.from_severity(1) == LegitimacyBand.STRAINED
        assert LegitimacyBand.from_severity(2) == LegitimacyBand.ERODING
        assert LegitimacyBand.from_severity(3) == LegitimacyBand.COMPROMISED
        assert LegitimacyBand.from_severity(4) == LegitimacyBand.FAILED

    def test_from_severity_invalid_raises(self) -> None:
        """Invalid severity raises ValueError."""
        with pytest.raises(ValueError, match="Invalid severity level"):
            LegitimacyBand.from_severity(-1)

        with pytest.raises(ValueError, match="Invalid severity level"):
            LegitimacyBand.from_severity(5)

        with pytest.raises(ValueError, match="Invalid severity level"):
            LegitimacyBand.from_severity(100)


class TestLegitimacyBandDescription:
    """Tests for band descriptions (AC8)."""

    def test_each_band_has_description(self) -> None:
        """Every band has a non-empty description."""
        for band in LegitimacyBand:
            assert band.description
            assert isinstance(band.description, str)
            assert len(band.description) > 10  # Meaningful description

    def test_descriptions_are_distinct(self) -> None:
        """Each band has a unique description."""
        descriptions = [band.description for band in LegitimacyBand]
        assert len(set(descriptions)) == len(descriptions)

    def test_specific_descriptions(self) -> None:
        """Descriptions match expected content."""
        assert "Normal operation" in LegitimacyBand.STABLE.description
        assert "Minor issues" in LegitimacyBand.STRAINED.description
        assert "Significant issues" in LegitimacyBand.ERODING.description
        assert "Critical issues" in LegitimacyBand.COMPROMISED.description
        assert "halt recommended" in LegitimacyBand.FAILED.description.lower()


class TestLegitimacyBandProperties:
    """Tests for band helper properties."""

    def test_is_terminal_only_for_failed(self) -> None:
        """Only FAILED is terminal."""
        assert not LegitimacyBand.STABLE.is_terminal
        assert not LegitimacyBand.STRAINED.is_terminal
        assert not LegitimacyBand.ERODING.is_terminal
        assert not LegitimacyBand.COMPROMISED.is_terminal
        assert LegitimacyBand.FAILED.is_terminal

    def test_is_healthy_for_low_severity(self) -> None:
        """Only STABLE and STRAINED are healthy."""
        assert LegitimacyBand.STABLE.is_healthy
        assert LegitimacyBand.STRAINED.is_healthy
        assert not LegitimacyBand.ERODING.is_healthy
        assert not LegitimacyBand.COMPROMISED.is_healthy
        assert not LegitimacyBand.FAILED.is_healthy

    def test_is_critical_for_high_severity(self) -> None:
        """Only COMPROMISED and FAILED are critical."""
        assert not LegitimacyBand.STABLE.is_critical
        assert not LegitimacyBand.STRAINED.is_critical
        assert not LegitimacyBand.ERODING.is_critical
        assert LegitimacyBand.COMPROMISED.is_critical
        assert LegitimacyBand.FAILED.is_critical


class TestLegitimacyBandTransitionValidity:
    """Tests for can_transition_to method."""

    def test_downward_transition_allowed(self) -> None:
        """Downward transitions are structurally valid (AC5)."""
        assert LegitimacyBand.STABLE.can_transition_to(LegitimacyBand.STRAINED)
        assert LegitimacyBand.STABLE.can_transition_to(LegitimacyBand.ERODING)
        assert LegitimacyBand.STABLE.can_transition_to(LegitimacyBand.COMPROMISED)
        assert LegitimacyBand.STABLE.can_transition_to(LegitimacyBand.FAILED)

        assert LegitimacyBand.STRAINED.can_transition_to(LegitimacyBand.ERODING)
        assert LegitimacyBand.STRAINED.can_transition_to(LegitimacyBand.FAILED)

        assert LegitimacyBand.ERODING.can_transition_to(LegitimacyBand.COMPROMISED)
        assert LegitimacyBand.ERODING.can_transition_to(LegitimacyBand.FAILED)

        assert LegitimacyBand.COMPROMISED.can_transition_to(LegitimacyBand.FAILED)

    def test_upward_one_step_allowed(self) -> None:
        """Upward transitions one step are structurally valid (AC6)."""
        assert LegitimacyBand.STRAINED.can_transition_to(LegitimacyBand.STABLE)
        assert LegitimacyBand.ERODING.can_transition_to(LegitimacyBand.STRAINED)
        assert LegitimacyBand.COMPROMISED.can_transition_to(LegitimacyBand.ERODING)

    def test_upward_multiple_steps_invalid(self) -> None:
        """Upward transitions multiple steps are invalid."""
        assert not LegitimacyBand.ERODING.can_transition_to(LegitimacyBand.STABLE)
        assert not LegitimacyBand.COMPROMISED.can_transition_to(LegitimacyBand.STABLE)
        assert not LegitimacyBand.COMPROMISED.can_transition_to(LegitimacyBand.STRAINED)

    def test_failed_is_terminal(self) -> None:
        """FAILED cannot transition to any band."""
        for band in LegitimacyBand:
            assert not LegitimacyBand.FAILED.can_transition_to(band)

    def test_same_band_transition_invalid(self) -> None:
        """Cannot transition to the same band."""
        for band in LegitimacyBand:
            assert not band.can_transition_to(band)


class TestLegitimacyBandComparison:
    """Tests for comparison operators."""

    def test_less_than_based_on_severity(self) -> None:
        """Less than compares severity (healthier is less)."""
        assert LegitimacyBand.STABLE < LegitimacyBand.STRAINED
        assert LegitimacyBand.STRAINED < LegitimacyBand.ERODING
        assert LegitimacyBand.ERODING < LegitimacyBand.COMPROMISED
        assert LegitimacyBand.COMPROMISED < LegitimacyBand.FAILED

    def test_greater_than_based_on_severity(self) -> None:
        """Greater than compares severity (sicker is greater)."""
        assert LegitimacyBand.FAILED > LegitimacyBand.COMPROMISED
        assert LegitimacyBand.COMPROMISED > LegitimacyBand.ERODING
        assert LegitimacyBand.ERODING > LegitimacyBand.STRAINED
        assert LegitimacyBand.STRAINED > LegitimacyBand.STABLE

    def test_less_than_or_equal(self) -> None:
        """Less than or equal comparison."""
        assert LegitimacyBand.STABLE <= LegitimacyBand.STABLE
        assert LegitimacyBand.STABLE <= LegitimacyBand.STRAINED
        assert not LegitimacyBand.STRAINED <= LegitimacyBand.STABLE

    def test_greater_than_or_equal(self) -> None:
        """Greater than or equal comparison."""
        assert LegitimacyBand.FAILED >= LegitimacyBand.FAILED
        assert LegitimacyBand.FAILED >= LegitimacyBand.STABLE
        assert not LegitimacyBand.STABLE >= LegitimacyBand.FAILED

    def test_comparison_with_non_band_returns_not_implemented(self) -> None:
        """Comparing with non-band returns NotImplemented."""
        assert LegitimacyBand.STABLE.__lt__(5) == NotImplemented
        assert LegitimacyBand.STABLE.__gt__("stable") == NotImplemented
        assert LegitimacyBand.STABLE.__le__(None) == NotImplemented
        assert LegitimacyBand.STABLE.__ge__([]) == NotImplemented
