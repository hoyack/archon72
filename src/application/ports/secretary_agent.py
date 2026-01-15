"""Port definition for Secretary agent operations.

This port defines the interface for LLM-enhanced transcript processing.
Implementations may use CrewAI, direct LLM calls, or mock implementations
for testing.

The Secretary agent performs multi-step analysis:
1. Extract recommendations from speeches
2. Validate extractions for completeness
3. Cluster semantically similar recommendations
4. Detect conflicting positions
5. Generate formal motion text
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.secretary import (
        ConflictingPosition,
        ExtractedRecommendation,
        QueuedMotion,
        RecommendationCluster,
    )


@dataclass
class SpeechContext:
    """Context for a single Archon speech to be analyzed."""

    archon_name: str
    archon_id: str
    speech_content: str
    motion_context: str | None = None
    line_start: int = 0
    line_end: int = 0


@dataclass
class ExtractionResult:
    """Result of recommendation extraction from a speech."""

    recommendations: list[ExtractedRecommendation]
    missed_count: int = 0  # Estimated missed recommendations (from validation)
    confidence: float = 1.0  # Overall extraction confidence


@dataclass
class ClusteringResult:
    """Result of semantic clustering."""

    clusters: list[RecommendationCluster]
    unclustered: list[ExtractedRecommendation]  # Recommendations that didn't fit


@dataclass
class ConflictResult:
    """Result of conflict detection."""

    conflicts: list[ConflictingPosition]
    resolution_suggestions: list[str]


class SecretaryAgentProtocol(ABC):
    """Port for Secretary agent operations using LLM enhancement.

    This protocol defines the interface for LLM-powered transcript analysis.
    Implementations handle the actual CrewAI or LLM invocation details.

    Constitutional Compliance:
    - CT-11: All operations must be logged, failures reported
    - CT-12: All extractions must trace to source lines
    """

    @abstractmethod
    async def extract_recommendations(
        self,
        speech: SpeechContext,
    ) -> ExtractionResult:
        """Extract recommendations from a single Archon speech.

        Uses LLM to identify all recommendations with nuanced understanding,
        including implicit suggestions and action items.

        Args:
            speech: The speech context to analyze

        Returns:
            ExtractionResult with list of recommendations and confidence

        Raises:
            SecretaryAgentError: If extraction fails
        """
        ...

    @abstractmethod
    async def validate_extractions(
        self,
        recommendations: list[ExtractedRecommendation],
        original_speeches: list[SpeechContext],
    ) -> ExtractionResult:
        """Validate and enhance extractions for completeness.

        Double-checks each extraction against source material and
        identifies any missed recommendations.

        Args:
            recommendations: Previously extracted recommendations
            original_speeches: Original speech contexts for reference

        Returns:
            ExtractionResult with validated/enhanced recommendations

        Raises:
            SecretaryAgentError: If validation fails
        """
        ...

    @abstractmethod
    async def cluster_semantically(
        self,
        recommendations: list[ExtractedRecommendation],
    ) -> ClusteringResult:
        """Cluster recommendations by semantic similarity.

        Uses LLM to identify thematic relationships beyond keyword
        overlap, grouping compatible recommendations together.

        Args:
            recommendations: List of recommendations to cluster

        Returns:
            ClusteringResult with clusters and unclustered items

        Raises:
            SecretaryAgentError: If clustering fails
        """
        ...

    @abstractmethod
    async def detect_conflicts(
        self,
        recommendations: list[ExtractedRecommendation],
    ) -> ConflictResult:
        """Detect conflicting positions between recommendations.

        Uses LLM to identify subtle conflicts and contradictions
        that may not be apparent from surface-level analysis.

        Args:
            recommendations: List of recommendations to analyze

        Returns:
            ConflictResult with detected conflicts and suggestions

        Raises:
            SecretaryAgentError: If conflict detection fails
        """
        ...

    @abstractmethod
    async def generate_motion_text(
        self,
        cluster: RecommendationCluster,
        session_context: str,
    ) -> QueuedMotion:
        """Generate formal motion text for a recommendation cluster.

        Synthesizes a formal, actionable motion from the clustered
        recommendations, suitable for the next Conclave agenda.

        Args:
            cluster: The recommendation cluster to synthesize
            session_context: Context about the originating session

        Returns:
            QueuedMotion ready for the motion queue

        Raises:
            SecretaryAgentError: If motion generation fails
        """
        ...

    @abstractmethod
    async def process_full_transcript(
        self,
        speeches: list[SpeechContext],
        session_id: str,
        session_name: str,
    ) -> FullProcessingResult:
        """Process a complete transcript through all analysis steps.

        Convenience method that runs the full pipeline:
        1. Extract from all speeches
        2. Validate extractions
        3. Cluster semantically
        4. Detect conflicts
        5. Generate motions for high-consensus clusters

        Args:
            speeches: All speeches from the transcript
            session_id: Unique session identifier
            session_name: Human-readable session name

        Returns:
            FullProcessingResult with all outputs

        Raises:
            SecretaryAgentError: If any step fails
        """
        ...


@dataclass
class FullProcessingResult:
    """Complete result from processing a transcript."""

    recommendations: list[ExtractedRecommendation]
    clusters: list[RecommendationCluster]
    conflicts: list[ConflictingPosition]
    motions: list[QueuedMotion]
    extraction_confidence: float
    processing_time_ms: int


class SecretaryAgentError(Exception):
    """Base exception for Secretary agent operations."""

    pass


class ExtractionError(SecretaryAgentError):
    """Error during recommendation extraction."""

    pass


class ValidationError(SecretaryAgentError):
    """Error during extraction validation."""

    pass


class ClusteringError(SecretaryAgentError):
    """Error during semantic clustering."""

    pass


class MotionGenerationError(SecretaryAgentError):
    """Error during motion text generation."""

    pass
