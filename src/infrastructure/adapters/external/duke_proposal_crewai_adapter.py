"""CrewAI adapter for Duke Proposal generation.

Each Administrative Duke reads a finalized Executive RFP and produces a
complete implementation proposal covering HOW to accomplish the requirements.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from crewai import Agent, Crew, Task

from src.application.ports.duke_proposal_generation import (
    DukeProposalGeneratorProtocol,
)
from src.domain.models.duke_proposal import (
    DukeProposal,
    ProposalStatus,
)
from src.domain.models.llm_config import LLMConfig

if TYPE_CHECKING:
    from crewai import LLM

    from src.domain.models.rfp import RFPDocument
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        ArchonProfileRepository,
    )

from src.application.llm.crewai_llm_factory import create_crewai_llm


def _duke_abbreviation(name: str) -> str:
    """Generate 4-char uppercase abbreviation from duke name."""
    return name[:4].upper()


class DukeProposalCrewAIAdapter(DukeProposalGeneratorProtocol):
    """CrewAI adapter for generating Duke implementation proposals."""

    # Administrative scope constraint - Dukes propose HOW, not WHAT
    ADMINISTRATIVE_SCOPE_CONSTRAINT = """
ADMINISTRATIVE SCOPE CONSTRAINT (MANDATORY):
You are an Administrative Duke. Your role is to propose HOW to implement the RFP requirements.
- You MUST NOT redefine, modify, or add new requirements. The RFP requirements are fixed.
- You MUST NOT assign work to other branches (Legislative, Executive, Judicial).
- You MAY propose tactics, approaches, resource needs, and risk mitigations.
- You MAY propose how to organize work within the Administrative branch.
- You MUST reference RFP requirements by their existing IDs (FR-xxx, NFR-xxx).
- Focus on: implementation approach, resource needs, risk identification, timeline.
"""

    CONTEXT_PURITY_CONSTRAINT = """
CONTEXT PURITY CONSTRAINT (MANDATORY):
You may ONLY reference:
- The governance system itself (ledger, events, tasks, roles, branches)
- Conclave / Aegis Network / Archon task lifecycle artifacts
- Abstract system concepts (state changes, authority, attribution, verification)

You may NOT:
- Invent real-world domains (healthcare/HIPAA, military/Geneva, nuclear, financial/SOX)
- Reference external compliance frameworks unless the RFP explicitly names them
- Create fictional urgency or compliance burdens
"""

    BRANCH_BOUNDARY_CONSTRAINT = """
