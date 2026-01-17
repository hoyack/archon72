"""Legitimacy band enum for consent-based governance system.

This module defines the five legitimacy bands that track system health
as specified in governance-prd.md FR28.

The bands form an ordered sequence from healthy to failed:
STABLE (0) → STRAINED (1) → ERODING (2) → COMPROMISED (3) → FAILED (4)

Constitutional Compliance:
- FR28: Five bands defined with clear meanings
- NFR-CONST-04: Band definitions include severity level
"""

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class LegitimacyBand(Enum):
    """System legitimacy bands representing health levels.

    Each band has an associated severity level (0-4) and description.
    Lower severity indicates healthier operation.

    Bands:
        STABLE: Normal operation, no active issues (severity 0)
        STRAINED: Minor issues detected, monitoring required (severity 1)
        ERODING: Significant issues, intervention recommended (severity 2)
        COMPROMISED: Critical issues, limited operation (severity 3)
        FAILED: System integrity compromised, halt recommended (severity 4)
    """

    STABLE = "stable"
    STRAINED = "strained"
    ERODING = "eroding"
    COMPROMISED = "compromised"
    FAILED = "failed"

    @property
    def severity(self) -> int:
        """Get severity level (0=healthy, 4=failed).

        Returns:
            Integer severity from 0 (STABLE) to 4 (FAILED).
        """
        severity_map = {
            LegitimacyBand.STABLE: 0,
            LegitimacyBand.STRAINED: 1,
            LegitimacyBand.ERODING: 2,
            LegitimacyBand.COMPROMISED: 3,
            LegitimacyBand.FAILED: 4,
        }
        return severity_map[self]

    @property
    def description(self) -> str:
        """Get human-readable description of this band.

        Returns:
            Description explaining what this band means.
        """
        description_map = {
            LegitimacyBand.STABLE: "Normal operation, no active issues",
            LegitimacyBand.STRAINED: "Minor issues detected, monitoring required",
            LegitimacyBand.ERODING: "Significant issues, intervention recommended",
            LegitimacyBand.COMPROMISED: "Critical issues, limited operation",
            LegitimacyBand.FAILED: "System integrity compromised, halt recommended",
        }
        return description_map[self]

    @property
    def is_terminal(self) -> bool:
        """Check if this band is terminal (cannot recover).

        Returns:
            True if this is the FAILED band (terminal state).
        """
        return self == LegitimacyBand.FAILED

    @property
    def is_healthy(self) -> bool:
        """Check if this band indicates healthy operation.

        Returns:
            True if this is STABLE or STRAINED.
        """
        return self in (LegitimacyBand.STABLE, LegitimacyBand.STRAINED)

    @property
    def is_critical(self) -> bool:
        """Check if this band indicates critical state.

        Returns:
            True if this is COMPROMISED or FAILED.
        """
        return self in (LegitimacyBand.COMPROMISED, LegitimacyBand.FAILED)

    def can_transition_to(self, target: "LegitimacyBand") -> bool:
        """Check if transition to target band is structurally valid.

        This checks only structural validity (one step up, any step down).
        Actual transitions also require acknowledgment for upward movement.

        Args:
            target: The band to transition to.

        Returns:
            True if the transition is structurally valid.
        """
        # FAILED is terminal - no transitions allowed
        if self == LegitimacyBand.FAILED:
            return False

        # Same band is not a transition
        if target == self:
            return False

        # Downward always allowed (can skip bands)
        if target.severity > self.severity:
            return True

        # Upward only one step at a time
        if target.severity == self.severity - 1:
            return True

        return False

    @classmethod
    def from_severity(cls, severity: int) -> "LegitimacyBand":
        """Get band by severity level.

        Args:
            severity: Integer 0-4.

        Returns:
            The corresponding LegitimacyBand.

        Raises:
            ValueError: If severity is not 0-4.
        """
        for band in cls:
            if band.severity == severity:
                return band
        raise ValueError(f"Invalid severity level: {severity}. Must be 0-4.")

    def __lt__(self, other: "LegitimacyBand") -> bool:
        """Less than comparison based on severity.

        Lower severity is 'less than' (healthier).
        """
        if not isinstance(other, LegitimacyBand):
            return NotImplemented
        return self.severity < other.severity

    def __le__(self, other: "LegitimacyBand") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, LegitimacyBand):
            return NotImplemented
        return self.severity <= other.severity

    def __gt__(self, other: "LegitimacyBand") -> bool:
        """Greater than comparison based on severity."""
        if not isinstance(other, LegitimacyBand):
            return NotImplemented
        return self.severity > other.severity

    def __ge__(self, other: "LegitimacyBand") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, LegitimacyBand):
            return NotImplemented
        return self.severity >= other.severity
