"""Unit tests for AegisTaskSpec domain models.

Tests the formal contract between President Service, Aegis Network, and Prince Service.
Per Government PRD FR-GOV-9: President produces execution specifications.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.models.aegis_task_spec import (
    AegisTaskSpec,
    Constraint,
    ConstraintType,
    Dependency,
    DependencyType,
    ExpectedOutput,
    MeasurementPoint,
    MeasurementTrigger,
    MeasurementType,
    OutputType,
    SuccessCriterion,
    TaskMetadata,
    TaskPriority,
    TaskStatus,
    ThresholdOperator,
    WitnessingRequirements,
)


# =============================================================================
# TEST SUCCESS CRITERION
# =============================================================================


class TestSuccessCriterion:
    """Test SuccessCriterion dataclass."""

    def test_create_boolean_criterion(self) -> None:
        """Test creating a boolean success criterion."""
        criterion = SuccessCriterion.create(
            description="Task completes without errors",
            measurement_type=MeasurementType.BOOLEAN,
        )

        assert criterion.criterion_id is not None
        assert criterion.description == "Task completes without errors"
        assert criterion.measurement_type == MeasurementType.BOOLEAN
        assert criterion.weight == 1.0

    def test_create_threshold_criterion(self) -> None:
        """Test creating a threshold criterion with target value."""
        criterion = SuccessCriterion.create(
            description="Response time under 100ms",
            measurement_type=MeasurementType.THRESHOLD,
            target_value=100,
            threshold_operator=ThresholdOperator.LTE,
            weight=2.0,
        )

        assert criterion.target_value == 100
        assert criterion.threshold_operator == ThresholdOperator.LTE
        assert criterion.weight == 2.0

    def test_criterion_is_immutable(self) -> None:
        """Test that criterion is frozen."""
        criterion = SuccessCriterion.create(
            description="Test",
            measurement_type=MeasurementType.BOOLEAN,
        )

        with pytest.raises(Exception):
            criterion.description = "Modified"  # type: ignore

    def test_criterion_to_dict(self) -> None:
        """Test serialization."""
        criterion = SuccessCriterion.create(
            description="Test",
            measurement_type=MeasurementType.NUMERIC,
            target_value=50,
        )

        d = criterion.to_dict()

        assert "criterion_id" in d
        assert d["description"] == "Test"
        assert d["measurement_type"] == "numeric"
        assert d["target_value"] == 50


# =============================================================================
# TEST DEPENDENCY
# =============================================================================


class TestDependency:
    """Test Dependency dataclass."""

    def test_create_blocking_dependency(self) -> None:
        """Test creating a blocking dependency."""
        task_ref = uuid4()
        dep = Dependency.create(
            dependency_type=DependencyType.BLOCKS,
            task_ref=task_ref,
            required=True,
        )

        assert dep.dependency_id is not None
        assert dep.dependency_type == DependencyType.BLOCKS
        assert dep.task_ref == task_ref
        assert dep.required is True

    def test_create_informing_dependency(self) -> None:
        """Test creating an informing dependency."""
        task_ref = uuid4()
        dep = Dependency.create(
            dependency_type=DependencyType.INFORMS,
            task_ref=task_ref,
            required=False,
        )

        assert dep.dependency_type == DependencyType.INFORMS
        assert dep.required is False

    def test_dependency_to_dict(self) -> None:
        """Test serialization."""
        task_ref = uuid4()
        dep = Dependency.create(
            dependency_type=DependencyType.PARALLEL,
            task_ref=task_ref,
        )

        d = dep.to_dict()

        assert d["dependency_type"] == "parallel"
        assert d["task_ref"] == str(task_ref)


# =============================================================================
# TEST CONSTRAINT
# =============================================================================


class TestConstraint:
    """Test Constraint dataclass."""

    def test_create_time_limit_constraint(self) -> None:
        """Test creating a time limit constraint."""
        constraint = Constraint.create(
            constraint_type=ConstraintType.TIME_LIMIT,
            description="Maximum execution time",
            value=3600,  # 1 hour in seconds
        )

        assert constraint.constraint_type == ConstraintType.TIME_LIMIT
        assert constraint.value == 3600

    def test_create_constitutional_constraint(self) -> None:
        """Test creating a constitutional constraint."""
        constraint = Constraint.create(
            constraint_type=ConstraintType.CONSTITUTIONAL,
            description="Must not define execution details",
            prd_reference="FR-GOV-6",
        )

        assert constraint.constraint_type == ConstraintType.CONSTITUTIONAL
        assert constraint.prd_reference == "FR-GOV-6"

    def test_constraint_to_dict(self) -> None:
        """Test serialization."""
        constraint = Constraint.create(
            constraint_type=ConstraintType.SCOPE_LIMIT,
            description="Cannot modify database directly",
        )

        d = constraint.to_dict()

        assert d["constraint_type"] == "scope_limit"
        assert d["description"] == "Cannot modify database directly"


# =============================================================================
# TEST EXPECTED OUTPUT
# =============================================================================


class TestExpectedOutput:
    """Test ExpectedOutput dataclass."""

    def test_create_file_output(self) -> None:
        """Test creating a file output."""
        output = ExpectedOutput.create(
            name="report.pdf",
            output_type=OutputType.FILE,
            description="Analysis report",
            required=True,
        )

        assert output.name == "report.pdf"
        assert output.output_type == OutputType.FILE
        assert output.required is True

    def test_create_witness_output(self) -> None:
        """Test creating a witness statement output."""
        output = ExpectedOutput.create(
            name="completion_witness",
            output_type=OutputType.WITNESS,
            required=True,
        )

        assert output.output_type == OutputType.WITNESS


# =============================================================================
# TEST MEASUREMENT POINT
# =============================================================================


class TestMeasurementPoint:
    """Test MeasurementPoint dataclass."""

    def test_create_checkpoint(self) -> None:
        """Test creating a checkpoint measurement point."""
        criterion_id = uuid4()
        point = MeasurementPoint.create(
            name="Midpoint Check",
            trigger=MeasurementTrigger.CHECKPOINT,
            criteria_refs=[criterion_id],
        )

        assert point.name == "Midpoint Check"
        assert point.trigger == MeasurementTrigger.CHECKPOINT
        assert criterion_id in point.criteria_refs

    def test_measurement_point_to_dict(self) -> None:
        """Test serialization."""
        point = MeasurementPoint.create(
            name="Completion",
            trigger=MeasurementTrigger.COMPLETION,
        )

        d = point.to_dict()

        assert d["trigger"] == "completion"


# =============================================================================
# TEST AEGIS TASK SPEC
# =============================================================================


class TestAegisTaskSpec:
    """Test AegisTaskSpec dataclass."""

    @pytest.fixture
    def sample_criterion(self) -> SuccessCriterion:
        """Create a sample success criterion."""
        return SuccessCriterion.create(
            description="Task completes successfully",
            measurement_type=MeasurementType.BOOLEAN,
        )

    @pytest.fixture
    def sample_output(self) -> ExpectedOutput:
        """Create a sample expected output."""
        return ExpectedOutput.create(
            name="result.json",
            output_type=OutputType.FILE,
        )

    def test_create_minimal_spec(
        self,
        sample_criterion: SuccessCriterion,
        sample_output: ExpectedOutput,
    ) -> None:
        """Test creating a minimal valid spec."""
        motion_ref = uuid4()
        spec = AegisTaskSpec.create(
            motion_ref=motion_ref,
            intent_summary="Analyze customer feedback data",
            success_criteria=[sample_criterion],
            expected_outputs=[sample_output],
            created_by="archon-president-001",
        )

        assert spec.task_id is not None
        assert spec.motion_ref == motion_ref
        assert spec.intent_summary == "Analyze customer feedback data"
        assert spec.status == TaskStatus.DRAFT
        assert len(spec.success_criteria) == 1
        assert len(spec.expected_outputs) == 1

    def test_create_full_spec(
        self,
        sample_criterion: SuccessCriterion,
        sample_output: ExpectedOutput,
    ) -> None:
        """Test creating a spec with all fields."""
        motion_ref = uuid4()
        session_ref = uuid4()
        dep_task_ref = uuid4()

        dep = Dependency.create(
            dependency_type=DependencyType.BLOCKS,
            task_ref=dep_task_ref,
        )

        constraint = Constraint.create(
            constraint_type=ConstraintType.TIME_LIMIT,
            description="Max 1 hour",
            value=3600,
        )

        measurement = MeasurementPoint.create(
            name="Start",
            trigger=MeasurementTrigger.START,
        )

        metadata = TaskMetadata(
            priority=TaskPriority.HIGH,
            tags=("urgent", "analytics"),
            estimated_duration_seconds=1800,
        )

        witnessing = WitnessingRequirements(
            require_witness_on_start=True,
            require_witness_on_complete=True,
        )

        spec = AegisTaskSpec.create(
            motion_ref=motion_ref,
            intent_summary="Full test spec",
            success_criteria=[sample_criterion],
            expected_outputs=[sample_output],
            created_by="archon-president-001",
            session_ref=session_ref,
            dependencies=[dep],
            constraints=[constraint],
            measurement_points=[measurement],
            metadata=metadata,
            witnessing=witnessing,
        )

        assert spec.session_ref == session_ref
        assert len(spec.dependencies) == 1
        assert len(spec.constraints) == 1
        assert len(spec.measurement_points) == 1
        assert spec.metadata.priority == TaskPriority.HIGH
        assert spec.witnessing.require_witness_on_start is True

    def test_spec_is_immutable(
        self,
        sample_criterion: SuccessCriterion,
        sample_output: ExpectedOutput,
    ) -> None:
        """Test that spec is frozen."""
        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test",
            success_criteria=[sample_criterion],
            expected_outputs=[sample_output],
            created_by="test",
        )

        with pytest.raises(Exception):
            spec.intent_summary = "Modified"  # type: ignore

    def test_spec_to_dict(
        self,
        sample_criterion: SuccessCriterion,
        sample_output: ExpectedOutput,
    ) -> None:
        """Test serialization."""
        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test serialization",
            success_criteria=[sample_criterion],
            expected_outputs=[sample_output],
            created_by="test",
        )

        d = spec.to_dict()

        assert "task_id" in d
        assert d["intent_summary"] == "Test serialization"
        assert d["status"] == "draft"
        assert len(d["success_criteria"]) == 1

    def test_is_executable(
        self,
        sample_criterion: SuccessCriterion,
        sample_output: ExpectedOutput,
    ) -> None:
        """Test is_executable property."""
        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test",
            success_criteria=[sample_criterion],
            expected_outputs=[sample_output],
            created_by="test",
        )

        assert spec.is_executable is True

    def test_total_weight(self) -> None:
        """Test total_weight property."""
        criteria = [
            SuccessCriterion.create(
                description="C1",
                measurement_type=MeasurementType.BOOLEAN,
                weight=1.0,
            ),
            SuccessCriterion.create(
                description="C2",
                measurement_type=MeasurementType.BOOLEAN,
                weight=2.0,
            ),
        ]

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test",
            success_criteria=criteria,
            expected_outputs=[ExpectedOutput.create("out", OutputType.FILE)],
            created_by="test",
        )

        assert spec.total_weight == 3.0

    def test_get_criterion_by_id(
        self,
        sample_criterion: SuccessCriterion,
        sample_output: ExpectedOutput,
    ) -> None:
        """Test get_criterion_by_id method."""
        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test",
            success_criteria=[sample_criterion],
            expected_outputs=[sample_output],
            created_by="test",
        )

        found = spec.get_criterion_by_id(sample_criterion.criterion_id)
        assert found is not None
        assert found.criterion_id == sample_criterion.criterion_id

        not_found = spec.get_criterion_by_id(uuid4())
        assert not_found is None


# =============================================================================
# TEST ENUMS
# =============================================================================


class TestEnums:
    """Test enum values."""

    def test_task_status_values(self) -> None:
        """Test TaskStatus enum."""
        assert TaskStatus.DRAFT.value == "draft"
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.EXECUTING.value == "executing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.JUDGED.value == "judged"

    def test_measurement_type_values(self) -> None:
        """Test MeasurementType enum."""
        assert MeasurementType.BOOLEAN.value == "boolean"
        assert MeasurementType.NUMERIC.value == "numeric"
        assert MeasurementType.THRESHOLD.value == "threshold"
        assert MeasurementType.COMPLETION.value == "completion"

    def test_constraint_type_values(self) -> None:
        """Test ConstraintType enum."""
        assert ConstraintType.TIME_LIMIT.value == "time_limit"
        assert ConstraintType.CONSTITUTIONAL.value == "constitutional"
