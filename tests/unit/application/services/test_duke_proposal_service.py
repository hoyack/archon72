"""Tests for DukeProposalService."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.duke_proposal_generation import (
    DukeProposalGeneratorProtocol,
)
from src.application.services.duke_proposal_service import (
    DukeProposalService,
    _duke_abbreviation,
)
from src.domain.models.duke_proposal import (
    DukeProposal,
    ProposalStatus,
)
from src.domain.models.rfp import (
    Deliverable,
    FunctionalRequirement,
    NonFunctionalRequirement,
    RequirementCategory,
    RequirementPriority,
    RFPDocument,
    RFPStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_PROPOSAL_MD = """# Proposal from Duke {duke_name}

## Executive Summary
Test proposal from {duke_name}.

## Approach Philosophy
Structured approach.

## Tactics

### T-{abbrev}-001: Test Tactic
- **Description:** Test tactic
- **Rationale:** Test rationale

## Risks

### R-{abbrev}-001: Test Risk
- **Description:** Test risk
- **Likelihood:** POSSIBLE
- **Impact:** MODERATE
- **Mitigation Strategy:** Test mitigation

## Resource Requests

### RR-{abbrev}-001: Staff Hours
- **Type:** HUMAN_HOURS
- **Description:** Staff hours

## Requirement Coverage
| Requirement ID | Type | Covered | Description | Tactic References | Confidence |
|---------------|------|---------|-------------|-------------------|------------|

## Deliverable Plan
| Deliverable ID | Approach | Tactic References | Duration | Dependencies |
|---------------|----------|-------------------|----------|--------------|

## Assumptions
- Test assumption

