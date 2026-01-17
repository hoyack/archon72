"""Transition validation result model.

This module defines the TransitionValidation dataclass that represents
the result of validating a proposed legitimacy band transition.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TransitionValidation:
    """Result of validating a proposed legitimacy transition.

    This is a simple result object indicating whether a proposed
    transition is valid and, if not, why it was rejected.

    Attributes:
        is_valid: Whether the transition is allowed.
        reason: Explanation of why transition was rejected (if invalid).
    """

    is_valid: bool
    reason: Optional[str]

    @classmethod
    def valid(cls) -> "TransitionValidation":
        """Create a validation result indicating success.

        Returns:
            TransitionValidation with is_valid=True.
        """
        return cls(is_valid=True, reason=None)

    @classmethod
    def invalid(cls, reason: str) -> "TransitionValidation":
        """Create a validation result indicating failure.

        Args:
            reason: Explanation of why the transition is invalid.

        Returns:
            TransitionValidation with is_valid=False and reason.
        """
        return cls(is_valid=False, reason=reason)

    def __bool__(self) -> bool:
        """Allow use in boolean context.

        Returns:
            True if validation passed.
        """
        return self.is_valid
