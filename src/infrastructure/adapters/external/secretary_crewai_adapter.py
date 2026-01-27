"""Secretary CrewAI adapter for LLM-enhanced transcript analysis.

This adapter implements SecretaryAgentProtocol using CrewAI to perform
nuanced recommendation extraction, validation, clustering, and motion
generation from Conclave transcripts.

The Secretary uses a DUAL-MODEL approach:
- Text model (ministral-3b): For extraction and analysis tasks
- JSON model (devstral-small): For structured output formatting

Checkpointing is enabled to save progress after each major step,
allowing recovery from failures without losing work.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> log all operations
- CT-12: Witnessing creates accountability -> trace to source lines
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from structlog import get_logger

from src.application.ports.secretary_agent import (
    ClusteringError,
    ClusteringResult,
    ConflictResult,
    ExtractionError,
    ExtractionResult,
    FullProcessingResult,
    MotionGenerationError,
    SecretaryAgentProtocol,
    SpeechContext,
    ValidationError,
)
from src.domain.models.llm_config import LLMConfig
from src.domain.models.secretary import (
    ConsensusLevel,
    ExtractedRecommendation,
    QueuedMotion,
    QueuedMotionStatus,
    RecommendationCategory,
    RecommendationCluster,
    RecommendationType,
    SourceReference,
)
from src.domain.models.secretary_agent import SecretaryAgentProfile
from src.infrastructure.adapters.external.crewai_json_utils import (
    aggressive_clean,
    sanitize_json_string,
    strip_markdown_fence,
)
from src.infrastructure.adapters.external.crewai_llm_factory import create_crewai_llm
from src.optional_deps.crewai import Agent, Crew, Task

logger = get_logger(__name__)

# Batch size for clustering to avoid overwhelming the model
# Reduced from 50 to 15 to prevent output truncation with smaller max_tokens configs
# See docs/spikes/secretary-alignment-v2.md section 11 for analysis
CLUSTERING_BATCH_SIZE = 15
# Default concurrency for per-speech extraction (can override via env).
DEFAULT_EXTRACTION_CONCURRENCY = 4


def _is_truncated_json(text: str) -> bool:
    """Check if JSON appears to be truncated mid-output."""
    cleaned = text.strip()

    # Check for unclosed brackets/braces
    open_brackets = cleaned.count("[") - cleaned.count("]")
    open_braces = cleaned.count("{") - cleaned.count("}")

    if open_brackets > 0 or open_braces > 0:
        return True

    # Check for trailing incomplete patterns
    truncation_patterns = [
        '": "',  # Truncated mid-string value
        '":"',  # Same without spaces
        '": [',  # Truncated mid-array
        '": {',  # Truncated mid-object
        ",",  # Ends with comma (expecting more)
    ]

    return any(cleaned.rstrip().endswith(pattern) for pattern in truncation_patterns)


class SecretaryCrewAIAdapter(SecretaryAgentProtocol):
    """CrewAI implementation of Secretary agent capabilities.

    Uses a dual-model approach:
    - text_agent: For extraction and analysis (ministral-3b)
    - json_agent: For structured output formatting (devstral-small)

    Includes checkpointing to save progress after each major step.

    Attributes:
        _profile: Secretary agent profile
        _text_agent: CrewAI Agent for text processing
        _json_agent: CrewAI Agent for JSON formatting
        _verbose: Enable verbose logging
        _checkpoint_dir: Directory for checkpoint files
    """

    def __init__(
        self,
        profile: SecretaryAgentProfile | None = None,
        verbose: bool = False,
        checkpoint_dir: str | Path | None = None,
    ) -> None:
        """Initialize the Secretary CrewAI adapter.

        Args:
            profile: Secretary profile (uses default if None)
            verbose: Enable verbose CrewAI logging
            checkpoint_dir: Directory for checkpoints (default: _bmad-output/secretary/checkpoints)
        """
        from src.domain.models.secretary_agent import create_default_secretary_profile

        self._profile = profile or create_default_secretary_profile()
        self._verbose = verbose
        self._checkpoint_dir = Path(
            checkpoint_dir or "_bmad-output/secretary/checkpoints"
        )
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Bound per-speech extraction concurrency.
        try:
            env_val = os.environ.get("SECRETARY_EXTRACT_CONCURRENCY", "")
            self._extraction_concurrency = max(
                1, int(env_val) if env_val else DEFAULT_EXTRACTION_CONCURRENCY
            )
        except ValueError:
            self._extraction_concurrency = DEFAULT_EXTRACTION_CONCURRENCY

        # Create dual agents
        self._text_agent = self._create_agent(self._profile.text_llm_config, "text")
        self._json_agent = self._create_agent(self._profile.json_llm_config, "json")

        logger.info(
            "secretary_crewai_adapter_initialized",
            agent_name=self._profile.name,
            text_model=self._profile.text_llm_config.model,
            json_model=self._profile.json_llm_config.model,
            checkpoints_enabled=self._profile.checkpoints_enabled,
            verbose=verbose,
        )

        # Warn if JSON model max_tokens is too low for clustering
        # Clustering 15 recommendations needs ~2000-4000 tokens output
        json_max_tokens = self._profile.json_llm_config.max_tokens
        if json_max_tokens < 4096:
            logger.warning(
                "json_model_max_tokens_low",
                current=json_max_tokens,
                recommended=8192,
                impact="Clustering may truncate with batches of 15+ recommendations",
            )

    def _create_agent(self, llm_config: LLMConfig, agent_type: str) -> Agent:
        """Create a CrewAI Agent with specified LLM config.

        Args:
            llm_config: LLM configuration to use
            agent_type: "text" or "json" for logging

        Returns:
            Configured CrewAI Agent
        """
        llm = create_crewai_llm(llm_config)

        # Local models don't support tool calling
        use_tools = llm_config.provider != "local"
        max_iter = 5 if use_tools else 3

        agent = Agent(
            role=self._profile.role,
            goal=self._profile.goal,
            backstory=self._profile.backstory,
            verbose=self._verbose,
            allow_delegation=False,
            llm=llm,
            max_iter=max_iter,
            tools=[],  # No tools for local models
        )

        logger.debug(
            "secretary_agent_created",
            agent_type=agent_type,
            model=llm_config.model,
            provider=llm_config.provider,
        )

        return agent

    def _save_checkpoint(
        self,
        session_id: str,
        step: str,
        data: dict | list,
    ) -> Path:
        """Save checkpoint data to file.

        Args:
            session_id: Session identifier
            step: Step name (extraction, validation, clustering, etc.)
            data: Data to save

        Returns:
            Path to checkpoint file
        """
        if not self._profile.checkpoints_enabled:
            return Path("/dev/null")

        checkpoint_file = self._checkpoint_dir / f"{session_id}_{step}.json"

        # Convert to JSON-serializable format
        if isinstance(data, list) and data and hasattr(data[0], "__dict__"):
            # Convert dataclass objects to dicts
            serializable = [self._to_dict(item) for item in data]
        elif isinstance(data, dict):
            serializable = {k: self._to_dict(v) for k, v in data.items()}
        else:
            serializable = data

        with open(checkpoint_file, "w") as f:
            json.dump(serializable, f, indent=2, default=str)

        logger.info(
            "checkpoint_saved",
            step=step,
            file=str(checkpoint_file),
            items=len(data) if isinstance(data, list) else 1,
        )

        return checkpoint_file

    def _to_dict(self, obj: object) -> object:
        """Convert object to JSON-serializable form.

        Args:
            obj: Any object to convert

        Returns:
            JSON-serializable representation (dict, list, str, int, float, bool, None)
        """
        if hasattr(obj, "__dict__"):
            result = {}
            for k, v in obj.__dict__.items():
                if not k.startswith("_"):
                    result[k] = self._to_dict(v)
            return result
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Enums and other types - convert to string
            return str(obj)

    def _load_checkpoint(
        self,
        session_id: str,
        step: str,
    ) -> dict | list | None:
        """Load checkpoint data if exists.

        Args:
            session_id: Session identifier
            step: Step name

        Returns:
            Loaded data or None if not found
        """
        checkpoint_file = self._checkpoint_dir / f"{session_id}_{step}.json"
        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                data = json.load(f)
            logger.info(
                "checkpoint_loaded",
                step=step,
                file=str(checkpoint_file),
            )
            return data
        return None

    async def extract_recommendations(
        self,
        speech: SpeechContext,
    ) -> ExtractionResult:
        """Extract recommendations from a single Archon speech using text model."""
        task = Task(
            description=f"""Extract recommendations from {speech.archon_name}'s speech.

