"""Domain models for Execution Program lifecycle.

Execution Programs transform Executive execution plans into coordinated
work containers, routing tasks through Dukes and Earls with consent-based
activation and reality-visible status tracking.

Principle: "Administration exists to make reality visible, not obedient."

Constitutional truths honored:
- T6: No substitution (same-cluster retry only)
- T7: Programs are descriptive, not prescriptive (status tracking, not enforcement)
- T8: Halting is not failure (HALTED is valid terminal state)
- T9: Smooth running is suspicious (honest completion, no gaming incentive)
- T10: Capacity is first-class fact (confidence tracking + attestation)

Schema Versions:
- 2.0: Initial version aligned with Executive v2 artifacts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# =============================================================================
# Schema Version & Constants
# =============================================================================

EXECUTION_PROGRAM_SCHEMA_VERSION = "2.0"

DUKE_MAX_CONCURRENT_PROGRAMS = 5
MAX_SAME_CLUSTER_RETRIES = 2
MAX_EXTENSIONS = 2
TASK_MAX_LIFETIME_DAYS = 30
HIGH_VELOCITY_THRESHOLD = 10


# =============================================================================
# Enums
# =============================================================================


class TaskLifecycleStatus(str, Enum):
    """Descriptive status tracking for task lifecycle.

    Per T7: tracks what IS, not what MUST BE. Unusual transitions
    emit warning events but are NOT blocked.
    """

    PENDING = "PENDING"
    ACTIVATED = "ACTIVATED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WITHDRAWN = "WITHDRAWN"
    TIMED_OUT = "TIMED_OUT"


class BlockerType(str, Enum):
    """Classification of administrative blocker types."""

    REQUIREMENTS_AMBIGUOUS = "REQUIREMENTS_AMBIGUOUS"
    CAPACITY_UNAVAILABLE = "CAPACITY_UNAVAILABLE"
    CONSTRAINT_CONFLICT = "CONSTRAINT_CONFLICT"
    RESOURCE_MISSING = "RESOURCE_MISSING"


class AdminBlockerSeverity(str, Enum):
    """Severity of administrative blockers.

    Named AdminBlockerSeverity to avoid collision with
    executive_planning.BlockerSeverity.
    """

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class RequestedAction(str, Enum):
    """Action requested from Executive in blocker report."""

    CLARIFY = "CLARIFY"
    REVISE_PLAN = "REVISE_PLAN"
    REDUCE_SCOPE = "REDUCE_SCOPE"
    DEFER = "DEFER"


class ProgramCompletionStatus(str, Enum):
    """Terminal states for program completion.

    Per T8/T9: all terminal states are valid. No gates block completion.
    The STATUS is the truth - Executive reads and decides.
    """

    COMPLETED_CLEAN = "COMPLETED_CLEAN"
    COMPLETED_WITH_ACCEPTED_RISKS = "COMPLETED_WITH_ACCEPTED_RISKS"
    COMPLETED_WITH_UNRESOLVED = "COMPLETED_WITH_UNRESOLVED"
    FAILED = "FAILED"
    HALTED = "HALTED"


class ResultType(str, Enum):
    """Classification of task result artifacts."""

    DRAFT_PRODUCED = "DRAFT_PRODUCED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    AUTOMATED_VERIFIED = "AUTOMATED_VERIFIED"


class ActionReversibility(str, Enum):
    """Determines verification requirements based on consequence, not origin."""

    REVERSIBLE = "REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    PARTIALLY_REVERSIBLE = "PARTIALLY_REVERSIBLE"


class CapacityConfidence(str, Enum):
    """Confidence level for capacity snapshots based on freshness."""

    HIGH = "HIGH"  # Snapshot < 1 hour old
    MEDIUM = "MEDIUM"  # Snapshot 1-4 hours old
    LOW = "LOW"  # Snapshot > 4 hours old


class ClarificationType(str, Enum):
    """Type of clarification requested in blocker reports."""

    AMBIGUITY_RESOLUTION = "AMBIGUITY_RESOLUTION"
    CONSTRAINT_INTERPRETATION = "CONSTRAINT_INTERPRETATION"
    DEPENDENCY_QUESTION = "DEPENDENCY_QUESTION"


class AdminBlockerDisposition(str, Enum):
    """Disposition of administrative blockers.

    Named AdminBlockerDisposition to avoid collision with
    executive_planning.BlockerDisposition.
    """

    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    ESCALATED = "ESCALATED"


class ProgramStage(str, Enum):
    """Current stage in the Execution Program lifecycle."""

    INTAKE = "INTAKE"
    FEASIBILITY = "FEASIBILITY"
    COMMIT = "COMMIT"
    ACTIVATION = "ACTIVATION"
    RESULTS = "RESULTS"
    VIOLATION_HANDLING = "VIOLATION_HANDLING"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class DukeAssignment:
    """Role binding of an Archon as Duke (coordinator) for a program.

    Dukes are existing Archon profiles bound to a coordinator role.
    The same Archon pool is used across all branches.
    """

    archon_id: str
    duke_name: str
    duke_title: str
    program_id: str
    assigned_at: str  # ISO8601
    current_programs: int = 0
    max_programs: int = DUKE_MAX_CONCURRENT_PROGRAMS

    def to_dict(self) -> dict[str, Any]:
        return {
            "archon_id": self.archon_id,
            "duke_name": self.duke_name,
            "duke_title": self.duke_title,
            "program_id": self.program_id,
            "assigned_at": self.assigned_at,
            "current_programs": self.current_programs,
            "max_programs": self.max_programs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DukeAssignment:
        return cls(
            archon_id=data["archon_id"],
            duke_name=data["duke_name"],
            duke_title=data["duke_title"],
            program_id=data["program_id"],
            assigned_at=data["assigned_at"],
            current_programs=data.get("current_programs", 0),
            max_programs=data.get("max_programs", DUKE_MAX_CONCURRENT_PROGRAMS),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.archon_id:
            errors.append("DukeAssignment missing required field: archon_id")
        if not self.program_id:
            errors.append("DukeAssignment missing required field: program_id")
        if self.current_programs > self.max_programs:
            errors.append(
                f"DukeAssignment overloaded: current_programs ({self.current_programs}) "
                f"exceeds max_programs ({self.max_programs})"
            )
        return errors


@dataclass
class EarlAssignment:
    """Role binding of an Archon as Earl (task router) for a program."""

    archon_id: str
    earl_name: str
    task_ids: list[str] = field(default_factory=list)
    assigned_at: str = ""  # ISO8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "archon_id": self.archon_id,
            "earl_name": self.earl_name,
            "task_ids": self.task_ids,
            "assigned_at": self.assigned_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EarlAssignment:
        return cls(
            archon_id=data["archon_id"],
            earl_name=data["earl_name"],
            task_ids=data.get("task_ids", []),
            assigned_at=data.get("assigned_at", ""),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.archon_id:
            errors.append("EarlAssignment missing required field: archon_id")
        if not self.earl_name:
            errors.append("EarlAssignment missing required field: earl_name")
        return errors


@dataclass
class CapacitySnapshot:
    """Point-in-time capacity assessment for a program."""

    snapshot_id: str
    program_id: str
    timestamp: str  # ISO8601
    total_tasks: int = 0
    eligible_clusters: int = 0
    declared_capacity: int = 0
    confidence: CapacityConfidence = CapacityConfidence.HIGH
    acceptance_rate: float = 1.0  # 0.0 - 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "program_id": self.program_id,
            "timestamp": self.timestamp,
            "total_tasks": self.total_tasks,
            "eligible_clusters": self.eligible_clusters,
            "declared_capacity": self.declared_capacity,
            "confidence": self.confidence.value,
            "acceptance_rate": self.acceptance_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapacitySnapshot:
        return cls(
            snapshot_id=data["snapshot_id"],
            program_id=data["program_id"],
            timestamp=data["timestamp"],
            total_tasks=data.get("total_tasks", 0),
            eligible_clusters=data.get("eligible_clusters", 0),
            declared_capacity=data.get("declared_capacity", 0),
            confidence=CapacityConfidence(data.get("confidence", "HIGH")),
            acceptance_rate=data.get("acceptance_rate", 1.0),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.snapshot_id:
            errors.append("CapacitySnapshot missing required field: snapshot_id")
        if not self.program_id:
            errors.append("CapacitySnapshot missing required field: program_id")
        if not 0.0 <= self.acceptance_rate <= 1.0:
            errors.append(
                f"CapacitySnapshot acceptance_rate out of range: {self.acceptance_rate}"
            )
        return errors


@dataclass
class TaskActivationRequest:
    """Request to activate a task for execution.

    One TaskActivationRequest per WorkPackage from Executive.
    Per T6: same-cluster retry only, no substitution.
    """

    request_id: str
    task_id: str
    program_id: str
    earl_archon_id: str
    scope_description: str
    constraints: list[str] = field(default_factory=list)
    success_definition: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    action_reversibility: ActionReversibility = ActionReversibility.REVERSIBLE
    activation_deadline: str = ""  # ISO8601
    max_deadline: str = ""  # ISO8601
    target_cluster_id: str | None = None
    retry_count: int = 0
    original_request_id: str | None = None  # For retry lineage

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "program_id": self.program_id,
            "earl_archon_id": self.earl_archon_id,
            "scope_description": self.scope_description,
            "constraints": self.constraints,
            "success_definition": self.success_definition,
            "required_capabilities": self.required_capabilities,
            "action_reversibility": self.action_reversibility.value,
            "activation_deadline": self.activation_deadline,
            "max_deadline": self.max_deadline,
            "target_cluster_id": self.target_cluster_id,
            "retry_count": self.retry_count,
            "original_request_id": self.original_request_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskActivationRequest:
        return cls(
            request_id=data["request_id"],
            task_id=data["task_id"],
            program_id=data["program_id"],
            earl_archon_id=data["earl_archon_id"],
            scope_description=data["scope_description"],
            constraints=data.get("constraints", []),
            success_definition=data.get("success_definition", ""),
            required_capabilities=data.get("required_capabilities", []),
            action_reversibility=ActionReversibility(
                data.get("action_reversibility", "REVERSIBLE")
            ),
            activation_deadline=data.get("activation_deadline", ""),
            max_deadline=data.get("max_deadline", ""),
            target_cluster_id=data.get("target_cluster_id"),
            retry_count=data.get("retry_count", 0),
            original_request_id=data.get("original_request_id"),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.request_id:
            errors.append("TaskActivationRequest missing required field: request_id")
        if not self.task_id:
            errors.append("TaskActivationRequest missing required field: task_id")
        if not self.scope_description:
            errors.append(
                "TaskActivationRequest missing required field: scope_description"
            )
        if (
            self.activation_deadline
            and self.max_deadline
            and self.activation_deadline > self.max_deadline
        ):
            errors.append(
                "TaskActivationRequest activation_deadline exceeds max_deadline"
            )
        return errors


@dataclass
class TaskResultArtifact:
    """Result artifact from task execution.

    Verification is based on action_reversibility, not cluster type.
    """

    result_id: str
    task_id: str
    request_id: str
    result_type: ResultType
    action_reversibility: ActionReversibility
    deliverable_ref: str = ""
    summary: str = ""
    submitted_at: str = ""  # ISO8601
    verifier_id: str | None = None
    verification_notes: str = ""

    @property
    def requires_verification(self) -> bool:
        """Verification need is based on consequence, not origin."""
        if self.action_reversibility == ActionReversibility.IRREVERSIBLE:
            return True
        if self.action_reversibility == ActionReversibility.PARTIALLY_REVERSIBLE:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "result_type": self.result_type.value,
            "action_reversibility": self.action_reversibility.value,
            "deliverable_ref": self.deliverable_ref,
            "summary": self.summary,
            "submitted_at": self.submitted_at,
            "verifier_id": self.verifier_id,
            "verification_notes": self.verification_notes,
            "requires_verification": self.requires_verification,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskResultArtifact:
        return cls(
            result_id=data["result_id"],
            task_id=data["task_id"],
            request_id=data["request_id"],
            result_type=ResultType(data["result_type"]),
            action_reversibility=ActionReversibility(
                data.get("action_reversibility", "REVERSIBLE")
            ),
            deliverable_ref=data.get("deliverable_ref", ""),
            summary=data.get("summary", ""),
            submitted_at=data.get("submitted_at", ""),
            verifier_id=data.get("verifier_id"),
            verification_notes=data.get("verification_notes", ""),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.result_id:
            errors.append("TaskResultArtifact missing required field: result_id")
        if not self.task_id:
            errors.append("TaskResultArtifact missing required field: task_id")
        if self.result_type == ResultType.HUMAN_VERIFIED and not self.verifier_id:
            errors.append("HUMAN_VERIFIED results must include verifier_id")
        if (
            self.action_reversibility == ActionReversibility.IRREVERSIBLE
            and self.result_type == ResultType.DRAFT_PRODUCED
        ):
            errors.append("IRREVERSIBLE actions cannot remain as DRAFT_PRODUCED")
        return errors


@dataclass
class AdministrativeBlockerReport:
    """Upward negotiation artifact from Admin to Executive.

    Admin validates STRUCTURE only. Content judgment (is this scope
    expansion?) is Executive's responsibility.
    """

    report_id: str
    program_id: str
    execution_plan_id: str
    summary: str
    blocker_type: BlockerType
    severity: AdminBlockerSeverity
    affected_task_ids: list[str] = field(default_factory=list)
    requested_action: RequestedAction = RequestedAction.CLARIFY
    clarification_type: ClarificationType | None = None
    original_plan_reference: str = ""
    options: list[str] = field(default_factory=list)
    details_ref: str = ""
    disposition: AdminBlockerDisposition | None = None
    created_at: str = ""  # ISO8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "program_id": self.program_id,
            "execution_plan_id": self.execution_plan_id,
            "summary": self.summary,
            "blocker_type": self.blocker_type.value,
            "severity": self.severity.value,
            "affected_task_ids": self.affected_task_ids,
            "requested_action": self.requested_action.value,
            "clarification_type": (
                self.clarification_type.value if self.clarification_type else None
            ),
            "original_plan_reference": self.original_plan_reference,
            "options": self.options,
            "details_ref": self.details_ref,
            "disposition": (self.disposition.value if self.disposition else None),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdministrativeBlockerReport:
        clarification_type = data.get("clarification_type")
        disposition = data.get("disposition")
        return cls(
            report_id=data["report_id"],
            program_id=data["program_id"],
            execution_plan_id=data["execution_plan_id"],
            summary=data["summary"],
            blocker_type=BlockerType(data["blocker_type"]),
            severity=AdminBlockerSeverity(data["severity"]),
            affected_task_ids=data.get("affected_task_ids", []),
            requested_action=RequestedAction(data.get("requested_action", "CLARIFY")),
            clarification_type=(
                ClarificationType(clarification_type) if clarification_type else None
            ),
            original_plan_reference=data.get("original_plan_reference", ""),
            options=data.get("options", []),
            details_ref=data.get("details_ref", ""),
            disposition=(AdminBlockerDisposition(disposition) if disposition else None),
            created_at=data.get("created_at", ""),
        )

    def validate(self) -> list[str]:
        """Validate STRUCTURE only. Content judgment is Executive's role."""
        errors: list[str] = []
        if not self.report_id:
            errors.append(
                "AdministrativeBlockerReport missing required field: report_id"
            )
        if not self.summary:
            errors.append("Blocker report must have summary")
        if not self.affected_task_ids:
            errors.append("Blocker report must reference affected tasks")
        if self.requested_action == RequestedAction.CLARIFY:
            if not self.clarification_type:
                errors.append("CLARIFY requests must specify clarification_type")
            if not self.original_plan_reference:
                errors.append(
                    "CLARIFY requests must quote ambiguous text from original plan"
                )
        return errors


