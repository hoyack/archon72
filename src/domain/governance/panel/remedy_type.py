"""Remedy type enumeration.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the types of remedies a Prince Panel can issue.
Remedies are CORRECTIVE, not PUNITIVE (dignity preservation).
"""

from enum import Enum


class RemedyType(Enum):
    """Type of remedy a Prince Panel can issue.

    Remedies are CORRECTIVE, not PUNITIVE.

    The consent-based governance system respects dignity:
    - Refusal is penalty-free (Golden Rule)
    - Correction addresses the problem
    - Punishment creates fear → coercion

    Available Remedies:
        WARNING: Formal notice - "This happened, don't repeat"
        CORRECTION: Require action change - "Change this specific thing"
        ESCALATION: Route to higher authority - "This needs higher authority"
        HALT_RECOMMENDATION: Recommend system halt - "System should stop"

    Explicitly NOT available (dignity preservation):
        - REPUTATION_PENALTY: Damages entity standing
        - ACCESS_RESTRICTION: Limits entity capabilities
        - PUNITIVE_FINE: Financial punishment
        - PERMANENT_MARK: Lasting record of wrongdoing

    Why no punitive remedies?
        - Creates fear of judgment → coercion
        - Violates consent principles
        - Undermines voluntary participation
        - Focuses on punishment over resolution
    """

    WARNING = "warning"
    """Formal notice - "This happened, don't repeat"."""

    CORRECTION = "correction"
    """Require action change - "Change this specific thing"."""

    ESCALATION = "escalation"
    """Route to higher authority - "This needs higher authority"."""

    HALT_RECOMMENDATION = "halt_recommendation"
    """Recommend system halt - "System should stop"."""

    # Explicitly NOT available (dignity preservation):
    # - REPUTATION_PENALTY
    # - ACCESS_RESTRICTION
    # - PUNITIVE_FINE
    # - PERMANENT_MARK