SPEECH:
{speech.speech_content}

CONTEXT: {speech.motion_context or "General deliberation"}

Extract ALL recommendations (explicit or implicit). For each, output JSON:
{{"category": "establish|implement|mandate|amend|investigate|pilot|educate|review|other",
  "type": "policy|task|amendment|concern",
  "text": "the recommendation text",
  "keywords": ["key", "terms"],
  "stance": "FOR|AGAINST|NEUTRAL or null",
  "source_archon": "{speech.archon_name}",
  "source_line_start": {speech.line_start},
  "source_line_end": {speech.line_end}}}

CRITICAL: Output ONLY a JSON array. No text before or after. Example:
[{{"category":"implement","type":"policy","text":"...","keywords":["a","b"],"stance":null,"source_archon":"{speech.archon_name}","source_line_start":{speech.line_start},"source_line_end":{speech.line_end}}}]""",
            expected_output="A JSON array of recommendation objects only",
            agent=self._text_agent,  # Use text model for extraction
        )

        try:
            crew = Crew(
                agents=[self._text_agent],
                tasks=[task],
                verbose=self._verbose,
            )
            result = await asyncio.to_thread(crew.kickoff)
            recommendations = self._parse_extraction_result(
                str(result), speech.archon_name, speech
            )

            logger.info(
                "recommendations_extracted",
                archon=speech.archon_name,
                count=len(recommendations),
            )

            return ExtractionResult(
                recommendations=recommendations,
                missed_count=0,
                confidence=0.9,
            )

        except Exception as e:
            logger.error(
                "extraction_failed",
                archon=speech.archon_name,
                error=str(e),
            )
            raise ExtractionError(f"Failed to extract from {speech.archon_name}: {e}")

    def _parse_extraction_result(
        self,
        result: str,
        archon_name: str,
        speech: SpeechContext,
    ) -> list[ExtractedRecommendation]:
        """Parse LLM extraction result into domain objects."""
        recommendations: list[ExtractedRecommendation] = []
        json_str: str | None = None

        try:
            # Try to extract JSON array from response
            json_str = self._extract_json_array(result)
            if not json_str:
                # Check if response was truncated
                if _is_truncated_json(result):
                    logger.warning(
                        "truncated_json_response",
                        archon=archon_name,
                        raw_result=result[:300],
                    )
                else:
                    logger.warning(
                        "no_json_array_found",
                        archon=archon_name,
                        raw_result=result[:200],
                    )
                return recommendations

            # First attempt: normal parsing
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback: aggressive cleaning
                cleaned = aggressive_clean(json_str)
                data = json.loads(cleaned)
                logger.debug("aggressive_clean_succeeded", archon=archon_name)

            if not isinstance(data, list):
                data = [data]

            for item in data:
                source = SourceReference(
                    archon_id=speech.archon_id,
                    archon_name=archon_name,
                    archon_rank="",
                    line_number=item.get("source_line_start", speech.line_start),
                    timestamp=datetime.now(timezone.utc),
                    raw_text=item.get("text", ""),
                )
                rec = ExtractedRecommendation(
                    recommendation_id=uuid4(),
                    source=source,
                    category=self._parse_category(item.get("category", "other")),
                    recommendation_type=self._parse_type(item.get("type", "policy")),
                    summary=item.get("text", ""),
                    keywords=item.get("keywords", []),
                    extracted_at=datetime.now(timezone.utc),
                    stance=item.get("stance"),
                )
                recommendations.append(rec)

        except json.JSONDecodeError as e:
            logger.warning(
                "json_parse_failed",
                adapter="secretary",
                stage="extraction",
                archon=archon_name,
                error=str(e),
                raw_output=result[:500],
                json_attempted=json_str[:300] if json_str else "N/A",
            )

        return recommendations

    def _extract_json_array(self, text: str) -> str | None:
        """Extract JSON array from text, handling extra content and control chars."""
        cleaned = strip_markdown_fence(text)

        # Find first [ and matching ]
        start = cleaned.find("[")
        if start == -1:
            return None

        depth = 0
        end = -1
        for i, char in enumerate(cleaned[start:], start):
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end == -1:
            return None

        # Sanitize control characters before returning
        json_str = cleaned[start : end + 1]
        return sanitize_json_string(json_str)

    def _extract_json_object(self, text: str) -> str | None:
        """Extract JSON object from text, handling extra content and control chars."""
        cleaned = strip_markdown_fence(text)

        # Find first { and matching }
        start = cleaned.find("{")
        if start == -1:
            return None

        depth = 0
        end = -1
        for i, char in enumerate(cleaned[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end == -1:
            return None

        # Sanitize control characters before returning
        json_str = cleaned[start : end + 1]
        return sanitize_json_string(json_str)

    def _parse_category(self, category: str) -> RecommendationCategory:
        """Parse category string to enum."""
        category_map = {
            "establish": RecommendationCategory.ESTABLISH,
            "implement": RecommendationCategory.IMPLEMENT,
            "mandate": RecommendationCategory.MANDATE,
            "amend": RecommendationCategory.AMEND,
            "investigate": RecommendationCategory.INVESTIGATE,
            "pilot": RecommendationCategory.PILOT,
            "educate": RecommendationCategory.EDUCATE,
            "review": RecommendationCategory.REVIEW,
        }
        return category_map.get(category.lower(), RecommendationCategory.OTHER)

    def _parse_type(self, rec_type: str) -> RecommendationType:
        """Parse type string to enum."""
        type_map = {
            "policy": RecommendationType.POLICY,
            "task": RecommendationType.TASK,
            "amendment": RecommendationType.AMENDMENT,
            "concern": RecommendationType.CONCERN,
        }
        return type_map.get(rec_type.lower(), RecommendationType.POLICY)

    async def validate_extractions(
        self,
        recommendations: list[ExtractedRecommendation],
        original_speeches: list[SpeechContext],
    ) -> ExtractionResult:
        """Validate extractions using JSON model."""
        # Limit content to avoid context overflow
        rec_sample = (
            recommendations[:100] if len(recommendations) > 100 else recommendations
        )
        speech_sample = (
            original_speeches[:20] if len(original_speeches) > 20 else original_speeches
        )

        combined_content = "\n\n---\n\n".join(
            f"[{s.archon_name}]\n{s.speech_content[:500]}..." for s in speech_sample
        )

        rec_json = json.dumps(
            [
                {"text": r.summary[:200], "archon": r.source.archon_name}
                for r in rec_sample
            ],
            indent=2,
        )

        task = Task(
            description=f"""Validate extracted recommendations (sample of {len(rec_sample)}).