@dataclass
class ExecutionProgram:
    """Aggregate root for Execution Program lifecycle.

    A coordinated work container that makes reality visible.
    One ExecutionProgram per motion processed.
    """

    program_id: str
    execution_plan_id: str
    motion_id: str
    duke_assignment: DukeAssignment | None = None
    earl_assignments: list[EarlAssignment] = field(default_factory=list)
    stage: ProgramStage = ProgramStage.INTAKE
    tasks: dict[str, TaskLifecycleStatus] = field(default_factory=dict)
    activation_requests: list[TaskActivationRequest] = field(default_factory=list)
    result_artifacts: list[TaskResultArtifact] = field(default_factory=list)
    blocker_reports: list[AdministrativeBlockerReport] = field(default_factory=list)
    capacity_snapshots: list[CapacitySnapshot] = field(default_factory=list)
    completion_status: ProgramCompletionStatus | None = None
    created_at: str = ""  # ISO8601
    updated_at: str = ""  # ISO8601
    schema_version: str = EXECUTION_PROGRAM_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "program_id": self.program_id,
            "execution_plan_id": self.execution_plan_id,
            "motion_id": self.motion_id,
            "duke_assignment": (
                self.duke_assignment.to_dict() if self.duke_assignment else None
            ),
            "earl_assignments": [e.to_dict() for e in self.earl_assignments],
            "stage": self.stage.value,
            "tasks": {k: v.value for k, v in self.tasks.items()},
            "activation_requests": [r.to_dict() for r in self.activation_requests],
            "result_artifacts": [r.to_dict() for r in self.result_artifacts],
            "blocker_reports": [b.to_dict() for b in self.blocker_reports],
            "capacity_snapshots": [s.to_dict() for s in self.capacity_snapshots],
            "completion_status": (
                self.completion_status.value if self.completion_status else None
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionProgram:
        duke_data = data.get("duke_assignment")
        completion = data.get("completion_status")
        tasks_data = data.get("tasks", {})
        return cls(
            program_id=data["program_id"],
            execution_plan_id=data["execution_plan_id"],
            motion_id=data["motion_id"],
            duke_assignment=(
                DukeAssignment.from_dict(duke_data) if duke_data else None
            ),
            earl_assignments=[
                EarlAssignment.from_dict(e) for e in data.get("earl_assignments", [])
            ],
            stage=ProgramStage(data.get("stage", "INTAKE")),
            tasks={k: TaskLifecycleStatus(v) for k, v in tasks_data.items()},
            activation_requests=[
                TaskActivationRequest.from_dict(r)
                for r in data.get("activation_requests", [])
            ],
            result_artifacts=[
                TaskResultArtifact.from_dict(r)
                for r in data.get("result_artifacts", [])
            ],
            blocker_reports=[
                AdministrativeBlockerReport.from_dict(b)
                for b in data.get("blocker_reports", [])
            ],
            capacity_snapshots=[
                CapacitySnapshot.from_dict(s)
                for s in data.get("capacity_snapshots", [])
            ],
            completion_status=(
                ProgramCompletionStatus(completion) if completion else None
            ),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            schema_version=data.get("schema_version", EXECUTION_PROGRAM_SCHEMA_VERSION),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.program_id:
            errors.append("ExecutionProgram missing required field: program_id")
        if not self.execution_plan_id:
            errors.append("ExecutionProgram missing required field: execution_plan_id")
        if not self.motion_id:
            errors.append("ExecutionProgram missing required field: motion_id")
        if not self.duke_assignment:
            errors.append("ExecutionProgram missing duke_assignment")
        return errors
