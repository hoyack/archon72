"""Domain models for the Execution Planner.

The Execution Planner transforms ratified motions into actionable execution plans
by classifying motions into implementation patterns and instantiating task templates.

Key Concepts:
- Pattern: A category of implementation (CONST, POLICY, TECH, etc.)
- Task: A concrete action derived from a task template
- Blocker: An impediment that may require Conclave escalation
- ExecutionPlan: The complete plan for implementing a ratified motion
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PatternDomain(Enum):
    """Domain categories for implementation patterns."""

    GOVERNANCE = "governance"
    IMPLEMENTATION = "implementation"
    OPERATIONS = "operations"
    KNOWLEDGE = "knowledge"


class TaskStatus(Enum):
    """Status of an execution task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EffortEstimate(Enum):
    """Effort estimate for tasks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BlockerType(Enum):
    """Types of blockers that can impede execution."""

    MISSING_PREREQUISITE = "missing_prerequisite"
    UNDEFINED_SCOPE = "undefined_scope"
    RESOURCE_GAP = "resource_gap"
    POLICY_CONFLICT = "policy_conflict"
    TECHNICAL_INFEASIBILITY = "technical_infeasibility"
    STAKEHOLDER_CONFLICT = "stakeholder_conflict"


class EscalationType(Enum):
    """How a blocker should be escalated."""

    AUTO = "auto"  # Automatically resolve (e.g., queue prerequisite)
    CONCLAVE = "conclave"  # Requires Conclave deliberation
    MANUAL = "manual"  # Requires human intervention


@dataclass
class TaskTemplate:
    """Template for a task within a pattern."""

    task_type: str
    description: str
    assignable: bool
    estimated_effort: EffortEstimate = EffortEstimate.MEDIUM

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskTemplate:
        """Create from dictionary (YAML parsing)."""
        return cls(
            task_type=data["type"],
            description=data["description"],
            assignable=data.get("assignable", True),
            estimated_effort=EffortEstimate(data.get("estimated_effort", "medium")),
        )


@dataclass
class ImplementationPattern:
    """An implementation pattern from the taxonomy."""

    pattern_id: str
    name: str
    description: str
    domain: PatternDomain
    task_templates: list[TaskTemplate]
    outputs: list[str]
    prerequisites: list[str]
    typical_blockers: list[str]

    @classmethod
    def from_dict(cls, pattern_id: str, data: dict[str, Any]) -> ImplementationPattern:
        """Create from dictionary (YAML parsing)."""
        return cls(
            pattern_id=data["id"],
            name=data["name"],
            description=data["description"],
            domain=PatternDomain(data["domain"]),
            task_templates=[
                TaskTemplate.from_dict(t) for t in data.get("task_templates", [])
            ],
            outputs=data.get("outputs", []),
            prerequisites=data.get("prerequisites", []),
            typical_blockers=data.get("typical_blockers", []),
        )


@dataclass
class ExecutionTask:
    """A concrete task instantiated from a template."""

    task_id: str
    task_type: str
    description: str
    pattern_id: str
    motion_id: str
    status: TaskStatus = TaskStatus.PENDING
    assignable: bool = True
    estimated_effort: EffortEstimate = EffortEstimate.MEDIUM
    dependencies: list[str] = field(default_factory=list)  # task_ids
    assigned_to: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "pattern_id": self.pattern_id,
            "motion_id": self.motion_id,
            "status": self.status.value,
            "assignable": self.assignable,
            "estimated_effort": self.estimated_effort.value,
            "dependencies": self.dependencies,
            "assigned_to": self.assigned_to,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "notes": self.notes,
        }


@dataclass
class Blocker:
    """An impediment to execution that may require escalation."""

    blocker_id: str
    motion_id: str
    blocker_type: BlockerType
    description: str
    escalation_type: EscalationType
    escalate_to_conclave: bool
    suggested_agenda_item: str | None = None
    related_task_id: str | None = None
    resolved: bool = False
    resolution_notes: str | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "blocker_id": self.blocker_id,
            "motion_id": self.motion_id,
            "blocker_type": self.blocker_type.value,
            "description": self.description,
            "escalation_type": self.escalation_type.value,
            "escalate_to_conclave": self.escalate_to_conclave,
            "suggested_agenda_item": self.suggested_agenda_item,
            "related_task_id": self.related_task_id,
            "resolved": self.resolved,
            "resolution_notes": self.resolution_notes,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class PatternClassification:
    """Result of classifying a motion into patterns."""

    motion_id: str
    motion_title: str
    primary_pattern: str  # pattern_id
    secondary_patterns: list[str] = field(default_factory=list)
    classification_confidence: float = 0.0
    classification_reasoning: str = ""
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "motion_id": self.motion_id,
            "motion_title": self.motion_title,
            "primary_pattern": self.primary_pattern,
            "secondary_patterns": self.secondary_patterns,
            "classification_confidence": self.classification_confidence,
            "classification_reasoning": self.classification_reasoning,
            "matched_keywords": self.matched_keywords,
        }


@dataclass
class ExecutionPhase:
    """A phase of execution containing related tasks."""

    phase_id: str
    phase_number: int
    pattern_id: str
    pattern_name: str
    tasks: list[ExecutionTask]
    phase_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase_id": self.phase_id,
            "phase_number": self.phase_number,
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "tasks": [t.to_dict() for t in self.tasks],
            "phase_description": self.phase_description,
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan for a ratified motion."""

    plan_id: str
    motion_id: str
    motion_title: str
    motion_text: str
    classification: PatternClassification
    phases: list[ExecutionPhase]
    blockers: list[Blocker]
    expected_outputs: list[str]
    total_tasks: int = 0
    assignable_tasks: int = 0
    estimated_total_effort: str = ""  # "low", "medium", "high", "very_high"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "draft"  # "draft", "approved", "in_progress", "completed", "blocked"

    def __post_init__(self):
        """Calculate derived fields."""
        self.total_tasks = sum(len(phase.tasks) for phase in self.phases)
        self.assignable_tasks = sum(
            1 for phase in self.phases for task in phase.tasks if task.assignable
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "plan_id": self.plan_id,
            "motion_id": self.motion_id,
            "motion_title": self.motion_title,
            "motion_text": self.motion_text,
            "classification": self.classification.to_dict(),
            "phases": [p.to_dict() for p in self.phases],
            "blockers": [b.to_dict() for b in self.blockers],
            "expected_outputs": self.expected_outputs,
            "total_tasks": self.total_tasks,
            "assignable_tasks": self.assignable_tasks,
            "estimated_total_effort": self.estimated_total_effort,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }


@dataclass
class ExecutionPlannerResult:
    """Result of running the Execution Planner on multiple motions."""

    session_id: str
    session_name: str
    plans: list[ExecutionPlan]
    total_motions_processed: int
    total_tasks_generated: int
    total_blockers_identified: int
    blockers_requiring_conclave: int
    patterns_used: dict[str, int]  # pattern_id -> count
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "plans": [p.to_dict() for p in self.plans],
            "total_motions_processed": self.total_motions_processed,
            "total_tasks_generated": self.total_tasks_generated,
            "total_blockers_identified": self.total_blockers_identified,
            "blockers_requiring_conclave": self.blockers_requiring_conclave,
            "patterns_used": self.patterns_used,
            "created_at": self.created_at.isoformat(),
        }
