"""Unit tests for ExecutionProgramService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.audit_event_bus import AuditEvent, AuditEventBus
from src.application.ports.tool_execution import ToolExecutionProtocol
from src.application.services.execution_program_service import (
    ExecutionProgramService,
    _now_iso,
)
from src.domain.models.execution_program import (
    MAX_SAME_CLUSTER_RETRIES,
    ActionReversibility,
    AdminBlockerDisposition,
    AdminBlockerSeverity,
    AdministrativeBlockerReport,
    BlockerType,
    CapacityConfidence,
    DukeAssignment,
    ExecutionProgram,
    ProgramCompletionStatus,
    ProgramStage,
    ResultType,
    TaskActivationRequest,
    TaskLifecycleStatus,
    TaskResultArtifact,
)
from src.domain.models.executive_planning import Epic, WorkPackage

ISO = "%Y-%m-%dT%H:%M:%SZ"


# =============================================================================
# Helpers
# =============================================================================


def _mk_epic(**overrides: object) -> Epic:
    defaults: dict = {
        "epic_id": "epic-001",
        "intent": "Test intent",
        "success_signals": ["Tests pass"],
        "constraints": ["Must be async"],
        "assumptions": [],
        "discovery_required": [],
        "mapped_motion_clauses": [],
    }
    defaults.update(overrides)
    return Epic(**defaults)


def _mk_work_package(**overrides: object) -> WorkPackage:
    defaults: dict = {
        "package_id": "wp-001",
        "epic_id": "epic-001",
        "scope_description": "Implement feature X",
        "portfolio_id": "portfolio_engineering",
    }
    defaults.update(overrides)
    return WorkPackage(**defaults)


def _mk_duke(**overrides: object) -> DukeAssignment:
    defaults: dict = {
        "archon_id": "archon-001",
        "duke_name": "Foras",
        "duke_title": "Tactical Coordination",
        "program_id": "prog-001",
        "assigned_at": "2026-01-28T12:00:00Z",
        "current_programs": 1,
        "max_programs": 5,
    }
    defaults.update(overrides)
    return DukeAssignment(**defaults)


def _mk_program(**overrides: object) -> ExecutionProgram:
    defaults: dict = {
        "program_id": "prog-001",
        "execution_plan_id": "plan-001",
        "motion_id": "motion-001",
        "duke_assignment": _mk_duke(),
        "stage": ProgramStage.INTAKE,
        "created_at": "2026-01-28T12:00:00Z",
        "updated_at": "2026-01-28T12:00:00Z",
    }
    defaults.update(overrides)
    return ExecutionProgram(**defaults)


def _mk_handoff(**overrides: object) -> dict:
    defaults: dict = {
        "cycle_id": "cycle-001",
        "motion_id": "motion-001",
        "motion_title": "Test Motion",
        "motion_text": "Test motion text",
        "execution_plan_path": "",
    }
    defaults.update(overrides)
    return defaults


def _mk_result(**overrides: object) -> TaskResultArtifact:
    defaults: dict = {
        "result_id": "res-001",
        "task_id": "wp-001",
        "request_id": "req-001",
        "result_type": ResultType.DRAFT_PRODUCED,
        "action_reversibility": ActionReversibility.REVERSIBLE,
        "deliverable_ref": "/output/artifact.json",
        "summary": "Draft produced",
        "submitted_at": "2026-01-29T12:00:00Z",
    }
    defaults.update(overrides)
    return TaskResultArtifact(**defaults)


def _mk_activation_request(**overrides: object) -> TaskActivationRequest:
    defaults: dict = {
        "request_id": "req-001",
        "task_id": "wp-001",
        "program_id": "prog-001",
        "earl_archon_id": "archon-002",
        "scope_description": "Implement feature X",
        "activation_deadline": "2026-01-30T12:00:00Z",
        "max_deadline": "2026-02-28T12:00:00Z",
    }
    defaults.update(overrides)
    return TaskActivationRequest(**defaults)


class EventCapture:
    """Captures events emitted by the service."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def __call__(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))

    def has_event(self, event_type: str) -> bool:
        return any(t == event_type for t, _ in self.events)

    def count_event(self, event_type: str) -> int:
        return sum(1 for t, _ in self.events if t == event_type)

    def get_events(self, event_type: str) -> list[dict]:
        return [p for t, p in self.events if t == event_type]


