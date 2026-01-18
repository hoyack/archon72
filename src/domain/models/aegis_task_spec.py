"""AegisTaskSpec Domain Models.

This module defines the formal contract between:
- President Service (producer): Creates task specifications from ratified motions
- Aegis Network (consumer): Executes tasks according to specifications
- Prince Service (evaluator): Measures outcomes against success criteria

Per Government PRD FR-GOV-9: President produces execution specifications.
Per Government PRD AR-6: Integration with Aegis Network for task execution.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class TaskStatus(Enum):
    """Status of a task in the execution lifecycle."""

    DRAFT = "draft"  # Being created
    PENDING = "pending"  # Awaiting execution
    EXECUTING = "executing"  # Currently being executed
    COMPLETED = "completed"  # Execution finished
    JUDGED = "judged"  # Prince has evaluated


class MeasurementType(Enum):
    """Types of measurements for success criteria."""

    BOOLEAN = "boolean"  # Pass/fail
    NUMERIC = "numeric"  # Measurable value
    THRESHOLD = "threshold"  # Value must meet threshold
    COMPLETION = "completion"  # All sub-items complete


class ThresholdOperator(Enum):
    """Operators for threshold comparisons."""

    EQ = "eq"  # Equal to
    GT = "gt"  # Greater than
    GTE = "gte"  # Greater than or equal
    LT = "lt"  # Less than
    LTE = "lte"  # Less than or equal
    BETWEEN = "between"  # Between two values


class DependencyType(Enum):
    """Types of task dependencies."""

    BLOCKS = "blocks"  # Must complete before this task starts
    INFORMS = "informs"  # Output is input to this task
    PARALLEL = "parallel"  # Can run simultaneously but shares resources


class ConstraintType(Enum):
    """Types of task constraints."""

    TIME_LIMIT = "time_limit"  # Maximum execution time
    RESOURCE_LIMIT = "resource_limit"  # Maximum resource usage
    SCOPE_LIMIT = "scope_limit"  # What the task CANNOT do
    APPROVAL_GATE = "approval_gate"  # Requires approval to proceed
    CONSTITUTIONAL = "constitutional"  # Must adhere to constitutional constraint


class OutputType(Enum):
    """Types of expected task outputs."""

    FILE = "file"  # File artifact
    EVENT = "event"  # Event in event store
    STATE = "state"  # State change
    REPORT = "report"  # Human-readable report
    WITNESS = "witness"  # Witness statement


class MeasurementTrigger(Enum):
    """Triggers for measurement points."""

    START = "start"  # At task start
    CHECKPOINT = "checkpoint"  # At defined checkpoint
    COMPLETION = "completion"  # At task completion
    PERIODIC = "periodic"  # At regular intervals
    EVENT = "event"  # On specific event


class TaskPriority(Enum):
    """Task priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SuccessCriterion:
    """A measurable criterion for task success.

    Each criterion must be objectively evaluable by Prince.
    Immutable per Government PRD requirements.
    """

    criterion_id: UUID
    description: str
    measurement_type: MeasurementType
    target_value: Any | None = None
    threshold_operator: ThresholdOperator | None = None
    weight: float = 1.0

    @classmethod
    def create(
        cls,
        description: str,
        measurement_type: MeasurementType,
        target_value: Any | None = None,
        threshold_operator: ThresholdOperator | None = None,
        weight: float = 1.0,
    ) -> "SuccessCriterion":
        """Create a new success criterion.

        Args:
            description: What this criterion measures
            measurement_type: How to measure success
            target_value: Target value for numeric/threshold
            threshold_operator: Operator for threshold comparison
            weight: Weight in overall success calculation

        Returns:
            New immutable SuccessCriterion
        """
        return cls(
            criterion_id=uuid4(),
            description=description,
            measurement_type=measurement_type,
            target_value=target_value,
            threshold_operator=threshold_operator,
            weight=weight,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "criterion_id": str(self.criterion_id),
            "description": self.description,
            "measurement_type": self.measurement_type.value,
            "target_value": self.target_value,
            "threshold_operator": self.threshold_operator.value
            if self.threshold_operator
            else None,
            "weight": self.weight,
        }


