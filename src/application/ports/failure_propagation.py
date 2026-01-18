"""Failure Propagation Port (Administrative Branch - Failure Handling).

This module defines the abstract protocol for failure signal propagation.
Per FR-GOV-13: Duke/Earl constraints - No suppression of failure signals.

Per Government PRD:
- CT-11: Silent failure destroys legitimacy - HALT OVER DEGRADE
- CT-12: Witnessing creates accountability - All failures must be witnessed
- CT-13: Integrity outranks availability - Never suppress failure signals
- FR-GOV-13: Duke/Earl constraints - No suppression of failure signals
- NFR-GOV-5: System may fail to enforce but must not conceal

HARDENING-1: All timestamps must be provided via TimeAuthorityProtocol injection.
Factory methods require explicit timestamp parameters - no datetime.now() calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class FailureSignalType(Enum):
    """Types of failure signals from Duke/Earl execution.

    These represent different failure modes that can occur during
    task execution in the administrative branch.
    """

    TASK_FAILED = "task_failed"  # General task execution failure
    CONSTRAINT_VIOLATED = "constraint_violated"  # Execution constraint violated
    RESOURCE_EXHAUSTED = "resource_exhausted"  # Resource limits exceeded
    TIMEOUT = "timeout"  # Execution timeout
    BLOCKED = "blocked"  # Execution blocked by dependency
    INTENT_AMBIGUITY = "intent_ambiguity"  # Cannot determine intent


class FailureSeverity(Enum):
    """Severity levels for failure signals.

    Determines the urgency and handling of the failure signal.
    """

    CRITICAL = "critical"  # Halt execution, immediate Prince review
    HIGH = "high"  # Prince review in next cycle
    MEDIUM = "medium"  # Logged, advisory Prince notification
    LOW = "low"  # Logged only


class SuppressionDetectionMethod(Enum):
    """Methods for detecting failure suppression.

    Per FR-GOV-13: Failure suppression is prohibited.
    """

    TIMEOUT = "timeout"  # Failure not propagated within timeout
    MANUAL_OVERRIDE = "manual_override"  # Explicit suppression attempt
    STATE_MISMATCH = "state_mismatch"  # Failure observed but not reported
    AUDIT_DISCREPANCY = "audit_discrepancy"  # Audit found unreported failure


@dataclass(frozen=True)
class FailureSignal:
    """A failure signal emitted by Duke/Earl.

    Per FR-GOV-13: Failure signals MUST be propagated, never suppressed.
    Per CT-11: Silent failure destroys legitimacy.

    Attributes:
        signal_id: Unique identifier for this failure signal
        signal_type: Type of failure that occurred
        source_archon_id: Duke or Earl who detected the failure
        task_id: Reference to the failed task
        severity: Severity level of the failure
        evidence: Details supporting the failure
        detected_at: When the failure was detected
        propagated_at: When the failure was propagated (None if pending)
        prince_notified: Whether Prince has been notified
        motion_ref: Optional reference to related motion
        witness_ref: Optional reference to Knight witness statement
    """

    signal_id: UUID
    signal_type: FailureSignalType
    source_archon_id: str
    task_id: UUID
    severity: FailureSeverity
    evidence: dict[str, Any]
    detected_at: datetime
    propagated_at: datetime | None = None
    prince_notified: bool = False
    motion_ref: UUID | None = None
    witness_ref: UUID | None = None  # Reference to Knight witness statement

    @classmethod
    def create(
        cls,
        signal_type: FailureSignalType,
        source_archon_id: str,
        task_id: UUID,
        severity: FailureSeverity,
        evidence: dict[str, Any],
        timestamp: datetime,
        motion_ref: UUID | None = None,
    ) -> "FailureSignal":
        """Create a new failure signal.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            signal_type: Type of failure
            source_archon_id: Duke/Earl Archon ID who detected
            task_id: Task that failed
            severity: Failure severity
            evidence: Supporting evidence
            timestamp: Current time from TimeAuthorityProtocol
            motion_ref: Optional related motion

        Returns:
            New immutable FailureSignal with generated ID
        """
        return cls(
            signal_id=uuid4(),
            signal_type=signal_type,
            source_archon_id=source_archon_id,
            task_id=task_id,
            severity=severity,
            evidence=evidence,
            detected_at=timestamp,
            motion_ref=motion_ref,
        )

    def with_propagation(
        self, timestamp: datetime, witness_ref: UUID | None = None
    ) -> "FailureSignal":
        """Mark signal as propagated.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            timestamp: Current time from TimeAuthorityProtocol
            witness_ref: Optional Knight witness statement reference

        Returns:
            New FailureSignal with propagated_at set
        """
        return FailureSignal(
            signal_id=self.signal_id,
            signal_type=self.signal_type,
            source_archon_id=self.source_archon_id,
            task_id=self.task_id,
            severity=self.severity,
            evidence=self.evidence,
            detected_at=self.detected_at,
            propagated_at=timestamp,
            prince_notified=self.prince_notified,
            motion_ref=self.motion_ref,
            witness_ref=witness_ref,
        )

    def with_prince_notification(self) -> "FailureSignal":
        """Mark signal as Prince-notified.

        Returns:
            New FailureSignal with prince_notified=True
        """
        return FailureSignal(
            signal_id=self.signal_id,
            signal_type=self.signal_type,
            source_archon_id=self.source_archon_id,
            task_id=self.task_id,
            severity=self.severity,
            evidence=self.evidence,
            detected_at=self.detected_at,
            propagated_at=self.propagated_at,
            prince_notified=True,
            motion_ref=self.motion_ref,
            witness_ref=self.witness_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "signal_id": str(self.signal_id),
            "signal_type": self.signal_type.value,
            "source_archon_id": self.source_archon_id,
            "task_id": str(self.task_id),
            "severity": self.severity.value,
            "evidence": self.evidence,
            "detected_at": self.detected_at.isoformat(),
            "propagated_at": self.propagated_at.isoformat()
            if self.propagated_at
            else None,
            "prince_notified": self.prince_notified,
            "motion_ref": str(self.motion_ref) if self.motion_ref else None,
            "witness_ref": str(self.witness_ref) if self.witness_ref else None,
        }

    @property
    def is_propagated(self) -> bool:
        """Check if signal has been propagated."""
        return self.propagated_at is not None

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical failure."""
        return self.severity == FailureSeverity.CRITICAL


