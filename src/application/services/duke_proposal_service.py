"""Service for generating Duke implementation proposals from finalized RFPs.

Orchestrates the competitive proposal generation stage where all Administrative
Dukes read a finalized Executive RFP and each produce a complete implementation
proposal applying their unique domain expertise.

Output Structure:
    <outdir>/<rfp_session_id>/mandates/<mandate_id>/proposals_inbox/
    ├── inbox_manifest.json
    ├── proposal_summary.json
    ├── proposal_agares.json
    ├── proposal_agares.md
    ├── proposal_valefor.json
    ├── proposal_valefor.md
    └── ... (one per Duke)
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.domain.models.duke_proposal import (
    DukeProposal,
    DukeProposalSummary,
    ProposalStatus,
)
from src.domain.models.rfp import RFPDocument

if TYPE_CHECKING:
    from src.application.ports.duke_proposal_generation import (
        DukeProposalGeneratorProtocol,
    )


def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _duke_abbreviation(name: str) -> str:
    """Generate 4-char uppercase abbreviation from duke name."""
    return name[:4].upper()


class DukeProposalService:
    """Service for generating Duke implementation proposals.

    Orchestrates sequential proposal generation from all Dukes,
    with retry logic, simulation fallback, and event emission.
    """

    def __init__(
        self,
        duke_proposal_generator: DukeProposalGeneratorProtocol | None = None,
        event_sink: Callable[[str, dict], None] | None = None,
        verbose: bool = False,
        session_id: str | None = None,
    ) -> None:
        self._generator = duke_proposal_generator
        self._event_sink = event_sink or (lambda t, p: None)
        self._verbose = verbose
        self._session_id = session_id or f"duke_{uuid.uuid4().hex[:12]}"

    @property
    def session_id(self) -> str:
        return self._session_id

    def _emit(self, event_type: str, payload: dict) -> None:
        self._event_sink(event_type, {"timestamp": now_iso(), **payload})

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    def _is_retryable_error(self, error: str) -> bool:
        message = error.lower()
        retry_signals = [
            "service temporarily unavailable",
            "temporarily unavailable",
            "api connection",
            "connection error",
            "timeout",
            "timed out",
            "rate limit",
            "429",
            "503",
            "empty response",
            "invalid response",
        ]
        return any(signal in message for signal in retry_signals)

    def _backoff_delay(self, attempt: int) -> float:
        base = float(os.getenv("DUKE_PROPOSAL_BACKOFF_BASE_SECONDS", "2.0"))
        maximum = float(os.getenv("DUKE_PROPOSAL_BACKOFF_MAX_SECONDS", "15.0"))
        delay = min(maximum, base * (2 ** (attempt - 1)))
        jitter = delay * random.uniform(0.1, 0.25)
        return delay + jitter

    # ------------------------------------------------------------------
    # Main generation
    # ------------------------------------------------------------------

    async def generate_all_proposals(
        self,
        rfp: RFPDocument,
        dukes: list[dict[str, Any]],
    ) -> list[DukeProposal]:
        """Generate proposals from all Dukes sequentially.

        Args:
            rfp: Finalized RFP document
            dukes: List of duke dicts from archons-base.json

        Returns:
            List of DukeProposal (one per duke, GENERATED or FAILED)
        """
        self._emit(
            "duke_proposal.started",
            {
                "rfp_id": rfp.implementation_dossier_id,
                "mandate_id": rfp.mandate_id,
                "duke_count": len(dukes),
            },
        )

        proposals: list[DukeProposal] = []
        inter_request_delay = float(
            os.getenv("DUKE_PROPOSAL_INTER_REQUEST_DELAY", "1.0")
        )
        max_attempts = int(os.getenv("DUKE_PROPOSAL_MAX_RETRIES", "3"))

        for i, duke in enumerate(dukes):
            duke_name = duke.get("name", "Unknown")
            duke_archon_id = duke.get("id", "")
            duke_role = duke.get("role", "")
            duke_backstory = duke.get("backstory", "")
            duke_personality = duke.get("personality", "")
            duke_domain = duke_role
            abbrev = _duke_abbreviation(duke_name)

            self._emit(
                "duke_proposal.requested",
                {
                    "duke_name": duke_name,
                    "duke_archon_id": duke_archon_id,
                    "index": i,
                    "total": len(dukes),
                },
            )

            if self._verbose:
                print(
                    f"  [{i + 1}/{len(dukes)}] Requesting proposal from {duke_name} ({abbrev})..."
                )

            proposal: DukeProposal | None = None
            last_error = ""

            for attempt in range(1, max_attempts + 1):
                try:
                    if self._generator is None:
                        raise RuntimeError("No proposal generator configured")

                    proposal = await self._generator.generate_proposal(
                        rfp=rfp,
                        duke_archon_id=duke_archon_id,
                        duke_name=duke_name,
                        duke_domain=duke_domain,
                        duke_role=duke_role,
                        duke_backstory=duke_backstory,
                        duke_personality=duke_personality,
                    )

                    if proposal.status == ProposalStatus.GENERATED:
                        self._emit(
                            "duke_proposal.received",
                            {
                                "duke_name": duke_name,
                                "proposal_id": proposal.proposal_id,
                                "tactic_count": proposal.tactic_count,
                                "risk_count": proposal.risk_count,
                            },
                        )
                        break

                except Exception as exc:
                    last_error = str(exc)
                    if attempt < max_attempts and self._is_retryable_error(last_error):
                        if self._verbose:
                            print(
                                f"    Attempt {attempt} failed (retryable): {last_error[:100]}"
                            )
                        self._emit(
                            "duke_proposal.retry",
                            {
                                "duke_name": duke_name,
                                "attempt": attempt,
                                "error": last_error[:200],
                            },
                        )
                        await asyncio.sleep(self._backoff_delay(attempt))
                        continue
                    else:
                        if self._verbose:
                            print(f"    Attempt {attempt} failed: {last_error[:100]}")
                        break

            if proposal is None or proposal.status != ProposalStatus.GENERATED:
                # Create a FAILED proposal
                proposal = DukeProposal(
                    proposal_id=f"dprop-{abbrev.lower()}-{uuid.uuid4().hex[:8]}",
                    duke_archon_id=duke_archon_id,
                    duke_name=duke_name,
                    duke_domain=duke_domain,
                    duke_abbreviation=abbrev,
                    rfp_id=rfp.implementation_dossier_id,
                    mandate_id=rfp.mandate_id,
                    status=ProposalStatus.FAILED,
                    created_at=now_iso(),
                    failure_reason=last_error or "Unknown error",
                )
                self._emit(
                    "duke_proposal.failed",
                    {
                        "duke_name": duke_name,
                        "error": last_error[:200],
                    },
                )

            proposals.append(proposal)

            # Inter-request delay (skip after last duke)
            if i < len(dukes) - 1 and inter_request_delay > 0:
                await asyncio.sleep(inter_request_delay)

        self._emit(
            "duke_proposal.complete",
            {
                "rfp_id": rfp.implementation_dossier_id,
                "total_proposals": len(proposals),
                "generated": sum(
                    1 for p in proposals if p.status == ProposalStatus.GENERATED
                ),
                "failed": sum(
                    1 for p in proposals if p.status == ProposalStatus.FAILED
                ),
            },
        )

        return proposals

    # ------------------------------------------------------------------
    # Simulation mode
    # ------------------------------------------------------------------

    def _simulate_proposals(
        self,
        rfp: RFPDocument,
        dukes: list[dict[str, Any]],
    ) -> list[DukeProposal]:
        """Generate templated simulation proposals (no LLM)."""
        self._emit(
            "duke_proposal.started",
            {
                "rfp_id": rfp.implementation_dossier_id,
                "mandate_id": rfp.mandate_id,
                "duke_count": len(dukes),
                "mode": "simulation",
            },
        )

        proposals: list[DukeProposal] = []

        for i, duke in enumerate(dukes):
            duke_name = duke.get("name", "Unknown")
            duke_archon_id = duke.get("id", "")
            duke_role = duke.get("role", "")
            abbrev = _duke_abbreviation(duke_name)

            # Build requirement coverage table rows
            coverage_rows: list[str] = []
            fr_count = 0
            nfr_count = 0
            for fr in rfp.functional_requirements:
                coverage_rows.append(
                    f"| {fr.req_id} | functional | Yes | "
                    f"Addressed via {abbrev} standard approach | "
                    f"T-{abbrev}-001 | MEDIUM |"
                )
                fr_count += 1
            for nfr in rfp.non_functional_requirements:
                coverage_rows.append(
                    f"| {nfr.req_id} | non_functional | Yes | "
                    f"Addressed via {abbrev} quality measures | "
                    f"T-{abbrev}-001 | MEDIUM |"
                )
                nfr_count += 1

            # Build deliverable plan table rows
            deliverable_rows: list[str] = []
            for d in rfp.deliverables:
                deliverable_rows.append(
                    f"| {d.deliverable_id} | {duke_name}'s approach to {d.name} | "
                    f"T-{abbrev}-001 | P14D | |"
                )

            # Build constraints list
            constraint_items = [f"- {c.description}" for c in rfp.constraints[:3]]

            coverage_table = "\n".join(coverage_rows) if coverage_rows else ""
            deliverable_table = "\n".join(deliverable_rows) if deliverable_rows else ""
            constraints_text = (
                "\n".join(constraint_items) if constraint_items else "- None"
            )

            markdown = f"""# Proposal from Duke {duke_name}