@dataclass(frozen=True)
class Dependency:
    """A dependency on another task."""

    dependency_id: UUID
    dependency_type: DependencyType
    task_ref: UUID  # ID of the dependent task
    required: bool = True  # If true, failure of dependency fails this task

    @classmethod
    def create(
        cls,
        dependency_type: DependencyType,
        task_ref: UUID,
        required: bool = True,
    ) -> "Dependency":
        """Create a new dependency."""
        return cls(
            dependency_id=uuid4(),
            dependency_type=dependency_type,
            task_ref=task_ref,
            required=required,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "dependency_id": str(self.dependency_id),
            "dependency_type": self.dependency_type.value,
            "task_ref": str(self.task_ref),
            "required": self.required,
        }


@dataclass(frozen=True)
class Constraint:
    """A constraint on task execution."""

    constraint_id: UUID
    constraint_type: ConstraintType
    description: str
    value: Any | None = None
    prd_reference: str | None = None  # e.g., "FR-GOV-12"

    @classmethod
    def create(
        cls,
        constraint_type: ConstraintType,
        description: str,
        value: Any | None = None,
        prd_reference: str | None = None,
    ) -> "Constraint":
        """Create a new constraint."""
        return cls(
            constraint_id=uuid4(),
            constraint_type=constraint_type,
            description=description,
            value=value,
            prd_reference=prd_reference,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "constraint_id": str(self.constraint_id),
            "constraint_type": self.constraint_type.value,
            "description": self.description,
            "value": self.value,
            "prd_reference": self.prd_reference,
        }


@dataclass(frozen=True)
class ExpectedOutput:
    """An expected output from task execution."""

    output_id: UUID
    name: str
    output_type: OutputType
    description: str | None = None
    required: bool = True

    @classmethod
    def create(
        cls,
        name: str,
        output_type: OutputType,
        description: str | None = None,
        required: bool = True,
    ) -> "ExpectedOutput":
        """Create a new expected output."""
        return cls(
            output_id=uuid4(),
            name=name,
            output_type=output_type,
            description=description,
            required=required,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "output_id": str(self.output_id),
            "name": self.name,
            "output_type": self.output_type.value,
            "description": self.description,
            "required": self.required,
        }


@dataclass(frozen=True)
class MeasurementPoint:
    """A point during execution where progress can be measured.

    Used by Prince to evaluate partial compliance.
    """

    point_id: UUID
    name: str
    trigger: MeasurementTrigger
    criteria_refs: tuple[UUID, ...] = field(
        default_factory=tuple
    )  # Criteria to evaluate

    @classmethod
    def create(
        cls,
        name: str,
        trigger: MeasurementTrigger,
        criteria_refs: list[UUID] | None = None,
    ) -> "MeasurementPoint":
        """Create a new measurement point."""
        return cls(
            point_id=uuid4(),
            name=name,
            trigger=trigger,
            criteria_refs=tuple(criteria_refs or []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "point_id": str(self.point_id),
            "name": self.name,
            "trigger": self.trigger.value,
            "criteria_refs": [str(ref) for ref in self.criteria_refs],
        }


@dataclass(frozen=True)
class WitnessingRequirements:
    """Witnessing requirements for task execution."""

    require_witness_on_start: bool = True
    require_witness_on_complete: bool = True
    require_witness_on_failure: bool = True
    witness_checkpoints: tuple[UUID, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "require_witness_on_start": self.require_witness_on_start,
            "require_witness_on_complete": self.require_witness_on_complete,
            "require_witness_on_failure": self.require_witness_on_failure,
            "witness_checkpoints": [str(cp) for cp in self.witness_checkpoints],
        }


@dataclass(frozen=True)
class TaskMetadata:
    """Optional metadata for task specifications."""

    priority: TaskPriority = TaskPriority.NORMAL
    tags: tuple[str, ...] = field(default_factory=tuple)
    estimated_duration_seconds: int | None = None
    max_retries: int = 0
    assigned_executor: str | None = None  # Archon ID of assigned Duke/Earl

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "priority": self.priority.value,
            "tags": list(self.tags),
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "max_retries": self.max_retries,
            "assigned_executor": self.assigned_executor,
        }