EXTRACTED RECOMMENDATIONS (sample):
{rec_json}

ORIGINAL SPEECHES (sample):
{combined_content}

Return a JSON object with:
- "validated_count": Number of accurate extractions
- "confidence": Float 0.0-1.0 for completeness
- "missed_count": Estimated missed recommendations

CRITICAL: Output ONLY valid JSON. Example:
{{"validated_count": 95, "confidence": 0.85, "missed_count": 5}}""",
            expected_output="JSON validation result",
            agent=self._json_agent,  # Use JSON model
        )

        try:
            crew = Crew(
                agents=[self._json_agent],
                tasks=[task],
                verbose=self._verbose,
            )
            result = await asyncio.to_thread(crew.kickoff)

            # Parse validation result
            json_str = self._extract_json_object(str(result))
            if json_str:
                data = json.loads(json_str)
                confidence = data.get("confidence", 0.9)
                missed_count = data.get("missed_count", 0)
            else:
                confidence = 0.8
                missed_count = 0

            logger.info(
                "extractions_validated",
                original_count=len(recommendations),
                confidence=confidence,
            )

            return ExtractionResult(
                recommendations=recommendations,
                missed_count=missed_count,
                confidence=confidence,
            )

        except Exception as e:
            logger.error("validation_failed", error=str(e))
            return ExtractionResult(
                recommendations=recommendations,
                missed_count=0,
                confidence=0.7,
            )

    async def cluster_semantically(
        self,
        recommendations: list[ExtractedRecommendation],
    ) -> ClusteringResult:
        """Cluster recommendations in batches, then consolidate across batches.

        Phase 1: Per-batch clustering (handles token limits)
        Phase 2: Cross-batch consolidation (merges similar themes)
        """
        all_clusters: list[RecommendationCluster] = []

        # Phase 1: Process in batches to avoid overwhelming the model
        total_batches = (
            len(recommendations) + CLUSTERING_BATCH_SIZE - 1
        ) // CLUSTERING_BATCH_SIZE

        for i in range(0, len(recommendations), CLUSTERING_BATCH_SIZE):
            batch = recommendations[i : i + CLUSTERING_BATCH_SIZE]
            batch_num = i // CLUSTERING_BATCH_SIZE + 1

            logger.info(
                "clustering_batch",
                batch=batch_num,
                total=total_batches,
                size=len(batch),
            )

            try:
                batch_clusters = await self._cluster_batch(batch)
                all_clusters.extend(batch_clusters)
            except Exception as e:
                logger.error(
                    "batch_clustering_failed",
                    batch=batch_num,
                    error=str(e),
                )

        logger.info(
            "phase1_clustering_complete",
            input_count=len(recommendations),
            raw_cluster_count=len(all_clusters),
        )

        # Phase 2: Cross-batch consolidation (merge similar themes)
        if len(all_clusters) > 10:
            try:
                consolidated = await self._consolidate_clusters(all_clusters)
                logger.info(
                    "phase2_consolidation_complete",
                    raw_clusters=len(all_clusters),
                    consolidated_clusters=len(consolidated),
                    reduction_ratio=f"{(1 - len(consolidated)/len(all_clusters))*100:.1f}%",
                )
                all_clusters = consolidated
            except Exception as e:
                logger.warning(
                    "cluster_consolidation_failed",
                    error=str(e),
                    keeping_raw_clusters=len(all_clusters),
                )

        logger.info(
            "recommendations_clustered",
            input_count=len(recommendations),
            cluster_count=len(all_clusters),
        )

        return ClusteringResult(clusters=all_clusters, unclustered=[])

    async def _cluster_batch(
        self,
        recommendations: list[ExtractedRecommendation],
    ) -> list[RecommendationCluster]:
        """Cluster a single batch of recommendations."""
        rec_json = json.dumps(
            [
                {
                    "id": str(r.recommendation_id),
                    "text": r.summary[:200],  # Truncate for context
                    "keywords": r.keywords[:5],
                    "archon": r.source.archon_name,
                }
                for r in recommendations
            ],
            indent=2,
        )

        task = Task(
            description=f"""Cluster these {len(recommendations)} recommendations by theme.

