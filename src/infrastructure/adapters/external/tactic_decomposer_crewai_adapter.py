"""CrewAI adapter for multi-Earl collaborative tactic decomposition.

All 6 Earls (strategic_director rank) decompose every tactic independently
using their own per-archon LLM binding, then a facilitator Earl synthesizes
the best elements into a unified set of TaskDrafts.

Follows the President scoring + deliberation pattern from
proposal_scorer_crewai_adapter.py:
- Per-archon LLM binding from ArchonProfileRepository (cached)
- Crew(agents=[agent], tasks=[task]) -> crew.kickoff()
- Retry with exponential backoff, per-Earl checkpointing
- Facilitator synthesis merges all Earl decompositions

Pipeline per tactic:
  1. Load all 6 Earls via profile_repository.get_by_rank("strategic_director")
  2. Run each Earl sequentially with its own LLM
  3. Save per-Earl checkpoints (T-ZEPA-001.earl_raum.json, etc.)
  4. Resolve facilitator Earl (closest domain match or default Bifrons)
  5. Synthesis phase: facilitator merges best elements
  6. Return synthesized TaskDrafts with vote_count metadata
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.application.llm.crewai_llm_factory import create_crewai_llm
from src.application.ports.tactic_decomposition import (
    DecompositionContext,
    TacticDecomposerProtocol,
)
from src.domain.models.earl_decomposition import EarlVote
from src.domain.models.llm_config import LLMConfig
from src.infrastructure.adapters.external.crewai_json_utils import parse_json_response
from src.optional_deps.crewai import Agent, Crew, Task

if TYPE_CHECKING:
    from src.domain.models.archon_profile import ArchonProfile
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        ArchonProfileRepository,
    )
    from src.optional_deps.crewai import LLM


# Valid capability tags from cluster-schema.json
_VALID_CAPABILITY_TAGS = {
    "research",
    "analysis",
    "writing",
    "review",
    "design",
    "dev_backend",
    "dev_frontend",
    "devops",
    "security",
    "data_engineering",
    "qa_testing",
    "product_ops",
    "community_ops",
    "incident_response",
    "compliance_ops",
    "other",
}


class TacticDecomposerCrewAIAdapter(TacticDecomposerProtocol):
    """CrewAI adapter: multi-Earl collaborative tactic decomposition."""

    def __init__(
        self,
        profile_repository: ArchonProfileRepository,
        earl_routing_table: dict[str, Any] | None = None,
        verbose: bool = False,
        checkpoint_dir: Path | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._earl_routing_table = earl_routing_table or {}
        self._verbose = verbose
        self._checkpoint_dir = checkpoint_dir
        self._llm_cache: dict[str, tuple[LLM | object, LLMConfig]] = {}
        self._earl_profiles: list[ArchonProfile] | None = None

    # ------------------------------------------------------------------
    # Earl profile loading
    # ------------------------------------------------------------------

    def _load_earl_profiles(self) -> list[ArchonProfile]:
        """Load the 6 Earl strategic directors via branch filter.

        Uses get_by_branch("administrative_strategic") to get exactly the
        6 Earls, excluding Princes (judicial) and Knight-Witness (witness)
        who share the same aegis_rank but belong to different branches.
        """
        if self._earl_profiles is not None:
            return self._earl_profiles
        self._earl_profiles = self._profile_repository.get_by_branch(
            "administrative_strategic"
        )
        if self._verbose:
            names = [p.name for p in self._earl_profiles]
            print(f"    [multi-earl] loaded {len(self._earl_profiles)} earls: {names}")
        return self._earl_profiles

    # ------------------------------------------------------------------
    # LLM resolution (per-Earl, cached)
    # ------------------------------------------------------------------

    def _get_earl_llm(self, earl_name: str) -> tuple[LLM | object, LLMConfig]:
        """Get an Earl's LLM from their profile (cached).

        Follows the _get_president_llm pattern from proposal_scorer_crewai_adapter.
        """
        if earl_name in self._llm_cache:
            return self._llm_cache[earl_name]

        llm_config: LLMConfig | None = None

        profile = self._profile_repository.get_by_name(earl_name)
        if profile and profile.llm_config:
            llm_config = profile.llm_config

        if not llm_config:
            llm_config = LLMConfig(
                provider="local",
                model="qwen3:latest",
                temperature=0.4,
                max_tokens=4096,
            )

        llm = create_crewai_llm(llm_config)
        if self._verbose:
            print(
                f"    [earl-llm] {earl_name} -> "
                f"crewai_llm_initialized model={llm_config.model} "
                f"provider={llm_config.provider}"
            )
        self._llm_cache[earl_name] = (llm, llm_config)
        return llm, llm_config

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            signal in message
            for signal in [
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
        )

    @staticmethod
    def _backoff(attempt: int) -> float:
        base = float(os.getenv("TACTIC_DECOMPOSER_BACKOFF_BASE", "1.0"))
        maximum = float(os.getenv("TACTIC_DECOMPOSER_BACKOFF_MAX", "8.0"))
        delay = min(maximum, base * (2 ** (attempt - 1)))
        return delay + delay * random.uniform(0.1, 0.25)

    # ------------------------------------------------------------------
    # Checkpointing (per-Earl)
    # ------------------------------------------------------------------

    def _checkpoint_path(self, tactic_id: str, suffix: str) -> Path | None:
        if self._checkpoint_dir is None:
            return None
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return self._checkpoint_dir / f"{tactic_id}.{suffix}"

    def _save_checkpoint(
        self, tactic_id: str, suffix: str, data: list[dict[str, Any]]
    ) -> None:
        path = self._checkpoint_path(tactic_id, suffix)
        if path is None:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if self._verbose:
            print(f"    [checkpoint] saved {tactic_id}.{suffix}")

    def _load_checkpoint(
        self, tactic_id: str, suffix: str
    ) -> list[dict[str, Any]] | None:
        path = self._checkpoint_path(tactic_id, suffix)
        if path is not None and path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    if self._verbose:
                        print(f"    [checkpoint] loaded {tactic_id}.{suffix}")
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return None

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_decomposition_prompt(
        context: DecompositionContext,
        earl_profile: ArchonProfile,
    ) -> str:
        """Build the decomposition prompt for a single Earl."""
        tactic = context.tactic
        abbrev = tactic.tactic_id.split("-")[1] if "-" in tactic.tactic_id else "XXXX"
        num = tactic.tactic_id.rsplit("-", 1)[-1] if "-" in tactic.tactic_id else "001"

        fr_line = (
            ", ".join(context.related_fr_ids[:6]) if context.related_fr_ids else "None"
        )
        nfr_line = (
            ", ".join(context.related_nfr_ids[:6])
            if context.related_nfr_ids
            else "None"
        )
        constraint_line = (
            "; ".join(context.constraints[:4]) if context.constraints else "None"
        )
        ac_line = (
            "; ".join(context.deliverable_acceptance_criteria[:4])
            if context.deliverable_acceptance_criteria
            else "None"
        )

        return f"""You are {earl_profile.name}, {earl_profile.role}.
{earl_profile.backstory}

