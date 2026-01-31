"""CrewAI adapter for Duke Proposal generation.

Each Administrative Duke reads a finalized Executive RFP and produces a
complete implementation proposal covering HOW to accomplish the requirements.

Multi-pass pipeline (5 phases) to avoid single-call token truncation:
  Phase 1: Strategic Foundation (Overview, Issues, Philosophy)
  Phase 2: Per-Deliverable Solutions (Tactics, Risks, Resources) - N calls
  Phase 3: Cross-Cutting (Coverage table, Deliverable plan, Assumptions, Constraints)
  Phase 4: Consolidation Review (secretary text agent reviews for consistency)
  Phase 5: Executive Summary (synthesises the completed proposal)
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
        secretary_text_archon_id: str | None = None,
        checkpoint_dir: str | Path | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._verbose = verbose
        self._default_llm_config = llm_config
        self._model_override = model
        self._provider_override = provider
        self._base_url_override = base_url
        self._llm_cache: dict[str, tuple[LLM | str, LLMConfig]] = {}
        self._secretary_text_archon_id = secretary_text_archon_id
        self._secretary_text_llm: LLM | object | None = None
        self._checkpoint_dir: Path | None = (
            Path(checkpoint_dir) if checkpoint_dir else None
        )

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

    def _get_secretary_text_llm(self) -> LLM | object | None:
        """Get the Secretary Text LLM for Phase 4 consolidation (cached).

        Resolved via secretary_text_archon_id -> profile repository.
        Returns None if archon ID was not provided.
        """
        if self._secretary_text_llm is not None:
            return self._secretary_text_llm

        if not self._secretary_text_archon_id:
            return None

        llm_config: LLMConfig | None = None

        if self._profile_repository:
            try:
                from uuid import UUID

                profile = self._profile_repository.get_by_id(
                    UUID(self._secretary_text_archon_id)
                )
                if profile and profile.llm_config:
                    llm_config = profile.llm_config
            except ValueError:
                pass

        if not llm_config:
            llm_config = LLMConfig(
                provider="ollama",
                model="qwen3:latest",
                temperature=0.3,
                max_tokens=4096,
            )

        self._secretary_text_llm = create_crewai_llm(llm_config)
        return self._secretary_text_llm

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
    # Checkpoint helpers
    # ------------------------------------------------------------------

    def _checkpoint_path(self, duke_name: str, phase_key: str) -> Path | None:
        """Return checkpoint file path, or None if checkpointing disabled."""
        if self._checkpoint_dir is None:
            return None
        duke_dir = self._checkpoint_dir / duke_name.lower()
        duke_dir.mkdir(parents=True, exist_ok=True)
        return duke_dir / f"{phase_key}.md"

    def _save_checkpoint(self, duke_name: str, phase_key: str, content: str) -> None:
        """Write markdown to checkpoint file."""
        path = self._checkpoint_path(duke_name, phase_key)
        if path is not None:
            path.write_text(content, encoding="utf-8")
            if self._verbose:
                print(f"    [checkpoint] saved {phase_key} ({len(content)} chars)")

    def _load_checkpoint(self, duke_name: str, phase_key: str) -> str | None:
        """Read checkpoint if it exists. Returns None if not found."""
        path = self._checkpoint_path(duke_name, phase_key)
        if path is not None and path.exists():
            content = path.read_text(encoding="utf-8")
            if content.strip():
                if self._verbose:
                    print(f"    [checkpoint] loaded {phase_key} ({len(content)} chars)")
                return content
        return None

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

    def _build_deliverable_context(self, rfp: RFPDocument, deliverable_id: str) -> str:
        """Build focused context for one deliverable.

        Includes the deliverable details plus related FRs/NFRs/constraints.
        """
        sections: list[str] = []

        # Find the deliverable
        target_d = None
        for d in rfp.deliverables:
            if d.deliverable_id == deliverable_id:
                target_d = d
                break
        if target_d is None:
            return f"DELIVERABLE: {deliverable_id} (not found)"

        sections.append(f"DELIVERABLE: {target_d.deliverable_id}")
        sections.append(f"  Name: {target_d.name}")
        sections.append(f"  Description: {target_d.description}")
        if target_d.acceptance_criteria:
            sections.append("  Acceptance Criteria:")
            for ac in target_d.acceptance_criteria:
                sections.append(f"    - {ac}")
        if target_d.dependencies:
            sections.append(f"  Dependencies: {', '.join(target_d.dependencies)}")

        # Include all FRs (they may relate to any deliverable)
        if rfp.functional_requirements:
            sections.append("\nFUNCTIONAL REQUIREMENTS:")
            for fr in rfp.functional_requirements:
                sections.append(
                    f"  {fr.req_id} [{fr.priority.value}]: {fr.description}"
                )

        # Include all NFRs
        if rfp.non_functional_requirements:
            sections.append("\nNON-FUNCTIONAL REQUIREMENTS:")
            for nfr in rfp.non_functional_requirements:
                sections.append(
                    f"  {nfr.req_id} [{nfr.category.value}]: {nfr.description}"
                )

        # Include constraints
        if rfp.constraints:
            sections.append("\nCONSTRAINTS:")
            for c in rfp.constraints:
                neg = " [negotiable]" if c.negotiable else " [non-negotiable]"
                sections.append(
                    f"  {c.constraint_id} [{c.constraint_type.value}]{neg}: {c.description}"
                )

        return "\n".join(sections)

    def _build_accumulated_summary(self, sections: dict[str, str], abbrev: str) -> str:
        """Build compact ID-only summary of prior phases (~200 tokens).

        Extracts T-/R-/RR- IDs from collected phase outputs.
        """
        all_text = "\n".join(sections.values())
        tactic_ids = re.findall(rf"^###\s+(T-{abbrev}-\d+)", all_text, re.MULTILINE)
        risk_ids = re.findall(rf"^###\s+(R-{abbrev}-\d+)", all_text, re.MULTILINE)
        resource_ids = re.findall(rf"^###\s+(RR-{abbrev}-\d+)", all_text, re.MULTILINE)

        parts: list[str] = []
        if tactic_ids:
            parts.append(f"Tactics so far: {', '.join(tactic_ids)}")
        if risk_ids:
            parts.append(f"Risks so far: {', '.join(risk_ids)}")
        if resource_ids:
            parts.append(f"Resources so far: {', '.join(resource_ids)}")
        return "\n".join(parts) if parts else "No prior items."

    # ------------------------------------------------------------------
    # Counter extraction from phase 2 checkpoints
    # ------------------------------------------------------------------

    def _extract_counter_state(
        self, section: str, abbrev: str, t: int, r: int, rr: int
    ) -> tuple[int, int, int]:
        """Parse highest T-/R-/RR- numbers from a section, return updated counters."""
        for m in re.finditer(rf"^###\s+T-{abbrev}-(\d+)", section, re.MULTILINE):
            t = max(t, int(m.group(1)))
        for m in re.finditer(rf"^###\s+R-{abbrev}-(\d+)", section, re.MULTILINE):
            r = max(r, int(m.group(1)))
        for m in re.finditer(rf"^###\s+RR-{abbrev}-(\d+)", section, re.MULTILINE):
            rr = max(rr, int(m.group(1)))
        return t, r, rr

    # ------------------------------------------------------------------
    # Phase runners
    # ------------------------------------------------------------------

    async def _run_phase_1_foundation(
        self,
        llm: LLM | str,
        duke_name: str,
        duke_role: str,
        duke_backstory: str,
        abbrev: str,
        rfp_context: str,
    ) -> str:
        """Phase 1: Generate Overview + Issues + Approach Philosophy."""
        prompt = f"""You are Duke {duke_name}, {duke_role}.

