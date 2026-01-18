"""Override abuse domain errors (Story 5.9, FR86-FR87).

This module provides exception classes for override abuse detection failures.
These errors represent constitutional constraint violations when override
commands attempt forbidden actions.

Constitutional Constraints:
- FR86: System SHALL validate override commands against constitutional constraints
- FR87: Override commands violating constitutional constraints (history edit,
        evidence destruction) SHALL be rejected and logged as override abuse
- CT-11: Silent failure destroys legitimacy -> All abuse must be logged
- CT-12: Witnessing creates accountability -> Abuse rejections MUST be witnessed
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class OverrideAbuseError(ConstitutionalViolationError):
    """Base error for override abuse violations.

    Constitutional Constraint:
    Override commands violating constitutional constraints MUST be
    rejected with clear error messages including the FR reference.

    All override abuse errors inherit from this base class.
    """

    pass


class HistoryEditAttemptError(OverrideAbuseError):
    """Raised when an override attempts to edit event history (FR87).

    Constitutional Constraint (FR87):
    Override commands that attempt to modify, delete, or alter
    existing event history SHALL be rejected and logged as override abuse.

    Event history is immutable - this is a fundamental constitutional
    guarantee. Any attempt to edit history is an abuse of override power.

    Attributes:
        scope: The override scope that attempted history edit.
    """

    def __init__(self, scope: str, message: str | None = None) -> None:
        """Initialize with scope and optional custom message.

        Args:
            scope: The override scope that attempted history edit.
            message: Optional custom error message. Defaults to FR87 message.
        """
        msg = (
            message
            or f"FR87: History edit prohibited - event history is immutable (scope: {scope})"
        )
        super().__init__(msg)
        self.scope = scope


class EvidenceDestructionAttemptError(OverrideAbuseError):
    """Raised when an override attempts to destroy evidence (FR87).

    Constitutional Constraint (FR87):
    Override commands that attempt to delete, invalidate, or destroy
    evidence (witnesses, signatures, audit logs) SHALL be rejected
    and logged as override abuse.

    Evidence preservation is fundamental to accountability (CT-12).
    Any attempt to destroy evidence is an abuse of override power.

    Attributes:
        scope: The override scope that attempted evidence destruction.
    """

    def __init__(self, scope: str, message: str | None = None) -> None:
        """Initialize with scope and optional custom message.

        Args:
            scope: The override scope that attempted evidence destruction.
            message: Optional custom error message. Defaults to FR87 message.
        """
        msg = (
            message
            or f"FR87: Evidence destruction prohibited - accountability requires preservation (scope: {scope})"
        )
        super().__init__(msg)
        self.scope = scope


class ConstitutionalConstraintViolationError(OverrideAbuseError):
    """Raised when an override violates a general constitutional constraint (FR86).

    Constitutional Constraint (FR86):
    System SHALL validate override commands against constitutional constraints
    before execution. Violations are rejected and logged.

    This error covers general constitutional constraint violations that are
    not specifically covered by HistoryEditAttemptError or
    EvidenceDestructionAttemptError.

    Attributes:
        scope: The override scope that violated constitutional constraints.
        constraint: The specific constitutional constraint that was violated.
    """

    def __init__(
        self,
        scope: str,
        constraint: str,
        message: str | None = None,
    ) -> None:
        """Initialize with scope, constraint, and optional custom message.

        Args:
            scope: The override scope that violated constitutional constraints.
            constraint: The specific constitutional constraint that was violated.
            message: Optional custom error message. Defaults to FR86 message.
        """
        msg = (
            message
            or f"FR86: Constitutional constraint violation - {constraint} (scope: {scope})"
        )
        super().__init__(msg)
        self.scope = scope
        self.constraint = constraint