## Executive Summary
Simulation proposal from {duke_name} applying {duke_role} expertise to RFP requirements.

## Approach Philosophy
{duke_name} proposes a structured approach leveraging domain expertise in {duke_role}.

## Tactics

### T-{abbrev}-001: Primary Implementation Approach
- **Description:** Primary implementation approach via {duke_role}
- **Rationale:** Leverages {duke_name}'s domain expertise
- **Prerequisites:** None
- **Dependencies:** None
- **Estimated Duration:** P14D
- **Owner:** duke_{duke_name.lower()}

## Risks

### R-{abbrev}-001: Standard Implementation Risk
- **Description:** Standard implementation risk for {duke_role} scope
- **Likelihood:** POSSIBLE
- **Impact:** MODERATE
- **Mitigation Strategy:** Iterative delivery with checkpoints
- **Contingency Plan:** Fallback to simplified approach
- **Trigger Conditions:** Schedule delay exceeding 20%

## Resource Requests

### RR-{abbrev}-001: Staff Hours
- **Type:** HUMAN_HOURS
- **Description:** Staff hours for {duke_role} implementation
- **Justification:** Required for {duke_name}'s proposal execution
- **Required By:** 2026-06-01T00:00:00Z
- **Priority:** MEDIUM

## Capacity Commitment
| Field | Value |
|-------|-------|
| Portfolio ID | duke_{duke_name.lower()} |
| Committed Units | 40.0 |
| Unit Label | hours |
| Confidence | MEDIUM |

