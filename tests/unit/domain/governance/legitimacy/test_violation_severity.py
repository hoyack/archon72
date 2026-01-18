"""Unit tests for violation severity domain model.

Tests the ViolationSeverity enum and VIOLATION_SEVERITY_MAP
as specified in consent-gov-5-2 story.
"""

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.violation_severity import (
    VIOLATION_SEVERITY_MAP,
    ViolationSeverity,
    calculate_target_band,
    get_severity_for_violation,
)


class TestViolationSeverityEnum:
    """Tests for ViolationSeverity enum."""

    def test_minor_severity_value(self) -> None:
        """MINOR severity has value 'minor'."""
        assert ViolationSeverity.MINOR.value == "minor"

    def test_major_severity_value(self) -> None:
        """MAJOR severity has value 'major'."""
        assert ViolationSeverity.MAJOR.value == "major"

    def test_critical_severity_value(self) -> None:
        """CRITICAL severity has value 'critical'."""
        assert ViolationSeverity.CRITICAL.value == "critical"

    def test_integrity_severity_value(self) -> None:
        """INTEGRITY severity has value 'integrity'."""
        assert ViolationSeverity.INTEGRITY.value == "integrity"

    def test_bands_to_drop_minor(self) -> None:
        """MINOR violations drop 1 band."""
        assert ViolationSeverity.MINOR.bands_to_drop == 1

    def test_bands_to_drop_major(self) -> None:
        """MAJOR violations drop 2 bands."""
        assert ViolationSeverity.MAJOR.bands_to_drop == 2

    def test_bands_to_drop_critical(self) -> None:
        """CRITICAL violations have no fixed drop (jumps to COMPROMISED)."""
        # Critical has special behavior - no bands_to_drop
        assert ViolationSeverity.CRITICAL.is_jump_to_compromised

    def test_bands_to_drop_integrity(self) -> None:
        """INTEGRITY violations have no fixed drop (immediate FAILED)."""
        # Integrity has special behavior - immediate terminal
        assert ViolationSeverity.INTEGRITY.is_immediate_terminal

    def test_all_severities_have_description(self) -> None:
        """All severities have human-readable descriptions."""
        for severity in ViolationSeverity:
            assert severity.description
            assert isinstance(severity.description, str)
            assert len(severity.description) > 0

    def test_severity_ordering(self) -> None:
        """Severities are ordered by impact (MINOR < MAJOR < CRITICAL < INTEGRITY)."""
        assert ViolationSeverity.MINOR.impact_level == 1
        assert ViolationSeverity.MAJOR.impact_level == 2
        assert ViolationSeverity.CRITICAL.impact_level == 3
        assert ViolationSeverity.INTEGRITY.impact_level == 4


class TestViolationSeverityMap:
    """Tests for violation type to severity mapping."""

    def test_minor_violations_mapped(self) -> None:
        """MINOR violations are mapped correctly."""
        assert (
            VIOLATION_SEVERITY_MAP["task.timeout_without_decline"]
            == ViolationSeverity.MINOR
        )
        assert (
            VIOLATION_SEVERITY_MAP["task.reminder_at_90_percent"]
            == ViolationSeverity.MINOR
        )
        assert (
            VIOLATION_SEVERITY_MAP["advisory.acknowledgment_timeout"]
            == ViolationSeverity.MINOR
        )

    def test_major_violations_mapped(self) -> None:
        """MAJOR violations are mapped correctly."""
        assert (
            VIOLATION_SEVERITY_MAP["coercion.filter_blocked"] == ViolationSeverity.MAJOR
        )
        assert (
            VIOLATION_SEVERITY_MAP["consent.bypass_detected"] == ViolationSeverity.MAJOR
        )
        assert (
            VIOLATION_SEVERITY_MAP["role.constraint_violated"]
            == ViolationSeverity.MAJOR
        )

    def test_critical_violations_mapped(self) -> None:
        """CRITICAL violations are mapped correctly."""
        assert (
            VIOLATION_SEVERITY_MAP["coercion.multiple_concurrent"]
            == ViolationSeverity.CRITICAL
        )
        assert (
            VIOLATION_SEVERITY_MAP["task.unauthorized_creation"]
            == ViolationSeverity.CRITICAL
        )
        assert (
            VIOLATION_SEVERITY_MAP["panel.finding_ignored"]
            == ViolationSeverity.CRITICAL
        )

    def test_integrity_violations_mapped(self) -> None:
        """INTEGRITY violations are mapped correctly."""
        assert (
            VIOLATION_SEVERITY_MAP["chain.discontinuity"] == ViolationSeverity.INTEGRITY
        )
        assert (
            VIOLATION_SEVERITY_MAP["event.tampering_detected"]
            == ViolationSeverity.INTEGRITY
        )
        assert (
            VIOLATION_SEVERITY_MAP["witness.signature_invalid"]
            == ViolationSeverity.INTEGRITY
        )

    def test_all_mapped_violations_have_valid_severity(self) -> None:
        """All mapped violations have valid severity values."""
        for violation_type, severity in VIOLATION_SEVERITY_MAP.items():
            assert isinstance(violation_type, str)
            assert isinstance(severity, ViolationSeverity)


