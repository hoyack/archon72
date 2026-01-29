"""Unit tests for task reroute logic.

Tests the refusal loop: decline -> reroute -> (maybe) decline again -> escalation.

All tests are pure unit tests with NO infrastructure dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from scripts.reroute_task import (
    build_exclusion_set,
    build_reroute_tar,
    check_max_attempts,
    filter_reroute_candidates,
    select_tool,
    update_task_state_for_exhaustion,
    update_task_state_for_reroute,
    validate_reroute_precondition,
)

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "contracts"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_task_state(
    *,
    state: str = "NEEDS_REROUTE",
    attempt_count: int = 0,
    attempt_history: list | None = None,
    excluded_tools: list | None = None,
    reroute_policy: dict | None = None,
) -> dict:
    """Build a minimal task state for reroute testing."""
    result = {
        "schema_version": "1.0",
        "task_id": "task-test-001",
        "program_id": "program-test-001",
        "tar_id": "tar-original-001",
        "tra_id": "tra-declined-001",
        "last_updated_at": "2026-01-29T14:00:00Z",
        "state": state,
        "last_outcome_status": "DECLINED",
        "blockers": [],
        "deliverables": [],
        "escalations": [],
        "attempt_count": attempt_count,
        "attempt_history": attempt_history or [],
        "excluded_tools": excluded_tools or [],
        "reroute_policy": reroute_policy
        or {"max_attempts": 3, "escalate_on_exhaustion": True},
    }
    return result


def _make_registry(*tools: dict) -> dict:
    """Build a tool registry from tool dicts."""
    return {
        "schema_version": "1.0",
        "updated_at": "2026-01-29T00:00:00Z",
        "tools": list(tools),
    }


def _tool(
    tool_id: str,
    *,
    capabilities: list[str] | None = None,
    status: str = "AVAILABLE",
    tool_class: str = "HUMAN_CLUSTER",
) -> dict:
    return {
        "tool_id": tool_id,
        "tool_class": tool_class,
        "capabilities": capabilities or ["doc_drafting"],
        "status": status,
    }


def _make_program(
    *,
    program_id: str = "program-test-001",
    task_id: str = "task-test-001",
) -> dict:
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
                "task_id": task_id,
                "title": "Test Task",
                "intent": "Produce test deliverable",
                "required_capabilities": ["doc_drafting"],
                "acceptance_criteria": ["Document produced"],
                "constraints": [],
                "activation": {
                    "earl_id": "earl-test",
                    "target_tool_class": "HUMAN_CLUSTER",
                    "eligible_tools": ["cluster:alpha"],
                    "priority": "NORMAL",
                },
            }
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
# 1) Round-robin selection: A tried, B selected
# ===========================================================================


class TestRoundRobinSelection:
    def test_skips_already_tried_tool(self) -> None:
        registry = _make_registry(
            _tool("cluster:alpha"),
            _tool("cluster:beta"),
            _tool("cluster:gamma"),
        )
        excluded = {"cluster:alpha"}
        candidates = filter_reroute_candidates(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=registry,
            excluded_tool_ids=excluded,
        )
        selected = select_tool(candidates, "round_robin")
        assert selected is not None
        assert selected["tool_id"] == "cluster:beta"

    def test_stable_ordering_by_tool_id(self) -> None:
        registry = _make_registry(
            _tool("cluster:gamma"),
            _tool("cluster:alpha"),
            _tool("cluster:beta"),
        )
        candidates = filter_reroute_candidates(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=registry,
            excluded_tool_ids=set(),
        )
        # Sorted by tool_id: alpha, beta, gamma
        assert [c["tool_id"] for c in candidates] == [
            "cluster:alpha",
            "cluster:beta",
            "cluster:gamma",
        ]

    def test_exclusion_set_built_from_history(self) -> None:
        state = _make_task_state(
            attempt_history=[
                {
                    "tar_id": "tar-1",
                    "tool_id": "cluster:alpha",
                    "created_at": "2026-01-29T14:00:00Z",
                },
            ],
            excluded_tools=["cluster:alpha"],
        )
        excluded = build_exclusion_set(state)
        assert excluded == {"cluster:alpha"}


# ===========================================================================
# 2) No duplicates: A and B tried, C selected, then exhausted
# ===========================================================================


class TestNoDuplicates:
    def test_two_excluded_selects_third(self) -> None:
        registry = _make_registry(
            _tool("cluster:alpha"),
            _tool("cluster:beta"),
            _tool("cluster:gamma"),
        )
        excluded = {"cluster:alpha", "cluster:beta"}
        candidates = filter_reroute_candidates(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=registry,
            excluded_tool_ids=excluded,
        )
        assert len(candidates) == 1
        assert candidates[0]["tool_id"] == "cluster:gamma"

    def test_all_excluded_returns_empty(self) -> None:
        registry = _make_registry(
            _tool("cluster:alpha"),
            _tool("cluster:beta"),
        )
        excluded = {"cluster:alpha", "cluster:beta"}
        candidates = filter_reroute_candidates(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=registry,
            excluded_tool_ids=excluded,
        )
        assert len(candidates) == 0

    def test_select_on_empty_returns_none(self) -> None:
        assert select_tool([], "round_robin") is None


# ===========================================================================
# 3) Capability enforcement during reroute
# ===========================================================================


class TestCapabilityEnforcement:
    def test_tool_without_required_capability_excluded(self) -> None:
        registry = _make_registry(
            _tool("cluster:alpha", capabilities=["doc_drafting"]),
            _tool("cluster:beta", capabilities=["coding"]),
        )
        candidates = filter_reroute_candidates(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=registry,
            excluded_tool_ids=set(),
        )
        assert len(candidates) == 1
        assert candidates[0]["tool_id"] == "cluster:alpha"

    def test_unavailable_tool_excluded(self) -> None:
        registry = _make_registry(
            _tool("cluster:alpha", status="UNAVAILABLE"),
            _tool("cluster:beta"),
        )
        candidates = filter_reroute_candidates(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=registry,
            excluded_tool_ids=set(),
        )
        assert len(candidates) == 1
        assert candidates[0]["tool_id"] == "cluster:beta"

    def test_wrong_class_excluded(self) -> None:
        registry = _make_registry(
            _tool("cluster:alpha", tool_class="DIGITAL_TOOL"),
        )
        candidates = filter_reroute_candidates(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=registry,
            excluded_tool_ids=set(),
        )
        assert len(candidates) == 0


# ===========================================================================
# 4) Exhaustion: no eligible tools -> BLOCKED + escalation
# ===========================================================================


class TestExhaustion:
    def test_exhaustion_sets_blocked_state(self) -> None:
        state = _make_task_state()
        updated = update_task_state_for_exhaustion(
            state, "REROUTE_EXHAUSTED", "2026-01-29T15:00:00Z"
        )
        assert updated["state"] == "BLOCKED"
        assert len(updated["escalations"]) == 1
        assert updated["escalations"][0]["reason"] == "REROUTE_EXHAUSTED"
        assert updated["escalations"][0]["to"] == "DUKE"

    def test_max_attempts_reached_detected(self) -> None:
        state = _make_task_state(
            attempt_count=3,
            reroute_policy={"max_attempts": 3, "escalate_on_exhaustion": True},
        )
        assert check_max_attempts(state) is True

    def test_under_max_attempts_not_reached(self) -> None:
        state = _make_task_state(
            attempt_count=1,
            reroute_policy={"max_attempts": 3, "escalate_on_exhaustion": True},
        )
        assert check_max_attempts(state) is False

    def test_max_attempts_exhaustion_sets_correct_reason(self) -> None:
        state = _make_task_state()
        updated = update_task_state_for_exhaustion(
            state, "REROUTE_MAX_ATTEMPTS_REACHED", "2026-01-29T15:00:00Z"
        )
        assert updated["escalations"][0]["reason"] == "REROUTE_MAX_ATTEMPTS_REACHED"


# ===========================================================================
# 5) Schema validation
# ===========================================================================


class TestSchemaValidation:
    def test_reroute_tar_validates_against_schema(self) -> None:
        schema = _load_schema("task_activation_request.schema.json")
        state = _make_task_state()
        program = _make_program()
        selected = _tool("cluster:beta")

        tar = build_reroute_tar(state, program, selected, response_hours=8)
        jsonschema.validate(instance=tar, schema=schema)

    def test_updated_task_state_validates_against_schema(self) -> None:
        schema = _load_schema("task_state.schema.json")
        state = _make_task_state()
        updated = update_task_state_for_reroute(
            state,
            "tar-new-001",
            "cluster:beta",
            "2026-01-29T15:00:00Z",
        )
        jsonschema.validate(instance=updated, schema=schema)

    def test_exhausted_task_state_validates_against_schema(self) -> None:
        schema = _load_schema("task_state.schema.json")
        state = _make_task_state()
        updated = update_task_state_for_exhaustion(
            state, "REROUTE_EXHAUSTED", "2026-01-29T15:00:00Z"
        )
        jsonschema.validate(instance=updated, schema=schema)


# ===========================================================================
# Precondition checks
# ===========================================================================


class TestPreconditions:
    def test_needs_reroute_state_passes(self) -> None:
        state = _make_task_state(state="NEEDS_REROUTE")
        validate_reroute_precondition(state)  # should not raise

    def test_closed_state_rejected(self) -> None:
        state = _make_task_state(state="CLOSED")
        with pytest.raises(ValueError, match="NEEDS_REROUTE"):
            validate_reroute_precondition(state)

    def test_blocked_state_rejected(self) -> None:
        state = _make_task_state(state="BLOCKED")
        with pytest.raises(ValueError, match="NEEDS_REROUTE"):
            validate_reroute_precondition(state)

    def test_reroute_updates_attempt_count(self) -> None:
        state = _make_task_state(attempt_count=1)
        updated = update_task_state_for_reroute(
            state, "tar-new", "cluster:beta", "2026-01-29T15:00:00Z"
        )
        assert updated["attempt_count"] == 2
        assert len(updated["attempt_history"]) == 1
        assert updated["attempt_history"][0]["tool_id"] == "cluster:beta"
        assert updated["state"] == "ACTIVATION_SENT"
