"""Unit tests for TaskSpecValidator.

Tests validation of AegisTaskSpec instances per Government PRD.
"""

from uuid import uuid4

import pytest

from src.application.services.task_spec_validator import (
    TaskSpecValidator,
    ValidationSeverity,
    create_task_spec_validator,
)
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
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def validator() -> TaskSpecValidator:
    """Create a validator for testing."""
    return TaskSpecValidator(verbose=True)


@pytest.fixture
def valid_criterion() -> SuccessCriterion:
    """Create a valid success criterion."""
    return SuccessCriterion.create(
        description="Task completes without errors",
        measurement_type=MeasurementType.BOOLEAN,
    )


@pytest.fixture
def valid_output() -> ExpectedOutput:
    """Create a valid expected output."""
    return ExpectedOutput.create(
        name="result.json",
        output_type=OutputType.FILE,
    )


@pytest.fixture
def valid_spec(
    valid_criterion: SuccessCriterion,
    valid_output: ExpectedOutput,
) -> AegisTaskSpec:
    """Create a valid task spec."""
    return AegisTaskSpec.create(
        motion_ref=uuid4(),
        intent_summary="Analyze the quarterly sales data to identify trends",
        success_criteria=[valid_criterion],
        expected_outputs=[valid_output],
        created_by="archon-president-001",
    )


# =============================================================================
# TEST VALIDATOR INITIALIZATION
# =============================================================================


class TestValidatorInit:
    """Test validator initialization."""

    def test_create_validator(self) -> None:
        """Test basic validator creation."""
        validator = TaskSpecValidator()
        assert validator is not None

    def test_factory_function(self) -> None:
        """Test factory function."""
        validator = create_task_spec_validator(verbose=True)
        assert isinstance(validator, TaskSpecValidator)


# =============================================================================
# TEST VALID SPECS
# =============================================================================


