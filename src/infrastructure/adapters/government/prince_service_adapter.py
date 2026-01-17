"""Prince Service Adapter (Judicial Branch).

This module implements the PrinceServiceProtocol for compliance evaluation
and judicial enforcement.

Per Government PRD FR-GOV-14: Princes evaluate compliance with intent and plan.
Per Government PRD FR-GOV-15: Princes may invalidate, force reconsideration.
Per Government PRD FR-GOV-16: Princes may NOT introduce motions or define execution.
"""

import re
from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatementType,
)
from src.application.ports.permission_enforcer import (
    GovernanceAction,
    PermissionContext,
    PermissionEnforcerProtocol,
)
from src.application.ports.prince_service import (
    ComplianceFinding,
    ComplianceVerdict,
    ComplianceViolation,
    ConclaveReviewRequest,
    ConclaveReviewResult,
    CriterionResult,
    CriterionVerdict,
    EvaluationRequest,
    EvaluationResult,
    Evidence,
    InvalidationResult,
    PrinceServiceProtocol,
    ReviewSeverity,
    ViolationType,
)

logger = get_logger(__name__)


class PrinceServiceAdapter(PrinceServiceProtocol):
    """Implementation of Prince-rank judicial functions.

    This service evaluates execution results against original intent
    and approved plans, issuing compliance findings and enforcement actions.

    Key capabilities (per FR-GOV-14, FR-GOV-15):
    - Evaluate compliance with WHAT (intent) and HOW (plan)
    - Issue compliance findings
    - Invalidate non-compliant executions
    - Trigger Conclave review

    All findings are witnessed by Knight per FR-GOV-20.
    """

    def __init__(
        self,
        permission_enforcer: PermissionEnforcerProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the Prince Service.

        Args:
            permission_enforcer: Permission enforcement (optional for testing)
            knight_witness: Knight witness for recording events (optional)
            verbose: Enable verbose logging
        """
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness
        self._verbose = verbose

        # In-memory storage
        self._findings: dict[UUID, ComplianceFinding] = {}
        self._invalidations: dict[UUID, InvalidationResult] = {}
        self._reviews: dict[UUID, ConclaveReviewRequest] = {}

        if self._verbose:
            logger.debug("prince_service_initialized")

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
        """
        if self._verbose:
            logger.debug(
                "compliance_evaluation_requested",
                plan_ref=str(request.plan_ref),
                prince_id=request.prince_id,
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource="compliance_finding",
                action_details={"plan_ref": str(request.plan_ref)},
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.prince_id,
                action=GovernanceAction.JUDGE,
                context=context,
            )

            if not permission_result.allowed:
                await self._witness_violation(
                    archon_id=request.prince_id,
                    violation_type="rank_violation",
                    description="Attempted to judge compliance without Prince rank",
                )
                return EvaluationResult(
                    success=False,
                    error=f"Permission denied: {permission_result.violation_reason}",
                )

        # Evaluate intent compliance (WHAT honored)
        intent_results, intent_violations = await self._evaluate_intent_compliance(
            request.original_intent,
            request.execution_result,
        )

        # Evaluate plan compliance (HOW followed)
        plan_violations = await self._evaluate_plan_compliance(
            request.execution_result,
        )

        # Evaluate constraint compliance
        constraint_violations = await self._evaluate_constraint_compliance(
            request.execution_result,
        )

        # Combine all violations
        all_violations = intent_violations + plan_violations + constraint_violations

        # Determine overall verdict
        verdict = self._determine_verdict(intent_results, all_violations)

        # Generate recommendations
        recommendations = self._generate_recommendations(all_violations)

        # Create finding
        finding = ComplianceFinding.create(
            plan_ref=request.plan_ref,
            motion_ref=request.motion_ref,
            verdict=verdict,
            criteria_results=intent_results,
            violations=all_violations,
            recommendations=recommendations,
            evaluated_by=request.prince_id,
            summary=self._generate_summary(verdict, all_violations),
        )

        # Store finding
        self._findings[finding.finding_id] = finding

        # Issue and witness the finding
        await self.issue_finding(finding)

        if self._verbose:
            logger.info(
                "compliance_evaluation_complete",
                finding_id=str(finding.finding_id),
                verdict=verdict.value,
                violation_count=finding.violation_count,
            )

        return EvaluationResult(
            success=True,
            finding=finding,
        )

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
        # Store if not already stored
        if finding.finding_id not in self._findings:
            self._findings[finding.finding_id] = finding

        # Witness the finding
        await self._observe_event(
            event_type="compliance_finding_issued",
            description=f"Prince {finding.evaluated_by} issued compliance finding: {finding.verdict.value}",
            data={
                "finding_id": str(finding.finding_id),
                "plan_ref": str(finding.plan_ref),
                "motion_ref": str(finding.motion_ref),
                "verdict": finding.verdict.value,
                "violation_count": finding.violation_count,
            },
        )

        if self._verbose:
            logger.info(
                "finding_issued",
                finding_id=str(finding.finding_id),
                verdict=finding.verdict.value,
            )

        return True

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
        if self._verbose:
            logger.debug(
                "invalidation_requested",
                plan_ref=str(plan_ref),
                finding_id=str(finding.finding_id),
            )

        # Verify finding supports invalidation
        if finding.verdict == ComplianceVerdict.COMPLIANT:
            return InvalidationResult(
                success=False,
                error="Cannot invalidate compliant execution",
            )

        result = InvalidationResult(
            success=True,
            invalidation_id=plan_ref,
            plan_ref=plan_ref,
            reason=reason,
        )

        # Store invalidation
        self._invalidations[plan_ref] = result

        # Witness the invalidation
        await self._observe_event(
            event_type="execution_invalidated",
            description=f"Prince invalidated execution for plan {plan_ref}",
            data={
                "plan_ref": str(plan_ref),
                "finding_id": str(finding.finding_id),
                "verdict": finding.verdict.value,
                "reason": reason,
            },
        )

        if self._verbose:
            logger.info(
                "execution_invalidated",
                plan_ref=str(plan_ref),
                reason=reason,
            )

        return result

    async def trigger_conclave_review(
        self,
        request: ConclaveReviewRequest,
    ) -> ConclaveReviewResult:
        """Trigger Conclave reconsideration of a motion.

        Per FR-GOV-15: Princes may force reconsideration.

        Args:
            request: Review request with finding and questions

        Returns:
            ConclaveReviewResult with agenda position
        """
        if self._verbose:
            logger.debug(
                "conclave_review_triggered",
                motion_ref=str(request.motion_ref),
                severity=request.severity.value,
            )

        # Store review request
        review_id = request.finding.finding_id
        self._reviews[review_id] = request

        # Determine agenda position based on severity
        agenda_position = 1 if request.severity == ReviewSeverity.CRITICAL else 2

        # Witness the review trigger
        await self._observe_event(
            event_type="conclave_review_triggered",
            description=f"Prince triggered Conclave review for motion {request.motion_ref}",
            data={
                "motion_ref": str(request.motion_ref),
                "finding_id": str(request.finding.finding_id),
                "severity": request.severity.value,
                "questions": request.questions,
                "agenda_position": agenda_position,
            },
        )

        if self._verbose:
            logger.info(
                "conclave_review_scheduled",
                motion_ref=str(request.motion_ref),
                agenda_position=agenda_position,
            )

        return ConclaveReviewResult(
            success=True,
            review_id=review_id,
            agenda_position=agenda_position,
        )

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
        if not evidence:
            return CriterionResult(
                criterion_id=criterion_id,
                criterion_description=criterion_description,
                verdict=CriterionVerdict.UNMEASURABLE,
                notes="No evidence provided for evaluation",
            )

        # Simple evaluation logic - check if evidence supports criterion
        # Production would use more sophisticated analysis
        evidence_text = " ".join(
            e.description.lower() + " " + str(e.data).lower()
            for e in evidence
        )

        # Extract key words from criterion
        criterion_words = set(
            word.lower()
            for word in re.findall(r"\b\w{4,}\b", criterion_description)
        )

        # Check overlap
        matches = sum(1 for word in criterion_words if word in evidence_text)
        match_ratio = matches / len(criterion_words) if criterion_words else 0

        if match_ratio >= 0.7:
            verdict = CriterionVerdict.MET
        elif match_ratio >= 0.4:
            verdict = CriterionVerdict.PARTIALLY_MET
        else:
            verdict = CriterionVerdict.NOT_MET

        return CriterionResult(
            criterion_id=criterion_id,
            criterion_description=criterion_description,
            verdict=verdict,
            evidence=tuple(evidence),
            notes=f"Evidence match ratio: {match_ratio:.2f}",
        )

    async def get_finding(self, finding_id: UUID) -> ComplianceFinding | None:
        """Retrieve a compliance finding by ID."""
        return self._findings.get(finding_id)

    async def get_findings_by_motion(
        self,
        motion_ref: UUID,
    ) -> list[ComplianceFinding]:
        """Get all findings for a specific motion."""
        return [f for f in self._findings.values() if f.motion_ref == motion_ref]

    async def get_findings_by_plan(
        self,
        plan_ref: UUID,
    ) -> list[ComplianceFinding]:
        """Get all findings for a specific execution plan."""
        return [f for f in self._findings.values() if f.plan_ref == plan_ref]

    # =========================================================================
    # INTERNAL EVALUATION METHODS
    # =========================================================================

    async def _evaluate_intent_compliance(
        self,
        original_intent: str,
        execution_result: dict[str, Any],
    ) -> tuple[list[CriterionResult], list[ComplianceViolation]]:
        """Evaluate if WHAT was honored.

        Args:
            original_intent: The motion's original intent
            execution_result: Results from execution

        Returns:
            Tuple of criterion results and violations
        """
        results: list[CriterionResult] = []
        violations: list[ComplianceViolation] = []

        # Extract success criteria from execution result
        criteria = execution_result.get("criteria", [])
        evidence_list = execution_result.get("evidence", [])

        # Convert evidence to Evidence objects
        evidence_objects = [
            Evidence.create(
                description=str(e.get("description", "")),
                source=str(e.get("source", "execution_result")),
                data=e,
            )
            for e in evidence_list
        ]

        for criterion in criteria:
            result = await self.measure_criterion(
                criterion_id=str(criterion.get("id", "unknown")),
                criterion_description=str(criterion.get("description", "")),
                evidence=evidence_objects,
            )
            results.append(result)

            if result.verdict == CriterionVerdict.NOT_MET:
                violation = ComplianceViolation.create(
                    violation_type=ViolationType.INTENT_DEVIATION,
                    description=f"Criterion not met: {criterion.get('description', '')}",
                    severity=ReviewSeverity.HIGH,
                    evidence=evidence_objects,
                )
                violations.append(violation)

        # Check intent keywords present in results
        if not criteria:
            # No criteria provided - check for general intent match
            intent_words = set(
                word.lower()
                for word in re.findall(r"\b\w{4,}\b", original_intent)
            )

            summary = execution_result.get("summary", "")
            summary_words = set(
                word.lower()
                for word in re.findall(r"\b\w{4,}\b", summary)
            )

            overlap = len(intent_words & summary_words) / len(intent_words) if intent_words else 0

            result = CriterionResult(
                criterion_id="intent_match",
                criterion_description=f"Intent: {original_intent[:50]}...",
                verdict=(
                    CriterionVerdict.MET if overlap >= 0.5
                    else CriterionVerdict.PARTIALLY_MET if overlap >= 0.25
                    else CriterionVerdict.NOT_MET
                ),
                notes=f"Intent keyword overlap: {overlap:.2f}",
            )
            results.append(result)

            if result.verdict == CriterionVerdict.NOT_MET:
                violation = ComplianceViolation.create(
                    violation_type=ViolationType.INTENT_DEVIATION,
                    description="Execution results do not align with original intent",
                    severity=ReviewSeverity.CRITICAL,
                )
                violations.append(violation)

        return results, violations

    async def _evaluate_plan_compliance(
        self,
        execution_result: dict[str, Any],
    ) -> list[ComplianceViolation]:
        """Evaluate if HOW followed approved plan.

        Args:
            execution_result: Results from execution

        Returns:
            List of plan deviation violations
        """
        violations: list[ComplianceViolation] = []

        # Check for plan deviations
        deviations = execution_result.get("deviations", [])

        for deviation in deviations:
            violation = ComplianceViolation.create(
                violation_type=ViolationType.PLAN_DEVIATION,
                description=str(deviation.get("description", "Unknown deviation")),
                severity=ReviewSeverity.MEDIUM,
                remediation=deviation.get("remediation"),
            )
            violations.append(violation)

        # Check for unauthorized actions
        unauthorized = execution_result.get("unauthorized_actions", [])

        for action in unauthorized:
            violation = ComplianceViolation.create(
                violation_type=ViolationType.UNAUTHORIZED_ACTION,
                description=f"Unauthorized action: {action}",
                severity=ReviewSeverity.HIGH,
            )
            violations.append(violation)

        return violations

    async def _evaluate_constraint_compliance(
        self,
        execution_result: dict[str, Any],
    ) -> list[ComplianceViolation]:
        """Evaluate if constraints were respected.

        Args:
            execution_result: Results from execution

        Returns:
            List of constraint violations
        """
        violations: list[ComplianceViolation] = []

        # Check for constraint violations
        constraint_violations = execution_result.get("constraint_violations", [])

        for cv in constraint_violations:
            violation = ComplianceViolation.create(
                violation_type=ViolationType.CONSTRAINT_VIOLATION,
                description=str(cv.get("description", "Constraint violated")),
                severity=ReviewSeverity.HIGH,
                remediation=cv.get("remediation"),
            )
            violations.append(violation)

        # Check for incomplete execution
        if not execution_result.get("complete", True):
            violation = ComplianceViolation.create(
                violation_type=ViolationType.INCOMPLETE_EXECUTION,
                description="Execution did not complete all required outputs",
                severity=ReviewSeverity.MEDIUM,
            )
            violations.append(violation)

        return violations

    def _determine_verdict(
        self,
        criteria_results: list[CriterionResult],
        violations: list[ComplianceViolation],
    ) -> ComplianceVerdict:
        """Determine overall compliance verdict.

        Args:
            criteria_results: Results of criterion evaluations
            violations: All violations found

        Returns:
            Overall ComplianceVerdict
        """
        # Check for critical violations
        if any(v.severity == ReviewSeverity.CRITICAL for v in violations):
            return ComplianceVerdict.INVALID

        # Count criteria results
        met_count = sum(1 for r in criteria_results if r.verdict == CriterionVerdict.MET)
        partial_count = sum(
            1 for r in criteria_results if r.verdict == CriterionVerdict.PARTIALLY_MET
        )
        total = len(criteria_results)

        # Calculate effective score (partial met counts as 0.5)
        effective_score = met_count + (partial_count * 0.5)

        # No violations and all criteria fully met = COMPLIANT
        if not violations and total > 0 and met_count == total:
            return ComplianceVerdict.COMPLIANT

        # No violations and mostly met (including partial) = PARTIALLY_COMPLIANT
        if not violations and total > 0 and effective_score >= total * 0.5:
            return ComplianceVerdict.PARTIALLY_COMPLIANT

        # With violations but still mostly met = PARTIALLY_COMPLIANT
        if effective_score >= total * 0.5:
            return ComplianceVerdict.PARTIALLY_COMPLIANT

        return ComplianceVerdict.NON_COMPLIANT

    def _generate_recommendations(
        self,
        violations: list[ComplianceViolation],
    ) -> list[str]:
        """Generate recommendations based on violations.

        Args:
            violations: Violations found during evaluation

        Returns:
            List of recommendations
        """
        recommendations: list[str] = []

        for violation in violations:
            if violation.remediation:
                recommendations.append(violation.remediation)
            else:
                # Generate default recommendations
                if violation.violation_type == ViolationType.INTENT_DEVIATION:
                    recommendations.append(
                        "Review execution approach to ensure alignment with original intent"
                    )
                elif violation.violation_type == ViolationType.PLAN_DEVIATION:
                    recommendations.append(
                        "Future executions should follow approved plan more closely"
                    )
                elif violation.violation_type == ViolationType.CONSTRAINT_VIOLATION:
                    recommendations.append(
                        "Implement better constraint checking during execution"
                    )

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)

        return unique_recommendations

    def _generate_summary(
        self,
        verdict: ComplianceVerdict,
        violations: list[ComplianceViolation],
    ) -> str:
        """Generate a summary of the compliance finding.

        Args:
            verdict: The overall verdict
            violations: Violations found

        Returns:
            Summary string
        """
        if verdict == ComplianceVerdict.COMPLIANT:
            return "Execution fully complies with original intent and approved plan."

        if verdict == ComplianceVerdict.PARTIALLY_COMPLIANT:
            return (
                f"Execution partially complies with {len(violations)} minor violation(s). "
                "Review recommendations for improvement."
            )

        if verdict == ComplianceVerdict.NON_COMPLIANT:
            return (
                f"Execution does not comply with original intent or plan. "
                f"{len(violations)} violation(s) found requiring remediation."
            )

        return (
            f"Execution invalidated due to critical violation(s). "
            f"{len(violations)} total violation(s) found."
        )

    # =========================================================================
    # INTERNAL WITNESS METHODS
    # =========================================================================

    async def _witness_violation(
        self,
        archon_id: str,
        violation_type: str,
        description: str,
        evidence: dict | None = None,
    ) -> None:
        """Record a violation via Knight Witness."""
        if not self._knight_witness:
            return

        record = ViolationRecord(
            statement_type=WitnessStatementType.ROLE_VIOLATION,
            description=description,
            roles_involved=(archon_id,),
            evidence=evidence or {},
            prd_reference="FR-GOV-16",
        )

        await self._knight_witness.record_violation(record)

    async def _observe_event(
        self,
        event_type: str,
        description: str,
        data: dict | None = None,
    ) -> None:
        """Record an event via Knight Witness."""
        if not self._knight_witness:
            return

        context = ObservationContext(
            event_type=event_type,
            source_service="prince_service",
            data=data or {},
        )

        await self._knight_witness.observe(description, context)


def create_prince_service(
    permission_enforcer: PermissionEnforcerProtocol | None = None,
    knight_witness: KnightWitnessProtocol | None = None,
    verbose: bool = False,
) -> PrinceServiceAdapter:
    """Factory function to create a PrinceServiceAdapter.

    Args:
        permission_enforcer: Permission enforcement
        knight_witness: Knight witness service
        verbose: Enable verbose logging

    Returns:
        Configured PrinceServiceAdapter
    """
    return PrinceServiceAdapter(
        permission_enforcer=permission_enforcer,
        knight_witness=knight_witness,
        verbose=verbose,
    )
