"""Motion Consolidator Service for sustainable governance.

Consolidates many motions into fewer mega-motions while preserving
full traceability to original recommendations and clusters.

This is the HYBRID approach:
- All original data preserved (909 recommendations, 69 motions)
- Consolidated mega-motions for efficient deliberation
- Full audit trail maintained

Constitutional Constraints:
- CT-11: No silent failures - all consolidation decisions logged
- CT-12: Witnessing accountability - every mega-motion traces to sources
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from crewai import Agent, Crew, LLM, Task
from structlog import get_logger

from src.domain.models.secretary_agent import load_secretary_config_from_yaml

logger = get_logger(__name__)

# Target number of mega-motions
TARGET_MEGA_MOTION_COUNT = 12


@dataclass
class SourceMotion:
    """A motion from the Secretary output."""

    motion_id: str
    title: str
    text: str
    theme: str
    archon_count: int
    supporting_archons: list[str]
    cluster_id: str


@dataclass
class MegaMotion:
    """A consolidated mega-motion combining related motions."""

    mega_motion_id: UUID
    title: str
    theme: str
    consolidated_text: str
    rationale: str
    source_motion_ids: list[str]
    source_motion_titles: list[str]
    source_cluster_ids: list[str]
    all_supporting_archons: list[str]
    unique_archon_count: int
    consensus_tier: str  # "high", "medium", "low"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConsolidationResult:
    """Result of motion consolidation."""

    mega_motions: list[MegaMotion]
    original_motion_count: int
    consolidation_ratio: float
    traceability_complete: bool
    orphaned_motions: list[str]  # Should be empty if successful


class MotionConsolidatorService:
    """Service to consolidate motions into mega-motions.

    Uses LLM to identify thematic groupings and synthesize
    consolidated motion text while preserving traceability.
    """

    def __init__(
        self,
        verbose: bool = False,
        target_count: int = TARGET_MEGA_MOTION_COUNT,
    ) -> None:
        """Initialize the consolidator.

        Args:
            verbose: Enable verbose LLM logging
            target_count: Target number of mega-motions to produce
        """
        self._verbose = verbose
        self._target_count = target_count

        # Load LLM config from YAML (uses JSON model for structured output)
        _, json_config, _ = load_secretary_config_from_yaml()

        # Create LLM for consolidation tasks
        self._llm = self._create_llm(json_config)
        self._agent = Agent(
            role="Motion Consolidator",
            goal="Group related motions into coherent mega-motions while preserving all source references",
            backstory="""You are a legislative expert specializing in consolidating
            multiple related proposals into coherent, comprehensive motions. You identify
            thematic overlaps, merge compatible provisions, and produce clear consolidated
            text that honors all source contributions.""",
            verbose=verbose,
            allow_delegation=False,
            llm=self._llm,
            max_iter=3,
            tools=[],
        )

        logger.info(
            "motion_consolidator_initialized",
            target_count=target_count,
            model=json_config.model,
        )

    def _create_llm(self, llm_config) -> LLM:
        """Create CrewAI LLM from config."""
        import os

        if llm_config.provider == "local":
            ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            return LLM(
                model=f"ollama/{llm_config.model}",
                base_url=ollama_host,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )
        return LLM(model=f"{llm_config.provider}/{llm_config.model}")

    def load_motions_from_checkpoint(self, checkpoint_path: Path) -> list[SourceMotion]:
        """Load motions from Secretary checkpoint file.

        Args:
            checkpoint_path: Path to *_05_motions.json checkpoint

        Returns:
            List of SourceMotion objects
        """
        with open(checkpoint_path) as f:
            data = json.load(f)

        motions = []
        for item in data:
            motion = SourceMotion(
                motion_id=item.get("queued_motion_id", str(uuid4())),
                title=item.get("title", "Untitled Motion"),
                text=item.get("text", ""),
                theme=item.get("source_cluster_theme", "Unknown"),
                archon_count=item.get("original_archon_count", 1),
                supporting_archons=item.get("supporting_archons", []),
                cluster_id=item.get("source_cluster_id", ""),
            )
            motions.append(motion)

        logger.info("motions_loaded_from_checkpoint", count=len(motions))
        return motions

    async def consolidate(
        self,
        motions: list[SourceMotion],
    ) -> ConsolidationResult:
        """Consolidate motions into mega-motions.

        Args:
            motions: List of source motions to consolidate

        Returns:
            ConsolidationResult with mega-motions and traceability
        """
        logger.info("consolidation_start", motion_count=len(motions))

        # Step 1: Get thematic groupings from LLM
        groupings = await self._identify_groupings(motions)

        # Step 2: Synthesize mega-motions for each group
        mega_motions = []
        accounted_motion_ids = set()

        for group in groupings:
            group_motions = [m for m in motions if m.motion_id in group["motion_ids"]]
            if not group_motions:
                continue

            mega_motion = await self._synthesize_mega_motion(
                theme=group["theme"],
                motions=group_motions,
            )
            mega_motions.append(mega_motion)
            accounted_motion_ids.update(group["motion_ids"])

        # Check for orphaned motions
        all_motion_ids = {m.motion_id for m in motions}
        orphaned = list(all_motion_ids - accounted_motion_ids)

        if orphaned:
            logger.warning("orphaned_motions_found", count=len(orphaned))

        result = ConsolidationResult(
            mega_motions=mega_motions,
            original_motion_count=len(motions),
            consolidation_ratio=len(mega_motions) / len(motions) if motions else 0,
            traceability_complete=len(orphaned) == 0,
            orphaned_motions=orphaned,
        )

        logger.info(
            "consolidation_complete",
            mega_motion_count=len(mega_motions),
            original_count=len(motions),
            ratio=f"{result.consolidation_ratio:.2%}",
            orphaned=len(orphaned),
        )

        return result

    async def _identify_groupings(
        self,
        motions: list[SourceMotion],
    ) -> list[dict]:
        """Use LLM to identify thematic groupings."""
        # Prepare motion summaries for LLM
        motion_summaries = json.dumps(
            [
                {
                    "id": m.motion_id,
                    "title": m.title,
                    "theme": m.theme,
                    "archon_count": m.archon_count,
                }
                for m in motions
            ],
            indent=2,
        )

        task = Task(
            description=f"""Group these {len(motions)} motions into {self._target_count} thematic categories.

