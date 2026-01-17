"""Anti-Metrics Violation Domain Models.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

This module defines the violation models for anti-metrics enforcement.
When an attempt is made to violate anti-metrics constraints, a violation
record is created and the operation is blocked.

Constitutional Guarantees:
- FR61-63: No metrics collection
- NFR-CONST-08: Collection attempts are blocked at data layer
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.antimetrics.prohibited_pattern import ProhibitedPattern


@dataclass(frozen=True)
class AntiMetricsViolation:
    """Record of an anti-metrics violation attempt.

    This is an immutable record of an attempt to violate anti-metrics
    constraints. The attempt was blocked, but the record is preserved
    for auditing and accountability.

    Attributes:
        violation_id: Unique identifier for this violation
        attempted_at: When the violation was attempted
        pattern: Which prohibited pattern was violated
        attempted_by: Who/what attempted the violation
        description: Human-readable description of the attempt

    Note:
        This is a frozen dataclass - all fields are immutable.
        Violations are recorded for accountability but the
        violating operation is always blocked.
    """

    violation_id: UUID
    attempted_at: datetime
    pattern: ProhibitedPattern
    attempted_by: str
    description: str

    def __str__(self) -> str:
        """Return human-readable violation summary."""
        return (
            f"AntiMetricsViolation({self.pattern.value}): "
            f"{self.description} by {self.attempted_by}"
        )


class AntiMetricsViolationError(ValueError):
    """Raised when anti-metrics constraint is violated.

    This error is raised when an attempt is made to:
    - Create a prohibited metric table
    - Add a prohibited metric column
    - Store participant-level performance data
    - Track engagement or retention metrics

    The error ALWAYS results in the operation being blocked.
    It should NEVER be caught and silently ignored.

    Constitutional Reference:
        NFR-CONST-08: Anti-metrics are enforced at data layer;
        collection endpoints do not exist.

    Attributes:
        violation: The violation record that triggered this error
        message: Human-readable error message
    """

    def __init__(
        self,
        message: str,
        violation: AntiMetricsViolation | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error message
            violation: Optional violation record for audit
        """
        super().__init__(message)
        self.violation = violation

    def __str__(self) -> str:
        """Return error message."""
        if self.violation:
            return f"{super().__str__()} [{self.violation.pattern.value}]"
        return super().__str__()
