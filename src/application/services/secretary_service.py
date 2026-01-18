"""Secretary Service - Automated Conclave post-processing.

Processes Conclave transcripts to extract, cluster, and queue recommendations
for future Conclave sessions. The Secretary is fully automated with deterministic
outputs - same transcript produces same analysis.

Key responsibilities:
1. Extract recommendations from Archon speeches
2. Cluster similar recommendations semantically
3. Generate Motion Seed queue for next Conclave
4. Create task registry for operational items
5. Detect conflicting positions for resolution

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> log all operations
- CT-12: Witnessing creates accountability -> full traceability
- FR9: All outputs through witnessing pipeline
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.application.ports.secretary_agent import SecretaryAgentProtocol

from src.domain.models.secretary import (
    ConflictingPosition,
    ExtractedRecommendation,
    QueuedMotion,
    RecommendationCategory,
    RecommendationCluster,
    RecommendationType,
    SecretaryReport,
    SourceReference,
    TaskItem,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Extraction Patterns
# =============================================================================


@dataclass
class ExtractionPattern:
    """A pattern for extracting recommendations from text."""

    name: str
    pattern: re.Pattern[str]
    category: RecommendationCategory
    recommendation_type: RecommendationType


# Core extraction patterns for recommendation identification
EXTRACTION_PATTERNS: list[ExtractionPattern] = [
    # Explicit recommendations section
    ExtractionPattern(
        name="recommendations_section",
        pattern=re.compile(
            r"\*\*Recommend(?:ation)?s?\*\*:?\s*\n?((?:[-•\d]+\.?\s*.+?\n?)+)",
            re.IGNORECASE | re.MULTILINE,
        ),
        category=RecommendationCategory.OTHER,
        recommendation_type=RecommendationType.POLICY,
    ),
    # Numbered recommendations
    ExtractionPattern(
        name="numbered_recommendation",
        pattern=re.compile(
            r"^\s*(\d+)\.\s*\*\*([^*]+)\*\*:?\s*(.+?)(?=\n\s*\d+\.|$)",
            re.MULTILINE | re.DOTALL,
        ),
        category=RecommendationCategory.OTHER,
        recommendation_type=RecommendationType.POLICY,
    ),
    # "I recommend/propose/suggest" patterns
    ExtractionPattern(
        name="i_recommend",
        pattern=re.compile(
            r"I\s+(?:recommend|propose|suggest|urge|advocate)\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.OTHER,
        recommendation_type=RecommendationType.POLICY,
    ),
    # "Establish" patterns (councils, bodies, frameworks)
    ExtractionPattern(
        name="establish",
        pattern=re.compile(
            r"[Ee]stablish\s+(?:a\s+|an\s+)?(.+?)(?:\s+to\s+|\s+for\s+|\s+that\s+|,|\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.ESTABLISH,
        recommendation_type=RecommendationType.POLICY,
    ),
    # "Create" patterns
    ExtractionPattern(
        name="create",
        pattern=re.compile(
            r"[Cc]reate\s+(?:a\s+|an\s+)?(.+?)(?:\s+to\s+|\s+for\s+|\s+that\s+|,|\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.ESTABLISH,
        recommendation_type=RecommendationType.POLICY,
    ),
    # "Implement" patterns
    ExtractionPattern(
        name="implement",
        pattern=re.compile(
            r"[Ii]mplement\s+(?:a\s+|an\s+)?(.+?)(?:\s+to\s+|\s+for\s+|\s+that\s+|,|\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.IMPLEMENT,
        recommendation_type=RecommendationType.TASK,
    ),
    # "Mandate" patterns
    ExtractionPattern(
        name="mandate",
        pattern=re.compile(
            r"[Mm]andate\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.MANDATE,
        recommendation_type=RecommendationType.POLICY,
    ),
    # "Require" patterns
    ExtractionPattern(
        name="require",
        pattern=re.compile(
            r"[Rr]equire\s+(?:that\s+)?(.+?)(?:\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.MANDATE,
        recommendation_type=RecommendationType.POLICY,
    ),
    # "Task force" patterns
    ExtractionPattern(
        name="task_force",
        pattern=re.compile(
            r"(?:task\s+force|committee|council|panel|body)\s+(?:to\s+|for\s+)?(.+?)(?:\.|,|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.ESTABLISH,
        recommendation_type=RecommendationType.POLICY,
    ),
    # "Pilot" patterns
    ExtractionPattern(
        name="pilot",
        pattern=re.compile(
            r"[Pp]ilot\s+(?:the\s+|a\s+|an\s+)?(.+?)(?:\s+in\s+|\s+before\s+|,|\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.PILOT,
        recommendation_type=RecommendationType.TASK,
    ),
    # "Invest in" patterns
    ExtractionPattern(
        name="invest",
        pattern=re.compile(
            r"[Ii]nvest\s+in\s+(.+?)(?:\s+to\s+|\s+for\s+|,|\.|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.IMPLEMENT,
        recommendation_type=RecommendationType.TASK,
    ),
    # "Training/education" patterns
    ExtractionPattern(
        name="education",
        pattern=re.compile(
            r"(?:training|education|curriculum)\s+(?:program|initiative)?\s*(?:for\s+|to\s+|in\s+)?(.+?)(?:\.|,|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.EDUCATE,
        recommendation_type=RecommendationType.TASK,
    ),
    # "Review/audit" patterns
    ExtractionPattern(
        name="review",
        pattern=re.compile(
            r"(?:periodic|regular|annual|biennial)\s+(?:review|audit|assessment)s?\s+(?:of\s+|for\s+)?(.+?)(?:\.|,|$)",
            re.IGNORECASE,
        ),
        category=RecommendationCategory.REVIEW,
        recommendation_type=RecommendationType.POLICY,
    ),
]

# Patterns to extract stance (FOR/AGAINST/NEUTRAL)
STANCE_PATTERNS = [
    (re.compile(r"^\*\*(?:FOR|AYE)\*\*", re.IGNORECASE), "FOR"),
    (re.compile(r"^\*\*(?:AGAINST|NAY)\*\*", re.IGNORECASE), "AGAINST"),
    (re.compile(r"^\*\*NEUTRAL\*\*", re.IGNORECASE), "NEUTRAL"),
    (re.compile(r"I\s+am\s+(?:FOR|AYE)", re.IGNORECASE), "FOR"),
    (re.compile(r"I\s+am\s+(?:AGAINST|NAY)", re.IGNORECASE), "AGAINST"),
    (re.compile(r"I\s+(?:support|endorse|approve)", re.IGNORECASE), "FOR"),
    (re.compile(r"I\s+(?:oppose|reject|vote\s+against)", re.IGNORECASE), "AGAINST"),
]

# Keywords for semantic clustering
CLUSTER_KEYWORDS = {
    "oversight": [
        "oversight",
        "council",
        "committee",
        "panel",
        "review",
        "audit",
        "monitor",
    ],
    "ethics": ["ethics", "ethical", "moral", "values", "principles", "integrity"],
    "transparency": [
        "transparent",
        "transparency",
        "audit",
        "trail",
        "log",
        "record",
        "accountability",
    ],
    "human_control": [
        "human",
        "oversight",
        "control",
        "loop",
        "intervention",
        "judgment",
    ],
    "risk": [
        "risk",
        "assessment",
        "mitigation",
        "proactive",
        "prevention",
        "vulnerability",
    ],
    "education": ["training", "education", "curriculum", "learn", "teach", "develop"],
    "governance": [
        "governance",
        "framework",
        "policy",
        "procedure",
        "protocol",
        "standard",
    ],
    "security": ["security", "secure", "protect", "safeguard", "defense", "resilient"],
    "ai_alignment": [
        "alignment",
        "align",
        "values",
        "constitutional",
        "ethical",
        "safeguard",
    ],
    "blockchain": ["blockchain", "immutable", "tamper", "ledger", "distributed"],
    "task_force": ["task force", "committee", "council", "panel", "body", "group"],
}


# =============================================================================
# Clustering Algorithm
# =============================================================================


def extract_keywords(text: str) -> list[str]:
    """Extract relevant keywords from text for clustering."""
    text_lower = text.lower()
    found_keywords = []

    for category, keywords in CLUSTER_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                if category not in found_keywords:
                    found_keywords.append(category)
                break

    return found_keywords


def compute_similarity(
    rec_a: ExtractedRecommendation, rec_b: ExtractedRecommendation
) -> float:
    """Compute similarity score between two recommendations.

    Uses keyword overlap and category matching.
    Returns score between 0.0 and 1.0.
    """
    # Same category bonus
    category_score = 0.3 if rec_a.category == rec_b.category else 0.0

    # Keyword overlap (Jaccard similarity)
    set_a = set(rec_a.keywords)
    set_b = set(rec_b.keywords)

    if not set_a and not set_b or not set_a or not set_b:
        keyword_score = 0.0
    else:
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        keyword_score = intersection / union * 0.5

    # Text similarity (simple word overlap)
    words_a = set(rec_a.summary.lower().split())
    words_b = set(rec_b.summary.lower().split())

    # Remove common stop words
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "for",
        "of",
        "in",
        "on",
        "with",
        "that",
        "this",
        "be",
        "is",
        "are",
        "was",
        "were",
    }
    words_a = words_a - stop_words
    words_b = words_b - stop_words

    if not words_a or not words_b:
        text_score = 0.0
    else:
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        text_score = intersection / union * 0.2

    return category_score + keyword_score + text_score


def cluster_recommendations(
    recommendations: list[ExtractedRecommendation],
    similarity_threshold: float = 0.3,
) -> list[RecommendationCluster]:
    """Cluster similar recommendations using agglomerative approach.

    Args:
        recommendations: List of extracted recommendations
        similarity_threshold: Minimum similarity to merge (0.0-1.0)

    Returns:
        List of recommendation clusters
    """
    if not recommendations:
        return []

    # Start with each recommendation in its own cluster
    clusters: list[RecommendationCluster] = []

    for rec in recommendations:
        # Try to find an existing cluster to join
        best_cluster = None
        best_similarity = 0.0

        for cluster in clusters:
            # Compare against first (canonical) recommendation
            if cluster.recommendations:
                sim = compute_similarity(rec, cluster.recommendations[0])
                if sim > best_similarity and sim >= similarity_threshold:
                    best_similarity = sim
                    best_cluster = cluster

        if best_cluster:
            # Join existing cluster
            best_cluster.add_recommendation(rec)
        else:
            # Create new cluster
            cluster = RecommendationCluster.create(
                theme=_generate_theme(rec),
                canonical_summary=rec.summary,
                category=rec.category,
                recommendation_type=rec.recommendation_type,
                keywords=rec.keywords.copy(),
            )
            cluster.add_recommendation(rec)
            clusters.append(cluster)

    # Post-process: refine themes based on all cluster members
    for cluster in clusters:
        if len(cluster.recommendations) > 1:
            cluster.theme = _refine_cluster_theme(cluster)

    return clusters


def _generate_theme(rec: ExtractedRecommendation) -> str:
    """Generate a theme name from a single recommendation."""
    # Extract key noun phrases
    summary = rec.summary

    # Try to find council/body/framework mentions
    council_match = re.search(
        r"([\w\s]+(?:council|committee|panel|body|framework|protocol|system))",
        summary,
        re.IGNORECASE,
    )
    if council_match:
        return council_match.group(1).strip().title()

    # Fall back to category-based theme
    theme_map = {
        RecommendationCategory.ESTABLISH: "Establish New Body",
        RecommendationCategory.IMPLEMENT: "Implementation Initiative",
        RecommendationCategory.MANDATE: "Policy Mandate",
        RecommendationCategory.AMEND: "Amendment Proposal",
        RecommendationCategory.INVESTIGATE: "Investigation/Research",
        RecommendationCategory.PILOT: "Pilot Program",
        RecommendationCategory.EDUCATE: "Education/Training Initiative",
        RecommendationCategory.REVIEW: "Review Procedure",
        RecommendationCategory.OTHER: "General Recommendation",
    }

    return theme_map.get(rec.category, "General Recommendation")


def _refine_cluster_theme(cluster: RecommendationCluster) -> str:
    """Refine cluster theme based on all members."""
    # Find common terms across all recommendations
    all_text = " ".join(r.summary for r in cluster.recommendations)

    # Look for specific entity mentions
    patterns = [
        (r"(AI\s+Ethics\s+Council)", "AI Ethics Council"),
        (r"(Oversight\s+(?:Council|Committee|Body))", "Oversight Body"),
        (
            r"(Risk\s+Assessment\s+(?:Framework|Protocol|System))",
            "Risk Assessment Framework",
        ),
        (r"(Human[- ]in[- ](?:the[- ])?Loop)", "Human-in-the-Loop Protocol"),
        (r"(Audit\s+(?:Trail|System|Protocol))", "Audit System"),
        (r"(Training\s+(?:Program|Initiative|Curriculum))", "Training Program"),
        (r"(Task\s+Force)", "Task Force"),
        (r"(Ethics\s+(?:Council|Panel|Committee))", "Ethics Council"),
        (r"(Governance\s+(?:Framework|Model))", "Governance Framework"),
    ]

    for pattern, theme in patterns:
        if re.search(pattern, all_text, re.IGNORECASE):
            return theme

    # Fall back to keyword-based theme
    if "oversight" in cluster.keywords:
        return "Oversight Mechanism"
    if "ethics" in cluster.keywords:
        return "Ethics Framework"
    if "risk" in cluster.keywords:
        return "Risk Management"
    if "transparency" in cluster.keywords:
        return "Transparency Protocol"
    if "education" in cluster.keywords:
        return "Education Initiative"

    # Keep original theme
    return cluster.theme


# =============================================================================
# Secretary Service
# =============================================================================


@dataclass
class SecretaryConfig:
    """Configuration for Secretary operations."""

    # Extraction settings
    min_recommendation_length: int = 20  # Minimum chars for valid recommendation
    max_recommendation_length: int = 500  # Maximum chars to capture

    # Clustering settings
    similarity_threshold: float = 0.3  # Minimum similarity to cluster
    min_cluster_size_for_queue: int = 3  # Minimum Archons for Motion Seed queue

    # Output settings
    output_dir: Path = Path("_bmad-output/secretary")


class SecretaryService:
    """Automated Conclave transcript processor.

    Extracts recommendations, clusters them, and generates:
    - Recommendations Register (all ideas)
    - Motion Queue (high-consensus for next Conclave)
    - Task Registry (operational items)
    - Conflict Report (contradictory positions)

    Supports two modes:
    1. Regex-based extraction (deterministic, fast)
    2. LLM-enhanced extraction via CrewAI (nuanced, thorough)
    """

    def __init__(
        self,
        config: SecretaryConfig | None = None,
        secretary_agent: SecretaryAgentProtocol | None = None,
    ):
        """Initialize the Secretary service.

        Args:
            config: Service configuration
            secretary_agent: Optional LLM-powered agent for enhanced extraction.
                If provided, enables async process_transcript_enhanced().
        """
        self._config = config or SecretaryConfig()
        self._config.output_dir.mkdir(parents=True, exist_ok=True)
        self._secretary_agent = secretary_agent

    @property
    def has_agent(self) -> bool:
        """Check if LLM agent is available for enhanced processing."""
        return self._secretary_agent is not None

    # =========================================================================
    # Main Processing
    # =========================================================================

    def process_transcript(
        self,
        transcript_path: str | Path,
        session_id: UUID,
        session_name: str,
    ) -> SecretaryReport:
        """Process a Conclave transcript and generate full analysis.

        Args:
            transcript_path: Path to the markdown transcript
            session_id: UUID of the source Conclave session
            session_name: Human-readable session name

        Returns:
            Complete SecretaryReport with all analysis
        """
        start_time = time.time()
        logger.info(f"Processing transcript: {transcript_path}")

        # Initialize report
        report = SecretaryReport.create(
            session_id=session_id,
            session_name=session_name,
            transcript_path=str(transcript_path),
        )

        # Load transcript
        transcript_content = Path(transcript_path).read_text(encoding="utf-8")
        lines = transcript_content.split("\n")

        # Parse speeches from transcript
        speeches = self._parse_speeches(lines)
        report.total_speeches_analyzed = len(speeches)

        logger.info(f"Found {len(speeches)} speeches to analyze")

        # Extract recommendations from each speech
        for speech in speeches:
            recommendations = self._extract_recommendations_from_speech(speech)
            report.recommendations.extend(recommendations)

        report.total_recommendations_extracted = len(report.recommendations)
        logger.info(f"Extracted {len(report.recommendations)} recommendations")

        # Cluster similar recommendations
        report.clusters = cluster_recommendations(
            report.recommendations,
            similarity_threshold=self._config.similarity_threshold,
        )
        logger.info(f"Formed {len(report.clusters)} clusters")

        # Generate Motion Seed queue from high-consensus clusters
        for cluster in report.clusters:
            if cluster.archon_count >= self._config.min_cluster_size_for_queue:
                if cluster.recommendation_type == RecommendationType.POLICY:
                    motion = QueuedMotion.from_cluster(
                        cluster, session_id, session_name
                    )
                    report.motion_queue.append(motion)
                else:
                    # Task-type recommendations go to task registry
                    task = TaskItem.from_cluster(cluster, session_id)
                    report.task_registry.append(task)

        logger.info(
            f"Queued {len(report.motion_queue)} motions, {len(report.task_registry)} tasks"
        )

        # Detect conflicts (opposing stances on similar topics)
        report.conflict_report = self._detect_conflicts(report.recommendations)
        logger.info(f"Detected {len(report.conflict_report)} conflicts")

        # Compute statistics
        report.compute_statistics()
        report.processing_duration_seconds = time.time() - start_time

        logger.info(f"Processing complete in {report.processing_duration_seconds:.2f}s")

        return report

    # =========================================================================
    # Speech Parsing
    # =========================================================================

    @dataclass
    class ParsedSpeech:
        """A parsed speech from the transcript."""

        archon_id: str
        archon_name: str
        archon_rank: str
        content: str
        line_number: int
        timestamp: datetime
        stance: str | None = None
        motion_context: str | None = None

    def _parse_speeches(self, lines: list[str]) -> list[ParsedSpeech]:
        """Parse individual speeches from transcript lines."""
        speeches: list[SecretaryService.ParsedSpeech] = []
        current_speech_lines: list[str] = []
        current_speaker: str | None = None
        current_line_start: int = 0
        current_timestamp: datetime | None = None

        # Pattern for speech headers: **[HH:MM:SS] Archon_Name:**
        speech_header = re.compile(r"\*\*\[(\d{2}:\d{2}:\d{2})\]\s+([^:*]+):\*\*")

        # Pattern for procedural entries (skip these)
        procedural = re.compile(r"\*\*\[\d{2}:\d{2}:\d{2}\]\s+\[PROCEDURAL\]")

        # Pattern for vote entries (skip these)
        vote_pattern = re.compile(r"Vote:\s*(?:AYE|NAY|ABSTAIN)", re.IGNORECASE)

        for i, line in enumerate(lines):
            # Skip procedural entries
            if procedural.match(line):
                continue

            # Skip vote entries
            if vote_pattern.search(line):
                continue

            # Check for new speech header
            header_match = speech_header.match(line)
            if header_match:
                # Save previous speech if exists
                if current_speaker and current_speech_lines:
                    speech_content = "\n".join(current_speech_lines).strip()
                    if len(speech_content) >= self._config.min_recommendation_length:
                        speeches.append(
                            self.ParsedSpeech(
                                archon_id=current_speaker.lower().replace(" ", "_"),
                                archon_name=current_speaker,
                                archon_rank=self._infer_rank(speech_content),
                                content=speech_content,
                                line_number=current_line_start,
                                timestamp=current_timestamp
                                or datetime.now(timezone.utc),
                                stance=self._extract_stance(speech_content),
                            )
                        )

                # Start new speech
                time_str = header_match.group(1)
                current_speaker = header_match.group(2).strip()
                current_line_start = i + 1
                current_speech_lines = []

                # Parse timestamp (assume today's date)
                try:
                    h, m, s = map(int, time_str.split(":"))
                    current_timestamp = datetime.now(timezone.utc).replace(
                        hour=h, minute=m, second=s, microsecond=0
                    )
                except ValueError:
                    current_timestamp = datetime.now(timezone.utc)

            elif current_speaker:
                # Continue current speech
                current_speech_lines.append(line)

        # Don't forget the last speech
        if current_speaker and current_speech_lines:
            speech_content = "\n".join(current_speech_lines).strip()
            if len(speech_content) >= self._config.min_recommendation_length:
                speeches.append(
                    self.ParsedSpeech(
                        archon_id=current_speaker.lower().replace(" ", "_"),
                        archon_name=current_speaker,
                        archon_rank=self._infer_rank(speech_content),
                        content=speech_content,
                        line_number=current_line_start,
                        timestamp=current_timestamp or datetime.now(timezone.utc),
                        stance=self._extract_stance(speech_content),
                    )
                )

        return speeches

    def _infer_rank(self, content: str) -> str:
        """Infer Archon rank from speech content mentions."""
        rank_patterns = [
            (r"Executive\s+Director", "executive_director"),
            (r"Senior\s+Director", "senior_director"),
            (r"Managing\s+Director", "managing_director"),
            (r"Strategic\s+Director", "strategic_director"),
            (r"Director", "director"),
        ]

        for pattern, rank in rank_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return rank

        return "unknown"

    def _extract_stance(self, content: str) -> str | None:
        """Extract voting stance from speech content."""
        for pattern, stance in STANCE_PATTERNS:
            if pattern.search(content):
                return stance
        return None

    # =========================================================================
    # Recommendation Extraction
    # =========================================================================

    def _extract_recommendations_from_speech(
        self,
        speech: ParsedSpeech,
    ) -> list[ExtractedRecommendation]:
        """Extract all recommendations from a single speech."""
        recommendations: list[ExtractedRecommendation] = []

        # Try each extraction pattern
        for pattern_def in EXTRACTION_PATTERNS:
            matches = pattern_def.pattern.findall(speech.content)

            for match in matches:
                # Handle tuple matches from capture groups
                if isinstance(match, tuple):
                    raw_text = " ".join(str(m) for m in match if m)
                else:
                    raw_text = str(match)

                # Clean and validate
                raw_text = raw_text.strip()
                if len(raw_text) < self._config.min_recommendation_length:
                    continue
                if len(raw_text) > self._config.max_recommendation_length:
                    raw_text = (
                        raw_text[: self._config.max_recommendation_length] + "..."
                    )

                # Create source reference
                source = SourceReference.create(
                    archon_id=speech.archon_id,
                    archon_name=speech.archon_name,
                    archon_rank=speech.archon_rank,
                    line_number=speech.line_number,
                    timestamp=speech.timestamp,
                    raw_text=raw_text,
                )

                # Extract keywords
                keywords = extract_keywords(raw_text)

                # Create recommendation
                rec = ExtractedRecommendation.create(
                    source=source,
                    category=pattern_def.category,
                    recommendation_type=pattern_def.recommendation_type,
                    summary=self._normalize_summary(raw_text),
                    keywords=keywords,
                    stance=speech.stance,
                )

                recommendations.append(rec)

        # Deduplicate within same speech
        return self._dedupe_recommendations(recommendations)

    def _normalize_summary(self, text: str) -> str:
        """Normalize recommendation text for comparison."""
        # Remove markdown formatting
        text = re.sub(r"\*+", "", text)

        # Remove multiple whitespace
        text = re.sub(r"\s+", " ", text)

        # Capitalize first letter
        text = text.strip()
        if text:
            text = text[0].upper() + text[1:]

        return text

    def _dedupe_recommendations(
        self,
        recommendations: list[ExtractedRecommendation],
    ) -> list[ExtractedRecommendation]:
        """Remove duplicate recommendations from same speech."""
        seen: set[str] = set()
        unique: list[ExtractedRecommendation] = []

        for rec in recommendations:
            # Create a signature for deduplication
            sig = rec.summary.lower()[:100]
            if sig not in seen:
                seen.add(sig)
                unique.append(rec)

        return unique

    # =========================================================================
    # Conflict Detection
    # =========================================================================

    def _detect_conflicts(
        self,
        recommendations: list[ExtractedRecommendation],
    ) -> list[ConflictingPosition]:
        """Detect conflicting positions between Archons."""
        conflicts: list[ConflictingPosition] = []

        # Group recommendations by keywords (potential topic overlap)
        by_topic: dict[str, list[ExtractedRecommendation]] = defaultdict(list)
        for rec in recommendations:
            for kw in rec.keywords:
                by_topic[kw].append(rec)

        # Look for opposing stances on same topic
        for topic, topic_recs in by_topic.items():
            for_recs = [r for r in topic_recs if r.stance == "FOR"]
            against_recs = [r for r in topic_recs if r.stance == "AGAINST"]

            # Create conflicts between opposing stances
            for for_rec in for_recs:
                for against_rec in against_recs:
                    # Skip if same Archon
                    if for_rec.source.archon_id == against_rec.source.archon_id:
                        continue

                    # Check if they're discussing similar things
                    sim = compute_similarity(for_rec, against_rec)
                    if sim > 0.2:  # Some topical overlap
                        conflict = ConflictingPosition.create(
                            theme=f"Opposing views on {topic}",
                            position_a=for_rec,
                            position_b=against_rec,
                        )
                        conflicts.append(conflict)

        return conflicts

    # =========================================================================
    # Output Generation
    # =========================================================================

    def generate_recommendations_register(
        self,
        report: SecretaryReport,
    ) -> str:
        """Generate markdown Recommendations Register."""
        lines = [
            "# Recommendations Register",
            "",
            f"**Source Session:** {report.source_session_name}",
            f"**Generated:** {report.generated_at.isoformat()}",
            f"**Total Recommendations:** {report.total_recommendations_extracted}",
            f"**Clusters Formed:** {len(report.clusters)}",
            "",
            "---",
            "",
        ]

        # Group clusters by consensus level
        for level in ["critical", "high", "medium", "low", "single"]:
            level_clusters = [
                c for c in report.clusters if c.consensus_level.value == level
            ]

            if level_clusters:
                lines.append(
                    f"## {level.upper()} Consensus ({len(level_clusters)} clusters)"
                )
                lines.append("")

                for cluster in level_clusters:
                    lines.append(f"### {cluster.theme}")
                    lines.append("")
                    lines.append(
                        f"**Archons ({cluster.archon_count}):** {', '.join(cluster.archon_names)}"
                    )
                    lines.append("")
                    lines.append(f"**Summary:** {cluster.canonical_summary}")
                    lines.append("")
                    lines.append(f"**Keywords:** {', '.join(cluster.keywords)}")
                    lines.append("")
                    lines.append("---")
                    lines.append("")

        return "\n".join(lines)

    def generate_motion_queue_markdown(
        self,
        report: SecretaryReport,
    ) -> str:
        """Generate markdown Motion Queue for next Conclave."""
        lines = [
            "# Motion Queue",
            "",
            f"**Source Session:** {report.source_session_name}",
            f"**Generated:** {report.generated_at.isoformat()}",
            f"**Total Queued Motions:** {len(report.motion_queue)}",
            "",
            "---",
            "",
        ]

        for i, motion in enumerate(report.motion_queue, 1):
            lines.append(f"## Motion {i}: {motion.title}")
            lines.append("")
            lines.append(f"**Status:** {motion.status.value}")
            lines.append(f"**Consensus Level:** {motion.consensus_level.value}")
            lines.append(
                f"**Original Supporters ({motion.original_archon_count}):** {', '.join(motion.supporting_archons)}"
            )
            lines.append("")
            lines.append("### Motion Text")
            lines.append("")
            lines.append(motion.text)
            lines.append("")
            lines.append(f"**Rationale:** {motion.rationale}")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def save_report(self, report: SecretaryReport) -> Path:
        """Save complete report and artifacts to disk."""
        # Create session output directory
        session_dir = self._config.output_dir / str(report.source_session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save recommendations register
        register_path = session_dir / "recommendations-register.md"
        register_path.write_text(
            self.generate_recommendations_register(report),
            encoding="utf-8",
        )

        # Save Motion Seed queue
        queue_path = session_dir / "motion-queue.md"
        queue_path.write_text(
            self.generate_motion_queue_markdown(report),
            encoding="utf-8",
        )

        # Save summary JSON
        summary_path = session_dir / "secretary-report.json"
        import json

        summary_path.write_text(
            json.dumps(report.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

        logger.info(f"Saved Secretary report to {session_dir}")
        return session_dir

    # =========================================================================
    # LLM-Enhanced Processing (CrewAI)
    # =========================================================================

    async def process_transcript_enhanced(
        self,
        transcript_path: str | Path,
        session_id: UUID,
        session_name: str,
    ) -> SecretaryReport:
        """Process transcript with LLM enhancement for nuanced extraction.

        Uses the CrewAI-powered SecretaryAgent for:
        - Better understanding of nuanced recommendations
        - Double-checking each statement for completeness
        - Semantic clustering beyond keyword overlap
        - Conflict detection with resolution suggestions
        - Motion text generation

        Falls back to regex-based extraction if no agent is configured.

        Args:
            transcript_path: Path to the markdown transcript
            session_id: UUID of the source Conclave session
            session_name: Human-readable session name

        Returns:
            Complete SecretaryReport with enhanced analysis
        """
        if not self._secretary_agent:
            logger.warning(
                "No secretary agent configured, falling back to regex extraction"
            )
            return self.process_transcript(transcript_path, session_id, session_name)

        from src.application.ports.secretary_agent import SpeechContext

        start_time = time.time()
        logger.info(f"Processing transcript with LLM enhancement: {transcript_path}")

        # Initialize report
        report = SecretaryReport.create(
            session_id=session_id,
            session_name=session_name,
            transcript_path=str(transcript_path),
        )

        # Load transcript
        transcript_content = Path(transcript_path).read_text(encoding="utf-8")
        lines = transcript_content.split("\n")

        # Parse speeches from transcript
        parsed_speeches = self._parse_speeches(lines)
        report.total_speeches_analyzed = len(parsed_speeches)

        logger.info(f"Found {len(parsed_speeches)} speeches for LLM analysis")

        # Convert to SpeechContext for the agent
        speech_contexts = [
            SpeechContext(
                archon_name=speech.archon_name,
                archon_id=speech.archon_id,
                speech_content=speech.content,
                motion_context=speech.motion_context,
                line_start=speech.line_number,
                line_end=speech.line_number + len(speech.content.split("\n")),
            )
            for speech in parsed_speeches
        ]

        # Use the LLM agent for full processing
        result = await self._secretary_agent.process_full_transcript(
            speeches=speech_contexts,
            session_id=str(session_id),
            session_name=session_name,
        )

        # Map results to report
        report.recommendations = result.recommendations
        report.total_recommendations_extracted = len(result.recommendations)
        report.clusters = result.clusters
        report.conflict_report = result.conflicts

        # Generate Motion Seed queue from high-consensus clusters
        for motion in result.motions:
            report.motion_queue.append(motion)

        # Generate task registry from task-type clusters
        for cluster in report.clusters:
            if cluster.recommendation_type == RecommendationType.TASK:
                if cluster.archon_count >= self._config.min_cluster_size_for_queue:
                    task = TaskItem.from_cluster(cluster, session_id)
                    report.task_registry.append(task)

        logger.info(
            f"LLM extraction complete: {len(report.recommendations)} recommendations, "
            f"{len(report.clusters)} clusters, {len(report.motion_queue)} motions"
        )

        # Compute statistics
        report.compute_statistics()
        report.processing_duration_seconds = time.time() - start_time

        logger.info(
            f"Enhanced processing complete in {report.processing_duration_seconds:.2f}s"
        )

        return report
