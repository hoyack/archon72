"""Unit tests for IntentValidator.

Tests validation that motion text contains only WHAT (intent), not HOW (execution details).
Per Government PRD FR-GOV-6.
"""

import pytest

from src.application.ports.king_service import IntentViolationType
from src.application.services.intent_validator import (
    IntentValidator,
    create_intent_validator,
    is_intent_only,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def validator() -> IntentValidator:
    """Create a validator for testing."""
    return IntentValidator(verbose=True)


# =============================================================================
# TEST VALIDATOR INITIALIZATION
# =============================================================================


class TestValidatorInit:
    """Test validator initialization."""

    def test_create_validator(self) -> None:
        """Test basic validator creation."""
        validator = IntentValidator()
        assert validator is not None

    def test_factory_function(self) -> None:
        """Test factory function."""
        validator = create_intent_validator(verbose=True)
        assert isinstance(validator, IntentValidator)


# =============================================================================
# TEST VALID INTENT (WHAT ONLY)
# =============================================================================


class TestValidIntent:
    """Test validation of valid intent-only content."""

    def test_simple_intent(self, validator: IntentValidator) -> None:
        """Test simple, clean intent."""
        intent = "Improve customer satisfaction by reducing response times."
        result = validator.validate(intent)

        assert result.is_valid is True
        assert result.violation_count == 0

    def test_goal_oriented_intent(self, validator: IntentValidator) -> None:
        """Test goal-oriented WHAT statement."""
        intent = (
            "Increase market share in the enterprise segment by addressing "
            "the needs of large organizations better."
        )
        result = validator.validate(intent)

        assert result.is_valid is True

    def test_outcome_focused_intent(self, validator: IntentValidator) -> None:
        """Test outcome-focused WHAT."""
        intent = (
            "Ensure all users can access their data within acceptable time frames, "
            "even during peak usage periods."
        )
        result = validator.validate(intent)

        assert result.is_valid is True

    def test_value_proposition_intent(self, validator: IntentValidator) -> None:
        """Test value proposition style intent."""
        intent = (
            "Deliver an analytics capability that enables business users to "
            "understand trends without technical expertise."
        )
        result = validator.validate(intent)

        assert result.is_valid is True


# =============================================================================
# TEST TASK LIST VIOLATIONS
# =============================================================================


class TestTaskListViolations:
    """Test detection of task list execution details."""

    def test_numbered_steps(self, validator: IntentValidator) -> None:
        """Test detection of numbered steps."""
        intent = "Step 1: Analyze the data. Step 2: Generate the report."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TASK_LIST for v in result.violations
        )

    def test_sequential_ordering(self, validator: IntentValidator) -> None:
        """Test detection of sequential ordering."""
        intent = (
            "First, we should analyze the requirements. Second, we build the solution."
        )
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TASK_LIST for v in result.violations
        )

    def test_bullet_point_tasks(self, validator: IntentValidator) -> None:
        """Test detection of bullet-point task lists."""
        intent = """The motion proposes:
- Implement the new API
- Create the database schema
- Build the frontend"""
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TASK_LIST for v in result.violations
        )

    def test_explicit_task_enumeration(self, validator: IntentValidator) -> None:
        """Test detection of explicit task enumeration."""
        intent = "Task 1 will handle authentication, task 2 will handle authorization."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TASK_LIST for v in result.violations
        )


# =============================================================================
# TEST TIMELINE VIOLATIONS
# =============================================================================


class TestTimelineViolations:
    """Test detection of timeline execution details."""

    def test_explicit_timeline(self, validator: IntentValidator) -> None:
        """Test detection of explicit timeline."""
        intent = "Achieve the goal with timeline: 3 weeks for development."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TIMELINE for v in result.violations
        )

    def test_deadline_specification(self, validator: IntentValidator) -> None:
        """Test detection of deadline specification."""
        intent = "Complete the project within 2 weeks."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TIMELINE for v in result.violations
        )

    def test_phased_timeline(self, validator: IntentValidator) -> None:
        """Test detection of phased timeline."""
        intent = "Phase 1 will deliver core features, Phase 2 will add extensions."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TIMELINE for v in result.violations
        )

    def test_schedule_specification(self, validator: IntentValidator) -> None:
        """Test detection of schedule specification."""
        intent = "Schedule: Development starts Monday."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TIMELINE for v in result.violations
        )


# =============================================================================
# TEST TOOL SPECIFICATION VIOLATIONS
# =============================================================================


class TestToolSpecificationViolations:
    """Test detection of tool specification execution details."""

    def test_programming_language(self, validator: IntentValidator) -> None:
        """Test detection of programming language specification."""
        intent = "Build the solution using Python."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TOOL_SPECIFICATION
            for v in result.violations
        )

    def test_framework_specification(self, validator: IntentValidator) -> None:
        """Test detection of framework specification."""
        intent = "Implement with Django for the backend."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TOOL_SPECIFICATION
            for v in result.violations
        )

    def test_tool_usage(self, validator: IntentValidator) -> None:
        """Test detection of tool usage specification."""
        intent = "Use the API and SDK to integrate with external services."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TOOL_SPECIFICATION
            for v in result.violations
        )

    def test_deployment_target(self, validator: IntentValidator) -> None:
        """Test detection of deployment target specification."""
        intent = "Deploy to AWS for scalability."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.TOOL_SPECIFICATION
            for v in result.violations
        )