@dataclass(frozen=True)
class AegisTaskSpec:
    """Formal task specification for Aegis Network execution.

    This is the contract between:
    - President Service (producer)
    - Aegis Network (consumer)
    - Prince Service (evaluator)

    Per Government PRD FR-GOV-9: President produces execution specifications.
    All instances are immutable (frozen).

    Attributes:
        task_id: Unique identifier for this task
        motion_ref: Reference to the ratified motion
        intent_summary: WHAT the task should accomplish (no HOW)
        success_criteria: Measurable criteria for success
        dependencies: Tasks that must complete first
        constraints: Boundaries for execution
        expected_outputs: Artifacts to produce
        measurement_points: Progress measurement points
        metadata: Optional task metadata
        witnessing: Witnessing requirements
        created_at: When this spec was created
        created_by: President who created it
        status: Current status
        session_ref: Optional session reference
    """

    task_id: UUID
    motion_ref: UUID
    intent_summary: str
    success_criteria: tuple[SuccessCriterion, ...]
    expected_outputs: tuple[ExpectedOutput, ...]
    created_at: datetime
    created_by: str  # Archon ID of President
    status: TaskStatus = TaskStatus.DRAFT
    session_ref: UUID | None = None
    dependencies: tuple[Dependency, ...] = field(default_factory=tuple)
    constraints: tuple[Constraint, ...] = field(default_factory=tuple)
    measurement_points: tuple[MeasurementPoint, ...] = field(default_factory=tuple)
    metadata: TaskMetadata | None = None
    witnessing: WitnessingRequirements | None = None

    @classmethod
    def create(
        cls,
        motion_ref: UUID,
        intent_summary: str,
        success_criteria: list[SuccessCriterion],
        expected_outputs: list[ExpectedOutput],
        created_by: str,
        session_ref: UUID | None = None,
        dependencies: list[Dependency] | None = None,
        constraints: list[Constraint] | None = None,
        measurement_points: list[MeasurementPoint] | None = None,
        metadata: TaskMetadata | None = None,
        witnessing: WitnessingRequirements | None = None,
    ) -> "AegisTaskSpec":
        """Create a new AegisTaskSpec.

        Args:
            motion_ref: Reference to ratified motion
            intent_summary: WHAT the task should accomplish
            success_criteria: Measurable criteria
            expected_outputs: Expected artifacts
            created_by: President's Archon ID
            session_ref: Optional session reference
            dependencies: Task dependencies
            constraints: Execution constraints
            measurement_points: Progress measurement points
            metadata: Optional metadata
            witnessing: Witnessing requirements

        Returns:
            New immutable AegisTaskSpec
        """
        return cls(
            task_id=uuid4(),
            motion_ref=motion_ref,
            intent_summary=intent_summary,
            success_criteria=tuple(success_criteria),
            expected_outputs=tuple(expected_outputs),
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            status=TaskStatus.DRAFT,
            session_ref=session_ref,
            dependencies=tuple(dependencies or []),
            constraints=tuple(constraints or []),
            measurement_points=tuple(measurement_points or []),
            metadata=metadata,
            witnessing=witnessing or WitnessingRequirements(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": str(self.task_id),
            "motion_ref": str(self.motion_ref),
            "session_ref": str(self.session_ref) if self.session_ref else None,
            "intent_summary": self.intent_summary,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "success_criteria": [c.to_dict() for c in self.success_criteria],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "constraints": [c.to_dict() for c in self.constraints],
            "expected_outputs": [o.to_dict() for o in self.expected_outputs],
            "measurement_points": [m.to_dict() for m in self.measurement_points],
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "witnessing": self.witnessing.to_dict() if self.witnessing else None,
        }

    @property
    def is_executable(self) -> bool:
        """Check if the spec can be executed."""
        return (
            self.status in (TaskStatus.DRAFT, TaskStatus.PENDING)
            and len(self.success_criteria) > 0
            and len(self.expected_outputs) > 0
        )

    @property
    def total_weight(self) -> float:
        """Calculate total weight of all success criteria."""
        return sum(c.weight for c in self.success_criteria)

    def get_criterion_by_id(self, criterion_id: UUID) -> SuccessCriterion | None:
        """Get a success criterion by ID."""
        for c in self.success_criteria:
            if c.criterion_id == criterion_id:
                return c
        return None
