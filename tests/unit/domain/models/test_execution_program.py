"""Unit tests for execution_program domain models."""

from __future__ import annotations

import json

import pytest

from src.domain.models.execution_program import (
    DUKE_MAX_CONCURRENT_PROGRAMS,
    EXECUTION_PROGRAM_SCHEMA_VERSION,
    HIGH_VELOCITY_THRESHOLD,
    MAX_EXTENSIONS,
    MAX_SAME_CLUSTER_RETRIES,
    TASK_MAX_LIFETIME_DAYS,
    ActionReversibility,
    AdminBlockerDisposition,
    AdminBlockerSeverity,
    AdministrativeBlockerReport,
    BlockerType,
    CapacityConfidence,
    CapacitySnapshot,
    ClarificationType,
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


# =============================================================================
# Helpers
# =============================================================================


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


def _mk_earl(**overrides: object) -> EarlAssignment:
    defaults: dict = {
        "archon_id": "archon-002",
        "earl_name": "Paimon",
        "task_ids": ["task-001"],
        "assigned_at": "2026-01-28T12:00:00Z",
    }
    defaults.update(overrides)
    return EarlAssignment(**defaults)


def _mk_snapshot(**overrides: object) -> CapacitySnapshot:
    defaults: dict = {
        "snapshot_id": "snap-001",
        "program_id": "prog-001",
        "timestamp": "2026-01-28T12:00:00Z",
        "total_tasks": 5,
        "eligible_clusters": 3,
        "declared_capacity": 10,
        "confidence": CapacityConfidence.HIGH,
        "acceptance_rate": 0.8,
    }
    defaults.update(overrides)
    return CapacitySnapshot(**defaults)


def _mk_activation_request(**overrides: object) -> TaskActivationRequest:
    defaults: dict = {
        "request_id": "req-001",
        "task_id": "task-001",
        "program_id": "prog-001",
        "earl_archon_id": "archon-002",
        "scope_description": "Implement feature X",
        "constraints": ["Must use async"],
        "success_definition": "All tests pass",
        "activation_deadline": "2026-01-30T12:00:00Z",
        "max_deadline": "2026-02-28T12:00:00Z",
    }
    defaults.update(overrides)
    return TaskActivationRequest(**defaults)


def _mk_result(**overrides: object) -> TaskResultArtifact:
    defaults: dict = {
        "result_id": "res-001",
        "task_id": "task-001",
        "request_id": "req-001",
        "result_type": ResultType.DRAFT_PRODUCED,
        "action_reversibility": ActionReversibility.REVERSIBLE,
        "deliverable_ref": "/path/to/artifact",
        "summary": "Draft produced",
        "submitted_at": "2026-01-29T12:00:00Z",
    }
    defaults.update(overrides)
    return TaskResultArtifact(**defaults)


def _mk_blocker_report(**overrides: object) -> AdministrativeBlockerReport:
    defaults: dict = {
        "report_id": "blocker-001",
        "program_id": "prog-001",
        "execution_plan_id": "plan-001",
        "summary": "Capacity unavailable for 3 tasks",
        "blocker_type": BlockerType.CAPACITY_UNAVAILABLE,
        "severity": AdminBlockerSeverity.MAJOR,
        "affected_task_ids": ["task-001", "task-002"],
        "requested_action": RequestedAction.REDUCE_SCOPE,
        "created_at": "2026-01-28T12:00:00Z",
    }
    defaults.update(overrides)
    return AdministrativeBlockerReport(**defaults)


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


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    def test_task_lifecycle_has_9_statuses(self) -> None:
        assert len(TaskLifecycleStatus) == 9

    def test_task_lifecycle_members(self) -> None:
        expected = {
            "PENDING", "ACTIVATED", "ACCEPTED", "DECLINED",
            "EXECUTING", "COMPLETED", "FAILED", "WITHDRAWN", "TIMED_OUT",
        }
        assert {m.name for m in TaskLifecycleStatus} == expected

    def test_program_completion_has_5_states(self) -> None:
        assert len(ProgramCompletionStatus) == 5

    def test_program_completion_members(self) -> None:
        expected = {
            "COMPLETED_CLEAN", "COMPLETED_WITH_ACCEPTED_RISKS",
            "COMPLETED_WITH_UNRESOLVED", "FAILED", "HALTED",
        }
        assert {m.name for m in ProgramCompletionStatus} == expected

    def test_program_stage_has_6_stages(self) -> None:
        assert len(ProgramStage) == 6

    def test_enums_are_json_serializable(self) -> None:
        """str, Enum allows direct JSON serialization."""
        status = TaskLifecycleStatus.PENDING
        assert json.dumps(status) == '"PENDING"'

    def test_blocker_type_members(self) -> None:
        expected = {
            "REQUIREMENTS_AMBIGUOUS", "CAPACITY_UNAVAILABLE",
            "CONSTRAINT_CONFLICT", "RESOURCE_MISSING",
        }
        assert {m.name for m in BlockerType} == expected

    def test_result_type_members(self) -> None:
        expected = {"DRAFT_PRODUCED", "HUMAN_VERIFIED", "AUTOMATED_VERIFIED"}
        assert {m.name for m in ResultType} == expected

    def test_action_reversibility_members(self) -> None:
        expected = {"REVERSIBLE", "IRREVERSIBLE", "PARTIALLY_REVERSIBLE"}
        assert {m.name for m in ActionReversibility} == expected

    def test_clarification_type_members(self) -> None:
        expected = {
            "AMBIGUITY_RESOLUTION", "CONSTRAINT_INTERPRETATION",
            "DEPENDENCY_QUESTION",
        }
        assert {m.name for m in ClarificationType} == expected

    def test_capacity_confidence_members(self) -> None:
        expected = {"HIGH", "MEDIUM", "LOW"}
        assert {m.name for m in CapacityConfidence} == expected

    def test_admin_blocker_disposition_members(self) -> None:
        expected = {"RESOLVED", "ACCEPTED_RISK", "ESCALATED"}
        assert {m.name for m in AdminBlockerDisposition} == expected

    def test_requested_action_members(self) -> None:
        expected = {"CLARIFY", "REVISE_PLAN", "REDUCE_SCOPE", "DEFER"}
        assert {m.name for m in RequestedAction} == expected


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    def test_schema_version(self) -> None:
        assert EXECUTION_PROGRAM_SCHEMA_VERSION == "2.0"

    def test_duke_max_concurrent(self) -> None:
        assert DUKE_MAX_CONCURRENT_PROGRAMS == 5

    def test_max_same_cluster_retries(self) -> None:
        assert MAX_SAME_CLUSTER_RETRIES == 2

    def test_max_extensions(self) -> None:
        assert MAX_EXTENSIONS == 2

    def test_task_max_lifetime(self) -> None:
        assert TASK_MAX_LIFETIME_DAYS == 30

    def test_high_velocity_threshold(self) -> None:
        assert HIGH_VELOCITY_THRESHOLD == 10


# =============================================================================
# DukeAssignment Tests
# =============================================================================


class TestDukeAssignment:
    def test_roundtrip(self) -> None:
        duke = _mk_duke()
        restored = DukeAssignment.from_dict(duke.to_dict())
        assert restored.archon_id == duke.archon_id
        assert restored.duke_name == duke.duke_name
        assert restored.program_id == duke.program_id
        assert restored.current_programs == duke.current_programs
        assert restored.max_programs == duke.max_programs

    def test_validate_ok(self) -> None:
        assert _mk_duke().validate() == []

    def test_validate_missing_archon_id(self) -> None:
        errors = _mk_duke(archon_id="").validate()
        assert any("archon_id" in e for e in errors)

    def test_validate_overloaded(self) -> None:
        errors = _mk_duke(current_programs=6, max_programs=5).validate()
        assert any("overloaded" in e for e in errors)


# =============================================================================
# EarlAssignment Tests
# =============================================================================


class TestEarlAssignment:
    def test_roundtrip(self) -> None:
        earl = _mk_earl()
        restored = EarlAssignment.from_dict(earl.to_dict())
        assert restored.archon_id == earl.archon_id
        assert restored.earl_name == earl.earl_name
        assert restored.task_ids == earl.task_ids

    def test_validate_ok(self) -> None:
        assert _mk_earl().validate() == []

    def test_validate_missing_name(self) -> None:
        errors = _mk_earl(earl_name="").validate()
        assert any("earl_name" in e for e in errors)


# =============================================================================
# CapacitySnapshot Tests
# =============================================================================


class TestCapacitySnapshot:
    def test_roundtrip(self) -> None:
        snap = _mk_snapshot()
        restored = CapacitySnapshot.from_dict(snap.to_dict())
        assert restored.snapshot_id == snap.snapshot_id
        assert restored.confidence == snap.confidence
        assert restored.acceptance_rate == snap.acceptance_rate

    def test_validate_ok(self) -> None:
        assert _mk_snapshot().validate() == []

    def test_validate_acceptance_rate_out_of_range(self) -> None:
        errors = _mk_snapshot(acceptance_rate=1.5).validate()
        assert any("acceptance_rate" in e for e in errors)

    def test_validate_negative_acceptance_rate(self) -> None:
        errors = _mk_snapshot(acceptance_rate=-0.1).validate()
        assert any("acceptance_rate" in e for e in errors)


# =============================================================================
# TaskActivationRequest Tests
# =============================================================================


class TestTaskActivationRequest:
    def test_roundtrip(self) -> None:
        req = _mk_activation_request()
        restored = TaskActivationRequest.from_dict(req.to_dict())
        assert restored.request_id == req.request_id
        assert restored.task_id == req.task_id
        assert restored.scope_description == req.scope_description
        assert restored.action_reversibility == req.action_reversibility
        assert restored.retry_count == req.retry_count

    def test_validate_ok(self) -> None:
        assert _mk_activation_request().validate() == []

    def test_validate_empty_scope(self) -> None:
        errors = _mk_activation_request(scope_description="").validate()
        assert any("scope_description" in e for e in errors)

    def test_validate_deadline_exceeds_max(self) -> None:
        errors = _mk_activation_request(
            activation_deadline="2026-03-01T00:00:00Z",
            max_deadline="2026-02-01T00:00:00Z",
        ).validate()
        assert any("exceeds max_deadline" in e for e in errors)

    def test_retry_lineage(self) -> None:
        req = _mk_activation_request(
            retry_count=1,
            original_request_id="req-original",
        )
        d = req.to_dict()
        assert d["retry_count"] == 1
        assert d["original_request_id"] == "req-original"


# =============================================================================
# TaskResultArtifact Tests
# =============================================================================


class TestTaskResultArtifact:
    def test_roundtrip(self) -> None:
        result = _mk_result()
        restored = TaskResultArtifact.from_dict(result.to_dict())
        assert restored.result_id == result.result_id
        assert restored.result_type == result.result_type
        assert restored.action_reversibility == result.action_reversibility

    def test_validate_ok(self) -> None:
        assert _mk_result().validate() == []

    def test_validate_human_verified_without_verifier(self) -> None:
        errors = _mk_result(
            result_type=ResultType.HUMAN_VERIFIED,
            verifier_id=None,
        ).validate()
        assert any("verifier_id" in e for e in errors)

    def test_validate_irreversible_draft(self) -> None:
        errors = _mk_result(
            action_reversibility=ActionReversibility.IRREVERSIBLE,
            result_type=ResultType.DRAFT_PRODUCED,
        ).validate()
        assert any("IRREVERSIBLE" in e for e in errors)

    def test_requires_verification_irreversible(self) -> None:
        result = _mk_result(
            action_reversibility=ActionReversibility.IRREVERSIBLE,
        )
        assert result.requires_verification is True

    def test_requires_verification_partially_reversible(self) -> None:
        result = _mk_result(
            action_reversibility=ActionReversibility.PARTIALLY_REVERSIBLE,
        )
        assert result.requires_verification is True

    def test_requires_verification_reversible(self) -> None:
        result = _mk_result(
            action_reversibility=ActionReversibility.REVERSIBLE,
        )
        assert result.requires_verification is False

    def test_to_dict_includes_requires_verification(self) -> None:
        d = _mk_result().to_dict()
        assert "requires_verification" in d
        assert d["requires_verification"] is False


# =============================================================================
# AdministrativeBlockerReport Tests
# =============================================================================


class TestAdministrativeBlockerReport:
    def test_roundtrip(self) -> None:
        report = _mk_blocker_report()
        restored = AdministrativeBlockerReport.from_dict(report.to_dict())
        assert restored.report_id == report.report_id
        assert restored.blocker_type == report.blocker_type
        assert restored.severity == report.severity
        assert restored.affected_task_ids == report.affected_task_ids

    def test_roundtrip_with_clarification_type(self) -> None:
        report = _mk_blocker_report(
            requested_action=RequestedAction.CLARIFY,
            clarification_type=ClarificationType.AMBIGUITY_RESOLUTION,
            original_plan_reference="Section 3.1: unclear scope",
        )
        restored = AdministrativeBlockerReport.from_dict(report.to_dict())
        assert restored.clarification_type == ClarificationType.AMBIGUITY_RESOLUTION

    def test_roundtrip_with_disposition(self) -> None:
        report = _mk_blocker_report(
            disposition=AdminBlockerDisposition.RESOLVED,
        )
        restored = AdministrativeBlockerReport.from_dict(report.to_dict())
        assert restored.disposition == AdminBlockerDisposition.RESOLVED

    def test_validate_ok(self) -> None:
        assert _mk_blocker_report().validate() == []

    def test_validate_empty_summary(self) -> None:
        errors = _mk_blocker_report(summary="").validate()
        assert any("summary" in e for e in errors)

    def test_validate_empty_affected_tasks(self) -> None:
        errors = _mk_blocker_report(affected_task_ids=[]).validate()
        assert any("affected tasks" in e for e in errors)

    def test_validate_clarify_without_type(self) -> None:
        errors = _mk_blocker_report(
            requested_action=RequestedAction.CLARIFY,
            clarification_type=None,
            original_plan_reference="some ref",
        ).validate()
        assert any("clarification_type" in e for e in errors)

    def test_validate_clarify_without_reference(self) -> None:
        errors = _mk_blocker_report(
            requested_action=RequestedAction.CLARIFY,
            clarification_type=ClarificationType.AMBIGUITY_RESOLUTION,
            original_plan_reference="",
        ).validate()
        assert any("ambiguous text" in e for e in errors)


# =============================================================================
# ExecutionProgram Tests
# =============================================================================


class TestExecutionProgram:
    def test_roundtrip(self) -> None:
        program = _mk_program(
            tasks={"task-001": TaskLifecycleStatus.PENDING},
            earl_assignments=[_mk_earl()],
            capacity_snapshots=[_mk_snapshot()],
        )
        restored = ExecutionProgram.from_dict(program.to_dict())
        assert restored.program_id == program.program_id
        assert restored.motion_id == program.motion_id
        assert restored.stage == program.stage
        assert restored.tasks["task-001"] == TaskLifecycleStatus.PENDING
        assert len(restored.earl_assignments) == 1
        assert len(restored.capacity_snapshots) == 1
        assert restored.duke_assignment is not None
        assert restored.duke_assignment.duke_name == "Foras"

    def test_roundtrip_with_nested(self) -> None:
        program = _mk_program(
            activation_requests=[_mk_activation_request()],
            result_artifacts=[_mk_result()],
            blocker_reports=[_mk_blocker_report()],
            completion_status=ProgramCompletionStatus.COMPLETED_CLEAN,
        )
        restored = ExecutionProgram.from_dict(program.to_dict())
        assert len(restored.activation_requests) == 1
        assert len(restored.result_artifacts) == 1
        assert len(restored.blocker_reports) == 1
        assert restored.completion_status == ProgramCompletionStatus.COMPLETED_CLEAN

    def test_validate_ok(self) -> None:
        assert _mk_program().validate() == []

    def test_validate_missing_program_id(self) -> None:
        errors = _mk_program(program_id="").validate()
        assert any("program_id" in e for e in errors)

    def test_validate_missing_duke(self) -> None:
        errors = _mk_program(duke_assignment=None).validate()
        assert any("duke_assignment" in e for e in errors)

    def test_validate_missing_execution_plan_id(self) -> None:
        errors = _mk_program(execution_plan_id="").validate()
        assert any("execution_plan_id" in e for e in errors)

    def test_schema_version_default(self) -> None:
        program = _mk_program()
        assert program.schema_version == EXECUTION_PROGRAM_SCHEMA_VERSION
        assert program.to_dict()["schema_version"] == "2.0"

    def test_roundtrip_null_completion(self) -> None:
        program = _mk_program(completion_status=None)
        restored = ExecutionProgram.from_dict(program.to_dict())
        assert restored.completion_status is None

    def test_roundtrip_null_duke(self) -> None:
        program = _mk_program(duke_assignment=None)
        d = program.to_dict()
        assert d["duke_assignment"] is None
        restored = ExecutionProgram.from_dict(d)
        assert restored.duke_assignment is None
