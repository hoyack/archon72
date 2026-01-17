"""Transition type enum for legitimacy band transitions.

Defines the two types of legitimacy transitions:
- AUTOMATIC: System-triggered decay (no acknowledgment required)
- ACKNOWLEDGED: Human-acknowledged restoration (explicit operator action)

This distinction is critical for NFR-CONST-04 compliance: upward transitions
require explicit acknowledgment to ensure accountability.
"""

from enum import Enum


class TransitionType(Enum):
    """Type of legitimacy band transition.

    Transitions can be:
    - AUTOMATIC: Triggered by system events (violations, issues)
    - ACKNOWLEDGED: Explicitly acknowledged by human operator

    Downward transitions (decay) can be either type.
    Upward transitions (restoration) MUST be ACKNOWLEDGED.
    """

    AUTOMATIC = "automatic"
    ACKNOWLEDGED = "acknowledged"

    @property
    def requires_operator(self) -> bool:
        """Check if this transition type requires an operator.

        Returns:
            True if this is an ACKNOWLEDGED transition.
        """
        return self == TransitionType.ACKNOWLEDGED

    @property
    def description(self) -> str:
        """Get human-readable description.

        Returns:
            Description of what this transition type means.
        """
        if self == TransitionType.AUTOMATIC:
            return "System-triggered transition (decay)"
        return "Human-acknowledged transition (restoration)"
