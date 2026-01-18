"""Secretary DTOs for application layer.

Application-layer DTOs for Secretary operations including transcript processing,
recommendation extraction, clustering, and motion queue management.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> comprehensive error DTOs
- CT-12: Witnessing creates accountability -> full traceability in outputs
- FR9: All outputs through witnessing pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class ProcessTranscriptRequestDTO:
    """Request to process a Conclave transcript.

    Attributes:
        transcript_path: Path to the markdown transcript file.
        session_id: UUID of the source Conclave session.
        session_name: Human-readable session name.
        min_consensus_for_queue: Minimum Archon count for motion queue promotion.
        enable_conflict_detection: Whether to detect contradictory positions.
    """

    transcript_path: str
    session_id: UUID
    session_name: str
    min_consensus_for_queue: int = 3
    enable_conflict_detection: bool = True


@dataclass
class EndorseMotionRequestDTO:
    """Request to endorse a queued motion.

    Attributes:
        queued_motion_id: UUID of the queued motion to endorse.
        archon_id: ID of the endorsing Archon.
        archon_name: Name of the endorsing Archon.
    """

    queued_motion_id: UUID
    archon_id: str
    archon_name: str


@dataclass
class PromoteMotionRequestDTO:
    """Request to promote a queued motion to Conclave agenda.

    Attributes:
        queued_motion_id: UUID of the motion to promote.
        target_conclave_id: UUID of the target Conclave session.
    """

    queued_motion_id: UUID
    target_conclave_id: UUID


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class ExtractedRecommendationDTO:
    """DTO for a single extracted recommendation.

    Attributes:
        recommendation_id: Unique identifier.
        archon_id: Source Archon ID.
        archon_name: Source Archon name.
        archon_rank: Source Archon rank.
        line_number: Line in transcript.
        category: Recommendation category.
        recommendation_type: Policy vs task.
        summary: Normalized recommendation text.
        keywords: Extracted keywords.
        stance: FOR/AGAINST/NEUTRAL on motion.
        raw_text: Original source text.
    """

    recommendation_id: UUID
    archon_id: str
    archon_name: str
    archon_rank: str
    line_number: int
    category: str
    recommendation_type: str
    summary: str
    keywords: list[str]
    stance: str | None
    raw_text: str


@dataclass
class RecommendationClusterDTO:
    """DTO for a cluster of similar recommendations.

    Attributes:
        cluster_id: Unique identifier.
        theme: Human-readable cluster theme.
        canonical_summary: Best representative summary.
        category: Primary category.
        recommendation_type: Policy vs task.
        archon_count: Number of supporting Archons.
        consensus_level: HIGH/MEDIUM/LOW/SINGLE.
        archon_names: List of supporting Archon names.
        keywords: Combined keywords.
        recommendation_ids: Member recommendation IDs.
    """

    cluster_id: UUID
    theme: str
    canonical_summary: str
    category: str
    recommendation_type: str
    archon_count: int
    consensus_level: str
    archon_names: list[str]
    keywords: list[str]
    recommendation_ids: list[UUID]


@dataclass
class QueuedMotionDTO:
    """DTO for a motion in the queue.

    Attributes:
        queued_motion_id: Unique identifier.
        status: PENDING/ENDORSED/MERGED/DEFERRED/PROMOTED/WITHDRAWN.
        title: Motion title.
        text: Full motion text.
        rationale: Why this motion was generated.
        original_archon_count: Initial supporter count.
        consensus_level: Consensus level.
        supporting_archons: Original supporting Archon names.
        endorsement_count: Additional endorsements received.
        endorsements: Names of endorsing Archons.
        source_session_name: Source Conclave name.
        created_at: When queued.
    """

    queued_motion_id: UUID
    status: str
    title: str
    text: str
    rationale: str
    original_archon_count: int
    consensus_level: str
    supporting_archons: list[str]
    endorsement_count: int
    endorsements: list[str]
    source_session_name: str
    created_at: datetime


@dataclass
class TaskItemDTO:
    """DTO for an operational task.

    Attributes:
        task_id: Unique identifier.
        title: Task title.
        description: Task description.
        category: Task category.
        source_archons: Archons who proposed this.
        status: pending/assigned/in_progress/completed.
        assigned_to: Assigned workgroup/Archon.
        created_at: When created.
    """

    task_id: UUID
    title: str
    description: str
    category: str
    source_archons: list[str]
    status: str
    assigned_to: str | None
    created_at: datetime


@dataclass
class ConflictDTO:
    """DTO for a conflicting position pair.

    Attributes:
        conflict_id: Unique identifier.
        theme: What the conflict is about.
        position_a_archon: First Archon's name.
        position_a_summary: First position summary.
        position_b_archon: Second Archon's name.
        position_b_summary: Second position summary.
        resolved: Whether conflict has been resolved.
    """

    conflict_id: UUID
    theme: str
    position_a_archon: str
    position_a_summary: str
    position_b_archon: str
    position_b_summary: str
    resolved: bool


@dataclass
class SecretaryReportDTO:
    """DTO for the complete Secretary analysis report.

    Attributes:
        report_id: Unique identifier.
        source_session_id: Source Conclave session.
        source_session_name: Source Conclave name.
        generated_at: When report was generated.
        processing_duration_seconds: Processing time.
        total_speeches_analyzed: Number of speeches processed.
        total_recommendations_extracted: Total recommendations found.
        cluster_count: Number of clusters formed.
        motion_queue_count: Motions queued for next Conclave.
        task_registry_count: Tasks created.
        conflict_count: Conflicts detected.
        clusters_by_consensus: Breakdown by consensus level.
        recommendations_by_category: Breakdown by category.
    """

    report_id: UUID
    source_session_id: UUID
    source_session_name: str
    generated_at: datetime
    processing_duration_seconds: float
    total_speeches_analyzed: int
    total_recommendations_extracted: int
    cluster_count: int
    motion_queue_count: int
    task_registry_count: int
    conflict_count: int
    clusters_by_consensus: dict[str, int]
    recommendations_by_category: dict[str, int]


@dataclass
class ProcessTranscriptResponseDTO:
    """Response from transcript processing.

    Attributes:
        success: Whether processing succeeded.
        report: The generated report DTO.
        recommendations: All extracted recommendations.
        clusters: Formed clusters.
        motion_queue: Queued motions.
        task_registry: Created tasks.
        conflicts: Detected conflicts.
        errors: Any errors encountered.
    """

    success: bool
    report: SecretaryReportDTO
    recommendations: list[ExtractedRecommendationDTO]
    clusters: list[RecommendationClusterDTO]
    motion_queue: list[QueuedMotionDTO]
    task_registry: list[TaskItemDTO]
    conflicts: list[ConflictDTO]
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Pydantic Models for API Layer
# =============================================================================


class ProcessTranscriptRequest(BaseModel):
    """API request to process a Conclave transcript.

    Attributes:
        transcript_path: Path to the markdown transcript file.
        session_id: UUID of the source Conclave session.
        session_name: Human-readable session name.
        min_consensus_for_queue: Minimum Archon count for motion queue.
        enable_conflict_detection: Whether to detect conflicts.
    """

    transcript_path: str = Field(description="Path to transcript markdown file")
    session_id: UUID = Field(description="Source Conclave session ID")
    session_name: str = Field(description="Source Conclave session name")
    min_consensus_for_queue: int = Field(
        default=3,
        ge=1,
        le=72,
        description="Minimum Archons for motion queue promotion",
    )
    enable_conflict_detection: bool = Field(
        default=True,
        description="Whether to detect contradictory positions",
    )


class RecommendationClusterResponse(BaseModel):
    """API response for a recommendation cluster.

    Attributes:
        cluster_id: Unique identifier.
        theme: Human-readable theme.
        canonical_summary: Best representative summary.
        category: Primary category.
        archon_count: Number of supporting Archons.
        consensus_level: Consensus level string.
        archon_names: List of supporting Archon names.
        keywords: Combined keywords.
    """

    cluster_id: UUID
    theme: str = Field(description="Human-readable cluster theme")
    canonical_summary: str = Field(description="Best representative summary")
    category: str = Field(description="Recommendation category")
    archon_count: int = Field(description="Number of supporting Archons")
    consensus_level: str = Field(
        description="Consensus level (critical/high/medium/low/single)"
    )
    archon_names: list[str] = Field(description="Names of supporting Archons")
    keywords: list[str] = Field(description="Keywords from all recommendations")


class QueuedMotionResponse(BaseModel):
    """API response for a queued motion.

    Attributes:
        queued_motion_id: Unique identifier.
        status: Current status.
        title: Motion title.
        text: Full motion text.
        rationale: Generation rationale.
        original_archon_count: Initial supporter count.
        consensus_level: Consensus level.
        supporting_archons: Original supporters.
        endorsement_count: Additional endorsements.
        source_session_name: Source Conclave.
        created_at: Creation timestamp.
    """

    queued_motion_id: UUID
    status: str = Field(description="Motion status")
    title: str = Field(description="Motion title")
    text: str = Field(description="Full motion text")
    rationale: str = Field(description="Why this motion was generated")
    original_archon_count: int = Field(description="Initial supporter count")
    consensus_level: str = Field(description="Consensus level")
    supporting_archons: list[str] = Field(description="Original supporters")
    endorsement_count: int = Field(default=0, description="Additional endorsements")
    source_session_name: str = Field(description="Source Conclave name")
    created_at: datetime = Field(description="When queued")


class SecretaryReportResponse(BaseModel):
    """API response for Secretary report summary.

    Attributes:
        report_id: Unique identifier.
        source_session_name: Source Conclave name.
        generated_at: Generation timestamp.
        processing_duration_seconds: Processing time.
        total_speeches_analyzed: Speeches processed.
        total_recommendations_extracted: Recommendations found.
        cluster_count: Clusters formed.
        motion_queue_count: Motions queued.
        task_registry_count: Tasks created.
        conflict_count: Conflicts detected.
        clusters_by_consensus: Breakdown by consensus.
        recommendations_by_category: Breakdown by category.
    """

    report_id: UUID
    source_session_name: str = Field(description="Source Conclave name")
    generated_at: datetime = Field(description="Report generation time")
    processing_duration_seconds: float = Field(description="Processing duration")
    total_speeches_analyzed: int = Field(description="Speeches analyzed")
    total_recommendations_extracted: int = Field(
        description="Recommendations extracted"
    )
    cluster_count: int = Field(description="Clusters formed")
    motion_queue_count: int = Field(description="Motions queued")
    task_registry_count: int = Field(description="Tasks created")
    conflict_count: int = Field(description="Conflicts detected")
    clusters_by_consensus: dict[str, int] = Field(
        description="Clusters by consensus level"
    )
    recommendations_by_category: dict[str, int] = Field(
        description="Recommendations by category"
    )


class MotionQueueResponse(BaseModel):
    """API response for the full motion queue.

    Attributes:
        total_count: Total motions in queue.
        pending_count: Motions awaiting next Conclave.
        endorsed_count: Motions with endorsements.
        motions: List of queued motions.
    """

    total_count: int = Field(description="Total motions in queue")
    pending_count: int = Field(description="Pending motions")
    endorsed_count: int = Field(description="Endorsed motions")
    motions: list[QueuedMotionResponse] = Field(description="Queued motions")


class EndorseMotionRequest(BaseModel):
    """API request to endorse a queued motion.

    Attributes:
        archon_id: ID of endorsing Archon.
        archon_name: Name of endorsing Archon.
    """

    archon_id: str = Field(description="Endorsing Archon ID")
    archon_name: str = Field(description="Endorsing Archon name")


class EndorseMotionResponse(BaseModel):
    """API response after endorsing a motion.

    Attributes:
        success: Whether endorsement succeeded.
        queued_motion_id: The endorsed motion ID.
        new_endorsement_count: Updated endorsement count.
        message: Status message.
    """

    success: bool
    queued_motion_id: UUID
    new_endorsement_count: int
    message: str