Your task is to decompose the following high-level Duke proposal tactic into concrete, activation-ready tasks for Aegis Clusters.

TACTIC TO DECOMPOSE:
- Tactic ID: {tactic.tactic_id}
- Title: {tactic.title}
- Description: {tactic.description}
- Deliverable: {tactic.deliverable_id or "None"}
- Duration: {tactic.duration or "Not specified"}
- Prerequisites: {tactic.prerequisites or "None"}
- Dependencies: {tactic.dependencies or "None"}

RFP CONTEXT:
- RFP ID: {context.rfp_id}
- Mandate ID: {context.mandate_id}
- Proposal ID: {context.proposal_id}
- Deliverable Name: {context.deliverable_name or "Not specified"}
- Acceptance Criteria: {ac_line}
- Related FRs: {fr_line}
- Related NFRs: {nfr_line}
- Constraints: {constraint_line}

DECOMPOSITION RULES:
1. Produce 2-5 concrete tasks. Each task MUST be independently assignable to a single Cluster.
2. Each task MUST have a clear description (not vague, not a restatement of the tactic title).
3. Each task MUST have at least 2 specific expected outcomes (not placeholders like "TBD" or "done").
4. Each task MUST have at least 1 capability_tag from the valid set.
5. Each task MUST have a positive effort_hours estimate.
6. Tasks should reference parent FR/NFR IDs in their requirements where applicable.
7. Task refs follow the pattern: TASK-{abbrev}-{num}a, TASK-{abbrev}-{num}b, etc.

VALID CAPABILITY TAGS (use only these):
research, analysis, writing, review, design, dev_backend, dev_frontend,
devops, security, data_engineering, qa_testing, product_ops, community_ops,
incident_response, compliance_ops, other