MOTIONS:
{motion_summaries}

Create exactly {self._target_count} groups based on thematic similarity.
Each motion must belong to exactly ONE group.
No motion should be left ungrouped.

Return a JSON array of groups:
[{{"theme": "Theme Name", "motion_ids": ["id1", "id2", ...]}}]

CRITICAL: Output ONLY valid JSON. Include ALL motion IDs exactly once.""",
            expected_output="JSON array of motion groupings",
            agent=self._agent,
        )

        crew = Crew(
            agents=[self._agent],
            tasks=[task],
            verbose=self._verbose,
        )

        result = await asyncio.to_thread(crew.kickoff)
        return self._parse_groupings(str(result), motions)

    def _parse_groupings(
        self,
        result: str,
        motions: list[SourceMotion],
    ) -> list[dict]:
        """Parse LLM grouping result."""
        # Extract JSON array
        cleaned = result.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1:
            logger.error("no_json_array_in_groupings", raw=result[:200])
            # Fallback: single group with all motions
            return [{"theme": "All Motions", "motion_ids": [m.motion_id for m in motions]}]

        try:
            json_str = cleaned[start:end + 1]
            data = json.loads(json_str)

            # Validate all motions are accounted for
            all_ids = {m.motion_id for m in motions}
            grouped_ids = set()
            for group in data:
                grouped_ids.update(group.get("motion_ids", []))

            missing = all_ids - grouped_ids
            if missing:
                logger.warning("motions_missing_from_groups", count=len(missing))
                # Add missing to last group or create "Other" group
                if data:
                    data[-1]["motion_ids"].extend(list(missing))
                else:
                    data.append({"theme": "Other", "motion_ids": list(missing)})

            return data

        except json.JSONDecodeError as e:
            logger.error("grouping_parse_failed", error=str(e))
            return [{"theme": "All Motions", "motion_ids": [m.motion_id for m in motions]}]

    async def _synthesize_mega_motion(
        self,
        theme: str,
        motions: list[SourceMotion],
    ) -> MegaMotion:
        """Synthesize a mega-motion from grouped motions."""
        # Collect all unique archons
        all_archons = set()
        for m in motions:
            all_archons.update(m.supporting_archons)
        unique_archons = sorted(list(all_archons))

        # Determine consensus tier
        archon_count = len(unique_archons)
        if archon_count >= 10:
            consensus_tier = "high"
        elif archon_count >= 4:
            consensus_tier = "medium"
        else:
            consensus_tier = "low"

        # Prepare motion texts for synthesis
        motion_texts = "\n\n---\n\n".join(
            f"**{m.title}** (Archons: {', '.join(m.supporting_archons)})\n{m.text[:500]}..."
            for m in motions
        )

        task = Task(
            description=f"""Synthesize these {len(motions)} related motions into ONE comprehensive mega-motion.

THEME: {theme}
SUPPORTING ARCHONS: {', '.join(unique_archons)} ({archon_count} total)

SOURCE MOTIONS:
{motion_texts}

Create a consolidated motion that:
1. Captures the key provisions from all source motions
2. Eliminates redundancy while preserving important nuances
3. Uses formal legislative language
4. Is comprehensive but not longer than necessary

Return JSON:
{{"title": "Mega-Motion: {theme}", "text": "The Conclave hereby...", "rationale": "This mega-motion consolidates..."}}

