"""Tests for Duke Proposal domain models."""

from __future__ import annotations

from src.domain.models.duke_proposal import (
    DUKE_PROPOSAL_SCHEMA_VERSION,
    DukeProposal,
    DukeProposalSummary,
    ProposalStatus,
)

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

SAMPLE_MARKDOWN = """# Proposal from Duke Agares

## Executive Summary
Comprehensive market disruption approach.

## Approach Philosophy
Move fast, break paradigms.

## Tactics

### T-AGAR-001: Disruptive Market Analysis
- **Description:** Disruptive market analysis
- **Rationale:** Identify paradigm shifts early
- **Prerequisites:** None
- **Dependencies:** None
- **Estimated Duration:** P7D
- **Owner:** duke_agares

## Risks

### R-AGAR-001: Market Resistance
- **Description:** Market resistance to paradigm shift
- **Likelihood:** POSSIBLE
- **Impact:** MODERATE
- **Mitigation Strategy:** Gradual rollout with fallback plan

## Resource Requests

### RR-AGAR-001: Analysis Compute
- **Type:** COMPUTE
- **Description:** Analysis compute cluster
- **Justification:** Needed for large-scale data processing
- **Required By:** 2026-03-01T00:00:00Z
- **Priority:** HIGH

## Capacity Commitment
| Field | Value |
|-------|-------|
| Portfolio ID | duke_agares |
| Committed Units | 40.0 |
| Unit Label | hours |
| Confidence | MEDIUM |

## Requirement Coverage
| Requirement ID | Type | Covered | Description | Tactic References | Confidence |
|---------------|------|---------|-------------|-------------------|------------|
| FR-AGAR-001 | functional | Yes | Covered by tactic T-AGAR-001 | T-AGAR-001 | HIGH |

## Deliverable Plan
| Deliverable ID | Approach | Tactic References | Duration | Dependencies |
|---------------|----------|-------------------|----------|--------------|
| D-001 | Iterative delivery | T-AGAR-001 | P14D | |

## Assumptions
- Stable governance framework

## Constraints Acknowledged
- Budget ceiling applies
"""


def _mk_proposal(**overrides: object) -> DukeProposal:
    defaults: dict = {
        "proposal_id": "dprop-agar-001",
        "duke_archon_id": "caa48223-c30c-4d07-aac1-3c04c842eb57",
        "duke_name": "Agares",
        "duke_domain": "Senior Director - Market Disruption & Paradigm Shifting",
        "duke_abbreviation": "AGAR",
        "rfp_id": "eid-abc123",
        "mandate_id": "mandate-001",
        "status": ProposalStatus.GENERATED,
        "created_at": "2026-01-28T12:00:00Z",
        "proposal_markdown": SAMPLE_MARKDOWN,
        "tactic_count": 1,
        "risk_count": 1,
        "resource_request_count": 1,
        "requirement_coverage_count": 1,
        "deliverable_plan_count": 1,
        "assumption_count": 1,
        "constraint_count": 1,
        "llm_model": "qwen3:latest",
        "llm_provider": "ollama",
    }
    defaults.update(overrides)
    return DukeProposal(**defaults)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestProposalStatus:
    def test_values(self) -> None:
        assert ProposalStatus.GENERATED.value == "GENERATED"
        assert ProposalStatus.FAILED.value == "FAILED"
        assert ProposalStatus.SIMULATION.value == "SIMULATION"

    def test_str_enum(self) -> None:
        assert isinstance(ProposalStatus.GENERATED, str)
        assert ProposalStatus("GENERATED") == ProposalStatus.GENERATED


# ---------------------------------------------------------------------------
# DukeProposal tests
# ---------------------------------------------------------------------------


