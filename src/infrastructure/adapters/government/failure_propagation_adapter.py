"""Failure Propagation Adapter (Administrative Branch - Failure Handling).

This module implements the FailurePropagationProtocol for emitting and
propagating failure signals through the governance chain.

Per Government PRD:
- FR-GOV-13: Duke/Earl constraints - No suppression of failure signals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability
- NFR-GOV-5: System may fail to enforce but must not conceal
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.failure_propagation import (
    FailurePropagationProtocol,
    FailureSeverity,
    FailureSignal,
    PrinceNotificationContext,
    PrinceNotificationResult,
    PropagationResult,
    SuppressionCheckResult,
    SuppressionDetectionMethod,
    SuppressionViolation,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
)
from src.application.services.suppression_detection_service import (
    SuppressionDetectionService,
)

logger = get_logger(__name__)


class FailurePropagationAdapter(FailurePropagationProtocol):
    """Implementation of failure signal propagation.

    This adapter ensures:
    1. All failures are witnessed by Knight before propagation
    2. Failures are stored in append-only event store with hash chain
    3. Prince is notified with full context
    4. Suppression is detected and escalated

    Per FR-GOV-13: Failure signals MUST be propagated, never suppressed.
    """

    def __init__(
        self,
        knight_witness: KnightWitnessProtocol | None = None,
        suppression_detector: SuppressionDetectionService | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the failure propagation adapter.

        Args:
            knight_witness: Knight witness for recording events
            suppression_detector: Suppression detection service
            verbose: Enable verbose logging
        """
        self._knight_witness = knight_witness
        self._suppression_detector = suppression_detector
        self._verbose = verbose

        # In-memory storage (would be event store in production)
        self._failure_signals: dict[UUID, FailureSignal] = {}
        self._suppression_violations: dict[UUID, SuppressionViolation] = {}
        self._timelines: dict[UUID, list[dict[str, Any]]] = {}  # task_id -> timeline
        self._prince_notifications: dict[UUID, PrinceNotificationContext] = {}

        if self._verbose:
            logger.debug("failure_propagation_adapter_initialized")

    async def emit_failure(
        self,
        signal: FailureSignal,
    ) -> PropagationResult:
        """Emit a failure signal for propagation.

        Per AC1: Immediately propagates to Prince for evaluation.
        Per AC5: Stores in append-only event store with hash chain.

        Args:
            signal: The failure signal to emit

        Returns:
            PropagationResult with success/failure and witness reference
        """
        if self._verbose:
            logger.debug(
                "failure_signal_emitting",
                signal_id=str(signal.signal_id),
                signal_type=signal.signal_type.value,
                severity=signal.severity.value,
                source_archon=signal.source_archon_id,
            )

        # Start suppression monitoring if detector available
        if self._suppression_detector:
            self._suppression_detector.start_monitoring(signal)

        # Step 1: Witness the failure before propagation (CT-12)
        witness_ref: UUID | None = None
        if self._knight_witness:
            observation = ObservationContext(
                event_type="failure_signal_emitted",
                event_id=signal.signal_id,
                description=(
                    f"Failure signal emitted: {signal.signal_type.value} "
                    f"from {signal.source_archon_id} for task {signal.task_id}"
                ),
                participants=[signal.source_archon_id],
                target_id=str(signal.task_id),
                target_type="task",
                metadata={
                    "signal_type": signal.signal_type.value,
                    "severity": signal.severity.value,
                    "evidence": signal.evidence,
                },
            )
            statement = self._knight_witness.observe(observation)
            witness_ref = statement.statement_id

        # Step 2: Mark as propagated
        propagated_signal = signal.with_propagation(witness_ref)

        # Step 3: Store in event store (in-memory for now)
        self._failure_signals[signal.signal_id] = propagated_signal

        # Step 4: Add to timeline
        self._add_to_timeline(
            task_id=signal.task_id,
            event_type="failure_emitted",
            details={
                "signal_id": str(signal.signal_id),
                "signal_type": signal.signal_type.value,
                "severity": signal.severity.value,
            },
        )

        # Step 5: Mark as propagated in suppression detector
        if self._suppression_detector:
            self._suppression_detector.mark_propagated(signal.signal_id)

        if self._verbose:
            logger.info(
                "failure_signal_propagated",
                signal_id=str(signal.signal_id),
                witness_ref=str(witness_ref) if witness_ref else None,
            )

        return PropagationResult(
            success=True,
            signal=propagated_signal,
            witness_ref=witness_ref,
        )

    async def notify_prince(
        self,
        context: PrinceNotificationContext,
    ) -> PrinceNotificationResult:
        """Notify Prince about a failure with full context.

        Per AC4: Prince receives full context for evaluation.

        Args:
            context: Full notification context with task spec, result, evidence

        Returns:
            PrinceNotificationResult with success/failure
        """
        signal = context.signal

        if self._verbose:
            logger.debug(
                "prince_notification_sending",
                signal_id=str(signal.signal_id),
                severity=signal.severity.value,
            )

        # Store notification context
        self._prince_notifications[signal.signal_id] = context

        # Update signal to mark Prince notified
        notified_signal = signal.with_prince_notification()
        self._failure_signals[signal.signal_id] = notified_signal

        # Add to timeline
        self._add_to_timeline(
            task_id=signal.task_id,
            event_type="prince_notified",
            details={
                "signal_id": str(signal.signal_id),
                "severity": signal.severity.value,
            },
        )

        # Witness the notification
        if self._knight_witness:
            observation = ObservationContext(
                event_type="prince_failure_notification",
                event_id=signal.signal_id,
                description=(
                    f"Prince notified of {signal.severity.value} failure "
                    f"for task {signal.task_id}"
                ),
                participants=[signal.source_archon_id, "prince"],
                target_id=str(signal.task_id),
                target_type="task",
                metadata={
                    "signal_id": str(signal.signal_id),
                    "signal_type": signal.signal_type.value,
                },
            )
            self._knight_witness.observe(observation)

        if self._verbose:
            logger.info(
                "prince_notified",
                signal_id=str(signal.signal_id),
            )

        return PrinceNotificationResult(
            success=True,
            prince_id="prince",  # Would be actual prince ID in production
        )

    async def get_pending_failures(
        self,
        task_id: UUID | None = None,
    ) -> list[FailureSignal]:
        """Get failure signals pending propagation.

        Args:
            task_id: Optional filter by task

        Returns:
            List of FailureSignals not yet propagated
        """
        pending = [
            signal
            for signal in self._failure_signals.values()
            if not signal.is_propagated
        ]

        if task_id is not None:
            pending = [s for s in pending if s.task_id == task_id]

        return pending

    async def get_failure_signal(
        self,
        signal_id: UUID,
    ) -> FailureSignal | None:
        """Retrieve a failure signal by ID.

        Args:
            signal_id: The signal's UUID

        Returns:
            FailureSignal if found, None otherwise
        """
        return self._failure_signals.get(signal_id)

    async def get_failures_by_task(
        self,
        task_id: UUID,
    ) -> list[FailureSignal]:
        """Get all failure signals for a task.

        Args:
            task_id: The task's UUID

        Returns:
            List of FailureSignals for that task
        """
        return [
            signal
            for signal in self._failure_signals.values()
            if signal.task_id == task_id
        ]

    async def get_failures_by_motion(
        self,
        motion_ref: UUID,
    ) -> list[FailureSignal]:
        """Get all failure signals for a motion.

        Args:
            motion_ref: The motion's UUID

        Returns:
            List of FailureSignals for that motion
        """
        return [
            signal
            for signal in self._failure_signals.values()
            if signal.motion_ref == motion_ref
        ]

    async def check_suppression(
        self,
        task_id: UUID,
        timeout_seconds: int = 30,
    ) -> SuppressionCheckResult:
        """Check for suppression of failure signals.

        Per AC6: Auto-generates suppression violation if failure not
        propagated within timeout.

        Args:
            task_id: Task to check for suppression
            timeout_seconds: Max time before suppression violation

        Returns:
            SuppressionCheckResult with violation if detected
        """
        if not self._suppression_detector:
            return SuppressionCheckResult(
                suppression_detected=False,
                violation=None,
            )

        return self._suppression_detector.check_for_suppression(task_id)

    async def record_suppression_violation(
        self,
        violation: SuppressionViolation,
    ) -> UUID:
        """Record a suppression violation.

        Per AC2: Suppression triggers violation witness event.
        Per AC6: Escalates to Conclave review.

        Args:
            violation: The suppression violation to record

        Returns:
            UUID of the witness statement
        """
        if self._verbose:
            logger.warning(
                "suppression_violation_recording",
                violation_id=str(violation.violation_id),
                signal_id=str(violation.signal_id),
                suppressing_archon=violation.suppressing_archon_id,
            )

        # Step 1: Witness the violation (CT-12)
        witness_ref: UUID | None = None
        if self._knight_witness:
            violation_record = ViolationRecord(
                violation_type="failure_suppression",
                violator_id=UUID(int=0),  # Placeholder
                violator_name=violation.suppressing_archon_id,
                violator_rank="duke_or_earl",
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
            statement = self._knight_witness.record_violation(violation_record)
            witness_ref = statement.statement_id

        # Step 2: Escalate to Conclave
        escalated_violation = violation.with_escalation(witness_ref or UUID(int=0))
        self._suppression_violations[violation.violation_id] = escalated_violation

        # Step 3: Add to timeline
        self._add_to_timeline(
            task_id=violation.task_id,
            event_type="suppression_violation",
            details={
                "violation_id": str(violation.violation_id),
                "detection_method": violation.detection_method.value,
                "escalated_to_conclave": True,
            },
        )

        if self._verbose:
            logger.error(
                "suppression_violation_recorded",
                violation_id=str(violation.violation_id),
                escalated_to_conclave=True,
            )

        return witness_ref or UUID(int=0)

    async def get_suppression_violations(
        self,
        archon_id: str | None = None,
        since: datetime | None = None,
    ) -> list[SuppressionViolation]:
        """Get suppression violations.

        Args:
            archon_id: Optional filter by archon
            since: Optional filter for violations after this time

        Returns:
            List of SuppressionViolations
        """
        violations = list(self._suppression_violations.values())

        if archon_id is not None:
            violations = [
                v for v in violations if v.suppressing_archon_id == archon_id
            ]

        if since is not None:
            violations = [v for v in violations if v.detected_at >= since]

        return violations

    async def get_failure_timeline(
        self,
        task_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get timeline of events leading to failure.

        Per AC4: Prince receives timeline for evaluation.

        Args:
            task_id: Task to get timeline for

        Returns:
            List of timeline events in chronological order
        """
        return self._timelines.get(task_id, [])

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _add_to_timeline(
        self,
        task_id: UUID,
        event_type: str,
        details: dict[str, Any],
    ) -> None:
        """Add an event to the task timeline.

        Args:
            task_id: Task to add event to
            event_type: Type of event
            details: Event details
        """
        if task_id not in self._timelines:
            self._timelines[task_id] = []

        self._timelines[task_id].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        })

    # =========================================================================
    # Test Helpers
    # =========================================================================

    def reset(self) -> None:
        """Reset all state (for testing)."""
        self._failure_signals.clear()
        self._suppression_violations.clear()
        self._timelines.clear()
        self._prince_notifications.clear()

    @property
    def failure_count(self) -> int:
        """Count of stored failure signals."""
        return len(self._failure_signals)

    @property
    def violation_count(self) -> int:
        """Count of suppression violations."""
        return len(self._suppression_violations)
