"""Suppression Detection Service.

This service monitors for failure suppression violations per FR-GOV-13.
It ensures that all failure signals are properly propagated and triggers
violations when suppression is detected.

Per Government PRD:
- FR-GOV-13: Duke/Earl constraints - No suppression of failure signals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- NFR-GOV-5: System may fail to enforce but must not conceal
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from src.application.ports.failure_propagation import (
    FailureSeverity,
    FailureSignal,
    FailureSignalType,
    SuppressionCheckResult,
    SuppressionDetectionMethod,
    SuppressionViolation,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ViolationRecord,
)

# Default configuration values
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_CHECK_INTERVAL_SECONDS = 10


@dataclass
class SuppressionDetectionConfig:
    """Configuration for suppression detection.

    Attributes:
        timeout_seconds: Max time before failure must be propagated
        check_interval_seconds: How often to check for suppression
        auto_escalate_to_conclave: Whether to auto-escalate violations
        critical_timeout_multiplier: Multiplier for critical failures (faster)
    """

    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS
    auto_escalate_to_conclave: bool = True
    critical_timeout_multiplier: float = 0.5  # Critical failures have half timeout


@dataclass
class MonitoredFailure:
    """A failure being monitored for suppression.

    Tracks when a failure was detected and whether it has been
    properly propagated within the timeout window.
    """

    signal: FailureSignal
    monitor_started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    timeout_at: datetime | None = None
    checked_count: int = 0

    def __post_init__(self) -> None:
        """Calculate timeout if not set."""
        if self.timeout_at is None:
            # Critical failures have shorter timeout
            multiplier = (
                0.5 if self.signal.severity == FailureSeverity.CRITICAL else 1.0
            )
            timeout_seconds = int(DEFAULT_TIMEOUT_SECONDS * multiplier)
            self.timeout_at = self.monitor_started_at + timedelta(
                seconds=timeout_seconds
            )

    @property
    def is_timed_out(self) -> bool:
        """Check if the failure has exceeded its timeout."""
        return (
            datetime.now(timezone.utc) > self.timeout_at if self.timeout_at else False
        )


class SuppressionDetectionService:
    """Service for detecting failure suppression violations.

    Per FR-GOV-13: Failure signals MUST be propagated, never suppressed.
    This service monitors for failures that are not propagated within
    the configured timeout and generates suppression violations.

    The service integrates with:
    - Knight Witness: To record violations per CT-12
    - Failure Propagation Port: To check propagation status
    - Conclave: To escalate critical violations

    Example usage:
        >>> service = SuppressionDetectionService(knight_witness)
        >>> service.start_monitoring(failure_signal)
        >>> result = await service.check_for_suppression(task_id)
        >>> if result.suppression_detected:
        ...     print(f"Violation: {result.violation}")
    """

    def __init__(
        self,
        knight_witness: KnightWitnessProtocol,
        config: SuppressionDetectionConfig | None = None,
    ) -> None:
        """Initialize the suppression detection service.

        Args:
            knight_witness: Knight witness protocol for recording violations
            config: Optional configuration
        """
        self._knight_witness = knight_witness
        self._config = config or SuppressionDetectionConfig()
        self._monitored_failures: dict[UUID, MonitoredFailure] = {}
        self._propagated_signals: set[UUID] = set()
        self._violations: dict[UUID, SuppressionViolation] = {}

    @property
    def config(self) -> SuppressionDetectionConfig:
        """Get current configuration."""
        return self._config

    @property
    def monitored_count(self) -> int:
        """Count of currently monitored failures."""
        return len(self._monitored_failures)

    @property
    def violation_count(self) -> int:
        """Count of detected violations."""
        return len(self._violations)

    def start_monitoring(
        self,
        signal: FailureSignal,
        timeout_seconds: int | None = None,
    ) -> MonitoredFailure:
        """Start monitoring a failure signal for suppression.

        This should be called immediately when a failure is detected
        by Duke/Earl, before propagation begins.

        Args:
            signal: The failure signal to monitor
            timeout_seconds: Optional override for timeout

        Returns:
            MonitoredFailure tracking object
        """
        # Calculate timeout
        if timeout_seconds is not None:
            timeout_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
        else:
            multiplier = (
                self._config.critical_timeout_multiplier
                if signal.severity == FailureSeverity.CRITICAL
                else 1.0
            )
            effective_timeout = int(self._config.timeout_seconds * multiplier)
            timeout_at = datetime.now(timezone.utc) + timedelta(
                seconds=effective_timeout
            )

        monitored = MonitoredFailure(
            signal=signal,
            monitor_started_at=datetime.now(timezone.utc),
            timeout_at=timeout_at,
        )

        self._monitored_failures[signal.signal_id] = monitored
        return monitored

    def mark_propagated(self, signal_id: UUID) -> bool:
        """Mark a failure signal as successfully propagated.

        This should be called after the failure has been propagated
        to Prince and witnessed by Knight.

        Args:
            signal_id: The propagated signal's ID

        Returns:
            True if signal was being monitored, False otherwise
        """
        if signal_id in self._monitored_failures:
            del self._monitored_failures[signal_id]
            self._propagated_signals.add(signal_id)
            return True
        return False

    def check_for_suppression(
        self,
        task_id: UUID | None = None,
    ) -> SuppressionCheckResult:
        """Check for suppression of failure signals.

        Examines all monitored failures (optionally filtered by task)
        and generates violations for any that have timed out.

        Args:
            task_id: Optional task ID to filter checks

        Returns:
            SuppressionCheckResult with violation if detected
        """
        now = datetime.now(timezone.utc)
        violations_found: list[SuppressionViolation] = []

        for signal_id, monitored in list(self._monitored_failures.items()):
            # Skip if filtering by task and doesn't match
            if task_id is not None and monitored.signal.task_id != task_id:
                continue

            # Increment check count
            monitored.checked_count += 1

            # Check for timeout
            if monitored.timeout_at and now > monitored.timeout_at:
                # Create suppression violation
                violation = SuppressionViolation.create(
                    signal_id=signal_id,
                    suppressing_archon_id=monitored.signal.source_archon_id,
                    detection_method=SuppressionDetectionMethod.TIMEOUT,
                    task_id=monitored.signal.task_id,
                    evidence={
                        "signal_type": monitored.signal.signal_type.value,
                        "severity": monitored.signal.severity.value,
                        "detected_at": monitored.signal.detected_at.isoformat(),
                        "timeout_at": monitored.timeout_at.isoformat(),
                        "exceeded_by_seconds": (
                            now - monitored.timeout_at
                        ).total_seconds(),
                        "check_count": monitored.checked_count,
                    },
                )
                violations_found.append(violation)
                self._violations[violation.violation_id] = violation

                # Remove from monitoring (violation recorded)
                del self._monitored_failures[signal_id]

        # Return first violation found (most common case)
        if violations_found:
            return SuppressionCheckResult(
                suppression_detected=True,
                violation=violations_found[0],
                escalated=False,  # Escalation happens separately
            )

        return SuppressionCheckResult(
            suppression_detected=False,
            violation=None,
            escalated=False,
        )

    def record_suppression_attempt(
        self,
        signal_id: UUID,
        suppressing_archon_id: str,
        task_id: UUID,
        method: SuppressionDetectionMethod,
        evidence: dict[str, Any] | None = None,
    ) -> SuppressionViolation:
        """Record an explicit suppression attempt.

        Use this when suppression is detected through means other than
        timeout (e.g., manual override attempt, state mismatch).

        Args:
            signal_id: The signal that was suppressed
            suppressing_archon_id: Archon who attempted suppression
            task_id: Associated task
            method: How suppression was detected
            evidence: Additional evidence

        Returns:
            Created SuppressionViolation
        """
        violation = SuppressionViolation.create(
            signal_id=signal_id,
            suppressing_archon_id=suppressing_archon_id,
            detection_method=method,
            task_id=task_id,
            evidence=evidence or {},
        )
        self._violations[violation.violation_id] = violation

        # Remove from monitoring if present
        if signal_id in self._monitored_failures:
            del self._monitored_failures[signal_id]

        return violation

    def witness_violation(
        self,
        violation: SuppressionViolation,
    ) -> UUID:
        """Create a witness statement for a suppression violation.

        Per CT-12: Witnessing creates accountability.
        This must be called for all suppression violations.

        Args:
            violation: The suppression violation to witness

        Returns:
            UUID of the witness statement
        """
        # Create violation record for Knight
        violation_record = ViolationRecord(
            violation_type="suppression_violation",
            violator_id=UUID(int=0),  # We don't have UUID for archon
            violator_name=violation.suppressing_archon_id,
            violator_rank="duke_or_earl",  # Could be either
            description=(
                f"Failure suppression detected via {violation.detection_method.value}. "
                f"Signal {violation.signal_id} was not propagated within timeout. "
                f"Per FR-GOV-13: Failure signals MUST be propagated."
            ),
            target_id=str(violation.task_id),
            target_type="task",
            prd_reference="FR-GOV-13",
            requires_acknowledgment=True,
            metadata={
                "violation_id": str(violation.violation_id),
                "signal_id": str(violation.signal_id),
                "detection_method": violation.detection_method.value,
                "evidence": violation.evidence,
            },
        )

        # Record with Knight
        statement = self._knight_witness.record_violation(violation_record)
        return statement.statement_id

    def escalate_to_conclave(
        self,
        violation: SuppressionViolation,
        witness_ref: UUID,
    ) -> SuppressionViolation:
        """Escalate a suppression violation to Conclave review.

        Per AC6: Suppression violations are escalated to Conclave.

        Args:
            violation: The violation to escalate
            witness_ref: Knight witness statement reference

        Returns:
            Updated SuppressionViolation with escalation
        """
        escalated = violation.with_escalation(witness_ref)
        self._violations[violation.violation_id] = escalated
        return escalated

    def get_violations(
        self,
        archon_id: str | None = None,
        since: datetime | None = None,
    ) -> list[SuppressionViolation]:
        """Get recorded suppression violations.

        Args:
            archon_id: Optional filter by archon
            since: Optional filter for violations after this time

        Returns:
            List of matching SuppressionViolations
        """
        violations = list(self._violations.values())

        if archon_id is not None:
            violations = [v for v in violations if v.suppressing_archon_id == archon_id]

        if since is not None:
            violations = [v for v in violations if v.detected_at >= since]

        return violations

    def get_monitored_failures(
        self,
        task_id: UUID | None = None,
    ) -> list[MonitoredFailure]:
        """Get currently monitored failures.

        Args:
            task_id: Optional filter by task

        Returns:
            List of MonitoredFailure objects
        """
        failures = list(self._monitored_failures.values())

        if task_id is not None:
            failures = [f for f in failures if f.signal.task_id == task_id]

        return failures

    def get_timed_out_failures(self) -> list[MonitoredFailure]:
        """Get failures that have exceeded their timeout.

        Returns:
            List of timed out MonitoredFailure objects
        """
        return [f for f in self._monitored_failures.values() if f.is_timed_out]

    def clear_monitoring(self, signal_id: UUID) -> bool:
        """Remove a signal from monitoring without recording violation.

        Use sparingly - this should only be used when there's a legitimate
        reason to stop monitoring (e.g., task cancelled).

        Args:
            signal_id: The signal to stop monitoring

        Returns:
            True if signal was being monitored
        """
        if signal_id in self._monitored_failures:
            del self._monitored_failures[signal_id]
            return True
        return False

    def create_failure_signal(
        self,
        signal_type: FailureSignalType,
        source_archon_id: str,
        task_id: UUID,
        severity: FailureSeverity,
        evidence: dict[str, Any],
        motion_ref: UUID | None = None,
    ) -> FailureSignal:
        """Create a failure signal and start monitoring.

        Convenience method that creates the signal and automatically
        starts monitoring for suppression.

        Args:
            signal_type: Type of failure
            source_archon_id: Duke/Earl Archon ID
            task_id: Failed task
            severity: Failure severity
            evidence: Supporting evidence
            motion_ref: Optional motion reference

        Returns:
            Created FailureSignal (already being monitored)
        """
        signal = FailureSignal.create(
            signal_type=signal_type,
            source_archon_id=source_archon_id,
            task_id=task_id,
            severity=severity,
            evidence=evidence,
            motion_ref=motion_ref,
        )
        self.start_monitoring(signal)
        return signal