class TestDukeProposal:
    def test_roundtrip(self) -> None:
        """JSON sidecar roundtrip (proposal_markdown lives in .md file, not JSON)."""
        p = _mk_proposal()
        d = p.to_dict()
        p2 = DukeProposal.from_dict(d)

        assert p2.proposal_id == p.proposal_id
        assert p2.duke_archon_id == p.duke_archon_id
        assert p2.duke_name == p.duke_name
        assert p2.duke_domain == p.duke_domain
        assert p2.duke_abbreviation == p.duke_abbreviation
        assert p2.rfp_id == p.rfp_id
        assert p2.mandate_id == p.mandate_id
        assert p2.status == p.status
        assert p2.created_at == p.created_at
        # proposal_markdown is NOT in the JSON sidecar — it's saved as .md
        assert p2.proposal_markdown == ""
        assert p2.tactic_count == p.tactic_count
        assert p2.risk_count == p.risk_count
        assert p2.resource_request_count == p.resource_request_count
        assert p2.requirement_coverage_count == p.requirement_coverage_count
        assert p2.deliverable_plan_count == p.deliverable_plan_count
        assert p2.assumption_count == p.assumption_count
        assert p2.constraint_count == p.constraint_count
        assert p2.llm_model == p.llm_model
        assert p2.llm_provider == p.llm_provider

    def test_to_dict_has_counts(self) -> None:
        p = _mk_proposal()
        d = p.to_dict()
        assert "counts" in d
        assert d["counts"]["tactics"] == 1
        assert d["counts"]["risks"] == 1
        assert d["counts"]["resource_requests"] == 1
        assert d["counts"]["requirement_coverage"] == 1
        assert d["counts"]["deliverable_plans"] == 1
        assert d["counts"]["assumptions"] == 1
        assert d["counts"]["constraints"] == 1

    def test_validate_ok(self) -> None:
        p = _mk_proposal()
        assert p.validate() == []

    def test_validate_missing_required_fields(self) -> None:
        p = _mk_proposal(
            proposal_id="",
            duke_archon_id="",
            duke_name="",
            rfp_id="",
            mandate_id="",
            created_at="",
        )
        errors = p.validate()
        assert len(errors) >= 5

    def test_generated_requires_tactic_count(self) -> None:
        p = _mk_proposal(tactic_count=0)
        errors = p.validate()
        assert any("at least one tactic" in e for e in errors)

    def test_generated_requires_nonempty_markdown(self) -> None:
        p = _mk_proposal(proposal_markdown="")
        errors = p.validate()
        assert any("proposal_markdown" in e for e in errors)

    def test_failed_no_tactic_requirement(self) -> None:
        p = _mk_proposal(
            status=ProposalStatus.FAILED,
            tactic_count=0,
            proposal_markdown="",
        )
        errors = p.validate()
        assert not any("at least one tactic" in e for e in errors)
        assert not any("proposal_markdown" in e for e in errors)

    def test_simulation_no_tactic_requirement(self) -> None:
        p = _mk_proposal(
            status=ProposalStatus.SIMULATION,
            tactic_count=0,
            proposal_markdown="",
        )
        errors = p.validate()
        assert not any("at least one tactic" in e for e in errors)

    def test_artifact_type_in_dict(self) -> None:
        p = _mk_proposal()
        d = p.to_dict()
        assert d["artifact_type"] == "duke_proposal"

    def test_schema_version(self) -> None:
        p = _mk_proposal()
        assert p.schema_version == DUKE_PROPOSAL_SCHEMA_VERSION
        assert p.schema_version == "2.0"
        d = p.to_dict()
        assert d["schema_version"] == DUKE_PROPOSAL_SCHEMA_VERSION

    def test_duke_nested_in_dict(self) -> None:
        p = _mk_proposal()
        d = p.to_dict()
        assert "duke" in d
        assert d["duke"]["name"] == "Agares"
        assert d["duke"]["abbreviation"] == "AGAR"

    def test_trace_nested_in_dict(self) -> None:
        p = _mk_proposal()
        d = p.to_dict()
        assert "trace" in d
        assert d["trace"]["llm_model"] == "qwen3:latest"
        assert d["trace"]["llm_provider"] == "ollama"

    def test_defaults(self) -> None:
        p = DukeProposal(
            proposal_id="p1",
            duke_archon_id="a1",
            duke_name="Test",
            duke_domain="Testing",
            duke_abbreviation="TEST",
            rfp_id="rfp1",
            mandate_id="m1",
            status=ProposalStatus.FAILED,
            created_at="2026-01-01T00:00:00Z",
        )
        assert p.proposal_markdown == ""
        assert p.tactic_count == 0
        assert p.risk_count == 0
        assert p.resource_request_count == 0
        assert p.requirement_coverage_count == 0
        assert p.deliverable_plan_count == 0
        assert p.assumption_count == 0
        assert p.constraint_count == 0


# ---------------------------------------------------------------------------
# DukeProposalSummary tests
# ---------------------------------------------------------------------------


class TestDukeProposalSummary:
    def test_from_proposals(self) -> None:
        p1 = _mk_proposal()
        p2 = _mk_proposal(
            proposal_id="dprop-vale-001",
            duke_name="Valefor",
            duke_abbreviation="VALE",
            status=ProposalStatus.FAILED,
            tactic_count=0,
            risk_count=0,
            resource_request_count=0,
            proposal_markdown="",
        )
        p3 = _mk_proposal(
            proposal_id="dprop-barb-001",
            duke_name="Barbatos",
            duke_abbreviation="BARB",
            status=ProposalStatus.SIMULATION,
        )

        summary = DukeProposalSummary.from_proposals(
            proposals=[p1, p2, p3],
            rfp_id="eid-abc123",
            mandate_id="mandate-001",
            created_at="2026-01-28T12:00:00Z",
        )

        assert summary.total_proposals == 3
        assert summary.generated_count == 1
        assert summary.failed_count == 1
        assert summary.simulation_count == 1
        assert summary.total_tactics == 2  # p1 + p3 each have 1
        assert summary.total_risks == 2
        assert "Agares" in summary.duke_names
        assert "Valefor" in summary.duke_names
        assert "Barbatos" in summary.duke_names

    def test_to_dict(self) -> None:
        summary = DukeProposalSummary(
            rfp_id="eid-abc123",
            mandate_id="mandate-001",
            created_at="2026-01-28T12:00:00Z",
            total_proposals=2,
            generated_count=1,
            failed_count=1,
            duke_names=["Agares", "Valefor"],
        )
        d = summary.to_dict()
        assert d["artifact_type"] == "duke_proposal_summary"
        assert d["total_proposals"] == 2
        assert d["duke_names"] == ["Agares", "Valefor"]

    def test_roundtrip(self) -> None:
        p1 = _mk_proposal()
        summary = DukeProposalSummary.from_proposals(
            proposals=[p1],
            rfp_id="eid-abc123",
            mandate_id="mandate-001",
            created_at="2026-01-28T12:00:00Z",
        )
        d = summary.to_dict()
        s2 = DukeProposalSummary.from_dict(d)
        assert s2.total_proposals == summary.total_proposals
        assert s2.duke_names == summary.duke_names
        assert s2.rfp_id == summary.rfp_id