RECOMMENDATIONS:
{rec_json}

Group by semantic similarity. For each cluster:
- "theme": 1-3 word label
- "canonical_summary": Representative text
- "member_ids": Array of recommendation IDs
- "archon_names": Array of archon names
- "archon_count": Number of unique archons

CRITICAL: Output ONLY a valid JSON array. Example:
[{{"theme":"Ethics Council","canonical_summary":"Establish ethics oversight","member_ids":["id1","id2"],"archon_names":["Bael","Asmoday"],"archon_count":2}}]""",
            expected_output="JSON array of clusters",
            agent=self._json_agent,  # Use JSON model
        )

        crew = Crew(
            agents=[self._json_agent],
            tasks=[task],
            verbose=self._verbose,
        )
        result = await asyncio.to_thread(crew.kickoff)
        return self._parse_clustering_result(str(result), recommendations)

    def _parse_clustering_result(
        self,
        result: str,
        recommendations: list[ExtractedRecommendation],
    ) -> list[RecommendationCluster]:
        """Parse clustering result into domain objects."""
        clusters: list[RecommendationCluster] = []
        rec_by_id = {str(r.recommendation_id): r for r in recommendations}

        try:
            json_str = self._extract_json_array(result)
            if not json_str:
                if _is_truncated_json(result):
                    logger.warning("truncated_clustering_response", raw=result[:300])
                else:
                    logger.warning("no_json_array_in_clustering", raw=result[:200])
                return clusters

            # First attempt: normal parsing
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback: aggressive cleaning
                cleaned = aggressive_clean(json_str)
                data = json.loads(cleaned)
                logger.debug("aggressive_clean_succeeded_clustering")

            if not isinstance(data, list):
                data = [data]

            for item in data:
                member_ids = item.get("member_ids", [])
                members = [rec_by_id[mid] for mid in member_ids if mid in rec_by_id]

                if members:
                    category = members[0].category
                    rec_type = members[0].recommendation_type
                    archon_count = item.get(
                        "archon_count", len(set(m.source.archon_name for m in members))
                    )

                    cluster = RecommendationCluster(
                        cluster_id=uuid4(),
                        theme=item.get("theme", "Uncategorized"),
                        canonical_summary=item.get("canonical_summary", ""),
                        category=category,
                        recommendation_type=rec_type,
                        keywords=item.get("combined_keywords", []),
                        recommendations=members,
                        archon_count=archon_count,
                        consensus_level=ConsensusLevel.from_count(archon_count),
                        archon_ids=[m.source.archon_id for m in members],
                        archon_names=item.get("archon_names", []),
                        created_at=datetime.now(timezone.utc),
                    )
                    clusters.append(cluster)

        except json.JSONDecodeError as e:
            logger.warning(
                "json_parse_failed",
                adapter="secretary",
                stage="clustering",
                error=str(e),
                raw_output=result[:300],
            )

        return clusters

    async def _consolidate_clusters(
        self,
        clusters: list[RecommendationCluster],
    ) -> list[RecommendationCluster]:
        """Consolidate similar clusters from different batches.

        Uses LLM to identify semantically similar clusters across batches,
        then merges them to reduce fragmentation.
        """
        # Build cluster summaries for comparison.
        # Keep a stable global index for mapping back to the original cluster list.
        cluster_summaries = [
            {
                "global_idx": i,
                "theme": c.theme,
                "summary": c.canonical_summary[:100],
                "keywords": c.keywords[:5] if c.keywords else [],
                "archon_count": c.archon_count,
            }
            for i, c in enumerate(clusters)
        ]

        def _norm(text: str) -> str:
            cleaned = re.sub(r"[^a-z0-9\\s]", " ", text.lower())
            return re.sub(r"\\s+", " ", cleaned).strip()

        # Sort so similar themes/summaries are nearby in windows.
        cluster_summaries.sort(
            key=lambda s: (
                _norm(s.get("theme", "")),
                _norm(s.get("summary", "")),
                -int(s.get("archon_count", 0)),
            )
        )

        # Process in batches if too many clusters
        consolidation_batch_size = 50
        if len(cluster_summaries) <= consolidation_batch_size:
            local_summaries = [
                {
                    "index": i,
                    "theme": s["theme"],
                    "summary": s["summary"],
                    "keywords": s["keywords"],
                    "archon_count": s["archon_count"],
                }
                for i, s in enumerate(cluster_summaries)
            ]
            index_map = {
                i: s["global_idx"] for i, s in enumerate(cluster_summaries)
            }
            merge_groups_local = await self._identify_merge_groups(local_summaries)
            merge_groups = [
                [index_map[idx] for idx in group if idx in index_map]
                for group in merge_groups_local
            ]
        else:
            # For large cluster sets, process in overlapping windows
            merge_groups = await self._identify_merge_groups_batched(
                cluster_summaries, consolidation_batch_size
            )

        if not merge_groups:
            return clusters

        # Build consolidated clusters
        consolidated: list[RecommendationCluster] = []
        merged_indices: set[int] = set()

        for group in merge_groups:
            if len(group) == 1:
                # Single cluster - no merge needed
                consolidated.append(clusters[group[0]])
                merged_indices.add(group[0])
            else:
                # Multiple clusters - merge them
                group_clusters = [clusters[i] for i in group]
                merged = self._merge_cluster_group(group_clusters)
                consolidated.append(merged)
                merged_indices.update(group)

        # Add any clusters that weren't in any merge group
        for i, cluster in enumerate(clusters):
            if i not in merged_indices:
                consolidated.append(cluster)

        return consolidated

    async def _identify_merge_groups(
        self,
        summaries: list[dict],
    ) -> list[list[int]]:
        """Use LLM to identify which clusters should be merged."""
        summaries_json = json.dumps(summaries, indent=2)

        task = Task(
            description=f"""Identify semantically similar clusters that should be merged.

