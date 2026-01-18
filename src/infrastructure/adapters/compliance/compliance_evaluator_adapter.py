"""Compliance Evaluator Adapter.

This module implements the ComplianceEvaluatorProtocol for mechanical
measurement of task execution against success criteria.

Per Government PRD FR-GOV-14: Provides measurement tools for compliance
evaluation. This adapter handles the mechanical measurement aspects,
while judicial judgment remains with the Prince Service.
"""

import re
from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.compliance_evaluator import (
    ComplianceEvaluation,
    ComplianceEvaluatorProtocol,
    CriterionMeasurement,
    EvaluationRequest,
    EvaluationResponse,
    EvidenceCollectionRequest,
    EvidenceCollectionResponse,
    ExecutionEvidence,
    MeasurementVerdict,
    OverallCompliance,
    SuccessCriterion,
)

logger = get_logger(__name__)


class ComplianceEvaluatorAdapter(ComplianceEvaluatorProtocol):
    """Implementation of compliance evaluation tools.

    This service provides mechanical measurement of execution results
    against success criteria from task specifications.

    Key capabilities (per Stories 10.2-10.4):
    - Measure individual criteria against evidence
    - Collect evidence from execution outputs
    - Determine overall compliance assessment

    All measurement is objective and mechanical.
    Judicial judgment (verdicts, invalidation) is NOT performed here.
    """

    def __init__(
        self,
        verbose: bool = False,
    ) -> None:
        """Initialize the Compliance Evaluator.

        Args:
            verbose: Enable verbose logging
        """
        self._verbose = verbose

        # In-memory storage
        self._evaluations: dict[UUID, ComplianceEvaluation] = {}
        self._evidence_store: dict[UUID, ExecutionEvidence] = {}

        if self._verbose:
            logger.debug("compliance_evaluator_initialized")

    async def evaluate(
        self,
        request: EvaluationRequest,
    ) -> EvaluationResponse:
        """Evaluate execution results against task specification.

        Args:
            request: Evaluation request with spec and results

        Returns:
            EvaluationResponse with measurements
        """
        if self._verbose:
            logger.debug(
                "evaluation_requested",
                task_spec_ref=str(request.task_spec_ref),
            )

        # Collect evidence from execution result
        evidence_request = EvidenceCollectionRequest(
            task_spec_ref=request.task_spec_ref,
            execution_outputs=request.execution_result.get("outputs", {}),
            execution_logs=request.execution_result.get("logs", []),
            execution_metrics=request.execution_result.get("metrics", {}),
        )

        evidence_response = await self.collect_evidence(evidence_request)

        if not evidence_response.success:
            return EvaluationResponse(
                success=False,
                error=f"Evidence collection failed: {evidence_response.error}",
            )

        # Add evidence from execution result directly
        direct_evidence = self._extract_direct_evidence(request.execution_result)
        all_evidence = evidence_response.evidence + direct_evidence

        # Store all evidence
        for e in all_evidence:
            self._evidence_store[e.evidence_id] = e

        # Measure each criterion
        measurements: list[CriterionMeasurement] = []

        for criterion in request.criteria:
            measurement = await self.measure_criterion(criterion, all_evidence)
            measurements.append(measurement)

        # Determine overall compliance
        overall = await self.determine_overall(measurements)

        # Generate summary
        summary = self._generate_summary(measurements, overall)

        # Create evaluation
        evaluation = ComplianceEvaluation.create(
            task_spec_ref=request.task_spec_ref,
            motion_ref=request.motion_ref,
            measurements=measurements,
            evidence_collected=all_evidence,
            overall=overall,
            summary=summary,
        )

        # Store evaluation
        self._evaluations[evaluation.evaluation_id] = evaluation

        if self._verbose:
            logger.info(
                "evaluation_complete",
                evaluation_id=str(evaluation.evaluation_id),
                overall=overall.value,
                met_count=evaluation.met_count,
                partial_count=evaluation.partial_count,
                not_met_count=evaluation.not_met_count,
            )

        return EvaluationResponse(
            success=True,
            evaluation=evaluation,
        )

    async def measure_criterion(
        self,
        criterion: SuccessCriterion,
        evidence: list[ExecutionEvidence],
    ) -> CriterionMeasurement:
        """Measure a single success criterion against evidence.

        Per Story 10.2: Produces MET, PARTIALLY_MET, NOT_MET, UNMEASURABLE.

        Args:
            criterion: The criterion to measure
            evidence: Available evidence to evaluate against

        Returns:
            CriterionMeasurement with verdict and evidence refs
        """
        if not evidence:
            return CriterionMeasurement(
                criterion=criterion,
                verdict=MeasurementVerdict.UNMEASURABLE,
                evidence_refs=(),
                notes="No evidence available for measurement",
            )

        # Extract searchable text from all evidence
        evidence_text = " ".join(
            f"{e.description.lower()} {str(e.data).lower()}" for e in evidence
        )

        # Extract key words from criterion
        criterion_text = f"{criterion.description} {criterion.measurement_method}"
        criterion_words = set(
            word.lower() for word in re.findall(r"\b\w{4,}\b", criterion_text)
        )

        # Calculate match ratio
        if not criterion_words:
            return CriterionMeasurement(
                criterion=criterion,
                verdict=MeasurementVerdict.UNMEASURABLE,
                evidence_refs=tuple(e.evidence_id for e in evidence),
                notes="Criterion has no measurable keywords",
            )

        matches = sum(1 for word in criterion_words if word in evidence_text)
        match_ratio = matches / len(criterion_words)

        # Find supporting evidence
        supporting_refs = self._find_supporting_evidence(criterion, evidence)

        # Determine verdict based on match ratio
        if match_ratio >= 0.7:
            verdict = MeasurementVerdict.MET
        elif match_ratio >= 0.4:
            verdict = MeasurementVerdict.PARTIALLY_MET
        else:
            verdict = MeasurementVerdict.NOT_MET

        # Check for explicit threshold if provided
        measured_value = None
        if criterion.threshold:
            measured_value = self._measure_against_threshold(
                criterion.threshold,
                evidence,
            )
            if measured_value:
                # Adjust verdict based on threshold
                verdict = self._apply_threshold_verdict(
                    criterion.threshold,
                    measured_value,
                    verdict,
                )

        return CriterionMeasurement(
            criterion=criterion,
            verdict=verdict,
            evidence_refs=supporting_refs,
            measured_value=measured_value,
            notes=f"Evidence match ratio: {match_ratio:.2f}",
        )

    async def collect_evidence(
        self,
        request: EvidenceCollectionRequest,
    ) -> EvidenceCollectionResponse:
        """Collect evidence from task execution.

        Per Story 10.4: Gathers task outputs, timing data,
        constraint violations, intermediate states.

        Args:
            request: Collection request with execution data

        Returns:
            EvidenceCollectionResponse with collected evidence
        """
        evidence: list[ExecutionEvidence] = []

        # Collect from outputs
        if request.execution_outputs:
            for key, value in request.execution_outputs.items():
                e = ExecutionEvidence.create(
                    description=f"Execution output: {key}",
                    source="execution_outputs",
                    evidence_type="output",
                    data={key: value},
                    collector="compliance_evaluator",
                )
                evidence.append(e)

        # Collect from logs
        if request.execution_logs:
            e = ExecutionEvidence.create(
                description=f"Execution logs ({len(request.execution_logs)} entries)",
                source="execution_logs",
                evidence_type="logs",
                data={"logs": request.execution_logs},
                collector="compliance_evaluator",
            )
            evidence.append(e)

        # Collect from metrics
        if request.execution_metrics:
            e = ExecutionEvidence.create(
                description="Execution metrics",
                source="execution_metrics",
                evidence_type="metrics",
                data=request.execution_metrics,
                collector="compliance_evaluator",
            )
            evidence.append(e)

        if self._verbose:
            logger.debug(
                "evidence_collected",
                task_spec_ref=str(request.task_spec_ref),
                evidence_count=len(evidence),
            )

        return EvidenceCollectionResponse(
            success=True,
            evidence=evidence,
        )

    async def determine_overall(
        self,
        measurements: list[CriterionMeasurement],
    ) -> OverallCompliance:
        """Determine overall compliance from individual measurements.

        Args:
            measurements: All criterion measurements

        Returns:
            OverallCompliance assessment
        """
        if not measurements:
            return OverallCompliance.FAILED

        met_count = sum(1 for m in measurements if m.verdict == MeasurementVerdict.MET)
        partial_count = sum(
            1 for m in measurements if m.verdict == MeasurementVerdict.PARTIALLY_MET
        )
        total = len(measurements)

        # Check required criteria
        required = [m for m in measurements if m.criterion.required]
        required_failed = [
            m for m in required if m.verdict == MeasurementVerdict.NOT_MET
        ]

        # If any required criterion failed, overall is FAILED
        if required_failed:
            return OverallCompliance.FAILED

        # Calculate effective score (partial met counts as 0.5)
        effective_score = met_count + (partial_count * 0.5)
        score_ratio = effective_score / total if total > 0 else 0

        if met_count == total:
            return OverallCompliance.FULL
        elif score_ratio >= 0.7:
            return OverallCompliance.PARTIAL
        elif score_ratio >= 0.4:
            return OverallCompliance.INSUFFICIENT
        else:
            return OverallCompliance.FAILED

    async def get_evaluation(
        self,
        evaluation_id: UUID,
    ) -> ComplianceEvaluation | None:
        """Retrieve a stored evaluation by ID."""
        return self._evaluations.get(evaluation_id)

    async def get_evaluations_by_task(
        self,
        task_spec_ref: UUID,
    ) -> list[ComplianceEvaluation]:
        """Get all evaluations for a task specification."""
        return [
            e for e in self._evaluations.values() if e.task_spec_ref == task_spec_ref
        ]

    # =========================================================================
    # INTERNAL HELPER METHODS
    # =========================================================================

    def _extract_direct_evidence(
        self,
        execution_result: dict[str, Any],
    ) -> list[ExecutionEvidence]:
        """Extract evidence directly from execution result structure."""
        evidence: list[ExecutionEvidence] = []

        # Extract from summary
        if summary := execution_result.get("summary"):
            e = ExecutionEvidence.create(
                description=f"Execution summary: {summary[:100]}...",
                source="execution_result",
                evidence_type="summary",
                data={"summary": summary},
                collector="compliance_evaluator",
            )
            evidence.append(e)

        # Extract from criteria results
        if criteria := execution_result.get("criteria"):
            for criterion in criteria:
                e = ExecutionEvidence.create(
                    description=f"Criterion result: {criterion.get('description', '')}",
                    source="execution_result.criteria",
                    evidence_type="criterion_result",
                    data=criterion,
                    collector="compliance_evaluator",
                )
                evidence.append(e)

        # Extract from explicit evidence
        if ev_list := execution_result.get("evidence"):
            for ev in ev_list:
                e = ExecutionEvidence.create(
                    description=str(ev.get("description", "Provided evidence")),
                    source=str(ev.get("source", "execution_result.evidence")),
                    evidence_type="provided",
                    data=ev,
                    collector="compliance_evaluator",
                )
                evidence.append(e)

        # Extract deviations as evidence
        if deviations := execution_result.get("deviations"):
            e = ExecutionEvidence.create(
                description=f"Deviations detected: {len(deviations)} deviation(s)",
                source="execution_result.deviations",
                evidence_type="deviation",
                data={"deviations": deviations},
                collector="compliance_evaluator",
            )
            evidence.append(e)

        # Extract constraint violations as evidence
        if violations := execution_result.get("constraint_violations"):
            e = ExecutionEvidence.create(
                description=f"Constraint violations: {len(violations)} violation(s)",
                source="execution_result.constraint_violations",
                evidence_type="violation",
                data={"constraint_violations": violations},
                collector="compliance_evaluator",
            )
            evidence.append(e)

        return evidence

    def _find_supporting_evidence(
        self,
        criterion: SuccessCriterion,
        evidence: list[ExecutionEvidence],
    ) -> tuple[UUID, ...]:
        """Find evidence that supports a criterion measurement."""
        criterion_text = criterion.description.lower()
        supporting: list[UUID] = []

        for e in evidence:
            evidence_text = f"{e.description.lower()} {str(e.data).lower()}"

            # Check for keyword overlap
            criterion_words = set(re.findall(r"\b\w{4,}\b", criterion_text))
            if any(word in evidence_text for word in criterion_words):
                supporting.append(e.evidence_id)

        return (
            tuple(supporting)
            if supporting
            else tuple(e.evidence_id for e in evidence[:3])
        )

    def _measure_against_threshold(
        self,
        threshold: str,
        evidence: list[ExecutionEvidence],
    ) -> str | None:
        """Extract measured value for threshold comparison."""
        # Look for numeric values in evidence
        for e in evidence:
            if e.evidence_type == "metrics":
                # Return first numeric metric as measured value
                for key, value in e.data.items():
                    if isinstance(value, (int, float)):
                        return f"{key}: {value}"
        return None

    def _apply_threshold_verdict(
        self,
        threshold: str,
        measured_value: str,
        current_verdict: MeasurementVerdict,
    ) -> MeasurementVerdict:
        """Adjust verdict based on threshold comparison."""
        # Simple threshold logic - production would parse threshold properly
        try:
            # Extract numeric value from measured_value
            match = re.search(r":\s*([\d.]+)", measured_value)
            if match:
                value = float(match.group(1))

                # Parse threshold (e.g., ">90", "<10", ">=99.9")
                threshold_match = re.match(r"([<>=]+)\s*([\d.]+)", threshold)
                if threshold_match:
                    op = threshold_match.group(1)
                    target = float(threshold_match.group(2))

                    if (
                        op == ">"
                        and value > target
                        or op == ">="
                        and value >= target
                        or op == "<"
                        and value < target
                        or op == "<="
                        and value <= target
                        or op == "="
                        and abs(value - target) < 0.001
                    ):
                        return MeasurementVerdict.MET
                    else:
                        return MeasurementVerdict.NOT_MET

        except (ValueError, AttributeError):
            pass

        return current_verdict

    def _generate_summary(
        self,
        measurements: list[CriterionMeasurement],
        overall: OverallCompliance,
    ) -> str:
        """Generate a summary of the evaluation."""
        met = sum(1 for m in measurements if m.verdict == MeasurementVerdict.MET)
        partial = sum(
            1 for m in measurements if m.verdict == MeasurementVerdict.PARTIALLY_MET
        )
        not_met = sum(
            1 for m in measurements if m.verdict == MeasurementVerdict.NOT_MET
        )
        total = len(measurements)

        if overall == OverallCompliance.FULL:
            return f"All {total} criteria fully met."
        elif overall == OverallCompliance.PARTIAL:
            return (
                f"Partial compliance: {met} met, {partial} partially met, "
                f"{not_met} not met out of {total} total criteria."
            )
        elif overall == OverallCompliance.INSUFFICIENT:
            return (
                f"Insufficient compliance: {met} met, {partial} partially met, "
                f"{not_met} not met out of {total} total criteria."
            )
        else:
            return (
                f"Compliance failed: Only {met + partial} of {total} criteria "
                f"satisfied (including partial)."
            )


def create_compliance_evaluator(
    verbose: bool = False,
) -> ComplianceEvaluatorAdapter:
    """Factory function to create a ComplianceEvaluatorAdapter.

    Args:
        verbose: Enable verbose logging

    Returns:
        Configured ComplianceEvaluatorAdapter
    """
    return ComplianceEvaluatorAdapter(verbose=verbose)
