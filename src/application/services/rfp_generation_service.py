"""Service for generating Executive Implementation Dossiers from mandates.

Orchestrates the Executive mini-conclave where all Presidents contribute
requirements and constraints from their portfolio perspective.

Output Structure (following executive pipeline pattern):
    <outdir>/<session_id>/
    ├── rfp_session_summary.json       # Session metadata
    └── mandates/<mandate_id>/
        ├── rfp.json                   # Final synthesized dossier (legacy filename)
        ├── rfp.md                     # Human-readable version
        ├── rfp_events.jsonl           # Event trail
        └── contributions/
            └── contribution_<portfolio_id>.json  # Per-President files
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.domain.models.rfp import (
    ContributionStatus,
    Deliverable,
    EvaluationCriterion,
    FunctionalRequirement,
    PortfolioContribution,
    RequirementPriority,
    RFPDocument,
)

if TYPE_CHECKING:
    from src.application.ports.rfp_generation import (
        RFPContributorProtocol,
        RFPDeliberationProtocol,
        RFPSynthesizerProtocol,
    )

SCHEMA_VERSION = "1.0"


def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


class RFPGenerationService:
    """Service for generating Executive Implementation Dossiers through President deliberation.

    The Executive branch translates Legislative mandates into detailed
    requirements for the Administrative branch. This service orchestrates
    the mini-conclave where all 11 Presidents contribute.
    """

    def __init__(
        self,
        rfp_contributor: RFPContributorProtocol | None = None,
        rfp_synthesizer: RFPSynthesizerProtocol | None = None,
        deliberation_protocol: RFPDeliberationProtocol | None = None,
        event_sink: Callable[[str, dict], None] | None = None,
        verbose: bool = False,
        session_id: str | None = None,
    ) -> None:
        """Initialize the RFP generation service.

        Args:
            rfp_contributor: Protocol for generating portfolio contributions
            rfp_synthesizer: Protocol for synthesizing contributions into RFP
            deliberation_protocol: Protocol for multi-round deliberation
            event_sink: Optional callback for emitting events
            verbose: Enable verbose logging
            session_id: Optional session ID (auto-generated if not provided)
        """
        self._contributor = rfp_contributor
        self._synthesizer = rfp_synthesizer
        self._deliberation = deliberation_protocol
        self._event_sink = event_sink or (lambda t, p: None)
        self._verbose = verbose
        self._session_id = session_id or f"rfp_{uuid.uuid4().hex[:12]}"
        self._contributions_by_mandate: dict[str, list[PortfolioContribution]] = {}

    @property
    def session_id(self) -> str:
        """Return the session ID for this RFP generation run."""
        return self._session_id

    def _emit(self, event_type: str, payload: dict) -> None:
        """Emit an event."""
        self._event_sink(event_type, {"timestamp": now_iso(), **payload})

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
        base = float(os.getenv("RFP_GENERATOR_BACKOFF_BASE_SECONDS", "2.0"))
        maximum = float(os.getenv("RFP_GENERATOR_BACKOFF_MAX_SECONDS", "15.0"))
        delay = min(maximum, base * (2 ** (attempt - 1)))
        jitter = delay * random.uniform(0.1, 0.25)
        return delay + jitter

    def _inter_request_delay(self) -> float:
        value = os.getenv("RFP_GENERATOR_INTER_REQUEST_DELAY_SECONDS", "").strip()
        if not value:
            return 0.0
        try:
            delay = max(0.0, float(value))
        except ValueError:
            return 0.0
        jitter = delay * random.uniform(0.05, 0.2)
        return delay + jitter

    def create_rfp_draft(
        self,
        mandate_id: str,
        motion_title: str,
        motion_text: str,
        business_justification: str = "",
        strategic_alignment: list[str] | None = None,
    ) -> RFPDocument:
        """Create an initial Executive Implementation Dossier draft from a mandate.

        Args:
            mandate_id: The mandate ID from the Registrar
            motion_title: Title of the passed motion
            motion_text: Full text of the passed motion
            business_justification: Why this work is needed
            strategic_alignment: How it aligns with strategic goals

        Returns:
            Draft dossier document ready for President contributions
        """
        rfp = RFPDocument.create(
            mandate_id=mandate_id,
            motion_title=motion_title,
            motion_text=motion_text,
        )
        rfp.business_justification = business_justification
        rfp.strategic_alignment = strategic_alignment or []

        self._emit(
            "rfp_draft_created",
            {
                "implementation_dossier_id": rfp.implementation_dossier_id,
                "mandate_id": mandate_id,
                "motion_title": motion_title,
            },
        )
        return rfp

    async def collect_contributions(
        self,
        rfp: RFPDocument,
        presidents: list[dict],
    ) -> list[PortfolioContribution]:
        """Collect contributions from all Presidents.

        Args:
            rfp: The draft dossier document
            presidents: List of President info dicts with portfolio_id, name, domain, id

        Returns:
            List of portfolio contributions
        """
        if not self._contributor:
            return self._simulate_contributions(rfp, presidents)

        contributions: list[PortfolioContribution] = []
        for president in presidents:
            president_id = president.get("id", "")
            max_attempts = int(os.getenv("RFP_GENERATOR_MAX_ATTEMPTS", "2"))
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                delay = self._inter_request_delay()
                if delay > 0:
                    await asyncio.sleep(delay)

                self._emit(
                    "contribution_requested",
                    {
                        "implementation_dossier_id": rfp.implementation_dossier_id,
                        "session_id": self._session_id,
                        "portfolio_id": president["portfolio_id"],
                        "president_id": president_id,
                        "president_name": president["name"],
                        "attempt": attempt,
                    },
                )

                try:
                    contribution = await self._contributor.generate_contribution(
                        mandate_id=rfp.mandate_id,
                        motion_title=rfp.motion_title,
                        motion_text=rfp.motion_text,
                        portfolio_id=president["portfolio_id"],
                        president_name=president["name"],
                        portfolio_domain=president.get("domain", ""),
                        president_id=president_id,
                        existing_contributions=contributions,
                    )
                    contribution.portfolio_label = president.get("portfolio_label", "")

                    if (
                        contribution.status == ContributionStatus.FAILED
                        and self._is_retryable_error(contribution.failure_reason)
                        and attempt < max_attempts
                    ):
                        self._emit(
                            "contribution_retry",
                            {
                                "implementation_dossier_id": rfp.implementation_dossier_id,
                                "session_id": self._session_id,
                                "portfolio_id": president["portfolio_id"],
                                "president_id": president_id,
                                "reason": contribution.failure_reason,
                                "attempt": attempt,
                            },
                        )
                        await asyncio.sleep(self._backoff_delay(attempt))
                        continue

                    contributions.append(contribution)

                    self._emit(
                        "contribution_received",
                        {
                            "implementation_dossier_id": rfp.implementation_dossier_id,
                            "session_id": self._session_id,
                            "portfolio_id": president["portfolio_id"],
                            "president_id": president_id,
                            "requirements_count": len(contribution.functional_requirements)
                            + len(contribution.non_functional_requirements),
                            "constraints_count": len(contribution.constraints),
                        },
                    )
                    break
                except Exception as e:
                    error_msg = str(e)
                    if attempt < max_attempts and self._is_retryable_error(error_msg):
                        self._emit(
                            "contribution_retry",
                            {
                                "implementation_dossier_id": rfp.implementation_dossier_id,
                                "session_id": self._session_id,
                                "portfolio_id": president["portfolio_id"],
                                "president_id": president_id,
                                "reason": error_msg,
                                "attempt": attempt,
                            },
                        )
                        await asyncio.sleep(self._backoff_delay(attempt))
                        continue

                    self._emit(
                        "contribution_failed",
                        {
                            "implementation_dossier_id": rfp.implementation_dossier_id,
                            "session_id": self._session_id,
                            "portfolio_id": president["portfolio_id"],
                            "president_id": president_id,
                            "error": error_msg,
                        },
                    )
                    contributions.append(
                        self._generate_fallback_contribution(rfp, president, error_msg)
                    )
                    break

        # Store contributions for this mandate for later saving
        self._contributions_by_mandate[rfp.mandate_id] = contributions

        return contributions

    # Portfolio abbreviations (mirror of adapter for consistency)
    PORTFOLIO_ABBREV = {
        "portfolio_architecture_engineering_standards": "TECH",
        "portfolio_adversarial_risk_security": "CONF",
        "portfolio_policy_knowledge_stewardship": "KNOW",
        "portfolio_capacity_resource_planning": "RSRC",
        "portfolio_infrastructure_platform_reliability": "INFR",
        "portfolio_change_management_migration": "ALCH",
        "portfolio_model_behavior_alignment": "BEHV",
        "portfolio_resilience_incident_response": "WELL",
        "portfolio_strategic_foresight_scenario_planning": "ASTR",
        "portfolio_identity_access_provenance": "IDEN",
        "portfolio_ethics_privacy_trust": "ETHC",
        "portfolio_managing_director_-_architecture_engineering_standards": "TECH",
        "portfolio_managing_director_-_adversarial_risk_security": "CONF",
        "portfolio_managing_director_-_policy_knowledge_stewardship": "KNOW",
        "portfolio_managing_director_-_capacity_resource_planning": "RSRC",
        "portfolio_managing_director_-_infrastructure_platform_reliability": "INFR",
        "portfolio_managing_director_-_change_management_migration": "ALCH",
        "portfolio_managing_director_-_model_behavior_alignment": "BEHV",
        "portfolio_managing_director_-_resilience_incident_response": "WELL",
        "portfolio_managing_director_-_strategic_foresight_scenario_planning": "ASTR",
        "portfolio_managing_director_-_identity_access_provenance": "IDEN",
        "portfolio_managing_director_-_ethics_privacy_trust": "ETHC",
    }

    def _get_portfolio_abbrev(self, portfolio_id: str) -> str:
        """Get unique abbreviation for a portfolio ID."""
        return self.PORTFOLIO_ABBREV.get(portfolio_id, portfolio_id[-4:].upper())

    def _simulate_contributions(
        self,
        rfp: RFPDocument,
        presidents: list[dict],
    ) -> list[PortfolioContribution]:
        """Generate simulated contributions for testing."""
        contributions = []
        for president in presidents:
            abbrev = self._get_portfolio_abbrev(president["portfolio_id"])
            contribution = PortfolioContribution(
                portfolio_id=president["portfolio_id"],
                president_id=president.get("id", ""),
                president_name=president["name"],
                portfolio_label=president.get("portfolio_label", ""),
                status=ContributionStatus.CONTRIBUTED,
                contribution_summary=f"Simulated contribution from {president['name']} "
                f"for mandate: {rfp.motion_title}",
                functional_requirements=[
                    FunctionalRequirement(
                        req_id=f"FR-{abbrev}-001",
                        description=f"[Simulated] The solution must address "
                        f"{president.get('domain', 'general')} concerns",
                        priority=RequirementPriority.SHOULD,
                        source_portfolio_id=president["portfolio_id"],
                        acceptance_criteria=["Criteria to be defined by Administrative"],
                    )
                ],
                deliberation_notes="Simulated contribution - no LLM available",
                generated_at=now_iso(),
            )
            contributions.append(contribution)

        # Store contributions for this mandate
        self._contributions_by_mandate[rfp.mandate_id] = contributions
        return contributions

    def _generate_fallback_contribution(
        self,
        rfp: RFPDocument,
        president: dict,
        error: str,
    ) -> PortfolioContribution:
        """Generate a FAILED fallback contribution when LLM fails.

        This blocks finalization - failures must be resolved before RFP is final.
        """
        return PortfolioContribution(
            portfolio_id=president["portfolio_id"],
            president_id=president.get("id", ""),
            president_name=president["name"],
            portfolio_label=president.get("portfolio_label", ""),
            status=ContributionStatus.FAILED,
            contribution_summary=f"FAILED: {president['name']} - {error[:100]}",
            failure_reason=error,
            functional_requirements=[],
            non_functional_requirements=[],
            constraints=[],
            deliberation_notes=f"LLM generation failed: {error}",
            generated_at=now_iso(),
        )

    async def run_deliberation(
        self,
        rfp: RFPDocument,
        contributions: list[PortfolioContribution],
        max_rounds: int = 2,
    ) -> list[PortfolioContribution]:
        """Run deliberation rounds for Presidents to refine contributions.

        Args:
            rfp: The RFP document
            contributions: Initial contributions
            max_rounds: Maximum deliberation rounds

        Returns:
            Refined contributions after deliberation
        """
        if not self._deliberation:
            return contributions

        current_contributions = contributions
        for round_num in range(1, max_rounds + 1):
            self._emit(
                "deliberation_round_start",
                {"implementation_dossier_id": rfp.implementation_dossier_id, "round": round_num},
            )

            # Identify focus areas (conflicts, gaps)
            conflicts = await self._synthesizer.identify_conflicts(current_contributions)
            focus_areas = [c.get("description", "") for c in conflicts[:3]]

            current_contributions = await self._deliberation.run_deliberation_round(
                rfp_draft=rfp,
                contributions=current_contributions,
                round_number=round_num,
                focus_areas=focus_areas if focus_areas else None,
            )

            rfp.deliberation_rounds = round_num
            self._emit(
                "deliberation_round_complete",
                {
                    "implementation_dossier_id": rfp.implementation_dossier_id,
                    "round": round_num,
                    "conflicts_addressed": len(focus_areas),
                },
            )

        return current_contributions

    async def synthesize_rfp(
        self,
        rfp: RFPDocument,
        contributions: list[PortfolioContribution],
        expected_portfolios: list[str] | None = None,
    ) -> RFPDocument:
        """Synthesize contributions into the final dossier.

        Args:
            rfp: The draft dossier
            contributions: All portfolio contributions
            expected_portfolios: List of expected portfolio IDs for completeness check

        Returns:
            Finalized dossier document (may be BLOCKED if incomplete)
        """
        # Add all contributions
        for contribution in contributions:
            rfp.add_contribution(contribution)

        if self._synthesizer:
            rfp = await self._synthesizer.synthesize_rfp(rfp, contributions)
        else:
            # Basic synthesis without LLM
            self._basic_synthesis(rfp, contributions)

        # Derive scope from requirements
        self._derive_scope(rfp)

        # Add default governance terms (without executive overreach)
        self._add_default_terms(rfp)

        # Check completeness before finalizing (may set status=BLOCKED)
        rfp.finalize(expected_portfolios=expected_portfolios)
        self._emit(
            "rfp_finalized",
            {
                "implementation_dossier_id": rfp.implementation_dossier_id,
                "functional_requirements": len(rfp.functional_requirements),
                "non_functional_requirements": len(rfp.non_functional_requirements),
                "constraints": len(rfp.constraints),
                "deliverables": len(rfp.deliverables),
                "evaluation_criteria": len(rfp.evaluation_criteria),
                "unresolved_conflicts": len(rfp.unresolved_conflicts),
            },
        )
        return rfp

    def _basic_synthesis(
        self,
        rfp: RFPDocument,
        contributions: list[PortfolioContribution],
    ) -> None:
        """Perform basic synthesis without LLM."""
        # Collect all risks and assumptions
        all_risks = []
        all_assumptions = []
        for contrib in contributions:
            all_risks.extend(contrib.risks_identified)
            all_assumptions.extend(contrib.assumptions)

        # Add default evaluation criteria if none provided
        if not rfp.evaluation_criteria:
            rfp.evaluation_criteria = [
                EvaluationCriterion(
                    criterion_id="EC-001",
                    name="Requirements Coverage",
                    description="How completely the proposal addresses all requirements",
                    scoring_method="1-5 scale",
                    priority_band="high",
                ),
                EvaluationCriterion(
                    criterion_id="EC-002",
                    name="Technical Feasibility",
                    description="How feasible the proposed approach is",
                    scoring_method="1-5 scale",
                    priority_band="high",
                ),
                EvaluationCriterion(
                    criterion_id="EC-003",
                    name="Risk Management",
                    description="How well risks are identified and mitigated",
                    scoring_method="1-5 scale",
                    priority_band="medium",
                ),
                EvaluationCriterion(
                    criterion_id="EC-004",
                    name="Resource Efficiency",
                    description="How efficiently resources are utilized",
                    scoring_method="1-5 scale",
                    priority_band="medium",
                ),
                EvaluationCriterion(
                    criterion_id="EC-005",
                    name="Timeline Realism",
                    description="How realistic the proposed timeline is",
                    scoring_method="1-5 scale",
                    priority_band="low",
                ),
            ]

        # Add default deliverable
        if not rfp.deliverables:
            rfp.deliverables = [
                Deliverable(
                    deliverable_id="D-001",
                    name="Solution Implementation",
                    description="Working implementation that addresses all MUST requirements",
                    acceptance_criteria=[
                        "All MUST requirements verified",
                        "All SHOULD requirements addressed or justified",
                        "Documentation complete",
                    ],
                    verification_method="Acceptance testing against requirements",
                )
            ]

    def _derive_scope(self, rfp: RFPDocument) -> None:
        """Derive scope from the motion and requirements."""
        if not rfp.objectives:
            # Extract objectives from motion text
            rfp.objectives = [
                f"Implement the mandate: {rfp.motion_title}",
            ]

        if not rfp.success_criteria:
            motion_native = self._extract_motion_success_criteria(rfp.motion_text)
            if motion_native:
                rfp.success_criteria = motion_native
            else:
                rfp.success_criteria = [
                    "All ratified clauses implemented without intent drift",
                    "No unresolved conflicts at completion",
                ]

    def _extract_motion_success_criteria(self, motion_text: str) -> list[str]:
        """Extract motion-native success criteria or clauses from motion text."""
        if not motion_text:
            return []

        lines = [line.strip() for line in motion_text.splitlines()]

        # First pass: explicit "Success Criteria" section (supports markdown headings)
        criteria: list[str] = []
        in_success = False
        for line in lines:
            if not line:
                if in_success and criteria:
                    break
                continue
            if re.search(r"success criteria", line, re.IGNORECASE):
                in_success = True
                continue
            if in_success:
                if re.match(r"^#{1,6}\s+", line) and criteria:
                    break
                if re.match(r"^[-*]\s+", line):
                    criteria.append(re.sub(r"^[-*]\s+", "", line))
                    continue
                if re.match(r"^\d+[.)]\s+", line):
                    criteria.append(re.sub(r"^\d+[.)]\s+", "", line))
                    continue
                if criteria and not re.match(r"^[-*]|\d+[.)]", line):
                    break

        if criteria:
            return criteria

        # Second pass: use numbered clauses after a "THEREFORE" or "BE IT MOVED" marker
        clauses: list[str] = []
        found_marker = False
        for line in lines:
            if re.search(r"(?i)therefore|be it (moved|resolved)", line):
                found_marker = True
                continue
            if found_marker:
                if re.match(r"^\d+[.)]\s+", line):
                    clauses.append(re.sub(r"^\d+[.)]\s+", "", line))
                elif clauses and line == "":
                    break

        if clauses:
            return clauses

        # Final fallback: any numbered clauses in the motion text
        for line in lines:
            if re.match(r"^\d+[.)]\s+", line):
                clauses.append(re.sub(r"^\d+[.)]\s+", "", line))
        return clauses

    def _add_default_terms(self, rfp: RFPDocument) -> None:
        """Add default governance terms.

        NOTE: Executive steps back after handoff - these terms must NOT
        create ongoing supervisory authority over execution. That violates
        branch boundaries.
        """
        if not rfp.governance_requirements:
            rfp.governance_requirements = [
                "Proposals must address all MUST priority requirements",
                # NO: "Changes to scope require Executive review" - Executive overreach
                # NO: "Progress reports required at milestones" - Executive overreach
            ]

        if not rfp.escalation_paths:
            # Escalation paths for ADMINISTRATIVE use, not Executive supervision
            rfp.escalation_paths = [
                "Intent ambiguity → Conclave clarification (via Executive escalation)",
                "Resource conflicts → Administrative coordination",
                "Technical blockers → Administrative triage",
                # Strategic conflicts go to Conclave, not Executive
            ]

    async def generate_rfp(
        self,
        mandate_id: str,
        motion_title: str,
        motion_text: str,
        presidents: list[dict],
        business_justification: str = "",
        strategic_alignment: list[str] | None = None,
        deliberation_rounds: int = 1,
        expected_portfolios: list[str] | None = None,
    ) -> RFPDocument:
        """Generate a complete dossier from a mandate.

        This is the main entry point for dossier generation.

        Args:
            mandate_id: The mandate ID from the Registrar
            motion_title: Title of the passed motion
            motion_text: Full text of the passed motion
            presidents: List of President info dicts
            business_justification: Why this work is needed
            strategic_alignment: How it aligns with strategic goals
            deliberation_rounds: Number of deliberation rounds

        Returns:
            Complete dossier document
        """
        self._emit(
            "rfp_generation_started",
            {
                "mandate_id": mandate_id,
                "motion_title": motion_title,
                "presidents_count": len(presidents),
            },
        )

        # Create draft
        rfp = self.create_rfp_draft(
            mandate_id=mandate_id,
            motion_title=motion_title,
            motion_text=motion_text,
            business_justification=business_justification,
            strategic_alignment=strategic_alignment,
        )

        # Collect contributions from all Presidents
        contributions = await self.collect_contributions(rfp, presidents)

        # Run deliberation if enabled
        if deliberation_rounds > 0 and self._deliberation:
            contributions = await self.run_deliberation(
                rfp, contributions, max_rounds=deliberation_rounds
            )

        # Synthesize into final RFP
        rfp = await self.synthesize_rfp(
            rfp,
            contributions,
            expected_portfolios=expected_portfolios,
        )

        self._emit(
            "rfp_generation_complete",
            {
                "implementation_dossier_id": rfp.implementation_dossier_id,
                "mandate_id": mandate_id,
                "status": rfp.status.value,
            },
        )

        return rfp

    def save_rfp(
        self,
        rfp: RFPDocument,
        output_dir: Path,
        events: list[dict] | None = None,
    ) -> Path:
        """Save the dossier document and per-President contributions to disk.

        Output structure follows executive pipeline pattern:
            <output_dir>/<session_id>/mandates/<mandate_id>/
            ├── rfp.json                   # Final synthesized RFP
            ├── rfp.md                     # Human-readable version
            ├── rfp_events.jsonl           # Event trail
            └── contributions/
                └── contribution_<portfolio_id>.json  # Per-President files

        Args:
            rfp: The dossier document to save
            output_dir: Base output directory
            events: Optional list of events to save

        Returns:
            Path to the saved RFP file
        """
        # Build session-based output structure
        session_dir = output_dir / self._session_id
        mandate_dir = session_dir / "mandates" / rfp.mandate_id
        contributions_dir = mandate_dir / "contributions"
        contributions_dir.mkdir(parents=True, exist_ok=True)

        # Save per-President contribution files
        contributions = self._contributions_by_mandate.get(rfp.mandate_id, rfp.portfolio_contributions)
        for contrib in contributions:
            contrib_dict = contrib.to_dict()
            status = getattr(contrib, "status", None)
            failure_reason = getattr(contrib, "failure_reason", "")
            if "status" not in contrib_dict and status is not None:
                contrib_dict["status"] = (
                    status.value if hasattr(status, "value") else status
                )
            if "failure_reason" not in contrib_dict and failure_reason:
                contrib_dict["failure_reason"] = failure_reason

            contrib_data = {
                "schema_version": SCHEMA_VERSION,
                "session_id": self._session_id,
                "mandate_id": rfp.mandate_id,
                **contrib_dict,
            }
            contrib_path = contributions_dir / f"contribution_{contrib.portfolio_id}.json"
            with open(contrib_path, "w", encoding="utf-8") as f:
                json.dump(contrib_data, f, indent=2)

        # Save final RFP
        rfp_path = mandate_dir / "rfp.json"
        rfp_data = {
            "schema_version": SCHEMA_VERSION,
            "session_id": self._session_id,
            **rfp.to_dict(),
        }
        with open(rfp_path, "w", encoding="utf-8") as f:
            json.dump(rfp_data, f, indent=2)

        # Save markdown version for human readability
        md_path = mandate_dir / "rfp.md"
        self._save_rfp_markdown(rfp, md_path)

        # Save events if provided
        if events:
            events_path = mandate_dir / "rfp_events.jsonl"
            with open(events_path, "w", encoding="utf-8") as f:
                for event in events:
                    f.write(json.dumps(event) + "\n")

        # Save session summary at session level
        self._save_session_summary(session_dir, rfp)

        return rfp_path

    def _save_session_summary(self, session_dir: Path, rfp: RFPDocument) -> None:
        """Save session summary metadata."""
        summary_path = session_dir / "rfp_session_summary.json"

        # Load existing summary or create new one
        if summary_path.exists():
            with open(summary_path, encoding="utf-8") as f:
                summary = json.load(f)
        else:
            summary = {
                "schema_version": SCHEMA_VERSION,
                "session_id": self._session_id,
                "created_at": now_iso(),
                "mandates_processed": [],
            }

        # Update with this RFP's info
        mandate_info = {
            "mandate_id": rfp.mandate_id,
            "motion_title": rfp.motion_title,
            "implementation_dossier_id": rfp.implementation_dossier_id,
            "status": rfp.status.value,
            "contributing_portfolios": len(rfp.portfolio_contributions),
            "functional_requirements": len(rfp.functional_requirements),
            "non_functional_requirements": len(rfp.non_functional_requirements),
            "constraints": len(rfp.constraints),
            "unresolved_conflicts": len(rfp.unresolved_conflicts),
            "processed_at": now_iso(),
        }

        # Avoid duplicates
        existing_ids = {m["mandate_id"] for m in summary["mandates_processed"]}
        if rfp.mandate_id not in existing_ids:
            summary["mandates_processed"].append(mandate_info)
        else:
            # Update existing entry
            summary["mandates_processed"] = [
                mandate_info if m["mandate_id"] == rfp.mandate_id else m
                for m in summary["mandates_processed"]
            ]

        summary["last_updated"] = now_iso()

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def _save_rfp_markdown(self, rfp: RFPDocument, path: Path) -> None:
        """Save a human-readable markdown version of the RFP."""
        lines = [
            f"# Executive Implementation Dossier: {rfp.motion_title}",
            "",
            f"**Implementation Dossier ID:** {rfp.implementation_dossier_id}",
            f"**Mandate ID:** {rfp.mandate_id}",
            f"**Status:** {rfp.status.value}",
            f"**Created:** {rfp.created_at}",
            "",
            "---",
            "",
            "## Executive Scope Disclaimer",
            "",
            rfp.executive_scope_disclaimer.get("statement", ""),
            "",
            "## 1. Background",
            "",
            "### Motion Text",
            "",
            rfp.motion_text,
            "",
        ]

        if rfp.business_justification:
            lines.extend([
                "### Business Justification",
                "",
                rfp.business_justification,
                "",
            ])

        if rfp.strategic_alignment:
            lines.extend([
                "### Strategic Alignment",
                "",
                *[f"- {a}" for a in rfp.strategic_alignment],
                "",
            ])

        # Scope
        lines.extend([
            "---",
            "",
            "## 2. Scope of Work",
            "",
        ])

        if rfp.objectives:
            lines.extend([
                "### Objectives",
                "",
                *[f"- {o}" for o in rfp.objectives],
                "",
            ])

        if rfp.in_scope:
            lines.extend([
                "### In Scope",
                "",
                *[f"- {s}" for s in rfp.in_scope],
                "",
            ])

        if rfp.out_of_scope:
            lines.extend([
                "### Out of Scope",
                "",
                *[f"- {s}" for s in rfp.out_of_scope],
                "",
            ])

        if rfp.success_criteria:
            lines.extend([
                "### Success Criteria",
                "",
                *[f"- {c}" for c in rfp.success_criteria],
                "",
            ])

        # Requirements
        lines.extend([
            "---",
            "",
            "## 3. Requirements",
            "",
            "### Functional Requirements",
            "",
        ])

        for req in rfp.functional_requirements:
            lines.extend([
                f"#### {req.req_id}: {req.description[:60]}...",
                "",
                f"- **Priority:** {req.priority.value.upper()}",
                f"- **Source:** {req.source_portfolio_id}",
            ])
            if req.acceptance_criteria:
                lines.append("- **Acceptance Criteria:**")
                for ac in req.acceptance_criteria:
                    lines.append(f"  - {ac}")
            lines.append("")

        lines.extend([
            "### Non-Functional Requirements",
            "",
        ])

        for req in rfp.non_functional_requirements:
            lines.extend([
                f"#### {req.req_id}: {req.description[:60]}...",
                "",
                f"- **Category:** {req.category.value}",
                f"- **Priority:** {req.priority.value.upper()}",
                f"- **Source:** {req.source_portfolio_id}",
            ])
            if req.target_metric:
                lines.append(f"- **Target:** {req.target_metric}")
            if req.threshold:
                lines.append(f"- **Threshold:** {req.threshold}")
            lines.append("")

        # Constraints
        lines.extend([
            "---",
            "",
            "## 4. Constraints",
            "",
        ])

        for const in rfp.constraints:
            lines.extend([
                f"#### {const.constraint_id}: {const.description[:60]}...",
                "",
                f"- **Type:** {const.constraint_type.value}",
                f"- **Source:** {const.source_portfolio_id}",
                f"- **Negotiable:** {'Yes' if const.negotiable else 'No'}",
            ])
            if const.rationale:
                lines.append(f"- **Rationale:** {const.rationale}")
            lines.append("")

        # Evaluation Criteria
        lines.extend([
            "---",
            "",
            "## 5. Evaluation Criteria",
            "",
            "| Criterion | Priority Band | Scoring Method |",
            "|-----------|---------------|----------------|",
        ])

        for ec in rfp.evaluation_criteria:
            lines.append(f"| {ec.name} | {ec.priority_band} | {ec.scoring_method} |")

        lines.append("")

        # Deliverables
        lines.extend([
            "---",
            "",
            "## 6. Deliverables",
            "",
        ])

        for deliv in rfp.deliverables:
            lines.extend([
                f"### {deliv.deliverable_id}: {deliv.name}",
                "",
                deliv.description,
                "",
            ])
            if deliv.acceptance_criteria:
                lines.append("**Acceptance Criteria:**")
                for ac in deliv.acceptance_criteria:
                    lines.append(f"- {ac}")
                lines.append("")

        # Terms
        lines.extend([
            "---",
            "",
            "## 7. Terms and Governance",
            "",
        ])

        if rfp.governance_requirements:
            lines.extend([
                "### Governance Requirements",
                "",
                *[f"- {g}" for g in rfp.governance_requirements],
                "",
            ])

        if rfp.escalation_paths:
            lines.extend([
                "### Escalation Paths",
                "",
                *[f"- {e}" for e in rfp.escalation_paths],
                "",
            ])

        # Contributing portfolios
        lines.extend([
            "---",
            "",
            "## 8. Contributing Portfolios",
            "",
            "| Portfolio | President | Requirements | Constraints |",
            "|-----------|-----------|--------------|-------------|",
        ])

        for contrib in rfp.portfolio_contributions:
            req_count = len(contrib.functional_requirements) + len(
                contrib.non_functional_requirements
            )
            lines.append(
                f"| {contrib.portfolio_id} | {contrib.president_name} | "
                f"{req_count} | {len(contrib.constraints)} |"
            )

        lines.append("")

        # Unresolved conflicts
        if rfp.unresolved_conflicts:
            lines.extend([
                "---",
                "",
                "## 9. Unresolved Conflicts",
                "",
                "The following conflicts require resolution:",
                "",
            ])

            for conflict in rfp.unresolved_conflicts:
                lines.extend([
                    f"### {conflict.conflict_id}",
                    "",
                    conflict.description,
                    "",
                    f"- **Parties:** {', '.join(conflict.conflicting_portfolios)}",
                    f"- **Escalate to Conclave:** {'Yes' if conflict.escalate_to_conclave else 'No'}",
                ])
                if conflict.proposed_resolution:
                    lines.append(f"- **Proposed Resolution:** {conflict.proposed_resolution}")
                lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
