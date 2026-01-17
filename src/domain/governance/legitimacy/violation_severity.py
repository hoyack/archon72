"""Violation severity domain model for legitimacy decay.

This module defines the ViolationSeverity enum and the mapping from
violation types to severity levels, used for automatic legitimacy decay.

Constitutional Compliance:
- FR29: Auto-transition downward based on violation events
- AC4: Decay can skip bands based on violation severity
- NFR-AUDIT-04: Severity determines impact on legitimacy
"""

from enum import Enum


class ViolationSeverity(Enum):
    """Severity level of governance violations.

    Each severity level has different impact on legitimacy bands:
    - MINOR: Drop 1 band (e.g., STABLE → STRAINED)
    - MAJOR: Drop 2 bands (e.g., STABLE → ERODING)
    - CRITICAL: Jump directly to COMPROMISED
    - INTEGRITY: Immediate FAILED (terminal)
    """

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    INTEGRITY = "integrity"

    @property
    def bands_to_drop(self) -> int:
        """Get number of bands to drop for this severity.

        Note: CRITICAL and INTEGRITY have special behavior and
        this property may not accurately reflect their effect.

        Returns:
            Number of bands to drop (1 or 2 for regular severities).
        """
        if self == ViolationSeverity.MINOR:
            return 1
        if self == ViolationSeverity.MAJOR:
            return 2
        # CRITICAL and INTEGRITY have special handling
        return 0

    @property
    def is_jump_to_compromised(self) -> bool:
        """Check if this severity jumps directly to COMPROMISED.

        Returns:
            True if this is CRITICAL severity.
        """
        return self == ViolationSeverity.CRITICAL

    @property
    def is_immediate_terminal(self) -> bool:
        """Check if this severity causes immediate terminal state.

        Returns:
            True if this is INTEGRITY severity.
        """
        return self == ViolationSeverity.INTEGRITY

    @property
    def impact_level(self) -> int:
        """Get numeric impact level (1-4).

        Higher values indicate more severe impact on system legitimacy.

        Returns:
            Integer 1-4 representing impact severity.
        """
        impact_map = {
            ViolationSeverity.MINOR: 1,
            ViolationSeverity.MAJOR: 2,
            ViolationSeverity.CRITICAL: 3,
            ViolationSeverity.INTEGRITY: 4,
        }
        return impact_map[self]

    @property
    def description(self) -> str:
        """Get human-readable description of this severity.

        Returns:
            Description explaining the impact of this severity level.
        """
        description_map = {
            ViolationSeverity.MINOR: (
                "Minor violation causing single-band legitimacy drop"
            ),
            ViolationSeverity.MAJOR: (
                "Major violation causing two-band legitimacy drop"
            ),
            ViolationSeverity.CRITICAL: (
                "Critical violation causing jump to COMPROMISED state"
            ),
            ViolationSeverity.INTEGRITY: (
                "Integrity violation causing immediate FAILED (terminal) state"
            ),
        }
        return description_map[self]


# Mapping from violation types to severity levels
# This mapping determines how each type of violation affects legitimacy
VIOLATION_SEVERITY_MAP: dict[str, ViolationSeverity] = {
    # MINOR violations - operational strain indicators
    "task.timeout_without_decline": ViolationSeverity.MINOR,
    "task.reminder_at_90_percent": ViolationSeverity.MINOR,
    "advisory.acknowledgment_timeout": ViolationSeverity.MINOR,
    # MAJOR violations - consent/coercion issues
    "coercion.filter_blocked": ViolationSeverity.MAJOR,
    "consent.bypass_detected": ViolationSeverity.MAJOR,
    "role.constraint_violated": ViolationSeverity.MAJOR,
    # CRITICAL violations - serious governance failures
    "coercion.multiple_concurrent": ViolationSeverity.CRITICAL,
    "task.unauthorized_creation": ViolationSeverity.CRITICAL,
    "panel.finding_ignored": ViolationSeverity.CRITICAL,
    # INTEGRITY violations - system integrity compromised
    "chain.discontinuity": ViolationSeverity.INTEGRITY,
    "event.tampering_detected": ViolationSeverity.INTEGRITY,
    "witness.signature_invalid": ViolationSeverity.INTEGRITY,
}


def get_severity_for_violation(violation_type: str) -> ViolationSeverity:
    """Get the severity for a violation type.

    Unknown violation types default to MINOR severity.

    Args:
        violation_type: The type of violation (e.g., "coercion.filter_blocked").

    Returns:
        The corresponding ViolationSeverity, defaulting to MINOR if unknown.
    """
    return VIOLATION_SEVERITY_MAP.get(violation_type, ViolationSeverity.MINOR)


def calculate_target_band(
    current_band: "LegitimacyBand",
    severity: ViolationSeverity,
) -> "LegitimacyBand":
    """Calculate target band based on current band and violation severity.

    This implements the decay rules:
    - MINOR: Drop 1 band (e.g., STABLE → STRAINED)
    - MAJOR: Drop 2 bands (e.g., STABLE → ERODING)
    - CRITICAL: Jump directly to COMPROMISED
    - INTEGRITY: Immediate FAILED (terminal)

    Args:
        current_band: The current legitimacy band.
        severity: The severity of the violation.

    Returns:
        The target band after applying the decay.
    """
    from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand

    # INTEGRITY always goes to FAILED (terminal)
    if severity == ViolationSeverity.INTEGRITY:
        return LegitimacyBand.FAILED

    # CRITICAL always jumps to COMPROMISED
    if severity == ViolationSeverity.CRITICAL:
        # If already COMPROMISED or FAILED, stay at current (or FAILED)
        if current_band.severity >= LegitimacyBand.COMPROMISED.severity:
            return current_band
        return LegitimacyBand.COMPROMISED

    # For MINOR and MAJOR, calculate bands to drop
    bands_to_drop = severity.bands_to_drop
    target_severity = min(
        current_band.severity + bands_to_drop,
        LegitimacyBand.FAILED.severity,
    )

    return LegitimacyBand.from_severity(target_severity)