{self.ADMINISTRATIVE_SCOPE_CONSTRAINT}
{self.CONTEXT_PURITY_CONSTRAINT}
{self.BRANCH_BOUNDARY_CONSTRAINT}

YOUR IDENTITY:
- Name: {duke_name}
- Role: {duke_role}
- Backstory: {duke_backstory}
- ID Prefix: {abbrev}

RFP CONTEXT:
{rfp_context}

TASK: Write ONLY the following three sections for your implementation proposal.
Do NOT write tactics, risks, resources, tables, or executive summary yet.

OUTPUT FORMAT (Markdown only):

## Overview
What needs to be accomplished, current state assessment, and why this work is needed.
(3-5 sentences)

## Issues
Key pain points and problem areas this RFP addresses.
(Bullet list, 3-6 items)

## Approach Philosophy
Your guiding principles for implementing this RFP from your domain expertise.
(3-5 sentences)

CRITICAL: Output ONLY Markdown. No JSON. No code fences wrapping the entire response."""

        return await self._run_crewai_call(
            llm=llm,
            role=f"Duke {duke_name} - {duke_role}",
            goal="Produce strategic foundation sections for the implementation proposal",
            backstory=f"You are Duke {duke_name}. {duke_backstory}",
            prompt=prompt,
            expected="Markdown with Overview, Issues, and Approach Philosophy sections",
        )

    async def _run_phase_2_deliverable(
        self,
        llm: LLM | str,
        duke_name: str,
        duke_role: str,
        duke_backstory: str,
        abbrev: str,
        deliverable_context: str,
        deliverable_id: str,
        t_counter: int,
        r_counter: int,
        rr_counter: int,
        accumulated: str,
    ) -> str:
        """Phase 2: Generate tactics/risks/resources for one deliverable."""
        prompt = f"""You are Duke {duke_name}, {duke_role}.

