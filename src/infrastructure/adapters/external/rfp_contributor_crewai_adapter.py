"""CrewAI adapter for RFP contribution generation.

Each President contributes requirements and constraints from their portfolio lens.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
from typing import TYPE_CHECKING
from uuid import UUID

from crewai import Agent, Crew, Task

from src.application.ports.rfp_generation import RFPContributorProtocol
from src.domain.models.llm_config import LLMConfig
from src.domain.models.rfp import (
    Constraint,
    ConstraintType,
    ContributionStatus,
    Deliverable,
    EvaluationCriterion,
    FunctionalRequirement,
    NonFunctionalRequirement,
    PortfolioContribution,
    RequirementCategory,
    RequirementPriority,
    ResourceType,
)
from src.infrastructure.adapters.external.crewai_llm_factory import create_crewai_llm

if TYPE_CHECKING:
    from crewai import LLM

    from src.infrastructure.adapters.config.archon_profile_adapter import (
        ArchonProfileRepository,
    )


def parse_json_response(raw: str, aggressive: bool = True) -> dict | list:
    """Parse JSON from LLM response, handling common issues."""
    text = raw.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract JSON from markdown code blocks
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
        r"\{[\s\S]*\}",
        r"\[[\s\S]*\]",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                candidate = match.group(1) if "```" in pattern else match.group(0)
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            return item
                    raise ValueError("Parsed JSON is a list, no object found")
                return parsed
            except (json.JSONDecodeError, IndexError):
                continue

    if aggressive:
        # Try to find any JSON-like structure
        start_brace = text.find("{")
        start_bracket = text.find("[")

        if start_brace >= 0:
            depth = 0
            for i, c in enumerate(text[start_brace:], start_brace):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            parsed = json.loads(text[start_brace : i + 1])
                            if isinstance(parsed, list):
                                for item in parsed:
                                    if isinstance(item, dict):
                                        return item
                                raise ValueError(
                                    "Parsed JSON is a list, no object found"
                                )
                            return parsed
                        except json.JSONDecodeError:
                            break

        if start_bracket >= 0:
            depth = 0
            for i, c in enumerate(text[start_bracket:], start_bracket):
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        try:
                            parsed = json.loads(text[start_bracket : i + 1])
                            if isinstance(parsed, list):
                                for item in parsed:
                                    if isinstance(item, dict):
                                        return item
                                raise ValueError(
                                    "Parsed JSON is a list, no object found"
                                )
                            return parsed
                        except json.JSONDecodeError:
                            break

    raise ValueError(f"Could not parse JSON from response: {text[:500]}")


class RFPContributorCrewAIAdapter(RFPContributorProtocol):
    """CrewAI adapter for generating RFP contributions from Presidents."""

    # Portfolio abbreviations for unique ID namespacing (avoids "PORT" collision)
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
        # Managing Director variants
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

    # Context purity constraint - CRITICAL for preventing domain hallucination
    CONTEXT_PURITY_CONSTRAINT = """
CONTEXT PURITY CONSTRAINT (MANDATORY):
- Only reference governance artifacts and abstract system concepts.
- Do NOT introduce real-world domains or external frameworks unless named in the motion.
- Do NOT add domain-specific terminology not present in the motion.
"""

    BRANCH_BOUNDARY_CONSTRAINT = """
BRANCH-BOUNDARY CONSTRAINT (MANDATORY):
- Do NOT assign work/approvals to other branches or portfolios.
- Independence requirements only; do not name portfolios/branches.
- Do NOT introduce new governance structures unless present in the motion.
"""

    EXECUTIVE_NON_OPERATIONAL_CONSTRAINT = """
EXECUTIVE NON-OPERATIONAL CONSTRAINT (MANDATORY):
- Do NOT specify mechanisms, metrics, or operators.
- Only state capabilities, constraints, and recognition properties.
"""

    # Portfolio focus areas (abstract, not domain-specific)
    PORTFOLIO_FOCUS = {
        "TECH": "technical feasibility, integration patterns, system boundaries",
        "CONF": "adversarial resilience, failure modes, conflict between requirements",
        "KNOW": "documentation, knowledge capture, handoff clarity",
        "RSRC": "capacity constraints, resource availability, discovery needs",
        "INFR": "operational requirements, deployment patterns, observability",
        "ALCH": "migration paths, transformation sequences, backward compatibility",
        "BEHV": "behavioral expectations, feedback loops, pattern recognition",
        "WELL": "reliability, recovery procedures, graceful degradation",
        "ASTR": "planning horizons, uncertainty handling, scenario coverage",
        "IDEN": "identity verification, perception consistency, access patterns",
        "ETHC": "ethical constraints, audit requirements, accountability chains",
    }

    ASTR_SPECIAL_LIMITS = """