CLUSTERS:
{summaries_json}

Group clusters by semantic similarity (same topic/intent). Each cluster should appear in EXACTLY ONE group.
Clusters with different themes should NOT be merged.

Return JSON array of index arrays using the 'index' field values. Example:
[[0, 5, 12], [1, 8], [2], [3, 7, 15], [4], ...]

CRITICAL:
- Every cluster index (0 to {len(summaries)-1}) must appear exactly once
- Only group clusters with genuinely similar themes
- Output ONLY a valid JSON array of arrays""",
            expected_output="JSON array of merge groups",
            agent=self._json_agent,
        )

        try:
            crew = Crew(
                agents=[self._json_agent],
                tasks=[task],
                verbose=self._verbose,
            )
            result = await asyncio.to_thread(crew.kickoff)
            return self._parse_merge_groups(str(result), len(summaries))

        except Exception as e:
            logger.warning("merge_group_identification_failed", error=str(e))
            return []

    async def _identify_merge_groups_batched(
        self,
        summaries: list[dict],
        batch_size: int,
    ) -> list[list[int]]:
        """Identify merge groups for large cluster sets using batched processing."""
        # Strategy: process in overlapping batches, then reconcile
        all_merge_groups: list[list[int]] = []

        for i in range(0, len(summaries), batch_size // 2):
            batch = summaries[i : i + batch_size]
            if len(batch) < 5:
                # Too small to cluster
                all_merge_groups.extend([[s["global_idx"]] for s in batch])
                continue

            local_summaries = [
                {
                    "index": j,
                    "theme": s["theme"],
                    "summary": s["summary"],
                    "keywords": s["keywords"],
                    "archon_count": s["archon_count"],
                }
                for j, s in enumerate(batch)
            ]
            index_map = {j: s["global_idx"] for j, s in enumerate(batch)}
            batch_groups = await self._identify_merge_groups(local_summaries)

            # Convert batch-local indices to global indices
            for group in batch_groups:
                global_group = [index_map[j] for j in group if j in index_map]
                if global_group:
                    all_merge_groups.append(global_group)

        # Reconcile overlapping groups (merge groups that share members)
        return self._reconcile_merge_groups(all_merge_groups, len(summaries))

    def _reconcile_merge_groups(
        self,
        groups: list[list[int]],
        total_count: int,
    ) -> list[list[int]]:
        """Reconcile overlapping merge groups using union-find."""
        # Union-find structure
        parent = list(range(total_count))

        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Union all indices in each group
        for group in groups:
            if len(group) > 1:
                for i in range(1, len(group)):
                    union(group[0], group[i])

        # Collect final groups
        group_map: dict[int, list[int]] = {}
        for i in range(total_count):
            root = find(i)
            if root not in group_map:
                group_map[root] = []
            group_map[root].append(i)

        return list(group_map.values())

    def _parse_merge_groups(
        self,
        result: str,
        cluster_count: int,
    ) -> list[list[int]]:
        """Parse LLM merge group response."""
        try:
            json_str = self._extract_json_array(result)
            if not json_str:
                if _is_truncated_json(result):
                    logger.warning("truncated_merge_groups_response", raw=result[:300])
                return []

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                cleaned = aggressive_clean(json_str)
                data = json.loads(cleaned)

            if not isinstance(data, list):
                return []

            # Validate and clean groups
            groups: list[list[int]] = []
            seen_indices: set[int] = set()

            for item in data:
                if isinstance(item, list):
                    group = [
                        int(idx) for idx in item
                        if isinstance(idx, (int, float)) and 0 <= int(idx) < cluster_count
                    ]
                    # Remove duplicates and already-seen indices
                    unique_group = [idx for idx in group if idx not in seen_indices]
                    if unique_group:
                        groups.append(unique_group)
                        seen_indices.update(unique_group)

            # Add any missing indices as singletons
            for i in range(cluster_count):
                if i not in seen_indices:
                    groups.append([i])

            logger.info(
                "merge_groups_identified",
                total_clusters=cluster_count,
                merge_groups=len(groups),
                multi_member_groups=sum(1 for g in groups if len(g) > 1),
            )

            return groups

        except Exception as e:
            logger.warning("merge_groups_parse_failed", error=str(e))
            return []

    def _merge_cluster_group(
        self,
        clusters: list[RecommendationCluster],
    ) -> RecommendationCluster:
        """Merge multiple clusters into one consolidated cluster."""
        if len(clusters) == 1:
            return clusters[0]

        # Combine all recommendations
        all_recommendations: list[ExtractedRecommendation] = []
        all_archon_names: list[str] = []
        all_archon_ids: list[str] = []
        all_keywords: list[str] = []
        themes: list[str] = []

        for cluster in clusters:
            all_recommendations.extend(cluster.recommendations)
            all_archon_names.extend(cluster.archon_names)
            all_archon_ids.extend(cluster.archon_ids)
            all_keywords.extend(cluster.keywords or [])
            themes.append(cluster.theme)

        # Deduplicate
        unique_archon_names = list(dict.fromkeys(all_archon_names))
        unique_archon_ids = list(dict.fromkeys(all_archon_ids))
        unique_keywords = list(dict.fromkeys(all_keywords))[:10]

        # Choose best theme (most common or first)
        theme_counts: dict[str, int] = {}
        for t in themes:
            theme_counts[t] = theme_counts.get(t, 0) + 1
        merged_theme = max(theme_counts, key=theme_counts.get)  # type: ignore[arg-type]

        # Use the canonical summary from the largest cluster
        largest_cluster = max(clusters, key=lambda c: c.archon_count)
        canonical_summary = largest_cluster.canonical_summary

        # Use category/type from largest cluster
        category = largest_cluster.category
        rec_type = largest_cluster.recommendation_type

        archon_count = len(unique_archon_names)

        merged = RecommendationCluster(
            cluster_id=uuid4(),
            theme=merged_theme,
            canonical_summary=canonical_summary,
            category=category,
            recommendation_type=rec_type,
            keywords=unique_keywords,
            recommendations=all_recommendations,
            archon_count=archon_count,
            consensus_level=ConsensusLevel.from_count(archon_count),
            archon_ids=unique_archon_ids,
            archon_names=unique_archon_names,
            created_at=datetime.now(timezone.utc),
        )

        logger.debug(
            "clusters_merged",
            source_count=len(clusters),
            themes=themes,
            merged_theme=merged_theme,
            archon_count=archon_count,
        )

        return merged

    async def detect_conflicts(
        self,
        recommendations: list[ExtractedRecommendation],
    ) -> ConflictResult:
        """Detect conflicts using JSON model."""
        # Sample for large lists
        sample = (
            recommendations[:100] if len(recommendations) > 100 else recommendations
        )

        rec_json = json.dumps(
            [
                {
                    "id": str(r.recommendation_id),
                    "text": r.summary[:150],
                    "archon": r.source.archon_name,
                }
                for r in sample
            ],
            indent=2,
        )

        task = Task(
            description=f"""Find conflicting positions in these recommendations.

