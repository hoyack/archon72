"""Unit tests for Task Result Artifact ingestion.

Tests the friction layer: proves the system can metabolize
COMPLETED, DECLINED, BLOCKED, FAILED, and invalid input
without silent success theater.

All tests are pure unit tests with NO infrastructure dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from scripts.ingest_task_result import (
    build_task_state,
    compute_escalations,
    resolve_task_state,
    validate_references,
    validate_tra,
)

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "contracts"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tra(
    *,
    status: str = "COMPLETED",
    deliverables: list | None = None,
    issues: list | None = None,
    next_actions: list | None = None,
) -> dict:
    """Build a minimal valid TRA for testing."""
    return {
        "schema_version": "1.0",
        "tra_id": "tra-test-001",
        "submitted_at": "2026-01-29T14:00:00Z",
        "references": {
            "tar_id": "tar-test-001",
            "program_id": "program-test-001",
            "task_id": "task-test-001",
        },
        "responder": {
            "tool_id": "cluster:alpha",
            "tool_class": "HUMAN_CLUSTER",
            "operator": "human",
        },
        "outcome": {
            "status": status,
            "summary": f"Task {status.lower()}.",
            "deliverables": deliverables or [],
            "evidence_refs": [],
            "issues": issues or [],
        },
        "next_actions": next_actions or [],
    }


def _make_program(
    *,
    program_id: str = "program-test-001",
    task_ids: list[str] | None = None,
) -> dict:
    """Build a minimal execution program for reference validation."""
    if task_ids is None:
        task_ids = ["task-test-001"]
    return {
        "schema_version": "1.0",
        "program_id": program_id,
        "created_at": "2026-01-29T12:00:00Z",
        "references": {
            "handoff_id": "handoff-test-001",
            "award_id": "award-test-001",
            "rfp_id": "rfp-test-001",
            "mandate_id": "mandate-test-001",
        },
        "ownership": {
            "duke_id": "duke-test",
            "supervising_earl_id": "earl-test",
            "routing_basis": {
                "routing_table_version": "1.0",
                "matched_portfolio": "transformation",
            },
        },
        "status": "ACTIVE",
        "tasks": [
            {
                "task_id": tid,
                "title": f"Task {tid}",
                "intent": "test",
                "required_capabilities": ["doc_drafting"],
                "acceptance_criteria": [],
                "constraints": [],
                "activation": {
                    "earl_id": "earl-test",
                    "target_tool_class": "HUMAN_CLUSTER",
                    "eligible_tools": ["cluster:alpha"],
                    "priority": "NORMAL",
                },
            }
            for tid in task_ids
        ],
        "capacity_snapshot": {
            "captured_at": "2026-01-29T12:00:00Z",
            "assumptions": [],
            "declared_constraints": [],
        },
        "blockers": [],
        "events_ref": "events.jsonl",
    }


# ===========================================================================
# 1) COMPLETED TRA → CLOSED, no escalation
# ===========================================================================


class TestCompletedTRA:
    def test_completed_maps_to_closed(self) -> None:
        assert resolve_task_state("COMPLETED") == "CLOSED"

    def test_completed_no_escalations(self) -> None:
        tra = _make_tra(
            status="COMPLETED",
            deliverables=[{"id": "deliv-1", "artifact_ref": "artifacts/doc.md"}],
        )
        escalations = compute_escalations(tra["outcome"], "2026-01-29T14:00:00Z")
        assert len(escalations) == 0

    def test_completed_task_state_has_deliverables(self) -> None:
        tra = _make_tra(
            status="COMPLETED",
            deliverables=[{"id": "deliv-1", "artifact_ref": "artifacts/doc.md"}],
        )
        state = build_task_state(
            tra, "CLOSED", [], "2026-01-29T14:00:00Z"
        )
        assert state["state"] == "CLOSED"
        assert state["last_outcome_status"] == "COMPLETED"
        assert len(state["deliverables"]) == 1
        assert state["deliverables"][0]["artifact_ref"] == "artifacts/doc.md"
        assert len(state["blockers"]) == 0
        assert len(state["escalations"]) == 0

    def test_completed_task_state_validates_schema(self) -> None:
        schema = _load_schema("task_state.schema.json")
        tra = _make_tra(
            status="COMPLETED",
            deliverables=[{"id": "deliv-1", "artifact_ref": "artifacts/doc.md"}],
        )
        state = build_task_state(
            tra, "CLOSED", [], "2026-01-29T14:00:00Z"
        )
        jsonschema.validate(instance=state, schema=schema)


# ===========================================================================
# 2) DECLINED TRA → NEEDS_REROUTE, no escalation
# ===========================================================================


class TestDeclinedTRA:
    def test_declined_maps_to_needs_reroute(self) -> None:
        assert resolve_task_state("DECLINED") == "NEEDS_REROUTE"

    def test_withdrawn_maps_to_needs_reroute(self) -> None:
        assert resolve_task_state("WITHDRAWN") == "NEEDS_REROUTE"

    def test_declined_no_escalations(self) -> None:
        tra = _make_tra(status="DECLINED")
        escalations = compute_escalations(tra["outcome"], "2026-01-29T14:00:00Z")
        assert len(escalations) == 0

    def test_declined_task_state_validates_schema(self) -> None:
        schema = _load_schema("task_state.schema.json")
        tra = _make_tra(status="DECLINED")
        state = build_task_state(
            tra, "NEEDS_REROUTE", [], "2026-01-29T14:00:00Z"
        )
        jsonschema.validate(instance=state, schema=schema)


# ===========================================================================
# 3) BLOCKED + needs_upstream_decision → escalation emitted
# ===========================================================================


class TestBlockedTRA:
    def test_blocked_maps_to_blocked_state(self) -> None:
        assert resolve_task_state("BLOCKED") == "BLOCKED"

    def test_blocked_with_upstream_decision_escalates(self) -> None:
        tra = _make_tra(
            status="BLOCKED",
            issues=[
                {
                    "type": "BLOCKER",
                    "severity": "MAJOR",
                    "description": "Cannot proceed without API credentials",
                    "needs_upstream_decision": True,
                }
            ],
        )
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        assert len(escalations) == 1
        assert escalations[0]["to"] == "DUKE"
        assert escalations[0]["reason"] == "BLOCKED_NEEDS_DECISION"

    def test_blocked_without_upstream_decision_no_escalation(self) -> None:
        tra = _make_tra(
            status="BLOCKED",
            issues=[
                {
                    "type": "BLOCKER",
                    "severity": "MINOR",
                    "description": "Waiting for external dependency",
                    "needs_upstream_decision": False,
                }
            ],
        )
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        assert len(escalations) == 0

    def test_blocked_task_state_includes_blockers(self) -> None:
        issues = [
            {
                "type": "BLOCKER",
                "severity": "MAJOR",
                "description": "Missing credentials",
                "needs_upstream_decision": True,
            }
        ]
        tra = _make_tra(status="BLOCKED", issues=issues)
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        state = build_task_state(
            tra, "BLOCKED", escalations, "2026-01-29T14:00:00Z"
        )
        assert state["state"] == "BLOCKED"
        assert len(state["blockers"]) == 1
        assert state["blockers"][0]["needs_upstream_decision"] is True
        assert len(state["escalations"]) == 1

    def test_blocked_task_state_validates_schema(self) -> None:
        schema = _load_schema("task_state.schema.json")
        issues = [
            {
                "type": "BLOCKER",
                "severity": "MAJOR",
                "description": "Missing credentials",
                "needs_upstream_decision": True,
            }
        ]
        tra = _make_tra(status="BLOCKED", issues=issues)
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        state = build_task_state(
            tra, "BLOCKED", escalations, "2026-01-29T14:00:00Z"
        )
        jsonschema.validate(instance=state, schema=schema)


# ===========================================================================
# 4) CONSTRAINT_VIOLATION SEVERE → escalation emitted
# ===========================================================================


class TestConstraintViolation:
    def test_severe_constraint_violation_escalates(self) -> None:
        tra = _make_tra(
            status="FAILED",
            issues=[
                {
                    "type": "CONSTRAINT_VIOLATION",
                    "severity": "SEVERE",
                    "description": "PII detected in output",
                    "needs_upstream_decision": False,
                }
            ],
        )
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        assert len(escalations) == 1
        assert escalations[0]["to"] == "DUKE"
        assert escalations[0]["reason"] == "SEVERE_CONSTRAINT_VIOLATION"

    def test_minor_constraint_violation_no_escalation(self) -> None:
        tra = _make_tra(
            status="COMPLETED",
            issues=[
                {
                    "type": "CONSTRAINT_VIOLATION",
                    "severity": "MINOR",
                    "description": "Style guide deviation",
                    "needs_upstream_decision": False,
                }
            ],
        )
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        assert len(escalations) == 0

    def test_multiple_issues_multiple_escalations(self) -> None:
        tra = _make_tra(
            status="BLOCKED",
            issues=[
                {
                    "type": "BLOCKER",
                    "severity": "MAJOR",
                    "description": "Blocked by dependency",
                    "needs_upstream_decision": True,
                },
                {
                    "type": "CONSTRAINT_VIOLATION",
                    "severity": "SEVERE",
                    "description": "Production data accessed",
                    "needs_upstream_decision": False,
                },
            ],
        )
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        assert len(escalations) == 2
        reasons = {e["reason"] for e in escalations}
        assert reasons == {
            "BLOCKED_NEEDS_DECISION",
            "SEVERE_CONSTRAINT_VIOLATION",
        }

    def test_constraint_violation_state_validates_schema(self) -> None:
        schema = _load_schema("task_state.schema.json")
        issues = [
            {
                "type": "CONSTRAINT_VIOLATION",
                "severity": "SEVERE",
                "description": "PII detected",
                "needs_upstream_decision": False,
            }
        ]
        tra = _make_tra(status="FAILED", issues=issues)
        escalations = compute_escalations(
            tra["outcome"], "2026-01-29T14:00:00Z"
        )
        state = build_task_state(
            tra, "FAILED", escalations, "2026-01-29T14:00:00Z"
        )
        jsonschema.validate(instance=state, schema=schema)


# ===========================================================================
# 5) Invalid TRA → rejected
# ===========================================================================


class TestInvalidTRA:
    def test_missing_required_field_fails_validation(self) -> None:
        invalid = {"schema_version": "1.0", "tra_id": "tra-bad"}
        with pytest.raises(jsonschema.ValidationError):
            validate_tra(invalid)

    def test_bad_outcome_status_enum_fails_validation(self) -> None:
        tra = _make_tra(status="COMPLETED")
        tra["outcome"]["status"] = "INVALID_STATUS"
        with pytest.raises(jsonschema.ValidationError):
            validate_tra(tra)

    def test_bad_tool_class_fails_validation(self) -> None:
        tra = _make_tra()
        tra["responder"]["tool_class"] = "MAGIC_TOOL"
        with pytest.raises(jsonschema.ValidationError):
            validate_tra(tra)

    def test_unknown_outcome_status_raises_in_resolve(self) -> None:
        with pytest.raises(ValueError, match="Unknown outcome status"):
            resolve_task_state("INVENTED_STATUS")


# ===========================================================================
# 6) Unmatched references with --program → error
# ===========================================================================


class TestReferenceValidation:
    def test_matching_references_pass(self) -> None:
        tra = _make_tra()
        program = _make_program()
        # Should not raise
        validate_references(tra, program)

    def test_mismatched_program_id_raises(self) -> None:
        tra = _make_tra()
        program = _make_program(program_id="program-wrong")
        with pytest.raises(ValueError, match="does not match"):
            validate_references(tra, program)

    def test_mismatched_task_id_raises(self) -> None:
        tra = _make_tra()
        program = _make_program(task_ids=["task-other"])
        with pytest.raises(ValueError, match="not found in program"):
            validate_references(tra, program)

    def test_valid_tra_schema_round_trip(self) -> None:
        """TRA fixture itself validates against the schema."""
        schema = _load_schema("task_result_artifact.schema.json")
        tra = _make_tra(
            status="COMPLETED",
            deliverables=[{"id": "d1", "artifact_ref": "out/d1.md"}],
        )
        jsonschema.validate(instance=tra, schema=schema)


# ===========================================================================
# All outcome states are mapped (exhaustive)
# ===========================================================================


class TestOutcomeStateMapping:
    @pytest.mark.parametrize(
        ("outcome", "expected_state"),
        [
            ("COMPLETED", "CLOSED"),
            ("PARTIAL", "CLOSED_PARTIAL"),
            ("DECLINED", "NEEDS_REROUTE"),
            ("WITHDRAWN", "NEEDS_REROUTE"),
            ("BLOCKED", "BLOCKED"),
            ("FAILED", "FAILED"),
        ],
    )
    def test_all_statuses_mapped(
        self, outcome: str, expected_state: str
    ) -> None:
        assert resolve_task_state(outcome) == expected_state
