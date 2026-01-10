"""Audit event query errors (Story 9.5, FR108).

Domain errors for audit event query operations.
All errors inherit from ConstitutionalViolationError per project patterns.

Constitutional Constraints:
- FR108: Audit results logged as events
- CT-11: HALT CHECK FIRST (handled by services)
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class AuditEventQueryError(ConstitutionalViolationError):
    """Base error for audit event query operations (FR108).

    All audit event query errors inherit from this class.
    """

    pass


class AuditEventNotFoundError(AuditEventQueryError):
    """Raised when a requested audit event is not found (FR108).

    Example:
        raise AuditEventNotFoundError("event-123", "audit.completed")
    """

    def __init__(self, event_id: str, event_type: str) -> None:
        """Initialize error with event details.

        Args:
            event_id: The event ID that was not found.
            event_type: The expected event type.
        """
        self.event_id = event_id
        self.event_type = event_type
        super().__init__(
            f"FR108: Audit event not found - id={event_id}, type={event_type}"
        )


class AuditTrendCalculationError(AuditEventQueryError):
    """Raised when trend calculation fails (FR108).

    Example:
        raise AuditTrendCalculationError("Division by zero in average calculation")
    """

    def __init__(self, reason: str) -> None:
        """Initialize error with failure reason.

        Args:
            reason: Description of why trend calculation failed.
        """
        self.reason = reason
        super().__init__(f"FR108: Audit trend calculation failed - {reason}")


class InsufficientAuditDataError(AuditEventQueryError):
    """Raised when there's not enough data for trend analysis (FR108).

    Example:
        raise InsufficientAuditDataError(
            requested_quarters=4,
            available_quarters=1,
        )
    """

    def __init__(
        self,
        message: str = "Not enough audit data available for trend analysis",
        requested_quarters: int = 0,
        available_quarters: int = 0,
    ) -> None:
        """Initialize error with data availability details.

        Args:
            message: Human-readable error message.
            requested_quarters: Number of quarters requested.
            available_quarters: Number of quarters available.
        """
        self.requested_quarters = requested_quarters
        self.available_quarters = available_quarters
        if requested_quarters > 0:
            detail = (
                f"FR108: {message} - "
                f"requested={requested_quarters}, available={available_quarters}"
            )
        else:
            detail = f"FR108: {message}"
        super().__init__(detail)


class AuditQueryTimeoutError(AuditEventQueryError):
    """Raised when an audit query times out (FR108).

    Example:
        raise AuditQueryTimeoutError(query_type="trend_analysis", timeout_seconds=30)
    """

    def __init__(self, query_type: str, timeout_seconds: int) -> None:
        """Initialize error with timeout details.

        Args:
            query_type: Type of query that timed out.
            timeout_seconds: Timeout duration in seconds.
        """
        self.query_type = query_type
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"FR108: Audit query timed out - "
            f"type={query_type}, timeout={timeout_seconds}s"
        )