{self.ADMINISTRATIVE_SCOPE_CONSTRAINT}
{self.CONTEXT_PURITY_CONSTRAINT}
{self.BRANCH_BOUNDARY_CONSTRAINT}

YOUR IDENTITY:
- Name: {duke_name}
- Role: {duke_role}
- Backstory: {duke_backstory}
- ID Prefix: {abbrev}

DELIVERABLE CONTEXT:
{deliverable_context}

ALREADY PRODUCED:
{accumulated}

TASK: Propose tactics, risks, and resource requests specifically for deliverable {deliverable_id}.
Start tactic numbering at T-{abbrev}-{t_counter + 1:03d}.
Start risk numbering at R-{abbrev}-{r_counter + 1:03d}.
Start resource request numbering at RR-{abbrev}-{rr_counter + 1:03d}.

Produce 2-4 tactics, 1-2 risks, and 0-2 resource requests for this deliverable.

OUTPUT FORMAT (Markdown only):

### T-{abbrev}-{t_counter + 1:03d}: <title>
- **Description:** ...
- **Deliverable:** {deliverable_id}
- **Rationale:** ...
- **Prerequisites:** ...
- **Dependencies:** ...
- **Estimated Duration:** P7D
- **Owner:** duke_{duke_name.lower()}

(repeat for each tactic)

### R-{abbrev}-{r_counter + 1:03d}: <title>
- **Description:** ...
- **Deliverable:** {deliverable_id}
- **Likelihood:** RARE|UNLIKELY|POSSIBLE|LIKELY|ALMOST_CERTAIN
- **Impact:** NEGLIGIBLE|MINOR|MODERATE|MAJOR|SEVERE
- **Mitigation Strategy:** ...
- **Contingency Plan:** ...
- **Trigger Conditions:** ...

(repeat for each risk)

### RR-{abbrev}-{rr_counter + 1:03d}: <title>
- **Type:** COMPUTE|STORAGE|NETWORK|HUMAN_HOURS|TOOLING|EXTERNAL_SERVICE|BUDGET|ACCESS|OTHER
- **Description:** ...
- **Deliverable:** {deliverable_id}
- **Justification:** ...
- **Required By:** 2026-06-01T00:00:00Z
- **Priority:** CRITICAL|HIGH|MEDIUM|LOW

(repeat for each resource request)

CRITICAL: Output ONLY Markdown. No JSON. No code fences wrapping the entire response."""

        return await self._run_crewai_call(
            llm=llm,
            role=f"Duke {duke_name} - {duke_role}",
            goal=f"Produce tactics/risks/resources for deliverable {deliverable_id}",
            backstory=f"You are Duke {duke_name}. {duke_backstory}",
            prompt=prompt,
            expected="Markdown with T-/R-/RR- subsections for this deliverable",
        )

    async def _run_phase_3_cross_cutting(
        self,
        llm: LLM | str,
        duke_name: str,
        duke_role: str,
        duke_backstory: str,
        abbrev: str,
        rfp_context: str,
        accumulated: str,
        fr_ids: list[str],
        nfr_ids: list[str],
        deliverable_ids: list[str],
    ) -> str:
        """Phase 3: Coverage table, Deliverable plan, Capacity, Assumptions, Constraints."""
        all_req_ids = json.dumps(fr_ids + nfr_ids)
        all_del_ids = json.dumps(deliverable_ids)

        prompt = f"""You are Duke {duke_name}, {duke_role}.

