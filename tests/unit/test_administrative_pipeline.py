"""Unit tests for Administrative Pipeline activation slice.

Tests the three pure functions:
1. Earl routing (deterministic portfolio-to-earl mapping)
2. Capability filtering (tool registry validation)
3. Schema validation (TAR + execution_program contract compliance)

All tests are pure unit tests with NO infrastructure dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

# Import the pure functions under test
from scripts.run_administrative_pipeline import (
    KNOWN_EARL_IDS,
    build_execution_program,
    filter_eligible_tools,
    route_earl,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "contracts"

BIFRONS_ID = "3af355a1-9026-4d4a-9294-9964bf230751"
RAUM_ID = "07fec517-1529-4499-aa55-b0a9faaf47b1"
HALPHAS_ID = "3836da54-2509-4dc1-be4d-0c321cd66e58"


@pytest.fixture()
def routing_table() -> dict:
    return {
        "schema_version": "1.0",
        "default_earl_id": BIFRONS_ID,
        "portfolio_to_earl": {
            "acquisition": RAUM_ID,
            "transformation": BIFRONS_ID,
            "knowledge": BIFRONS_ID,
            "military": HALPHAS_ID,
        },
    }


@pytest.fixture()
def tool_registry() -> dict:
    return {
        "schema_version": "1.0",
        "updated_at": "2026-01-29T00:00:00Z",
        "tools": [
            {
                "tool_id": "cluster:alpha",
                "tool_class": "HUMAN_CLUSTER",
                "capabilities": ["doc_drafting", "review"],
                "status": "AVAILABLE",
            },
            {
                "tool_id": "cluster:beta",
                "tool_class": "HUMAN_CLUSTER",
                "capabilities": ["doc_drafting"],
                "status": "AVAILABLE",
            },
            {
                "tool_id": "cluster:offline",
                "tool_class": "HUMAN_CLUSTER",
                "capabilities": ["doc_drafting", "review", "coding"],
                "status": "UNAVAILABLE",
            },
            {
                "tool_id": "tool:scanner",
                "tool_class": "DIGITAL_TOOL",
                "capabilities": ["scanning", "ocr"],
                "status": "AVAILABLE",
            },
        ],
    }


@pytest.fixture()
def minimal_handoff() -> dict:
    return {
        "schema_version": "1.0",
        "handoff_id": "handoff-test-001",
        "created_at": "2026-01-29T00:00:00Z",
        "references": {
            "session_id": "session-test",
            "mandate_id": "mandate-test-001",
            "motion_id": "motion-test-001",
            "rfp_id": "rfp-test-001",
            "award_id": "award-test-001",
            "selected_duke_id": "duke-agares-001",
            "selected_proposal_id": "proposal-test-001",
        },
        "work_package": {
            "title": "Test Work Package",
            "summary": "Produce a test deliverable for validation.",
            "deliverables": [
                {
                    "id": "deliv-1",
                    "title": "Test Document",
                    "acceptance_criteria": [
                        "Document is valid markdown",
                        "Covers all requirements",
                    ],
                }
            ],
            "constraints": {
                "deadline_iso": "2026-02-15",
                "budget_cap": {"amount": 0, "currency": "USD"},
                "explicit_exclusions": ["NO_PII"],
            },
        },
        "portfolio_context": {
            "portfolios": ["transformation", "knowledge"],
            "portfolios_involved_count": 2,
        },
        "admin_directives": {
            "require_task_contracts": True,
            "require_result_artifacts": True,
            "escalation_policy_id": "policy-admin-v1",
        },
    }


def _load_schema(name: str) -> dict:
    schema_path = SCHEMAS_DIR / name
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ===========================================================================
# 1) Routing tests
# ===========================================================================


class TestRouteEarl:
    """Tests for Earl routing logic."""

    def test_known_portfolio_routes_to_correct_earl(
        self, routing_table: dict
    ) -> None:
        earl_id, matched, fallback = route_earl(
            ["acquisition"], routing_table
        )
        assert earl_id == RAUM_ID
        assert matched == "acquisition"
        assert fallback is False

    def test_first_matching_portfolio_wins(
        self, routing_table: dict
    ) -> None:
        earl_id, matched, fallback = route_earl(
            ["military", "acquisition"], routing_table
        )
        assert earl_id == HALPHAS_ID
        assert matched == "military"
        assert fallback is False

    def test_unknown_portfolio_falls_back_to_default(
        self, routing_table: dict
    ) -> None:
        earl_id, matched, fallback = route_earl(
            ["unknown_domain"], routing_table
        )
        assert earl_id == BIFRONS_ID
        assert matched == "__default__"
        assert fallback is True

    def test_empty_portfolios_falls_back_to_default(
        self, routing_table: dict
    ) -> None:
        earl_id, matched, fallback = route_earl([], routing_table)
        assert earl_id == BIFRONS_ID
        assert fallback is True

    def test_invalid_earl_id_in_routing_table_raises(self) -> None:
        bad_table = {
            "schema_version": "1.0",
            "default_earl_id": BIFRONS_ID,
            "portfolio_to_earl": {
                "test": "not-a-real-earl-id",
            },
        }
        with pytest.raises(ValueError, match="unknown Earl ID"):
            route_earl(["test"], bad_table)

    def test_invalid_default_earl_id_raises(self) -> None:
        bad_table = {
            "schema_version": "1.0",
            "default_earl_id": "not-a-real-earl-id",
            "portfolio_to_earl": {},
        }
        with pytest.raises(ValueError, match="not a known Earl"):
            route_earl(["anything"], bad_table)

    def test_no_default_and_no_match_raises(self) -> None:
        bad_table = {
            "schema_version": "1.0",
            "portfolio_to_earl": {},
        }
        with pytest.raises(ValueError, match="No portfolio matched"):
            route_earl(["anything"], bad_table)


# ===========================================================================
# 2) Capability filter tests
# ===========================================================================


class TestFilterEligibleTools:
    """Tests for tool capability filtering."""

    def test_matching_capabilities_returns_tools(
        self, tool_registry: dict
    ) -> None:
        result = filter_eligible_tools(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=tool_registry,
        )
        # cluster:alpha and cluster:beta match; cluster:offline is UNAVAILABLE
        assert len(result) == 2
        tool_ids = {t["tool_id"] for t in result}
        assert tool_ids == {"cluster:alpha", "cluster:beta"}

    def test_stricter_capabilities_filters_further(
        self, tool_registry: dict
    ) -> None:
        result = filter_eligible_tools(
            required_capabilities=["doc_drafting", "review"],
            tool_class="HUMAN_CLUSTER",
            registry=tool_registry,
        )
        # Only cluster:alpha has both; cluster:beta lacks "review"
        assert len(result) == 1
        assert result[0]["tool_id"] == "cluster:alpha"

    def test_unavailable_tools_excluded(
        self, tool_registry: dict
    ) -> None:
        result = filter_eligible_tools(
            required_capabilities=["doc_drafting", "review", "coding"],
            tool_class="HUMAN_CLUSTER",
            registry=tool_registry,
        )
        # cluster:offline has all caps but is UNAVAILABLE
        assert len(result) == 0

    def test_wrong_tool_class_returns_empty(
        self, tool_registry: dict
    ) -> None:
        result = filter_eligible_tools(
            required_capabilities=["doc_drafting"],
            tool_class="DIGITAL_TOOL",
            registry=tool_registry,
        )
        # No DIGITAL_TOOL with doc_drafting
        assert len(result) == 0

    def test_digital_tool_class_matches(
        self, tool_registry: dict
    ) -> None:
        result = filter_eligible_tools(
            required_capabilities=["scanning"],
            tool_class="DIGITAL_TOOL",
            registry=tool_registry,
        )
        assert len(result) == 1
        assert result[0]["tool_id"] == "tool:scanner"

    def test_empty_registry_returns_empty(self) -> None:
        result = filter_eligible_tools(
            required_capabilities=["anything"],
            tool_class="HUMAN_CLUSTER",
            registry={"tools": []},
        )
        assert len(result) == 0

    def test_no_required_capabilities_matches_all_available(
        self, tool_registry: dict
    ) -> None:
        result = filter_eligible_tools(
            required_capabilities=[],
            tool_class="HUMAN_CLUSTER",
            registry=tool_registry,
        )
        # Empty set is subset of everything; 2 AVAILABLE HUMAN_CLUSTERs
        assert len(result) == 2


# ===========================================================================
# 3) Schema validation tests
# ===========================================================================


class TestSchemaValidation:
    """Tests that pipeline outputs validate against JSON schemas."""

    def test_tar_validates_against_schema(
        self,
        minimal_handoff: dict,
        tool_registry: dict,
    ) -> None:
        schema = _load_schema("task_activation_request.schema.json")
        eligible = filter_eligible_tools(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=tool_registry,
        )
        _, tars = build_execution_program(
            handoff=minimal_handoff,
            earl_id=BIFRONS_ID,
            matched_portfolio="transformation",
            routing_table_version="1.0",
            eligible_tools=eligible,
            tool_class="HUMAN_CLUSTER",
            required_capabilities=["doc_drafting"],
            response_hours=8,
        )
        assert len(tars) == 1
        jsonschema.validate(instance=tars[0], schema=schema)

    def test_execution_program_validates_against_schema(
        self,
        minimal_handoff: dict,
        tool_registry: dict,
    ) -> None:
        schema = _load_schema("execution_program.schema.json")
        eligible = filter_eligible_tools(
            required_capabilities=["doc_drafting"],
            tool_class="HUMAN_CLUSTER",
            registry=tool_registry,
        )
        program, _ = build_execution_program(
            handoff=minimal_handoff,
            earl_id=BIFRONS_ID,
            matched_portfolio="transformation",
            routing_table_version="1.0",
            eligible_tools=eligible,
            tool_class="HUMAN_CLUSTER",
            required_capabilities=["doc_drafting"],
            response_hours=8,
        )
        jsonschema.validate(instance=program, schema=schema)

    def test_tool_registry_validates_against_schema(
        self, tool_registry: dict
    ) -> None:
        schema = _load_schema("tool_registry.schema.json")
        jsonschema.validate(instance=tool_registry, schema=schema)

    def test_handoff_validates_against_schema(
        self, minimal_handoff: dict
    ) -> None:
        schema = _load_schema("administrative_handoff.schema.json")
        jsonschema.validate(instance=minimal_handoff, schema=schema)

    def test_invalid_tar_missing_required_field_fails(self) -> None:
        schema = _load_schema("task_activation_request.schema.json")
        invalid_tar = {"schema_version": "1.0", "tar_id": "tar-test"}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_tar, schema=schema)

    def test_invalid_tool_registry_bad_status_fails(self) -> None:
        schema = _load_schema("tool_registry.schema.json")
        invalid_registry = {
            "schema_version": "1.0",
            "updated_at": "2026-01-29T00:00:00Z",
            "tools": [
                {
                    "tool_id": "bad",
                    "tool_class": "HUMAN_CLUSTER",
                    "capabilities": [],
                    "status": "INVALID_STATUS",
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_registry, schema=schema)