BRANCH-BOUNDARY CONSTRAINT (MANDATORY):
- You may NOT assign work, responsibilities, validators, approvals, or signers to any other branch.
- You may state resource needs and dependencies only.
- You may NOT introduce new governance structures, matrices, cycles, councils, or consensus frameworks.
"""

    def __init__(
        self,
        profile_repository: ArchonProfileRepository | None = None,
        verbose: bool = False,
        llm_config: LLMConfig | None = None,
        model: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._verbose = verbose
        self._default_llm_config = llm_config
        self._model_override = model
        self._provider_override = provider
        self._base_url_override = base_url
        self._llm_cache: dict[str, tuple[LLM | str, LLMConfig]] = {}

    # ------------------------------------------------------------------
    # LLM management (follows RFP contributor pattern)
    # ------------------------------------------------------------------

    def _get_duke_llm(self, duke_name: str) -> tuple[LLM | str, LLMConfig]:
        """Get the appropriate LLM for a Duke (cached)."""
        if duke_name in self._llm_cache:
            return self._llm_cache[duke_name]

        llm_config = self._default_llm_config

        if self._profile_repository:
            profile = self._profile_repository.get_by_name(duke_name)
            if profile and profile.llm_config:
                llm_config = profile.llm_config

        if not llm_config:
            llm_config = LLMConfig(
                provider="ollama",
                model="qwen3:latest",
                temperature=0.4,
                max_tokens=8192,
            )

        # Apply overrides
        if self._model_override or self._provider_override or self._base_url_override:
            llm_config = LLMConfig(
                provider=self._provider_override or llm_config.provider,
                model=self._model_override or llm_config.model,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                base_url=self._base_url_override or llm_config.base_url,
            )

        llm = create_crewai_llm(llm_config)

        self._llm_cache[duke_name] = (llm, llm_config)
        return llm, llm_config

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    def _is_retryable_exception(self, exc: Exception) -> bool:
        message = str(exc).lower()
        retry_signals = [
            "service temporarily unavailable",
            "temporarily unavailable",
            "ollamaexception",
            "api connection",
            "connection error",
            "connectionerror",
            "timeout",
            "timed out",
            "rate limit",
            "429",
            "503",
        ]
        return any(signal in message for signal in retry_signals)

    def _backoff_delay(self, attempt: int) -> float:
        base = float(os.getenv("DUKE_PROPOSAL_BACKOFF_BASE_SECONDS", "1.0"))
        maximum = float(os.getenv("DUKE_PROPOSAL_BACKOFF_MAX_SECONDS", "8.0"))
        delay = min(maximum, base * (2 ** (attempt - 1)))
        jitter = delay * random.uniform(0.1, 0.25)
        return delay + jitter

    # ------------------------------------------------------------------
    # RFP context building
    # ------------------------------------------------------------------

    def _build_rfp_context(self, rfp: RFPDocument) -> str:
        """Build compact RFP summary for the prompt.

        Includes requirements, constraints, deliverables, evaluation criteria.
        Excludes full portfolio_contributions to stay within token budget.
        """
        sections: list[str] = []

        # Background
        sections.append(f"MOTION TITLE: {rfp.motion_title}")
        sections.append(f"MOTION TEXT: {rfp.motion_text}")
        if rfp.business_justification:
            sections.append(f"BUSINESS JUSTIFICATION: {rfp.business_justification}")

        # Scope
        if rfp.objectives:
            sections.append("OBJECTIVES:")
            for obj in rfp.objectives:
                sections.append(f"  - {obj}")

        # Functional Requirements
        if rfp.functional_requirements:
            sections.append("\nFUNCTIONAL REQUIREMENTS:")
            for fr in rfp.functional_requirements:
                sections.append(
                    f"  {fr.req_id} [{fr.priority.value}]: {fr.description}"
                )
                if fr.acceptance_criteria:
                    for ac in fr.acceptance_criteria:
                        sections.append(f"    AC: {ac}")

        # Non-Functional Requirements
        if rfp.non_functional_requirements:
            sections.append("\nNON-FUNCTIONAL REQUIREMENTS:")
            for nfr in rfp.non_functional_requirements:
                metric = f" (metric: {nfr.target_metric})" if nfr.target_metric else ""
                sections.append(
                    f"  {nfr.req_id} [{nfr.category.value}]: {nfr.description}{metric}"
                )

        # Constraints
        if rfp.constraints:
            sections.append("\nCONSTRAINTS:")
            for c in rfp.constraints:
                neg = " [negotiable]" if c.negotiable else " [non-negotiable]"
                sections.append(
                    f"  {c.constraint_id} [{c.constraint_type.value}]{neg}: {c.description}"
                )

        # Deliverables
        if rfp.deliverables:
            sections.append("\nDELIVERABLES:")
            for d in rfp.deliverables:
                sections.append(f"  {d.deliverable_id}: {d.name} - {d.description}")

        # Evaluation Criteria
        if rfp.evaluation_criteria:
            sections.append("\nEVALUATION CRITERIA:")
            for ec in rfp.evaluation_criteria:
                sections.append(
                    f"  {ec.criterion_id}: {ec.name} ({ec.priority_band}) - {ec.description}"
                )

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Proposal generation
    # ------------------------------------------------------------------

    async def generate_proposal(
        self,
        rfp: RFPDocument,
        duke_archon_id: str,
        duke_name: str,
        duke_domain: str,
        duke_role: str,
        duke_backstory: str,
        duke_personality: str,
    ) -> DukeProposal:
        """Generate a complete implementation proposal for the given RFP."""
        llm, llm_config = self._get_duke_llm(duke_name)
        abbrev = _duke_abbreviation(duke_name)
        rfp_context = self._build_rfp_context(rfp)

        # Build FR/NFR ID lists for coverage template
        fr_ids = [fr.req_id for fr in rfp.functional_requirements]
        nfr_ids = [nfr.req_id for nfr in rfp.non_functional_requirements]
        deliverable_ids = [d.deliverable_id for d in rfp.deliverables]

        proposal_prompt = f"""You are Duke {duke_name}, {duke_role}.

