"""Execution Planner Service.

Transforms ratified motions into actionable execution plans by:
1. Loading the pattern taxonomy from configuration
2. Classifying motions into implementation patterns
3. Instantiating concrete tasks from templates
4. Identifying blockers that may require Conclave escalation

This service bridges the Legislative pipeline (Conclave → Review)
with the Executive pipeline (Planning → Implementation → Tracking).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import yaml
from structlog import get_logger

from src.application.ports.execution_planner import (
    ExecutionPlannerProtocol,
    MotionForPlanning,
    PlanningResult,
)
from src.domain.models.execution_plan import (
    Blocker,
    BlockerType,
    EffortEstimate,
    EscalationType,
    ExecutionPhase,
    ExecutionPlan,
    ExecutionPlannerResult,
    ExecutionTask,
    ImplementationPattern,
    PatternClassification,
    TaskStatus,
)

logger = get_logger(__name__)

# Default patterns config path
DEFAULT_PATTERNS_PATH = Path("config/execution-patterns.yaml")


@dataclass
class PatternTaxonomy:
    """Loaded pattern taxonomy from YAML."""

    patterns: dict[str, ImplementationPattern]
    blocker_types: dict[str, dict]
    classification_hints: dict[str, dict]

    @classmethod
    def from_yaml(cls, path: Path) -> PatternTaxonomy:
        """Load taxonomy from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        patterns = {}
        for key, pattern_data in data.get("patterns", {}).items():
            patterns[pattern_data["id"]] = ImplementationPattern.from_dict(
                key, pattern_data
            )

        return cls(
            patterns=patterns,
            blocker_types=data.get("blocker_types", {}),
            classification_hints=data.get("classification_hints", {}),
        )