RECOMMENDATIONS:
{rec_json}

Look for contradictions, incompatible approaches, or resource conflicts.

Return JSON:
{{"conflicts": [{{"archon_a": "Name", "archon_b": "Name", "description": "Brief conflict description"}}], "conflict_count": 0}}

CRITICAL: Output ONLY valid JSON.""",
            expected_output="JSON conflict analysis",
            agent=self._json_agent,
        )

        try:
            crew = Crew(
                agents=[self._json_agent],
                tasks=[task],
                verbose=self._verbose,
            )
            result = await asyncio.to_thread(crew.kickoff)

            json_str = self._extract_json_object(str(result))
            if json_str:
                data = json.loads(json_str)
                conflict_count = data.get(
                    "conflict_count", len(data.get("conflicts", []))
                )
            else:
                conflict_count = 0

            logger.info("conflicts_detected", conflict_count=conflict_count)

            return ConflictResult(conflicts=[], resolution_suggestions=[])

        except Exception as e:
            logger.error("conflict_detection_failed", error=str(e))
            return ConflictResult(conflicts=[], resolution_suggestions=[])

    async def generate_motion_text(
        self,
        cluster: RecommendationCluster,
        session_context: str,
    ) -> QueuedMotion:
        """Generate motion text using JSON model."""
        cluster_json = json.dumps(
            {
                "theme": cluster.theme,
                "summary": cluster.canonical_summary[:300],
                "archon_names": cluster.archon_names[:10],
                "archon_count": cluster.archon_count,
            },
            indent=2,
        )

        task = Task(
            description=f"""Generate formal motion text for this cluster.