## Requirement Coverage
| Requirement ID | Type | Covered | Description | Tactic References | Confidence |
|---------------|------|---------|-------------|-------------------|------------|
{coverage_table}

## Deliverable Plan
| Deliverable ID | Approach | Tactic References | Duration | Dependencies |
|---------------|----------|-------------------|----------|--------------|
{deliverable_table}

## Assumptions
- Governance framework stable
- RFP requirements finalized

## Constraints Acknowledged
{constraints_text}
"""

            proposal = DukeProposal(
                proposal_id=f"dprop-{abbrev.lower()}-sim-{uuid.uuid4().hex[:8]}",
                duke_archon_id=duke_archon_id,
                duke_name=duke_name,
                duke_domain=duke_role,
                duke_abbreviation=abbrev,
                rfp_id=rfp.implementation_dossier_id,
                mandate_id=rfp.mandate_id,
                status=ProposalStatus.SIMULATION,
                created_at=now_iso(),
                proposal_markdown=markdown,
                tactic_count=1,
                risk_count=1,
                resource_request_count=1,
                requirement_coverage_count=fr_count + nfr_count,
                deliverable_plan_count=len(rfp.deliverables),
                assumption_count=2,
                constraint_count=len(constraint_items),
            )

            proposals.append(proposal)

        self._emit(
            "duke_proposal.complete",
            {
                "rfp_id": rfp.implementation_dossier_id,
                "total_proposals": len(proposals),
                "generated": 0,
                "failed": 0,
                "simulation": len(proposals),
            },
        )

        return proposals

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save_proposals(
        self,
        proposals: list[DukeProposal],
        rfp: RFPDocument,
        output_dir: Path,
    ) -> Path:
        """Save proposals to disk under the RFP session directory.

        Saves both a slim JSON sidecar (metadata + counts) and a Markdown file
        (full proposal body) for each proposal.

        Args:
            proposals: List of DukeProposal to save
            rfp: The source RFP document
            output_dir: Base output directory (e.g., rfp session mandates dir)

        Returns:
            Path to the duke_proposals directory
        """
        proposals_dir = output_dir / "proposals_inbox"
        proposals_dir.mkdir(parents=True, exist_ok=True)

        # Save individual proposals
        for proposal in proposals:
            duke_lower = proposal.duke_name.lower()

            # Always save the JSON sidecar
            json_filename = f"proposal_{duke_lower}.json"
            proposal_path = proposals_dir / json_filename
            with open(proposal_path, "w", encoding="utf-8") as f:
                json.dump(proposal.to_dict(), f, indent=2)

            # Save Markdown body if present
            if proposal.proposal_markdown:
                md_filename = f"proposal_{duke_lower}.md"
                md_path = proposals_dir / md_filename
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(proposal.proposal_markdown)

        # Save summary
        summary = DukeProposalSummary.from_proposals(
            proposals=proposals,
            rfp_id=rfp.implementation_dossier_id,
            mandate_id=rfp.mandate_id,
            created_at=now_iso(),
        )
        summary_path = proposals_dir / "proposal_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, indent=2)

        # Save inbox manifest
        manifest = self._build_inbox_manifest(proposals, rfp)
        manifest_path = proposals_dir / "inbox_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return proposals_dir

    def _build_inbox_manifest(
        self,
        proposals: list[DukeProposal],
        rfp: RFPDocument,
    ) -> dict:
        """Build inbox manifest tracking each Duke's submission status."""
        submissions = []
        for proposal in proposals:
            duke_lower = proposal.duke_name.lower()
            entry: dict[str, Any] = {
                "duke_name": proposal.duke_name,
                "duke_abbreviation": proposal.duke_abbreviation,
                "duke_archon_id": proposal.duke_archon_id,
                "proposal_file": f"proposal_{duke_lower}.json",
                "status": proposal.status.value,
                "submitted_at": proposal.created_at,
            }
            if proposal.proposal_markdown:
                entry["proposal_markdown_file"] = f"proposal_{duke_lower}.md"
            if proposal.llm_provider:
                entry["llm_provider"] = proposal.llm_provider
            if proposal.llm_model:
                entry["llm_model"] = proposal.llm_model
            if proposal.failure_reason:
                entry["failure_reason"] = proposal.failure_reason
            submissions.append(entry)

        return {
            "artifact_type": "duke_proposals_inbox_manifest",
            "rfp_id": rfp.implementation_dossier_id,
            "mandate_id": rfp.mandate_id,
            "created_at": now_iso(),
            "total_dukes": len(proposals),
            "submissions": submissions,
        }

    @staticmethod
    def load_rfp(rfp_path: Path) -> RFPDocument:
        """Load and deserialize an RFP document from disk.

        Args:
            rfp_path: Path to the rfp.json file

        Returns:
            Deserialized RFPDocument
        """
        with open(rfp_path, encoding="utf-8") as f:
            data = json.load(f)
        return RFPDocument.from_dict(data)