class ExecutionPlannerService:
    """Service for transforming ratified motions into execution plans.

    This service orchestrates the execution planning process:
    1. Load pattern taxonomy
    2. Load ratified motions from review pipeline output
    3. Classify each motion into patterns (LLM or heuristic)
    4. Instantiate tasks from pattern templates
    5. Detect blockers and prerequisites
    6. Generate complete execution plans
    """

    def __init__(
        self,
        patterns_path: Path = DEFAULT_PATTERNS_PATH,
        planner_agent: ExecutionPlannerProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the service.

        Args:
            patterns_path: Path to execution-patterns.yaml
            planner_agent: Optional LLM-powered planner for classification
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self._planner_agent = planner_agent
        self._taxonomy = PatternTaxonomy.from_yaml(patterns_path)

        logger.info(
            "execution_planner_initialized",
            patterns_loaded=len(self._taxonomy.patterns),
            llm_enabled=planner_agent is not None,
        )

    # =========================================================================
    # Data Loading
    # =========================================================================

    def load_ratified_motions(
        self, review_pipeline_path: Path
    ) -> tuple[list[MotionForPlanning], str, str]:
        """Load ratified motions from review pipeline output.

        Args:
            review_pipeline_path: Path to review pipeline session directory

        Returns:
            Tuple of (motions, session_id, session_name)
        """
        # Load ratification results
        ratification_path = review_pipeline_path / "ratification_results.json"
        with open(ratification_path) as f:
            ratifications = json.load(f)

        # Load full pipeline result for session info
        pipeline_path = review_pipeline_path / "pipeline_result.json"
        with open(pipeline_path) as f:
            pipeline_result = json.load(f)

        session_id = pipeline_result.get("session_id", str(uuid4()))
        session_name = pipeline_result.get("session_name", "Unknown Session")

        # Load motion text from consolidator output
        # The consolidator stores full motion text in mega-motions.json
        consolidator_path = (
            review_pipeline_path.parent.parent / "consolidator" / session_id
        )
        motion_lookup = {}

        # Try to load from consolidator
        mega_motions_file = consolidator_path / "mega-motions.json"
        novel_proposals_file = consolidator_path / "novel-proposals.json"

        if mega_motions_file.exists():
            with open(mega_motions_file) as f:
                mega_motions = json.load(f)
                for mm in mega_motions:
                    motion_lookup[mm["mega_motion_id"]] = {
                        "id": mm["mega_motion_id"],
                        "text": mm.get("consolidated_text", ""),
                        "theme": mm.get("theme", ""),
                        "contributing_archons": mm.get("all_supporting_archons", []),
                    }

        if novel_proposals_file.exists():
            with open(novel_proposals_file) as f:
                novel_proposals = json.load(f)
                for np in novel_proposals:
                    motion_lookup[np["proposal_id"]] = {
                        "id": np["proposal_id"],
                        "text": np.get("proposal_text", ""),
                        "theme": np.get("theme", ""),
                        "contributing_archons": [np.get("archon_name", "")],
                    }

        # Filter to ratified only
        motions = []
        for vote in ratifications:
            if vote["outcome"] != "ratified":
                continue

            motion_id = vote["mega_motion_id"]
            motion_data = motion_lookup.get(motion_id, {})
            # Prefer revised motion text from ratification (post-amendment) if present
            motion_text = vote.get("revised_motion_text") or motion_data.get(
                "text", ""
            )

            motions.append(
                MotionForPlanning(
                    motion_id=motion_id,
                    motion_title=vote["mega_motion_title"],
                    motion_text=motion_text,
                    ratified_at=vote["ratified_at"],
                    yeas=vote["yeas"],
                    nays=vote["nays"],
                    abstentions=vote["abstentions"],
                    source_archons=motion_data.get("contributing_archons", []),
                    theme=motion_data.get("theme", ""),
                )
            )

        logger.info(
            "ratified_motions_loaded",
            motion_count=len(motions),
            session_id=session_id,
        )

        return motions, session_id, session_name

    # =========================================================================
    # Pattern Classification (Heuristic)
    # =========================================================================

    def classify_motion_heuristic(
        self, motion: MotionForPlanning
    ) -> PatternClassification:
        """Classify motion using keyword heuristics (no LLM).

        Falls back to this when LLM planner is not available.
        """
        hints = self._taxonomy.classification_hints
        text_lower = (motion.motion_title + " " + motion.motion_text).lower()

        # Score each pattern by keyword matches
        scores: dict[str, tuple[int, list[str]]] = {}

        for pattern_key, hint_data in hints.items():
            keywords = hint_data.get("keywords", [])
            phrases = hint_data.get("phrases", [])

            matched = []
            score = 0

            for kw in keywords:
                if kw.lower() in text_lower:
                    score += 1
                    matched.append(kw)

            for phrase in phrases:
                if phrase.lower() in text_lower:
                    score += 2  # Phrases worth more
                    matched.append(phrase)

            if score > 0:
                # Map pattern key to pattern ID
                pattern = self._taxonomy.patterns.get(
                    pattern_key.upper(),
                    self._taxonomy.patterns.get(
                        hint_data.get("id", pattern_key.upper())
                    ),
                )
                if pattern:
                    scores[pattern.pattern_id] = (score, matched)

        # Sort by score
        sorted_patterns = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)

        if not sorted_patterns:
            # Default to POLICY if no matches
            primary = "POLICY"
            matched_keywords = []
            confidence = 0.3
        else:
            primary = sorted_patterns[0][0]
            matched_keywords = sorted_patterns[0][1][1]
            # Confidence based on number of matches
            confidence = min(0.9, 0.4 + (sorted_patterns[0][1][0] * 0.1))

        secondary = [p[0] for p in sorted_patterns[1:3]]

        return PatternClassification(
            motion_id=motion.motion_id,
            motion_title=motion.motion_title,
            primary_pattern=primary,
            secondary_patterns=secondary,
            classification_confidence=confidence,
            classification_reasoning=f"Heuristic classification based on {len(matched_keywords)} keyword matches",
            matched_keywords=matched_keywords,
        )

    # =========================================================================
    # Task Instantiation
    # =========================================================================

    def instantiate_tasks_from_pattern(
        self,
        motion: MotionForPlanning,
        pattern: ImplementationPattern,
        phase_number: int,
    ) -> ExecutionPhase:
        """Create concrete tasks from a pattern's templates.

        Args:
            motion: The motion being planned
            pattern: The implementation pattern
            phase_number: Phase number in the execution plan

        Returns:
            ExecutionPhase with instantiated tasks
        """
        tasks = []
        prev_task_id = None

        for template in pattern.task_templates:
            task_id = str(uuid4())

            # Customize description with motion context
            description = f"{template.description} for: {motion.motion_title[:50]}..."

            task = ExecutionTask(
                task_id=task_id,
                task_type=template.task_type,
                description=description,
                pattern_id=pattern.pattern_id,
                motion_id=motion.motion_id,
                status=TaskStatus.PENDING,
                assignable=template.assignable,
                estimated_effort=template.estimated_effort,
                dependencies=[prev_task_id] if prev_task_id else [],
            )
            tasks.append(task)

            if template.assignable:
                prev_task_id = task_id

        return ExecutionPhase(
            phase_id=str(uuid4()),
            phase_number=phase_number,
            pattern_id=pattern.pattern_id,
            pattern_name=pattern.name,
            tasks=tasks,
            phase_description=f"{pattern.name}: {pattern.description}",
        )

    # =========================================================================
    # Blocker Detection
    # =========================================================================

    def detect_blockers_heuristic(
        self,
        motion: MotionForPlanning,
        classification: PatternClassification,
    ) -> list[Blocker]:
        """Detect potential blockers using heuristics.

        Checks for:
        - Missing prerequisites
        - Ambiguous scope keywords
        - Resource-related language without allocation
        """
        blockers: list[Blocker] = []
        pattern = self._taxonomy.patterns.get(classification.primary_pattern)

        if not pattern:
            return blockers

        # Check prerequisites
        for prereq_id in pattern.prerequisites:
            if prereq_id not in classification.secondary_patterns:
                prereq_pattern = self._taxonomy.patterns.get(prereq_id)
                prereq_name = prereq_pattern.name if prereq_pattern else prereq_id

                blockers.append(
                    Blocker(
                        blocker_id=str(uuid4()),
                        motion_id=motion.motion_id,
                        blocker_type=BlockerType.MISSING_PREREQUISITE,
                        description=f"Pattern '{pattern.name}' requires '{prereq_name}' to be completed first",
                        escalation_type=EscalationType.AUTO,
                        escalate_to_conclave=False,
                        suggested_agenda_item=None,
                        related_task_id=None,
                    )
                )

        # Check for scope ambiguity
        ambiguous_phrases = [
            "as appropriate",
            "as needed",
            "when necessary",
            "if applicable",
            "to be determined",
            "tbd",
        ]
        text_lower = motion.motion_text.lower()

        for phrase in ambiguous_phrases:
            if phrase in text_lower:
                blockers.append(
                    Blocker(
                        blocker_id=str(uuid4()),
                        motion_id=motion.motion_id,
                        blocker_type=BlockerType.UNDEFINED_SCOPE,
                        description=f"Motion contains ambiguous language: '{phrase}'",
                        escalation_type=EscalationType.CONCLAVE,
                        escalate_to_conclave=True,
                        suggested_agenda_item=f"Clarify scope for: {motion.motion_title[:50]}...",
                        related_task_id=None,
                    )
                )
                break  # Only report one scope blocker

        # Check typical blockers from pattern
        for typical in pattern.typical_blockers[:2]:  # Limit to 2
            blockers.append(
                Blocker(
                    blocker_id=str(uuid4()),
                    motion_id=motion.motion_id,
                    blocker_type=BlockerType.UNDEFINED_SCOPE,
                    description=f"Potential issue: {typical}",
                    escalation_type=EscalationType.MANUAL,
                    escalate_to_conclave=False,
                    suggested_agenda_item=None,
                    related_task_id=None,
                )
            )

        return blockers

    # =========================================================================
    # Plan Generation
    # =========================================================================

    def generate_execution_plan(self, motion: MotionForPlanning) -> ExecutionPlan:
        """Generate complete execution plan for a motion (heuristic mode).

        Args:
            motion: The ratified motion to plan

        Returns:
            Complete ExecutionPlan
        """
        # Classify
        classification = self.classify_motion_heuristic(motion)

        # Build phases from patterns
        phases = []
        all_outputs = []
        phase_num = 1

        # Primary pattern
        primary_pattern = self._taxonomy.patterns.get(classification.primary_pattern)
        if primary_pattern:
            phase = self.instantiate_tasks_from_pattern(
                motion, primary_pattern, phase_num
            )
            phases.append(phase)
            all_outputs.extend(primary_pattern.outputs)
            phase_num += 1

        # Secondary patterns
        for sec_id in classification.secondary_patterns:
            sec_pattern = self._taxonomy.patterns.get(sec_id)
            if sec_pattern:
                phase = self.instantiate_tasks_from_pattern(
                    motion, sec_pattern, phase_num
                )
                phases.append(phase)
                all_outputs.extend(sec_pattern.outputs)
                phase_num += 1

        # Detect blockers
        blockers = self.detect_blockers_heuristic(motion, classification)

        # Calculate effort
        total_tasks = sum(len(p.tasks) for p in phases)
        if total_tasks <= 5:
            effort = "low"
        elif total_tasks <= 10:
            effort = "medium"
        elif total_tasks <= 15:
            effort = "high"
        else:
            effort = "very_high"

        plan = ExecutionPlan(
            plan_id=str(uuid4()),
            motion_id=motion.motion_id,
            motion_title=motion.motion_title,
            motion_text=motion.motion_text,
            classification=classification,
            phases=phases,
            blockers=blockers,
            expected_outputs=list(set(all_outputs)),
            estimated_total_effort=effort,
            status="draft",
        )

        logger.info(
            "execution_plan_generated",
            motion_id=motion.motion_id,
            pattern=classification.primary_pattern,
            phases=len(phases),
            tasks=plan.total_tasks,
            blockers=len(blockers),
        )

        return plan

    async def generate_execution_plan_async(
        self, motion: MotionForPlanning
    ) -> ExecutionPlan:
        """Generate execution plan using LLM planner if available.

        Args:
            motion: The ratified motion to plan

        Returns:
            Complete ExecutionPlan
        """
        if not self._planner_agent:
            return self.generate_execution_plan(motion)

        # Use LLM planner
        patterns_list = [
            {
                "id": p.pattern_id,
                "name": p.name,
                "description": p.description,
                "domain": p.domain.value,
                "task_templates": [
                    {"type": t.task_type, "description": t.description}
                    for t in p.task_templates
                ],
                "prerequisites": p.prerequisites,
                "typical_blockers": p.typical_blockers,
            }
            for p in self._taxonomy.patterns.values()
        ]

        result = await self._planner_agent.plan_motion_execution(motion, patterns_list)

        # Convert PlanningResult to ExecutionPlan
        return self._convert_planning_result(motion, result)

    def _convert_planning_result(
        self,
        motion: MotionForPlanning,
        result: PlanningResult,
    ) -> ExecutionPlan:
        """Convert LLM PlanningResult to domain ExecutionPlan."""
        classification = PatternClassification(
            motion_id=result.motion_id,
            motion_title=result.motion_title,
            primary_pattern=result.classification.primary_pattern_id,
            secondary_patterns=result.classification.secondary_pattern_ids,
            classification_confidence=result.classification.confidence,
            classification_reasoning=result.classification.reasoning,
            matched_keywords=result.classification.matched_keywords,
        )

        # Group tasks by pattern into phases
        phases = []
        pattern_tasks: dict[str, list[ExecutionTask]] = {}

        for task in result.tasks:
            # Determine pattern from task type
            pattern_id = classification.primary_pattern
            for pid, pattern in self._taxonomy.patterns.items():
                if any(t.task_type == task.task_type for t in pattern.task_templates):
                    pattern_id = pid
                    break

            if pattern_id not in pattern_tasks:
                pattern_tasks[pattern_id] = []

            pattern_tasks[pattern_id].append(
                ExecutionTask(
                    task_id=str(uuid4()),
                    task_type=task.task_type,
                    description=task.description,
                    pattern_id=pattern_id,
                    motion_id=motion.motion_id,
                    assignable=task.assignable,
                    estimated_effort=EffortEstimate(task.estimated_effort),
                    notes=task.context_notes,
                )
            )

        phase_num = 1
        for pattern_id, tasks in pattern_tasks.items():
            pattern = self._taxonomy.patterns.get(pattern_id)
            phases.append(
                ExecutionPhase(
                    phase_id=str(uuid4()),
                    phase_number=phase_num,
                    pattern_id=pattern_id,
                    pattern_name=pattern.name if pattern else pattern_id,
                    tasks=tasks,
                )
            )
            phase_num += 1

        # Convert blockers
        blockers = [
            Blocker(
                blocker_id=str(uuid4()),
                motion_id=motion.motion_id,
                blocker_type=BlockerType(b.blocker_type),
                description=b.description,
                escalation_type=(
                    EscalationType.CONCLAVE
                    if b.escalate_to_conclave
                    else EscalationType.MANUAL
                ),
                escalate_to_conclave=b.escalate_to_conclave,
                suggested_agenda_item=b.suggested_agenda_item,
            )
            for b in result.blockers
        ]

        total_tasks = sum(len(p.tasks) for p in phases)
        effort = (
            "low"
            if total_tasks <= 5
            else "medium"
            if total_tasks <= 10
            else "high"
            if total_tasks <= 15
            else "very_high"
        )

        return ExecutionPlan(
            plan_id=str(uuid4()),
            motion_id=motion.motion_id,
            motion_title=motion.motion_title,
            motion_text=motion.motion_text,
            classification=classification,
            phases=phases,
            blockers=blockers,
            expected_outputs=result.expected_outputs,
            estimated_total_effort=effort,
            status="draft",
        )

    # =========================================================================
    # Batch Processing
    # =========================================================================

    def run_planning_pipeline(
        self,
        review_pipeline_path: Path,
    ) -> ExecutionPlannerResult:
        """Run the full planning pipeline on ratified motions (sync/heuristic).

        Args:
            review_pipeline_path: Path to review pipeline session output

        Returns:
            ExecutionPlannerResult with all plans
        """
        motions, session_id, session_name = self.load_ratified_motions(
            review_pipeline_path
        )

        plans = []
        patterns_used: dict[str, int] = {}

        for motion in motions:
            plan = self.generate_execution_plan(motion)
            plans.append(plan)

            # Track pattern usage
            pattern_id = plan.classification.primary_pattern
            patterns_used[pattern_id] = patterns_used.get(pattern_id, 0) + 1

        total_tasks = sum(p.total_tasks for p in plans)
        total_blockers = sum(len(p.blockers) for p in plans)
        conclave_blockers = sum(
            1 for p in plans for b in p.blockers if b.escalate_to_conclave
        )

        result = ExecutionPlannerResult(
            session_id=session_id,
            session_name=session_name,
            plans=plans,
            total_motions_processed=len(motions),
            total_tasks_generated=total_tasks,
            total_blockers_identified=total_blockers,
            blockers_requiring_conclave=conclave_blockers,
            patterns_used=patterns_used,
        )

        logger.info(
            "planning_pipeline_complete",
            motions=len(motions),
            plans=len(plans),
            tasks=total_tasks,
            blockers=total_blockers,
            conclave_blockers=conclave_blockers,
        )

        return result

    async def run_planning_pipeline_async(
        self,
        review_pipeline_path: Path,
    ) -> ExecutionPlannerResult:
        """Run the full planning pipeline with LLM planner.

        Args:
            review_pipeline_path: Path to review pipeline session output

        Returns:
            ExecutionPlannerResult with all plans
        """
        motions, session_id, session_name = self.load_ratified_motions(
            review_pipeline_path
        )

        plans = []
        patterns_used: dict[str, int] = {}

        for motion in motions:
            plan = await self.generate_execution_plan_async(motion)
            plans.append(plan)

            pattern_id = plan.classification.primary_pattern
            patterns_used[pattern_id] = patterns_used.get(pattern_id, 0) + 1

        total_tasks = sum(p.total_tasks for p in plans)
        total_blockers = sum(len(p.blockers) for p in plans)
        conclave_blockers = sum(
            1 for p in plans for b in p.blockers if b.escalate_to_conclave
        )

        return ExecutionPlannerResult(
            session_id=session_id,
            session_name=session_name,
            plans=plans,
            total_motions_processed=len(motions),
            total_tasks_generated=total_tasks,
            total_blockers_identified=total_blockers,
            blockers_requiring_conclave=conclave_blockers,
            patterns_used=patterns_used,
        )

    # =========================================================================
    # Output
    # =========================================================================

    def save_results(
        self,
        result: ExecutionPlannerResult,
        output_dir: Path,
    ) -> Path:
        """Save planning results to disk.

        Args:
            result: The planning result to save
            output_dir: Base output directory

        Returns:
            Path to session output directory
        """
        session_dir = output_dir / result.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save full result
        with open(session_dir / "execution_plans.json", "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        # Save individual plans
        plans_dir = session_dir / "plans"
        plans_dir.mkdir(exist_ok=True)

        for plan in result.plans:
            plan_file = plans_dir / f"{plan.plan_id}.json"
            with open(plan_file, "w") as f:
                json.dump(plan.to_dict(), f, indent=2)

        # Save blockers summary
        all_blockers = [b for p in result.plans for b in p.blockers]
        conclave_blockers = [b for b in all_blockers if b.escalate_to_conclave]

        blockers_summary = {
            "total_blockers": len(all_blockers),
            "conclave_escalations": len(conclave_blockers),
            "blockers": [b.to_dict() for b in all_blockers],
            "agenda_items": [
                b.suggested_agenda_item
                for b in conclave_blockers
                if b.suggested_agenda_item
            ],
        }

        with open(session_dir / "blockers_summary.json", "w") as f:
            json.dump(blockers_summary, f, indent=2)

        # Save pattern usage summary
        with open(session_dir / "pattern_usage.json", "w") as f:
            json.dump(
                {
                    "patterns_used": result.patterns_used,
                    "total_motions": result.total_motions_processed,
                },
                f,
                indent=2,
            )

        logger.info(
            "results_saved",
            session_dir=str(session_dir),
            plans=len(result.plans),
            blockers=len(all_blockers),
        )

        return session_dir
