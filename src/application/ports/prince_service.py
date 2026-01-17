"""Prince Service Port (Judicial Branch).

This module defines the abstract protocol for Prince-rank judicial functions.
Princes evaluate compliance with original intent and approved execution plans.

Per Government PRD FR-GOV-14: Princes evaluate whether WHAT was honored, HOW followed
approved plan, constraints violated; issue compliance findings.
Per Government PRD FR-GOV-15: Princes may invalidate execution, force reconsideration,
trigger Conclave review.
Per Government PRD FR-GOV-16: Princes may NOT introduce motions, may NOT define
execution plans.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ComplianceVerdict(Enum):
    """Verdict from compliance evaluation."""

    COMPLIANT = "compliant"  # Full compliance with intent and plan
    PARTIALLY_COMPLIANT = "partially_compliant"  # Some criteria met
    NON_COMPLIANT = "non_compliant"  # Significant deviations
    INVALID = "invalid"  # Execution invalidated


class CriterionVerdict(Enum):
    """Verdict for individual criterion evaluation."""

    MET = "met"  # Criterion fully satisfied
    PARTIALLY_MET = "partially_met"  # Criterion partially satisfied
    NOT_MET = "not_met"  # Criterion not satisfied
    UNMEASURABLE = "unmeasurable"  # Cannot be measured (missing evidence)


class ViolationType(Enum):
    """Types of compliance violations."""

    INTENT_DEVIATION = "intent_deviation"  # WHAT was not honored
    PLAN_DEVIATION = "plan_deviation"  # HOW differed from approved plan
    CONSTRAINT_VIOLATION = "constraint_violation"  # Constraints were violated
    UNAUTHORIZED_ACTION = "unauthorized_action"  # Action outside scope
    INCOMPLETE_EXECUTION = "incomplete_execution"  # Required outputs missing


class ReviewSeverity(Enum):
    """Severity levels for Conclave review triggers."""

    CRITICAL = "critical"  # Immediate review required
    HIGH = "high"  # Review in next session
    MEDIUM = "medium"  # Advisory review
    LOW = "low"  # Informational only


@dataclass(frozen=True)
class Evidence:
    """Evidence supporting a compliance evaluation."""

    evidence_id: UUID
    description: str
    source: str  # Where the evidence came from
    data: dict[str, Any]
    collected_at: datetime

    @classmethod
    def create(
        cls,
        description: str,
        source: str,
        data: dict[str, Any],
    ) -> "Evidence":
        """Create new evidence."""
        return cls(
            evidence_id=uuid4(),
            description=description,
            source=source,
            data=data,
            collected_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "evidence_id": str(self.evidence_id),
            "description": self.description,
            "source": self.source,
            "data": self.data,
            "collected_at": self.collected_at.isoformat(),
        }


@dataclass(frozen=True)
class CriterionResult:
    """Result of evaluating a single criterion."""

    criterion_id: str
    criterion_description: str
    verdict: CriterionVerdict
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "criterion_id": self.criterion_id,
            "criterion_description": self.criterion_description,
            "verdict": self.verdict.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ComplianceViolation:
    """A compliance violation found during evaluation."""

    violation_id: UUID
    violation_type: ViolationType
    description: str
    severity: ReviewSeverity
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    remediation: str | None = None

    @classmethod
    def create(
        cls,
        violation_type: ViolationType,
        description: str,
        severity: ReviewSeverity,
        evidence: list[Evidence] | None = None,
        remediation: str | None = None,
    ) -> "ComplianceViolation":
        """Create a new violation."""
        return cls(
            violation_id=uuid4(),
            violation_type=violation_type,
            description=description,
            severity=severity,
            evidence=tuple(evidence or []),
            remediation=remediation,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "violation_id": str(self.violation_id),
            "violation_type": self.violation_type.value,
            "description": self.description,
            "severity": self.severity.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class ComplianceFinding:
    """Complete compliance finding from judicial evaluation.

    This is the Prince's formal output after evaluating execution
    against the original intent and approved plan.
    """

    finding_id: UUID
    plan_ref: UUID  # Reference to execution plan evaluated
    motion_ref: UUID  # Reference to original motion
    verdict: ComplianceVerdict
    criteria_results: tuple[CriterionResult, ...]
    violations: tuple[ComplianceViolation, ...]
    recommendations: tuple[str, ...]
    evaluated_by: str  # Prince Archon ID
    evaluated_at: datetime
    summary: str

    @classmethod
    def create(
        cls,
        plan_ref: UUID,
        motion_ref: UUID,
        verdict: ComplianceVerdict,
        criteria_results: list[CriterionResult],
        violations: list[ComplianceViolation],
        recommendations: list[str],
        evaluated_by: str,
        summary: str,
    ) -> "ComplianceFinding":
        """Create a new compliance finding."""
        return cls(
            finding_id=uuid4(),
            plan_ref=plan_ref,
            motion_ref=motion_ref,
            verdict=verdict,
            criteria_results=tuple(criteria_results),
            violations=tuple(violations),
            recommendations=tuple(recommendations),
            evaluated_by=evaluated_by,
            evaluated_at=datetime.now(timezone.utc),
            summary=summary,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "finding_id": str(self.finding_id),
            "plan_ref": str(self.plan_ref),
            "motion_ref": str(self.motion_ref),
            "verdict": self.verdict.value,
            "criteria_results": [r.to_dict() for r in self.criteria_results],
            "violations": [v.to_dict() for v in self.violations],
            "recommendations": list(self.recommendations),
            "evaluated_by": self.evaluated_by,
            "evaluated_at": self.evaluated_at.isoformat(),
            "summary": self.summary,
        }

    @property
    def is_compliant(self) -> bool:
        """Check if finding indicates compliance."""
        return self.verdict == ComplianceVerdict.COMPLIANT

    @property
    def violation_count(self) -> int:
        """Count of violations found."""
        return len(self.violations)

    @property
    def has_critical_violations(self) -> bool:
        """Check if there are critical violations."""
        return any(v.severity == ReviewSeverity.CRITICAL for v in self.violations)


@dataclass
class InvalidationResult:
    """Result of invalidating an execution."""

    success: bool
    invalidation_id: UUID | None = None
    plan_ref: UUID | None = None
    reason: str | None = None
    error: str | None = None


@dataclass
class ConclaveReviewRequest:
    """Request to trigger Conclave review."""

    motion_ref: UUID
    finding: ComplianceFinding
    severity: ReviewSeverity
    questions: list[str]  # Questions for Conclave consideration


@dataclass
class ConclaveReviewResult:
    """Result of triggering Conclave review."""

    success: bool
    review_id: UUID | None = None
    agenda_position: int | None = None  # Position in next Conclave agenda
    error: str | None = None


@dataclass
class EvaluationRequest:
    """Request to evaluate compliance."""

    plan_ref: UUID
    motion_ref: UUID
    original_intent: str
    execution_result: dict[str, Any]  # Results from Duke/Earl execution
    prince_id: str  # Prince's Archon ID


@dataclass
class EvaluationResult:
    """Result of compliance evaluation."""

    success: bool
    finding: ComplianceFinding | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "finding": self.finding.to_dict() if self.finding else None,
            "error": self.error,
        }


class PrinceServiceProtocol(ABC):
    """Abstract protocol for Prince-rank judicial functions.

    Per Government PRD:
    - FR-GOV-14: Evaluate whether WHAT was honored, HOW followed approved plan,
                 constraints violated; issue compliance findings
    - FR-GOV-15: May invalidate execution, force reconsideration, trigger
                 Conclave review
    - FR-GOV-16: May NOT introduce motions, may NOT define execution plans

    This protocol explicitly EXCLUDES:
    - Motion introduction (King function)
    - Execution definition (President function)
    - Task execution (Duke/Earl function)
    """

    @abstractmethod
    async def evaluate_compliance(
        self,
        request: EvaluationRequest,
    ) -> EvaluationResult:
        """Evaluate execution results against original intent and plan.

        Per FR-GOV-14: Checks WHAT honored, HOW followed, constraints respected.

        Args:
            request: Evaluation request with execution results

        Returns:
            EvaluationResult with compliance finding

        Note:
            Findings are witnessed by Knight per FR-GOV-20.
        """
        ...

    @abstractmethod
    async def issue_finding(
        self,
        finding: ComplianceFinding,
    ) -> bool:
        """Issue a formal compliance finding.

        Args:
            finding: The compliance finding to issue

        Returns:
            True if successfully issued and witnessed
        """
        ...

    @abstractmethod
    async def invalidate_execution(
        self,
        plan_ref: UUID,
        finding: ComplianceFinding,
        reason: str,
    ) -> InvalidationResult:
        """Invalidate a non-compliant execution.

        Per FR-GOV-15: Princes may invalidate execution.

        Args:
            plan_ref: Reference to the execution plan
            finding: Compliance finding supporting invalidation
            reason: Detailed reason for invalidation

        Returns:
            InvalidationResult with success/failure
        """
        ...

    @abstractmethod
    async def trigger_conclave_review(
        self,
        request: ConclaveReviewRequest,
    ) -> ConclaveReviewResult:
        """Trigger Conclave reconsideration of a motion.

        Per FR-GOV-15: Princes may force reconsideration and trigger
        Conclave review for serious violations.

        Args:
            request: Review request with finding and questions

        Returns:
            ConclaveReviewResult with agenda position
        """
        ...

    @abstractmethod
    async def measure_criterion(
        self,
        criterion_id: str,
        criterion_description: str,
        evidence: list[Evidence],
    ) -> CriterionResult:
        """Evaluate a single success criterion.

        Args:
            criterion_id: ID of the criterion
            criterion_description: Description of what to evaluate
            evidence: Evidence to evaluate against

        Returns:
            CriterionResult with verdict
        """
        ...

    @abstractmethod
    async def get_finding(self, finding_id: UUID) -> ComplianceFinding | None:
        """Retrieve a compliance finding by ID.

        Args:
            finding_id: UUID of the finding

        Returns:
            ComplianceFinding if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_findings_by_motion(
        self,
        motion_ref: UUID,
    ) -> list[ComplianceFinding]:
        """Get all findings for a specific motion.

        Args:
            motion_ref: The motion's UUID

        Returns:
            List of compliance findings for that motion
        """
        ...

    @abstractmethod
    async def get_findings_by_plan(
        self,
        plan_ref: UUID,
    ) -> list[ComplianceFinding]:
        """Get all findings for a specific execution plan.

        Args:
            plan_ref: The plan's UUID

        Returns:
            List of compliance findings for that plan
        """
        ...

    # =========================================================================
    # EXPLICITLY EXCLUDED METHODS
    # These methods are NOT part of the Prince Service per FR-GOV-16
    # =========================================================================

    # def introduce_motion(self) -> None:  # PROHIBITED (King function)
    # def define_execution(self) -> None:  # PROHIBITED (President function)
    # def execute_task(self) -> None:  # PROHIBITED (Duke/Earl function)
    # def ratify_motion(self) -> None:  # PROHIBITED (Conclave function)