# =============================================================================
# TEST RESOURCE ALLOCATION VIOLATIONS
# =============================================================================


class TestResourceAllocationViolations:
    """Test detection of resource allocation execution details."""

    def test_team_allocation(self, validator: IntentValidator) -> None:
        """Test detection of team allocation."""
        intent = "Allocate 3 developers to the project."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.RESOURCE_ALLOCATION
            for v in result.violations
        )

    def test_budget_specification(self, validator: IntentValidator) -> None:
        """Test detection of budget specification."""
        intent = "Budget: $50000 for the initiative."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.RESOURCE_ALLOCATION
            for v in result.violations
        )

    def test_resource_requirements(self, validator: IntentValidator) -> None:
        """Test detection of resource requirements."""
        intent = "Requires 5 developers and 2 weeks effort."
        result = validator.validate(intent)

        assert result.is_valid is False
        # Should have both resource allocation and timeline violations


# =============================================================================
# TEST EXECUTION METHOD VIOLATIONS
# =============================================================================


class TestExecutionMethodViolations:
    """Test detection of execution method details."""

    def test_method_definition(self, validator: IntentValidator) -> None:
        """Test detection of method definition."""
        intent = "The method will be agile sprints with daily standups."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.EXECUTION_METHOD
            for v in result.violations
        )

    def test_procedure_specification(self, validator: IntentValidator) -> None:
        """Test detection of procedure specification."""
        intent = "The procedure to achieve this involves automated testing."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.EXECUTION_METHOD
            for v in result.violations
        )


# =============================================================================
# TEST SUPERVISION DIRECTION VIOLATIONS
# =============================================================================


class TestSupervisionDirectionViolations:
    """Test detection of supervision direction details."""

    def test_supervision_directive(self, validator: IntentValidator) -> None:
        """Test detection of supervision directive."""
        intent = "Supervise the execution closely with weekly check-ins."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.SUPERVISION_DIRECTION
            for v in result.violations
        )

    def test_reporting_structure(self, validator: IntentValidator) -> None:
        """Test detection of reporting structure."""
        intent = "The team will report to the project manager."
        result = validator.validate(intent)

        assert result.is_valid is False
        assert any(
            v.violation_type == IntentViolationType.SUPERVISION_DIRECTION
            for v in result.violations
        )


# =============================================================================
# TEST VIOLATION SUMMARY
# =============================================================================


class TestViolationSummary:
    """Test violation summary generation."""

    def test_valid_summary(self, validator: IntentValidator) -> None:
        """Test summary for valid intent."""
        intent = "Improve system reliability."
        result = validator.validate(intent)
        summary = validator.get_violation_summary(result)

        assert "valid" in summary.lower()
        assert "WHAT, not HOW" in summary

    def test_violation_summary(self, validator: IntentValidator) -> None:
        """Test summary for invalid intent."""
        intent = "Step 1: Build the API using Python within 2 weeks."
        result = validator.validate(intent)
        summary = validator.get_violation_summary(result)

        assert "violation" in summary.lower()
        assert "FR-GOV-6" in summary


# =============================================================================
# TEST CONVENIENCE FUNCTION
# =============================================================================


class TestConvenienceFunction:
    """Test is_intent_only convenience function."""

    def test_valid_intent(self) -> None:
        """Test with valid intent."""
        assert is_intent_only("Improve customer satisfaction.") is True

    def test_invalid_intent(self) -> None:
        """Test with invalid intent containing execution details."""
        assert is_intent_only("Step 1: Analyze. Step 2: Build.") is False


# =============================================================================
# TEST EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self, validator: IntentValidator) -> None:
        """Test empty string validation."""
        result = validator.validate("")
        assert result.is_valid is True

    def test_very_long_valid_intent(self, validator: IntentValidator) -> None:
        """Test very long valid intent."""
        intent = (
            "Improve the overall user experience by making the system more intuitive. "
            * 50
        )
        result = validator.validate(intent)
        assert result.is_valid is True

    def test_case_insensitivity(self, validator: IntentValidator) -> None:
        """Test that detection is case-insensitive."""
        intent = "STEP 1: DO SOMETHING. USING PYTHON."
        result = validator.validate(intent)
        assert result.is_valid is False

    def test_multiple_violations(self, validator: IntentValidator) -> None:
        """Test detection of multiple violation types."""
        intent = (
            "Step 1: Build using Python within 2 weeks. "
            "Allocate 3 developers. Supervise the execution daily."
        )
        result = validator.validate(intent)

        assert result.is_valid is False
        # Should detect multiple types
        violation_types = {v.violation_type for v in result.violations}
        assert len(violation_types) >= 3
