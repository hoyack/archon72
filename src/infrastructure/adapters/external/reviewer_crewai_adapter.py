"""CrewAI adapter for Reviewer agent operations.

Implements ReviewerAgentProtocol using CrewAI for LLM-powered motion review.
Each Archon reviews motions through their unique personality and expertise.

Constitutional Compliance:
- CT-11: All LLM calls logged, failures reported
- CT-12: All responses attributed to reviewing Archon

LLM Configuration:
- Each Archon uses their per-archon LLM binding from archon-llm-bindings.yaml
- Falls back to rank-based defaults, then global default
- Local models use Ollama via OLLAMA_HOST environment variable
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time

from crewai import LLM, Agent, Crew, Task
from structlog import get_logger

from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.reviewer_agent import (
    AmendmentSynthesis,
    AmendmentSynthesisError,
    ArchonReviewerContext,
    ConflictAnalysis,
    ConflictDetectionError,
    DeliberationError,
    MotionReviewContext,
    PanelDeliberationContext,
    PanelDeliberationResult,
    ReviewDecision,
    ReviewerAgentProtocol,
    ReviewError,
)
from src.domain.models.llm_config import LLMConfig

logger = get_logger(__name__)


def _create_llm_for_config(llm_config: LLMConfig) -> LLM:
    """Create a CrewAI LLM instance from LLMConfig.

    For local/Ollama, creates an LLM object with base_url.
    Priority for base_url:
      1. Per-archon base_url from LLMConfig (enables distributed inference)
      2. OLLAMA_HOST environment variable (global fallback)
      3. Default localhost:11434

    Args:
        llm_config: The LLM configuration

    Returns:
        CrewAI LLM instance
    """
    # Map provider to CrewAI format
    provider_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "google": "google",
        "local": "ollama",
    }
    provider = provider_map.get(llm_config.provider, llm_config.provider)
    model_string = f"{provider}/{llm_config.model}"

    # For local/Ollama, include base_url
    if llm_config.provider == "local":
        if llm_config.base_url:
            ollama_host = llm_config.base_url
        else:
            ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        return LLM(
            model=model_string,
            base_url=ollama_host,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
        )

    # For cloud providers
    return LLM(
        model=model_string,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
    )


def _escape_control_chars_in_strings(text: str) -> str:
    """Escape unescaped control characters inside JSON string values.

    LLMs sometimes generate JSON with raw newlines/tabs inside strings.
    This finds string values and escapes control characters properly.
    """
    result = []
    in_string = False
    escape_next = False
    i = 0

    while i < len(text):
        char = text[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == "\\" and in_string:
            escape_next = True
            result.append(char)
            i += 1
            continue

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        # Inside a string, escape control characters
        if in_string and ord(char) < 32:
            if char == "\n":
                result.append("\\n")
            elif char == "\r":
                result.append("\\r")
            elif char == "\t":
                result.append("\\t")
            else:
                # Other control chars: use unicode escape
                result.append(f"\\u{ord(char):04x}")
        else:
            result.append(char)

        i += 1

    return "".join(result)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling common formatting issues."""
    cleaned = text.strip()

    # Remove markdown code blocks
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1])
        else:
            cleaned = "\n".join(lines[1:])

    # Fix trailing commas
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

    # Try to find JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]

    # Escape control characters inside string values (common LLM issue)
    cleaned = _escape_control_chars_in_strings(cleaned)

    return json.loads(cleaned)