CRITICAL: Output ONLY valid JSON.""",
            expected_output="JSON mega-motion object",
            agent=self._agent,
        )

        crew = Crew(
            agents=[self._agent],
            tasks=[task],
            verbose=self._verbose,
        )

        result = await asyncio.to_thread(crew.kickoff)
        data = self._parse_mega_motion(str(result), theme, motions)

        return MegaMotion(
            mega_motion_id=uuid4(),
            title=data.get("title", f"Mega-Motion: {theme}"),
            theme=theme,
            consolidated_text=data.get("text", ""),
            rationale=data.get("rationale", f"Consolidates {len(motions)} related motions"),
            source_motion_ids=[m.motion_id for m in motions],
            source_motion_titles=[m.title for m in motions],
            source_cluster_ids=[m.cluster_id for m in motions if m.cluster_id],
            all_supporting_archons=unique_archons,
            unique_archon_count=archon_count,
            consensus_tier=consensus_tier,
        )

    def _parse_mega_motion(
        self,
        result: str,
        theme: str,
        motions: list[SourceMotion],
    ) -> dict:
        """Parse mega-motion synthesis result."""
        cleaned = result.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            logger.warning("no_json_object_in_synthesis", theme=theme)
            # Fallback: combine motion texts
            combined_text = "\n\n".join(m.text[:300] for m in motions)
            return {
                "title": f"Mega-Motion: {theme}",
                "text": combined_text,
                "rationale": f"Combined from {len(motions)} related motions",
            }

        try:
            json_str = cleaned[start:end + 1]
            # Sanitize control characters
            json_str = json_str.replace("\n", "\\n").replace("\t", "\\t")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("synthesis_parse_failed", theme=theme, error=str(e))
            combined_text = "\n\n".join(m.text[:300] for m in motions)
            return {
                "title": f"Mega-Motion: {theme}",
                "text": combined_text,
                "rationale": f"Combined from {len(motions)} related motions",
            }

    def save_results(
        self,
        result: ConsolidationResult,
        output_dir: Path,
    ) -> Path:
        """Save consolidation results to files.

        Args:
            result: ConsolidationResult to save
            output_dir: Directory to save outputs

        Returns:
            Path to output directory
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save mega-motions JSON
        mega_motions_json = output_dir / "mega-motions.json"
        with open(mega_motions_json, "w") as f:
            json.dump(
                [
                    {
                        "mega_motion_id": str(m.mega_motion_id),
                        "title": m.title,
                        "theme": m.theme,
                        "consolidated_text": m.consolidated_text,
                        "rationale": m.rationale,
                        "source_motion_ids": m.source_motion_ids,
                        "source_motion_titles": m.source_motion_titles,
                        "source_cluster_ids": m.source_cluster_ids,
                        "all_supporting_archons": m.all_supporting_archons,
                        "unique_archon_count": m.unique_archon_count,
                        "consensus_tier": m.consensus_tier,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in result.mega_motions
                ],
                f,
                indent=2,
            )

        # Save mega-motions markdown
        mega_motions_md = output_dir / "mega-motions.md"
        with open(mega_motions_md, "w") as f:
            f.write("# Consolidated Mega-Motions\n\n")
            f.write(f"**Original Motions:** {result.original_motion_count}\n")
            f.write(f"**Mega-Motions:** {len(result.mega_motions)}\n")
            f.write(f"**Consolidation Ratio:** {result.consolidation_ratio:.1%}\n")
            f.write(f"**Generated:** {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write("---\n\n")

            for i, mm in enumerate(result.mega_motions, 1):
                f.write(f"## {i}. {mm.title}\n\n")
                f.write(f"**Theme:** {mm.theme}\n")
                f.write(f"**Consensus Tier:** {mm.consensus_tier.upper()}\n")
                f.write(f"**Supporting Archons ({mm.unique_archon_count}):** {', '.join(mm.all_supporting_archons)}\n\n")
                f.write("### Consolidated Motion Text\n\n")
                f.write(f"{mm.consolidated_text}\n\n")
                f.write("### Rationale\n\n")
                f.write(f"{mm.rationale}\n\n")
                f.write("### Source Motions\n\n")
                for title in mm.source_motion_titles:
                    f.write(f"- {title}\n")
                f.write("\n---\n\n")

        # Save traceability matrix
        traceability_md = output_dir / "traceability-matrix.md"
        with open(traceability_md, "w") as f:
            f.write("# Traceability Matrix\n\n")
            f.write("| Mega-Motion | Source Motions | Archon Count | Tier |\n")
            f.write("|-------------|----------------|--------------|------|\n")
            for mm in result.mega_motions:
                f.write(f"| {mm.title[:40]}... | {len(mm.source_motion_ids)} | {mm.unique_archon_count} | {mm.consensus_tier} |\n")

            if result.orphaned_motions:
                f.write("\n## Orphaned Motions\n\n")
                for orphan_id in result.orphaned_motions:
                    f.write(f"- {orphan_id}\n")

        logger.info(
            "consolidation_results_saved",
            output_dir=str(output_dir),
            mega_motions=len(result.mega_motions),
        )

        return output_dir
