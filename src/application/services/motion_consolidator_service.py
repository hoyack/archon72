"""Motion Consolidator Service for sustainable governance.

Consolidates many Motion Seeds into fewer mega-motions while preserving
full traceability to original recommendations and clusters.

This is the HYBRID approach:
- All original data preserved (909 recommendations, 69 Motion Seeds)
- Consolidated mega-motions (from Motion Seeds) for efficient deliberation
- Full audit trail maintained

Additional Analysis:
- Novelty detection: Identify uniquely creative/unconventional proposals
- Conclave summary: Executive overview of deliberation themes
- Acronym registry: Catalog emerging terminology

Constitutional Constraints:
- CT-11: No silent failures - all consolidation decisions logged
- CT-12: Witnessing accountability - every mega-motion traces to sources
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.llm.crewai_llm_factory import create_crewai_llm
from src.domain.models.secretary_agent import load_secretary_config_from_yaml
from src.optional_deps.crewai import LLM, Agent, Crew, Task

logger = get_logger(__name__)


def _sanitize_json_string(text: str) -> str:
    """Sanitize JSON string by escaping control characters inside strings."""
    # Remove markdown code blocks
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1])
        else:
            cleaned = "\n".join(lines[1:])

    # Replace control chars that break JSON
    # This is aggressive but necessary for LLM outputs
    result = []
    in_string = False
    escape_next = False

    for char in cleaned:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\":
            result.append(char)
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if in_string:
            if char == "\n":
                result.append("\\n")
            elif char == "\r":
                result.append("\\r")
            elif char == "\t":
                result.append("\\t")
            elif ord(char) < 32:
                result.append(f"\\u{ord(char):04x}")
            else:
                result.append(char)
        else:
            result.append(char)

    return "".join(result)


def _aggressive_json_clean(text: str) -> str:
    """Aggressively clean JSON for parsing."""
    import re

    cleaned = text.strip()

    # Remove markdown
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1])
        else:
            cleaned = "\n".join(lines[1:])

    # Fix trailing commas before ] or }
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

    # Fix missing quotes around keys
    cleaned = re.sub(r"{\s*(\w+):", r'{"\1":', cleaned)
    cleaned = re.sub(r",\s*(\w+):", r',"\1":', cleaned)

    # Replace unescaped control characters
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", cleaned)

    return cleaned


# Target number of mega-motions
TARGET_MEGA_MOTION_COUNT = 12
# Default concurrency settings (override via env vars).
DEFAULT_SYNTHESIS_CONCURRENCY = 3
DEFAULT_NOVELTY_CONCURRENCY = 2


@dataclass
class SourceMotion:
    """A Motion Seed from the Secretary output."""

    motion_id: str
    title: str
    text: str
    theme: str
    archon_count: int
    supporting_archons: list[str]
    cluster_id: str


@dataclass
class MegaMotion:
    """A consolidated mega-motion combining related Motion Seeds."""

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
    """Result of Motion Seed consolidation."""

    mega_motions: list[MegaMotion]
    original_motion_count: int
    consolidation_ratio: float
    traceability_complete: bool
    orphaned_motions: list[str]  # Should be empty if successful
    merge_audit: list[dict[str, object]] = field(default_factory=list)


@dataclass
class NovelProposal:
    """A uniquely interesting or unconventional proposal."""

    proposal_id: str
    recommendation_id: str
    archon_name: str
    text: str
    novelty_reason: str
    novelty_score: float  # 0-1, higher = more novel
    category: str  # "unconventional", "cross-domain", "minority-insight", "creative"
    keywords: list[str]
    deferred: bool = True
    deferred_reason: str | None = None


@dataclass
class AcronymEntry:
    """A catalogued acronym from the deliberation."""

    acronym: str
    full_form: str
    definition: str
    introduced_by: list[str]  # Archon names
    first_seen_in: str  # recommendation_id or motion_id
    usage_count: int


@dataclass
class ConclaveSummary:
    """Executive summary of the conclave deliberation."""

    session_id: str
    session_name: str
    total_speeches: int
    total_recommendations: int
    total_motions: int
    key_themes: list[str]
    areas_of_consensus: list[str]
    points_of_contention: list[str]
    notable_dynamics: str
    executive_summary: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FullConsolidationResult:
    """Complete result including all analysis vectors."""

    consolidation: ConsolidationResult
    novel_proposals: list[NovelProposal]
    conclave_summary: ConclaveSummary | None
    acronym_registry: list[AcronymEntry]
    session_id: str
    session_name: str


class MotionConsolidatorService:
    """Service to consolidate Motion Seeds into mega-motions.

    Uses LLM to identify thematic groupings and synthesize
    consolidated motion text while preserving traceability.
    """

    def __init__(
        self,
        verbose: bool = False,
        target_count: int = TARGET_MEGA_MOTION_COUNT,
        llm: LLM | object | None = None,
        llm_factory: Callable[[Any], object] | None = None,
    ) -> None:
        """Initialize the consolidator.

        Args:
            verbose: Enable verbose LLM logging
            target_count: Target number of mega-motions to produce
        """
        self._verbose = verbose
        self._target_count = target_count

        if llm is None:
            if llm_factory is None:
                llm_factory = create_crewai_llm
            # Load LLM config from YAML (uses JSON model for structured output)
            _, json_config, _ = load_secretary_config_from_yaml()
            llm = llm_factory(json_config)

        self._llm = llm
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

        # Concurrency controls
        self._synthesis_concurrency = self._resolve_concurrency(
            "CONSOLIDATOR_SYNTH_CONCURRENCY", DEFAULT_SYNTHESIS_CONCURRENCY
        )
        self._novelty_concurrency = self._resolve_concurrency(
            "CONSOLIDATOR_NOVELTY_CONCURRENCY", DEFAULT_NOVELTY_CONCURRENCY
        )

        logger.info(
            "motion_consolidator_initialized",
            target_count=target_count,
            model=getattr(self._llm, "model", None),
        )

    def _resolve_concurrency(self, env_var: str, default: int) -> int:
        """Resolve a bounded concurrency value from env."""
        try:
            raw = os.environ.get(env_var, "")
            value = int(raw) if raw else default
        except ValueError:
            value = default
        return max(1, value)

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

    def load_recommendations_from_checkpoint(self, checkpoint_path: Path) -> list[dict]:
        """Load recommendations from Secretary extraction checkpoint.

        Args:
            checkpoint_path: Path to *_01_extraction.json checkpoint

        Returns:
            List of recommendation dicts
        """
        with open(checkpoint_path) as f:
            data = json.load(f)

        logger.info("recommendations_loaded_from_checkpoint", count=len(data))
        return data

    def extract_session_info_from_checkpoint(
        self, checkpoint_path: Path
    ) -> tuple[str, str]:
        """Extract session ID and name from checkpoint path.

        Args:
            checkpoint_path: Path to any checkpoint file

        Returns:
            Tuple of (session_id, session_name)
        """
        # Checkpoint filename format: {session_id}_{timestamp}_{step}_*.json
        filename = checkpoint_path.stem
        parts = filename.split("_")
        session_id = parts[0] if parts else str(uuid4())

        # Try to find session name from secretary report
        secretary_dir = checkpoint_path.parent.parent / session_id
        report_path = secretary_dir / "secretary-report.json"
        session_name = f"Conclave {session_id[:8]}"

        if report_path.exists():
            with open(report_path) as f:
                report = json.load(f)
                session_name = report.get("source_session_name", session_name)

        return session_id, session_name

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

        # Step 2: Synthesize mega-motions for each group (bounded concurrency)

        semaphore = asyncio.Semaphore(self._synthesis_concurrency)
        results_by_index: dict[int, MegaMotion] = {}

        async def _synthesize_group(idx: int, group: dict) -> None:
            group_motions = [
                m for m in motions if m.motion_id in group.get("motion_ids", [])
            ]
            if not group_motions:
                return
            async with semaphore:
                try:
                    mega_motion = await self._synthesize_mega_motion(
                        theme=group.get("theme", "Unknown"),
                        motions=group_motions,
                    )
                    results_by_index[idx] = mega_motion
                except Exception as exc:
                    logger.warning(
                        "mega_motion_synthesis_failed",
                        theme=group.get("theme", "Unknown"),
                        error=str(exc),
                    )

        tasks = [
            asyncio.create_task(_synthesize_group(idx, group))
            for idx, group in enumerate(groupings)
        ]
        if tasks:
            await asyncio.gather(*tasks)

        mega_motions = [results_by_index[i] for i in sorted(results_by_index)]

        mega_motions, merge_audit = await self._merge_similar_mega_motions(
            mega_motions, motions
        )
        mega_motions = self._dedupe_mega_motion_sources(mega_motions, motions)
        self._apply_emergency_exception_clause(mega_motions)

        # Check for orphaned motions
        all_motion_ids = {m.motion_id for m in motions}
        accounted_motion_ids = {
            mid for mm in mega_motions for mid in mm.source_motion_ids
        }
        orphaned = list(all_motion_ids - accounted_motion_ids)

        if orphaned:
            logger.warning("orphaned_motions_found", count=len(orphaned))

        result = ConsolidationResult(
            mega_motions=mega_motions,
            original_motion_count=len(motions),
            consolidation_ratio=len(mega_motions) / len(motions) if motions else 0,
            traceability_complete=len(orphaned) == 0,
            orphaned_motions=orphaned,
            merge_audit=merge_audit,
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
        """Use LLM to identify thematic groupings.

        For large motion counts (>50), uses batched pre-grouping to avoid
        LLM output truncation.
        """
        # For large motion sets, use batched approach
        if len(motions) > 50:
            return await self._identify_groupings_batched(motions)

        return await self._identify_groupings_single(motions)

    async def _identify_groupings_single(
        self,
        motions: list[SourceMotion],
    ) -> list[dict]:
        """Identify groupings for a manageable number of motions."""
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

INSTRUCTIONS:
1. Create exactly {self._target_count} thematic groups
2. Each motion belongs to exactly ONE group
3. Group by similar topics (ethics, transparency, oversight, etc.)

OUTPUT FORMAT - Return ONLY this JSON structure, nothing else:
[
  {{"theme": "Ethics & Oversight", "motion_ids": ["uuid1", "uuid2"]}},
  {{"theme": "Transparency", "motion_ids": ["uuid3", "uuid4"]}}
]

RULES:
- Output ONLY valid JSON array
- No text before or after the JSON
- Use the exact motion IDs from the input
- Every motion ID must appear exactly once""",
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

    async def _identify_groupings_batched(
        self,
        motions: list[SourceMotion],
    ) -> list[dict]:
        """Identify groupings for large motion sets using batched approach.

        Strategy:
        1. Divide motions into batches of ~30
        2. Ask LLM to identify themes in each batch
        3. Merge themes across batches using keyword matching
        4. Final grouping based on consolidated themes
        """
        batch_size = 30
        batches = [
            motions[i : i + batch_size]
            for i in range(0, len(motions), batch_size)
        ]

        logger.info(
            "batched_grouping_start",
            total_motions=len(motions),
            batch_count=len(batches),
            target_groups=self._target_count,
        )

        # Step 1: Pre-group within each batch
        all_themes: dict[str, list[str]] = {}  # theme -> motion_ids

        for batch_idx, batch in enumerate(batches):
            # Ask LLM to categorize this batch into ~target_count themes
            batch_summaries = json.dumps(
                [
                    {
                        "id": m.motion_id,
                        "title": m.title[:80],
                        "theme": m.theme,
                    }
                    for m in batch
                ],
                indent=2,
            )

            task = Task(
                description=f"""Categorize these {len(batch)} motions into {self._target_count} broad themes.

MOTIONS:
{batch_summaries}

OUTPUT: Return ONLY a JSON array of theme groups:
[{{"theme": "Theme Name", "motion_ids": ["id1", "id2"]}}]

RULES:
- Use broad theme names (e.g., "Attribution", "Security", "Compliance")
- Every motion ID must appear exactly once
- Output ONLY valid JSON, no other text""",
                expected_output="JSON array of theme groups",
                agent=self._agent,
            )

            try:
                crew = Crew(
                    agents=[self._agent],
                    tasks=[task],
                    verbose=self._verbose,
                )
                result = await asyncio.to_thread(crew.kickoff)
                batch_groups = self._parse_groupings(str(result), batch)

                # Merge into all_themes
                for group in batch_groups:
                    theme = group.get("theme", "Unknown")
                    motion_ids = group.get("motion_ids", [])

                    # Normalize theme name for matching
                    theme_key = theme.lower().strip()
                    if theme_key not in all_themes:
                        all_themes[theme_key] = []
                    all_themes[theme_key].extend(motion_ids)

                logger.debug(
                    "batch_grouped",
                    batch=batch_idx + 1,
                    groups=len(batch_groups),
                )

            except Exception as e:
                logger.warning(
                    "batch_grouping_failed",
                    batch=batch_idx + 1,
                    error=str(e),
                )
                # Fallback: assign all motions in batch to "Ungrouped"
                all_themes.setdefault("ungrouped", []).extend(
                    [m.motion_id for m in batch]
                )

        # Step 2: Consolidate similar themes
        consolidated = self._consolidate_themes(all_themes)

        logger.info(
            "batched_grouping_complete",
            raw_themes=len(all_themes),
            consolidated_themes=len(consolidated),
        )

        # Convert to expected format
        return [
            {"theme": theme, "motion_ids": ids}
            for theme, ids in consolidated.items()
        ]

    def _consolidate_themes(
        self,
        themes: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        """Consolidate similar theme names."""
        # Common theme keywords to normalize
        theme_aliases = {
            "attribution": ["attribution", "traceability", "audit", "tracking"],
            "security": ["security", "protection", "compartment", "encrypt"],
            "compliance": ["compliance", "conform", "adherence", "calibrat"],
            "review": ["review", "clause", "safeguard", "feedback"],
            "authority": ["authority", "definition", "scope", "power"],
            "transparency": ["transparent", "accountab", "disclosure", "visib"],
            "governance": ["governance", "oversight", "framework", "protocol"],
            "verification": ["verif", "valid", "confirm", "check"],
        }

        consolidated: dict[str, list[str]] = {}

        for theme, motion_ids in themes.items():
            # Find matching alias group
            matched = False
            for canonical, aliases in theme_aliases.items():
                if any(alias in theme for alias in aliases):
                    if canonical not in consolidated:
                        consolidated[canonical] = []
                    consolidated[canonical].extend(motion_ids)
                    matched = True
                    break

            if not matched:
                # Keep original theme
                if theme not in consolidated:
                    consolidated[theme] = []
                consolidated[theme].extend(motion_ids)

        # If we have too many themes, merge smallest into "Other"
        if len(consolidated) > self._target_count * 2:
            # Sort by motion count
            sorted_themes = sorted(
                consolidated.items(), key=lambda x: len(x[1]), reverse=True
            )
            # Keep top themes, merge rest into "other"
            final: dict[str, list[str]] = {}
            for i, (theme, ids) in enumerate(sorted_themes):
                if i < self._target_count:
                    final[theme] = ids
                else:
                    if "other" not in final:
                        final["other"] = []
                    final["other"].extend(ids)
            return final

        return consolidated

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
            cleaned = (
                "\n".join(lines[1:-1])
                if lines[-1].startswith("```")
                else "\n".join(lines[1:])
            )

        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1:
            logger.error("no_json_array_in_groupings", raw=result[:200])
            # Fallback: single group with all motions
            return [
                {"theme": "All Motions", "motion_ids": [m.motion_id for m in motions]}
            ]

        json_str = cleaned[start : end + 1]

        # Try multiple parsing strategies
        data = None
        for attempt, parser in enumerate(
            [
                lambda s: json.loads(s),
                lambda s: json.loads(_sanitize_json_string(s)),
                lambda s: json.loads(_aggressive_json_clean(s)),
            ]
        ):
            try:
                data = parser(json_str)
                if attempt > 0:
                    logger.debug("grouping_parse_succeeded", attempt=attempt + 1)
                break
            except json.JSONDecodeError:
                continue

        if data is None:
            logger.error("grouping_parse_failed_all_attempts", raw=json_str[:300])
            return [
                {"theme": "All Motions", "motion_ids": [m.motion_id for m in motions]}
            ]

        # Normalize groups: remove duplicates across groups and ensure coverage
        all_ids = {m.motion_id for m in motions}
        seen: set[str] = set()
        normalized: list[dict] = []

        for group in data:
            raw_ids = group.get("motion_ids", [])
            unique_ids = []
            for mid in raw_ids:
                if mid in all_ids and mid not in seen:
                    seen.add(mid)
                    unique_ids.append(mid)
            if unique_ids:
                normalized.append(
                    {"theme": group.get("theme", "Other"), "motion_ids": unique_ids}
                )

        missing = all_ids - seen
        if missing:
            logger.warning("motions_missing_from_groups", count=len(missing))
            # Add missing to last group or create "Other" group
            if normalized:
                normalized[-1]["motion_ids"].extend(sorted(missing))
            else:
                normalized.append({"theme": "Other", "motion_ids": sorted(missing)})

        return normalized

    async def _merge_similar_mega_motions(
        self,
        mega_motions: list[MegaMotion],
        motions: list[SourceMotion],
    ) -> tuple[list[MegaMotion], list[dict[str, object]]]:
        """Merge overlapping mega-motions using deterministic similarity rules."""
        if len(mega_motions) < 2:
            return mega_motions, []

        motion_lookup = {m.motion_id: m for m in motions}

        def _tokenize(text: str) -> set[str]:
            cleaned = re.sub(r"[^a-z0-9\\s]", " ", text.lower())
            tokens = [t for t in cleaned.split() if t and len(t) > 2]
            stopwords = {
                "mega",
                "motion",
                "comprehensive",
                "the",
                "and",
                "for",
                "of",
                "to",
                "on",
                "with",
                "into",
            }
            return {t for t in tokens if t not in stopwords}

        def _jaccard(a: set[str], b: set[str]) -> float:
            if not a or not b:
                return 0.0
            return len(a & b) / len(a | b)

        tokens_by_id = {
            mm.mega_motion_id: _tokenize(f"{mm.title} {mm.theme}")
            for mm in mega_motions
        }
        mm_by_id = {mm.mega_motion_id: mm for mm in mega_motions}

        adjacency: dict[UUID, set[UUID]] = {
            mm.mega_motion_id: set() for mm in mega_motions
        }
        pair_audit: list[dict[str, object]] = []

        ids = list(tokens_by_id.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_a = ids[i]
                id_b = ids[j]
                mm_a = mm_by_id[id_a]
                mm_b = mm_by_id[id_b]
                tokens_a = tokens_by_id[id_a]
                tokens_b = tokens_by_id[id_b]
                score = _jaccard(tokens_a, tokens_b)

                reason = None
                if mm_a.theme.lower() == mm_b.theme.lower():
                    reason = "theme_match"
                elif (
                    {"framework", "governance"} <= tokens_a
                    and {"framework", "governance"} <= tokens_b
                    and score >= 0.3
                ):
                    reason = "framework_governance_overlap"
                elif score >= 0.5:
                    reason = "token_jaccard"

                if reason:
                    adjacency[id_a].add(id_b)
                    adjacency[id_b].add(id_a)
                    pair_audit.append(
                        {
                            "id_a": str(id_a),
                            "id_b": str(id_b),
                            "title_a": mm_a.title,
                            "title_b": mm_b.title,
                            "theme_a": mm_a.theme,
                            "theme_b": mm_b.theme,
                            "similarity": round(score, 3),
                            "reason": reason,
                        }
                    )

        if not pair_audit:
            return mega_motions, []

        visited: set[UUID] = set()
        merged: list[MegaMotion] = []
        merge_audit: list[dict[str, object]] = []

        for mm_id in ids:
            if mm_id in visited:
                continue
            stack = [mm_id]
            component: set[UUID] = set()
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                stack.extend(adjacency[current] - visited)

            if len(component) == 1:
                merged.append(mm_by_id[mm_id])
                continue

            component_mms = [mm_by_id[cid] for cid in component]
            primary = sorted(
                component_mms,
                key=lambda m: (m.unique_archon_count, len(m.source_motion_ids)),
                reverse=True,
            )[0]
            source_ids = {
                motion_id for mm in component_mms for motion_id in mm.source_motion_ids
            }
            source_motions = [
                motion_lookup[motion_id]
                for motion_id in source_ids
                if motion_id in motion_lookup
            ]
            if not source_motions:
                logger.warning(
                    "mega_motion_merge_failed_no_sources",
                    mega_motion_ids=[str(m.mega_motion_id) for m in component_mms],
                )
                merged.extend(component_mms)
                continue

            merged_mm = await self._synthesize_mega_motion(
                theme=primary.theme,
                motions=source_motions,
            )
            merged.append(merged_mm)

            merge_audit.append(
                {
                    "merged_into_theme": primary.theme,
                    "merged_mega_motion_ids": [
                        str(m.mega_motion_id) for m in component_mms
                    ],
                    "merged_titles": [m.title for m in component_mms],
                    "source_motion_ids": sorted(source_ids),
                    "pairwise_matches": [
                        p
                        for p in pair_audit
                        if p["id_a"] in {str(m.mega_motion_id) for m in component_mms}
                        and p["id_b"] in {str(m.mega_motion_id) for m in component_mms}
                    ],
                }
            )

        if merge_audit:
            logger.info(
                "mega_motion_merge_completed",
                original_count=len(mega_motions),
                merged_count=len(merged),
                merge_groups=len(merge_audit),
            )

        return merged, merge_audit

    def _dedupe_mega_motion_sources(
        self,
        mega_motions: list[MegaMotion],
        motions: list[SourceMotion],
    ) -> list[MegaMotion]:
        """Ensure each source motion appears in only one mega-motion."""
        motion_lookup = {m.motion_id: m for m in motions}
        seen: set[str] = set()
        deduped: list[MegaMotion] = []

        for mm in mega_motions:
            retained_ids: list[str] = []
            retained_titles: list[str] = []
            retained_cluster_ids: list[str] = []
            supporting_archons: set[str] = set()

            for mid in mm.source_motion_ids:
                if mid in seen:
                    continue
                motion = motion_lookup.get(mid)
                if not motion:
                    continue
                seen.add(mid)
                retained_ids.append(mid)
                retained_titles.append(motion.title)
                if motion.cluster_id:
                    retained_cluster_ids.append(motion.cluster_id)
                supporting_archons.update(motion.supporting_archons)

            if not retained_ids:
                logger.warning(
                    "mega_motion_dropped_no_unique_sources",
                    mega_motion_id=str(mm.mega_motion_id),
                    title=mm.title,
                )
                continue

            mm.source_motion_ids = retained_ids
            mm.source_motion_titles = retained_titles
            mm.source_cluster_ids = retained_cluster_ids
            mm.all_supporting_archons = sorted(supporting_archons)
            mm.unique_archon_count = len(mm.all_supporting_archons)
            if mm.unique_archon_count >= 10:
                mm.consensus_tier = "high"
            elif mm.unique_archon_count >= 4:
                mm.consensus_tier = "medium"
            else:
                mm.consensus_tier = "low"

            deduped.append(mm)

        return deduped

    def _apply_emergency_exception_clause(
        self, mega_motions: list[MegaMotion]
    ) -> None:
        """Add explicit emergency exception when post-hoc limits exist."""
        emergency_keywords = ("emergency", "exemption", "contingency")
        emergency_present = any(
            any(
                k in f"{mm.title} {mm.theme} {mm.consolidated_text}".lower()
                for k in emergency_keywords
            )
            for mm in mega_motions
        )
        if not emergency_present:
            return

        clause = (
            "EMERGENCY EXCEPTION: When an Emergency/Exemption protocol explicitly "
            "requires post-hoc documentation, that documentation is permitted solely "
            "to record the exception and does not retroactively legitimize non-emergency actions."
        )

        for mm in mega_motions:
            combined = f"{mm.title}\n{mm.theme}\n{mm.consolidated_text}".lower()
            if ("post-hoc" in combined or "post hoc" in combined) and "justif" in combined:
                if "emergency exception" in combined:
                    continue
                mm.consolidated_text = mm.consolidated_text.rstrip() + "\n\n" + clause

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
SUPPORTING ARCHONS: {", ".join(unique_archons)} ({archon_count} total)

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
            rationale=data.get(
                "rationale", f"Consolidates {len(motions)} related motions"
            ),
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
            cleaned = (
                "\n".join(lines[1:-1])
                if lines[-1].startswith("```")
                else "\n".join(lines[1:])
            )

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

        json_str = cleaned[start : end + 1]

        # Try multiple parsing strategies
        for attempt, parser in enumerate(
            [
                lambda s: json.loads(s),
                lambda s: json.loads(_sanitize_json_string(s)),
                lambda s: json.loads(_aggressive_json_clean(s)),
            ]
        ):
            try:
                data = parser(json_str)
                if attempt > 0:
                    logger.debug(
                        "synthesis_parse_succeeded", theme=theme, attempt=attempt + 1
                    )
                return data
            except json.JSONDecodeError:
                continue

        # All attempts failed - use fallback
        logger.warning(
            "synthesis_parse_failed_all_attempts", theme=theme, raw=json_str[:200]
        )
        combined_text = "\n\n".join(m.text[:300] for m in motions)
        return {
            "title": f"Mega-Motion: {theme}",
            "text": combined_text,
            "rationale": f"Combined from {len(motions)} related motions",
        }

    async def detect_novel_proposals(
        self,
        recommendations: list[dict],
        top_n: int = 15,
    ) -> list[NovelProposal]:
        """Identify uniquely interesting or unconventional proposals.

        Scans all recommendations to find creative, minority, or
        cross-domain insights that deserve special attention.

        Args:
            recommendations: List of recommendation dicts from extraction
            top_n: Maximum number of novel proposals to return

        Returns:
            List of NovelProposal objects
        """
        logger.info(
            "novelty_detection_start", recommendation_count=len(recommendations)
        )

        # Prepare summaries for LLM - batch in chunks to avoid token limits
        batch_size = 100
        batches = [
            (batch_start, recommendations[batch_start : batch_start + batch_size])
            for batch_start in range(0, len(recommendations), batch_size)
        ]

        semaphore = asyncio.Semaphore(self._novelty_concurrency)
        results_by_batch: dict[int, list[NovelProposal]] = {}

        async def _process_batch(batch_index: int, batch_start: int, batch: list[dict]):
            batch_summaries = json.dumps(
                [
                    {
                        "id": r.get("recommendation_id", ""),
                        "archon": r.get("source", {}).get("archon_name", "Unknown"),
                        "text": r.get(
                            "summary", r.get("source", {}).get("raw_text", "")
                        )[:300],
                        "keywords": r.get("keywords", [])[:5],
                    }
                    for r in batch
                ],
                indent=2,
            )

            task = Task(
                description=f"""Analyze these {len(batch)} recommendations and identify the TOP 5 most NOVEL, CREATIVE, or UNCONVENTIONAL proposals.

RECOMMENDATIONS (batch {batch_index + 1}):
{batch_summaries}

Look for proposals that are:
1. UNCONVENTIONAL: Challenge mainstream thinking or propose unusual approaches
2. CROSS-DOMAIN: Synthesize ideas from different fields in creative ways
3. MINORITY-INSIGHT: Unique perspectives not echoed by others
4. CREATIVE: Innovative mechanisms, novel frameworks, or unexpected solutions

Return ONLY a JSON array with the top 5 most novel proposals:
[
  {{
    "recommendation_id": "uuid",
    "text_excerpt": "EXACT excerpt copied verbatim from the recommendation text",
    "novelty_reason": "Why this is novel/interesting",
    "novelty_score": 0.85,
    "category": "unconventional"
  }}
]

RULES:
- novelty_score: 0.0 to 1.0 (higher = more novel)
- category: one of "unconventional", "cross-domain", "minority-insight", "creative"
- Only include truly standout proposals, not generic ones
- text_excerpt MUST be copied verbatim from the recommendation text provided (no paraphrase)
- Output ONLY valid JSON""",
                expected_output="JSON array of novel proposals",
                agent=self._agent,
            )

            crew = Crew(
                agents=[self._agent],
                tasks=[task],
                verbose=self._verbose,
            )

            async with semaphore:
                result = await asyncio.to_thread(crew.kickoff)
                results_by_batch[batch_index] = self._parse_novel_proposals(
                    str(result), batch
                )

        tasks = [
            asyncio.create_task(_process_batch(i, start, batch))
            for i, (start, batch) in enumerate(batches)
        ]
        if tasks:
            await asyncio.gather(*tasks)

        all_novel: list[NovelProposal] = []
        for i in range(len(batches)):
            all_novel.extend(results_by_batch.get(i, []))

        # Sort by novelty score and take top N
        all_novel.sort(key=lambda x: x.novelty_score, reverse=True)
        final_novel = all_novel[:top_n]

        logger.info(
            "novelty_detection_complete",
            candidates_found=len(all_novel),
            top_n_selected=len(final_novel),
        )

        return final_novel

    def _parse_novel_proposals(
        self,
        result: str,
        recommendations: list[dict],
    ) -> list[NovelProposal]:
        """Parse novelty detection result."""
        cleaned = result.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = (
                "\n".join(lines[1:-1])
                if lines[-1].startswith("```")
                else "\n".join(lines[1:])
            )

        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1:
            logger.warning("no_json_array_in_novelty_result")
            return []

        json_str = cleaned[start : end + 1]

        # Try multiple parsing strategies
        data = None
        for parser in [
            lambda s: json.loads(s),
            lambda s: json.loads(_sanitize_json_string(s)),
            lambda s: json.loads(_aggressive_json_clean(s)),
        ]:
            try:
                data = parser(json_str)
                break
            except json.JSONDecodeError:
                continue

        if data is None:
            logger.warning("novelty_parse_failed")
            return []

        # Build lookup for recommendations
        rec_lookup = {r.get("recommendation_id", ""): r for r in recommendations}

        proposals = []
        for item in data:
            rec_id = item.get("recommendation_id", "")
            rec = rec_lookup.get(rec_id, {})

            if not rec:
                continue

            source_text = rec.get("summary", rec.get("source", {}).get("raw_text", ""))
            excerpt = (item.get("text_excerpt") or "").strip()
            match_ok = False
            if excerpt:
                if excerpt in source_text or source_text in excerpt:
                    match_ok = True

            if match_ok:
                text = excerpt
                novelty_reason = item.get("novelty_reason", "")
                novelty_score = float(item.get("novelty_score", 0.5))
                category = item.get("category", "creative")
                deferred_reason = "Deferred for later review"
            else:
                text = source_text
                novelty_reason = (
                    "DEFERRED: LLM excerpt did not match recommendation text."
                )
                novelty_score = 0.0
                category = "deferred"
                deferred_reason = "Excerpt mismatch"

            proposals.append(
                NovelProposal(
                    proposal_id=str(uuid4()),
                    recommendation_id=rec_id,
                    archon_name=rec.get("source", {}).get("archon_name", "Unknown"),
                    text=text,
                    novelty_reason=novelty_reason,
                    novelty_score=novelty_score,
                    category=category,
                    keywords=rec.get("keywords", []),
                    deferred=True,
                    deferred_reason=deferred_reason,
                )
            )

        return proposals

    async def generate_conclave_summary(
        self,
        recommendations: list[dict],
        motions: list[SourceMotion],
        session_id: str,
        session_name: str,
    ) -> ConclaveSummary:
        """Generate executive summary of the conclave deliberation.

        Args:
            recommendations: All extracted recommendations
            motions: Consolidated motions
            session_id: Conclave session ID
            session_name: Conclave session name

        Returns:
            ConclaveSummary object
        """
        logger.info("conclave_summary_start", session_id=session_id)

        # Collect unique archons and themes
        archon_counts: dict[str, int] = {}
        for rec in recommendations:
            archon = rec.get("source", {}).get("archon_name", "Unknown")
            archon_counts[archon] = archon_counts.get(archon, 0) + 1

        motion_themes = [m.theme for m in motions]
        total_speeches = len(
            set(rec.get("source", {}).get("archon_name", "") for rec in recommendations)
        )

        # Sample recommendations for LLM summary
        sample_size = min(50, len(recommendations))
        sample_recs = recommendations[:sample_size]
        sample_text = "\n".join(
            f"- {r.get('source', {}).get('archon_name', 'Unknown')}: {r.get('summary', '')[:150]}"
            for r in sample_recs
        )

        task = Task(
            description=f"""Generate an executive summary of this Conclave deliberation.

SESSION: {session_name} ({session_id})
STATISTICS:
- Total Recommendations: {len(recommendations)}
- Total Motion Seeds Generated: {len(motions)}
- Participating Archons: {len(archon_counts)}
- Motion Seed Themes: {", ".join(list(set(motion_themes))[:10])}

SAMPLE RECOMMENDATIONS:
{sample_text}

Generate a comprehensive summary with:
1. key_themes: List of 5-7 main themes discussed
2. areas_of_consensus: List of 3-5 areas where multiple Archons agreed
3. points_of_contention: List of 2-4 areas of disagreement or debate
4. notable_dynamics: One paragraph on interesting patterns or dynamics
5. executive_summary: 2-3 paragraph overview of the deliberation

Return JSON:
{{
  "key_themes": ["theme1", "theme2"],
  "areas_of_consensus": ["consensus1", "consensus2"],
  "points_of_contention": ["contention1", "contention2"],
  "notable_dynamics": "Paragraph describing dynamics...",
  "executive_summary": "Full summary..."
}}

CRITICAL: Output ONLY valid JSON.""",
            expected_output="JSON summary object",
            agent=self._agent,
        )

        crew = Crew(
            agents=[self._agent],
            tasks=[task],
            verbose=self._verbose,
        )

        result = await asyncio.to_thread(crew.kickoff)
        data = self._parse_summary(str(result))

        summary = ConclaveSummary(
            session_id=session_id,
            session_name=session_name,
            total_speeches=total_speeches,
            total_recommendations=len(recommendations),
            total_motions=len(motions),
            key_themes=data.get("key_themes", motion_themes[:7]),
            areas_of_consensus=data.get("areas_of_consensus", []),
            points_of_contention=data.get("points_of_contention", []),
            notable_dynamics=data.get("notable_dynamics", ""),
            executive_summary=data.get("executive_summary", ""),
        )

        logger.info("conclave_summary_complete", session_id=session_id)
        return summary

    def _parse_summary(self, result: str) -> dict:
        """Parse conclave summary result."""
        cleaned = result.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = (
                "\n".join(lines[1:-1])
                if lines[-1].startswith("```")
                else "\n".join(lines[1:])
            )

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            logger.warning("no_json_object_in_summary")
            return {}

        json_str = cleaned[start : end + 1]

        for parser in [
            lambda s: json.loads(s),
            lambda s: json.loads(_sanitize_json_string(s)),
            lambda s: json.loads(_aggressive_json_clean(s)),
        ]:
            try:
                return parser(json_str)
            except json.JSONDecodeError:
                continue

        logger.warning("summary_parse_failed")
        return {}

    def extract_acronyms(
        self,
        recommendations: list[dict],
        motions: list[SourceMotion],
    ) -> list[AcronymEntry]:
        """Extract and catalog acronyms from deliberation content.

        Uses regex to find uppercase acronyms and attempts to infer
        meanings from context.

        Args:
            recommendations: All recommendations
            motions: All motions

        Returns:
            List of AcronymEntry objects
        """
        logger.info("acronym_extraction_start")

        # Pattern for acronyms: 2-6 uppercase letters, optionally with numbers
        acronym_pattern = re.compile(r"\b([A-Z]{2,6})\b")

        # Common acronyms to exclude (not domain-specific)
        exclude = {
            "AI",
            "ML",
            "LLM",
            "API",
            "EU",
            "US",
            "UK",
            "UN",
            "CEO",
            "CTO",
            "GDP",
            "ROI",
            "KPI",
            "FAQ",
            "PDF",
            "JSON",
            "XML",
            "HTML",
            "CSS",
            "HTTP",
            "SQL",
            "AWS",
            "GCP",
            "FOR",
            "AND",
            "THE",
            "BUT",
            "NOT",
        }

        # Collect acronyms with context
        acronym_data: dict[str, dict] = {}

        # Scan recommendations
        for rec in recommendations:
            text = (
                rec.get("summary", "") + " " + rec.get("source", {}).get("raw_text", "")
            )
            archon = rec.get("source", {}).get("archon_name", "Unknown")
            rec_id = rec.get("recommendation_id", "")

            for match in acronym_pattern.finditer(text):
                acronym = match.group(1)
                if acronym in exclude:
                    continue

                if acronym not in acronym_data:
                    acronym_data[acronym] = {
                        "count": 0,
                        "archons": set(),
                        "first_seen": rec_id,
                        "contexts": [],
                    }

                acronym_data[acronym]["count"] += 1
                acronym_data[acronym]["archons"].add(archon)
                # Store context (text around acronym)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()
                if len(acronym_data[acronym]["contexts"]) < 3:
                    acronym_data[acronym]["contexts"].append(context)

        # Scan motions
        for motion in motions:
            text = motion.title + " " + motion.text
            for match in acronym_pattern.finditer(text):
                acronym = match.group(1)
                if acronym in exclude or acronym not in acronym_data:
                    continue
                acronym_data[acronym]["count"] += 1

        # Convert to AcronymEntry objects
        entries = []
        for acronym, data in acronym_data.items():
            if data["count"] < 2:  # Only include if used more than once
                continue

            # Try to infer meaning from context
            contexts = data["contexts"]
            definition = self._infer_acronym_meaning(acronym, contexts)

            entries.append(
                AcronymEntry(
                    acronym=acronym,
                    full_form=definition.get("full_form", f"[{acronym}]"),
                    definition=definition.get("definition", "Meaning not determined"),
                    introduced_by=sorted(list(data["archons"])),
                    first_seen_in=data["first_seen"],
                    usage_count=data["count"],
                )
            )

        # Sort by usage count
        entries.sort(key=lambda x: x.usage_count, reverse=True)

        logger.info("acronym_extraction_complete", acronyms_found=len(entries))
        return entries

    def _infer_acronym_meaning(self, acronym: str, contexts: list[str]) -> dict:
        """Attempt to infer acronym meaning from context."""
        # Look for patterns like "ACRONYM (Full Form)" or "Full Form (ACRONYM)"
        for context in contexts:
            # Pattern: ACRONYM (Full Form)
            pattern1 = re.compile(rf"{acronym}\s*\(([^)]+)\)", re.IGNORECASE)
            match = pattern1.search(context)
            if match:
                full_form = match.group(1).strip()
                return {"full_form": full_form, "definition": full_form}

            # Pattern: Full Form (ACRONYM)
            pattern2 = re.compile(rf"([A-Z][^(]+)\s*\({acronym}\)", re.IGNORECASE)
            match = pattern2.search(context)
            if match:
                full_form = match.group(1).strip()
                return {"full_form": full_form, "definition": full_form}

        # If no expansion found, return placeholder
        return {
            "full_form": f"[{acronym}]",
            "definition": "Expansion not found in context",
        }

    async def consolidate_full(
        self,
        motions_checkpoint: Path,
        recommendations_checkpoint: Path | None = None,
        run_novelty: bool = True,
        run_summary: bool = True,
        run_acronyms: bool = True,
    ) -> FullConsolidationResult:
        """Run full consolidation with all analysis vectors.

        Args:
            motions_checkpoint: Path to motions checkpoint
            recommendations_checkpoint: Path to recommendations checkpoint (auto-detected if None)
            run_novelty: Whether to run novelty detection
            run_summary: Whether to generate conclave summary
            run_acronyms: Whether to extract acronyms

        Returns:
            FullConsolidationResult with all analysis
        """
        # Extract session info
        session_id, session_name = self.extract_session_info_from_checkpoint(
            motions_checkpoint
        )
        logger.info("full_consolidation_start", session_id=session_id)

        # Auto-detect recommendations checkpoint if not provided
        if recommendations_checkpoint is None:
            # Replace _05_motions with _01_extraction
            checkpoint_name = motions_checkpoint.name.replace(
                "_05_motions", "_01_extraction"
            )
            recommendations_checkpoint = motions_checkpoint.parent / checkpoint_name

        # Load data
        motions = self.load_motions_from_checkpoint(motions_checkpoint)
        recommendations = []
        if recommendations_checkpoint.exists():
            recommendations = self.load_recommendations_from_checkpoint(
                recommendations_checkpoint
            )

        # Run consolidation
        consolidation_result = await self.consolidate(motions)

        # Run novelty detection
        novel_proposals = []
        if run_novelty and recommendations:
            novel_proposals = await self.detect_novel_proposals(recommendations)

        # Generate summary
        summary = None
        if run_summary and recommendations:
            summary = await self.generate_conclave_summary(
                recommendations, motions, session_id, session_name
            )

        # Extract acronyms
        acronyms = []
        if run_acronyms:
            acronyms = self.extract_acronyms(recommendations, motions)

        result = FullConsolidationResult(
            consolidation=consolidation_result,
            novel_proposals=novel_proposals,
            conclave_summary=summary,
            acronym_registry=acronyms,
            session_id=session_id,
            session_name=session_name,
        )

        logger.info(
            "full_consolidation_complete",
            session_id=session_id,
            mega_motions=len(consolidation_result.mega_motions),
            novel_proposals=len(novel_proposals),
            acronyms=len(acronyms),
        )

        return result

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

        # Save merge audit if available
        if result.merge_audit:
            merge_audit_path = output_dir / "merge-audit.json"
            with open(merge_audit_path, "w") as f:
                json.dump(result.merge_audit, f, indent=2)

        # Save mega-motions markdown
        mega_motions_md = output_dir / "mega-motions.md"
        with open(mega_motions_md, "w") as f:
            f.write("# Consolidated Mega-Motions\n\n")
            f.write(f"**Original Motion Seeds:** {result.original_motion_count}\n")
            f.write(f"**Mega-Motions:** {len(result.mega_motions)}\n")
            f.write(f"**Consolidation Ratio:** {result.consolidation_ratio:.1%}\n")
            f.write(f"**Generated:** {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write("---\n\n")

            for i, mm in enumerate(result.mega_motions, 1):
                f.write(f"## {i}. {mm.title}\n\n")
                f.write(f"**Theme:** {mm.theme}\n")
                f.write(f"**Consensus Tier:** {mm.consensus_tier.upper()}\n")
                f.write(
                    f"**Supporting Archons ({mm.unique_archon_count}):** {', '.join(mm.all_supporting_archons)}\n\n"
                )
                f.write("### Consolidated Motion Seed Text\n\n")
                f.write(f"{mm.consolidated_text}\n\n")
                f.write("### Rationale\n\n")
                f.write(f"{mm.rationale}\n\n")
                f.write("### Source Motion Seeds\n\n")
                for title in mm.source_motion_titles:
                    f.write(f"- {title}\n")
                f.write("\n---\n\n")

        # Save traceability matrix
        traceability_md = output_dir / "traceability-matrix.md"
        with open(traceability_md, "w") as f:
            f.write("# Traceability Matrix\n\n")
            f.write("| Mega-Motion | Source Motion Seeds | Archon Count | Tier |\n")
            f.write("|-------------|----------------|--------------|------|\n")
            for mm in result.mega_motions:
                f.write(
                    f"| {mm.title[:40]}... | {len(mm.source_motion_ids)} | {mm.unique_archon_count} | {mm.consensus_tier} |\n"
                )

            if result.orphaned_motions:
                f.write("\n## Orphaned Motion Seeds\n\n")
                for orphan_id in result.orphaned_motions:
                    f.write(f"- {orphan_id}\n")

        logger.info(
            "consolidation_results_saved",
            output_dir=str(output_dir),
            mega_motions=len(result.mega_motions),
        )

        return output_dir

    def save_full_results(
        self,
        result: FullConsolidationResult,
        base_output_dir: Path,
    ) -> Path:
        """Save full consolidation results to session-organized directory.

        Args:
            result: FullConsolidationResult to save
            base_output_dir: Base directory (e.g., _bmad-output/consolidator)

        Returns:
            Path to session output directory
        """
        # Create session-based directory structure
        session_dir = base_output_dir / result.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save basic consolidation results
        self.save_results(result.consolidation, session_dir)

        # Save novel proposals
        if result.novel_proposals:
            self._save_novel_proposals(result.novel_proposals, session_dir)

        # Save conclave summary
        if result.conclave_summary:
            self._save_conclave_summary(result.conclave_summary, session_dir)

        # Save acronym registry
        if result.acronym_registry:
            self._save_acronym_registry(result.acronym_registry, session_dir)

        # Cleanup legacy/stale artifacts from previous runs
        self._cleanup_legacy_files(result, session_dir)

        # Save master index
        self._save_master_index(result, session_dir)

        logger.info(
            "full_results_saved",
            session_id=result.session_id,
            output_dir=str(session_dir),
        )

        return session_dir

    def _cleanup_legacy_files(
        self,
        result: FullConsolidationResult,
        output_dir: Path,
    ) -> None:
        """Remove legacy or stale artifacts from prior runs."""
        legacy_paths = [
            output_dir / "novel-proposals.json",
            output_dir / "novel-proposals.md",
        ]
        for path in legacy_paths:
            if path.exists():
                path.unlink()
                logger.info("legacy_output_removed", file=str(path))

        # Remove stale merge audit if not produced this run
        if not result.consolidation.merge_audit:
            merge_audit = output_dir / "merge-audit.json"
            if merge_audit.exists():
                merge_audit.unlink()
                logger.info("stale_output_removed", file=str(merge_audit))

    def _save_novel_proposals(
        self,
        proposals: list[NovelProposal],
        output_dir: Path,
    ) -> None:
        """Save novel proposals to files."""
        # JSON
        novel_json = output_dir / "deferred-novel-proposals.json"
        with open(novel_json, "w") as f:
            json.dump(
                [
                    {
                        "proposal_id": p.proposal_id,
                        "recommendation_id": p.recommendation_id,
                        "archon_name": p.archon_name,
                        "text": p.text,
                        "novelty_reason": p.novelty_reason,
                        "novelty_score": p.novelty_score,
                        "category": p.category,
                        "keywords": p.keywords,
                        "deferred": p.deferred,
                        "deferred_reason": p.deferred_reason,
                    }
                    for p in proposals
                ],
                f,
                indent=2,
            )

        # Markdown
        novel_md = output_dir / "deferred-novel-proposals.md"
        with open(novel_md, "w") as f:
            f.write("# Deferred Novel & Unconventional Proposals\n\n")
            f.write(
                "*Set aside for later review; not included in consolidation outputs.*\n\n"
            )
            f.write("---\n\n")

            for i, p in enumerate(proposals, 1):
                score_bar = "█" * int(p.novelty_score * 10) + "░" * (
                    10 - int(p.novelty_score * 10)
                )
                f.write(f"## {i}. {p.category.upper()} Proposal\n\n")
                f.write(f"**Archon:** {p.archon_name}\n")
                f.write(f"**Novelty Score:** {score_bar} ({p.novelty_score:.0%})\n")
                f.write(f"**Category:** {p.category}\n\n")
                f.write("### Proposal\n\n")
                f.write(f"> {p.text}\n\n")
                f.write("### Why It's Interesting\n\n")
                f.write(f"{p.novelty_reason}\n\n")
                if p.deferred_reason:
                    f.write(f"**Deferred Reason:** {p.deferred_reason}\n\n")
                if p.keywords:
                    f.write(f"**Keywords:** {', '.join(p.keywords)}\n\n")
                f.write("---\n\n")

    def _save_conclave_summary(
        self,
        summary: ConclaveSummary,
        output_dir: Path,
    ) -> None:
        """Save conclave summary to files."""
        # JSON
        summary_json = output_dir / "conclave-summary.json"
        with open(summary_json, "w") as f:
            json.dump(
                {
                    "session_id": summary.session_id,
                    "session_name": summary.session_name,
                    "total_speeches": summary.total_speeches,
                    "total_recommendations": summary.total_recommendations,
                    "total_motions": summary.total_motions,
                    "key_themes": summary.key_themes,
                    "areas_of_consensus": summary.areas_of_consensus,
                    "points_of_contention": summary.points_of_contention,
                    "notable_dynamics": summary.notable_dynamics,
                    "executive_summary": summary.executive_summary,
                    "generated_at": summary.generated_at.isoformat(),
                },
                f,
                indent=2,
            )

        # Markdown
        summary_md = output_dir / "conclave-summary.md"
        with open(summary_md, "w") as f:
            f.write(f"# Conclave Summary: {summary.session_name}\n\n")
            f.write(f"**Session ID:** `{summary.session_id}`\n")
            f.write(f"**Generated:** {summary.generated_at.isoformat()}\n\n")
            f.write("---\n\n")

            f.write("## Statistics\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Participating Archons | {summary.total_speeches} |\n")
            f.write(f"| Total Recommendations | {summary.total_recommendations} |\n")
            f.write(f"| Motion Seeds Generated | {summary.total_motions} |\n\n")

            f.write("## Executive Summary\n\n")
            f.write(f"{summary.executive_summary}\n\n")

            f.write("## Key Themes\n\n")
            for theme in summary.key_themes:
                f.write(f"- {theme}\n")
            f.write("\n")

            f.write("## Areas of Consensus\n\n")
            for consensus in summary.areas_of_consensus:
                f.write(f"- ✅ {consensus}\n")
            f.write("\n")

            if summary.points_of_contention:
                f.write("## Points of Contention\n\n")
                for contention in summary.points_of_contention:
                    f.write(f"- ⚠️ {contention}\n")
                f.write("\n")

            if summary.notable_dynamics:
                f.write("## Notable Dynamics\n\n")
                f.write(f"{summary.notable_dynamics}\n\n")

    def _save_acronym_registry(
        self,
        acronyms: list[AcronymEntry],
        output_dir: Path,
    ) -> None:
        """Save acronym registry to files."""
        # JSON
        acronym_json = output_dir / "acronym-registry.json"
        with open(acronym_json, "w") as f:
            json.dump(
                [
                    {
                        "acronym": a.acronym,
                        "full_form": a.full_form,
                        "definition": a.definition,
                        "introduced_by": a.introduced_by,
                        "first_seen_in": a.first_seen_in,
                        "usage_count": a.usage_count,
                    }
                    for a in acronyms
                ],
                f,
                indent=2,
            )

        # Markdown
        acronym_md = output_dir / "acronym-registry.md"
        with open(acronym_md, "w") as f:
            f.write("# Acronym Registry\n\n")
            f.write("*Terminology emerging from Conclave deliberations.*\n\n")
            f.write("---\n\n")

            f.write("| Acronym | Full Form | Usage | Introduced By |\n")
            f.write("|---------|-----------|-------|---------------|\n")
            for a in acronyms:
                archons = ", ".join(a.introduced_by[:3])
                if len(a.introduced_by) > 3:
                    archons += f" (+{len(a.introduced_by) - 3})"
                f.write(
                    f"| **{a.acronym}** | {a.full_form} | {a.usage_count}x | {archons} |\n"
                )

            f.write("\n---\n\n## Detailed Definitions\n\n")
            for a in acronyms:
                f.write(f"### {a.acronym}\n\n")
                f.write(f"**Full Form:** {a.full_form}\n\n")
                f.write(f"**Definition:** {a.definition}\n\n")
                f.write(f"**Usage Count:** {a.usage_count}\n\n")
                f.write(f"**Introduced By:** {', '.join(a.introduced_by)}\n\n")

    def _save_master_index(
        self,
        result: FullConsolidationResult,
        output_dir: Path,
    ) -> None:
        """Save master index linking all outputs."""
        index_md = output_dir / "index.md"
        with open(index_md, "w") as f:
            f.write(f"# Consolidation Report: {result.session_name}\n\n")
            f.write(f"**Session ID:** `{result.session_id}`\n")
            f.write(f"**Generated:** {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write("---\n\n")

            f.write("## Quick Stats\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(
                f"| Original Motion Seeds | {result.consolidation.original_motion_count} |\n"
            )
            f.write(f"| Mega-Motions | {len(result.consolidation.mega_motions)} |\n")
            f.write(
                f"| Deferred Novel Proposals | {len(result.novel_proposals)} |\n"
            )
            f.write(f"| Acronyms Catalogued | {len(result.acronym_registry)} |\n")
            f.write(
                f"| Consolidation Ratio | {result.consolidation.consolidation_ratio:.1%} |\n"
            )
            f.write(
                f"| Traceability Complete | {'✅' if result.consolidation.traceability_complete else '❌'} |\n\n"
            )

            f.write("## Output Files\n\n")
            f.write("| File | Description |\n")
            f.write("|------|-------------|\n")
            f.write(
                "| [mega-motions.md](mega-motions.md) | Consolidated mega-motions (human-readable) |\n"
            )
            f.write(
                "| [mega-motions.json](mega-motions.json) | Mega-motions (machine-readable) |\n"
            )
            f.write(
                "| [traceability-matrix.md](traceability-matrix.md) | Source Motion Seed mapping |\n"
            )
            if result.consolidation.merge_audit:
                f.write(
                    "| [merge-audit.json](merge-audit.json) | Mega-motion merge audit trail |\n"
                )
            if result.novel_proposals:
                f.write(
                    "| [deferred-novel-proposals.md](deferred-novel-proposals.md) | Novel proposals deferred for later review |\n"
                )
            if result.conclave_summary:
                f.write(
                    "| [conclave-summary.md](conclave-summary.md) | Executive summary of deliberation |\n"
                )
            if result.acronym_registry:
                f.write(
                    "| [acronym-registry.md](acronym-registry.md) | Emerging terminology catalogue |\n"
                )
            f.write("\n")

            f.write("## Mega-Motion Summary\n\n")
            f.write("| # | Theme | Tier | Archons | Sources |\n")
            f.write("|---|-------|------|---------|--------|\n")
            tier_emoji = {"high": "🟢", "medium": "🟡", "low": "🔵"}
            for i, mm in enumerate(result.consolidation.mega_motions, 1):
                emoji = tier_emoji.get(mm.consensus_tier, "⚪")
                f.write(
                    f"| {i} | {mm.theme[:30]} | {emoji} {mm.consensus_tier.upper()} | {mm.unique_archon_count} | {len(mm.source_motion_ids)} |\n"
                )