class MockAuditBus(AuditEventBus):
    def __init__(self) -> None:
        self.published: list[AuditEvent] = []

    async def publish(self, event: AuditEvent) -> None:
        self.published.append(event)


# =============================================================================
# Constructor Tests
# =============================================================================


class TestConstructor:
    def test_simulation_mode(self) -> None:
        service = ExecutionProgramService()
        assert service._tool_executor is None
        assert service._audit_bus is None
        assert service._profile_repository is None

    def test_with_ports(self) -> None:
        tool = AsyncMock(spec=ToolExecutionProtocol)
        bus = MockAuditBus()
        events = EventCapture()
        service = ExecutionProgramService(
            tool_executor=tool,
            audit_bus=bus,
            event_sink=events,
        )
        assert service._tool_executor is tool
        assert service._audit_bus is bus


# =============================================================================
# Stage A: Intake
# =============================================================================


class TestStageAIntake:
    @pytest.mark.asyncio
    async def test_creates_program_from_handoff(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)
        handoff = _mk_handoff()

        program = await service.create_program_from_handoff(
            handoff=handoff,
            executive_output_path=__import__("pathlib").Path("/nonexistent"),
            work_packages=[_mk_work_package()],
        )

        assert program.program_id.startswith("prog_")
        assert program.motion_id == "motion-001"
        assert program.execution_plan_id == "cycle-001"
        assert program.stage == ProgramStage.INTAKE
        assert program.duke_assignment is not None

    @pytest.mark.asyncio
    async def test_creates_capacity_snapshot(self) -> None:
        service = ExecutionProgramService()
        program = await service.create_program_from_handoff(
            handoff=_mk_handoff(),
            executive_output_path=__import__("pathlib").Path("/nonexistent"),
            work_packages=[_mk_work_package(), _mk_work_package(package_id="wp-002")],
        )

        assert len(program.capacity_snapshots) == 1
        snapshot = program.capacity_snapshots[0]
        assert snapshot.total_tasks == 2
        assert snapshot.confidence == CapacityConfidence.HIGH

    @pytest.mark.asyncio
    async def test_emits_program_created_event(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)

        await service.create_program_from_handoff(
            handoff=_mk_handoff(),
            executive_output_path=__import__("pathlib").Path("/nonexistent"),
            work_packages=[_mk_work_package()],
        )

        assert events.has_event("administrative.program.created")
        assert events.has_event("administrative.program.stage_entered")

    @pytest.mark.asyncio
    async def test_simulation_mode_creates_synthetic_duke(self) -> None:
        service = ExecutionProgramService()
        program = await service.create_program_from_handoff(
            handoff=_mk_handoff(),
            executive_output_path=__import__("pathlib").Path("/nonexistent"),
            work_packages=[],
        )

        assert program.duke_assignment is not None
        assert program.duke_assignment.duke_name == "Simulation Duke"


# =============================================================================
# Stage B: Feasibility
# =============================================================================