class TestGetSeverityForViolation:
    """Tests for get_severity_for_violation helper function."""

    def test_known_violation_returns_mapped_severity(self) -> None:
        """Known violation types return their mapped severity."""
        severity = get_severity_for_violation("coercion.filter_blocked")
        assert severity == ViolationSeverity.MAJOR

    def test_unknown_violation_returns_minor(self) -> None:
        """Unknown violation types default to MINOR severity."""
        severity = get_severity_for_violation("unknown.violation.type")
        assert severity == ViolationSeverity.MINOR

    def test_empty_violation_returns_minor(self) -> None:
        """Empty violation type defaults to MINOR severity."""
        severity = get_severity_for_violation("")
        assert severity == ViolationSeverity.MINOR

    def test_none_like_violation_returns_minor(self) -> None:
        """None-like violation type defaults to MINOR severity."""
        severity = get_severity_for_violation("unknown")
        assert severity == ViolationSeverity.MINOR


class TestCalculateTargetBand:
    """Tests for calculate_target_band function (AC4: severity-based decay)."""

    def test_minor_from_stable_drops_one_band(self) -> None:
        """MINOR violation from STABLE drops to STRAINED."""
        target = calculate_target_band(LegitimacyBand.STABLE, ViolationSeverity.MINOR)
        assert target == LegitimacyBand.STRAINED

    def test_minor_from_strained_drops_one_band(self) -> None:
        """MINOR violation from STRAINED drops to ERODING."""
        target = calculate_target_band(LegitimacyBand.STRAINED, ViolationSeverity.MINOR)
        assert target == LegitimacyBand.ERODING

    def test_minor_from_eroding_drops_one_band(self) -> None:
        """MINOR violation from ERODING drops to COMPROMISED."""
        target = calculate_target_band(LegitimacyBand.ERODING, ViolationSeverity.MINOR)
        assert target == LegitimacyBand.COMPROMISED

    def test_minor_from_compromised_drops_to_failed(self) -> None:
        """MINOR violation from COMPROMISED drops to FAILED."""
        target = calculate_target_band(
            LegitimacyBand.COMPROMISED, ViolationSeverity.MINOR
        )
        assert target == LegitimacyBand.FAILED

    def test_major_from_stable_drops_two_bands(self) -> None:
        """MAJOR violation from STABLE drops to ERODING (skips STRAINED)."""
        target = calculate_target_band(LegitimacyBand.STABLE, ViolationSeverity.MAJOR)
        assert target == LegitimacyBand.ERODING

    def test_major_from_strained_drops_two_bands(self) -> None:
        """MAJOR violation from STRAINED drops to COMPROMISED."""
        target = calculate_target_band(LegitimacyBand.STRAINED, ViolationSeverity.MAJOR)
        assert target == LegitimacyBand.COMPROMISED

    def test_major_from_eroding_drops_to_failed(self) -> None:
        """MAJOR violation from ERODING drops to FAILED."""
        target = calculate_target_band(LegitimacyBand.ERODING, ViolationSeverity.MAJOR)
        assert target == LegitimacyBand.FAILED

    def test_critical_from_stable_jumps_to_compromised(self) -> None:
        """CRITICAL violation from STABLE jumps directly to COMPROMISED."""
        target = calculate_target_band(
            LegitimacyBand.STABLE, ViolationSeverity.CRITICAL
        )
        assert target == LegitimacyBand.COMPROMISED

    def test_critical_from_strained_jumps_to_compromised(self) -> None:
        """CRITICAL violation from STRAINED jumps directly to COMPROMISED."""
        target = calculate_target_band(
            LegitimacyBand.STRAINED, ViolationSeverity.CRITICAL
        )
        assert target == LegitimacyBand.COMPROMISED

    def test_critical_from_eroding_jumps_to_compromised(self) -> None:
        """CRITICAL violation from ERODING jumps directly to COMPROMISED."""
        target = calculate_target_band(
            LegitimacyBand.ERODING, ViolationSeverity.CRITICAL
        )
        assert target == LegitimacyBand.COMPROMISED

    def test_critical_from_compromised_stays_compromised(self) -> None:
        """CRITICAL violation from COMPROMISED stays at COMPROMISED."""
        target = calculate_target_band(
            LegitimacyBand.COMPROMISED, ViolationSeverity.CRITICAL
        )
        assert target == LegitimacyBand.COMPROMISED

    def test_integrity_from_any_band_goes_to_failed(self) -> None:
        """INTEGRITY violation from any band goes directly to FAILED."""
        for band in LegitimacyBand:
            if band != LegitimacyBand.FAILED:
                target = calculate_target_band(band, ViolationSeverity.INTEGRITY)
                assert target == LegitimacyBand.FAILED

    def test_integrity_from_failed_stays_failed(self) -> None:
        """INTEGRITY violation from FAILED stays at FAILED."""
        target = calculate_target_band(
            LegitimacyBand.FAILED, ViolationSeverity.INTEGRITY
        )
        assert target == LegitimacyBand.FAILED
