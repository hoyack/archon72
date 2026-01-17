"""Unit tests for PrinceServiceAdapter.

Tests the Prince Service judicial functions per Government PRD FR-GOV-14/FR-GOV-15/FR-GOV-16.
"""

import pytest
from uuid import uuid4

from src.application.ports.prince_service import (
    ComplianceVerdict,
    ConclaveReviewRequest,
    CriterionVerdict,
    EvaluationRequest,
    Evidence,
    ReviewSeverity,
    ViolationType,
)
from src.infrastructure.adapters.government.prince_service_adapter import (
    PrinceServiceAdapter,
    create_prince_service,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def prince_service() -> PrinceServiceAdapter:
    """Create a Prince Service for testing."""
    return PrinceServiceAdapter(verbose=True)


@pytest.fixture
def compliant_execution_result() -> dict:
    """Create a compliant execution result."""
    return {
        "summary": "Successfully improved system reliability with monitoring and alerting",
        "complete": True,
        "criteria": [
            {
                "id": "c1",
                "description": "System uptime improved",
            },
            {
                "id": "c2",
                "description": "Monitoring implemented",
            },
        ],
        "evidence": [
            {
                "description": "System uptime improved to 99.9%",
                "source": "metrics_dashboard",
            },
            {
                "description": "Monitoring and alerting system deployed",
                "source": "deployment_log",
            },
        ],
        "deviations": [],
        "unauthorized_actions": [],
        "constraint_violations": [],
    }


@pytest.fixture
def non_compliant_execution_result() -> dict:
    """Create a non-compliant execution result."""
    return {
        "summary": "Performance optimization completed but scope exceeded",
        "complete": False,
        "criteria": [
            {
                "id": "c1",
                "description": "Response time reduced",
            },
        ],
        "evidence": [],
        "deviations": [
            {
                "description": "Modified database schema without approval",
                "remediation": "Revert schema changes and get approval",
            },
        ],
        "unauthorized_actions": [
            "Database schema modification",
        ],
        "constraint_violations": [
            {
                "description": "Exceeded time limit by 50%",
            },
        ],
    }


# =============================================================================
# TEST ADAPTER INITIALIZATION
# =============================================================================


class TestAdapterInit:
    """Test adapter initialization."""

    def test_create_adapter(self) -> None:
        """Test basic adapter creation."""
        adapter = PrinceServiceAdapter()
        assert adapter is not None

    def test_factory_function(self) -> None:
        """Test factory function."""
        adapter = create_prince_service(verbose=True)
        assert isinstance(adapter, PrinceServiceAdapter)


# =============================================================================
# TEST COMPLIANCE EVALUATION - COMPLIANT
# =============================================================================


class TestComplianceEvaluationCompliant:
    """Test compliance evaluation with compliant results."""

    @pytest.mark.asyncio
    async def test_evaluate_compliant_execution(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test evaluating a compliant execution."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Improve system reliability through monitoring and alerting",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",  # Prince rank
        )

        result = await prince_service.evaluate_compliance(request)

        assert result.success is True
        assert result.finding is not None
        # Should be at least partially compliant given matching criteria
        assert result.finding.verdict in [
            ComplianceVerdict.COMPLIANT,
            ComplianceVerdict.PARTIALLY_COMPLIANT,
        ]

    @pytest.mark.asyncio
    async def test_finding_stored(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test that finding is stored after evaluation."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Improve system reliability",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",
        )

        result = await prince_service.evaluate_compliance(request)

        finding = await prince_service.get_finding(result.finding.finding_id)
        assert finding is not None
        assert finding.finding_id == result.finding.finding_id


# =============================================================================
# TEST COMPLIANCE EVALUATION - NON-COMPLIANT
# =============================================================================


class TestComplianceEvaluationNonCompliant:
    """Test compliance evaluation with non-compliant results."""

    @pytest.mark.asyncio
    async def test_evaluate_non_compliant_execution(
        self,
        prince_service: PrinceServiceAdapter,
        non_compliant_execution_result: dict,
    ) -> None:
        """Test evaluating a non-compliant execution."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Reduce response time without schema changes",
            execution_result=non_compliant_execution_result,
            prince_id="archon-sitri-001",
        )

        result = await prince_service.evaluate_compliance(request)

        assert result.success is True
        assert result.finding is not None
        assert result.finding.verdict == ComplianceVerdict.NON_COMPLIANT

    @pytest.mark.asyncio
    async def test_violations_detected(
        self,
        prince_service: PrinceServiceAdapter,
        non_compliant_execution_result: dict,
    ) -> None:
        """Test that violations are detected and recorded."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Reduce response time",
            execution_result=non_compliant_execution_result,
            prince_id="archon-sitri-001",
        )

        result = await prince_service.evaluate_compliance(request)

        assert result.finding.violation_count > 0
        # Should detect plan deviation, unauthorized action, constraint violation
        violation_types = {v.violation_type for v in result.finding.violations}
        assert ViolationType.PLAN_DEVIATION in violation_types
        assert ViolationType.UNAUTHORIZED_ACTION in violation_types
        assert ViolationType.CONSTRAINT_VIOLATION in violation_types

    @pytest.mark.asyncio
    async def test_recommendations_generated(
        self,
        prince_service: PrinceServiceAdapter,
        non_compliant_execution_result: dict,
    ) -> None:
        """Test that recommendations are generated for violations."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Reduce response time",
            execution_result=non_compliant_execution_result,
            prince_id="archon-sitri-001",
        )

        result = await prince_service.evaluate_compliance(request)

        assert len(result.finding.recommendations) > 0


# =============================================================================
# TEST CRITERION MEASUREMENT
# =============================================================================


class TestCriterionMeasurement:
    """Test individual criterion measurement."""

    @pytest.mark.asyncio
    async def test_measure_criterion_met(
        self,
        prince_service: PrinceServiceAdapter,
    ) -> None:
        """Test measuring a criterion that is met."""
        evidence = [
            Evidence.create(
                description="System response time reduced to 50ms",
                source="performance_test",
                data={"response_time_ms": 50},
            ),
        ]

        result = await prince_service.measure_criterion(
            criterion_id="c1",
            criterion_description="Response time should be reduced",
            evidence=evidence,
        )

        # Evidence matches criterion description
        assert result.verdict in [CriterionVerdict.MET, CriterionVerdict.PARTIALLY_MET]

    @pytest.mark.asyncio
    async def test_measure_criterion_no_evidence(
        self,
        prince_service: PrinceServiceAdapter,
    ) -> None:
        """Test measuring a criterion with no evidence."""
        result = await prince_service.measure_criterion(
            criterion_id="c1",
            criterion_description="Performance improved",
            evidence=[],
        )

        assert result.verdict == CriterionVerdict.UNMEASURABLE


# =============================================================================
# TEST INVALIDATION (Story 5.3)
# =============================================================================


class TestInvalidation:
    """Test execution invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_non_compliant(
        self,
        prince_service: PrinceServiceAdapter,
        non_compliant_execution_result: dict,
    ) -> None:
        """Test invalidating a non-compliant execution."""
        plan_ref = uuid4()

        # First evaluate
        request = EvaluationRequest(
            plan_ref=plan_ref,
            motion_ref=uuid4(),
            original_intent="Reduce response time",
            execution_result=non_compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        eval_result = await prince_service.evaluate_compliance(request)

        # Then invalidate
        invalidation = await prince_service.invalidate_execution(
            plan_ref=plan_ref,
            finding=eval_result.finding,
            reason="Multiple unauthorized actions and constraint violations",
        )

        assert invalidation.success is True
        assert invalidation.plan_ref == plan_ref

    @pytest.mark.asyncio
    async def test_cannot_invalidate_compliant(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test that compliant executions cannot be invalidated."""
        plan_ref = uuid4()

        # Evaluate (should be compliant or partially compliant)
        request = EvaluationRequest(
            plan_ref=plan_ref,
            motion_ref=uuid4(),
            original_intent="Improve system reliability through monitoring and alerting",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        eval_result = await prince_service.evaluate_compliance(request)

        # If compliant, should fail to invalidate
        if eval_result.finding.verdict == ComplianceVerdict.COMPLIANT:
            invalidation = await prince_service.invalidate_execution(
                plan_ref=plan_ref,
                finding=eval_result.finding,
                reason="No valid reason",
            )
            assert invalidation.success is False
            assert "compliant" in invalidation.error.lower()


# =============================================================================
# TEST CONCLAVE REVIEW TRIGGER (Story 5.4)
# =============================================================================


class TestConclaveReviewTrigger:
    """Test Conclave review triggering."""

    @pytest.mark.asyncio
    async def test_trigger_review(
        self,
        prince_service: PrinceServiceAdapter,
        non_compliant_execution_result: dict,
    ) -> None:
        """Test triggering Conclave review."""
        motion_ref = uuid4()

        # Evaluate
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=motion_ref,
            original_intent="Reduce response time",
            execution_result=non_compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        eval_result = await prince_service.evaluate_compliance(request)

        # Trigger review
        review_request = ConclaveReviewRequest(
            motion_ref=motion_ref,
            finding=eval_result.finding,
            severity=ReviewSeverity.HIGH,
            questions=[
                "Should the original intent be revised?",
                "Are the constraints too restrictive?",
            ],
        )

        result = await prince_service.trigger_conclave_review(review_request)

        assert result.success is True
        assert result.review_id is not None
        assert result.agenda_position is not None

    @pytest.mark.asyncio
    async def test_critical_severity_prioritized(
        self,
        prince_service: PrinceServiceAdapter,
        non_compliant_execution_result: dict,
    ) -> None:
        """Test that critical severity reviews are prioritized."""
        motion_ref = uuid4()

        # Evaluate
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=motion_ref,
            original_intent="Reduce response time",
            execution_result=non_compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        eval_result = await prince_service.evaluate_compliance(request)

        # Trigger critical review
        review_request = ConclaveReviewRequest(
            motion_ref=motion_ref,
            finding=eval_result.finding,
            severity=ReviewSeverity.CRITICAL,
            questions=["Urgent: Why did execution deviate?"],
        )

        result = await prince_service.trigger_conclave_review(review_request)

        assert result.agenda_position == 1  # First position for critical


# =============================================================================
# TEST FINDING RETRIEVAL
# =============================================================================


class TestFindingRetrieval:
    """Test finding retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_finding_exists(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test retrieving an existing finding."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Improve reliability",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        result = await prince_service.evaluate_compliance(request)

        finding = await prince_service.get_finding(result.finding.finding_id)
        assert finding is not None

    @pytest.mark.asyncio
    async def test_get_finding_not_exists(
        self,
        prince_service: PrinceServiceAdapter,
    ) -> None:
        """Test retrieving a non-existent finding."""
        finding = await prince_service.get_finding(uuid4())
        assert finding is None

    @pytest.mark.asyncio
    async def test_get_findings_by_motion(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test retrieving findings by motion."""
        motion_ref = uuid4()

        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=motion_ref,
            original_intent="Improve reliability",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        await prince_service.evaluate_compliance(request)

        findings = await prince_service.get_findings_by_motion(motion_ref)
        assert len(findings) == 1
        assert findings[0].motion_ref == motion_ref

    @pytest.mark.asyncio
    async def test_get_findings_by_plan(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test retrieving findings by plan."""
        plan_ref = uuid4()

        request = EvaluationRequest(
            plan_ref=plan_ref,
            motion_ref=uuid4(),
            original_intent="Improve reliability",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        await prince_service.evaluate_compliance(request)

        findings = await prince_service.get_findings_by_plan(plan_ref)
        assert len(findings) == 1
        assert findings[0].plan_ref == plan_ref


# =============================================================================
# TEST SERIALIZATION
# =============================================================================


class TestSerialization:
    """Test object serialization."""

    @pytest.mark.asyncio
    async def test_finding_to_dict(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test ComplianceFinding serialization."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Improve reliability",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        result = await prince_service.evaluate_compliance(request)
        d = result.finding.to_dict()

        assert "finding_id" in d
        assert "verdict" in d
        assert "criteria_results" in d
        assert "violations" in d
        assert "recommendations" in d
        assert "evaluated_by" in d
        assert "summary" in d

    @pytest.mark.asyncio
    async def test_result_to_dict(
        self,
        prince_service: PrinceServiceAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test EvaluationResult serialization."""
        request = EvaluationRequest(
            plan_ref=uuid4(),
            motion_ref=uuid4(),
            original_intent="Improve reliability",
            execution_result=compliant_execution_result,
            prince_id="archon-sitri-001",
        )
        result = await prince_service.evaluate_compliance(request)
        d = result.to_dict()

        assert d["success"] is True
        assert d["finding"] is not None
