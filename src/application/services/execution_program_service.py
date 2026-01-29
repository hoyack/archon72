"""Execution Program Service.

Orchestrates the 6-stage Execution Program lifecycle:
  Stage A - Intake: ExecutionPlan → ExecutionProgramDraft
  Stage B - Feasibility: Validate tasks can become activation requests
  Stage C - Commit: Append-only program record
  Stage D - Activation: Earl issues requests, routes to tools/clusters
  Stage E - Results: Aggregate results, update status, escalate blockers
  Stage F - Violation Handling: Witness statements, halt/quarantine (skeleton)

Principle: "Administration exists to make reality visible, not obedient."

Constitutional truths honored:
- T5: No silence - all transitions emit events
- T6: No substitution - same-cluster retry only
- T7: Descriptive, not prescriptive - status tracking, not enforcement
- T8: Halting is not failure
- T9: Smooth running is suspicious
- T10: Capacity is first-class fact
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from structlog import get_logger

from src.application.ports.audit_event_bus import AuditEvent, AuditEventBus
from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.tool_execution import ToolExecutionProtocol
from src.domain.models.execution_program import (
    DUKE_MAX_CONCURRENT_PROGRAMS,
    EXECUTION_PROGRAM_SCHEMA_VERSION,
    MAX_SAME_CLUSTER_RETRIES,
    ActionReversibility,
    AdminBlockerDisposition,
    AdminBlockerSeverity,
    AdministrativeBlockerReport,
    BlockerType,
    CapacityConfidence,
    CapacitySnapshot,
    DukeAssignment,
    EarlAssignment,
    ExecutionProgram,
    ProgramCompletionStatus,
    ProgramStage,
    RequestedAction,
    ResultType,
    TaskActivationRequest,
    TaskLifecycleStatus,
    TaskResultArtifact,
)
from src.domain.models.executive_planning import Epic, WorkPackage

logger = get_logger(__name__)

ISO = "%Y-%m-%dT%H:%M:%SZ"

# Terminal task statuses (task is done, regardless of outcome)
_TERMINAL_STATUSES = frozenset({
    TaskLifecycleStatus.COMPLETED,
    TaskLifecycleStatus.FAILED,
    TaskLifecycleStatus.WITHDRAWN,
    TaskLifecycleStatus.TIMED_OUT,
    TaskLifecycleStatus.DECLINED,
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class ExecutionProgramService:
    """Orchestrates Execution Program lifecycle (Stages A-F).

    Takes hexagonal port injections for tool execution, audit events,
    and Archon profile lookup. Falls back to simulation mode when
    ports are not provided.
    """

    def __init__(
        self,
        tool_executor: ToolExecutionProtocol | None = None,
        audit_bus: AuditEventBus | None = None,
        profile_repository: ArchonProfileRepository | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        verbose: bool = False,
    ) -> None:
        self._tool_executor = tool_executor
        self._audit_bus = audit_bus
        self._profile_repository = profile_repository
        self._event_sink = event_sink
        self._verbose = verbose

        # In-memory duke load tracking (reset per service instance)
        self._duke_load: dict[str, int] = {}

        logger.info(
            "execution_program_service_initialized",
            tool_executor=tool_executor is not None,
            audit_bus=audit_bus is not None,
            profile_repository=profile_repository is not None,
            verbose=verbose,
        )

    # ------------------------------------------------------------------
    # Event Emission
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        logger.info("admin_event", event_type=event_type, **payload)
        if self._event_sink:
            self._event_sink(event_type, payload)

    async def _publish_audit(
        self,
        event_type: str,
        program_id: str,
        payload: dict[str, Any],
        severity: str = "info",
    ) -> None:
        """Fire-and-forget audit event publication."""
        if not self._audit_bus:
            return
        event = AuditEvent(
            event_type=event_type,
            timestamp=_now_iso(),
            source="administrative",
            program_id=program_id,
            payload=payload,
            severity=severity,
        )
        try:
            await self._audit_bus.publish(event)
        except Exception:
            logger.warning(
                "audit_publish_failed",
                event_type=event_type,
                program_id=program_id,
            )

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def load_work_packages_from_handoff(
        self,
        handoff: dict[str, Any],
        executive_output_path: Path,
    ) -> list[WorkPackage]:
        """Load work packages from execution plan referenced in handoff.

        Fills the gap: existing service loads Epics, this loads WorkPackages.
        """
        execution_plan_path = handoff.get("execution_plan_path")
        if not execution_plan_path:
            motion_id = handoff.get("motion_id", "unknown")
            execution_plan_path = str(
                executive_output_path / "motions" / motion_id / "execution_plan.json"
            )

        plan_path = Path(execution_plan_path)
        if not plan_path.exists():
            logger.warning(
                "execution_plan_not_found_for_work_packages",
                path=str(plan_path),
            )
            return []

        plan = _load_json(plan_path)
        return [WorkPackage.from_dict(wp) for wp in plan.get("work_packages", [])]

    # ------------------------------------------------------------------
    # Stage A: Intake
    # ------------------------------------------------------------------

    async def create_program_from_handoff(
        self,
        handoff: dict[str, Any],
        executive_output_path: Path,
        epics: list[Epic] | None = None,
        work_packages: list[WorkPackage] | None = None,
    ) -> ExecutionProgram:
        """Stage A: Create ExecutionProgram from Executive handoff.

        Assigns a Duke, creates the program container, and takes
        an initial capacity snapshot.
        """
        cycle_id = handoff.get("cycle_id", "")
        motion_id = handoff.get("motion_id", "")
        program_id = _new_id("prog_")

        # Load work packages if not provided
        if work_packages is None:
            work_packages = self.load_work_packages_from_handoff(
                handoff, executive_output_path
            )

        # Assign Duke
        duke = self._assign_duke(program_id)

        # Initial capacity snapshot
        snapshot = CapacitySnapshot(
            snapshot_id=_new_id("snap_"),
            program_id=program_id,
            timestamp=_now_iso(),
            total_tasks=len(work_packages),
            eligible_clusters=0,
            declared_capacity=0,
            confidence=CapacityConfidence.HIGH,
            acceptance_rate=1.0,
        )

        program = ExecutionProgram(
            program_id=program_id,
            execution_plan_id=cycle_id,
            motion_id=motion_id,
            duke_assignment=duke,
            stage=ProgramStage.INTAKE,
            capacity_snapshots=[snapshot],
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )

        self._emit(
            "administrative.program.created",
            {
                "program_id": program_id,
                "motion_id": motion_id,
                "cycle_id": cycle_id,
                "duke_name": duke.duke_name,
                "work_package_count": len(work_packages),
                "ts": _now_iso(),
            },
        )
        self._emit(
            "administrative.program.stage_entered",
            {
                "program_id": program_id,
                "stage": ProgramStage.INTAKE.value,
                "ts": _now_iso(),
            },
        )

        logger.info(
            "program_created",
            program_id=program_id,
            motion_id=motion_id,
            duke=duke.duke_name,
            work_packages=len(work_packages),
        )

        return program

    # ------------------------------------------------------------------
    # Stage B: Feasibility
    # ------------------------------------------------------------------

    async def run_feasibility_checks(
        self,
        program: ExecutionProgram,
        epics: list[Epic],
        work_packages: list[WorkPackage],
    ) -> tuple[ExecutionProgram, list[AdministrativeBlockerReport]]:
        """Stage B: Validate each WorkPackage can become a TaskActivationRequest.

        Returns the updated program and any blocker reports generated.
        """
        blocker_reports: list[AdministrativeBlockerReport] = []

        # Build epic lookup for success_signals
        epic_by_id = {e.epic_id: e for e in epics}

        for wp in work_packages:
            errors: list[str] = []

            if not wp.scope_description:
                errors.append("WorkPackage missing scope_description")
            if not wp.scope_description.strip():
                errors.append("WorkPackage scope_description is empty/whitespace")

            epic = epic_by_id.get(wp.epic_id)
            if not epic:
                errors.append(
                    f"WorkPackage references unknown epic_id: {wp.epic_id}"
                )

            if errors:
                severity = AdminBlockerSeverity.CRITICAL if not wp.scope_description else AdminBlockerSeverity.MAJOR
                report = AdministrativeBlockerReport(
                    report_id=_new_id("blocker_"),
                    program_id=program.program_id,
                    execution_plan_id=program.execution_plan_id,
                    summary=f"Cannot form activation request for {wp.package_id}: {'; '.join(errors)}",
                    blocker_type=BlockerType.REQUIREMENTS_AMBIGUOUS,
                    severity=severity,
                    affected_task_ids=[wp.package_id],
                    requested_action=RequestedAction.CLARIFY,
                    created_at=_now_iso(),
                )
                blocker_reports.append(report)
                program.blocker_reports.append(report)

                if severity in (
                    AdminBlockerSeverity.CRITICAL,
                    AdminBlockerSeverity.MAJOR,
                ):
                    self._emit(
                        "administrative.blocker.escalated",
                        {
                            "program_id": program.program_id,
                            "report_id": report.report_id,
                            "severity": severity.value,
                            "summary": report.summary,
                            "ts": _now_iso(),
                        },
                    )
                    await self._publish_audit(
                        "administrative.blocker.escalated",
                        program.program_id,
                        {"report_id": report.report_id, "severity": severity.value},
                        severity="critical" if severity == AdminBlockerSeverity.CRITICAL else "warning",
                    )
            else:
                # Task is feasible - register as PENDING
                program.tasks[wp.package_id] = TaskLifecycleStatus.PENDING

        program.stage = ProgramStage.FEASIBILITY
        program.updated_at = _now_iso()

        self._emit(
            "administrative.program.stage_entered",
            {
                "program_id": program.program_id,
                "stage": ProgramStage.FEASIBILITY.value,
                "feasible_tasks": len(program.tasks),
                "blocker_count": len(blocker_reports),
                "ts": _now_iso(),
            },
        )

        return program, blocker_reports

    # ------------------------------------------------------------------
    # Stage C: Commit
    # ------------------------------------------------------------------

    async def commit_program(
        self, program: ExecutionProgram
    ) -> ExecutionProgram:
        """Stage C: Commit program as append-only record."""
        program.stage = ProgramStage.COMMIT
        program.updated_at = _now_iso()

        self._emit(
            "administrative.program.stage_entered",
            {
                "program_id": program.program_id,
                "stage": ProgramStage.COMMIT.value,
                "task_count": len(program.tasks),
                "ts": _now_iso(),
            },
        )

        return program

    # ------------------------------------------------------------------
    # Stage D: Activation
    # ------------------------------------------------------------------

    async def activate_tasks(
        self,
        program: ExecutionProgram,
        work_packages: list[WorkPackage],
        epics: list[Epic],
    ) -> ExecutionProgram:
        """Stage D: Activate tasks via tool executor or stub for human clusters."""
        # Refresh capacity snapshot
        snapshot = self.refresh_capacity_snapshot(program)
        program.capacity_snapshots.append(snapshot)

        if snapshot.confidence == CapacityConfidence.LOW:
            self._emit(
                "administrative.capacity.stale_warning",
                {
                    "program_id": program.program_id,
                    "confidence": snapshot.confidence.value,
                    "ts": _now_iso(),
                },
            )

        # Assign Earls
        pending_task_ids = [
            tid for tid, status in program.tasks.items()
            if status == TaskLifecycleStatus.PENDING
        ]
        earl_assignments = self._assign_earls(program, pending_task_ids)
        program.earl_assignments.extend(earl_assignments)

        # Build epic lookup
        epic_by_id = {e.epic_id: e for e in epics}
        wp_by_id = {wp.package_id: wp for wp in work_packages}

        # Build earl lookup
        earl_by_task: dict[str, EarlAssignment] = {}
        for earl in earl_assignments:
            for tid in earl.task_ids:
                earl_by_task[tid] = earl

        # Activate each pending task
        for task_id in pending_task_ids:
            wp = wp_by_id.get(task_id)
            if not wp:
                continue

            epic = epic_by_id.get(wp.epic_id)
            earl = earl_by_task.get(task_id)

            request = TaskActivationRequest(
                request_id=_new_id("req_"),
                task_id=task_id,
                program_id=program.program_id,
                earl_archon_id=earl.archon_id if earl else "",
                scope_description=wp.scope_description,
                constraints=wp.constraints_respected,
                success_definition=(
                    "; ".join(epic.success_signals) if epic else ""
                ),
                required_capabilities=[],
                action_reversibility=ActionReversibility.REVERSIBLE,
                activation_deadline=(
                    datetime.now(timezone.utc) + timedelta(days=7)
                ).strftime(ISO),
                max_deadline=(
                    datetime.now(timezone.utc) + timedelta(days=30)
                ).strftime(ISO),
            )
            program.activation_requests.append(request)

            # Execute via tool executor (Lane B) if available
            if self._tool_executor:
                try:
                    result = await self._tool_executor.execute_task(request)
                    program.result_artifacts.append(result)
                    self._update_task_status(
                        program, task_id, TaskLifecycleStatus.COMPLETED
                    )
                except Exception:
                    logger.warning(
                        "tool_execution_failed",
                        task_id=task_id,
                        program_id=program.program_id,
                    )
                    self._update_task_status(
                        program, task_id, TaskLifecycleStatus.ACTIVATED
                    )
            else:
                # Simulation / Lane A stub
                self._update_task_status(
                    program, task_id, TaskLifecycleStatus.ACTIVATED
                )

            self._emit(
                "administrative.task.activated",
                {
                    "program_id": program.program_id,
                    "task_id": task_id,
                    "request_id": request.request_id,
                    "ts": _now_iso(),
                },
            )

        program.stage = ProgramStage.ACTIVATION
        program.updated_at = _now_iso()

        self._emit(
            "administrative.program.stage_entered",
            {
                "program_id": program.program_id,
                "stage": ProgramStage.ACTIVATION.value,
                "activated_count": len(pending_task_ids),
                "ts": _now_iso(),
            },
        )

        return program

    def handle_task_declined(
        self,
        program: ExecutionProgram,
        task_id: str,
        reason: str = "",
    ) -> AdministrativeBlockerReport | None:
        """Handle a cluster declining a task activation.

        Per T6: same-cluster retry only. After MAX_SAME_CLUSTER_RETRIES,
        creates a CAPACITY_UNAVAILABLE blocker report.
        """
        # Find the activation request for this task
        matching_requests = [
            r for r in program.activation_requests if r.task_id == task_id
        ]
        if not matching_requests:
            return None

        latest_request = matching_requests[-1]

        self._emit(
            "administrative.task.cluster_declined",
            {
                "program_id": program.program_id,
                "task_id": task_id,
                "retry_count": latest_request.retry_count,
                "reason": reason,
                "ts": _now_iso(),
            },
        )

        if latest_request.retry_count < MAX_SAME_CLUSTER_RETRIES:
            # Re-ask same cluster with incremented retry
            retry_request = TaskActivationRequest(
                request_id=_new_id("req_"),
                task_id=task_id,
                program_id=program.program_id,
                earl_archon_id=latest_request.earl_archon_id,
                scope_description=latest_request.scope_description,
                constraints=latest_request.constraints,
                success_definition=latest_request.success_definition,
                required_capabilities=latest_request.required_capabilities,
                action_reversibility=latest_request.action_reversibility,
                activation_deadline=latest_request.activation_deadline,
                max_deadline=latest_request.max_deadline,
                target_cluster_id=latest_request.target_cluster_id,
                retry_count=latest_request.retry_count + 1,
                original_request_id=(
                    latest_request.original_request_id or latest_request.request_id
                ),
            )
            program.activation_requests.append(retry_request)

            self._emit(
                "administrative.task.reactivation_with_context",
                {
                    "program_id": program.program_id,
                    "task_id": task_id,
                    "retry_count": retry_request.retry_count,
                    "ts": _now_iso(),
                },
            )
            return None

        # Max retries exceeded - create blocker report
        self._update_task_status(
            program, task_id, TaskLifecycleStatus.DECLINED
        )

        report = AdministrativeBlockerReport(
            report_id=_new_id("blocker_"),
            program_id=program.program_id,
            execution_plan_id=program.execution_plan_id,
            summary=(
                f"Capacity unavailable for task {task_id}: "
                f"declined {MAX_SAME_CLUSTER_RETRIES + 1} times"
            ),
            blocker_type=BlockerType.CAPACITY_UNAVAILABLE,
            severity=AdminBlockerSeverity.MAJOR,
            affected_task_ids=[task_id],
            requested_action=RequestedAction.REDUCE_SCOPE,
            created_at=_now_iso(),
        )
        program.blocker_reports.append(report)

        self._emit(
            "administrative.blocker.escalated",
            {
                "program_id": program.program_id,
                "report_id": report.report_id,
                "severity": report.severity.value,
                "summary": report.summary,
                "ts": _now_iso(),
            },
        )

        return report

    # ------------------------------------------------------------------
    # Stage E: Results
    # ------------------------------------------------------------------

    async def collect_results(
        self,
        program: ExecutionProgram,
        results: list[TaskResultArtifact],
    ) -> ExecutionProgram:
        """Stage E: Collect results and determine completion status."""
        for result in results:
            # Validate result artifact
            validation_errors = result.validate()
            if validation_errors:
                logger.warning(
                    "result_validation_errors",
                    result_id=result.result_id,
                    errors=validation_errors,
                )

            program.result_artifacts.append(result)

            # Determine target status based on result type
            if result.result_type in (
                ResultType.HUMAN_VERIFIED,
                ResultType.AUTOMATED_VERIFIED,
                ResultType.DRAFT_PRODUCED,
            ):
                target_status = TaskLifecycleStatus.COMPLETED
            else:
                target_status = TaskLifecycleStatus.COMPLETED

            self._update_task_status(program, result.task_id, target_status)

        # Update acceptance stats
        total_tasks = len(program.tasks)
        completed = sum(
            1 for s in program.tasks.values()
            if s == TaskLifecycleStatus.COMPLETED
        )
        declined = sum(
            1 for s in program.tasks.values()
            if s == TaskLifecycleStatus.DECLINED
        )
        if total_tasks > 0:
            program.capacity_snapshots[-1].acceptance_rate = (
                completed / total_tasks if total_tasks else 1.0
            )

        # Check if all tasks are in terminal state
        all_terminal = all(
            status in _TERMINAL_STATUSES
            for status in program.tasks.values()
        ) if program.tasks else False

        if all_terminal:
            program.completion_status = self._determine_completion_status(
                program
            )

        # Escalate unresolved critical blockers
        for report in program.blocker_reports:
            if (
                report.severity == AdminBlockerSeverity.CRITICAL
                and report.disposition is None
            ):
                self._emit(
                    "administrative.blocker.escalated",
                    {
                        "program_id": program.program_id,
                        "report_id": report.report_id,
                        "severity": report.severity.value,
                        "ts": _now_iso(),
                    },
                )

        program.stage = ProgramStage.RESULTS
        program.updated_at = _now_iso()

        self._emit(
            "administrative.program.stage_entered",
            {
                "program_id": program.program_id,
                "stage": ProgramStage.RESULTS.value,
                "results_count": len(results),
                "completion_status": (
                    program.completion_status.value
                    if program.completion_status
                    else None
                ),
                "ts": _now_iso(),
            },
        )

        return program

    # ------------------------------------------------------------------
    # Stage F: Violation Handling (Skeleton)
    # ------------------------------------------------------------------

    async def handle_violation(
        self,
        program: ExecutionProgram,
        violation_description: str,
    ) -> ExecutionProgram:
        """Stage F: Handle constraint violations (skeleton).

        Sets program to HALTED and publishes audit event.
        Full Knight-Witness integration is out of scope.
        """
        program.completion_status = ProgramCompletionStatus.HALTED
        program.stage = ProgramStage.VIOLATION_HANDLING
        program.updated_at = _now_iso()

        self._emit(
            "administrative.program.stage_entered",
            {
                "program_id": program.program_id,
                "stage": ProgramStage.VIOLATION_HANDLING.value,
                "violation": violation_description,
                "ts": _now_iso(),
            },
        )

        await self._publish_audit(
            "administrative.program.halted",
            program.program_id,
            {"violation": violation_description},
            severity="critical",
        )

        logger.info(
            "program_halted",
            program_id=program.program_id,
            violation=violation_description,
        )

        return program

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def check_stale_tasks(
        self,
        program: ExecutionProgram,
        now: str | None = None,
    ) -> list[str]:
        """Detect tasks past their activation_deadline.

        Transitions stale tasks to TIMED_OUT (emits event per task).
        """
        current_time = now or _now_iso()
        stale_task_ids: list[str] = []

        for request in program.activation_requests:
            status = program.tasks.get(request.task_id)
            if status not in (
                TaskLifecycleStatus.ACTIVATED,
                TaskLifecycleStatus.ACCEPTED,
            ):
                continue

            if (
                request.activation_deadline
                and current_time > request.activation_deadline
            ):
                stale_task_ids.append(request.task_id)
                self._update_task_status(
                    program, request.task_id, TaskLifecycleStatus.TIMED_OUT
                )
                self._emit(
                    "administrative.task.timed_out",
                    {
                        "program_id": program.program_id,
                        "task_id": request.task_id,
                        "deadline": request.activation_deadline,
                        "ts": current_time,
                    },
                )

        return stale_task_ids

    def refresh_capacity_snapshot(
        self, program: ExecutionProgram
    ) -> CapacitySnapshot:
        """Create a new capacity snapshot with confidence decay."""
        now = datetime.now(timezone.utc)

        # Determine confidence based on latest snapshot age
        confidence = CapacityConfidence.HIGH
        if program.capacity_snapshots:
            latest = program.capacity_snapshots[-1]
            try:
                latest_time = datetime.strptime(
                    latest.timestamp, ISO
                ).replace(tzinfo=timezone.utc)
                age = now - latest_time
                if age > timedelta(hours=4):
                    confidence = CapacityConfidence.LOW
                elif age > timedelta(hours=1):
                    confidence = CapacityConfidence.MEDIUM
            except (ValueError, TypeError):
                confidence = CapacityConfidence.LOW

        # Calculate acceptance rate from tasks
        total = len(program.tasks)
        completed = sum(
            1 for s in program.tasks.values()
            if s == TaskLifecycleStatus.COMPLETED
        )
        declined = sum(
            1 for s in program.tasks.values()
            if s == TaskLifecycleStatus.DECLINED
        )
        decided = completed + declined
        acceptance_rate = completed / decided if decided > 0 else 1.0

        snapshot = CapacitySnapshot(
            snapshot_id=_new_id("snap_"),
            program_id=program.program_id,
            timestamp=now.strftime(ISO),
            total_tasks=total,
            eligible_clusters=0,
            declared_capacity=0,
            confidence=confidence,
            acceptance_rate=acceptance_rate,
        )

        self._emit(
            "administrative.capacity.snapshot_refreshed",
            {
                "program_id": program.program_id,
                "snapshot_id": snapshot.snapshot_id,
                "confidence": confidence.value,
                "acceptance_rate": acceptance_rate,
                "ts": snapshot.timestamp,
            },
        )

        return snapshot

    def _determine_completion_status(
        self, program: ExecutionProgram
    ) -> ProgramCompletionStatus:
        """Map program state to honest completion status.

        Per T8/T9: no gates block completion. Status IS the truth.
        """
        if program.completion_status == ProgramCompletionStatus.HALTED:
            return ProgramCompletionStatus.HALTED

        # Check blocker dispositions
        has_undispositioned = any(
            r.disposition is None for r in program.blocker_reports
        )
        has_accepted_risk = any(
            r.disposition == AdminBlockerDisposition.ACCEPTED_RISK
            for r in program.blocker_reports
        )

        # Check task outcomes
        failed_count = sum(
            1 for s in program.tasks.values()
            if s == TaskLifecycleStatus.FAILED
        )
        total_tasks = len(program.tasks)

        if has_undispositioned:
            return ProgramCompletionStatus.COMPLETED_WITH_UNRESOLVED

        if failed_count > 0 and total_tasks > 0 and failed_count > total_tasks / 2:
            return ProgramCompletionStatus.FAILED

        if has_accepted_risk:
            return ProgramCompletionStatus.COMPLETED_WITH_ACCEPTED_RISKS

        return ProgramCompletionStatus.COMPLETED_CLEAN

    def _assign_duke(self, program_id: str) -> DukeAssignment:
        """Select Duke by availability (load-balancing primary)."""
        if self._profile_repository:
            candidates = self._profile_repository.get_by_branch("administrative")
            if candidates:
                # Sort by current load, pick least loaded
                best = None
                best_load = float("inf")
                for profile in candidates:
                    archon_id = str(profile.archon_id)
                    current_load = self._duke_load.get(archon_id, 0)
                    if current_load < DUKE_MAX_CONCURRENT_PROGRAMS and current_load < best_load:
                        best = profile
                        best_load = current_load

                if best:
                    archon_id = str(best.archon_id)
                    self._duke_load[archon_id] = self._duke_load.get(archon_id, 0) + 1
                    return DukeAssignment(
                        archon_id=archon_id,
                        duke_name=best.name,
                        duke_title="Administrative Coordinator",
                        program_id=program_id,
                        assigned_at=_now_iso(),
                        current_programs=self._duke_load[archon_id],
                        max_programs=DUKE_MAX_CONCURRENT_PROGRAMS,
                    )

        # Simulation fallback
        return DukeAssignment(
            archon_id="simulation-duke",
            duke_name="Simulation Duke",
            duke_title="Simulated Coordinator",
            program_id=program_id,
            assigned_at=_now_iso(),
            current_programs=1,
            max_programs=DUKE_MAX_CONCURRENT_PROGRAMS,
        )

    def _assign_earls(
        self,
        program: ExecutionProgram,
        task_ids: list[str],
    ) -> list[EarlAssignment]:
        """Distribute tasks across available Earls."""
        if not task_ids:
            return []

        if self._profile_repository:
            candidates = self._profile_repository.get_by_branch("administrative")
            if candidates:
                # Round-robin distribution across available Archons
                assignments: list[EarlAssignment] = []
                tasks_per_earl: dict[str, list[str]] = {}

                for i, task_id in enumerate(task_ids):
                    candidate = candidates[i % len(candidates)]
                    archon_id = str(candidate.archon_id)
                    if archon_id not in tasks_per_earl:
                        tasks_per_earl[archon_id] = []
                    tasks_per_earl[archon_id].append(task_id)

                for archon_id, assigned_tasks in tasks_per_earl.items():
                    profile = self._profile_repository.get_by_id(
                        __import__("uuid").UUID(archon_id)
                    )
                    name = profile.name if profile else archon_id
                    assignments.append(
                        EarlAssignment(
                            archon_id=archon_id,
                            earl_name=name,
                            task_ids=assigned_tasks,
                            assigned_at=_now_iso(),
                        )
                    )
                return assignments

        # Simulation fallback: single synthetic Earl
        return [
            EarlAssignment(
                archon_id="simulation-earl",
                earl_name="Simulation Earl",
                task_ids=task_ids,
                assigned_at=_now_iso(),
            )
        ]

    def _update_task_status(
        self,
        program: ExecutionProgram,
        task_id: str,
        new_status: TaskLifecycleStatus,
    ) -> None:
        """Update task status with T7-compliant unusual transition tracking."""
        old_status = program.tasks.get(task_id)

        # Define expected transitions (for warning, not blocking)
        expected_transitions: dict[TaskLifecycleStatus | None, set[TaskLifecycleStatus]] = {
            None: {TaskLifecycleStatus.PENDING},
            TaskLifecycleStatus.PENDING: {
                TaskLifecycleStatus.ACTIVATED,
                TaskLifecycleStatus.WITHDRAWN,
            },
            TaskLifecycleStatus.ACTIVATED: {
                TaskLifecycleStatus.ACCEPTED,
                TaskLifecycleStatus.DECLINED,
                TaskLifecycleStatus.TIMED_OUT,
                TaskLifecycleStatus.WITHDRAWN,
                TaskLifecycleStatus.COMPLETED,
            },
            TaskLifecycleStatus.ACCEPTED: {
                TaskLifecycleStatus.EXECUTING,
                TaskLifecycleStatus.WITHDRAWN,
                TaskLifecycleStatus.TIMED_OUT,
            },
            TaskLifecycleStatus.EXECUTING: {
                TaskLifecycleStatus.COMPLETED,
                TaskLifecycleStatus.FAILED,
                TaskLifecycleStatus.WITHDRAWN,
            },
        }

        expected = expected_transitions.get(old_status, set())
        if new_status not in expected:
            # T7: Log unusual transition as warning, do NOT block
            self._emit(
                "administrative.task.unusual_transition",
                {
                    "program_id": program.program_id,
                    "task_id": task_id,
                    "from_status": old_status.value if old_status else None,
                    "to_status": new_status.value,
                    "ts": _now_iso(),
                },
            )

        program.tasks[task_id] = new_status
        program.updated_at = _now_iso()
