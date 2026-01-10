"""Failure prevention errors (Story 8.8, FR106-FR107).

Domain errors for pre-mortem failure prevention.

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load

Usage:
    from src.domain.errors.failure_prevention import (
        FailureModeViolationError,
        EarlyWarningError,
        QueryPerformanceViolationError,
        ConstitutionalEventSheddingError,
    )

    # Raise on pattern violation
    raise FailureModeViolationError(
        mode_id=FailureModeId.PV_001,
        violation_description="Raw string event type detected",
        location="src/domain/events/foo.py:42",
    )
"""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.failure_mode import FailureModeId


class FailureModeViolationError(Exception):
    """Raised when a pattern violation from the FMEA risk matrix is detected.

    Constitutional Constraint (FR106-FR107):
    Pattern violations (PV-*) represent code patterns that could cause
    constitutional integrity failures if not corrected.

    Attributes:
        mode_id: Which failure mode was violated.
        violation_description: Description of the violation.
        location: Optional file:line location of the violation.
        remediation: Suggested fix for the violation.
        message: Human-readable error message.
    """

    def __init__(
        self,
        mode_id: "FailureModeId",
        violation_description: str,
        location: Optional[str] = None,
        remediation: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            mode_id: Which failure mode was violated.
            violation_description: Description of what went wrong.
            location: Optional file:line where violation occurred.
            remediation: Optional suggested fix.
            message: Optional custom message.
        """
        self.mode_id = mode_id
        self.violation_description = violation_description
        self.location = location
        self.remediation = remediation

        if message is None:
            parts = [
                f"Pattern violation [{mode_id.value}]: {violation_description}."
            ]
            if location:
                parts.append(f"Location: {location}.")
            if remediation:
                parts.append(f"Remediation: {remediation}.")
            message = " ".join(parts)

        self.message = message
        super().__init__(self.message)


class EarlyWarningError(Exception):
    """Raised when a failure mode enters warning or critical state.

    This error is informational - it indicates that preventive action
    should be taken, but does not necessarily block operations.

    Constitutional Constraint (FR106-FR107):
    Early warnings enable operators to prevent failures before they
    impact constitutional operations.

    Attributes:
        mode_id: Which failure mode triggered the warning.
        warning_type: "warning" or "critical".
        current_value: The metric value that triggered the warning.
        threshold: The threshold that was breached.
        recommended_action: What action should be taken.
        message: Human-readable error message.
    """

    def __init__(
        self,
        mode_id: "FailureModeId",
        warning_type: str,
        current_value: float,
        threshold: float,
        recommended_action: str,
        metric_name: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            mode_id: Which failure mode triggered the warning.
            warning_type: "warning" or "critical".
            current_value: The metric value that triggered.
            threshold: The threshold that was breached.
            recommended_action: What action should be taken.
            metric_name: Name of the metric.
            message: Optional custom message.
        """
        self.mode_id = mode_id
        self.warning_type = warning_type
        self.current_value = current_value
        self.threshold = threshold
        self.recommended_action = recommended_action
        self.metric_name = metric_name

        if message is None:
            emoji = "⚠️" if warning_type == "warning" else "🚨"
            message = (
                f"{emoji} [{mode_id.value}] Early {warning_type.upper()}: "
                f"{metric_name}={current_value} (threshold: {threshold}). "
                f"Action: {recommended_action}"
            )

        self.message = message
        super().__init__(self.message)


class QueryPerformanceViolationError(Exception):
    """Raised when a historical query exceeds the FR106 SLA.

    Constitutional Constraint (FR106):
    Historical queries SHALL complete within 30 seconds for ranges
    up to 10,000 events; larger ranges batched with progress indication.

    Attributes:
        query_id: Identifier for the query.
        event_count: Number of events in the query.
        duration_seconds: Actual duration of the query.
        sla_seconds: The SLA threshold (30 seconds for <10k events).
        message: Human-readable error message.
    """

    def __init__(
        self,
        query_id: str,
        event_count: int,
        duration_seconds: float,
        sla_seconds: float = 30.0,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            query_id: Identifier for the query.
            event_count: Number of events queried.
            duration_seconds: Actual query duration.
            sla_seconds: SLA threshold.
            message: Optional custom message.
        """
        self.query_id = query_id
        self.event_count = event_count
        self.duration_seconds = duration_seconds
        self.sla_seconds = sla_seconds
        self.overage_seconds = duration_seconds - sla_seconds

        if message is None:
            message = (
                f"FR106 violation: Query {query_id} took {duration_seconds:.2f}s "
                f"for {event_count} events (SLA: {sla_seconds}s, overage: {self.overage_seconds:.2f}s). "
                f"Historical queries must complete within {sla_seconds}s for <10k events."
            )

        self.message = message
        super().__init__(self.message)


class ConstitutionalEventSheddingError(Exception):
    """Raised when an attempt is made to shed a constitutional event.

    Constitutional Constraint (FR107):
    System SHALL NOT shed constitutional events under load; operational
    telemetry may be deprioritized but canonical events never dropped.

    This error should NEVER be recoverable - shedding constitutional
    events is a fundamental violation.

    Attributes:
        event_type: Type of constitutional event attempted to shed.
        reason: Why the shedding was attempted.
        message: Human-readable error message.
    """

    def __init__(
        self,
        event_type: str,
        reason: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            event_type: Type of constitutional event.
            reason: Why shedding was attempted (e.g., "load shedding").
            message: Optional custom message.
        """
        self.event_type = event_type
        self.reason = reason

        if message is None:
            message = (
                f"🚨 CRITICAL FR107 VIOLATION: Attempted to shed constitutional event "
                f"'{event_type}' for reason: {reason}. "
                f"Constitutional events MUST NEVER be shed. "
                f"Only operational telemetry may be deprioritized under load."
            )

        self.message = message
        super().__init__(self.message)


class LoadSheddingDecisionError(Exception):
    """Raised when there is an error in load shedding decision making.

    Constitutional Constraint (FR107):
    Load shedding decisions must be logged and constitutional events
    protected from shedding.

    Attributes:
        reason: Why the decision failed.
        current_load: Current load percentage.
        message: Human-readable error message.
    """

    def __init__(
        self,
        reason: str,
        current_load: Optional[float] = None,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            reason: Why the decision failed.
            current_load: Current load percentage if available.
            message: Optional custom message.
        """
        self.reason = reason
        self.current_load = current_load

        if message is None:
            load_info = f" (current load: {current_load:.1f}%)" if current_load else ""
            message = f"Load shedding decision error: {reason}{load_info}"

        self.message = message
        super().__init__(self.message)
