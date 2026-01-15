"""Port definition for Execution Planner operations.

This port defines the interface for LLM-powered motion-to-task decomposition.
The Execution Planner classifies ratified motions into implementation patterns
and instantiates concrete tasks from templates.

Operations:
1. Classify a motion into implementation patterns
2. Instantiate tasks from pattern templates
3. Identify blockers and prerequisites
4. Generate execution plans

Constitutional Compliance:
- CT-11: All planning operations must be logged, failures reported
- CT-12: All plans must be traceable to source motions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MotionForPlanning:
    """A ratified motion to be transformed into an execution plan."""

    motion_id: str
    motion_title: str
    motion_text: str
    ratified_at: str
    yeas: int
    nays: int
    abstentions: int
    source_archons: list[str] = field(default_factory=list)
    theme: str = ""


@dataclass
class ClassificationResult:
    """Result of classifying a motion into patterns."""

    motion_id: str
    primary_pattern_id: str
    primary_pattern_name: str
    secondary_pattern_ids: list[str]
    confidence: float
    reasoning: str
    matched_keywords: list[str]


@dataclass
class TaskInstantiation:
    """A task instantiated from a template."""

    task_type: str
    description: str
    assignable: bool
    estimated_effort: str
    context_notes: str  # Motion-specific context for this task


@dataclass
class BlockerDetection:
    """A detected blocker for a motion."""

    blocker_type: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    escalate_to_conclave: bool
    suggested_agenda_item: str | None
    resolution_hint: str | None


@dataclass
class PlanningResult:
    """Complete result of planning execution for a motion."""

    motion_id: str
    motion_title: str
    classification: ClassificationResult
    tasks: list[TaskInstantiation]
    blockers: list[BlockerDetection]
    expected_outputs: list[str]
    planning_notes: str
    planning_duration_ms: int = 0


class ExecutionPlannerProtocol(ABC):
    """Port for Execution Planner operations using LLM enhancement.

    This protocol defines the interface for LLM-powered motion planning.
    Implementations handle the actual CrewAI or LLM invocation details.

    The Execution Planner transforms legislative decisions (ratified motions)
    into operational plans (tasks, dependencies, blockers).
    """

    @abstractmethod
    async def classify_motion(
        self,
        motion: MotionForPlanning,
        available_patterns: list[dict],
    ) -> ClassificationResult:
        """Classify a motion into implementation patterns.

        Analyzes the motion text and metadata to determine which
        implementation patterns best fit the motion's intent.

        Args:
            motion: The ratified motion to classify
            available_patterns: List of pattern definitions from taxonomy

        Returns:
            ClassificationResult with primary and secondary patterns

        Raises:
            ClassificationError: If classification fails
        """
        ...

    @abstractmethod
    async def instantiate_tasks(
        self,
        motion: MotionForPlanning,
        pattern_id: str,
        task_templates: list[dict],
    ) -> list[TaskInstantiation]:
        """Instantiate concrete tasks from pattern templates.

        Takes generic task templates and creates motion-specific
        task descriptions with appropriate context.

        Args:
            motion: The motion being planned
            pattern_id: The pattern being instantiated
            task_templates: Task templates from the pattern

        Returns:
            List of instantiated tasks with motion-specific details

        Raises:
            InstantiationError: If task instantiation fails
        """
        ...

    @abstractmethod
    async def detect_blockers(
        self,
        motion: MotionForPlanning,
        classification: ClassificationResult,
        available_patterns: list[dict],
    ) -> list[BlockerDetection]:
        """Detect potential blockers for motion execution.

        Analyzes the motion and its classification to identify
        impediments that may require resolution or escalation.

        Args:
            motion: The motion being analyzed
            classification: The motion's pattern classification
            available_patterns: Pattern definitions with prerequisites

        Returns:
            List of detected blockers with escalation recommendations

        Raises:
            BlockerDetectionError: If detection fails
        """
        ...

    @abstractmethod
    async def plan_motion_execution(
        self,
        motion: MotionForPlanning,
        available_patterns: list[dict],
    ) -> PlanningResult:
        """Generate complete execution plan for a motion.

        Combines classification, task instantiation, and blocker
        detection into a comprehensive execution plan.

        Args:
            motion: The ratified motion to plan
            available_patterns: Pattern definitions from taxonomy

        Returns:
            Complete PlanningResult with tasks and blockers

        Raises:
            PlanningError: If planning fails
        """
        ...

    @abstractmethod
    async def batch_plan_motions(
        self,
        motions: list[MotionForPlanning],
        available_patterns: list[dict],
    ) -> list[PlanningResult]:
        """Generate execution plans for multiple motions.

        Batch processing for efficiency when planning many motions.

        Args:
            motions: List of ratified motions to plan
            available_patterns: Pattern definitions from taxonomy

        Returns:
            List of PlanningResults, one per motion

        Raises:
            PlanningError: If any planning fails
        """
        ...


class ExecutionPlannerError(Exception):
    """Base exception for Execution Planner operations."""

    pass


class ClassificationError(ExecutionPlannerError):
    """Error during motion classification."""

    pass


class InstantiationError(ExecutionPlannerError):
    """Error during task instantiation."""

    pass


class BlockerDetectionError(ExecutionPlannerError):
    """Error during blocker detection."""

    pass


class PlanningError(ExecutionPlannerError):
    """Error during execution planning."""

    pass
