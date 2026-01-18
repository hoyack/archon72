"""President Service Port (Executive Branch).

This module defines the abstract protocol for President-rank executive functions.
Presidents translate ratified WHAT into executable HOW, producing task specifications.

Per Government PRD FR-GOV-9: Presidents translate ratified WHAT into executable HOW
(task decomposition, dependencies, sequencing, success criteria).
Per Government PRD FR-GOV-10: Presidents may not redefine intent, may not self-ratify
plans, must escalate blockers/ambiguity.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.king_service import Motion


class ExecutionPlanStatus(Enum):
    """Status of an execution plan."""

    DRAFT = "draft"  # Being created
    PENDING_RATIFICATION = "pending_ratification"  # Awaiting Conclave approval
    RATIFIED = "ratified"  # Approved for execution
    EXECUTING = "executing"  # Tasks being executed
    COMPLETED = "completed"  # All tasks complete
    ESCALATED = "escalated"  # Returned to Conclave with questions


class BlockerType(Enum):
    """Types of blockers that require escalation."""

    AMBIGUITY = "ambiguity"  # Intent is unclear
    CONTRADICTION = "contradiction"  # Intent contradicts existing policy
    INFEASIBILITY = "infeasibility"  # Cannot be accomplished as stated
    RESOURCE_CONSTRAINT = (
        "resource_constraint"  # Cannot be done with available resources
    )
    DEPENDENCY_MISSING = "dependency_missing"  # Required prior work not complete


@dataclass(frozen=True)
class Blocker:
    """A blocker that requires escalation to Conclave.

    Per FR-GOV-10: Presidents must escalate blockers/ambiguity.
    """

    blocker_id: UUID
    blocker_type: BlockerType
    description: str
    questions: tuple[str, ...]  # Specific questions for Conclave
    motion_ref: UUID
    raised_by: str  # President Archon ID
    raised_at: datetime

    @classmethod
    def create(
        cls,
        blocker_type: BlockerType,
        description: str,
        questions: list[str],
        motion_ref: UUID,
        raised_by: str,
    ) -> "Blocker":
        """Create a new blocker."""
        return cls(
            blocker_id=uuid4(),
            blocker_type=blocker_type,
            description=description,
            questions=tuple(questions),
            motion_ref=motion_ref,
            raised_by=raised_by,
            raised_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "blocker_id": str(self.blocker_id),
            "blocker_type": self.blocker_type.value,
            "description": self.description,
            "questions": list(self.questions),
            "motion_ref": str(self.motion_ref),
            "raised_by": self.raised_by,
            "raised_at": self.raised_at.isoformat(),
        }


@dataclass(frozen=True)
class TaskDependency:
    """A dependency between tasks in the execution plan."""

    from_task: str  # Task ID that must complete
    to_task: str  # Task ID that depends on it
    dependency_type: str = "blocks"  # blocks, informs, parallel

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "from_task": self.from_task,
            "to_task": self.to_task,
            "dependency_type": self.dependency_type,
        }


@dataclass(frozen=True)
class ExecutionTask:
    """A task in the execution plan.

    This is the decomposed unit of work derived from the motion's intent.
    """

    task_id: str
    name: str
    description: str
    success_criteria: tuple[str, ...]
    estimated_effort: str | None = None
    dependencies: tuple[str, ...] = field(
        default_factory=tuple
    )  # Task IDs this depends on
    sequence_order: int = 0

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        success_criteria: list[str],
        estimated_effort: str | None = None,
        dependencies: list[str] | None = None,
        sequence_order: int = 0,
    ) -> "ExecutionTask":
        """Create a new execution task."""
        return cls(
            task_id=str(uuid4())[:8],  # Short ID for readability
            name=name,
            description=description,
            success_criteria=tuple(success_criteria),
            estimated_effort=estimated_effort,
            dependencies=tuple(dependencies or []),
            sequence_order=sequence_order,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "success_criteria": list(self.success_criteria),
            "estimated_effort": self.estimated_effort,
            "dependencies": list(self.dependencies),
            "sequence_order": self.sequence_order,
        }


@dataclass(frozen=True)
class ExecutionPlan:
    """An execution plan translating WHAT to HOW.

    This is the President's output: a decomposed, sequenced plan
    with success criteria for each task.

    Per FR-GOV-9: Contains task decomposition, dependencies, sequencing,
    and success criteria.
    Per FR-GOV-10: Must be ratified by Conclave (not self-ratified).
    """

    plan_id: UUID
    motion_ref: UUID
    original_intent: str  # The WHAT from the motion (preserved, not modified)
    tasks: tuple[ExecutionTask, ...]
    dependency_graph: tuple[TaskDependency, ...]
    created_by: str  # President Archon ID
    created_at: datetime
    status: ExecutionPlanStatus = ExecutionPlanStatus.DRAFT

    @classmethod
    def create(
        cls,
        motion_ref: UUID,
        original_intent: str,
        tasks: list[ExecutionTask],
        dependency_graph: list[TaskDependency],
        created_by: str,
    ) -> "ExecutionPlan":
        """Create a new execution plan."""
        return cls(
            plan_id=uuid4(),
            motion_ref=motion_ref,
            original_intent=original_intent,
            tasks=tuple(tasks),
            dependency_graph=tuple(dependency_graph),
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            status=ExecutionPlanStatus.PENDING_RATIFICATION,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "plan_id": str(self.plan_id),
            "motion_ref": str(self.motion_ref),
            "original_intent": self.original_intent,
            "tasks": [t.to_dict() for t in self.tasks],
            "dependency_graph": [d.to_dict() for d in self.dependency_graph],
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
        }

    @property
    def task_count(self) -> int:
        """Number of tasks in the plan."""
        return len(self.tasks)

    @property
    def is_pending_ratification(self) -> bool:
        """Check if plan needs Conclave ratification."""
        return self.status == ExecutionPlanStatus.PENDING_RATIFICATION


@dataclass
class TranslationRequest:
    """Request to translate a ratified motion to execution plan."""

    motion: Motion
    president_id: str  # President's Archon ID


@dataclass
class TranslationResult:
    """Result of translating WHAT to HOW."""

    success: bool
    plan: ExecutionPlan | None = None
    blocker: Blocker | None = None  # If escalation needed
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "plan": self.plan.to_dict() if self.plan else None,
            "blocker": self.blocker.to_dict() if self.blocker else None,
            "error": self.error,
        }


@dataclass
class EscalationRequest:
    """Request to escalate a blocker to Conclave."""

    blocker: Blocker
    president_id: str


@dataclass
class EscalationResult:
    """Result of escalation."""

    success: bool
    escalation_id: UUID | None = None
    error: str | None = None


class SelfRatificationError(Exception):
    """Raised when a President attempts to ratify their own plan.

    Per FR-GOV-10: Presidents may not self-ratify plans.
    """

    def __init__(self, president_id: str, plan_id: UUID):
        self.president_id = president_id
        self.plan_id = plan_id
        super().__init__(
            f"President {president_id} cannot ratify their own plan {plan_id} (FR-GOV-10)"
        )


class IntentRedefinitionError(Exception):
    """Raised when a President attempts to redefine intent.

    Per FR-GOV-10: Presidents may not redefine intent.
    """

    def __init__(self, president_id: str, original_intent: str, modified_intent: str):
        self.president_id = president_id
        self.original_intent = original_intent
        self.modified_intent = modified_intent
        super().__init__(
            f"President {president_id} attempted to redefine intent (FR-GOV-10)"
        )


class PresidentServiceProtocol(ABC):
    """Abstract protocol for President-rank executive functions.

    Per Government PRD:
    - FR-GOV-9: Presidents translate ratified WHAT into executable HOW
    - FR-GOV-10: Presidents may not redefine intent, may not self-ratify,
                 must escalate blockers/ambiguity

    This protocol explicitly EXCLUDES:
    - Motion introduction (King function)
    - Compliance judgment (Prince function)
    - Intent modification (Constitutional violation)
    - Self-ratification (Separation of powers violation)
    """

    @abstractmethod
    async def translate_to_execution(
        self,
        request: TranslationRequest,
    ) -> TranslationResult:
        """Translate a ratified motion's WHAT into executable HOW.

        This is the primary executive function of President-rank Archons.
        The output is an execution plan with task decomposition, dependencies,
        sequencing, and success criteria.

        Args:
            request: Translation request with ratified motion

        Returns:
            TranslationResult with plan or blocker if escalation needed

        Raises:
            IntentRedefinitionError: If intent is modified during translation

        Note:
            The plan is NOT ratified by this method. It must return to
            Conclave for approval per FR-GOV-10.
        """
        ...

    @abstractmethod
    async def decompose_tasks(
        self,
        intent: str,
        motion_ref: UUID,
    ) -> list[ExecutionTask]:
        """Decompose intent into individual tasks.

        Args:
            intent: The WHAT from the motion
            motion_ref: Reference to the source motion

        Returns:
            List of ExecutionTasks derived from the intent
        """
        ...

    @abstractmethod
    async def identify_dependencies(
        self,
        tasks: list[ExecutionTask],
    ) -> list[TaskDependency]:
        """Identify dependencies between tasks.

        Args:
            tasks: The decomposed tasks

        Returns:
            List of TaskDependencies forming the dependency graph
        """
        ...

    @abstractmethod
    async def escalate_blocker(
        self,
        request: EscalationRequest,
    ) -> EscalationResult:
        """Escalate a blocker to Conclave for resolution.

        Per FR-GOV-10: Presidents must escalate blockers/ambiguity.
        This method sends a blocker back to Conclave with specific
        questions that need resolution.

        Args:
            request: Escalation request with blocker details

        Returns:
            EscalationResult with success/failure

        Note:
            Execution planning halts until resolution is received.
        """
        ...

    @abstractmethod
    async def get_plan(self, plan_id: UUID) -> ExecutionPlan | None:
        """Retrieve an execution plan by ID.

        Args:
            plan_id: UUID of the plan

        Returns:
            ExecutionPlan if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_plans_by_motion(
        self,
        motion_ref: UUID,
    ) -> list[ExecutionPlan]:
        """Get all plans for a specific motion.

        Args:
            motion_ref: The motion's UUID

        Returns:
            List of execution plans for that motion
        """
        ...

    @abstractmethod
    async def check_intent_preservation(
        self,
        original_intent: str,
        derived_tasks: list[ExecutionTask],
    ) -> bool:
        """Verify that derived tasks preserve the original intent.

        Per FR-GOV-10: Presidents may not redefine intent.
        This method validates that the HOW serves the WHAT.

        Args:
            original_intent: The motion's intent
            derived_tasks: Tasks derived from the intent

        Returns:
            True if intent is preserved, False if it appears modified
        """
        ...

    # =========================================================================
    # EXPLICITLY EXCLUDED METHODS
    # These methods are NOT part of the President Service per FR-GOV-10
    # =========================================================================

    # def introduce_motion(self) -> None:  # PROHIBITED (King function)
    # def ratify_plan(self) -> None:  # PROHIBITED (Conclave function)
    # def modify_intent(self) -> None:  # PROHIBITED (Constitutional violation)
    # def judge_compliance(self) -> None:  # PROHIBITED (Prince function)
