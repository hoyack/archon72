"""Breach declaration domain errors (Story 6.1, FR30).

This module provides exception classes for breach declaration failures.
These errors represent issues when creating, querying, or processing
breach events.

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events with
        breach_type, violated_requirement, detection_timestamp
- CT-11: Silent failure destroys legitimacy -> All errors must be logged
        and include FR reference for traceability
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class BreachError(ConstitutionalViolationError):
    """Base error for breach-related operations.

    Constitutional Constraint:
    All breach errors inherit from ConstitutionalViolationError and
    represent failures in the breach detection and declaration system.

    All subclasses include FR30 reference for traceability.
    """

    pass


class BreachDeclarationError(BreachError):
    """Raised when a breach cannot be declared (FR30).

    Constitutional Constraint (FR30):
    Breach declarations SHALL create constitutional events. If declaration
    fails, this error is raised with details about the failure.

    This is a critical error - breach declarations MUST NOT fail silently
    (CT-11: Silent failure destroys legitimacy).

    Attributes:
        message: Error message describing the declaration failure.
    """

    def __init__(self, message: str | None = None) -> None:
        """Initialize with optional custom message.

        Args:
            message: Optional custom error message. Defaults to FR30 message.
        """
        msg = (
            message
            or "FR30: Breach declaration failed - unable to create constitutional event"
        )
        super().__init__(msg)


class InvalidBreachTypeError(BreachError):
    """Raised when an unknown breach type is provided (FR30).

    Constitutional Constraint (FR30):
    Breach events must have a valid breach_type from the defined enum.
    Unknown or invalid types are rejected.

    Attributes:
        invalid_type: The invalid breach type value that was provided.
    """

    def __init__(self, invalid_type: str, message: str | None = None) -> None:
        """Initialize with the invalid type and optional custom message.

        Args:
            invalid_type: The invalid breach type value.
            message: Optional custom error message. Defaults to FR30 message.
        """
        msg = (
            message
            or f"FR30: Invalid breach type '{invalid_type}' - must be a valid BreachType enum value"
        )
        super().__init__(msg)
        self.invalid_type = invalid_type


class BreachQueryError(BreachError):
    """Raised when breach queries fail (FR30).

    Constitutional Constraint (FR30):
    Breach history queries support filtering by type and date range.
    If queries fail, this error is raised.

    Attributes:
        message: Error message describing the query failure.
    """

    def __init__(self, message: str | None = None) -> None:
        """Initialize with optional custom message.

        Args:
            message: Optional custom error message. Defaults to FR30 message.
        """
        msg = message or "FR30: Breach query failed - unable to retrieve breach history"
        super().__init__(msg)