OUTPUT FORMAT: JSON array. Output ONLY the JSON array, no markdown fences, no extra text.

[
  {{
    "task_ref": "TASK-{abbrev}-{num}a",
    "parent_tactic_id": "{tactic.tactic_id}",
    "rfp_id": "{context.rfp_id}",
    "mandate_id": "{context.mandate_id}",
    "proposal_id": "{context.proposal_id}",
    "deliverable_id": "{tactic.deliverable_id or ""}",
    "description": "Concrete description of what must be done",
    "requirements": ["Addresses FR-XXX-001", "Contributes to deliverable D-001"],
    "expected_outcomes": ["Specific measurable outcome 1", "Specific measurable outcome 2"],
    "capability_tags": ["dev_backend"],
    "effort_hours": 8.0,
    "dependencies": []
  }}
]"""

    @staticmethod
    def _build_synthesis_prompt(
        context: DecompositionContext,
        earl_results: dict[str, list[dict[str, Any]]],
    ) -> str:
        """Build the synthesis prompt for the facilitator Earl."""
        tactic = context.tactic

        # Format each Earl's decomposition
        decomposition_sections: list[str] = []
        for earl_name, drafts in earl_results.items():
            section = f"### Earl {earl_name} ({len(drafts)} tasks):\n"
            section += json.dumps(drafts, indent=2)
            decomposition_sections.append(section)

        all_decompositions = "\n\n".join(decomposition_sections)

        return f"""You are the facilitator Earl synthesizing multiple independent tactic decompositions.

{len(earl_results)} Earls have independently decomposed the same tactic. Your job is to merge
the best elements from all decompositions into a single, unified set of TaskDrafts.

ORIGINAL TACTIC:
- Tactic ID: {tactic.tactic_id}
- Title: {tactic.title}
- Description: {tactic.description}

INDEPENDENT DECOMPOSITIONS:
{all_decompositions}

SYNTHESIS RULES:
1. Merge the best descriptions, requirements, and expected outcomes across all Earls.
2. Deduplicate tasks that cover the same work — pick the most detailed version.
3. Resolve conflicts by choosing the most specific and actionable version.
4. Keep 2-5 tasks total in the final output.
5. Each task must have a unique task_ref, matching pattern TASK-XXXX-NNNx.
6. Preserve all valid capability_tags, effort_hours, and dependency information.
7. For each task, record how many Earls proposed similar work in a "vote_count" field.
8. For each task, list which Earls contributed in a "contributing_earls" field (array of names).

VALID CAPABILITY TAGS (use only these):
research, analysis, writing, review, design, dev_backend, dev_frontend,
devops, security, data_engineering, qa_testing, product_ops, community_ops,
incident_response, compliance_ops, other

