"""CrewAI adapter for Proposal Selection scoring.

Implements ProposalScorerProtocol using CrewAI for LLM-powered scoring,
novelty detection, and panel deliberation across Executive Presidents.

Pattern: One-agent-per-President (same as reviewer_crewai_adapter.py)
- Per-President LLM binding from ArchonProfileRepository (cached)
- Crew(agents=[agent], tasks=[task]) -> asyncio.to_thread(crew.kickoff)
- Retry with exponential backoff (2s, 4s, 8s), max 3 retries
- 500ms inter-request delay between proposals
- JSON output parsing with aggressive cleanup fallbacks
"""

from __future__ import annotations

import asyncio
import os
import random
from typing import TYPE_CHECKING
from uuid import UUID

from crewai import Agent, Crew, Task

from src.application.ports.proposal_selection import (
    ProposalScorerProtocol,
)
from src.domain.models.llm_config import LLMConfig
from src.domain.models.proposal_selection import (
    ProposalNovelty,
    ProposalScore,
    SelectionDeliberation,
)
from src.infrastructure.adapters.external.crewai_json_utils import parse_json_response

if TYPE_CHECKING:
    from crewai import LLM

    from src.application.ports.proposal_selection import SelectionContext
    from src.domain.models.duke_proposal import DukeProposal
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        ArchonProfileRepository,
    )

from src.application.llm.crewai_llm_factory import create_crewai_llm

# Maximum tokens from proposal markdown to include in scoring prompts
SCORING_TOKEN_LIMIT = 800
# Full text for finalist deliberation only
DELIBERATION_TOKEN_LIMIT = 3000

# JSON shapes for secretary repair prompts
_SCORE_JSON_SHAPE = """{
    "feasibility": 0.0, "completeness": 0.0, "risk_mitigation": 0.0,
    "resource_efficiency": 0.0, "innovation": 0.0, "alignment": 0.0,
    "overall_score": 0.0, "confidence": 0.0,
    "reasoning": "", "strengths": [], "weaknesses": []
}"""

_NOVELTY_JSON_SHAPE = """[
    {"proposal_id": "...", "novelty_score": 0.0, "category": "",
     "novelty_reason": "", "novel_elements": []}
]"""

_DELIBERATION_JSON_SHAPE = """{
    "finalist_proposal_ids": ["id1", "id2"],
    "recommended_winner_id": "the winning proposal_id",
    "recommendation_rationale": "Why this proposal was selected",
    "arguments_for": {"proposal_id": ["argument1"]},
    "arguments_against": {"proposal_id": ["concern1"]},
    "dissenting_opinions": ["opinion1"],
    "votes": {"president_name": "voted_proposal_id"}
}"""


def _truncate_proposal(markdown: str, limit: int = SCORING_TOKEN_LIMIT) -> str:
    """Truncate proposal markdown to approximately `limit` tokens.

    Rough approximation: 1 token ~ 4 characters.
    """
    char_limit = limit * 4
    if len(markdown) <= char_limit:
        return markdown
    return markdown[:char_limit] + "\n\n[... truncated for scoring ...]"