ASTR SPECIAL LIMITS (MANDATORY):
- You may discuss uncertainty and forecasting only as metadata attached to actions.
- You may NOT introduce new clocks, divination cycles, matrices, consensus systems, or role schemas.
- You may NOT require alignment to celestial events, divination schedules, or scenario scores as gating conditions.
    - Allowed: "If an ASTR output is authority-bearing, it must include explicit attribution and a declared uncertainty note."
    - Forbidden: "must align to divination cycles", "astrological role matrix governs legitimacy", "scenario coverage score required".
"""

    def _compact_motion_text(self, motion_text: str, max_chars: int = 1200) -> str:
        """Return a compact motion snippet for retry prompts."""
        if not motion_text:
            return ""

        sections: list[str] = []
        patterns = [
            r"##\s*Definitions[\s\S]*?(?=^##\s|\Z)",
            r"##\s*Binding Requirement[\s\S]*?(?=^##\s|\Z)",
            r"##\s*Success Criteria[\s\S]*?(?=^##\s|\Z)",
        ]
        for pattern in patterns:
            match = re.search(pattern, motion_text, re.MULTILINE)
            if match:
                sections.append(match.group(0).strip())

        compact = "\n\n".join(sections) if sections else motion_text.strip()

        if len(compact) > max_chars:
            compact = compact[:max_chars].rstrip()
        return compact

    def _is_empty_contribution(self, contribution: PortfolioContribution) -> bool:
        """Return True if the contribution has no substantive content."""
        return not any(
            [
                contribution.functional_requirements,
                contribution.non_functional_requirements,
                contribution.constraints,
                contribution.deliverables,
                contribution.evaluation_criteria,
                contribution.risks_identified,
                contribution.assumptions,
            ]
        )

    def __init__(
        self,
        profile_repository: ArchonProfileRepository | None = None,
        verbose: bool = False,
        llm_config: LLMConfig | None = None,
        model: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the RFP contributor adapter.

        Args:
            profile_repository: Repository for loading Archon profiles with LLM configs
            verbose: Enable verbose logging
            llm_config: Default LLM configuration
            model: Override model name
            provider: Override LLM provider (e.g., 'ollama', 'openai', 'anthropic')
            base_url: Override base URL for API
        """
        self._profile_repository = profile_repository
        self._verbose = verbose
        self._default_llm_config = llm_config
        self._model_override = model
        self._provider_override = provider
        self._base_url_override = base_url
        self._llm_cache: dict[str, tuple[LLM | str, LLMConfig]] = {}
        self._secretary_llm: tuple[LLM | str, LLMConfig] | None = None

    def _get_president_llm(self, president_name: str) -> tuple[LLM | str, LLMConfig]:
        """Get the appropriate LLM for a President (cached)."""
        if president_name in self._llm_cache:
            return self._llm_cache[president_name]

        llm_config = self._default_llm_config

        if self._profile_repository:
            profile = self._profile_repository.get_by_name(president_name)
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

        # Use the factory to properly normalize provider and handle Ollama Cloud
        llm = create_crewai_llm(llm_config)

        self._llm_cache[president_name] = (llm, llm_config)
        return llm, llm_config

    def _get_secretary_llm(self) -> tuple[LLM | str, LLMConfig] | None:
        """Get LLM for Secretary JSON parsing (cached)."""
        if self._secretary_llm:
            return self._secretary_llm

        secretary_id = os.getenv("SECRETARY_JSON_ARCHON_ID", "").strip()
        if not secretary_id:
            return None

        llm_config = None
        if self._profile_repository:
            try:
                profile = self._profile_repository.get_by_id(UUID(secretary_id))
                if profile and profile.llm_config:
                    llm_config = profile.llm_config
            except ValueError:
                llm_config = None

        if not llm_config:
            llm_config = LLMConfig(
                provider="ollama",
                model="qwen3:latest",
                temperature=0.0,
                max_tokens=4096,
            )

        llm = create_crewai_llm(llm_config)
        self._secretary_llm = (llm, llm_config)
        return self._secretary_llm

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
        base = float(os.getenv("RFP_CONTRIBUTION_BACKOFF_BASE_SECONDS", "1.0"))
        maximum = float(os.getenv("RFP_CONTRIBUTION_BACKOFF_MAX_SECONDS", "8.0"))
        delay = min(maximum, base * (2 ** (attempt - 1)))
        jitter = delay * random.uniform(0.1, 0.25)
        return delay + jitter

    def _repair_json_with_secretary(
        self,
        raw_output: str,
        portfolio_id: str,
        president_name: str,
    ) -> str | None:
        """Use Secretary JSON Archon to repair malformed JSON output."""
        secretary = self._get_secretary_llm()
        if not secretary:
            return None
        llm, _ = secretary

        repair_prompt = f"""OUTPUT ONLY VALID JSON.
You are a JSON repair tool. You must ONLY reformat the input into a valid JSON object.
Do NOT invent new content. Do NOT add requirements not present in the input.
If a field is missing, use empty arrays or empty strings.

EXPECTED JSON SHAPE:
{{
  "contribution_summary": "string",
  "functional_requirements": [{{"req_id":"string","description":"string","priority":"must|should|could|wont","acceptance_criteria":["string"],"rationale":"string","independence_requirements":["string"]}}],
  "non_functional_requirements": [{{"req_id":"string","category":"performance|security|reliability|scalability|usability|compliance|maintainability|interoperability","description":"string","target_metric":"string","threshold":"string","priority":"must|should|could|wont"}}],
  "constraints": [{{"constraint_id":"string","constraint_type":"technical|resource|organizational|temporal|regulatory","description":"string","rationale":"string","negotiable":true}}],
  "deliverables": [{{"deliverable_id":"string","name":"string","description":"string","acceptance_criteria":["string"]}}],
  "evaluation_criteria": [{{"criterion_id":"string","name":"string","description":"string","priority_band":"high|medium|low","scoring_method":"1-5 scale"}}],
  "risks_identified": ["string"],
  "assumptions": ["string"],
  "deliberation_notes": "string"
}}

INPUT FROM PRESIDENT {president_name} ({portfolio_id}):
{raw_output}

If the input contains multiple JSON objects, select the first complete object and discard the rest.
Output ONLY ONE JSON object. Do not return a list.
"""

        agent = Agent(
            role="Secretary JSON Parser",
            goal="Repair malformed JSON without altering meaning",
            backstory="You are a JSON repair tool. You only reformat.",
            llm=llm,
            verbose=self._verbose,
        )

        task = Task(
            description=repair_prompt,
            expected_output="A single valid JSON object matching the required shape",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=self._verbose,
        )

        result = crew.kickoff()
        repaired = str(result.raw) if hasattr(result, "raw") else str(result)
        return repaired.strip()

    async def generate_contribution(
        self,
        mandate_id: str,
        motion_title: str,
        motion_text: str,
        portfolio_id: str,
        president_name: str,
        portfolio_domain: str,
        president_id: str = "",
        existing_contributions: list[PortfolioContribution] | None = None,
    ) -> PortfolioContribution:
        """Generate a portfolio contribution to the RFP."""
        llm, llm_config = self._get_president_llm(president_name)

        use_compact_prompt = False

        # Get unique portfolio abbreviation for ID namespacing
        abbrev = self.PORTFOLIO_ABBREV.get(portfolio_id, portfolio_id[-4:].upper())
        focus = self.PORTFOLIO_FOCUS.get(
            abbrev, "requirements relevant to your portfolio"
        )

        # Build context from existing contributions
        existing_context = ""
        if existing_contributions:
            existing_context = "\n\nOther Presidents have already contributed:\n"
            for contrib in existing_contributions:
                existing_context += f"- {contrib.president_name}: {len(contrib.functional_requirements)} functional, "
                existing_context += (
                    f"{len(contrib.non_functional_requirements)} non-functional, "
                )
                existing_context += f"{len(contrib.constraints)} constraints\n"

        special_limits = self.ASTR_SPECIAL_LIMITS if abbrev == "ASTR" else ""

        agent = Agent(
            role=f"{president_name} - {portfolio_domain} President",
            goal=f"Contribute requirements and constraints from {portfolio_id} perspective within governance system context only",
            backstory=f"You are {president_name}, President responsible for {portfolio_domain} "
            f"within the Aegis Network governance system. You analyze mandates through your "
            f"portfolio lens but ONLY within the context of this governance system - you do not "
            f"invent external compliance frameworks, real-world domains, or fictional urgency.",
            llm=llm,
            verbose=self._verbose,
        )

        max_attempts = int(os.getenv("RFP_CONTRIBUTION_RETRIES", "3"))
        attempts = 0
        last_raw = ""
        while attempts < max_attempts:
            attempts += 1
            base_header = "OUTPUT ONLY VALID JSON."
            retry_header = (
                "OUTPUT ONLY VALID JSON.\nRETRY MODE: Your last response was empty/invalid or violated constraints. "
                "Provide a minimal, non-empty contribution using capability language only."
            )
            prompt_header = retry_header if use_compact_prompt else base_header

            mandate_text = (
                self._compact_motion_text(motion_text)
                if use_compact_prompt
                else motion_text
            )

            contribution_prompt = f"""{prompt_header}
You are {president_name}, President of {portfolio_id}.

MANDATE:
Title: {motion_title}
Text: {mandate_text}

{self.CONTEXT_PURITY_CONSTRAINT}
{self.BRANCH_BOUNDARY_CONSTRAINT}
{self.EXECUTIVE_NON_OPERATIONAL_CONSTRAINT}
{special_limits}

PORTFOLIO LENS: {focus}
{existing_context}

Rules:
- Define WHAT is needed, not HOW to implement it
- Use "The implementation shall enable ..." for requirement/constraint descriptions
- If no action is required, set contribution_summary to "NO_ACTION: <reason>" and leave all arrays empty
- Otherwise include at least one requirement or constraint (aim for 2-4 if applicable)
- Do NOT leave all arrays empty unless NO_ACTION (empty contributions are rejected and retried)
- Use empty arrays/empty strings for fields you are not populating (never use null)
- If independence is required, record it only in "independence_requirements" without naming portfolios or branches

Use ID prefix "{abbrev}" for all IDs.

JSON SHAPE (exact keys, arrays may be empty):
{{
  "contribution_summary": "string",
  "functional_requirements": [{{"req_id":"FR-{abbrev}-001","description":"string","priority":"must|should|could|wont","acceptance_criteria":["string"],"rationale":"string","independence_requirements":["string"]}}],
  "non_functional_requirements": [{{"req_id":"NFR-{abbrev}-001","category":"performance|security|reliability|scalability|usability|compliance|maintainability|interoperability","description":"string","target_metric":"string","threshold":"string","priority":"must|should|could|wont"}}],
  "constraints": [{{"constraint_id":"C-{abbrev}-001","constraint_type":"technical|resource|organizational|temporal|regulatory","description":"string","rationale":"string","negotiable":true}}],
  "deliverables": [{{"deliverable_id":"D-{abbrev}-001","name":"string","description":"string","acceptance_criteria":["string"]}}],
  "evaluation_criteria": [{{"criterion_id":"EC-{abbrev}-001","name":"string","description":"string","priority_band":"high|medium|low","scoring_method":"1-5 scale"}}],
  "risks_identified": ["string"],
  "assumptions": ["string"],
  "deliberation_notes": "string"
}}

CRITICAL: Output ONLY ONE JSON OBJECT. Do not output a list. No markdown. No extra text."""

            task = Task(
                description=contribution_prompt,
                expected_output="JSON object with requirements, constraints, deliverables, and evaluation criteria",
                agent=agent,
            )

            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=self._verbose,
            )

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
                    cooldown = float(
                        os.getenv("RFP_CONTRIBUTION_EMPTY_COOLDOWN_SECONDS", "0")
                    )
                    if cooldown > 0:
                        await asyncio.sleep(cooldown)
                    await asyncio.sleep(self._backoff_delay(attempts))
                    continue
                break

            try:
                contribution = self._parse_contribution(
                    raw_output=raw_output,
                    portfolio_id=portfolio_id,
                    president_name=president_name,
                    motion_text=motion_text,
                    president_id=president_id,
                    llm_config=llm_config,
                    raise_on_error=True,
                )
                if (
                    self._is_empty_contribution(contribution)
                    and not contribution.is_no_action()
                ):
                    if attempts < max_attempts:
                        use_compact_prompt = True
                        await asyncio.sleep(self._backoff_delay(attempts))
                        continue
                return contribution
            except ValueError:
                repaired = self._repair_json_with_secretary(
                    raw_output=raw_output,
                    portfolio_id=portfolio_id,
                    president_name=president_name,
                )
                if repaired:
                    try:
                        contribution = self._parse_contribution(
                            raw_output=repaired,
                            portfolio_id=portfolio_id,
                            president_name=president_name,
                            motion_text=motion_text,
                            president_id=president_id,
                            llm_config=llm_config,
                            raise_on_error=True,
                        )
                        if (
                            self._is_empty_contribution(contribution)
                            and not contribution.is_no_action()
                        ):
                            if attempts < max_attempts:
                                use_compact_prompt = True
                                await asyncio.sleep(self._backoff_delay(attempts))
                                continue
                        return contribution
                    except ValueError:
                        use_compact_prompt = True
                        if attempts < max_attempts:
                            await asyncio.sleep(self._backoff_delay(attempts))
                            continue
                if attempts < max_attempts:
                    await asyncio.sleep(self._backoff_delay(attempts))
                    continue
                break

        return self._parse_contribution(
            raw_output=last_raw,
            portfolio_id=portfolio_id,
            president_name=president_name,
            motion_text=motion_text,
            president_id=president_id,
            llm_config=llm_config,
            raise_on_error=False,
        )

    def _parse_contribution(
        self,
        raw_output: str,
        portfolio_id: str,
        president_name: str,
        motion_text: str = "",
        president_id: str = "",
        llm_config: LLMConfig | None = None,
        raise_on_error: bool = False,
    ) -> PortfolioContribution:
        """Parse the LLM output into a PortfolioContribution."""
        from datetime import datetime, timezone

        generated_at = datetime.now(timezone.utc).isoformat()
        llm_model = llm_config.model if llm_config else ""
        llm_provider = llm_config.provider if llm_config else ""

        # Get unique abbreviation for fallback IDs
        abbrev = self.PORTFOLIO_ABBREV.get(portfolio_id, portfolio_id[-4:].upper())

        try:
            data = parse_json_response(raw_output, aggressive=True)
        except ValueError as e:
            if raise_on_error:
                raise
            return PortfolioContribution(
                portfolio_id=portfolio_id,
                president_id=president_id,
                president_name=president_name,
                status=ContributionStatus.FAILED,
                contribution_summary=f"Parse failure: {e}",
                failure_reason=f"JSON parse error: {e}",
                deliberation_notes=f"Raw output could not be parsed: {raw_output[:500]}",
                llm_model=llm_model,
                llm_provider=llm_provider,
                generated_at=generated_at,
            )

        violations = self._lint_contribution(data, motion_text)
        if violations:
            if raise_on_error:
                raise ValueError("; ".join(violations))
            return PortfolioContribution(
                portfolio_id=portfolio_id,
                president_id=president_id,
                president_name=president_name,
                status=ContributionStatus.FAILED,
                contribution_summary="Lint violations detected in contribution output.",
                failure_reason="; ".join(violations),
                deliberation_notes="Contribution blocked by constitutional lint.",
                llm_model=llm_model,
                llm_provider=llm_provider,
                generated_at=generated_at,
            )

        # Parse functional requirements (use unique abbrev for IDs)
        functional_reqs = []
        for i, req_data in enumerate(data.get("functional_requirements", []), 1):
            try:
                priority = RequirementPriority(
                    req_data.get("priority", "should").lower()
                )
            except ValueError:
                priority = RequirementPriority.SHOULD

            functional_reqs.append(
                FunctionalRequirement(
                    req_id=req_data.get("req_id", f"FR-{abbrev}-{i:03d}"),
                    description=self._normalize_requirement_text(
                        req_data.get("description", "")
                    ),
                    priority=priority,
                    source_portfolio_id=portfolio_id,
                    acceptance_criteria=[
                        self._normalize_requirement_text(item)
                        for item in req_data.get("acceptance_criteria", [])
                    ],
                    rationale=self._normalize_requirement_text(
                        req_data.get("rationale", "")
                    ),
                    dependencies=req_data.get("dependencies", []),
                    independence_requirements=[
                        self._normalize_requirement_text(item)
                        for item in req_data.get("independence_requirements", [])
                    ],
                )
            )

        # Parse non-functional requirements
        non_functional_reqs = []
        for i, req_data in enumerate(data.get("non_functional_requirements", []), 1):
            try:
                category = RequirementCategory(
                    req_data.get("category", "performance").lower()
                )
            except ValueError:
                category = RequirementCategory.PERFORMANCE

            try:
                priority = RequirementPriority(
                    req_data.get("priority", "should").lower()
                )
            except ValueError:
                priority = RequirementPriority.SHOULD

            non_functional_reqs.append(
                NonFunctionalRequirement(
                    req_id=req_data.get("req_id", f"NFR-{abbrev}-{i:03d}"),
                    category=category,
                    description=self._normalize_requirement_text(
                        req_data.get("description", "")
                    ),
                    source_portfolio_id=portfolio_id,
                    target_metric=self._normalize_requirement_text(
                        req_data.get("target_metric", "")
                    ),
                    threshold=self._normalize_requirement_text(
                        req_data.get("threshold", "")
                    ),
                    measurement_method=req_data.get("measurement_method", ""),
                    priority=priority,
                )
            )

        # Parse constraints
        constraints = []
        for i, const_data in enumerate(data.get("constraints", []), 1):
            try:
                const_type = ConstraintType(
                    const_data.get("constraint_type", "technical").lower()
                )
            except ValueError:
                const_type = ConstraintType.TECHNICAL

            resource_type = None
            if const_type == ConstraintType.RESOURCE:
                try:
                    resource_type = ResourceType(
                        const_data.get("resource_type", "capacity").lower()
                    )
                except ValueError:
                    resource_type = ResourceType.CAPACITY

            constraints.append(
                Constraint(
                    constraint_id=const_data.get(
                        "constraint_id", f"C-{abbrev}-{i:03d}"
                    ),
                    constraint_type=const_type,
                    description=self._normalize_requirement_text(
                        const_data.get("description", "")
                    ),
                    source_portfolio_id=portfolio_id,
                    rationale=self._normalize_requirement_text(
                        const_data.get("rationale", "")
                    ),
                    negotiable=const_data.get("negotiable", True),
                    resource_type=resource_type,
                    limit_value=const_data.get("limit_value", ""),
                )
            )

        # Parse deliverables
        deliverables = []
        for i, deliv_data in enumerate(data.get("deliverables", []), 1):
            deliverables.append(
                Deliverable(
                    deliverable_id=deliv_data.get(
                        "deliverable_id", f"D-{abbrev}-{i:03d}"
                    ),
                    name=deliv_data.get("name", ""),
                    description=self._normalize_requirement_text(
                        deliv_data.get("description", "")
                    ),
                    acceptance_criteria=[
                        self._normalize_requirement_text(item)
                        for item in deliv_data.get("acceptance_criteria", [])
                    ],
                    verification_method=deliv_data.get("verification_method", ""),
                    dependencies=deliv_data.get("dependencies", []),
                )
            )

        # Parse evaluation criteria
        eval_criteria = []
        for i, ec_data in enumerate(data.get("evaluation_criteria", []), 1):
            priority_band = ec_data.get("priority_band")
            if not priority_band and "weight" in ec_data:
                weight = float(ec_data.get("weight", 0.0))
                if weight >= 0.5:
                    priority_band = "high"
                elif weight >= 0.2:
                    priority_band = "medium"
                else:
                    priority_band = "low"
            priority_band = (priority_band or "medium").lower()
            eval_criteria.append(
                EvaluationCriterion(
                    criterion_id=ec_data.get("criterion_id", f"EC-{abbrev}-{i:03d}"),
                    name=ec_data.get("name", ""),
                    description=ec_data.get("description", ""),
                    scoring_method=ec_data.get("scoring_method", "1-5 scale"),
                    minimum_threshold=ec_data.get("minimum_threshold", ""),
                    priority_band=priority_band,
                )
            )

        # Determine contribution status
        contribution_summary = data.get("contribution_summary", "")
        has_content = bool(
            functional_reqs or non_functional_reqs or constraints or deliverables
        )

        # Detect no-action responses
        no_action_phrases = [
            "no action required",
            "nothing to contribute",
            "not applicable",
            "no requirements from this portfolio",
            "does not apply",
        ]
        is_no_action = any(
            phrase in contribution_summary.lower() for phrase in no_action_phrases
        )

        if is_no_action or (not has_content and contribution_summary):
            status = ContributionStatus.NO_ACTION
        else:
            status = ContributionStatus.CONTRIBUTED

        return PortfolioContribution(
            portfolio_id=portfolio_id,
            president_id=president_id,
            president_name=president_name,
            status=status,
            contribution_summary=contribution_summary,
            functional_requirements=functional_reqs,
            non_functional_requirements=non_functional_reqs,
            constraints=constraints,
            deliverables=deliverables,
            evaluation_criteria=eval_criteria,
            risks_identified=data.get("risks_identified", []),
            assumptions=data.get("assumptions", []),
            deliberation_notes=data.get("deliberation_notes", ""),
            llm_model=llm_model,
            llm_provider=llm_provider,
            generated_at=generated_at,
        )

    def _normalize_requirement_text(self, text: str) -> str:
        """Normalize requirement phrasing to avoid mechanism-specific language."""
        if not text:
            return text
        normalized = text.strip()
        lowered = normalized.lower()

        # Normalize leading phrasing to capability language
        replacements = {
            "the system must ": "The implementation shall enable ",
            "system must ": "The implementation shall enable ",
            "the system shall ": "The implementation shall enable ",
            "system shall ": "The implementation shall enable ",
        }
        for prefix, replacement in replacements.items():
            if lowered.startswith(prefix):
                normalized = replacement + normalized[len(prefix) :]
                lowered = normalized.lower()
                break

        # Replace enforcement/revocation language with constitutional phrasing
        enforcement_map = {
            "revocation of authority": "non-recognition of binding authority",
            "revocation": "non-recognition",
            "revoke authority": "do not recognize binding authority",
            "revoking authority": "non-recognizing binding authority",
            "revoked": "not recognized as binding",
            "enforcement": "verification and non-recognition",
            "enforce": "verify and refuse to recognize",
        }
        for needle, replacement in enforcement_map.items():
            if needle in lowered:
                normalized = re.sub(
                    re.escape(needle), replacement, normalized, flags=re.IGNORECASE
                )
                lowered = normalized.lower()

        if re.search(r"\b(reject|rejected|rejection)\b", lowered):
            if "authority" in lowered or "action" in lowered:
                normalized = re.sub(
                    r"\b(reject|rejected|rejection)\b",
                    "refuse to recognize",
                    normalized,
                    flags=re.IGNORECASE,
                )
                lowered = normalized.lower()

        # De-mechanize timing/automation specifics into capability language
        normalized = re.sub(
            r"\bwithin\s+\d+\s*ms\b",
            "within a bounded, justified latency",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\b(automatic|automated)\s+arbitration\b",
            "arbitration capability (method proposed by Administrative)",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bautomatically\b",
            "consistently",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bdaily\s+reports?\b",
            "periodic reports (cadence proposed by Administrative)",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\breal[- ]time\b",
            "timely",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\bimmediate\b",
            "prompt",
            normalized,
            flags=re.IGNORECASE,
        )

        return normalized

    def _collect_lint_strings(self, data: dict) -> list[str]:
        """Collect strings from contribution payload for linting."""
        strings: list[str] = []

        def add(value: str) -> None:
            if value:
                strings.append(value)

        def add_list(values: list) -> None:
            for item in values:
                if isinstance(item, str):
                    add(item)

        add(data.get("contribution_summary", ""))
        add(data.get("deliberation_notes", ""))
        add_list(data.get("assumptions", []))
        add_list(data.get("risks_identified", []))

        for req in data.get("functional_requirements", []):
            add(req.get("description", ""))
            add(req.get("rationale", ""))
            add_list(req.get("acceptance_criteria", []))
            add_list(req.get("independence_requirements", []))
            add_list(req.get("dependencies", []))

        for req in data.get("non_functional_requirements", []):
            add(req.get("description", ""))
            add(req.get("target_metric", ""))
            add(req.get("threshold", ""))

        for const in data.get("constraints", []):
            add(const.get("description", ""))
            add(const.get("rationale", ""))
            add(const.get("limit_value", ""))

        for deliverable in data.get("deliverables", []):
            add(deliverable.get("description", ""))
            add_list(deliverable.get("acceptance_criteria", []))

        for criterion in data.get("evaluation_criteria", []):
            add(criterion.get("name", ""))
            add(criterion.get("description", ""))
            add(criterion.get("minimum_threshold", ""))

        return strings

    def _lint_contribution(self, data: dict, motion_text: str) -> list[str]:
        """Lint contribution content for constitutional violations."""
        violations: list[str] = []
        motion_lower = (motion_text or "").lower()
        text_blobs = self._collect_lint_strings(data)

        branch_terms = (
            "witness",
            "audit oversight",
            "accurate guidance",
            "conclave",
            "legislative",
            "executive",
            "administrative",
            "judicial",
            "custodial",
            "secretary",
            "registrar",
            "king",
            "duke",
            "earl",
            "marquis",
            "knight",
            "president",
            "prince",
        )
        branch_pattern = r"|".join(re.escape(t) for t in branch_terms)
        assignment_patterns = [
            rf"\\b(performed|validated|approved|signed|ratified|reviewed|authorized|maintained|handled)\\s+by\\s+(the\\s+)?({branch_pattern})\\b",
            rf"\\baccessible\\s+to\\s+(the\\s+)?({branch_pattern})\\b",
            rf"\\bby\\s+the\\s+({branch_pattern})\\b",
            rf"\\bmust\\s+be\\s+validated\\s+by\\s+({branch_pattern})\\b",
            rf"\\bmust\\s+be\\s+approved\\s+by\\s+({branch_pattern})\\b",
        ]

        governance_terms = [
            "role matrix",
            "consensus framework",
            "divination horizon",
            "divination cycle",
            "council",
            "committee",
            "governance matrix",
            "authority matrix",
            "permission matrix",
        ]

        mechanism_terms = [
            "protocol",
            "engine",
            "dashboard",
            "heatmap",
            "rule set",
            "schema",
            "api",
            "endpoint",
            "ledger implementation",
            "cryptographic",
            "hash",
            "signature",
            "key",
        ]

        metric_patterns = [
            r"\\b\\d+\\s*(ms|millisecond|seconds?|minutes?|hours?|days?)\\b",
            r"\\b\\d+(?:\\.\\d+)?%\\b",
            r"\\b\\d+\\s*concurrent\\b",
        ]

        for text in text_blobs:
            lowered = text.lower()

            for term in branch_terms:
                if term in lowered and term not in motion_lower:
                    violations.append(
                        "Branch or role reference detected outside motion text."
                    )
                    break

            for pattern in assignment_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    violations.append(
                        "Branch assignment detected in contribution content."
                    )
                    break

            for term in governance_terms:
                if term in lowered and term not in motion_lower:
                    violations.append(
                        f"Introduces governance construct not in motion: {term}"
                    )
                    break

            for term in mechanism_terms:
                if term in lowered and term not in motion_lower:
                    violations.append(
                        "Mechanism-specific term detected; use capability language."
                    )
                    break

            for pattern in metric_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    violations.append(
                        "Quantitative constraint detected; defer to Administrative proposals."
                    )
                    break

        # Dedupe violations
        return list(dict.fromkeys(violations))


def create_rfp_contributor(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    llm_config: LLMConfig | None = None,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
) -> RFPContributorCrewAIAdapter:
    """Factory function to create an RFP contributor adapter.

    Args:
        profile_repository: Repository for Archon profiles with LLM configs
        verbose: Enable verbose logging
        llm_config: Default LLM configuration
        model: Override model name
        provider: Override LLM provider (e.g., 'ollama', 'openai', 'anthropic')
        base_url: Override base URL

    Returns:
        Configured RFP contributor adapter
    """
    return RFPContributorCrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        llm_config=llm_config,
        model=model,
        provider=provider,
        base_url=base_url,
    )
