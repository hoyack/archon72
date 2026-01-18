"""AegisTaskSpec Validator.

This service validates that task specifications are complete and measurable
before being submitted to the Aegis Network for execution.

Per Government PRD FR-GOV-9: President produces execution specifications.
Per Government PRD: All success criteria must be measurable by Prince.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from structlog import get_logger

from src.domain.models.aegis_task_spec import (
    AegisTaskSpec,
    ConstraintType,
    MeasurementType,
    SuccessCriterion,
)

logger = get_logger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Spec cannot be executed
    WARNING = "warning"  # Spec can execute but has issues
    INFO = "info"  # Informational note


@dataclass
class ValidationIssue:
    """A validation issue found in the task spec."""

    severity: ValidationSeverity
    field: str
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity.value,
            "field": self.field,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Result of validating an AegisTaskSpec."""

    is_valid: bool
    task_id: UUID
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "task_id": str(self.task_id),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
        }


class TaskSpecValidator:
    """Validator for AegisTaskSpec instances.

    Validates that task specifications are:
    1. Complete: All required fields present
    2. Measurable: Success criteria can be evaluated
    3. Resolvable: Dependencies can be resolved
    4. Enforceable: Constraints can be enforced

    Per Government PRD: Incomplete specs are rejected with specific missing fields.
    """

    def __init__(
        self,
        task_registry: dict[UUID, AegisTaskSpec] | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the validator.

        Args:
            task_registry: Optional registry for resolving dependencies
            verbose: Enable verbose logging
        """
        self._task_registry = task_registry or {}
        self._verbose = verbose

    def validate(self, spec: AegisTaskSpec) -> ValidationResult:
        """Validate a task specification.

        Args:
            spec: The task spec to validate

        Returns:
            ValidationResult with any issues found
        """
        issues: list[ValidationIssue] = []

        # Run all validation checks
        issues.extend(self._validate_required_fields(spec))
        issues.extend(self._validate_success_criteria(spec))
        issues.extend(self._validate_dependencies(spec))
        issues.extend(self._validate_constraints(spec))
        issues.extend(self._validate_outputs(spec))
        issues.extend(self._validate_measurement_points(spec))
        issues.extend(self._validate_intent_summary(spec))

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        result = ValidationResult(
            is_valid=is_valid,
            task_id=spec.task_id,
            issues=issues,
        )

        if self._verbose:
            logger.debug(
                "task_spec_validated",
                task_id=str(spec.task_id),
                is_valid=is_valid,
                error_count=result.error_count,
                warning_count=result.warning_count,
            )

        return result

    def _validate_required_fields(self, spec: AegisTaskSpec) -> list[ValidationIssue]:
        """Validate required fields are present."""
        issues = []

        if not spec.motion_ref:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="motion_ref",
                    message="Motion reference is required",
                    suggestion="Provide the UUID of the ratified motion",
                )
            )

        if not spec.intent_summary:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="intent_summary",
                    message="Intent summary is required",
                    suggestion="Provide a summary of WHAT the task should accomplish",
                )
            )

        if not spec.created_by:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="created_by",
                    message="Creator (President) ID is required",
                    suggestion="Specify the Archon ID of the President who created this spec",
                )
            )

        if len(spec.success_criteria) == 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="success_criteria",
                    message="At least one success criterion is required",
                    suggestion="Add measurable criteria for task success",
                )
            )

        if len(spec.expected_outputs) == 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="expected_outputs",
                    message="At least one expected output is required",
                    suggestion="Specify what artifacts the task should produce",
                )
            )

        return issues

    def _validate_success_criteria(self, spec: AegisTaskSpec) -> list[ValidationIssue]:
        """Validate all success criteria are measurable."""
        issues = []

        for criterion in spec.success_criteria:
            # Check measurability
            if not self._is_criterion_measurable(criterion):
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field=f"success_criteria[{criterion.criterion_id}]",
                        message=f"Criterion '{criterion.description}' is not measurable",
                        suggestion="Ensure criterion has target_value for numeric/threshold types",
                    )
                )

            # Check description
            if len(criterion.description) < 10:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        field=f"success_criteria[{criterion.criterion_id}]",
                        message="Criterion description is very short",
                        suggestion="Provide a more detailed description for clarity",
                    )
                )

            # Check weight
            if criterion.weight <= 0:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field=f"success_criteria[{criterion.criterion_id}].weight",
                        message="Criterion weight must be positive",
                        suggestion="Set weight to a value greater than 0",
                    )
                )

        # Check total weight sums to something reasonable
        total_weight = sum(c.weight for c in spec.success_criteria)
        if total_weight == 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="success_criteria",
                    message="Total weight of criteria is zero",
                    suggestion="Assign positive weights to success criteria",
                )
            )

        return issues

    def _is_criterion_measurable(self, criterion: SuccessCriterion) -> bool:
        """Check if a success criterion is measurable."""
        if criterion.measurement_type == MeasurementType.BOOLEAN:
            # Boolean criteria are always measurable (pass/fail)
            return True

        if criterion.measurement_type in (
            MeasurementType.NUMERIC,
            MeasurementType.THRESHOLD,
        ):
            # Numeric/threshold criteria need a target value
            return criterion.target_value is not None

        if criterion.measurement_type == MeasurementType.COMPLETION:
            # Completion criteria are measurable if they have a description
            return bool(criterion.description)

        return True

    def _validate_dependencies(self, spec: AegisTaskSpec) -> list[ValidationIssue]:
        """Validate dependencies can be resolved."""
        issues = []

        for dep in spec.dependencies:
            # Check if dependency can be resolved
            if self._task_registry and dep.task_ref not in self._task_registry:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        field=f"dependencies[{dep.dependency_id}]",
                        message=f"Dependency task {dep.task_ref} not found in registry",
                        suggestion="Ensure the dependent task exists before execution",
                    )
                )

            # Check for self-reference
            if dep.task_ref == spec.task_id:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field=f"dependencies[{dep.dependency_id}]",
                        message="Task cannot depend on itself",
                        suggestion="Remove self-referential dependency",
                    )
                )

        # Check for circular dependencies (simplified check)
        self._check_circular_dependencies(spec, issues)

        return issues

    def _check_circular_dependencies(
        self,
        spec: AegisTaskSpec,
        issues: list[ValidationIssue],
    ) -> None:
        """Check for circular dependencies (simplified)."""
        if not self._task_registry:
            return

        visited: set[UUID] = set()
        stack: list[UUID] = [d.task_ref for d in spec.dependencies]

        while stack:
            task_id = stack.pop()
            if task_id in visited:
                continue
            visited.add(task_id)

            if task_id == spec.task_id:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field="dependencies",
                        message="Circular dependency detected",
                        suggestion="Review dependency graph to remove cycles",
                    )
                )
                return

            if task_id in self._task_registry:
                dep_task = self._task_registry[task_id]
                stack.extend(d.task_ref for d in dep_task.dependencies)

    def _validate_constraints(self, spec: AegisTaskSpec) -> list[ValidationIssue]:
        """Validate constraints are enforceable."""
        issues = []

        for constraint in spec.constraints:
            # Check constraint has required values
            if constraint.constraint_type == ConstraintType.TIME_LIMIT:
                if not isinstance(constraint.value, (int, float)):
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            field=f"constraints[{constraint.constraint_id}]",
                            message="Time limit constraint requires numeric value",
                            suggestion="Provide time limit in seconds",
                        )
                    )
                elif constraint.value <= 0:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            field=f"constraints[{constraint.constraint_id}]",
                            message="Time limit must be positive",
                            suggestion="Set time limit to a value greater than 0",
                        )
                    )

            if constraint.constraint_type == ConstraintType.CONSTITUTIONAL:
                if not constraint.prd_reference:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            field=f"constraints[{constraint.constraint_id}]",
                            message="Constitutional constraint should have PRD reference",
                            suggestion="Add prd_reference field (e.g., 'FR-GOV-12')",
                        )
                    )

        return issues

    def _validate_outputs(self, spec: AegisTaskSpec) -> list[ValidationIssue]:
        """Validate expected outputs are defined properly."""
        issues = []

        required_outputs = [o for o in spec.expected_outputs if o.required]
        if len(required_outputs) == 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field="expected_outputs",
                    message="No required outputs defined",
                    suggestion="Consider marking at least one output as required",
                )
            )

        for output in spec.expected_outputs:
            if not output.name:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field=f"expected_outputs[{output.output_id}]",
                        message="Output name is required",
                        suggestion="Provide a name for this output",
                    )
                )

        return issues

    def _validate_measurement_points(
        self, spec: AegisTaskSpec
    ) -> list[ValidationIssue]:
        """Validate measurement points reference valid criteria."""
        issues = []

        criterion_ids = {c.criterion_id for c in spec.success_criteria}

        for point in spec.measurement_points:
            for criteria_ref in point.criteria_refs:
                if criteria_ref not in criterion_ids:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            field=f"measurement_points[{point.point_id}].criteria_refs",
                            message=f"Criterion {criteria_ref} not found in success_criteria",
                            suggestion="Ensure criteria_refs reference valid criterion IDs",
                        )
                    )

        return issues

    def _validate_intent_summary(self, spec: AegisTaskSpec) -> list[ValidationIssue]:
        """Validate intent summary doesn't contain execution details.

        Per Government PRD FR-GOV-6: Intent is WHAT, not HOW.
        """
        issues = []

        # Check for execution-detail patterns (similar to conclave service)
        execution_patterns = [
            ("step 1", "task list"),
            ("step 2", "task list"),
            ("first, ", "task list"),
            ("timeline:", "timeline"),
            ("schedule:", "timeline"),
            ("using ", "tool specification"),
            ("implement with", "tool specification"),
            ("allocate ", "resource allocation"),
            ("budget:", "resource allocation"),
        ]

        summary_lower = spec.intent_summary.lower()
        for pattern, category in execution_patterns:
            if pattern in summary_lower:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        field="intent_summary",
                        message=f"Intent summary may contain execution details ({category})",
                        suggestion="Intent should describe WHAT, not HOW. Review for execution details.",
                    )
                )
                break  # One warning is enough

        # Check summary length
        if len(spec.intent_summary) > 500:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field="intent_summary",
                    message="Intent summary exceeds recommended length (500 chars)",
                    suggestion="Keep intent summary concise and focused on WHAT",
                )
            )

        return issues


def create_task_spec_validator(
    task_registry: dict[UUID, AegisTaskSpec] | None = None,
    verbose: bool = False,
) -> TaskSpecValidator:
    """Factory function to create a TaskSpecValidator.

    Args:
        task_registry: Optional registry for dependency resolution
        verbose: Enable verbose logging

    Returns:
        Configured TaskSpecValidator
    """
    return TaskSpecValidator(task_registry=task_registry, verbose=verbose)