OUTPUT FORMAT: JSON array. Output ONLY the JSON array, no markdown fences, no extra text.
Each object must include all fields from the original schema plus vote_count and contributing_earls."""

    # ------------------------------------------------------------------
    # Single-Earl decomposition
    # ------------------------------------------------------------------

    async def _decompose_single_earl(
        self,
        earl_profile: ArchonProfile,
        context: DecompositionContext,
    ) -> list[dict[str, Any]]:
        """Run one Earl's independent decomposition of a tactic."""
        tactic_id = context.tactic.tactic_id
        earl_name = earl_profile.name

        # Check per-Earl checkpoint
        suffix = f"earl_{earl_name.lower()}.json"
        cached = self._load_checkpoint(tactic_id, suffix)
        if cached is not None:
            return cached

        llm, llm_config = self._get_earl_llm(earl_name)
        prompt = self._build_decomposition_prompt(context, earl_profile)
        max_attempts = int(os.getenv("TACTIC_DECOMPOSER_RETRIES", "3"))

        for attempt in range(1, max_attempts + 1):
            try:
                raw = await self._call_crewai(
                    llm=llm,
                    role=earl_profile.role,
                    backstory=earl_profile.backstory,
                    prompt=prompt,
                    tactic_id=tactic_id,
                    earl_name=earl_name,
                )

                data = parse_json_response(raw, aggressive=True)

                if isinstance(data, dict):
                    data = [data]
                if not isinstance(data, list):
                    raise ValueError(f"Expected JSON array, got {type(data).__name__}")

                # Sanitize capability tags
                for draft in data:
                    if "capability_tags" in draft:
                        draft["capability_tags"] = [
                            t
                            for t in draft["capability_tags"]
                            if t in _VALID_CAPABILITY_TAGS
                        ] or ["other"]

                if self._verbose:
                    print(
                        f"    [{tactic_id}] Earl {earl_name} produced "
                        f"{len(data)} task drafts (attempt {attempt})"
                    )

                # Save per-Earl checkpoint
                self._save_checkpoint(tactic_id, suffix, data)
                return data

            except Exception as exc:
                if self._verbose:
                    print(
                        f"    [{tactic_id}] Earl {earl_name} attempt "
                        f"{attempt}/{max_attempts} failed: {exc}"
                    )
                if attempt < max_attempts and self._is_retryable(exc):
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                if attempt >= max_attempts:
                    if self._verbose:
                        print(
                            f"    [{tactic_id}] Earl {earl_name} all attempts exhausted"
                        )
                    return []

        return []

    # ------------------------------------------------------------------
    # Facilitator resolution
    # ------------------------------------------------------------------

    def _resolve_facilitator(
        self,
        context: DecompositionContext,
        earl_profiles: list[ArchonProfile],
    ) -> ArchonProfile:
        """Resolve the facilitator Earl via closest domain match.

        1. Look up tactic's deliverable domain from RFP context
        2. Match to earl_routing_table portfolio_to_earl
        3. Fall back to default_earl_id (Bifrons)
        4. Final fallback: first Earl in the list
        """
        portfolio_to_earl = self._earl_routing_table.get("portfolio_to_earl", {})
        default_earl_id = self._earl_routing_table.get("default_earl_id", "")

        # Try domain match from deliverable name or tactic description
        match_text = (
            (context.deliverable_name or "") + " " + (context.tactic.description or "")
        ).lower()

        for domain, earl_id_str in portfolio_to_earl.items():
            if domain.lower() in match_text:
                # Find the profile matching this earl_id
                for profile in earl_profiles:
                    if str(profile.id) == earl_id_str:
                        if self._verbose:
                            print(
                                f"    [facilitator] domain match '{domain}' "
                                f"-> {profile.name}"
                            )
                        return profile

        # Fall back to default earl
        if default_earl_id:
            for profile in earl_profiles:
                if str(profile.id) == default_earl_id:
                    if self._verbose:
                        print(f"    [facilitator] default -> {profile.name}")
                    return profile

        # Final fallback: first Earl
        if self._verbose:
            print(f"    [facilitator] fallback -> {earl_profiles[0].name}")
        return earl_profiles[0]

    # ------------------------------------------------------------------
    # Synthesis phase
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        earl_results: dict[str, list[dict[str, Any]]],
        facilitator_profile: ArchonProfile,
        context: DecompositionContext,
    ) -> list[dict[str, Any]]:
        """Facilitator Earl merges all decompositions into final TaskDrafts."""
        tactic_id = context.tactic.tactic_id

        llm, llm_config = self._get_earl_llm(facilitator_profile.name)
        prompt = self._build_synthesis_prompt(context, earl_results)
        max_attempts = int(os.getenv("TACTIC_DECOMPOSER_RETRIES", "3"))

        for attempt in range(1, max_attempts + 1):
            try:
                raw = await self._call_crewai(
                    llm=llm,
                    role=f"Synthesis Facilitator — {facilitator_profile.role}",
                    backstory=(
                        f"You are {facilitator_profile.name}, serving as the "
                        f"synthesis facilitator. {facilitator_profile.backstory} "
                        f"You excel at merging diverse perspectives into "
                        f"unified, actionable plans."
                    ),
                    prompt=prompt,
                    tactic_id=tactic_id,
                    earl_name=f"{facilitator_profile.name}_synthesis",
                )

                data = parse_json_response(raw, aggressive=True)

                if isinstance(data, dict):
                    data = [data]
                if not isinstance(data, list):
                    raise ValueError(f"Expected JSON array, got {type(data).__name__}")

                # Sanitize capability tags
                for draft in data:
                    if "capability_tags" in draft:
                        draft["capability_tags"] = [
                            t
                            for t in draft["capability_tags"]
                            if t in _VALID_CAPABILITY_TAGS
                        ] or ["other"]

                if self._verbose:
                    print(
                        f"    [{tactic_id}] synthesis produced "
                        f"{len(data)} merged task drafts "
                        f"(facilitator: {facilitator_profile.name}, "
                        f"attempt {attempt})"
                    )

                return data

            except Exception as exc:
                if self._verbose:
                    print(
                        f"    [{tactic_id}] synthesis attempt "
                        f"{attempt}/{max_attempts} failed: {exc}"
                    )
                if attempt < max_attempts and self._is_retryable(exc):
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                if attempt >= max_attempts:
                    if self._verbose:
                        print(
                            f"    [{tactic_id}] synthesis all attempts "
                            f"exhausted, falling back to first successful Earl"
                        )
                    # Fallback: return the first Earl's results
                    for drafts in earl_results.values():
                        if drafts:
                            return drafts
                    return []

        return []

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    async def decompose_tactic(
        self,
        context: DecompositionContext,
    ) -> list[dict[str, Any]]:
        """Decompose a tactic via multi-Earl collaboration + synthesis."""
        tactic_id = context.tactic.tactic_id

        # Check if final synthesis checkpoint exists
        final_cached = self._load_checkpoint(tactic_id, "task_drafts.json")
        if final_cached is not None:
            return final_cached

        # Load all Earl profiles
        earl_profiles = self._load_earl_profiles()
        if not earl_profiles:
            if self._verbose:
                print(
                    f"    [{tactic_id}] no strategic_director profiles found, "
                    f"returning empty"
                )
            return []

        # Phase 1: Run all 6 Earls sequentially
        earl_results: dict[str, list[dict[str, Any]]] = {}
        earl_votes: list[EarlVote] = []

        for profile in earl_profiles:
            if self._verbose:
                print(f"    [{tactic_id}] running Earl {profile.name}...")

            drafts = await self._decompose_single_earl(profile, context)

            earl_results[profile.name] = drafts
            earl_votes.append(
                EarlVote(
                    earl_name=profile.name,
                    earl_id=str(profile.id),
                    task_count=len(drafts),
                    succeeded=bool(drafts),
                    failure_reason="" if drafts else "empty_response",
                )
            )

        # Check if any Earls succeeded
        successful = {name: drafts for name, drafts in earl_results.items() if drafts}

        if not successful:
            if self._verbose:
                print(f"    [{tactic_id}] ALL Earls failed, returning empty")
            return []

        if self._verbose:
            print(
                f"    [{tactic_id}] {len(successful)}/{len(earl_profiles)} "
                f"Earls succeeded"
            )

        # Phase 2: Synthesis
        facilitator = self._resolve_facilitator(context, earl_profiles)

        synthesized = await self._synthesize(
            earl_results=successful,
            facilitator_profile=facilitator,
            context=context,
        )

        # Save final checkpoint
        self._save_checkpoint(tactic_id, "task_drafts.json", synthesized)

        # Save votes checkpoint for audit
        self._save_checkpoint(
            tactic_id,
            "earl_votes.json",
            [v.to_dict() for v in earl_votes],
        )

        return synthesized

    # ------------------------------------------------------------------
    # CrewAI execution
    # ------------------------------------------------------------------

    async def _call_crewai(
        self,
        llm: LLM | object,
        role: str,
        backstory: str,
        prompt: str,
        tactic_id: str,
        earl_name: str,
    ) -> str:
        """Execute a single CrewAI Agent+Task+Crew call."""
        agent = Agent(
            role=role,
            goal=f"Decompose tactic {tactic_id} into concrete, executable task drafts",
            backstory=backstory,
            llm=llm,
            verbose=self._verbose,
        )

        task = Task(
            description=prompt,
            expected_output="A JSON array of task draft objects",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=self._verbose,
        )

        result = crew.kickoff()
        raw = str(result.raw) if hasattr(result, "raw") else str(result)

        if not raw or not raw.strip():
            raise RuntimeError(f"Empty response from LLM (Earl {earl_name})")

        return raw


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def create_tactic_decomposer(
    profile_repository: ArchonProfileRepository,
    earl_routing_table: dict[str, Any] | None = None,
    verbose: bool = False,
    checkpoint_dir: Path | None = None,
) -> TacticDecomposerProtocol:
    """Factory function to create the multi-Earl CrewAI tactic decomposer.

    Args:
        profile_repository: Repository for per-Earl LLM configs (required).
        earl_routing_table: Routing table dict for facilitator resolution.
        verbose: Enable verbose logging.
        checkpoint_dir: Directory for per-Earl checkpoint files.

    Returns:
        TacticDecomposerProtocol implementation.
    """
    return TacticDecomposerCrewAIAdapter(
        profile_repository=profile_repository,
        earl_routing_table=earl_routing_table,
        verbose=verbose,
        checkpoint_dir=checkpoint_dir,
    )