## Constraints Acknowledged
- Test constraint
"""


class EventCapture:
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


def _mk_rfp(**overrides: object) -> RFPDocument:
    defaults: dict[str, Any] = {
        "implementation_dossier_id": "eid-test-001",
        "mandate_id": "mandate-test-001",
        "status": RFPStatus.FINAL,
        "created_at": "2026-01-28T12:00:00Z",
        "motion_title": "Test Motion",
        "motion_text": "Implement governance improvements",
        "functional_requirements": [
            FunctionalRequirement(
                req_id="FR-TEST-001",
                description="Test functional requirement",
                priority=RequirementPriority.MUST,
                source_portfolio_id="portfolio_test",
            ),
        ],
        "non_functional_requirements": [
            NonFunctionalRequirement(
                req_id="NFR-TEST-001",
                category=RequirementCategory.RELIABILITY,
                description="Test non-functional requirement",
                source_portfolio_id="portfolio_test",
            ),
        ],
        "deliverables": [
            Deliverable(
                deliverable_id="D-TEST-001",
                name="Test Deliverable",
                description="A test deliverable",
            ),
        ],
        "constraints": [],
    }
    defaults.update(overrides)
    return RFPDocument(**defaults)


def _mk_duke(name: str = "Agares", archon_id: str = "aaa-001") -> dict:
    return {
        "id": archon_id,
        "name": name,
        "rank": "Duke",
        "branch": "administrative_senior",
        "role": f"Senior Director - {name}'s Domain",
        "backstory": f"Duke {name} is an expert.",
        "personality": "Strategic and methodical",
    }


def _mk_generated_proposal(
    duke_name: str = "Agares", rfp_id: str = "eid-test-001"
) -> DukeProposal:
    abbrev = _duke_abbreviation(duke_name)
    md = SAMPLE_PROPOSAL_MD.format(duke_name=duke_name, abbrev=abbrev)
    return DukeProposal(
        proposal_id=f"dprop-{abbrev.lower()}-001",
        duke_archon_id="aaa-001",
        duke_name=duke_name,
        duke_domain=f"Senior Director - {duke_name}'s Domain",
        duke_abbreviation=abbrev,
        rfp_id=rfp_id,
        mandate_id="mandate-test-001",
        status=ProposalStatus.GENERATED,
        created_at="2026-01-28T12:00:00Z",
        proposal_markdown=md,
        tactic_count=1,
        risk_count=1,
        resource_request_count=1,
        requirement_coverage_count=0,
        deliverable_plan_count=0,
        assumption_count=1,
        constraint_count=1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDukeAbbreviation:
    def test_normal_name(self) -> None:
        assert _duke_abbreviation("Agares") == "AGAR"

    def test_short_name(self) -> None:
        assert _duke_abbreviation("Aim") == "AIM"

    def test_lowercase(self) -> None:
        assert _duke_abbreviation("valefor") == "VALE"


class TestConstructor:
    def test_default_session_id(self) -> None:
        svc = DukeProposalService()
        assert svc.session_id.startswith("duke_")

    def test_custom_session_id(self) -> None:
        svc = DukeProposalService(session_id="my-session")
        assert svc.session_id == "my-session"


class TestSimulationMode:
    def test_generates_proposals_for_all_dukes(self) -> None:
        events = EventCapture()
        svc = DukeProposalService(event_sink=events)
        rfp = _mk_rfp()
        dukes = [_mk_duke("Agares"), _mk_duke("Valefor", "bbb-002")]

        proposals = svc._simulate_proposals(rfp, dukes)

        assert len(proposals) == 2
        assert proposals[0].duke_name == "Agares"
        assert proposals[1].duke_name == "Valefor"
        assert all(p.status == ProposalStatus.SIMULATION for p in proposals)

    def test_simulation_has_tactic_count(self) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = svc._simulate_proposals(rfp, dukes)

        assert proposals[0].tactic_count == 1

    def test_simulation_has_markdown(self) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = svc._simulate_proposals(rfp, dukes)

        assert "# Proposal from Duke Agares" in proposals[0].proposal_markdown
        assert "### T-AGAR-001" in proposals[0].proposal_markdown

    def test_simulation_covers_requirements(self) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = svc._simulate_proposals(rfp, dukes)

        # 1 FR + 1 NFR from _mk_rfp
        assert proposals[0].requirement_coverage_count == 2

    def test_simulation_covers_deliverables(self) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = svc._simulate_proposals(rfp, dukes)

        assert proposals[0].deliverable_plan_count == 1

    def test_simulation_emits_events(self) -> None:
        events = EventCapture()
        svc = DukeProposalService(event_sink=events)
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        svc._simulate_proposals(rfp, dukes)

        assert events.has_event("duke_proposal.started")
        assert events.has_event("duke_proposal.complete")
        started = events.get_events("duke_proposal.started")[0]
        assert started["mode"] == "simulation"


class TestGenerateAllProposals:
    @pytest.mark.asyncio
    async def test_successful_generation(self) -> None:
        events = EventCapture()
        mock_generator = AsyncMock(spec=DukeProposalGeneratorProtocol)
        mock_generator.generate_proposal.return_value = _mk_generated_proposal()

        svc = DukeProposalService(
            duke_proposal_generator=mock_generator,
            event_sink=events,
        )
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = await svc.generate_all_proposals(rfp, dukes)

        assert len(proposals) == 1
        assert proposals[0].status == ProposalStatus.GENERATED
        assert events.has_event("duke_proposal.started")
        assert events.has_event("duke_proposal.requested")
        assert events.has_event("duke_proposal.received")
        assert events.has_event("duke_proposal.complete")

    @pytest.mark.asyncio
    async def test_failure_creates_failed_proposal(self, monkeypatch) -> None:
        monkeypatch.setenv("DUKE_PROPOSAL_MAX_RETRIES", "1")
        events = EventCapture()
        mock_generator = AsyncMock(spec=DukeProposalGeneratorProtocol)
        mock_generator.generate_proposal.side_effect = RuntimeError("LLM error")

        svc = DukeProposalService(
            duke_proposal_generator=mock_generator,
            event_sink=events,
        )
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = await svc.generate_all_proposals(rfp, dukes)

        assert len(proposals) == 1
        assert proposals[0].status == ProposalStatus.FAILED
        assert "LLM error" in proposals[0].failure_reason
        assert events.has_event("duke_proposal.failed")

    @pytest.mark.asyncio
    async def test_no_generator_creates_failed(self, monkeypatch) -> None:
        monkeypatch.setenv("DUKE_PROPOSAL_MAX_RETRIES", "1")
        events = EventCapture()

        svc = DukeProposalService(event_sink=events)
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = await svc.generate_all_proposals(rfp, dukes)

        assert len(proposals) == 1
        assert proposals[0].status == ProposalStatus.FAILED

    @pytest.mark.asyncio
    async def test_multiple_dukes_sequential(self) -> None:
        events = EventCapture()
        mock_generator = AsyncMock(spec=DukeProposalGeneratorProtocol)

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            name = kwargs.get("duke_name", "Unknown")
            return _mk_generated_proposal(duke_name=name)

        mock_generator.generate_proposal.side_effect = side_effect

        svc = DukeProposalService(
            duke_proposal_generator=mock_generator,
            event_sink=events,
        )
        rfp = _mk_rfp()
        dukes = [_mk_duke("Agares"), _mk_duke("Valefor", "bbb-002")]

        proposals = await svc.generate_all_proposals(rfp, dukes)

        assert len(proposals) == 2
        assert events.count_event("duke_proposal.requested") == 2
        assert events.count_event("duke_proposal.received") == 2

    @pytest.mark.asyncio
    async def test_retryable_error_retries(self, monkeypatch) -> None:
        monkeypatch.setenv("DUKE_PROPOSAL_MAX_RETRIES", "3")
        monkeypatch.setenv("DUKE_PROPOSAL_BACKOFF_BASE_SECONDS", "0.01")
        events = EventCapture()
        mock_generator = AsyncMock(spec=DukeProposalGeneratorProtocol)

        # First call fails with retryable error, second succeeds
        mock_generator.generate_proposal.side_effect = [
            RuntimeError("service temporarily unavailable"),
            _mk_generated_proposal(),
        ]

        svc = DukeProposalService(
            duke_proposal_generator=mock_generator,
            event_sink=events,
        )
        rfp = _mk_rfp()
        dukes = [_mk_duke()]

        proposals = await svc.generate_all_proposals(rfp, dukes)

        assert len(proposals) == 1
        assert proposals[0].status == ProposalStatus.GENERATED
        assert events.has_event("duke_proposal.retry")


class TestSaveProposals:
    def test_saves_json_and_md(self, tmp_path: Path) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        proposals = [
            _mk_generated_proposal("Agares"),
            _mk_generated_proposal("Valefor"),
        ]

        proposals_dir = svc.save_proposals(proposals, rfp, tmp_path)

        assert proposals_dir == tmp_path / "proposals_inbox"
        assert proposals_dir.exists()
        # JSON sidecars
        assert (proposals_dir / "proposal_agares.json").exists()
        assert (proposals_dir / "proposal_valefor.json").exists()
        # Markdown files
        assert (proposals_dir / "proposal_agares.md").exists()
        assert (proposals_dir / "proposal_valefor.md").exists()
        # Summary
        assert (proposals_dir / "proposal_summary.json").exists()

    def test_json_has_counts(self, tmp_path: Path) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        proposals = [_mk_generated_proposal("Agares")]

        proposals_dir = svc.save_proposals(proposals, rfp, tmp_path)

        with open(proposals_dir / "proposal_agares.json") as f:
            data = json.load(f)
        assert data["duke"]["name"] == "Agares"
        assert data["artifact_type"] == "duke_proposal"
        assert "counts" in data
        assert data["counts"]["tactics"] == 1
        assert data["counts"]["risks"] == 1

    def test_failed_proposal_no_md(self, tmp_path: Path) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        failed = DukeProposal(
            proposal_id="dprop-agar-fail",
            duke_archon_id="aaa-001",
            duke_name="Agares",
            duke_domain="Test Domain",
            duke_abbreviation="AGAR",
            rfp_id="eid-test-001",
            mandate_id="mandate-test-001",
            status=ProposalStatus.FAILED,
            created_at="2026-01-28T12:00:00Z",
            failure_reason="Connection timeout",
        )
        proposals = [failed]

        proposals_dir = svc.save_proposals(proposals, rfp, tmp_path)

        # JSON should exist
        assert (proposals_dir / "proposal_agares.json").exists()
        # Markdown should NOT exist (empty proposal_markdown)
        assert not (proposals_dir / "proposal_agares.md").exists()

    def test_inbox_manifest_created(self, tmp_path: Path) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        proposals = [
            _mk_generated_proposal("Agares"),
            _mk_generated_proposal("Valefor"),
        ]

        proposals_dir = svc.save_proposals(proposals, rfp, tmp_path)

        manifest_path = proposals_dir / "inbox_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["artifact_type"] == "duke_proposals_inbox_manifest"
        assert manifest["rfp_id"] == rfp.implementation_dossier_id
        assert manifest["mandate_id"] == rfp.mandate_id
        assert manifest["total_dukes"] == 2

    def test_inbox_manifest_has_markdown_file(self, tmp_path: Path) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        proposals = [_mk_generated_proposal("Agares")]

        proposals_dir = svc.save_proposals(proposals, rfp, tmp_path)

        with open(proposals_dir / "inbox_manifest.json") as f:
            manifest = json.load(f)

        sub = manifest["submissions"][0]
        assert sub["proposal_file"] == "proposal_agares.json"
        assert sub["proposal_markdown_file"] == "proposal_agares.md"

    def test_inbox_manifest_failed_no_markdown_file(self, tmp_path: Path) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        failed = DukeProposal(
            proposal_id="dprop-agar-fail",
            duke_archon_id="aaa-001",
            duke_name="Agares",
            duke_domain="Test Domain",
            duke_abbreviation="AGAR",
            rfp_id="eid-test-001",
            mandate_id="mandate-test-001",
            status=ProposalStatus.FAILED,
            created_at="2026-01-28T12:00:00Z",
            failure_reason="Connection timeout",
        )
        proposals = [failed]

        proposals_dir = svc.save_proposals(proposals, rfp, tmp_path)

        with open(proposals_dir / "inbox_manifest.json") as f:
            manifest = json.load(f)

        sub = manifest["submissions"][0]
        assert sub["status"] == "FAILED"
        assert sub["failure_reason"] == "Connection timeout"
        assert "proposal_markdown_file" not in sub

    def test_inbox_manifest_includes_llm_info(self, tmp_path: Path) -> None:
        svc = DukeProposalService()
        rfp = _mk_rfp()
        proposal = _mk_generated_proposal("Agares")
        proposal.llm_provider = "ollama"
        proposal.llm_model = "qwen3:latest"
        proposals = [proposal]

        proposals_dir = svc.save_proposals(proposals, rfp, tmp_path)

        with open(proposals_dir / "inbox_manifest.json") as f:
            manifest = json.load(f)

        sub = manifest["submissions"][0]
        assert sub["llm_provider"] == "ollama"
        assert sub["llm_model"] == "qwen3:latest"


class TestLoadRFP:
    def test_loads_rfp_from_disk(self, tmp_path: Path) -> None:
        rfp = _mk_rfp()
        rfp_path = tmp_path / "rfp.json"
        with open(rfp_path, "w") as f:
            json.dump(rfp.to_dict(), f)

        loaded = DukeProposalService.load_rfp(rfp_path)

        assert loaded.implementation_dossier_id == rfp.implementation_dossier_id
        assert loaded.mandate_id == rfp.mandate_id
        assert loaded.status == rfp.status
        assert len(loaded.functional_requirements) == 1