{self.ADMINISTRATIVE_SCOPE_CONSTRAINT}

YOUR IDENTITY:
- Name: {duke_name}
- Role: {duke_role}
- ID Prefix: {abbrev}

RFP CONTEXT (abridged):
{rfp_context}

TACTICS/RISKS/RESOURCES PRODUCED:
{accumulated}

TASK: Write the cross-cutting sections that tie everything together.
Reference the tactic IDs listed above in the coverage and deliverable tables.

OUTPUT FORMAT (Markdown only):

## Requirement Coverage
One row per requirement:

| Requirement ID | Type | Covered | Description | Tactic References | Confidence |
|---------------|------|---------|-------------|-------------------|------------|
| FR-xxx | functional | Yes | How addressed | T-{abbrev}-001 | HIGH |

REQUIREMENT IDS TO COVER: {all_req_ids}

## Deliverable Plan
| Deliverable ID | Approach | Tactic References | Duration | Dependencies |
|---------------|----------|-------------------|----------|--------------|
| D-xxx | How you produce it | T-{abbrev}-001 | P14D | |

DELIVERABLE IDS TO COVER: {all_del_ids}

## Capacity Commitment
| Field | Value |
|-------|-------|
| Portfolio ID | duke_{duke_name.lower()} |
| Committed Units | 40.0 |
| Unit Label | hours |
| Confidence | HIGH/MEDIUM/LOW/SPECULATIVE |

## Assumptions
- List each assumption as a bullet point (3-6 items)

## Constraints Acknowledged
- List each acknowledged constraint as a bullet point (reference constraint IDs)

CRITICAL: Output ONLY Markdown. No JSON. No code fences wrapping the entire response."""

        return await self._run_crewai_call(
            llm=llm,
            role=f"Duke {duke_name} - {duke_role}",
            goal="Produce requirement coverage, deliverable plan, capacity, assumptions, constraints",
            backstory=f"You are Duke {duke_name}. {duke_backstory}",
            prompt=prompt,
            expected="Markdown with coverage table, deliverable plan, capacity, assumptions, constraints",
        )

    async def _run_phase_4_consolidation(
        self,
        full_proposal: str,
        duke_name: str,
        abbrev: str,
    ) -> str:
        """Phase 4: Secretary reviews for consistency and gap detection.

        Returns the original proposal if secretary is unavailable.
        """
        secretary_llm = self._get_secretary_text_llm()
        if secretary_llm is None:
            if self._verbose:
                print("    [phase 4] skipped - no secretary text agent configured")
            return full_proposal

        prompt = f"""You are reviewing a Duke implementation proposal for consistency and completeness.
Your task is editorial, NOT creative. You must preserve all existing content and structure.

