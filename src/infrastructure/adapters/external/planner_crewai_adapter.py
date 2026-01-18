"""CrewAI adapter for Execution Planner operations.

Implements ExecutionPlannerProtocol using CrewAI for LLM-powered motion classification
and task instantiation. The planner analyzes ratified motions and determines
the most appropriate implementation patterns.

Constitutional Compliance:
- CT-11: All LLM calls logged, failures reported
- CT-12: All plans traceable to source motions

LLM Configuration:
- Uses a dedicated planner agent (not an Archon)
- Configurable via environment or explicit config
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time

from crewai import LLM, Agent, Crew, Task
from structlog import get_logger

from src.application.ports.execution_planner import (
    BlockerDetection,
    BlockerDetectionError,
    ClassificationError,
    ClassificationResult,
    ExecutionPlannerProtocol,
    InstantiationError,
    MotionForPlanning,
    PlanningError,
    PlanningResult,
    TaskInstantiation,
)

logger = get_logger(__name__)


def _escape_control_chars_in_strings(text: str) -> str:
    """Escape unescaped control characters inside JSON string values."""
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

        if in_string and ord(char) < 32:
            if char == "\n":
                result.append("\\n")
            elif char == "\r":
                result.append("\\r")
            elif char == "\t":
                result.append("\\t")
            else:
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

    # Escape control characters inside string values
    cleaned = _escape_control_chars_in_strings(cleaned)

    return json.loads(cleaned)


class PlannerCrewAIAdapter(ExecutionPlannerProtocol):
    """CrewAI implementation of ExecutionPlannerProtocol.

    Uses CrewAI to orchestrate an LLM agent for motion classification,
    task instantiation, and blocker detection.
    """

    def __init__(
        self,
        verbose: bool = False,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            verbose: Enable verbose LLM logging
            model: Optional model override (default: ollama/qwen3:latest)
            base_url: Optional base URL for Ollama (default: from OLLAMA_HOST)
        """
        self.verbose = verbose

        # Configure LLM
        ollama_host = base_url or os.environ.get(
            "OLLAMA_HOST", "http://localhost:11434"
        )
        model_string = model or "ollama/qwen3:latest"

        self._llm = LLM(
            model=model_string,
            base_url=ollama_host,
            temperature=0.3,
            max_tokens=4096,
        )

        logger.info(
            "planner_adapter_initialized",
            model=model_string,
            base_url=ollama_host,
            verbose=verbose,
        )

    def _create_classifier_agent(self) -> Agent:
        """Create the classification agent."""
        return Agent(
            role="Motion Classifier",
            goal="Accurately classify motions into implementation patterns based on content analysis",
            backstory="""You are an expert classifier for the Archon72 governance system.
Your role is to analyze ratified motions from the Conclave and determine which
implementation patterns best fit each motion. You understand the distinctions
between governance changes (constitutional amendments, policy frameworks),
implementation work (technical safeguards, archon capabilities), and operational
procedures (process protocols, resource allocation). You focus on the substantive
content of each motion to make accurate classifications.""",
            llm=self._llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def _create_task_planner_agent(self) -> Agent:
        """Create the task planning agent."""
        return Agent(
            role="Task Planner",
            goal="Transform classified motions into concrete, actionable tasks",
            backstory="""You are an expert project planner for the Archon72 governance system.
Your role is to take classified motions and instantiate specific tasks based on
pattern templates. You understand how to customize generic task templates with
motion-specific context, creating clear descriptions that can be assigned and
executed. You ensure task dependencies are properly ordered and effort estimates
are realistic.""",
            llm=self._llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def _create_blocker_analyst_agent(self) -> Agent:
        """Create the blocker analysis agent."""
        return Agent(
            role="Blocker Analyst",
            goal="Identify impediments and risks that could block motion execution",
            backstory="""You are a risk analyst for the Archon72 governance system.
Your role is to examine motions and their execution plans to identify potential
blockers. You look for missing prerequisites, ambiguous scope, resource gaps,
policy conflicts, and technical infeasibility. When blockers are serious enough,
you recommend escalation to the Conclave for deliberation. You are thorough but
not alarmist - you flag genuine risks without creating unnecessary obstacles.""",
            llm=self._llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    async def classify_motion(
        self,
        motion: MotionForPlanning,
        available_patterns: list[dict],
    ) -> ClassificationResult:
        """Classify a motion into implementation patterns."""
        start_time = time.time()

        logger.info(
            "classify_motion_start",
            motion_id=motion.motion_id,
            motion_title=motion.motion_title[:50],
        )

        agent = self._create_classifier_agent()

        patterns_text = "\n".join(
            f"- **{p['id']}** ({p['name']}): {p['description']}"
            for p in available_patterns
        )

        classify_prompt = f"""Analyze this ratified motion and classify it into one or more implementation patterns.

**MOTION TO CLASSIFY:**
Title: {motion.motion_title}
Theme: {motion.theme}
Supporters: {len(motion.source_archons)} Archons
Vote: {motion.yeas} Yeas, {motion.nays} Nays, {motion.abstentions} Abstentions

**MOTION TEXT:**
{motion.motion_text[:3000]}

**AVAILABLE PATTERNS:**
{patterns_text}

**YOUR TASK:**
1. Read the motion text carefully
2. Identify the PRIMARY pattern that best fits the motion's main intent
3. Identify any SECONDARY patterns that apply (0-2)
4. Extract keywords that drove your classification
5. Explain your reasoning

**RESPOND IN JSON FORMAT:**
{{
    "primary_pattern_id": "PATTERN_ID",
    "primary_pattern_name": "Pattern Name",
    "secondary_pattern_ids": ["ID1", "ID2"],
    "confidence": 0.0-1.0,
    "reasoning": "Your classification reasoning (2-3 sentences)",
    "matched_keywords": ["keyword1", "keyword2", "keyword3"]
}}
"""

        task = Task(
            description=classify_prompt,
            expected_output="JSON with pattern classification",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = _parse_json_response(raw_output)

            classification = ClassificationResult(
                motion_id=motion.motion_id,
                primary_pattern_id=parsed.get("primary_pattern_id", "POLICY"),
                primary_pattern_name=parsed.get(
                    "primary_pattern_name", "Policy Framework"
                ),
                secondary_pattern_ids=parsed.get("secondary_pattern_ids", []),
                confidence=float(parsed.get("confidence", 0.7)),
                reasoning=parsed.get("reasoning", ""),
                matched_keywords=parsed.get("matched_keywords", []),
            )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "classify_motion_complete",
                motion_id=motion.motion_id,
                primary_pattern=classification.primary_pattern_id,
                secondary_patterns=classification.secondary_pattern_ids,
                confidence=classification.confidence,
                duration_ms=duration_ms,
            )

            return classification

        except json.JSONDecodeError as e:
            logger.error(
                "classify_motion_parse_failed",
                motion_id=motion.motion_id,
                error=str(e),
            )
            raise ClassificationError(f"Failed to parse classification: {e}") from e
        except Exception as e:
            logger.error(
                "classify_motion_failed",
                motion_id=motion.motion_id,
                error=str(e),
            )
            raise ClassificationError(f"Classification failed: {e}") from e

    async def instantiate_tasks(
        self,
        motion: MotionForPlanning,
        pattern_id: str,
        task_templates: list[dict],
    ) -> list[TaskInstantiation]:
        """Instantiate concrete tasks from pattern templates."""
        start_time = time.time()

        logger.info(
            "instantiate_tasks_start",
            motion_id=motion.motion_id,
            pattern_id=pattern_id,
            template_count=len(task_templates),
        )

        agent = self._create_task_planner_agent()

        templates_text = "\n".join(
            f"- **{t['type']}**: {t['description']}" for t in task_templates
        )

        instantiate_prompt = f"""Create motion-specific tasks based on these templates.

**MOTION:**
Title: {motion.motion_title}
Text: {motion.motion_text[:2000]}

**PATTERN:** {pattern_id}

**TASK TEMPLATES:**
{templates_text}

**YOUR TASK:**
For each template, create a concrete task with:
1. Motion-specific description (customize the generic template)
2. Whether it can be assigned to someone
3. Realistic effort estimate (low/medium/high)
4. Context notes specific to this motion

**RESPOND IN JSON FORMAT:**
{{
    "tasks": [
        {{
            "task_type": "template_type",
            "description": "Motion-specific task description",
            "assignable": true,
            "estimated_effort": "low|medium|high",
            "context_notes": "Motion-specific context for this task"
        }}
    ]
}}
"""

        task = Task(
            description=instantiate_prompt,
            expected_output="JSON with instantiated tasks",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = _parse_json_response(raw_output)

            tasks = [
                TaskInstantiation(
                    task_type=t.get("task_type", "unknown"),
                    description=t.get("description", ""),
                    assignable=t.get("assignable", True),
                    estimated_effort=t.get("estimated_effort", "medium"),
                    context_notes=t.get("context_notes", ""),
                )
                for t in parsed.get("tasks", [])
            ]

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "instantiate_tasks_complete",
                motion_id=motion.motion_id,
                task_count=len(tasks),
                duration_ms=duration_ms,
            )

            return tasks

        except json.JSONDecodeError as e:
            logger.error(
                "instantiate_tasks_parse_failed",
                motion_id=motion.motion_id,
                error=str(e),
            )
            raise InstantiationError(f"Failed to parse tasks: {e}") from e
        except Exception as e:
            logger.error(
                "instantiate_tasks_failed",
                motion_id=motion.motion_id,
                error=str(e),
            )
            raise InstantiationError(f"Task instantiation failed: {e}") from e

    async def detect_blockers(
        self,
        motion: MotionForPlanning,
        classification: ClassificationResult,
        available_patterns: list[dict],
    ) -> list[BlockerDetection]:
        """Detect potential blockers for motion execution."""
        start_time = time.time()

        logger.info(
            "detect_blockers_start",
            motion_id=motion.motion_id,
            pattern=classification.primary_pattern_id,
        )

        agent = self._create_blocker_analyst_agent()

        # Find the pattern details
        pattern = next(
            (
                p
                for p in available_patterns
                if p["id"] == classification.primary_pattern_id
            ),
            None,
        )

        prerequisites_text = ""
        typical_blockers_text = ""
        if pattern:
            prerequisites_text = ", ".join(pattern.get("prerequisites", [])) or "None"
            typical_blockers_text = (
                "\n".join(f"- {b}" for b in pattern.get("typical_blockers", []))
                or "None known"
            )

        blocker_prompt = f"""Analyze this motion for potential execution blockers.

**MOTION:**
Title: {motion.motion_title}
Pattern: {classification.primary_pattern_id} ({classification.primary_pattern_name})
Text: {motion.motion_text[:2500]}

**PATTERN PREREQUISITES:** {prerequisites_text}

**TYPICAL BLOCKERS FOR THIS PATTERN:**
{typical_blockers_text}

**YOUR TASK:**
Identify blockers that could impede execution:
1. Missing prerequisites (other patterns that must complete first)
2. Undefined scope (ambiguous language that needs clarification)
3. Resource gaps (insufficient budget, personnel, infrastructure)
4. Policy conflicts (contradictions with existing policies)
5. Technical infeasibility (cannot be implemented as specified)
6. Stakeholder conflicts (competing requirements)

For each blocker, determine if it should escalate to the Conclave.
Escalate when: the blocker requires deliberation, policy decision, or cannot be resolved operationally.

**RESPOND IN JSON FORMAT:**
{{
    "blockers": [
        {{
            "blocker_type": "missing_prerequisite|undefined_scope|resource_gap|policy_conflict|technical_infeasibility|stakeholder_conflict",
            "description": "Clear description of the blocker",
            "severity": "low|medium|high|critical",
            "escalate_to_conclave": true|false,
            "suggested_agenda_item": "If escalating, the agenda item title" or null,
            "resolution_hint": "How this might be resolved" or null
        }}
    ]
}}

If no blockers are detected, return: {{"blockers": []}}
"""

        task = Task(
            description=blocker_prompt,
            expected_output="JSON with detected blockers",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = _parse_json_response(raw_output)

            blockers = [
                BlockerDetection(
                    blocker_type=b.get("blocker_type", "undefined_scope"),
                    description=b.get("description", ""),
                    severity=b.get("severity", "medium"),
                    escalate_to_conclave=b.get("escalate_to_conclave", False),
                    suggested_agenda_item=b.get("suggested_agenda_item"),
                    resolution_hint=b.get("resolution_hint"),
                )
                for b in parsed.get("blockers", [])
            ]

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "detect_blockers_complete",
                motion_id=motion.motion_id,
                blocker_count=len(blockers),
                escalations=sum(1 for b in blockers if b.escalate_to_conclave),
                duration_ms=duration_ms,
            )

            return blockers

        except json.JSONDecodeError as e:
            logger.error(
                "detect_blockers_parse_failed",
                motion_id=motion.motion_id,
                error=str(e),
            )
            raise BlockerDetectionError(f"Failed to parse blockers: {e}") from e
        except Exception as e:
            logger.error(
                "detect_blockers_failed",
                motion_id=motion.motion_id,
                error=str(e),
            )
            raise BlockerDetectionError(f"Blocker detection failed: {e}") from e

    async def plan_motion_execution(
        self,
        motion: MotionForPlanning,
        available_patterns: list[dict],
    ) -> PlanningResult:
        """Generate complete execution plan for a motion."""
        start_time = time.time()

        logger.info(
            "plan_motion_execution_start",
            motion_id=motion.motion_id,
            motion_title=motion.motion_title[:50],
        )

        try:
            # Step 1: Classify
            classification = await self.classify_motion(motion, available_patterns)

            # Step 2: Get pattern templates
            pattern = next(
                (
                    p
                    for p in available_patterns
                    if p["id"] == classification.primary_pattern_id
                ),
                None,
            )

            if not pattern:
                raise PlanningError(
                    f"Pattern {classification.primary_pattern_id} not found"
                )

            # Step 3: Instantiate tasks
            tasks = await self.instantiate_tasks(
                motion,
                classification.primary_pattern_id,
                pattern.get("task_templates", []),
            )

            # Step 4: Detect blockers
            blockers = await self.detect_blockers(
                motion, classification, available_patterns
            )

            duration_ms = int((time.time() - start_time) * 1000)

            result = PlanningResult(
                motion_id=motion.motion_id,
                motion_title=motion.motion_title,
                classification=classification,
                tasks=tasks,
                blockers=blockers,
                expected_outputs=pattern.get("outputs", []),
                planning_notes=f"LLM-powered planning completed in {duration_ms}ms",
                planning_duration_ms=duration_ms,
            )

            logger.info(
                "plan_motion_execution_complete",
                motion_id=motion.motion_id,
                pattern=classification.primary_pattern_id,
                tasks=len(tasks),
                blockers=len(blockers),
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            logger.error(
                "plan_motion_execution_failed",
                motion_id=motion.motion_id,
                error=str(e),
            )
            raise PlanningError(f"Planning failed: {e}") from e

    async def batch_plan_motions(
        self,
        motions: list[MotionForPlanning],
        available_patterns: list[dict],
    ) -> list[PlanningResult]:
        """Generate execution plans for multiple motions."""
        logger.info(
            "batch_plan_motions_start",
            motion_count=len(motions),
        )

        results = []
        for motion in motions:
            try:
                result = await self.plan_motion_execution(motion, available_patterns)
                results.append(result)
            except PlanningError as e:
                logger.error(
                    "batch_plan_motion_failed",
                    motion_id=motion.motion_id,
                    error=str(e),
                )
                # Continue with other motions

        logger.info(
            "batch_plan_motions_complete",
            planned=len(results),
            failed=len(motions) - len(results),
        )

        return results


def create_planner_agent(
    verbose: bool = False,
    model: str | None = None,
    base_url: str | None = None,
) -> ExecutionPlannerProtocol:
    """Factory function to create an ExecutionPlanner instance.

    Args:
        verbose: Enable verbose LLM logging
        model: Optional model string (default: ollama/qwen3:latest)
        base_url: Optional Ollama base URL (default: from OLLAMA_HOST env)

    Returns:
        ExecutionPlannerProtocol implementation
    """
    return PlannerCrewAIAdapter(
        verbose=verbose,
        model=model,
        base_url=base_url,
    )