class TestStageBFeasibility:
    @pytest.mark.asyncio
    async def test_all_tasks_feasible(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program()
        epics = [_mk_epic()]
        wps = [_mk_work_package()]

        program, blockers = await service.run_feasibility_checks(program, epics, wps)

        assert len(blockers) == 0
        assert program.tasks["wp-001"] == TaskLifecycleStatus.PENDING
        assert program.stage == ProgramStage.FEASIBILITY

    @pytest.mark.asyncio
    async def test_emits_blocker_for_ambiguous_task(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)
        program = _mk_program()
        epics = [_mk_epic()]
        wps = [_mk_work_package(scope_description="")]

        program, blockers = await service.run_feasibility_checks(program, epics, wps)

        assert len(blockers) == 1
        assert blockers[0].blocker_type == BlockerType.REQUIREMENTS_AMBIGUOUS

    @pytest.mark.asyncio
    async def test_critical_blocker_escalated(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)
        program = _mk_program()
        epics = [_mk_epic()]
        wps = [_mk_work_package(scope_description="")]

        await service.run_feasibility_checks(program, epics, wps)

        assert events.has_event("administrative.blocker.escalated")

    @pytest.mark.asyncio
    async def test_unknown_epic_creates_blocker(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program()
        epics = []  # No epics
        wps = [_mk_work_package()]

        program, blockers = await service.run_feasibility_checks(program, epics, wps)

        assert len(blockers) == 1
        assert "unknown epic_id" in blockers[0].summary


# =============================================================================
# Stage C: Commit
# =============================================================================


class TestStageCCommit:
    @pytest.mark.asyncio
    async def test_commit_transitions_stage(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program(stage=ProgramStage.FEASIBILITY)

        program = await service.commit_program(program)

        assert program.stage == ProgramStage.COMMIT

    @pytest.mark.asyncio
    async def test_commit_emits_event(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)
        program = _mk_program(stage=ProgramStage.FEASIBILITY)

        await service.commit_program(program)

        assert events.has_event("administrative.program.stage_entered")
        stage_events = events.get_events("administrative.program.stage_entered")
        assert any(e["stage"] == "COMMIT" for e in stage_events)


# =============================================================================
# Stage D: Activation
# =============================================================================


class TestStageDActivation:
    @pytest.mark.asyncio
    async def test_activates_tasks_via_tool_executor(self) -> None:
        tool = AsyncMock(spec=ToolExecutionProtocol)
        tool.execute_task.return_value = _mk_result()
        events = EventCapture()
        service = ExecutionProgramService(tool_executor=tool, event_sink=events)

        program = _mk_program(
            stage=ProgramStage.COMMIT,
            tasks={"wp-001": TaskLifecycleStatus.PENDING},
        )
        epics = [_mk_epic()]
        wps = [_mk_work_package()]

        program = await service.activate_tasks(program, wps, epics)

        tool.execute_task.assert_called_once()
        assert program.stage == ProgramStage.ACTIVATION
        assert events.has_event("administrative.task.activated")

    @pytest.mark.asyncio
    async def test_simulation_mode_activates_without_executor(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)

        program = _mk_program(
            stage=ProgramStage.COMMIT,
            tasks={"wp-001": TaskLifecycleStatus.PENDING},
        )

        program = await service.activate_tasks(
            program, [_mk_work_package()], [_mk_epic()]
        )

        assert program.tasks["wp-001"] == TaskLifecycleStatus.ACTIVATED
        assert events.has_event("administrative.task.activated")

    @pytest.mark.asyncio
    async def test_refreshes_capacity_before_activation(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)

        program = _mk_program(
            stage=ProgramStage.COMMIT,
            tasks={"wp-001": TaskLifecycleStatus.PENDING},
        )

        program = await service.activate_tasks(
            program, [_mk_work_package()], [_mk_epic()]
        )

        assert events.has_event("administrative.capacity.snapshot_refreshed")
        # Should have 2 snapshots now (initial not there, refresh adds one)
        assert len(program.capacity_snapshots) >= 1

    def test_handles_declined_same_cluster_retry(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program(
            tasks={"wp-001": TaskLifecycleStatus.ACTIVATED},
            activation_requests=[_mk_activation_request(retry_count=0)],
        )

        report = service.handle_task_declined(program, "wp-001", "No capacity")

        assert report is None  # Not max retries yet
        assert len(program.activation_requests) == 2
        retry = program.activation_requests[-1]
        assert retry.retry_count == 1
        assert retry.original_request_id == "req-001"

    def test_max_retries_creates_blocker(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program(
            tasks={"wp-001": TaskLifecycleStatus.ACTIVATED},
            activation_requests=[
                _mk_activation_request(retry_count=MAX_SAME_CLUSTER_RETRIES)
            ],
        )

        report = service.handle_task_declined(program, "wp-001", "Still no capacity")

        assert report is not None
        assert report.blocker_type == BlockerType.CAPACITY_UNAVAILABLE
        assert program.tasks["wp-001"] == TaskLifecycleStatus.DECLINED

    def test_low_confidence_emits_warning(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)

        # Create program with old snapshot
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime(ISO)
        from src.domain.models.execution_program import CapacitySnapshot

        old_snap = CapacitySnapshot(
            snapshot_id="old",
            program_id="prog-001",
            timestamp=old_time,
            confidence=CapacityConfidence.HIGH,
        )
        program = _mk_program(stage=ProgramStage.COMMIT)
        program.capacity_snapshots = [old_snap]

        snapshot = service.refresh_capacity_snapshot(program)

        assert snapshot.confidence == CapacityConfidence.LOW


# =============================================================================
# Stage E: Results
# =============================================================================


class TestStageEResults:
    @pytest.mark.asyncio
    async def test_collects_results_and_updates_status(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program(
            stage=ProgramStage.ACTIVATION,
            tasks={"wp-001": TaskLifecycleStatus.ACTIVATED},
        )
        program.capacity_snapshots.append(
            __import__(
                "src.domain.models.execution_program", fromlist=["CapacitySnapshot"]
            ).CapacitySnapshot(
                snapshot_id="s1",
                program_id="prog-001",
                timestamp=_now_iso(),
            )
        )

        results = [_mk_result(task_id="wp-001")]
        program = await service.collect_results(program, results)

        assert program.tasks["wp-001"] == TaskLifecycleStatus.COMPLETED
        assert program.stage == ProgramStage.RESULTS
        assert program.completion_status == ProgramCompletionStatus.COMPLETED_CLEAN

    @pytest.mark.asyncio
    async def test_unusual_transition_logged_not_blocked(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)
        # PENDING → COMPLETED is unusual but allowed per T7
        program = _mk_program(
            stage=ProgramStage.ACTIVATION,
            tasks={"wp-001": TaskLifecycleStatus.PENDING},
        )
        program.capacity_snapshots.append(
            __import__(
                "src.domain.models.execution_program", fromlist=["CapacitySnapshot"]
            ).CapacitySnapshot(
                snapshot_id="s1",
                program_id="prog-001",
                timestamp=_now_iso(),
            )
        )

        results = [_mk_result(task_id="wp-001")]
        program = await service.collect_results(program, results)

        # Transition happened despite being unusual
        assert program.tasks["wp-001"] == TaskLifecycleStatus.COMPLETED
        assert events.has_event("administrative.task.unusual_transition")

    @pytest.mark.asyncio
    async def test_determines_completion_clean(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program(
            stage=ProgramStage.ACTIVATION,
            tasks={"wp-001": TaskLifecycleStatus.ACTIVATED},
        )
        program.capacity_snapshots.append(
            __import__(
                "src.domain.models.execution_program", fromlist=["CapacitySnapshot"]
            ).CapacitySnapshot(
                snapshot_id="s1",
                program_id="prog-001",
                timestamp=_now_iso(),
            )
        )

        results = [_mk_result(task_id="wp-001")]
        program = await service.collect_results(program, results)

        assert program.completion_status == ProgramCompletionStatus.COMPLETED_CLEAN

    @pytest.mark.asyncio
    async def test_determines_completion_with_risks(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program(
            stage=ProgramStage.ACTIVATION,
            tasks={"wp-001": TaskLifecycleStatus.ACTIVATED},
            blocker_reports=[
                AdministrativeBlockerReport(
                    report_id="b1",
                    program_id="prog-001",
                    execution_plan_id="plan-001",
                    summary="Risk accepted",
                    blocker_type=BlockerType.CAPACITY_UNAVAILABLE,
                    severity=AdminBlockerSeverity.MINOR,
                    affected_task_ids=["wp-002"],
                    disposition=AdminBlockerDisposition.ACCEPTED_RISK,
                ),
            ],
        )
        program.capacity_snapshots.append(
            __import__(
                "src.domain.models.execution_program", fromlist=["CapacitySnapshot"]
            ).CapacitySnapshot(
                snapshot_id="s1",
                program_id="prog-001",
                timestamp=_now_iso(),
            )
        )

        results = [_mk_result(task_id="wp-001")]
        program = await service.collect_results(program, results)

        assert (
            program.completion_status
            == ProgramCompletionStatus.COMPLETED_WITH_ACCEPTED_RISKS
        )

    @pytest.mark.asyncio
    async def test_determines_completion_unresolved(self) -> None:
        service = ExecutionProgramService()
        program = _mk_program(
            stage=ProgramStage.ACTIVATION,
            tasks={"wp-001": TaskLifecycleStatus.ACTIVATED},
            blocker_reports=[
                AdministrativeBlockerReport(
                    report_id="b1",
                    program_id="prog-001",
                    execution_plan_id="plan-001",
                    summary="Unresolved",
                    blocker_type=BlockerType.CONSTRAINT_CONFLICT,
                    severity=AdminBlockerSeverity.MAJOR,
                    affected_task_ids=["wp-001"],
                    disposition=None,  # Undispositioned
                ),
            ],
        )
        program.capacity_snapshots.append(
            __import__(
                "src.domain.models.execution_program", fromlist=["CapacitySnapshot"]
            ).CapacitySnapshot(
                snapshot_id="s1",
                program_id="prog-001",
                timestamp=_now_iso(),
            )
        )

        results = [_mk_result(task_id="wp-001")]
        program = await service.collect_results(program, results)

        assert (
            program.completion_status
            == ProgramCompletionStatus.COMPLETED_WITH_UNRESOLVED
        )


# =============================================================================
# Stage F: Violation
# =============================================================================


class TestStageFViolation:
    @pytest.mark.asyncio
    async def test_halts_program(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)
        program = _mk_program()

        program = await service.handle_violation(program, "Consent breach")

        assert program.completion_status == ProgramCompletionStatus.HALTED
        assert program.stage == ProgramStage.VIOLATION_HANDLING
        assert events.has_event("administrative.program.stage_entered")

    @pytest.mark.asyncio
    async def test_publishes_to_audit_bus(self) -> None:
        bus = MockAuditBus()
        service = ExecutionProgramService(audit_bus=bus)
        program = _mk_program()

        await service.handle_violation(program, "Consent breach")

        assert len(bus.published) == 1
        assert bus.published[0].event_type == "administrative.program.halted"
        assert bus.published[0].severity == "critical"


# =============================================================================
# Stale Task Detection
# =============================================================================


class TestStaleTaskDetection:
    def test_detects_stale_tasks(self) -> None:
        events = EventCapture()
        service = ExecutionProgramService(event_sink=events)

        past_deadline = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(ISO)

        program = _mk_program(
            tasks={"wp-001": TaskLifecycleStatus.ACTIVATED},
            activation_requests=[
                _mk_activation_request(
                    task_id="wp-001",
                    activation_deadline=past_deadline,
                )
            ],
        )

        stale = service.check_stale_tasks(program)

        assert stale == ["wp-001"]
        assert program.tasks["wp-001"] == TaskLifecycleStatus.TIMED_OUT
        assert events.has_event("administrative.task.timed_out")

    def test_ignores_completed_tasks(self) -> None:
        service = ExecutionProgramService()

        past_deadline = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(ISO)

        program = _mk_program(
            tasks={"wp-001": TaskLifecycleStatus.COMPLETED},
            activation_requests=[
                _mk_activation_request(
                    task_id="wp-001",
                    activation_deadline=past_deadline,
                )
            ],
        )

        stale = service.check_stale_tasks(program)

        assert stale == []
        assert program.tasks["wp-001"] == TaskLifecycleStatus.COMPLETED


# =============================================================================
# Capacity Refresh
# =============================================================================


class TestCapacityRefresh:
    def test_confidence_decay_by_age(self) -> None:
        service = ExecutionProgramService()

        # Recent snapshot → HIGH
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime(ISO)
        from src.domain.models.execution_program import CapacitySnapshot

        program = _mk_program()
        program.capacity_snapshots = [
            CapacitySnapshot(
                snapshot_id="s1",
                program_id="prog-001",
                timestamp=recent_time,
            )
        ]
        snapshot = service.refresh_capacity_snapshot(program)
        assert snapshot.confidence == CapacityConfidence.HIGH

        # 2-hour old snapshot → MEDIUM
        medium_time = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(ISO)
        program.capacity_snapshots = [
            CapacitySnapshot(
                snapshot_id="s2",
                program_id="prog-001",
                timestamp=medium_time,
            )
        ]
        snapshot = service.refresh_capacity_snapshot(program)
        assert snapshot.confidence == CapacityConfidence.MEDIUM

        # 5-hour old snapshot → LOW
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime(ISO)
        program.capacity_snapshots = [
            CapacitySnapshot(
                snapshot_id="s3",
                program_id="prog-001",
                timestamp=old_time,
            )
        ]
        snapshot = service.refresh_capacity_snapshot(program)
        assert snapshot.confidence == CapacityConfidence.LOW