RULES:
- Preserve ALL existing ### T-, ### R-, ### RR- headers and their IDs exactly.
- Preserve ALL table rows in Coverage and Deliverable Plan tables.
- You may ONLY:
  1. Fix inconsistent tactic references in tables (e.g., referencing T-{abbrev}-099 that doesn't exist)
  2. Add a brief "## Alternatives & Trade-offs" section (3-5 sentences) if missing
  3. Flag gaps with <!-- GAP: description --> comments
- Do NOT remove, rename, or renumber any sections.
- Do NOT add new tactics, risks, or resources.
- Output the COMPLETE proposal with your corrections applied.

PROPOSAL TO REVIEW:
{full_proposal}

CRITICAL: Output ONLY the corrected Markdown. No JSON. No code fences wrapping the entire response."""

        try:
            result = await self._run_crewai_call(
                llm=secretary_llm,
                role="Secretary Consolidation Reviewer",
                goal=f"Review Duke {duke_name}'s proposal for consistency",
                backstory="You are an editorial reviewer ensuring proposal consistency.",
                prompt=prompt,
                expected="Corrected Markdown proposal",
            )
            # Sanity check: the result should still contain key markers
            if f"T-{abbrev}-" in result and len(result) >= len(full_proposal) * 0.5:
                return result
            if self._verbose:
                print(
                    "    [phase 4] consolidation output looks degraded, keeping original"
                )
            return full_proposal
        except Exception as e:
            if self._verbose:
                print(f"    [phase 4] consolidation failed: {e}, keeping original")
            return full_proposal

    async def _run_phase_5_executive_summary(
        self,
        llm: LLM | str,
        duke_name: str,
        duke_role: str,
        duke_backstory: str,
        abbrev: str,
        accumulated: str,
    ) -> str:
        """Phase 5: Generate executive summary from completed proposal."""
        prompt = f"""You are Duke {duke_name}, {duke_role}.

YOUR IDENTITY:
- Name: {duke_name}
- Role: {duke_role}
- Backstory: {duke_backstory}

PROPOSAL SUMMARY (your prior work):
{accumulated}

TASK: Write a concise executive summary of your implementation proposal.
Address: What is the core approach? What are the key risks? What is the expected outcome?

OUTPUT FORMAT (Markdown only):

## Executive Summary
(4-6 sentences summarizing your complete proposal approach, key innovations, primary risks, and expected outcomes)

CRITICAL: Output ONLY Markdown. No JSON. No code fences wrapping the entire response."""

        return await self._run_crewai_call(
            llm=llm,
            role=f"Duke {duke_name} - {duke_role}",
            goal="Produce executive summary for the implementation proposal",
            backstory=f"You are Duke {duke_name}. {duke_backstory}",
            prompt=prompt,
            expected="Markdown executive summary section",
        )

    # ------------------------------------------------------------------
    # Shared CrewAI call with retry
    # ------------------------------------------------------------------

    async def _run_crewai_call(
        self,
        llm: LLM | str | object,
        role: str,
        goal: str,
        backstory: str,
        prompt: str,
        expected: str,
    ) -> str:
        """Run a single CrewAI call with retry logic. Returns raw markdown output."""
        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm,
            verbose=self._verbose,
        )

        task = Task(
            description=prompt,
            expected_output=expected,
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=self._verbose,
        )

        max_attempts = int(os.getenv("DUKE_PROPOSAL_CREWAI_RETRIES", "3"))
        attempts = 0

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

            if not raw_output or not raw_output.strip():
                if attempts < max_attempts:
                    await asyncio.sleep(self._backoff_delay(attempts))
                    continue
                raise RuntimeError("Empty response after all attempts")

            return raw_output

        raise RuntimeError("All retry attempts exhausted")

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------

    def _assemble_final_proposal(
        self,
        duke_name: str,
        phase_1: str,
        phase_2_sections: dict[str, str],
        phase_3: str,
        phase_5: str,
    ) -> str:
        """Merge all phases into final proposal with proper section ordering.

        Re-sorts interleaved tactics/risks/resources from per-deliverable
        Phase 2 output into grouped ## sections.
        """
        # Collect all T-, R-, RR- items from Phase 2
        all_tactics: list[str] = []
        all_risks: list[str] = []
        all_resources: list[str] = []

        for section_md in phase_2_sections.values():
            self._sort_items_from_section(
                section_md, all_tactics, all_risks, all_resources
            )

        # Build the assembled proposal
        parts: list[str] = []
        parts.append(f"# Proposal from Duke {duke_name}\n")

        # Phase 5: Executive Summary (first in output)
        parts.append(phase_5.strip())
        parts.append("")

        # Phase 1: Overview, Issues, Philosophy
        parts.append(phase_1.strip())
        parts.append("")

        # Phase 2 (re-sorted): Tactics
        if all_tactics:
            parts.append("## Tactics\n")
            parts.append("\n\n".join(all_tactics))
            parts.append("")

        # Phase 2 (re-sorted): Risks
        if all_risks:
            parts.append("## Risks\n")
            parts.append("\n\n".join(all_risks))
            parts.append("")

        # Phase 2 (re-sorted): Resource Requests
        if all_resources:
            parts.append("## Resource Requests\n")
            parts.append("\n\n".join(all_resources))
            parts.append("")

        # Phase 3: Cross-cutting sections
        parts.append(phase_3.strip())
        parts.append("")

        return "\n".join(parts)

    def _sort_items_from_section(
        self,
        section_md: str,
        tactics: list[str],
        risks: list[str],
        resources: list[str],
    ) -> None:
        """Parse ### items from a section and sort into T/R/RR buckets."""
        # Split on ### headers
        items = re.split(r"(?=^### )", section_md, flags=re.MULTILINE)
        for item in items:
            item = item.strip()
            if not item:
                continue
            if re.match(r"^### T-", item):
                tactics.append(item)
            elif re.match(r"^### RR-", item):
                resources.append(item)
            elif re.match(r"^### R-", item):
                risks.append(item)

    # ------------------------------------------------------------------
    # Proposal generation (5-phase orchestrator)
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
        """Generate a complete implementation proposal via 5-phase pipeline."""
        llm, llm_config = self._get_duke_llm(duke_name)
        abbrev = _duke_abbreviation(duke_name)
        rfp_context = self._build_rfp_context(rfp)
        generated_at = datetime.now(timezone.utc).isoformat()
        llm_model = llm_config.model if llm_config else ""
        llm_provider = llm_config.provider if llm_config else ""

        fr_ids = [fr.req_id for fr in rfp.functional_requirements]
        nfr_ids = [nfr.req_id for nfr in rfp.non_functional_requirements]
        deliverable_ids = [d.deliverable_id for d in rfp.deliverables]

        if self._verbose:
            print(
                f"  [{duke_name}] starting 5-phase pipeline "
                f"({len(deliverable_ids)} deliverables)"
            )

        # Track all phase 2 sections for assembly
        phase_2_sections: dict[str, str] = {}
        t_ctr, r_ctr, rr_ctr = 0, 0, 0

        # ---- Phase 1: Foundation ----
        if self._verbose:
            print(f"  [{duke_name}] Phase 1: Foundation")

        phase_1 = self._load_checkpoint(duke_name, "phase_1_foundation")
        if phase_1 is None:
            try:
                phase_1 = await self._run_phase_1_foundation(
                    llm=llm,
                    duke_name=duke_name,
                    duke_role=duke_role,
                    duke_backstory=duke_backstory,
                    abbrev=abbrev,
                    rfp_context=rfp_context,
                )
                self._save_checkpoint(duke_name, "phase_1_foundation", phase_1)
            except Exception as exc:
                if self._verbose:
                    print(f"  [{duke_name}] Phase 1 FAILED: {exc}")
                return self._build_failed_proposal(
                    abbrev=abbrev,
                    duke_archon_id=duke_archon_id,
                    duke_name=duke_name,
                    duke_domain=duke_domain,
                    rfp_id=rfp.implementation_dossier_id,
                    mandate_id=rfp.mandate_id,
                    created_at=generated_at,
                    failure_reason=f"Phase 1 failed: {exc}",
                    llm_model=llm_model,
                    llm_provider=llm_provider,
                )

        # ---- Phase 2: Per-Deliverable Solutions ----
        for d_id in deliverable_ids:
            phase_key = f"phase_2_{d_id}"
            if self._verbose:
                print(f"  [{duke_name}] Phase 2: {d_id}")

            cached = self._load_checkpoint(duke_name, phase_key)
            if cached is not None:
                phase_2_sections[d_id] = cached
                t_ctr, r_ctr, rr_ctr = self._extract_counter_state(
                    cached, abbrev, t_ctr, r_ctr, rr_ctr
                )
                continue

            deliverable_context = self._build_deliverable_context(rfp, d_id)
            accumulated = self._build_accumulated_summary(phase_2_sections, abbrev)

            try:
                section_md = await self._run_phase_2_deliverable(
                    llm=llm,
                    duke_name=duke_name,
                    duke_role=duke_role,
                    duke_backstory=duke_backstory,
                    abbrev=abbrev,
                    deliverable_context=deliverable_context,
                    deliverable_id=d_id,
                    t_counter=t_ctr,
                    r_counter=r_ctr,
                    rr_counter=rr_ctr,
                    accumulated=accumulated,
                )
                t_ctr, r_ctr, rr_ctr = self._extract_counter_state(
                    section_md, abbrev, t_ctr, r_ctr, rr_ctr
                )
                phase_2_sections[d_id] = section_md
                self._save_checkpoint(duke_name, phase_key, section_md)
            except Exception as exc:
                if self._verbose:
                    print(f"  [{duke_name}] Phase 2 FAILED for {d_id}: {exc}")
                phase_2_sections[d_id] = (
                    f"<!-- MISSING: {d_id} - Phase 2 failed: {exc} -->"
                )

        # ---- Phase 3: Cross-Cutting ----
        if self._verbose:
            print(f"  [{duke_name}] Phase 3: Cross-Cutting")

        phase_3 = self._load_checkpoint(duke_name, "phase_3_cross_cutting")
        if phase_3 is None:
            accumulated = self._build_accumulated_summary(phase_2_sections, abbrev)
            try:
                phase_3 = await self._run_phase_3_cross_cutting(
                    llm=llm,
                    duke_name=duke_name,
                    duke_role=duke_role,
                    duke_backstory=duke_backstory,
                    abbrev=abbrev,
                    rfp_context=rfp_context,
                    accumulated=accumulated,
                    fr_ids=fr_ids,
                    nfr_ids=nfr_ids,
                    deliverable_ids=deliverable_ids,
                )
                self._save_checkpoint(duke_name, "phase_3_cross_cutting", phase_3)
            except Exception as exc:
                if self._verbose:
                    print(f"  [{duke_name}] Phase 3 FAILED: {exc}")
                return self._build_failed_proposal(
                    abbrev=abbrev,
                    duke_archon_id=duke_archon_id,
                    duke_name=duke_name,
                    duke_domain=duke_domain,
                    rfp_id=rfp.implementation_dossier_id,
                    mandate_id=rfp.mandate_id,
                    created_at=generated_at,
                    failure_reason=f"Phase 3 failed: {exc}",
                    llm_model=llm_model,
                    llm_provider=llm_provider,
                )

        # ---- Phase 5: Executive Summary (before Phase 4 so consolidation sees it) ----
        if self._verbose:
            print(f"  [{duke_name}] Phase 5: Executive Summary")

        phase_5 = self._load_checkpoint(duke_name, "phase_5_exec_summary")
        if phase_5 is None:
            accumulated = self._build_accumulated_summary(phase_2_sections, abbrev)
            try:
                phase_5 = await self._run_phase_5_executive_summary(
                    llm=llm,
                    duke_name=duke_name,
                    duke_role=duke_role,
                    duke_backstory=duke_backstory,
                    abbrev=abbrev,
                    accumulated=accumulated,
                )
                self._save_checkpoint(duke_name, "phase_5_exec_summary", phase_5)
            except Exception as exc:
                if self._verbose:
                    print(f"  [{duke_name}] Phase 5 FAILED: {exc}")
                phase_5 = (
                    "## Executive Summary\n\n(Executive summary generation failed.)"
                )

        # ---- Assemble pre-consolidation proposal ----
        assembled = self._assemble_final_proposal(
            duke_name=duke_name,
            phase_1=phase_1,
            phase_2_sections=phase_2_sections,
            phase_3=phase_3,
            phase_5=phase_5,
        )

        # ---- Phase 4: Consolidation Review ----
        if self._verbose:
            print(f"  [{duke_name}] Phase 4: Consolidation Review")

        phase_4 = self._load_checkpoint(duke_name, "phase_4_consolidated")
        if phase_4 is None:
            phase_4 = await self._run_phase_4_consolidation(
                full_proposal=assembled,
                duke_name=duke_name,
                abbrev=abbrev,
            )
            self._save_checkpoint(duke_name, "phase_4_consolidated", phase_4)

        # ---- Final output ----
        final_markdown = phase_4

        # Lint for constitutional compliance
        violations = self._lint_proposal(final_markdown)
        if violations:
            if self._verbose:
                print(f"  [{duke_name}] Lint violations: {violations}")
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

        if self._verbose:
            print(f"  [{duke_name}] Pipeline complete")

        return self._build_proposal_from_markdown(
            raw_markdown=final_markdown,
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

    # ------------------------------------------------------------------
    # Markdown -> DukeProposal helpers
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
    secretary_text_archon_id: str | None = None,
    checkpoint_dir: str | Path | None = None,
) -> DukeProposalCrewAIAdapter:
    """Factory function to create a Duke Proposal generator adapter.

    Args:
        profile_repository: Repository for Archon profiles with LLM configs
        verbose: Enable verbose logging
        llm_config: Default LLM configuration
        model: Override model name
        provider: Override LLM provider (e.g., 'ollama', 'openai', 'anthropic')
        base_url: Override base URL
        secretary_text_archon_id: Archon ID for Secretary Text agent (Phase 4)
        checkpoint_dir: Directory for checkpoint files (None disables checkpointing)

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
        secretary_text_archon_id=secretary_text_archon_id,
        checkpoint_dir=checkpoint_dir,
    )
