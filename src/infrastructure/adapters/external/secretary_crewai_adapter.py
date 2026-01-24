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
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.optional_deps.crewai import Agent, Crew, Task
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

logger = get_logger(__name__)

# Batch size for clustering to avoid overwhelming the model
CLUSTERING_BATCH_SIZE = 50


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
        """Cluster recommendations in batches using JSON model."""
        all_clusters: list[RecommendationCluster] = []

        # Process in batches to avoid overwhelming the model
        for i in range(0, len(recommendations), CLUSTERING_BATCH_SIZE):
            batch = recommendations[i : i + CLUSTERING_BATCH_SIZE]
            batch_num = i // CLUSTERING_BATCH_SIZE + 1
            total_batches = (
                len(recommendations) + CLUSTERING_BATCH_SIZE - 1
            ) // CLUSTERING_BATCH_SIZE

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
        logger.info("step_1_extraction_start", speech_count=len(speeches))
        all_recommendations: list[ExtractedRecommendation] = []

        for i, speech in enumerate(speeches):
            try:
                result = await self.extract_recommendations(speech)
                all_recommendations.extend(result.recommendations)

                # Log progress every 10 speeches
                if (i + 1) % 10 == 0:
                    logger.info(
                        "extraction_progress",
                        processed=i + 1,
                        total=len(speeches),
                        recommendations_so_far=len(all_recommendations),
                    )

            except ExtractionError:
                logger.warning("skipping_speech_extraction", archon=speech.archon_name)

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
