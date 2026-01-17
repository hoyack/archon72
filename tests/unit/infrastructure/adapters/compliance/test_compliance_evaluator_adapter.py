"""Unit tests for ComplianceEvaluatorAdapter.

Tests the Compliance Evaluator measurement functions per Government PRD FR-GOV-14.
"""

import pytest
from uuid import uuid4

from src.application.ports.compliance_evaluator import (
    EvaluationRequest,
    EvidenceCollectionRequest,
    ExecutionEvidence,
    MeasurementVerdict,
    OverallCompliance,
    SuccessCriterion,
)
from src.infrastructure.adapters.compliance.compliance_evaluator_adapter import (
    ComplianceEvaluatorAdapter,
    create_compliance_evaluator,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def evaluator() -> ComplianceEvaluatorAdapter:
    """Create a Compliance Evaluator for testing."""
    return ComplianceEvaluatorAdapter(verbose=True)


@pytest.fixture
def sample_criterion() -> SuccessCriterion:
    """Create a sample success criterion."""
    return SuccessCriterion(
        criterion_id="c1",
        description="System response time should be reduced to under 100ms",
        measurement_method="Measure average response time from load tests",
        threshold="<100",
        required=True,
    )


@pytest.fixture
def sample_evidence() -> list[ExecutionEvidence]:
    """Create sample execution evidence."""
    return [
        ExecutionEvidence.create(
            description="Load test results show response time reduced to 50ms",
            source="load_test_report",
            evidence_type="metrics",
            data={"average_response_time_ms": 50, "p99_response_time_ms": 95},
        ),
        ExecutionEvidence.create(
            description="Performance optimization deployed",
            source="deployment_log",
            evidence_type="output",
            data={"status": "deployed", "optimizations": ["caching", "connection_pooling"]},
        ),
    ]


@pytest.fixture
def compliant_execution_result() -> dict:
    """Create a compliant execution result."""
    return {
        "summary": "Performance optimization completed successfully",
        "complete": True,
        "criteria": [
            {"id": "c1", "description": "Response time reduced"},
            {"id": "c2", "description": "Caching implemented"},
        ],
        "evidence": [
            {"description": "Response time is now 50ms", "source": "metrics"},
            {"description": "Redis caching deployed", "source": "logs"},
        ],
        "outputs": {
            "response_time_ms": 50,
            "cache_hit_rate": 0.95,
        },
        "metrics": {
            "avg_response_time": 50,
            "throughput": 1000,
        },
        "deviations": [],
        "constraint_violations": [],
    }


@pytest.fixture
def non_compliant_execution_result() -> dict:
    """Create a non-compliant execution result."""
    return {
        "summary": "Performance optimization failed to meet targets",
        "complete": False,
        "criteria": [
            {"id": "c1", "description": "Response time reduced"},
        ],
        "evidence": [],
        "outputs": {},
        "metrics": {},
        "deviations": [
            {"description": "Response time still at 200ms"},
        ],
        "constraint_violations": [
            {"description": "Exceeded time limit"},
        ],
    }


# =============================================================================
# TEST ADAPTER INITIALIZATION
# =============================================================================


class TestAdapterInit:
    """Test adapter initialization."""

    def test_create_adapter(self) -> None:
        """Test basic adapter creation."""
        adapter = ComplianceEvaluatorAdapter()
        assert adapter is not None

    def test_factory_function(self) -> None:
        """Test factory function."""
        adapter = create_compliance_evaluator(verbose=True)
        assert isinstance(adapter, ComplianceEvaluatorAdapter)


# =============================================================================
# TEST CRITERION MEASUREMENT - MET
# =============================================================================


class TestCriterionMeasurementMet:
    """Test criterion measurement when criteria are met."""

    @pytest.mark.asyncio
    async def test_measure_criterion_met(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        sample_criterion: SuccessCriterion,
        sample_evidence: list[ExecutionEvidence],
    ) -> None:
        """Test measuring a criterion that is fully met."""
        result = await evaluator.measure_criterion(
            criterion=sample_criterion,
            evidence=sample_evidence,
        )

        assert result.verdict in [MeasurementVerdict.MET, MeasurementVerdict.PARTIALLY_MET]
        assert len(result.evidence_refs) > 0

    @pytest.mark.asyncio
    async def test_measurement_includes_evidence_refs(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        sample_criterion: SuccessCriterion,
        sample_evidence: list[ExecutionEvidence],
    ) -> None:
        """Test that measurement includes evidence references."""
        result = await evaluator.measure_criterion(
            criterion=sample_criterion,
            evidence=sample_evidence,
        )

        # Should reference the evidence
        evidence_ids = {e.evidence_id for e in sample_evidence}
        assert any(ref in evidence_ids for ref in result.evidence_refs)


# =============================================================================
# TEST CRITERION MEASUREMENT - NOT MET
# =============================================================================


class TestCriterionMeasurementNotMet:
    """Test criterion measurement when criteria are not met."""

    @pytest.mark.asyncio
    async def test_measure_criterion_no_evidence(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        sample_criterion: SuccessCriterion,
    ) -> None:
        """Test measuring a criterion with no evidence."""
        result = await evaluator.measure_criterion(
            criterion=sample_criterion,
            evidence=[],
        )

        assert result.verdict == MeasurementVerdict.UNMEASURABLE
        assert "No evidence" in (result.notes or "")

    @pytest.mark.asyncio
    async def test_measure_criterion_irrelevant_evidence(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test measuring a criterion with irrelevant evidence."""
        criterion = SuccessCriterion(
            criterion_id="c1",
            description="Database schema migration completed",
            measurement_method="Check migration status",
            required=True,
        )

        evidence = [
            ExecutionEvidence.create(
                description="User interface updated",
                source="ui_logs",
                evidence_type="output",
                data={"ui_changes": ["button_color", "font_size"]},
            ),
        ]

        result = await evaluator.measure_criterion(criterion, evidence)

        assert result.verdict in [MeasurementVerdict.NOT_MET, MeasurementVerdict.PARTIALLY_MET]


# =============================================================================
# TEST EVIDENCE COLLECTION
# =============================================================================


class TestEvidenceCollection:
    """Test evidence collection from execution."""

    @pytest.mark.asyncio
    async def test_collect_evidence_outputs(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test collecting evidence from outputs."""
        request = EvidenceCollectionRequest(
            task_spec_ref=uuid4(),
            execution_outputs={"result": "success", "count": 42},
            execution_logs=[],
            execution_metrics={},
        )

        response = await evaluator.collect_evidence(request)

        assert response.success is True
        assert len(response.evidence) >= 2  # One per output key

    @pytest.mark.asyncio
    async def test_collect_evidence_logs(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test collecting evidence from logs."""
        request = EvidenceCollectionRequest(
            task_spec_ref=uuid4(),
            execution_outputs={},
            execution_logs=["Started task", "Completed task"],
            execution_metrics={},
        )

        response = await evaluator.collect_evidence(request)

        assert response.success is True
        assert any(e.evidence_type == "logs" for e in response.evidence)

    @pytest.mark.asyncio
    async def test_collect_evidence_metrics(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test collecting evidence from metrics."""
        request = EvidenceCollectionRequest(
            task_spec_ref=uuid4(),
            execution_outputs={},
            execution_logs=[],
            execution_metrics={"duration_ms": 100, "memory_mb": 256},
        )

        response = await evaluator.collect_evidence(request)

        assert response.success is True
        assert any(e.evidence_type == "metrics" for e in response.evidence)


# =============================================================================
# TEST OVERALL COMPLIANCE DETERMINATION
# =============================================================================


class TestOverallCompliance:
    """Test overall compliance determination."""

    @pytest.mark.asyncio
    async def test_full_compliance(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test full compliance when all criteria met."""
        criterion = SuccessCriterion(
            criterion_id="c1",
            description="Task completed",
            measurement_method="Check completion",
            required=True,
        )

        from src.application.ports.compliance_evaluator import CriterionMeasurement
        from datetime import datetime, timezone

        measurements = [
            CriterionMeasurement(
                criterion=criterion,
                verdict=MeasurementVerdict.MET,
                evidence_refs=(uuid4(),),
                measured_at=datetime.now(timezone.utc),
            ),
        ]

        overall = await evaluator.determine_overall(measurements)
        assert overall == OverallCompliance.FULL

    @pytest.mark.asyncio
    async def test_partial_compliance(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test partial compliance when some criteria partially met."""
        from src.application.ports.compliance_evaluator import CriterionMeasurement
        from datetime import datetime, timezone

        c1 = SuccessCriterion("c1", "First criterion", "measure", required=False)
        c2 = SuccessCriterion("c2", "Second criterion", "measure", required=False)

        measurements = [
            CriterionMeasurement(
                criterion=c1,
                verdict=MeasurementVerdict.MET,
                evidence_refs=(uuid4(),),
                measured_at=datetime.now(timezone.utc),
            ),
            CriterionMeasurement(
                criterion=c2,
                verdict=MeasurementVerdict.PARTIALLY_MET,
                evidence_refs=(uuid4(),),
                measured_at=datetime.now(timezone.utc),
            ),
        ]

        overall = await evaluator.determine_overall(measurements)
        assert overall == OverallCompliance.PARTIAL

    @pytest.mark.asyncio
    async def test_failed_compliance(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test failed compliance when required criteria not met."""
        from src.application.ports.compliance_evaluator import CriterionMeasurement
        from datetime import datetime, timezone

        c1 = SuccessCriterion("c1", "Required criterion", "measure", required=True)

        measurements = [
            CriterionMeasurement(
                criterion=c1,
                verdict=MeasurementVerdict.NOT_MET,
                evidence_refs=(),
                measured_at=datetime.now(timezone.utc),
            ),
        ]

        overall = await evaluator.determine_overall(measurements)
        assert overall == OverallCompliance.FAILED


# =============================================================================
# TEST FULL EVALUATION
# =============================================================================


class TestFullEvaluation:
    """Test full evaluation process."""

    @pytest.mark.asyncio
    async def test_evaluate_compliant_execution(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test evaluating a compliant execution."""
        request = EvaluationRequest(
            task_spec_ref=uuid4(),
            motion_ref=uuid4(),
            criteria=[
                SuccessCriterion(
                    criterion_id="c1",
                    description="Response time reduced",
                    measurement_method="Check metrics",
                    required=True,
                ),
                SuccessCriterion(
                    criterion_id="c2",
                    description="Caching implemented",
                    measurement_method="Check deployment",
                    required=False,
                ),
            ],
            execution_result=compliant_execution_result,
        )

        response = await evaluator.evaluate(request)

        assert response.success is True
        assert response.evaluation is not None
        assert response.evaluation.overall in [
            OverallCompliance.FULL,
            OverallCompliance.PARTIAL,
        ]

    @pytest.mark.asyncio
    async def test_evaluate_non_compliant_execution(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        non_compliant_execution_result: dict,
    ) -> None:
        """Test evaluating a non-compliant execution."""
        request = EvaluationRequest(
            task_spec_ref=uuid4(),
            motion_ref=uuid4(),
            criteria=[
                SuccessCriterion(
                    criterion_id="c1",
                    description="Performance targets met",
                    measurement_method="Check metrics",
                    required=True,
                ),
            ],
            execution_result=non_compliant_execution_result,
        )

        response = await evaluator.evaluate(request)

        assert response.success is True
        assert response.evaluation is not None
        # Should have low compliance due to deviations and violations
        assert response.evaluation.overall in [
            OverallCompliance.INSUFFICIENT,
            OverallCompliance.FAILED,
            OverallCompliance.PARTIAL,
        ]

    @pytest.mark.asyncio
    async def test_evaluation_stored(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test that evaluation is stored after completion."""
        request = EvaluationRequest(
            task_spec_ref=uuid4(),
            motion_ref=uuid4(),
            criteria=[
                SuccessCriterion("c1", "Criterion", "method", required=True),
            ],
            execution_result=compliant_execution_result,
        )

        response = await evaluator.evaluate(request)

        # Should be retrievable
        stored = await evaluator.get_evaluation(response.evaluation.evaluation_id)
        assert stored is not None
        assert stored.evaluation_id == response.evaluation.evaluation_id


# =============================================================================
# TEST EVALUATION RETRIEVAL
# =============================================================================


class TestEvaluationRetrieval:
    """Test evaluation retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_evaluation_exists(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test retrieving an existing evaluation."""
        request = EvaluationRequest(
            task_spec_ref=uuid4(),
            motion_ref=uuid4(),
            criteria=[SuccessCriterion("c1", "Test", "method", required=True)],
            execution_result=compliant_execution_result,
        )

        response = await evaluator.evaluate(request)
        evaluation = await evaluator.get_evaluation(response.evaluation.evaluation_id)

        assert evaluation is not None

    @pytest.mark.asyncio
    async def test_get_evaluation_not_exists(
        self,
        evaluator: ComplianceEvaluatorAdapter,
    ) -> None:
        """Test retrieving a non-existent evaluation."""
        evaluation = await evaluator.get_evaluation(uuid4())
        assert evaluation is None

    @pytest.mark.asyncio
    async def test_get_evaluations_by_task(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test retrieving evaluations by task spec."""
        task_ref = uuid4()

        request = EvaluationRequest(
            task_spec_ref=task_ref,
            motion_ref=uuid4(),
            criteria=[SuccessCriterion("c1", "Test", "method", required=True)],
            execution_result=compliant_execution_result,
        )

        await evaluator.evaluate(request)

        evaluations = await evaluator.get_evaluations_by_task(task_ref)
        assert len(evaluations) == 1
        assert evaluations[0].task_spec_ref == task_ref


# =============================================================================
# TEST SERIALIZATION
# =============================================================================


class TestSerialization:
    """Test object serialization."""

    @pytest.mark.asyncio
    async def test_evaluation_to_dict(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test ComplianceEvaluation serialization."""
        request = EvaluationRequest(
            task_spec_ref=uuid4(),
            motion_ref=uuid4(),
            criteria=[SuccessCriterion("c1", "Test", "method", required=True)],
            execution_result=compliant_execution_result,
        )

        response = await evaluator.evaluate(request)
        d = response.evaluation.to_dict()

        assert "evaluation_id" in d
        assert "task_spec_ref" in d
        assert "motion_ref" in d
        assert "measurements" in d
        assert "evidence_collected" in d
        assert "overall" in d
        assert "summary" in d

    @pytest.mark.asyncio
    async def test_response_to_dict(
        self,
        evaluator: ComplianceEvaluatorAdapter,
        compliant_execution_result: dict,
    ) -> None:
        """Test EvaluationResponse serialization."""
        request = EvaluationRequest(
            task_spec_ref=uuid4(),
            motion_ref=uuid4(),
            criteria=[SuccessCriterion("c1", "Test", "method", required=True)],
            execution_result=compliant_execution_result,
        )

        response = await evaluator.evaluate(request)
        d = response.to_dict()

        assert d["success"] is True
        assert d["evaluation"] is not None


# =============================================================================
# TEST EVIDENCE DATACLASS
# =============================================================================


class TestExecutionEvidence:
    """Test ExecutionEvidence dataclass."""

    def test_create_evidence(self) -> None:
        """Test creating execution evidence."""
        evidence = ExecutionEvidence.create(
            description="Test evidence",
            source="test_source",
            evidence_type="test",
            data={"key": "value"},
        )

        assert evidence.evidence_id is not None
        assert evidence.description == "Test evidence"
        assert evidence.evidence_type == "test"

    def test_evidence_to_dict(self) -> None:
        """Test evidence serialization."""
        evidence = ExecutionEvidence.create(
            description="Test evidence",
            source="test_source",
            evidence_type="test",
            data={"key": "value"},
        )

        d = evidence.to_dict()

        assert "evidence_id" in d
        assert d["description"] == "Test evidence"
        assert d["evidence_type"] == "test"


# =============================================================================
# TEST SUCCESS CRITERION
# =============================================================================


class TestSuccessCriterion:
    """Test SuccessCriterion dataclass."""

    def test_create_criterion(self) -> None:
        """Test creating a success criterion."""
        criterion = SuccessCriterion(
            criterion_id="c1",
            description="Test criterion",
            measurement_method="Test method",
            threshold=">90",
            required=True,
        )

        assert criterion.criterion_id == "c1"
        assert criterion.required is True

    def test_criterion_to_dict(self) -> None:
        """Test criterion serialization."""
        criterion = SuccessCriterion(
            criterion_id="c1",
            description="Test criterion",
            measurement_method="Test method",
        )

        d = criterion.to_dict()

        assert d["criterion_id"] == "c1"
        assert d["description"] == "Test criterion"
