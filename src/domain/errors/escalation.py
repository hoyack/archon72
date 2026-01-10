"""Escalation domain errors (Story 6.2, FR31).

This module provides exception classes for escalation-related failures.
These errors represent issues when creating, querying, or processing
escalation and acknowledgment events.

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> All errors must be logged
        and include FR reference for traceability
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


class EscalationError(ConstitutionalViolationError):
    """Base error for escalation-related operations.

    Constitutional Constraint:
    All escalation errors inherit from ConstitutionalViolationError and
    represent failures in the breach escalation and acknowledgment system.

    All subclasses include FR31 reference for traceability.
    """

    pass


class BreachNotFoundError(EscalationError):
    """Raised when a breach cannot be found for escalation/acknowledgment (FR31).

    Constitutional Constraint (FR31):
    Escalation and acknowledgment operations require a valid breach reference.
    If the breach does not exist, this error is raised.

    Attributes:
        breach_id: The UUID of the breach that was not found.
    """

    def __init__(self, breach_id: UUID, message: Optional[str] = None) -> None:
        """Initialize with the breach ID and optional custom message.

        Args:
            breach_id: The UUID of the breach that was not found.
            message: Optional custom error message. Defaults to FR31 message.
        """
        msg = message or f"FR31: Breach not found - unable to locate breach with ID {breach_id}"
        super().__init__(msg)
        self.breach_id = breach_id


class BreachAlreadyAcknowledgedError(EscalationError):
    """Raised when attempting to acknowledge an already-acknowledged breach (FR31).

    Constitutional Constraint (FR31):
    Each breach can only be acknowledged once. Subsequent acknowledgment
    attempts are rejected to maintain accountability.

    Attributes:
        breach_id: The UUID of the breach that was already acknowledged.
    """

    def __init__(self, breach_id: UUID, message: Optional[str] = None) -> None:
        """Initialize with the breach ID and optional custom message.

        Args:
            breach_id: The UUID of the breach that was already acknowledged.
            message: Optional custom error message. Defaults to FR31 message.
        """
        msg = message or f"FR31: Breach already acknowledged - breach {breach_id} has already been acknowledged"
        super().__init__(msg)
        self.breach_id = breach_id


class BreachAlreadyEscalatedError(EscalationError):
    """Raised when attempting to escalate an already-escalated breach (FR31).

    Constitutional Constraint (FR31):
    Each breach can only be escalated once. The escalation system is
    idempotent and will not create duplicate escalation events.

    Attributes:
        breach_id: The UUID of the breach that was already escalated.
    """

    def __init__(self, breach_id: UUID, message: Optional[str] = None) -> None:
        """Initialize with the breach ID and optional custom message.

        Args:
            breach_id: The UUID of the breach that was already escalated.
            message: Optional custom error message. Defaults to FR31 message.
        """
        msg = message or f"FR31: Breach already escalated - breach {breach_id} has already been escalated to agenda"
        super().__init__(msg)
        self.breach_id = breach_id


class InvalidAcknowledgmentError(EscalationError):
    """Raised when an acknowledgment attempt is invalid (FR31).

    Constitutional Constraint (FR31):
    Acknowledgment requires valid attributed response choice.
    Invalid or missing acknowledgment details are rejected.

    Attributes:
        reason: The reason the acknowledgment is invalid.
    """

    def __init__(self, reason: str, message: Optional[str] = None) -> None:
        """Initialize with the reason and optional custom message.

        Args:
            reason: The reason the acknowledgment is invalid.
            message: Optional custom error message. Defaults to FR31 message.
        """
        msg = message or f"FR31: Invalid acknowledgment - {reason}"
        super().__init__(msg)
        self.reason = reason


class EscalationTimerNotStartedError(EscalationError):
    """Raised when escalation timer operations fail due to timer not started (FR31).

    Constitutional Constraint (FR31):
    Escalation timer must be started for a breach before it can be stopped
    or queried.

    Attributes:
        breach_id: The UUID of the breach with no escalation timer.
    """

    def __init__(self, breach_id: UUID, message: Optional[str] = None) -> None:
        """Initialize with the breach ID and optional custom message.

        Args:
            breach_id: The UUID of the breach with no escalation timer.
            message: Optional custom error message. Defaults to FR31 message.
        """
        msg = message or f"FR31: Escalation timer not started for breach {breach_id}"
        super().__init__(msg)
        self.breach_id = breach_id