@dataclass(frozen=True)
class SuppressionViolation:
    """A violation where failure was suppressed.

    This is a CRITICAL governance violation per FR-GOV-13.
    Suppression violations trigger immediate Conclave review.

    Attributes:
        violation_id: Unique identifier for this violation
        signal_id: Original failure signal that was suppressed
        suppressing_archon_id: Archon who suppressed (or failed to propagate)
        detection_method: How the suppression was detected
        detected_at: When suppression was detected
        task_id: Task associated with suppressed failure
        evidence: Details of the suppression attempt
        escalated_to_conclave: Whether escalated to Conclave
        witness_ref: Reference to Knight witness statement
    """

    violation_id: UUID
    signal_id: UUID
    suppressing_archon_id: str
    detection_method: SuppressionDetectionMethod
    detected_at: datetime
    task_id: UUID
    evidence: dict[str, Any] = field(default_factory=dict)
    escalated_to_conclave: bool = False
    witness_ref: UUID | None = None

    @classmethod
    def create(
        cls,
        signal_id: UUID,
        suppressing_archon_id: str,
        detection_method: SuppressionDetectionMethod,
        task_id: UUID,
        timestamp: datetime,
        evidence: dict[str, Any] | None = None,
    ) -> "SuppressionViolation":
        """Create a new suppression violation.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            signal_id: The suppressed failure signal ID
            suppressing_archon_id: Archon responsible for suppression
            detection_method: How suppression was detected
            task_id: Task associated with failure
            timestamp: Current time from TimeAuthorityProtocol
            evidence: Supporting evidence

        Returns:
            New immutable SuppressionViolation
        """
        return cls(
            violation_id=uuid4(),
            signal_id=signal_id,
            suppressing_archon_id=suppressing_archon_id,
            detection_method=detection_method,
            detected_at=timestamp,
            task_id=task_id,
            evidence=evidence or {},
        )

    def with_escalation(self, witness_ref: UUID) -> "SuppressionViolation":
        """Mark violation as escalated to Conclave.

        Args:
            witness_ref: Knight witness statement reference

        Returns:
            New SuppressionViolation with escalation
        """
        return SuppressionViolation(
            violation_id=self.violation_id,
            signal_id=self.signal_id,
            suppressing_archon_id=self.suppressing_archon_id,
            detection_method=self.detection_method,
            detected_at=self.detected_at,
            task_id=self.task_id,
            evidence=self.evidence,
            escalated_to_conclave=True,
            witness_ref=witness_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "violation_id": str(self.violation_id),
            "signal_id": str(self.signal_id),
            "suppressing_archon_id": self.suppressing_archon_id,
            "detection_method": self.detection_method.value,
            "detected_at": self.detected_at.isoformat(),
            "task_id": str(self.task_id),
            "evidence": self.evidence,
            "escalated_to_conclave": self.escalated_to_conclave,
            "witness_ref": str(self.witness_ref) if self.witness_ref else None,
        }


@dataclass(frozen=True)
class PrinceNotificationContext:
    """Context for notifying Prince of a failure.

    Per AC4: Prince receives full context for evaluation.
    """

    signal: FailureSignal
    task_spec: dict[str, Any]  # AegisTaskSpec as dict
    execution_result: dict[str, Any]
    evidence: list[dict[str, Any]]
    timeline: list[dict[str, Any]]  # Events leading to failure

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "signal": self.signal.to_dict(),
            "task_spec": self.task_spec,
            "execution_result": self.execution_result,
            "evidence": self.evidence,
            "timeline": self.timeline,
        }


@dataclass
class PropagationResult:
    """Result of propagating a failure signal."""

    success: bool
    signal: FailureSignal | None = None
    witness_ref: UUID | None = None
    error: str | None = None


@dataclass
class PrinceNotificationResult:
    """Result of notifying Prince about a failure."""

    success: bool
    prince_id: str | None = None
    finding_ref: UUID | None = None  # If Prince creates immediate finding
    error: str | None = None


@dataclass
class SuppressionCheckResult:
    """Result of checking for suppression violations."""

    suppression_detected: bool
    violation: SuppressionViolation | None = None
    escalated: bool = False


class FailurePropagationProtocol(ABC):
    """Abstract protocol for failure signal propagation.

    Per Government PRD:
    - FR-GOV-13: Duke/Earl constraints - No suppression of failure signals
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability
    - CT-13: Integrity outranks availability

    This protocol ensures:
    1. Failures are immediately propagated to Prince
    2. All failures are witnessed by Knight before propagation
    3. Suppression attempts are detected and escalated
    4. Full failure chain integrity is maintained
    """

    @abstractmethod
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

        Note:
            Knight witnesses the failure before propagation per CT-12.
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
            timeout_seconds: Max time before suppression violation (default 30s)

        Returns:
            SuppressionCheckResult with violation if detected
        """
        ...

    @abstractmethod
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

        Note:
            Automatically witnessed by Knight and escalated to Conclave.
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...