class ProposalScorerCrewAIAdapter(ProposalScorerProtocol):
    """CrewAI adapter for scoring Duke proposals via Executive Presidents."""

    def __init__(
        self,
        profile_repository: ArchonProfileRepository | None = None,
        verbose: bool = False,
        model: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        secretary_text_archon_id: str | None = None,
        secretary_json_archon_id: str | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._verbose = verbose
        self._model_override = model
        self._provider_override = provider
        self._base_url_override = base_url
        self._llm_cache: dict[str, LLM | object] = {}
        self._secretary_text_archon_id = secretary_text_archon_id
        self._secretary_json_archon_id = secretary_json_archon_id
        self._secretary_text_llm: LLM | object | None = None
        self._secretary_json_llm: LLM | object | None = None

    # ------------------------------------------------------------------
    # LLM management (per-President caching)
    # ------------------------------------------------------------------

    def _get_secretary_text_llm(self) -> LLM | object:
        """Get the Secretary Text LLM for utility agents (cached).

        Resolved via secretary_text_archon_id (passed from script) -> profile
        repository. Used for: novelty analysis, deliberation facilitation.
        """
        if self._secretary_text_llm is not None:
            return self._secretary_text_llm

        llm_config: LLMConfig | None = None

        if self._secretary_text_archon_id and self._profile_repository:
            try:
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

    def _get_secretary_json_llm(self) -> LLM | object | None:
        """Get the Secretary JSON LLM for JSON repair (cached).

        Resolved via secretary_json_archon_id (passed from script) -> profile
        repository. Used for: repairing malformed JSON output from scoring/deliberation.
        Returns None if archon ID was not provided.
        """
        if self._secretary_json_llm is not None:
            return self._secretary_json_llm

        if not self._secretary_json_archon_id:
            return None

        llm_config: LLMConfig | None = None

        if self._profile_repository:
            try:
                profile = self._profile_repository.get_by_id(
                    UUID(self._secretary_json_archon_id)
                )
                if profile and profile.llm_config:
                    llm_config = profile.llm_config
            except ValueError:
                pass

        if not llm_config:
            llm_config = LLMConfig(
                provider="ollama",
                model="qwen3:latest",
                temperature=0.0,
                max_tokens=4096,
            )

        self._secretary_json_llm = create_crewai_llm(llm_config)
        return self._secretary_json_llm

    def _repair_json_with_secretary(self, raw_output: str, context: str) -> str | None:
        """Use Secretary JSON agent to repair malformed JSON output.

        Args:
            raw_output: The malformed LLM output
            context: Description of expected JSON shape for the repair prompt

        Returns:
            Repaired JSON string, or None if secretary is unavailable
        """
        json_llm = self._get_secretary_json_llm()
        if json_llm is None:
            return None

        repair_prompt = f"""OUTPUT ONLY VALID JSON.
You are a JSON repair tool. You must ONLY reformat the input into valid JSON.
Do NOT invent new content. Do NOT add fields not present in the input.
If a field is missing, use empty arrays, empty strings, or zero values.

EXPECTED JSON SHAPE:
{context}

INPUT TO REPAIR:
{raw_output[:3000]}

Output ONLY ONE JSON object or array. No markdown. No extra text."""

        agent = Agent(
            role="Secretary JSON Parser",
            goal="Repair malformed JSON without altering meaning",
            backstory="You are a JSON repair tool. You only reformat.",
            llm=json_llm,
            verbose=self._verbose,
            allow_delegation=False,
        )

        task = Task(
            description=repair_prompt,
            expected_output="A single valid JSON object matching the required shape",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self._verbose)

        try:
            result = crew.kickoff()
            repaired = str(result.raw) if hasattr(result, "raw") else str(result)
            return repaired.strip()
        except Exception:
            return None

    def _get_president_llm(self, president_name: str) -> LLM | object:
        """Get the appropriate LLM for a President (cached)."""
        if president_name in self._llm_cache:
            return self._llm_cache[president_name]

        llm_config: LLMConfig | None = None

        if self._profile_repository:
            profile = self._profile_repository.get_by_name(president_name)
            if profile and profile.llm_config:
                llm_config = profile.llm_config

        if not llm_config:
            llm_config = LLMConfig(
                provider="ollama",
                model="qwen3:latest",
                temperature=0.3,
                max_tokens=4096,
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
        self._llm_cache[president_name] = llm
        return llm

    # ------------------------------------------------------------------
    # Retry helpers
    # ------------------------------------------------------------------

    def _is_retryable(self, exc: Exception) -> bool:
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
            "empty response",
        ]
        return any(signal in message for signal in retry_signals)

    def _backoff_delay(self, attempt: int) -> float:
        base = float(os.getenv("PROPOSAL_SCORER_BACKOFF_BASE_SECONDS", "2.0"))
        maximum = float(os.getenv("PROPOSAL_SCORER_BACKOFF_MAX_SECONDS", "8.0"))
        delay = min(maximum, base * (2 ** (attempt - 1)))
        jitter = delay * random.uniform(0.1, 0.25)
        return delay + jitter

    # ------------------------------------------------------------------
    # Score one proposal
    # ------------------------------------------------------------------

    async def score_proposal(
        self,
        president_name: str,
        president_role: str,
        president_backstory: str,
        proposal: DukeProposal,
        context: SelectionContext,
    ) -> ProposalScore:
        """One President scores one Duke proposal."""
        llm = self._get_president_llm(president_name)

        truncated = _truncate_proposal(proposal.proposal_markdown)

        scoring_prompt = f"""You are {president_name}, an Executive President.
Role: {president_role}
{president_backstory}

You are evaluating a Duke implementation proposal for an RFP.

**RFP CONTEXT:**
Motion: {context.motion_title}
RFP ID: {context.rfp_id}

**DUKE PROPOSAL (by {proposal.duke_name}):**
{truncated}

**YOUR TASK:**
Score this proposal on 6 dimensions (0-10 each):
1. feasibility - Can this actually be implemented?
2. completeness - Does it cover all RFP requirements?
3. risk_mitigation - Are risks identified and mitigated?
4. resource_efficiency - Is the resource usage reasonable?
5. innovation - Does it bring creative or novel approaches?
6. alignment - Does it align with the RFP's objectives?

Also provide:
- overall_score: Your weighted overall assessment (0-10)
- confidence: How confident you are in this assessment (0.0-1.0)
- reasoning: 2-3 sentences explaining your assessment
- strengths: List of key strengths (2-4 items)
- weaknesses: List of key weaknesses (0-4 items)

**RESPOND IN JSON FORMAT:**
{{
    "feasibility": 0.0,
    "completeness": 0.0,
    "risk_mitigation": 0.0,
    "resource_efficiency": 0.0,
    "innovation": 0.0,
    "alignment": 0.0,
    "overall_score": 0.0,
    "confidence": 0.0,
    "reasoning": "",
    "strengths": [],
    "weaknesses": []
}}
"""

        agent = Agent(
            role=president_role or f"Executive President {president_name}",
            goal=f"Score Duke proposal as {president_name}",
            backstory=president_backstory
            or "Executive President evaluating implementation proposals",
            llm=llm,
            verbose=self._verbose,
            allow_delegation=False,
        )

        task = Task(
            description=scoring_prompt,
            expected_output="JSON with dimension scores, overall_score, reasoning",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self._verbose)

        last_error: Exception | None = None
        max_retries = 3

        for attempt in range(max_retries):
            try:
                result = await asyncio.to_thread(crew.kickoff)
                raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

                if not raw_output or raw_output.strip() in ("None", "null", ""):
                    raise ValueError("Empty response from LLM")

                try:
                    parsed = parse_json_response(raw_output, aggressive=True)
                except ValueError:
                    # Try secretary JSON repair before retrying
                    repaired = self._repair_json_with_secretary(
                        raw_output, _SCORE_JSON_SHAPE
                    )
                    if repaired:
                        parsed = parse_json_response(repaired, aggressive=True)
                    else:
                        raise

                return ProposalScore(
                    president_name=president_name,
                    proposal_id=proposal.proposal_id,
                    feasibility=float(parsed.get("feasibility", 5.0)),
                    completeness=float(parsed.get("completeness", 5.0)),
                    risk_mitigation=float(parsed.get("risk_mitigation", 5.0)),
                    resource_efficiency=float(parsed.get("resource_efficiency", 5.0)),
                    innovation=float(parsed.get("innovation", 5.0)),
                    alignment=float(parsed.get("alignment", 5.0)),
                    overall_score=float(parsed.get("overall_score", 5.0)),
                    confidence=float(parsed.get("confidence", 0.5)),
                    reasoning=parsed.get("reasoning", ""),
                    strengths=parsed.get("strengths", []),
                    weaknesses=parsed.get("weaknesses", []),
                )

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1 and self._is_retryable(e):
                    if self._verbose:
                        print(
                            f"    Score retry {attempt + 1} for "
                            f"{president_name}/{proposal.duke_name}: {e!s:.100}"
                        )
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                break

        # All retries failed - return neutral score
        if self._verbose:
            print(
                f"    Scoring failed for {president_name}/{proposal.duke_name}: "
                f"{last_error}"
            )
        return ProposalScore(
            president_name=president_name,
            proposal_id=proposal.proposal_id,
            feasibility=5.0,
            completeness=5.0,
            risk_mitigation=5.0,
            resource_efficiency=5.0,
            innovation=5.0,
            alignment=5.0,
            overall_score=5.0,
            confidence=0.0,
            reasoning=f"Scoring failed after {max_retries} attempts: {last_error}",
        )

    # ------------------------------------------------------------------
    # Batch score (sequential with delay)
    # ------------------------------------------------------------------

    async def batch_score_proposals(
        self,
        president_name: str,
        president_role: str,
        president_backstory: str,
        proposals: list[DukeProposal],
        context: SelectionContext,
    ) -> list[ProposalScore]:
        """One President scores all proposals sequentially with 500ms delay."""
        scores: list[ProposalScore] = []

        for i, proposal in enumerate(proposals):
            if i > 0:
                await asyncio.sleep(0.5)

            score = await self.score_proposal(
                president_name=president_name,
                president_role=president_role,
                president_backstory=president_backstory,
                proposal=proposal,
                context=context,
            )
            scores.append(score)

            if self._verbose:
                print(
                    f"      {proposal.duke_name}: "
                    f"{score.overall_score:.1f}/10 "
                    f"(confidence={score.confidence:.2f})"
                )

        return scores

    # ------------------------------------------------------------------
    # Novelty detection
    # ------------------------------------------------------------------

    async def detect_novelty(
        self,
        proposals: list[DukeProposal],
        context: SelectionContext,
    ) -> list[ProposalNovelty]:
        """Detect novelty across the field of proposals.

        Processes proposals in batches of 10, concurrency=2.
        """
        if not proposals:
            return []

        batch_size = 10
        batches: list[list[DukeProposal]] = []
        for i in range(0, len(proposals), batch_size):
            batches.append(proposals[i : i + batch_size])

        all_novelty: list[ProposalNovelty] = []

        for batch in batches:
            batch_novelty = await self._detect_novelty_batch(batch, context)
            all_novelty.extend(batch_novelty)

        return all_novelty

    async def _detect_novelty_batch(
        self,
        proposals: list[DukeProposal],
        context: SelectionContext,
    ) -> list[ProposalNovelty]:
        """Detect novelty for a batch of proposals."""
        proposal_summaries: list[str] = []
        for p in proposals:
            summary = _truncate_proposal(p.proposal_markdown, limit=200)
            proposal_summaries.append(
                f"- **{p.proposal_id}** (Duke {p.duke_name}): {summary[:300]}"
            )

        novelty_prompt = f"""You are analyzing a batch of Duke implementation proposals for novel elements.

**RFP CONTEXT:**
Motion: {context.motion_title}
RFP ID: {context.rfp_id}

**PROPOSALS TO ANALYZE:**
{chr(10).join(proposal_summaries)}

**YOUR TASK:**
For each proposal, assess:
1. novelty_score (0.0-1.0): How novel/creative is the approach compared to standard implementations?
2. category: One of "unconventional", "cross-domain", "minority-insight", "creative", or "" (none)
3. novelty_reason: Brief explanation of what makes it novel (or why it's standard)
4. novel_elements: List of specific novel elements (empty if standard)

**RESPOND IN JSON FORMAT (array of objects):**
[
    {{
        "proposal_id": "...",
        "novelty_score": 0.0,
        "category": "",
        "novelty_reason": "",
        "novel_elements": []
    }}
]
"""

        agent = Agent(
            role="Novelty Analyst",
            goal="Identify novel and creative elements in implementation proposals",
            backstory="Expert analyst specializing in innovation assessment",
            llm=self._get_secretary_text_llm(),
            verbose=self._verbose,
            allow_delegation=False,
        )

        task = Task(
            description=novelty_prompt,
            expected_output="JSON array of novelty assessments",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self._verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            try:
                parsed = parse_json_response(raw_output, aggressive=True)
            except ValueError:
                repaired = self._repair_json_with_secretary(
                    raw_output, _NOVELTY_JSON_SHAPE
                )
                if repaired:
                    parsed = parse_json_response(repaired, aggressive=True)
                else:
                    raise

            # Handle both list and dict responses
            if isinstance(parsed, dict):
                items = parsed.get("assessments", parsed.get("proposals", [parsed]))
            else:
                items = parsed if isinstance(parsed, list) else [parsed]

            novelty_results: list[ProposalNovelty] = []
            parsed_ids = set()

            for item in items:
                if not isinstance(item, dict):
                    continue
                pid = item.get("proposal_id", "")
                parsed_ids.add(pid)
                novelty_results.append(
                    ProposalNovelty(
                        proposal_id=pid,
                        novelty_score=float(item.get("novelty_score", 0.3)),
                        category=item.get("category", ""),
                        novelty_reason=item.get("novelty_reason", ""),
                        novel_elements=item.get("novel_elements", []),
                    )
                )

            # Fill in any missing proposals
            for p in proposals:
                if p.proposal_id not in parsed_ids:
                    novelty_results.append(
                        ProposalNovelty(
                            proposal_id=p.proposal_id,
                            novelty_score=0.3,
                            novelty_reason="Not assessed (parse gap)",
                        )
                    )

            return novelty_results

        except Exception as e:
            if self._verbose:
                print(f"    Novelty detection failed: {e}")
            return [
                ProposalNovelty(
                    proposal_id=p.proposal_id,
                    novelty_score=0.3,
                    novelty_reason=f"Novelty detection failed: {e!s:.100}",
                )
                for p in proposals
            ]

    # ------------------------------------------------------------------
    # Panel deliberation
    # ------------------------------------------------------------------

    async def run_deliberation(
        self,
        panelist_names: list[str],
        panelist_roles: list[str],
        panelist_backstories: list[str],
        finalist_proposals: list[DukeProposal],
        rankings_summary: str,
        context: SelectionContext,
    ) -> SelectionDeliberation:
        """Run panel deliberation on finalist proposals.

        Uses a facilitator agent (default LLM) to synthesize all President
        perspectives and recommend a winner.
        """
        # Build finalist summaries with full text for deliberation
        finalist_texts: list[str] = []
        for p in finalist_proposals:
            text = _truncate_proposal(
                p.proposal_markdown, limit=DELIBERATION_TOKEN_LIMIT
            )
            finalist_texts.append(f"### {p.proposal_id} (Duke {p.duke_name})\n{text}")

        panelist_list = "\n".join(
            f"- {name} ({role})"
            for name, role in zip(panelist_names, panelist_roles, strict=False)
        )

        deliberation_prompt = f"""You are facilitating a panel deliberation among Executive Presidents
to select the winning Duke implementation proposal.

**PANEL MEMBERS:**
{panelist_list}

**RANKINGS SUMMARY:**
{rankings_summary}

**FINALIST PROPOSALS:**
{chr(10).join(finalist_texts)}

**YOUR TASK:**
1. Present arguments FOR and AGAINST each finalist
2. Synthesize the panel's collective assessment
3. Recommend a winner based on overall merit
4. Record each panelist's vote (their top choice proposal_id)
5. Note any dissenting opinions

**RESPOND IN JSON FORMAT:**
{{
    "finalist_proposal_ids": ["id1", "id2", ...],
    "recommended_winner_id": "the winning proposal_id",
    "recommendation_rationale": "Why this proposal was selected",
    "arguments_for": {{
        "proposal_id": ["argument1", "argument2"]
    }},
    "arguments_against": {{
        "proposal_id": ["concern1", "concern2"]
    }},
    "dissenting_opinions": ["opinion1"],
    "votes": {{
        "president_name": "voted_proposal_id"
    }}
}}
"""

        facilitator = Agent(
            role="Selection Panel Facilitator",
            goal="Synthesize panel deliberation and recommend winning proposal",
            backstory=(
                "Experienced facilitator skilled at synthesizing diverse "
                "executive perspectives into actionable decisions"
            ),
            llm=self._get_secretary_text_llm(),
            verbose=self._verbose,
            allow_delegation=False,
        )

        task = Task(
            description=deliberation_prompt,
            expected_output="JSON with recommendation, arguments, votes",
            agent=facilitator,
        )

        crew = Crew(agents=[facilitator], tasks=[task], verbose=self._verbose)

        last_error: Exception | None = None
        max_retries = 3

        for attempt in range(max_retries):
            try:
                result = await asyncio.to_thread(crew.kickoff)
                raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

                if not raw_output or raw_output.strip() in ("None", "null", ""):
                    raise ValueError("Empty response from LLM")

                try:
                    parsed = parse_json_response(raw_output, aggressive=True)
                except ValueError:
                    repaired = self._repair_json_with_secretary(
                        raw_output, _DELIBERATION_JSON_SHAPE
                    )
                    if repaired:
                        parsed = parse_json_response(repaired, aggressive=True)
                    else:
                        raise

                return SelectionDeliberation(
                    finalist_proposal_ids=parsed.get(
                        "finalist_proposal_ids",
                        [p.proposal_id for p in finalist_proposals],
                    ),
                    recommended_winner_id=parsed.get("recommended_winner_id", ""),
                    recommendation_rationale=parsed.get("recommendation_rationale", ""),
                    arguments_for=parsed.get("arguments_for", {}),
                    arguments_against=parsed.get("arguments_against", {}),
                    dissenting_opinions=parsed.get("dissenting_opinions", []),
                    votes=parsed.get("votes", {}),
                )

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1 and self._is_retryable(e):
                    if self._verbose:
                        print(f"    Deliberation retry {attempt + 1}: {e!s:.100}")
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                break

        # All retries failed - return minimal deliberation
        if self._verbose:
            print(f"    Deliberation failed: {last_error}")

        # Fall back to selecting top-ranked proposal
        finalist_ids = [p.proposal_id for p in finalist_proposals]
        return SelectionDeliberation(
            finalist_proposal_ids=finalist_ids,
            recommended_winner_id=finalist_ids[0] if finalist_ids else "",
            recommendation_rationale=(
                f"Deliberation failed after {max_retries} attempts. "
                f"Defaulting to top-ranked proposal. Error: {last_error}"
            ),
            votes={},
        )


# ------------------------------------------------------------------
# Factory function
# ------------------------------------------------------------------


def create_proposal_scorer(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    secretary_text_archon_id: str | None = None,
    secretary_json_archon_id: str | None = None,
) -> ProposalScorerProtocol:
    """Factory function to create a ProposalScorer instance.

    Args:
        profile_repository: Optional repository for per-President LLM configs
        verbose: Enable verbose LLM logging
        model: Override LLM model name
        provider: Override LLM provider
        base_url: Override LLM base URL
        secretary_text_archon_id: Archon ID for Secretary Text agent (utility tasks)
        secretary_json_archon_id: Archon ID for Secretary JSON agent (JSON repair)

    Returns:
        ProposalScorerProtocol implementation
    """
    return ProposalScorerCrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        model=model,
        provider=provider,
        base_url=base_url,
        secretary_text_archon_id=secretary_text_archon_id,
        secretary_json_archon_id=secretary_json_archon_id,
    )