class ReviewerCrewAIAdapter(ReviewerAgentProtocol):
    """CrewAI implementation of ReviewerAgentProtocol.

    Uses CrewAI to orchestrate Archon agents for motion review,
    conflict detection, and panel deliberation.

    Each Archon uses their per-archon LLM binding from archon-llm-bindings.yaml,
    with rank-based defaults and global fallback for local Ollama models.
    """

    def __init__(
        self,
        profile_repository: ArchonProfileRepository | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the adapter.

        Args:
            profile_repository: Repository for loading Archon profiles with LLM configs.
                               If provided, each Archon uses their specific LLM binding.
                               If None, falls back to default local model.
            verbose: Enable verbose LLM logging
        """
        self.verbose = verbose
        self._profile_repository = profile_repository

        # Default LLM config for utility agents (conflict analysis, synthesis)
        # These are not character-specific, so use a default local model
        # Uses qwen3:latest which is consistent with archon-llm-bindings.yaml defaults
        self._default_llm = LLM(
            model="ollama/qwen3:latest",
            base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            temperature=0.3,
            max_tokens=2048,
        )

        if profile_repository:
            logger.info(
                "reviewer_adapter_initialized",
                using_profiles=True,
                verbose=verbose,
            )
        else:
            logger.warning(
                "reviewer_adapter_no_profiles",
                message="No profile repository provided. All Archons will use default LLM.",
            )

    def _get_archon_llm(self, archon_name: str) -> LLM:
        """Get the appropriate LLM for an Archon.

        Looks up the Archon's profile to get their per-archon LLM binding.
        Falls back to default if profile not found.

        Args:
            archon_name: Name of the Archon

        Returns:
            CrewAI LLM instance configured for this Archon
        """
        if self._profile_repository:
            try:
                profile = self._profile_repository.get_by_name(archon_name)
                if profile:
                    llm = _create_llm_for_config(profile.llm_config)
                    logger.debug(
                        "archon_llm_loaded",
                        archon=archon_name,
                        provider=profile.llm_config.provider,
                        model=profile.llm_config.model,
                    )
                    return llm
            except Exception as e:
                logger.warning(
                    "archon_profile_lookup_failed",
                    archon=archon_name,
                    error=str(e),
                )

        # Fallback to default
        logger.debug(
            "archon_using_default_llm",
            archon=archon_name,
        )
        return self._default_llm

    def _create_archon_agent(self, archon: ArchonReviewerContext) -> Agent:
        """Create a CrewAI agent representing an Archon.

        Uses the Archon's per-archon LLM binding from their profile.

        Args:
            archon: The Archon's context

        Returns:
            CrewAI Agent configured with Archon personality and LLM
        """
        llm = self._get_archon_llm(archon.archon_name)

        return Agent(
            role=archon.archon_role,
            goal=(
                "Review Motion Seeds (mega-motions) and provide considered judgment "
                f"as {archon.archon_name}"
            ),
            backstory=archon.archon_backstory,
            llm=llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    async def review_motion(
        self,
        archon: ArchonReviewerContext,
        motion: MotionReviewContext,
    ) -> ReviewDecision:
        """Have an Archon review a mega-motion."""
        start_time = time.time()

        logger.info(
            "review_motion_start",
            archon=archon.archon_name,
            motion_id=motion.mega_motion_id,
        )

        agent = self._create_archon_agent(archon)

        conflict_context = ""
        if motion.conflict_flag:
            conflict_context = f"""
**CONFLICT ALERT**: You have a flagged conflict with this motion:
{motion.conflict_flag}

Consider this carefully in your review. You may still endorse if you've changed your position,
but explain your reasoning.
"""

        review_prompt = f"""You are {archon.archon_name}, an Archon of the Conclave.

Review the following mega-motion and provide your stance.

**MOTION TO REVIEW:**
Title: {motion.mega_motion_title}
Theme: {motion.theme}
Supporters: {motion.supporting_archon_count} Archons ({", ".join(motion.supporting_archons[:5])}...)
Source Motion Seeds (pre-admission inputs): {motion.source_motion_count}

**MOTION TEXT:**
{motion.mega_motion_text[:3000]}

{conflict_context}

**YOUR TASK:**
Analyze this motion through the lens of your expertise and values. Consider:
1. Does this align with your principles and domain expertise?
2. Is the motion well-formed and actionable?
3. Are there gaps, risks, or concerns?
4. Would you endorse, oppose, propose amendments, or abstain?

**RESPOND IN JSON FORMAT:**
{{
    "stance": "endorse" | "oppose" | "amend" | "abstain",
    "reasoning": "Your detailed reasoning (2-3 paragraphs)",
    "confidence": 0.0-1.0,
    "opposition_concerns": ["concern1", "concern2"] (if opposing),
    "amendment_type": "minor_wording" | "major_revision" | "add_clause" | "remove_clause" (if amending),
    "amendment_text": "Your proposed amendment text" (if amending),
    "amendment_rationale": "Why this amendment improves the motion" (if amending)
}}
"""

        task = Task(
            description=review_prompt,
            expected_output="JSON with stance, reasoning, and optional amendment",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = _parse_json_response(raw_output)

            decision = ReviewDecision(
                stance=parsed.get("stance", "abstain"),
                reasoning=parsed.get("reasoning", ""),
                confidence=float(parsed.get("confidence", 0.5)),
                opposition_concerns=parsed.get("opposition_concerns", []),
                amendment_type=parsed.get("amendment_type"),
                amendment_text=parsed.get("amendment_text"),
                amendment_rationale=parsed.get("amendment_rationale"),
                review_duration_ms=int((time.time() - start_time) * 1000),
            )

            logger.info(
                "review_motion_complete",
                archon=archon.archon_name,
                motion_id=motion.mega_motion_id,
                stance=decision.stance,
                duration_ms=decision.review_duration_ms,
            )

            return decision

        except json.JSONDecodeError as e:
            logger.error(
                "review_parse_failed",
                archon=archon.archon_name,
                motion_id=motion.mega_motion_id,
                error=str(e),
            )
            # Return abstain on parse failure
            return ReviewDecision(
                stance="abstain",
                reasoning=f"Parse error: {str(e)}. Raw response could not be parsed.",
                confidence=0.0,
                review_duration_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error(
                "review_motion_failed",
                archon=archon.archon_name,
                motion_id=motion.mega_motion_id,
                error=str(e),
            )
            raise ReviewError(f"Review failed for {archon.archon_name}: {e}") from e

    async def detect_conflict(
        self,
        archon: ArchonReviewerContext,
        motion: MotionReviewContext,
        archon_prior_statements: list[str],
    ) -> ConflictAnalysis:
        """Detect conflicts between an Archon's positions and a motion."""
        logger.info(
            "conflict_detection_start",
            archon=archon.archon_name,
            motion_id=motion.mega_motion_id,
            prior_statements=len(archon_prior_statements),
        )

        if not archon_prior_statements:
            return ConflictAnalysis(
                has_conflict=False,
                conflict_severity="none",
                reconciliation_possible=True,
            )

        agent = Agent(
            role="Conflict Analyst",
            goal="Identify conflicts between positions with nuance and precision",
            backstory="Expert in analyzing policy positions and detecting contradictions",
            llm=self._llm,
            verbose=self.verbose,
        )

        prior_text = "\n".join(f"- {s}" for s in archon_prior_statements[:10])

        conflict_prompt = f"""Analyze whether there is a conflict between an Archon's prior positions
and a proposed motion.

**ARCHON:** {archon.archon_name}
**DOMAIN:** {archon.domain or "General"}

**PRIOR POSITIONS/STATEMENTS:**
{prior_text}

**PROPOSED MOTION:**
Title: {motion.mega_motion_title}
Text: {motion.mega_motion_text[:2000]}

**ANALYZE:**
1. Do any prior positions contradict the motion's provisions?
2. Are there subtle tensions even if no direct contradiction?
3. Could the Archon reasonably have evolved their position?
4. What would reconciliation require?

**RESPOND IN JSON:**
{{
    "has_conflict": true | false,
    "conflict_severity": "none" | "minor" | "moderate" | "major",
    "conflict_description": "Description of the conflict (if any)",
    "archon_position": "The Archon's prior position that conflicts",
    "motion_position": "The motion's position that conflicts",
    "reconciliation_possible": true | false,
    "suggested_resolution": "How this could be resolved"
}}
"""

        task = Task(
            description=conflict_prompt,
            expected_output="JSON with conflict analysis",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = _parse_json_response(raw_output)

            analysis = ConflictAnalysis(
                has_conflict=parsed.get("has_conflict", False),
                conflict_severity=parsed.get("conflict_severity", "none"),
                conflict_description=parsed.get("conflict_description"),
                archon_position=parsed.get("archon_position"),
                motion_position=parsed.get("motion_position"),
                reconciliation_possible=parsed.get("reconciliation_possible", True),
                suggested_resolution=parsed.get("suggested_resolution"),
            )

            logger.info(
                "conflict_detection_complete",
                archon=archon.archon_name,
                has_conflict=analysis.has_conflict,
                severity=analysis.conflict_severity,
            )

            return analysis

        except Exception as e:
            logger.error("conflict_detection_failed", error=str(e))
            raise ConflictDetectionError(f"Conflict detection failed: {e}") from e

    async def run_panel_deliberation(
        self,
        context: PanelDeliberationContext,
    ) -> PanelDeliberationResult:
        """Run a panel deliberation for a contested motion."""
        start_time = time.time()

        logger.info(
            "panel_deliberation_start",
            panel_id=context.panel_id,
            motion_id=context.mega_motion_id,
            supporters=len(context.supporters),
            critics=len(context.critics),
            neutrals=len(context.neutrals),
        )

        # Create agents for each panelist
        supporter_agents = [self._create_archon_agent(s) for s in context.supporters]
        critic_agents = [self._create_archon_agent(c) for c in context.critics]
        # Neutrals participate in synthesis but don't give individual arguments
        _neutral_agents = [self._create_archon_agent(n) for n in context.neutrals]

        # Phase 1: Supporter arguments
        supporter_args = []
        for agent, archon in zip(supporter_agents, context.supporters, strict=False):
            task = Task(
                description=f"""You are {archon.archon_name}, a SUPPORTER of this motion.

**MOTION:** {context.mega_motion_title}
{context.mega_motion_text[:2000]}

Present your strongest argument FOR this motion in 2-3 paragraphs.
Focus on benefits, alignment with Conclave principles, and why concerns are addressable.

Respond with your argument text only (no JSON).
""",
                expected_output="Argument text for the motion",
                agent=agent,
            )
            crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)
            result = await asyncio.to_thread(crew.kickoff)
            supporter_args.append(
                str(result.raw) if hasattr(result, "raw") else str(result)
            )

        # Phase 2: Critic arguments
        critic_args = []
        for agent, archon in zip(critic_agents, context.critics, strict=False):
            task = Task(
                description=f"""You are {archon.archon_name}, a CRITIC of this motion.

**MOTION:** {context.mega_motion_title}
{context.mega_motion_text[:2000]}

**SUPPORTER ARGUMENTS:**
{chr(10).join(f"- {a[:500]}..." for a in supporter_args)}

Present your strongest argument AGAINST this motion or for significant amendments.
Address the supporter arguments where relevant.

Respond with your argument text only (no JSON).
""",
                expected_output="Argument text against the motion",
                agent=agent,
            )
            crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)
            result = await asyncio.to_thread(crew.kickoff)
            critic_args.append(
                str(result.raw) if hasattr(result, "raw") else str(result)
            )

        # Phase 3: Neutral synthesis and recommendation
        facilitator = Agent(
            role="Panel Facilitator",
            goal="Synthesize discussion and guide panel to recommendation",
            backstory="Experienced facilitator skilled at finding consensus and summarizing debates",
            llm=self._llm,
            verbose=self.verbose,
        )

        all_panelists = (
            [s.archon_name for s in context.supporters]
            + [c.archon_name for c in context.critics]
            + [n.archon_name for n in context.neutrals]
        )

        synthesis_prompt = f"""You are facilitating a panel deliberation on a contested motion.

**MOTION:** {context.mega_motion_title}
{context.mega_motion_text[:1500]}

**SUPPORTER ARGUMENTS:**
{chr(10).join(f"{i + 1}. {a[:400]}..." for i, a in enumerate(supporter_args))}

**CRITIC ARGUMENTS:**
{chr(10).join(f"{i + 1}. {a[:400]}..." for i, a in enumerate(critic_args))}

**PROPOSED AMENDMENTS:**
{chr(10).join(context.proposed_amendments) if context.proposed_amendments else "None proposed"}

**YOUR TASK:**
1. Synthesize the key points of agreement and disagreement
2. Determine if amendment could satisfy both sides
3. Provide a panel recommendation

**PANELISTS:** {", ".join(all_panelists)}

**RESPOND IN JSON:**
{{
    "recommendation": "pass" | "fail" | "amend" | "defer",
    "recommendation_rationale": "Why this recommendation",
    "votes": {{"archon_name": "pass|fail|amend|defer", ...}},
    "revised_motion_text": "If amend, the revised text" or null,
    "revision_summary": "What was changed and why" or null,
    "key_points_discussed": ["point1", "point2", ...],
    "consensus_areas": ["area1", "area2", ...],
    "unresolved_concerns": ["concern1", "concern2", ...],
    "dissenting_opinions": [{{"archon_name": "Name", "opinion": "Their dissent"}}]
}}
"""

        task = Task(
            description=synthesis_prompt,
            expected_output="JSON with panel recommendation",
            agent=facilitator,
        )

        crew = Crew(agents=[facilitator], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = _parse_json_response(raw_output)

            deliberation_result = PanelDeliberationResult(
                panel_id=context.panel_id,
                mega_motion_id=context.mega_motion_id,
                recommendation=parsed.get("recommendation", "defer"),
                recommendation_rationale=parsed.get("recommendation_rationale", ""),
                votes=parsed.get("votes", {}),
                revised_motion_text=parsed.get("revised_motion_text"),
                revision_summary=parsed.get("revision_summary"),
                key_points_discussed=parsed.get("key_points_discussed", []),
                consensus_areas=parsed.get("consensus_areas", []),
                unresolved_concerns=parsed.get("unresolved_concerns", []),
                dissenting_opinions=parsed.get("dissenting_opinions", []),
                deliberation_duration_ms=int((time.time() - start_time) * 1000),
            )

            logger.info(
                "panel_deliberation_complete",
                panel_id=context.panel_id,
                recommendation=deliberation_result.recommendation,
                duration_ms=deliberation_result.deliberation_duration_ms,
            )

            return deliberation_result

        except Exception as e:
            logger.error("panel_deliberation_failed", error=str(e))
            raise DeliberationError(f"Panel deliberation failed: {e}") from e

    async def synthesize_amendments(
        self,
        motion_text: str,
        proposed_amendments: list[tuple[str, str]],
    ) -> AmendmentSynthesis:
        """Synthesize multiple amendment proposals into a coherent revision."""
        logger.info(
            "amendment_synthesis_start",
            amendment_count=len(proposed_amendments),
        )

        if not proposed_amendments:
            return AmendmentSynthesis(
                original_motion_text=motion_text,
                synthesized_amendment=motion_text,
                incorporated_proposals=[],
                excluded_proposals=[],
                synthesis_rationale="No amendments to synthesize",
                archons_satisfied=[],
            )

        agent = Agent(
            role="Amendment Synthesizer",
            goal="Combine compatible amendments into coherent revised text",
            backstory="Expert legislative drafter skilled at reconciling different proposals",
            llm=self._llm,
            verbose=self.verbose,
        )

        amendments_text = "\n\n".join(
            f"**{archon}:**\n{text}" for archon, text in proposed_amendments
        )

        synthesis_prompt = f"""You are synthesizing multiple amendment proposals into a single revised motion.

**ORIGINAL MOTION:**
{motion_text[:2000]}

**PROPOSED AMENDMENTS:**
{amendments_text}

**YOUR TASK:**
1. Identify which amendments are compatible and can be incorporated
2. Identify which amendments contradict each other
3. Create a synthesized revision that incorporates compatible changes
4. Explain what was included and excluded

**RESPOND IN JSON:**
{{
    "synthesized_amendment": "The full revised motion text",
    "incorporated_proposals": ["Archon names whose amendments were included"],
    "excluded_proposals": ["Archon names whose amendments couldn't be included"],
    "synthesis_rationale": "Explanation of synthesis decisions",
    "archons_satisfied": ["Archon names whose concerns are addressed"]
}}
"""

        task = Task(
            description=synthesis_prompt,
            expected_output="JSON with synthesized amendment",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = _parse_json_response(raw_output)

            synthesis = AmendmentSynthesis(
                original_motion_text=motion_text,
                synthesized_amendment=parsed.get("synthesized_amendment", motion_text),
                incorporated_proposals=parsed.get("incorporated_proposals", []),
                excluded_proposals=parsed.get("excluded_proposals", []),
                synthesis_rationale=parsed.get("synthesis_rationale", ""),
                archons_satisfied=parsed.get("archons_satisfied", []),
            )

            logger.info(
                "amendment_synthesis_complete",
                incorporated=len(synthesis.incorporated_proposals),
                excluded=len(synthesis.excluded_proposals),
            )

            return synthesis

        except Exception as e:
            logger.error("amendment_synthesis_failed", error=str(e))
            raise AmendmentSynthesisError(f"Amendment synthesis failed: {e}") from e

    async def batch_review_motions(
        self,
        archon: ArchonReviewerContext,
        motions: list[MotionReviewContext],
    ) -> list[ReviewDecision]:
        """Have an Archon review multiple motions."""
        logger.info(
            "batch_review_start",
            archon=archon.archon_name,
            motion_count=len(motions),
        )

        decisions = []
        for motion in motions:
            decision = await self.review_motion(archon, motion)
            decisions.append(decision)

        logger.info(
            "batch_review_complete",
            archon=archon.archon_name,
            reviewed=len(decisions),
        )

        return decisions


def create_reviewer_agent(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
) -> ReviewerAgentProtocol:
    """Factory function to create a ReviewerAgent instance.

    Args:
        profile_repository: Optional repository for loading per-Archon LLM configs.
                           If provided, each Archon uses their specific LLM binding.
                           If None, falls back to default local Ollama model.
        verbose: Enable verbose LLM logging

    Returns:
        ReviewerAgentProtocol implementation
    """
    return ReviewerCrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
    )