{self.ADMINISTRATIVE_SCOPE_CONSTRAINT}
{self.CONTEXT_PURITY_CONSTRAINT}
{self.BRANCH_BOUNDARY_CONSTRAINT}

YOUR IDENTITY:
- Name: {duke_name}
- Role: {duke_role}
- Backstory: {duke_backstory}
- ID Prefix: {abbrev} (use for all tactic/risk/resource IDs)

RFP CONTEXT:
{rfp_context}

TASK: Produce a complete implementation proposal for this RFP from your domain expertise.
Propose HOW to accomplish all requirements. Do NOT redefine requirements.

OUTPUT FORMAT: Markdown with the following section structure.
Use ID prefix "{abbrev}" for all IDs.

# Proposal from Duke {duke_name}

## Executive Summary
Brief overview of your approach.

## Approach Philosophy
Your guiding principles for this implementation.

## Tactics
One subsection per tactic:

### T-{abbrev}-001: <title>
- **Description:** ...
- **Rationale:** ...
- **Prerequisites:** ...
- **Dependencies:** ...
- **Estimated Duration:** P7D
- **Owner:** duke_{duke_name.lower()}

### T-{abbrev}-002: <title>
...

## Risks
One subsection per risk:

### R-{abbrev}-001: <title>
- **Description:** ...
- **Likelihood:** RARE|UNLIKELY|POSSIBLE|LIKELY|ALMOST_CERTAIN
- **Impact:** NEGLIGIBLE|MINOR|MODERATE|MAJOR|SEVERE
- **Mitigation Strategy:** ...
- **Contingency Plan:** ...
- **Trigger Conditions:** ...

## Resource Requests
One subsection per resource request:

### RR-{abbrev}-001: <title>
- **Type:** COMPUTE|STORAGE|NETWORK|HUMAN_HOURS|TOOLING|EXTERNAL_SERVICE|BUDGET|ACCESS|OTHER
- **Description:** ...
- **Justification:** ...
- **Required By:** 2026-06-01T00:00:00Z
- **Priority:** CRITICAL|HIGH|MEDIUM|LOW

## Capacity Commitment
| Field | Value |
|-------|-------|
| Portfolio ID | duke_{duke_name.lower()} |
| Committed Units | 40.0 |
| Unit Label | hours |
| Confidence | HIGH/MEDIUM/LOW/SPECULATIVE |

## Requirement Coverage
One row per requirement:

| Requirement ID | Type | Covered | Description | Tactic References | Confidence |
|---------------|------|---------|-------------|-------------------|------------|
| FR-xxx | functional | Yes | How addressed | T-{abbrev}-001 | HIGH |

REQUIREMENT IDS TO COVER: {json.dumps(fr_ids + nfr_ids)}

## Deliverable Plan
| Deliverable ID | Approach | Tactic References | Duration | Dependencies |
|---------------|----------|-------------------|----------|--------------|
| D-xxx | How you produce it | T-{abbrev}-001 | P14D | |

DELIVERABLE IDS TO COVER: {json.dumps(deliverable_ids)}

## Assumptions
- List each assumption as a bullet point

## Constraints Acknowledged
- List each acknowledged constraint as a bullet point

