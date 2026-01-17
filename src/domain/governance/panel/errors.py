"""Panel domain errors.

Story: consent-gov-6-4: Prince Panel Domain Model

This module defines domain-specific exceptions for Prince Panel operations.
"""


class InvalidPanelComposition(ValueError):
    """Raised when panel composition is invalid.

    A panel requires at least 3 active (non-recused) members to be valid.
    This exception is raised when:
    - Panel is created with fewer than 3 members
    - Recusal would leave fewer than 3 active members
    - Composition validation fails before issuing a finding

    Example:
        >>> raise InvalidPanelComposition(
        ...     "Panel requires ≥3 active members, has 2"
        ... )
    """

    pass
