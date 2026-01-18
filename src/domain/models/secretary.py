"""Secretary domain models for Conclave post-processing.

The Automated Secretary processes Conclave transcripts to extract:
- Recommendations from Archon speeches
- Semantic clusters of similar ideas
- Motion Seed queue for next Conclave
- Task registry for operational work items
- Conflict reports for contradictory positions

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> log all operations
- CT-12: Witnessing creates accountability -> full traceability to source
- FR9: All outputs through witnessing pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class RecommendationCategory(Enum):
    """Categories of extracted recommendations."""

    ESTABLISH = "establish"  # Create new body/council/system
    IMPLEMENT = "implement"  # Build/deploy something
    MANDATE = "mandate"  # Require specific behavior
    AMEND = "amend"  # Modify existing policy/motion
    INVESTIGATE = "investigate"  # Research/explore topic
    PILOT = "pilot"  # Test in limited scope
    EDUCATE = "educate"  # Training/curriculum
    REVIEW = "review"  # Periodic assessment
    OTHER = "other"


class RecommendationType(Enum):
    """Type distinguishing policy decisions from operational tasks."""

    POLICY = "policy"  # Requires Conclave vote
    TASK = "task"  # Operational work, assignable
    AMENDMENT = "amendment"  # Modification to existing motion
    CONCERN = "concern"  # Risk or objection raised


class ConsensusLevel(Enum):
    """Consensus level based on Archon support count."""

    CRITICAL = "critical"  # 15+ Archons (supermajority interest)
    HIGH = "high"  # 8-14 Archons
    MEDIUM = "medium"  # 4-7 Archons
    LOW = "low"  # 2-3 Archons
    SINGLE = "single"  # 1 Archon only

    @classmethod
    def from_count(cls, count: int) -> ConsensusLevel:
        """Determine consensus level from supporter count."""
        if count >= 15:
            return cls.CRITICAL
        elif count >= 8:
            return cls.HIGH
        elif count >= 4:
            return cls.MEDIUM
        elif count >= 2:
            return cls.LOW
        return cls.SINGLE


class QueuedMotionStatus(Enum):
    """Status of a Motion Seed in the queue."""

    PENDING = "pending"  # Awaiting next Conclave
    ENDORSED = "endorsed"  # Received additional endorsements
    MERGED = "merged"  # Combined with similar motion
    DEFERRED = "deferred"  # Pushed to later Conclave
    PROMOTED = "promoted"  # Moved to Conclave agenda
    WITHDRAWN = "withdrawn"  # Removed from queue


@dataclass
class SourceReference:
    """Reference to source location in transcript.

    Provides full traceability per CT-12.
    """

    archon_id: str
    archon_name: str
    archon_rank: str
    line_number: int
    timestamp: datetime
    raw_text: str  # Original text containing the recommendation

    @classmethod
    def create(
        cls,
        archon_id: str,
        archon_name: str,
        archon_rank: str,
        line_number: int,
        timestamp: datetime,
        raw_text: str,
    ) -> SourceReference:
        return cls(
            archon_id=archon_id,
            archon_name=archon_name,
            archon_rank=archon_rank,
            line_number=line_number,
            timestamp=timestamp,
            raw_text=raw_text,
        )


@dataclass
class ExtractedRecommendation:
    """A single recommendation extracted from an Archon's speech.

    Each recommendation maintains full traceability to its source.
    """

    recommendation_id: UUID
    source: SourceReference
    category: RecommendationCategory
    recommendation_type: RecommendationType
    summary: str  # Normalized/cleaned recommendation text
    keywords: list[str]  # Key terms for clustering
    extracted_at: datetime

    # Linkage to motion being debated
    motion_id: UUID | None = None
    motion_title: str | None = None

    # Stance on the motion
    stance: str | None = None  # "FOR", "AGAINST", "NEUTRAL"

    @classmethod
    def create(
        cls,
        source: SourceReference,
        category: RecommendationCategory,
        recommendation_type: RecommendationType,
        summary: str,
        keywords: list[str],
        motion_id: UUID | None = None,
        motion_title: str | None = None,
        stance: str | None = None,
    ) -> ExtractedRecommendation:
        return cls(
            recommendation_id=uuid4(),
            source=source,
            category=category,
            recommendation_type=recommendation_type,
            summary=summary,
            keywords=keywords,
            extracted_at=datetime.now(timezone.utc),
            motion_id=motion_id,
            motion_title=motion_title,
            stance=stance,
        )


@dataclass
class RecommendationCluster:
    """A cluster of semantically similar recommendations.

    Clusters aggregate recommendations from multiple Archons
    that express the same or similar ideas.
    """

    cluster_id: UUID
    theme: str  # Human-readable cluster theme
    canonical_summary: str  # Best representative summary
    category: RecommendationCategory
    recommendation_type: RecommendationType
    keywords: list[str]  # Combined keywords from all members

    # Member recommendations
    recommendations: list[ExtractedRecommendation] = field(default_factory=list)

    # Consensus metrics
    archon_count: int = 0
    consensus_level: ConsensusLevel = ConsensusLevel.SINGLE

    # Archon attribution
    archon_ids: list[str] = field(default_factory=list)
    archon_names: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        theme: str,
        canonical_summary: str,
        category: RecommendationCategory,
        recommendation_type: RecommendationType,
        keywords: list[str],
    ) -> RecommendationCluster:
        return cls(
            cluster_id=uuid4(),
            theme=theme,
            canonical_summary=canonical_summary,
            category=category,
            recommendation_type=recommendation_type,
            keywords=keywords,
        )

    def add_recommendation(self, rec: ExtractedRecommendation) -> None:
        """Add a recommendation to this cluster."""
        self.recommendations.append(rec)

        # Update archon tracking
        if rec.source.archon_id not in self.archon_ids:
            self.archon_ids.append(rec.source.archon_id)
            self.archon_names.append(rec.source.archon_name)

        # Update counts and consensus
        self.archon_count = len(self.archon_ids)
        self.consensus_level = ConsensusLevel.from_count(self.archon_count)

        # Merge keywords
        for kw in rec.keywords:
            if kw not in self.keywords:
                self.keywords.append(kw)


@dataclass
class QueuedMotion:
    """A Motion Seed queued for future Conclave consideration.

    Generated from high-consensus recommendation clusters before Motion admission.
    """

    queued_motion_id: UUID
    status: QueuedMotionStatus = QueuedMotionStatus.PENDING

    # Motion content
    title: str = ""
    text: str = ""
    rationale: str = ""

    # Source cluster
    source_cluster_id: UUID | None = None
    source_cluster_theme: str = ""

    # Consensus data
    original_archon_count: int = 0
    consensus_level: ConsensusLevel = ConsensusLevel.SINGLE
    supporting_archons: list[str] = field(default_factory=list)

    # Source Conclave
    source_session_id: UUID | None = None
    source_session_name: str = ""

    # Endorsements received after initial extraction
    endorsements: list[str] = field(default_factory=list)
    endorsement_count: int = 0

    # Lifecycle tracking
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    promoted_at: datetime | None = None
    target_conclave_id: UUID | None = None

    @classmethod
    def from_cluster(
        cls,
        cluster: RecommendationCluster,
        session_id: UUID,
        session_name: str,
    ) -> QueuedMotion:
        """Create a queued Motion Seed from a recommendation cluster."""
        return cls(
            queued_motion_id=uuid4(),
            status=QueuedMotionStatus.PENDING,
            title=cluster.theme,
            text=cluster.canonical_summary,
            rationale=f"Derived from {cluster.archon_count} Archon recommendations",
            source_cluster_id=cluster.cluster_id,
            source_cluster_theme=cluster.theme,
            original_archon_count=cluster.archon_count,
            consensus_level=cluster.consensus_level,
            supporting_archons=cluster.archon_names.copy(),
            source_session_id=session_id,
            source_session_name=session_name,
        )

    def add_endorsement(self, archon_name: str) -> None:
        """Add an endorsement from an Archon."""
        if archon_name not in self.endorsements:
            self.endorsements.append(archon_name)
            self.endorsement_count = len(self.endorsements)
            if self.status == QueuedMotionStatus.PENDING:
                self.status = QueuedMotionStatus.ENDORSED


@dataclass
class TaskItem:
    """An operational task derived from recommendations.

    Tasks are actionable work items that don't require
    Conclave vote but can be assigned to workgroups.
    """

    task_id: UUID
    title: str
    description: str
    category: RecommendationCategory

    # Source tracking
    source_cluster_id: UUID | None = None
    source_archons: list[str] = field(default_factory=list)
    source_session_id: UUID | None = None

    # Assignment
    assigned_to: str | None = None
    assigned_at: datetime | None = None

    # Status
    status: str = "pending"  # pending, assigned, in_progress, completed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @classmethod
    def from_cluster(
        cls,
        cluster: RecommendationCluster,
        session_id: UUID,
    ) -> TaskItem:
        """Create a task from a recommendation cluster."""
        return cls(
            task_id=uuid4(),
            title=cluster.theme,
            description=cluster.canonical_summary,
            category=cluster.category,
            source_cluster_id=cluster.cluster_id,
            source_archons=cluster.archon_names.copy(),
            source_session_id=session_id,
        )


@dataclass
class ConflictingPosition:
    """A pair of recommendations that contradict each other."""

    conflict_id: UUID
    theme: str  # What the conflict is about

    # The conflicting positions
    position_a: ExtractedRecommendation
    position_b: ExtractedRecommendation

    # Resolution status
    resolved: bool = False
    resolution_motion_id: UUID | None = None
    resolution_notes: str = ""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        theme: str,
        position_a: ExtractedRecommendation,
        position_b: ExtractedRecommendation,
    ) -> ConflictingPosition:
        return cls(
            conflict_id=uuid4(),
            theme=theme,
            position_a=position_a,
            position_b=position_b,
        )


@dataclass
class SecretaryReport:
    """Complete Secretary analysis of a Conclave transcript.

    This is the primary output artifact containing all
    extracted and processed information.
    """

    report_id: UUID
    source_session_id: UUID
    source_session_name: str

    # Timing
    source_transcript_path: str
    generated_at: datetime
    processing_duration_seconds: float = 0.0

    # Extraction results
    total_speeches_analyzed: int = 0
    total_recommendations_extracted: int = 0

    # All extracted recommendations (pre-clustering)
    recommendations: list[ExtractedRecommendation] = field(default_factory=list)

    # Clustered recommendations
    clusters: list[RecommendationCluster] = field(default_factory=list)

    # Output queues
    motion_queue: list[QueuedMotion] = field(default_factory=list)
    task_registry: list[TaskItem] = field(default_factory=list)
    conflict_report: list[ConflictingPosition] = field(default_factory=list)

    # Summary statistics
    clusters_by_consensus: dict[str, int] = field(default_factory=dict)
    recommendations_by_category: dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: UUID,
        session_name: str,
        transcript_path: str,
    ) -> SecretaryReport:
        return cls(
            report_id=uuid4(),
            source_session_id=session_id,
            source_session_name=session_name,
            source_transcript_path=transcript_path,
            generated_at=datetime.now(timezone.utc),
        )

    def compute_statistics(self) -> None:
        """Compute summary statistics for the report."""
        # Count clusters by consensus level
        self.clusters_by_consensus = {}
        for cluster in self.clusters:
            level = cluster.consensus_level.value
            self.clusters_by_consensus[level] = (
                self.clusters_by_consensus.get(level, 0) + 1
            )

        # Count recommendations by category
        self.recommendations_by_category = {}
        for rec in self.recommendations:
            cat = rec.category.value
            self.recommendations_by_category[cat] = (
                self.recommendations_by_category.get(cat, 0) + 1
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to dictionary."""
        return {
            "report_id": str(self.report_id),
            "source_session_id": str(self.source_session_id),
            "source_session_name": self.source_session_name,
            "source_transcript_path": self.source_transcript_path,
            "generated_at": self.generated_at.isoformat(),
            "processing_duration_seconds": self.processing_duration_seconds,
            "total_speeches_analyzed": self.total_speeches_analyzed,
            "total_recommendations_extracted": self.total_recommendations_extracted,
            "cluster_count": len(self.clusters),
            "motion_queue_count": len(self.motion_queue),
            "task_registry_count": len(self.task_registry),
            "conflict_count": len(self.conflict_report),
            "clusters_by_consensus": self.clusters_by_consensus,
            "recommendations_by_category": self.recommendations_by_category,
        }