CRITICAL: Output ONLY Markdown. No JSON. No code fences wrapping the entire response."""

        agent = Agent(
            role=f"Duke {duke_name} - {duke_role}",
            goal=(
                f"Produce a complete implementation proposal for the RFP "
                f"from {duke_name}'s domain expertise perspective"
            ),
            backstory=(
                f"You are Duke {duke_name}. {duke_backstory} "
                f"You propose HOW to implement requirements within the "
                f"Administrative branch scope."
            ),
            llm=llm,
            verbose=self._verbose,
        )

        task = Task(
            description=proposal_prompt,
            expected_output="Markdown document with implementation proposal",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=self._verbose,
        )

        max_attempts = int(os.getenv("DUKE_PROPOSAL_CREWAI_RETRIES", "3"))
        attempts = 0
        last_raw = ""
        generated_at = datetime.now(timezone.utc).isoformat()
        llm_model = llm_config.model if llm_config else ""
        llm_provider = llm_config.provider if llm_config else ""

        while attempts < max_attempts:
            attempts += 1
            try:
                result = crew.kickoff()
            except Exception as exc:
                if attempts < max_attempts and self._is_retryable_exception(exc):
                    await asyncio.sleep(self._backoff_delay(attempts))
                    continue
                raise

            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)
            last_raw = raw_output

            if not raw_output or not raw_output.strip():
                if attempts < max_attempts:
                    await asyncio.sleep(self._backoff_delay(attempts))
                    continue
                break

            # Lint for constitutional compliance
            violations = self._lint_proposal(raw_output)
            if violations:
                if attempts < max_attempts:
                    await asyncio.sleep(self._backoff_delay(attempts))
                    continue
                return self._build_failed_proposal(
                    abbrev=abbrev,
                    duke_archon_id=duke_archon_id,
                    duke_name=duke_name,
                    duke_domain=duke_domain,
                    rfp_id=rfp.implementation_dossier_id,
                    mandate_id=rfp.mandate_id,
                    created_at=generated_at,
                    failure_reason="; ".join(violations),
                    llm_model=llm_model,
                    llm_provider=llm_provider,
                )

            return self._build_proposal_from_markdown(
                raw_markdown=raw_output,
                abbrev=abbrev,
                duke_archon_id=duke_archon_id,
                duke_name=duke_name,
                duke_domain=duke_domain,
                rfp_id=rfp.implementation_dossier_id,
                mandate_id=rfp.mandate_id,
                created_at=generated_at,
                llm_model=llm_model,
                llm_provider=llm_provider,
            )

        # All attempts exhausted
        return self._build_failed_proposal(
            abbrev=abbrev,
            duke_archon_id=duke_archon_id,
            duke_name=duke_name,
            duke_domain=duke_domain,
            rfp_id=rfp.implementation_dossier_id,
            mandate_id=rfp.mandate_id,
            created_at=generated_at,
            failure_reason="Empty response after all attempts"
            if not last_raw.strip()
            else "Lint violations after all attempts",
            llm_model=llm_model,
            llm_provider=llm_provider,
        )

    # ------------------------------------------------------------------
    # Markdown → DukeProposal helpers
    # ------------------------------------------------------------------

    def _build_proposal_from_markdown(
        self,
        raw_markdown: str,
        abbrev: str,
        duke_archon_id: str,
        duke_name: str,
        duke_domain: str,
        rfp_id: str,
        mandate_id: str,
        created_at: str,
        llm_model: str,
        llm_provider: str,
    ) -> DukeProposal:
        """Wrap raw Markdown + extracted counts into a DukeProposal."""
        counts = self._extract_counts(raw_markdown, abbrev)

        return DukeProposal(
            proposal_id=f"dprop-{abbrev.lower()}-{uuid.uuid4().hex[:8]}",
            duke_archon_id=duke_archon_id,
            duke_name=duke_name,
            duke_domain=duke_domain,
            duke_abbreviation=abbrev,
            rfp_id=rfp_id,
            mandate_id=mandate_id,
            status=ProposalStatus.GENERATED,
            created_at=created_at,
            proposal_markdown=raw_markdown,
            tactic_count=counts["tactics"],
            risk_count=counts["risks"],
            resource_request_count=counts["resource_requests"],
            requirement_coverage_count=counts["requirement_coverage"],
            deliverable_plan_count=counts["deliverable_plans"],
            assumption_count=counts["assumptions"],
            constraint_count=counts["constraints"],
            llm_model=llm_model,
            llm_provider=llm_provider,
        )

    def _build_failed_proposal(
        self,
        abbrev: str,
        duke_archon_id: str,
        duke_name: str,
        duke_domain: str,
        rfp_id: str,
        mandate_id: str,
        created_at: str,
        failure_reason: str,
        llm_model: str = "",
        llm_provider: str = "",
    ) -> DukeProposal:
        """Build a FAILED DukeProposal."""
        return DukeProposal(
            proposal_id=f"dprop-{abbrev.lower()}-{uuid.uuid4().hex[:8]}",
            duke_archon_id=duke_archon_id,
            duke_name=duke_name,
            duke_domain=duke_domain,
            duke_abbreviation=abbrev,
            rfp_id=rfp_id,
            mandate_id=mandate_id,
            status=ProposalStatus.FAILED,
            created_at=created_at,
            failure_reason=failure_reason,
            llm_model=llm_model,
            llm_provider=llm_provider,
        )

    # ------------------------------------------------------------------
    # Count extraction
    # ------------------------------------------------------------------

    def _extract_counts(self, markdown: str, abbrev: str) -> dict[str, int]:
        """Extract structured counts from Markdown section headers and tables."""
        return {
            "tactics": len(re.findall(r"^###\s+T-", markdown, re.MULTILINE)),
            "risks": len(re.findall(r"^###\s+R-", markdown, re.MULTILINE)),
            "resource_requests": len(re.findall(r"^###\s+RR-", markdown, re.MULTILINE)),
            "requirement_coverage": self._count_table_rows(
                markdown, "Requirement Coverage"
            ),
            "deliverable_plans": self._count_table_rows(markdown, "Deliverable Plan"),
            "assumptions": self._count_list_items(markdown, "Assumptions"),
            "constraints": self._count_list_items(markdown, "Constraints Acknowledged"),
        }

    def _count_table_rows(self, markdown: str, section_name: str) -> int:
        """Count data rows in a Markdown table under the given ## section."""
        pattern = rf"^##\s+{re.escape(section_name)}\s*$(.*?)(?=^##\s|\Z)"
        match = re.search(pattern, markdown, re.MULTILINE | re.DOTALL)
        if not match:
            return 0
        section_text = match.group(1)
        # Table rows start with | and are not the header separator (|---|)
        rows = re.findall(r"^\|(?![\s-]*\|)", section_text, re.MULTILINE)
        # Subtract 1 for the header row
        return max(0, len(rows) - 1)

    def _count_list_items(self, markdown: str, section_name: str) -> int:
        """Count bullet-point list items under the given ## section."""
        pattern = rf"^##\s+{re.escape(section_name)}\s*$(.*?)(?=^##\s|\Z)"
        match = re.search(pattern, markdown, re.MULTILINE | re.DOTALL)
        if not match:
            return 0
        section_text = match.group(1)
        return len(re.findall(r"^\s*[-*]\s+", section_text, re.MULTILINE))

    # ------------------------------------------------------------------
    # Linting
    # ------------------------------------------------------------------

    def _lint_proposal(self, markdown: str) -> list[str]:
        """Lint proposal Markdown for constitutional compliance.

        Checks:
        - No cross-branch assignment
        """
        violations: list[str] = []

        lowered = markdown.lower()

        # Check for cross-branch assignment
        branch_terms = (
            "legislative",
            "executive",
            "judicial",
            "conclave shall",
            "king shall",
            "president shall",
        )
        assignment_phrases = (
            "must be performed by",
            "must be validated by",
            "must be approved by",
            "assigned to the",
            "responsibility of the",
        )

        for phrase in assignment_phrases:
            if phrase in lowered:
                for branch in branch_terms:
                    if branch in lowered:
                        violations.append(
                            f"Cross-branch assignment detected: '{phrase}' with '{branch}'"
                        )
                        break

        # Dedupe
        return list(dict.fromkeys(violations))


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def create_duke_proposal_generator(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    llm_config: LLMConfig | None = None,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
) -> DukeProposalCrewAIAdapter:
    """Factory function to create a Duke Proposal generator adapter.

    Args:
        profile_repository: Repository for Archon profiles with LLM configs
        verbose: Enable verbose logging
        llm_config: Default LLM configuration
        model: Override model name
        provider: Override LLM provider (e.g., 'ollama', 'openai', 'anthropic')
        base_url: Override base URL

    Returns:
        Configured DukeProposalCrewAIAdapter
    """
    return DukeProposalCrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        llm_config=llm_config,
        model=model,
        provider=provider,
        base_url=base_url,
    )
