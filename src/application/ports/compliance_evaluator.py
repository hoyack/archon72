"""Compliance Evaluator Port.

This module defines the abstract protocol for compliance evaluation tools.
The Compliance Evaluator provides mechanical measurement capabilities used
by the Prince Service for judicial evaluation.

Per Government PRD FR-GOV-14: Princes evaluate compliance with WHAT (intent)
and HOW (plan). This port provides the measurement infrastructure.

Key distinction:
- ComplianceEvaluator: Mechanical measurement (no judgment)
- PrinceService: Judicial judgment and enforcement
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MeasurementVerdict(Enum):
    """Verdict from measuring a criterion."""

    MET = "met"  # Criterion fully satisfied
    PARTIALLY_MET = "partially_met"  # Criterion partially satisfied
    NOT_MET = "not_met"  # Criterion not satisfied
    UNMEASURABLE = "unmeasurable"  # Cannot be measured (insufficient evidence)


class OverallCompliance(Enum):
    """Overall compliance assessment."""

    FULL = "full"  # All criteria met
    PARTIAL = "partial"  # Most criteria met
    INSUFFICIENT = "insufficient"  # Too few criteria met
    FAILED = "failed"  # Critical criteria not met


@dataclass(frozen=True)
class ExecutionEvidence:
    """Evidence collected from task execution.

    Evidence provides data supporting compliance measurement.
    Chain of custody is maintained via evidence_id and collection metadata.
    """

    evidence_id: UUID
    description: str
    source: str  # Where evidence was collected from
    evidence_type: str  # logs, outputs, metrics, states, etc.
    data: dict[str, Any]
    collected_at: datetime
    collector: str  # Who/what collected the evidence

    @classmethod
    def create(
        cls,
        description: str,
        source: str,
        evidence_type: str,
        data: dict[str, Any],
        collector: str = "compliance_evaluator",
    ) -> "ExecutionEvidence":
        """Create new execution evidence."""
        return cls(
            evidence_id=uuid4(),
            description=description,
            source=source,
            evidence_type=evidence_type,
            data=data,
            collected_at=datetime.now(timezone.utc),
            collector=collector,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "evidence_id": str(self.evidence_id),
            "description": self.description,
            "source": self.source,
            "evidence_type": self.evidence_type,
            "data": self.data,
            "collected_at": self.collected_at.isoformat(),
            "collector": self.collector,
        }


@dataclass(frozen=True)
class SuccessCriterion:
    """A success criterion from the task specification.

    Defines what must be achieved for the criterion to be considered met.
    """

    criterion_id: str
    description: str
    measurement_method: str  # How to measure this criterion
    threshold: str | None = None  # Optional threshold for quantitative criteria
    required: bool = True  # Whether this criterion is mandatory

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "criterion_id": self.criterion_id,
            "description": self.description,
            "measurement_method": self.measurement_method,
            "threshold": self.threshold,
            "required": self.required,
        }


@dataclass(frozen=True)
class CriterionMeasurement:
    """Result of measuring a single criterion.

    Contains the verdict and supporting evidence.
    """

    criterion: SuccessCriterion
    verdict: MeasurementVerdict
    evidence_refs: tuple[UUID, ...]  # References to supporting evidence
    measured_value: str | None = None  # Actual measured value if quantitative
    notes: str | None = None
    measured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "criterion": self.criterion.to_dict(),
            "verdict": self.verdict.value,
            "evidence_refs": [str(ref) for ref in self.evidence_refs],
            "measured_value": self.measured_value,
            "notes": self.notes,
            "measured_at": self.measured_at.isoformat(),
        }

    @property
    def is_met(self) -> bool:
        """Check if criterion is met (fully or partially)."""
        return self.verdict in (MeasurementVerdict.MET, MeasurementVerdict.PARTIALLY_MET)


@dataclass(frozen=True)
class ComplianceEvaluation:
    """Complete compliance evaluation result.

    Contains all criterion measurements and overall assessment.
    This is the output of the evaluation process, before judicial judgment.
    """

    evaluation_id: UUID
    task_spec_ref: UUID  # Reference to the AegisTaskSpec
    motion_ref: UUID  # Reference to original motion
    measurements: tuple[CriterionMeasurement, ...]
    evidence_collected: tuple[ExecutionEvidence, ...]
    overall: OverallCompliance
    summary: str
    evaluated_at: datetime

    @classmethod
    def create(
        cls,
        task_spec_ref: UUID,
        motion_ref: UUID,
        measurements: list[CriterionMeasurement],
        evidence_collected: list[ExecutionEvidence],
        overall: OverallCompliance,
        summary: str,
    ) -> "ComplianceEvaluation":
        """Create a new compliance evaluation."""
        return cls(
            evaluation_id=uuid4(),
            task_spec_ref=task_spec_ref,
            motion_ref=motion_ref,
            measurements=tuple(measurements),
            evidence_collected=tuple(evidence_collected),
            overall=overall,
            summary=summary,
            evaluated_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "evaluation_id": str(self.evaluation_id),
            "task_spec_ref": str(self.task_spec_ref),
            "motion_ref": str(self.motion_ref),
            "measurements": [m.to_dict() for m in self.measurements],
            "evidence_collected": [e.to_dict() for e in self.evidence_collected],
            "overall": self.overall.value,
            "summary": self.summary,
            "evaluated_at": self.evaluated_at.isoformat(),
        }

    @property
    def met_count(self) -> int:
        """Count of criteria fully met."""
        return sum(1 for m in self.measurements if m.verdict == MeasurementVerdict.MET)

    @property
    def partial_count(self) -> int:
        """Count of criteria partially met."""
        return sum(
            1 for m in self.measurements if m.verdict == MeasurementVerdict.PARTIALLY_MET
        )

    @property
    def not_met_count(self) -> int:
        """Count of criteria not met."""
        return sum(
            1 for m in self.measurements if m.verdict == MeasurementVerdict.NOT_MET
        )

    @property
    def required_met_ratio(self) -> float:
        """Ratio of required criteria that are met."""
        required = [m for m in self.measurements if m.criterion.required]
        if not required:
            return 1.0
        met = sum(1 for m in required if m.is_met)
        return met / len(required)


@dataclass
class EvaluationRequest:
    """Request to evaluate task execution compliance."""

    task_spec_ref: UUID
    motion_ref: UUID
    criteria: list[SuccessCriterion]
    execution_result: dict[str, Any]


@dataclass
class EvaluationResponse:
    """Response from compliance evaluation."""

    success: bool
    evaluation: ComplianceEvaluation | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "error": self.error,
        }


@dataclass
class EvidenceCollectionRequest:
    """Request to collect evidence from execution."""

    task_spec_ref: UUID
    execution_outputs: dict[str, Any]
    execution_logs: list[str]
    execution_metrics: dict[str, Any]


@dataclass
class EvidenceCollectionResponse:
    """Response from evidence collection."""

    success: bool
    evidence: list[ExecutionEvidence] = field(default_factory=list)
    error: str | None = None


class ComplianceEvaluatorProtocol(ABC):
    """Abstract protocol for compliance evaluation tools.

    Per Government PRD FR-GOV-14: This provides the measurement infrastructure
    for evaluating whether WHAT was honored and HOW followed approved plan.

    This protocol provides MECHANICAL measurement, not judicial judgment.
    Judgment (verdicts, invalidation, Conclave triggers) is the Prince's role.

    Key methods:
    - evaluate(): Full evaluation of task spec against execution result
    - measure_criterion(): Individual criterion measurement
    - collect_evidence(): Gather evidence from execution
    - generate_finding(): Create formal finding from evaluation

    This protocol explicitly EXCLUDES judicial functions:
    - Issuing verdicts (ComplianceVerdict) - Prince function
    - Invalidating execution - Prince function
    - Triggering Conclave review - Prince function
    """

    @abstractmethod
    async def evaluate(
        self,
        request: EvaluationRequest,
    ) -> EvaluationResponse:
        """Evaluate execution results against task specification.

        Performs mechanical measurement of all criteria against
        collected evidence. Does not pass judgment.

        Args:
            request: Evaluation request with spec and results

        Returns:
            EvaluationResponse with measurements
        """
        ...

    @abstractmethod
    async def measure_criterion(
        self,
        criterion: SuccessCriterion,
        evidence: list[ExecutionEvidence],
    ) -> CriterionMeasurement:
        """Measure a single success criterion against evidence.

        Per Story 10.2: Produces MET, PARTIALLY_MET, NOT_MET, UNMEASURABLE.
        Each verdict includes supporting evidence.

        Args:
            criterion: The criterion to measure
            evidence: Available evidence to evaluate against

        Returns:
            CriterionMeasurement with verdict and evidence refs
        """
        ...

    @abstractmethod
    async def collect_evidence(
        self,
        request: EvidenceCollectionRequest,
    ) -> EvidenceCollectionResponse:
        """Collect evidence from task execution.

        Per Story 10.4: Gathers task outputs, timing data,
        constraint violations, intermediate states.
        Evidence is stored with chain of custody.

        Args:
            request: Collection request with execution data

        Returns:
            EvidenceCollectionResponse with collected evidence
        """
        ...

    @abstractmethod
    async def determine_overall(
        self,
        measurements: list[CriterionMeasurement],
    ) -> OverallCompliance:
        """Determine overall compliance from individual measurements.

        Calculates overall compliance based on:
        - Ratio of criteria met
        - Whether required criteria are satisfied
        - Presence of critical failures

        Args:
            measurements: All criterion measurements

        Returns:
            OverallCompliance assessment
        """
        ...

    @abstractmethod
    async def get_evaluation(
        self,
        evaluation_id: UUID,
    ) -> ComplianceEvaluation | None:
        """Retrieve a stored evaluation by ID.

        Args:
            evaluation_id: The evaluation's UUID

        Returns:
            ComplianceEvaluation if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_evaluations_by_task(
        self,
        task_spec_ref: UUID,
    ) -> list[ComplianceEvaluation]:
        """Get all evaluations for a task specification.

        Args:
            task_spec_ref: The task spec's UUID

        Returns:
            List of evaluations for that task spec
        """
        ...
