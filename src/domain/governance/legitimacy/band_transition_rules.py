"""Band transition rules for legitimacy state machine.

This module implements the rules governing transitions between legitimacy
bands as specified in governance-prd.md.

Transition Rules:
- Downward (decay): Automatic allowed, any number of steps
- Upward (restoration): Requires acknowledgment, one step at a time
- FAILED: Terminal state, no transitions allowed

Constitutional Compliance:
- AC2: State machine enforces valid transitions only
- AC5: Downward transitions allowed automatically
- AC6: Upward transitions require explicit acknowledgment
"""

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.transition_type import TransitionType
from src.domain.governance.legitimacy.transition_validation import (
    TransitionValidation,
)


class BandTransitionRules:
    """Rules for legitimacy band transitions.

    This class provides static methods to validate proposed transitions
    between legitimacy bands according to the governance rules.

    Key Rules:
    - FAILED is terminal: No transitions out of FAILED
    - Downward transitions: Always allowed (automatic or acknowledged)
    - Upward transitions: Must be acknowledged, one step at a time
    """

    @staticmethod
    def validate_transition(
        current: LegitimacyBand,
        target: LegitimacyBand,
        transition_type: TransitionType,
    ) -> TransitionValidation:
        """Validate a proposed transition between bands.

        Args:
            current: The current legitimacy band.
            target: The proposed target band.
            transition_type: Whether automatic or acknowledged.

        Returns:
            TransitionValidation indicating if transition is valid.
        """
        # FAILED is terminal - no way out
        if current == LegitimacyBand.FAILED:
            return TransitionValidation.invalid(
                "FAILED is terminal - reconstitution required"
            )

        # Same band is not a valid transition
        if current == target:
            return TransitionValidation.invalid(
                "Already at target band"
            )

        # Downward transition (increasing severity)
        if target.severity > current.severity:
            # Downward transitions are always valid
            return TransitionValidation.valid()

        # Upward transition (decreasing severity)
        if target.severity < current.severity:
            # Upward requires acknowledgment
            if transition_type != TransitionType.ACKNOWLEDGED:
                return TransitionValidation.invalid(
                    "Upward transition requires acknowledgment"
                )

            # Upward must be exactly one step
            if target.severity != current.severity - 1:
                return TransitionValidation.invalid(
                    "Upward transition must be one step at a time"
                )

            return TransitionValidation.valid()

        # Should never reach here
        return TransitionValidation.invalid("Invalid transition")

    @staticmethod
    def is_decay(current: LegitimacyBand, target: LegitimacyBand) -> bool:
        """Check if transition is a decay (downward).

        Args:
            current: The current band.
            target: The proposed target band.

        Returns:
            True if this would be a downward transition.
        """
        return target.severity > current.severity

    @staticmethod
    def is_restoration(current: LegitimacyBand, target: LegitimacyBand) -> bool:
        """Check if transition is a restoration (upward).

        Args:
            current: The current band.
            target: The proposed target band.

        Returns:
            True if this would be an upward transition.
        """
        return target.severity < current.severity

    @staticmethod
    def get_next_restoration_target(
        current: LegitimacyBand,
    ) -> LegitimacyBand | None:
        """Get the band to restore to (one step up).

        Args:
            current: The current band.

        Returns:
            The band one step healthier, or None if at STABLE or FAILED.
        """
        if current == LegitimacyBand.STABLE:
            return None  # Already at healthiest
        if current == LegitimacyBand.FAILED:
            return None  # Terminal, can't restore

        return LegitimacyBand.from_severity(current.severity - 1)

    @staticmethod
    def calculate_decay_target(
        current: LegitimacyBand,
        severity_increase: int = 1,
    ) -> LegitimacyBand:
        """Calculate target band for a decay of given severity.

        Args:
            current: The current band.
            severity_increase: How many levels to decay (1-4).

        Returns:
            The target band after decay (capped at FAILED).

        Raises:
            ValueError: If current is FAILED or severity_increase invalid.
        """
        if current == LegitimacyBand.FAILED:
            raise ValueError("Cannot decay from FAILED")

        if severity_increase < 1:
            raise ValueError("severity_increase must be at least 1")

        new_severity = min(current.severity + severity_increase, 4)
        return LegitimacyBand.from_severity(new_severity)
