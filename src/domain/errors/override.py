"""Override domain errors (Story 5.1, FR23; Story 5.2, FR24, FR28; Story 5.4, FR26).

Provides specific exception classes for override-related failure scenarios.
These errors enforce the FR23 requirement: override actions must be logged
before they take effect, FR24/FR28 requirements for duration and reason,
and FR26 requirement that overrides cannot suppress witnessing.

Constitutional Constraints:
- FR23: Override must be logged before taking effect
- FR24: Override events SHALL include duration (no indefinite overrides)
- FR26: Overrides cannot suppress witnessing (Constitution Supremacy)
- FR28: Override reasons must be from enumerated list
- CT-11: Silent failure destroys legitimacy -> Failed log = NO override execution
- CT-12: Witnessing creates accountability -> no unwitnessed actions
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class OverrideLoggingFailedError(ConstitutionalViolationError):
    """Raised when override event fails to write to event store (FR23).

    Constitutional Constraint:
    Override actions MUST be logged before they take effect.
    If the override event fails to write, the override action
    MUST NOT execute.

    This error signals that the override was rejected due to
    logging failure - the override action did NOT execute.
    """

    pass


class OverrideBlockedError(ConstitutionalViolationError):
    """Raised when an override is blocked by constitutional constraints.

    This error is raised when an override request is rejected for
    reasons other than logging failure, such as:
    - Invalid override scope
    - Invalid action type
    - Missing required fields
    - Constitutional constraint violation

    The override action does NOT execute when this error is raised.
    """

    pass


class DurationValidationError(ConstitutionalViolationError):
    """Raised when override duration validation fails (FR24).

    Constitutional Constraint (FR24):
    Override events SHALL include duration, and indefinite overrides
    are prohibited. Duration must be within allowed bounds.

    Raised when:
    - Duration is missing or None
    - Duration is <= 0 (indefinite override attempt)
    - Duration exceeds maximum allowed (7 days = 604800 seconds)
    - Duration is below minimum allowed (1 minute = 60 seconds)
    """

    pass


class InvalidOverrideReasonError(ConstitutionalViolationError):
    """Raised when override reason is not from enumerated list (FR28).

    Constitutional Constraint (FR28):
    Override reasons must be from enumerated list to prevent
    arbitrary justifications and ensure auditable categorization.

    Raised when:
    - Reason is not an OverrideReason enum value
    - Reason string doesn't match any valid enum value
    """

    pass


class WitnessSuppressionAttemptError(ConstitutionalViolationError):
    """Raised when override attempts to suppress witnessing (FR26, PM-4).

    Constitutional Constraint (FR26):
    Overrides that attempt to suppress witnessing are invalid by definition.
    No Keeper can bypass accountability through override.

    Constitutional Truth (CT-12):
    Witnessing creates accountability - unwitnessed actions are invalid.

    Cross-Epic Requirement (PM-4):
    This error is the Epic 5 enforcement of FR26.
    Epic 1 ensures atomic witnessing; Epic 5 blocks suppression attempts.

    Raised when:
    - Override scope targets witness system (e.g., "witness", "witnessing")
    - Override scope targets attestation system (e.g., "attestation")
    - Any scope pattern that would disable witnessing

    Attributes:
        scope: The override scope that attempted witness suppression.
    """

    def __init__(self, scope: str, message: str | None = None) -> None:
        """Initialize with scope and optional custom message.

        Args:
            scope: The override scope that attempted witness suppression.
            message: Optional custom error message. Defaults to FR26 message.
        """
        msg = (
            message
            or f"FR26: Constitution supremacy - witnessing cannot be suppressed (scope: {scope})"
        )
        super().__init__(msg)
        self.scope = scope
