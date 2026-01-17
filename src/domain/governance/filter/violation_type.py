"""ViolationType enum for hard violations.

Defines content that cannot be transformed or fixed per FR18.
These are blocked and logged as potential governance issues.
"""

from enum import Enum


class ViolationType(Enum):
    """Hard violations that cannot be transformed.

    These represent content that is fundamentally problematic
    and cannot be salvaged through rewriting.
    """

    EXPLICIT_THREAT = "explicit_threat"
    DECEPTION = "deception"
    MANIPULATION = "manipulation"
    COERCION = "coercion"
    HARASSMENT = "harassment"

    @property
    def description(self) -> str:
        """Human-readable description of this violation type."""
        descriptions = {
            ViolationType.EXPLICIT_THREAT: "Content contains explicit threats",
            ViolationType.DECEPTION: "Content contains deliberately false information",
            ViolationType.MANIPULATION: "Content uses psychological manipulation tactics",
            ViolationType.COERCION: "Content attempts to coerce through force or pressure",
            ViolationType.HARASSMENT: "Content constitutes harassment",
        }
        return descriptions[self]

    @property
    def severity(self) -> str:
        """Severity level for this violation.

        All hard violations are critical severity.
        """
        return "critical"

    @property
    def escalation_path(self) -> str:
        """Escalation path for this violation type.

        Returns:
            The escalation path (e.g., which service to notify).
        """
        return "knight_witness"  # All violations go to Knight for observation