CLUSTER:
{cluster_json}

Return JSON:
{{"title": "Motion to...", "motion_text": "The Conclave hereby...", "rationale": "Based on..."}}

CRITICAL: Output ONLY valid JSON. Do not use line breaks within string values.""",
            expected_output="JSON motion object",
            agent=self._json_agent,
        )

        try:
            crew = Crew(
                agents=[self._json_agent],
                tasks=[task],
                verbose=self._verbose,
            )
            result = await asyncio.to_thread(crew.kickoff)
            result_str = str(result)

            json_str = self._extract_json_object(result_str)
            if json_str:
                # First attempt: normal parsing
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Fallback: aggressive cleaning
                    cleaned = aggressive_clean(json_str)
                    data = json.loads(cleaned)
                    logger.debug(
                        "aggressive_clean_succeeded_motion", theme=cluster.theme
                    )
            else:
                # No JSON object found - try aggressive cleaning on raw result
                if _is_truncated_json(result_str):
                    logger.warning(
                        "truncated_motion_response",
                        theme=cluster.theme,
                        raw_result=result_str[:200],
                    )
                data = {}

            motion = QueuedMotion(
                queued_motion_id=uuid4(),
                status=QueuedMotionStatus.PENDING,
                title=data.get("title", f"Motion: {cluster.theme}"),
                text=data.get("motion_text", cluster.canonical_summary),
                rationale=data.get(
                    "rationale",
                    f"Derived from {cluster.archon_count} Archon recommendations",
                ),
                source_cluster_id=cluster.cluster_id,
                source_cluster_theme=cluster.theme,
                original_archon_count=cluster.archon_count,
                consensus_level=cluster.consensus_level,
                supporting_archons=cluster.archon_names.copy(),
                source_session_name=session_context,
                created_at=datetime.now(timezone.utc),
            )

            logger.info(
                "motion_generated",
                theme=cluster.theme,
                archon_count=cluster.archon_count,
            )

            return motion

        except json.JSONDecodeError as e:
            # JSON parsing failed even with aggressive cleaning
            logger.error(
                "json_parse_failed",
                adapter="secretary",
                stage="motion_generation",
                error=str(e),
                theme=cluster.theme,
            )
            # Return a fallback motion rather than failing completely
            return QueuedMotion(
                queued_motion_id=uuid4(),
                status=QueuedMotionStatus.PENDING,
                title=f"Motion: {cluster.theme}",
                text=cluster.canonical_summary,
                rationale=f"Derived from {cluster.archon_count} Archon recommendations (auto-generated)",
                source_cluster_id=cluster.cluster_id,
                source_cluster_theme=cluster.theme,
                original_archon_count=cluster.archon_count,
                consensus_level=cluster.consensus_level,
                supporting_archons=cluster.archon_names.copy(),
                source_session_name=session_context,
                created_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("motion_generation_failed", error=str(e), theme=cluster.theme)
            raise MotionGenerationError(f"Failed to generate motion: {e}")

    async def process_full_transcript(
        self,
        speeches: list[SpeechContext],
        session_id: str,
        session_name: str,
    ) -> FullProcessingResult:
        """Process transcript with checkpointing after each step."""
        start_time = time.time()
        checkpoint_id = f"{session_id}_{int(start_time)}"

        # Step 1: Extract from all speeches
        logger.info(
            "step_1_extraction_start",
            speech_count=len(speeches),
            concurrency=self._extraction_concurrency,
        )
        all_recommendations: list[ExtractedRecommendation] = []
        recommendation_count = 0
        results_by_index: dict[int, list[ExtractedRecommendation]] = {}

        semaphore = asyncio.Semaphore(self._extraction_concurrency)

        async def _extract_one(idx: int, speech: SpeechContext):
            async with semaphore:
                try:
                    result = await self.extract_recommendations(speech)
                    return idx, result.recommendations, None
                except ExtractionError as exc:
                    return idx, [], exc

        tasks = [
            asyncio.create_task(_extract_one(i, speech))
            for i, speech in enumerate(speeches)
        ]
        processed = 0
        for task in asyncio.as_completed(tasks):
            idx, recs, err = await task
            results_by_index[idx] = recs
            if err:
                logger.warning(
                    "skipping_speech_extraction",
                    archon=speeches[idx].archon_name,
                )
            else:
                recommendation_count += len(recs)

            processed += 1
            if processed % 10 == 0:
                logger.info(
                    "extraction_progress",
                    processed=processed,
                    total=len(speeches),
                    recommendations_so_far=recommendation_count,
                )

        # Preserve original ordering in the aggregated output.
        for i in range(len(speeches)):
            all_recommendations.extend(results_by_index.get(i, []))

        # Checkpoint after extraction
        self._save_checkpoint(checkpoint_id, "01_extraction", all_recommendations)
        logger.info(
            "step_1_extraction_complete",
            recommendations=len(all_recommendations),
        )

        # Step 2: Validate extractions
        logger.info("step_2_validation_start")
        try:
            validated = await self.validate_extractions(all_recommendations, speeches)
            confidence = validated.confidence
        except ValidationError:
            confidence = 0.7

        self._save_checkpoint(
            checkpoint_id, "02_validation", {"confidence": confidence}
        )
        logger.info("step_2_validation_complete", confidence=confidence)

        # Step 3: Cluster semantically
        logger.info("step_3_clustering_start")
        try:
            clustering = await self.cluster_semantically(all_recommendations)
            clusters = clustering.clusters
        except ClusteringError:
            clusters = []

        self._save_checkpoint(checkpoint_id, "03_clustering", clusters)
        logger.info("step_3_clustering_complete", clusters=len(clusters))

        # Step 4: Detect conflicts
        logger.info("step_4_conflicts_start")
        conflict_result = await self.detect_conflicts(all_recommendations)
        self._save_checkpoint(
            checkpoint_id,
            "04_conflicts",
            {"count": len(conflict_result.conflicts)},
        )
        logger.info("step_4_conflicts_complete", count=len(conflict_result.conflicts))

        # Step 5: Generate motions for high-consensus clusters
        logger.info("step_5_motions_start")
        motions: list[QueuedMotion] = []
        for cluster in clusters:
            if cluster.archon_count >= 2:
                try:
                    motion = await self.generate_motion_text(
                        cluster, f"{session_id}:{session_name}"
                    )
                    motions.append(motion)
                except MotionGenerationError:
                    pass

        self._save_checkpoint(checkpoint_id, "05_motions", motions)
        logger.info("step_5_motions_complete", motions=len(motions))

        elapsed_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "full_transcript_processed",
            speech_count=len(speeches),
            recommendation_count=len(all_recommendations),
            cluster_count=len(clusters),
            motion_count=len(motions),
            conflict_count=len(conflict_result.conflicts),
            elapsed_ms=elapsed_ms,
        )

        return FullProcessingResult(
            recommendations=all_recommendations,
            clusters=clusters,
            conflicts=conflict_result.conflicts,
            motions=motions,
            extraction_confidence=confidence,
            processing_time_ms=elapsed_ms,
        )