class TestValidSpecs:
    """Test validation of valid specs."""

    def test_minimal_valid_spec(
        self,
        validator: TaskSpecValidator,
        valid_spec: AegisTaskSpec,
    ) -> None:
        """Test validating a minimal valid spec."""
        result = validator.validate(valid_spec)

        assert result.is_valid is True
        assert result.error_count == 0

    def test_full_valid_spec(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test validating a fully populated spec."""
        constraint = Constraint.create(
            constraint_type=ConstraintType.TIME_LIMIT,
            description="Max 1 hour",
            value=3600,
        )

        measurement = MeasurementPoint.create(
            name="Start",
            trigger=MeasurementTrigger.START,
            criteria_refs=[valid_criterion.criterion_id],
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Complete analysis of market data",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="president-001",
            constraints=[constraint],
            measurement_points=[measurement],
        )

        result = validator.validate(spec)

        assert result.is_valid is True


# =============================================================================
# TEST REQUIRED FIELD VALIDATION
# =============================================================================


class TestRequiredFields:
    """Test validation of required fields."""

    def test_missing_success_criteria(
        self,
        validator: TaskSpecValidator,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that empty success criteria fails validation."""
        # Create spec with empty criteria (bypassing create method validation)
        spec = AegisTaskSpec(
            task_id=uuid4(),
            motion_ref=uuid4(),
            intent_summary="Test",
            success_criteria=tuple(),
            expected_outputs=(valid_output,),
            created_at=None,  # type: ignore
            created_by="test",
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any(
            i.field == "success_criteria" and i.severity == ValidationSeverity.ERROR
            for i in result.issues
        )

    def test_missing_expected_outputs(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
    ) -> None:
        """Test that empty expected outputs fails validation."""
        spec = AegisTaskSpec(
            task_id=uuid4(),
            motion_ref=uuid4(),
            intent_summary="Test",
            success_criteria=(valid_criterion,),
            expected_outputs=tuple(),
            created_at=None,  # type: ignore
            created_by="test",
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any(
            i.field == "expected_outputs" and i.severity == ValidationSeverity.ERROR
            for i in result.issues
        )


# =============================================================================
# TEST SUCCESS CRITERIA VALIDATION
# =============================================================================


class TestSuccessCriteriaValidation:
    """Test validation of success criteria."""

    def test_threshold_without_target_value(
        self,
        validator: TaskSpecValidator,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that threshold criterion without target value fails."""
        criterion = SuccessCriterion.create(
            description="Response time is acceptable",
            measurement_type=MeasurementType.THRESHOLD,
            target_value=None,  # Missing!
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test threshold validation",
            success_criteria=[criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any("not measurable" in i.message for i in result.issues)

    def test_zero_weight_criterion(
        self,
        validator: TaskSpecValidator,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that zero weight criterion fails."""
        criterion = SuccessCriterion.create(
            description="Invalid criterion",
            measurement_type=MeasurementType.BOOLEAN,
            weight=0.0,
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test weight validation",
            success_criteria=[criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any(
            "weight" in i.field and "positive" in i.message for i in result.issues
        )

    def test_short_description_warning(
        self,
        validator: TaskSpecValidator,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that very short descriptions get warnings."""
        criterion = SuccessCriterion.create(
            description="OK",  # Very short
            measurement_type=MeasurementType.BOOLEAN,
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test description validation for short criterion",
            success_criteria=[criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        result = validator.validate(spec)

        assert any(
            i.severity == ValidationSeverity.WARNING and "short" in i.message
            for i in result.issues
        )


# =============================================================================
# TEST DEPENDENCY VALIDATION
# =============================================================================


class TestDependencyValidation:
    """Test validation of dependencies."""

    def test_self_referential_dependency(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that self-referential dependency fails."""
        task_id = uuid4()
        dep = Dependency.create(
            dependency_type=DependencyType.BLOCKS,
            task_ref=task_id,  # Same as spec task_id
        )

        # Create spec with known task_id
        spec = AegisTaskSpec(
            task_id=task_id,
            motion_ref=uuid4(),
            intent_summary="Test self-reference",
            success_criteria=(valid_criterion,),
            expected_outputs=(valid_output,),
            created_at=None,  # type: ignore
            created_by="test",
            dependencies=(dep,),
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any("itself" in i.message for i in result.issues)

    def test_unresolvable_dependency_warning(
        self,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that unresolvable dependency gives warning when registry exists."""
        # Create a spec that will be in the registry
        existing_spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Existing task",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        # Validator with a registry containing only the existing spec
        validator = TaskSpecValidator(
            task_registry={existing_spec.task_id: existing_spec}
        )

        dep = Dependency.create(
            dependency_type=DependencyType.BLOCKS,
            task_ref=uuid4(),  # Non-existent task (not existing_spec.task_id)
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test dependency resolution",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
            dependencies=[dep],
        )

        result = validator.validate(spec)

        assert any(
            i.severity == ValidationSeverity.WARNING and "not found" in i.message
            for i in result.issues
        )


# =============================================================================
# TEST CONSTRAINT VALIDATION
# =============================================================================


class TestConstraintValidation:
    """Test validation of constraints."""

    def test_time_limit_non_numeric(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that time limit with non-numeric value fails."""
        constraint = Constraint.create(
            constraint_type=ConstraintType.TIME_LIMIT,
            description="Invalid time limit",
            value="one hour",  # Should be numeric
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test constraint validation",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
            constraints=[constraint],
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any("numeric value" in i.message for i in result.issues)

    def test_negative_time_limit(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that negative time limit fails."""
        constraint = Constraint.create(
            constraint_type=ConstraintType.TIME_LIMIT,
            description="Invalid time limit",
            value=-100,
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test constraint validation",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
            constraints=[constraint],
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any("positive" in i.message for i in result.issues)

    def test_constitutional_without_prd_reference(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that constitutional constraint without PRD ref gets warning."""
        constraint = Constraint.create(
            constraint_type=ConstraintType.CONSTITUTIONAL,
            description="Must follow rules",
            prd_reference=None,  # Missing
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test constitutional constraint",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
            constraints=[constraint],
        )

        result = validator.validate(spec)

        assert any(
            i.severity == ValidationSeverity.WARNING and "PRD reference" in i.message
            for i in result.issues
        )


# =============================================================================
# TEST MEASUREMENT POINT VALIDATION
# =============================================================================


class TestMeasurementPointValidation:
    """Test validation of measurement points."""

    def test_invalid_criteria_ref(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that invalid criteria reference fails."""
        measurement = MeasurementPoint.create(
            name="Check",
            trigger=MeasurementTrigger.CHECKPOINT,
            criteria_refs=[uuid4()],  # Non-existent criterion
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test measurement validation",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
            measurement_points=[measurement],
        )

        result = validator.validate(spec)

        assert result.is_valid is False
        assert any("not found in success_criteria" in i.message for i in result.issues)


# =============================================================================
# TEST INTENT SUMMARY VALIDATION
# =============================================================================


class TestIntentSummaryValidation:
    """Test validation of intent summary for execution details."""

    def test_intent_with_task_list_warning(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that task lists in intent get warning."""
        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Step 1: analyze data. Step 2: generate report.",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        result = validator.validate(spec)

        assert any(
            i.field == "intent_summary" and "execution details" in i.message
            for i in result.issues
        )

    def test_intent_with_tool_spec_warning(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that tool specifications in intent get warning."""
        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Analyze data using Python pandas library",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        result = validator.validate(spec)

        assert any(
            i.field == "intent_summary" and "execution details" in i.message
            for i in result.issues
        )

    def test_clean_intent_no_warning(
        self,
        validator: TaskSpecValidator,
        valid_criterion: SuccessCriterion,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test that clean WHAT intent has no warnings."""
        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Identify trends in quarterly sales data to inform strategy",
            success_criteria=[valid_criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        result = validator.validate(spec)

        assert not any(
            i.field == "intent_summary" and "execution details" in i.message
            for i in result.issues
        )


# =============================================================================
# TEST VALIDATION RESULT
# =============================================================================


class TestValidationResult:
    """Test ValidationResult structure."""

    def test_result_to_dict(
        self,
        validator: TaskSpecValidator,
        valid_spec: AegisTaskSpec,
    ) -> None:
        """Test result serialization."""
        result = validator.validate(valid_spec)
        d = result.to_dict()

        assert "is_valid" in d
        assert "task_id" in d
        assert "error_count" in d
        assert "warning_count" in d
        assert "issues" in d

    def test_error_count(
        self,
        validator: TaskSpecValidator,
        valid_output: ExpectedOutput,
    ) -> None:
        """Test error_count property."""
        # Create spec with multiple errors
        criterion = SuccessCriterion.create(
            description="Bad",
            measurement_type=MeasurementType.THRESHOLD,
            target_value=None,
            weight=0,
        )

        spec = AegisTaskSpec.create(
            motion_ref=uuid4(),
            intent_summary="Test",
            success_criteria=[criterion],
            expected_outputs=[valid_output],
            created_by="test",
        )

        result = validator.validate(spec)

        assert result.error_count >= 2  # At least 2 errors (measurability + weight)
