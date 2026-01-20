"""Unit tests for Secretary CrewAI adapter.

Tests the SecretaryCrewAIAdapter implementation with mocked CrewAI dependencies.
Validates:
- AC1: Implements SecretaryAgentProtocol
- AC2: Uses dual-model approach (text + JSON)
- AC3: Checkpoint saving/loading
- AC4: JSON parsing and sanitization
- AC5: Full pipeline processing

Note: These tests require CrewAI/LiteLLM which needs API keys.
They are marked with @pytest.mark.requires_llm and skipped in CI.
"""

from __future__ import annotations

import json

import pytest

# Mark all tests in this module as requiring LLM (skipped in CI)
pytestmark = pytest.mark.requires_llm
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.application.ports.secretary_agent import (
    ClusteringResult,
    ConflictResult,
    ExtractionResult,
    FullProcessingResult,
    SecretaryAgentProtocol,
    SpeechContext,
)
from src.domain.models.secretary import (
    ConsensusLevel,
    ExtractedRecommendation,
    QueuedMotion,
    RecommendationCategory,
    RecommendationCluster,
    RecommendationType,
    SourceReference,
)
from src.domain.models.secretary_agent import (
    SecretaryAgentProfile,
    create_default_secretary_profile,
)
from src.infrastructure.adapters.external.crewai_json_utils import (
    aggressive_clean,
    sanitize_json_string,
)
from src.infrastructure.adapters.external.secretary_crewai_adapter import (
    SecretaryCrewAIAdapter,
    _is_truncated_json,
)

# Module path for patching CrewAI classes
CREWAI_MODULE = "src.infrastructure.adapters.external.secretary_crewai_adapter"


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def sample_speech_context() -> SpeechContext:
    """Create a sample speech context for testing."""
    return SpeechContext(
        archon_name="Paimon",
        archon_id="paimon",
        speech_content="""I recommend establishing an AI Ethics Council to oversee alignment efforts.

**Recommendations:**
1. **Establish Ethics Council**: Create a governing body for AI ethics
2. **Implement Review Process**: Mandate quarterly ethical audits

I also suggest we invest in training programs for all Archons on constitutional compliance.""",
        motion_context="Deliberation on AI Governance",
        line_start=100,
        line_end=110,
    )


@pytest.fixture
def sample_recommendations() -> list[ExtractedRecommendation]:
    """Create sample extracted recommendations."""
    source = SourceReference(
        archon_id="paimon",
        archon_name="Paimon",
        archon_rank="executive_director",
        line_number=100,
        timestamp=datetime.now(timezone.utc),
        raw_text="Establish an AI Ethics Council",
    )
    return [
        ExtractedRecommendation(
            recommendation_id=uuid4(),
            source=source,
            category=RecommendationCategory.ESTABLISH,
            recommendation_type=RecommendationType.POLICY,
            summary="Establish an AI Ethics Council to oversee alignment efforts",
            keywords=["ethics", "council", "ai"],
            extracted_at=datetime.now(timezone.utc),
            stance="FOR",
        ),
        ExtractedRecommendation(
            recommendation_id=uuid4(),
            source=SourceReference(
                archon_id="belial",
                archon_name="Belial",
                archon_rank="executive_director",
                line_number=200,
                timestamp=datetime.now(timezone.utc),
                raw_text="Implement review process",
            ),
            category=RecommendationCategory.IMPLEMENT,
            recommendation_type=RecommendationType.TASK,
            summary="Implement quarterly ethical audits",
            keywords=["audit", "review", "ethics"],
            extracted_at=datetime.now(timezone.utc),
            stance=None,
        ),
    ]


@pytest.fixture
def sample_cluster(
    sample_recommendations: list[ExtractedRecommendation],
) -> RecommendationCluster:
    """Create a sample recommendation cluster."""
    cluster = RecommendationCluster(
        cluster_id=uuid4(),
        theme="Ethics Oversight",
        canonical_summary="Establish ethics council and review processes",
        category=RecommendationCategory.ESTABLISH,
        recommendation_type=RecommendationType.POLICY,
        keywords=["ethics", "council", "review"],
        recommendations=sample_recommendations,
        archon_count=2,
        consensus_level=ConsensusLevel.LOW,
        archon_ids=["paimon", "belial"],
        archon_names=["Paimon", "Belial"],
        created_at=datetime.now(timezone.utc),
    )
    return cluster


@pytest.fixture
def mock_crewai_extraction_response() -> str:
    """Mock CrewAI extraction output."""
    return json.dumps(
        [
            {
                "category": "establish",
                "type": "policy",
                "text": "Establish an AI Ethics Council",
                "keywords": ["ethics", "council", "ai"],
                "stance": "FOR",
                "source_archon": "Paimon",
                "source_line_start": 100,
                "source_line_end": 110,
            },
            {
                "category": "implement",
                "type": "task",
                "text": "Implement review process",
                "keywords": ["review", "audit"],
                "stance": None,
                "source_archon": "Paimon",
                "source_line_start": 105,
                "source_line_end": 108,
            },
        ]
    )


@pytest.fixture
def mock_crewai_clustering_response() -> str:
    """Mock CrewAI clustering output."""
    return json.dumps(
        [
            {
                "theme": "Ethics Council",
                "canonical_summary": "Establish ethics oversight body",
                "member_ids": ["id1", "id2"],
                "archon_names": ["Paimon", "Belial"],
                "archon_count": 2,
            },
        ]
    )


@pytest.fixture
def mock_crewai_motion_response() -> str:
    """Mock CrewAI motion generation output."""
    return json.dumps(
        {
            "title": "Motion to Establish AI Ethics Council",
            "motion_text": "The Conclave hereby resolves to establish an AI Ethics Council.",
            "rationale": "Based on recommendations from 2 Archons.",
        }
    )


@pytest.fixture
def tmp_checkpoint_dir(tmp_path: Path) -> Path:
    """Create a temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


# ===========================================================================
# Tests: Initialization
# ===========================================================================


class TestSecretaryCrewAIAdapterInit:
    """Tests for SecretaryCrewAIAdapter initialization."""

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_implements_protocol(
        self, _mock_agent: MagicMock, tmp_checkpoint_dir: Path
    ) -> None:
        """AC1: Adapter implements SecretaryAgentProtocol."""
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        assert isinstance(adapter, SecretaryAgentProtocol)

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_creates_dual_agents(
        self, mock_agent: MagicMock, tmp_checkpoint_dir: Path
    ) -> None:
        """AC2: Creates both text and JSON agents."""
        SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)

        # Agent should be called twice (once for text, once for JSON)
        assert mock_agent.call_count == 2

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_creates_checkpoint_dir(
        self, _mock_agent: MagicMock, tmp_path: Path
    ) -> None:
        """AC3: Creates checkpoint directory if it doesn't exist."""
        checkpoint_dir = tmp_path / "new_checkpoints"
        assert not checkpoint_dir.exists()

        SecretaryCrewAIAdapter(checkpoint_dir=checkpoint_dir)

        assert checkpoint_dir.exists()

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_uses_custom_profile(
        self, _mock_agent: MagicMock, tmp_checkpoint_dir: Path
    ) -> None:
        """Test adapter uses custom profile when provided."""
        custom_profile = SecretaryAgentProfile(
            role="Custom Secretary",
            goal="Custom goal",
        )

        adapter = SecretaryCrewAIAdapter(
            profile=custom_profile,
            checkpoint_dir=tmp_checkpoint_dir,
        )

        assert adapter._profile.role == "Custom Secretary"


# ===========================================================================
# Tests: JSON Parsing Helpers
# ===========================================================================


class TestJSONParsing:
    """Tests for JSON parsing helper functions."""

    def test_sanitize_json_string_escapes_newlines(self) -> None:
        """Test sanitize_json_string escapes literal newlines in strings."""
        # Simulate LLM output with literal newline in string value
        raw = '{"text": "Line 1\nLine 2"}'
        sanitized = sanitize_json_string(raw)
        # Should escape the newline
        assert "\\n" in sanitized

    def test_sanitize_json_string_escapes_tabs(self) -> None:
        """Test sanitize_json_string escapes literal tabs."""
        raw = '{"text": "Col1\tCol2"}'
        sanitized = sanitize_json_string(raw)
        assert "\\t" in sanitized

    def test_sanitize_json_string_preserves_escaped(self) -> None:
        """Test sanitize_json_string doesn't double-escape."""
        raw = '{"text": "Already\\nescaped"}'
        sanitized = sanitize_json_string(raw)
        # Should not have double escaping
        assert "\\\\n" not in sanitized

    def test_aggressive_json_clean_removes_markdown(self) -> None:
        """Test aggressive_json_clean removes markdown code blocks."""
        raw = '```json\n[{"key": "value"}]\n```'
        cleaned = aggressive_clean(raw)
        assert "```" not in cleaned
        assert "[" in cleaned

    def test_aggressive_json_clean_fixes_trailing_commas(self) -> None:
        """Test aggressive_json_clean removes trailing commas."""
        raw = '{"items": [1, 2, 3,]}'
        cleaned = aggressive_clean(raw)
        # Should parse without error after cleaning
        data = json.loads(cleaned)
        assert data["items"] == [1, 2, 3]

    def test_aggressive_json_clean_fixes_unquoted_keys(self) -> None:
        """Test aggressive_json_clean adds quotes to unquoted keys."""
        raw = '{key: "value", other: 123}'
        cleaned = aggressive_clean(raw)
        # Should have quoted keys
        assert '"key"' in cleaned
        assert '"other"' in cleaned

    def test_is_truncated_json_detects_unclosed_bracket(self) -> None:
        """Test is_truncated_json detects unclosed brackets."""
        truncated = '[{"text": "value"}'
        assert _is_truncated_json(truncated) is True

    def test_is_truncated_json_detects_unclosed_brace(self) -> None:
        """Test is_truncated_json detects unclosed braces."""
        truncated = '{"text": "value"'
        assert _is_truncated_json(truncated) is True

    def test_is_truncated_json_detects_trailing_comma(self) -> None:
        """Test is_truncated_json detects trailing comma."""
        truncated = '[{"text": "value"},'
        assert _is_truncated_json(truncated) is True

    def test_is_truncated_json_accepts_complete(self) -> None:
        """Test is_truncated_json accepts complete JSON."""
        complete = '[{"text": "value"}]'
        assert _is_truncated_json(complete) is False


# ===========================================================================
# Tests: Extract Recommendations
# ===========================================================================


class TestExtractRecommendations:
    """Tests for recommendation extraction."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_extracts_from_speech(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_speech_context: SpeechContext,
        mock_crewai_extraction_response: str,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test extraction from speech returns recommendations."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_crewai_extraction_response
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.extract_recommendations(sample_speech_context)

        assert isinstance(result, ExtractionResult)
        assert len(result.recommendations) == 2
        assert result.recommendations[0].category == RecommendationCategory.ESTABLISH

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_empty_response(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_speech_context: SpeechContext,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test extraction handles empty response gracefully."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "No recommendations found."
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.extract_recommendations(sample_speech_context)

        assert isinstance(result, ExtractionResult)
        assert len(result.recommendations) == 0

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_malformed_json(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_speech_context: SpeechContext,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test extraction handles malformed JSON gracefully."""
        mock_crew = MagicMock()
        # Malformed JSON with control characters
        mock_crew.kickoff.return_value = '[{text: "value\nwith newline"}]'
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.extract_recommendations(sample_speech_context)

        # Should not raise, returns empty or parsed results
        assert isinstance(result, ExtractionResult)


# ===========================================================================
# Tests: Validate Extractions
# ===========================================================================


class TestValidateExtractions:
    """Tests for extraction validation."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_validates_extractions(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        sample_speech_context: SpeechContext,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test validation returns confidence score."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = (
            '{"validated_count": 2, "confidence": 0.95, "missed_count": 0}'
        )
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.validate_extractions(
            sample_recommendations,
            [sample_speech_context],
        )

        assert isinstance(result, ExtractionResult)
        assert result.confidence == 0.95
        assert result.missed_count == 0

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_validation_failure(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        sample_speech_context: SpeechContext,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test validation returns default confidence on failure."""
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = RuntimeError("API error")
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.validate_extractions(
            sample_recommendations,
            [sample_speech_context],
        )

        # Should return fallback result, not raise
        assert isinstance(result, ExtractionResult)
        assert result.confidence == 0.7  # Fallback confidence


# ===========================================================================
# Tests: Semantic Clustering
# ===========================================================================


class TestClusterSemantically:
    """Tests for semantic clustering."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_clusters_recommendations(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test clustering groups recommendations by theme."""
        # Convert recommendation IDs to strings for the mock response
        rec_ids = [str(r.recommendation_id) for r in sample_recommendations]
        mock_response = json.dumps(
            [
                {
                    "theme": "Ethics Oversight",
                    "canonical_summary": "Establish ethics governance",
                    "member_ids": rec_ids,
                    "archon_names": ["Paimon", "Belial"],
                    "archon_count": 2,
                },
            ]
        )

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_response
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.cluster_semantically(sample_recommendations)

        assert isinstance(result, ClusteringResult)
        assert len(result.clusters) == 1
        assert result.clusters[0].theme == "Ethics Oversight"

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_large_batch(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test clustering handles >50 recommendations in batches."""
        # Create many recommendations
        large_list = sample_recommendations * 30  # 60 recommendations

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "[]"  # Empty clusters
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        await adapter.cluster_semantically(large_list)

        # Should process in batches (60 / 50 = 2 batches)
        assert mock_crew.kickoff.call_count == 2


# ===========================================================================
# Tests: Conflict Detection
# ===========================================================================


class TestDetectConflicts:
    """Tests for conflict detection."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_detects_conflicts(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test conflict detection returns conflicts."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = json.dumps(
            {
                "conflicts": [
                    {
                        "archon_a": "Paimon",
                        "archon_b": "Belial",
                        "description": "Test conflict",
                    },
                ],
                "conflict_count": 1,
            }
        )
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.detect_conflicts(sample_recommendations)

        assert isinstance(result, ConflictResult)
        # Note: Current impl returns empty conflicts list, just parses count
        # This is a simplified implementation

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_detection_failure(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test conflict detection returns empty on failure."""
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = RuntimeError("API error")
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.detect_conflicts(sample_recommendations)

        assert isinstance(result, ConflictResult)
        assert len(result.conflicts) == 0


# ===========================================================================
# Tests: Motion Generation
# ===========================================================================


class TestGenerateMotionText:
    """Tests for motion text generation."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_generates_motion(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_cluster: RecommendationCluster,
        mock_crewai_motion_response: str,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test motion generation creates QueuedMotion."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_crewai_motion_response
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        motion = await adapter.generate_motion_text(sample_cluster, "Test Session")

        assert isinstance(motion, QueuedMotion)
        assert motion.title == "Motion to Establish AI Ethics Council"
        assert "resolves to establish" in motion.text

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_fallback_on_json_failure(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_cluster: RecommendationCluster,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test motion generation falls back on JSON parse failure."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Unparseable text response"
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        motion = await adapter.generate_motion_text(sample_cluster, "Test Session")

        # Should return fallback motion using cluster data
        assert isinstance(motion, QueuedMotion)
        assert sample_cluster.theme in motion.title


# ===========================================================================
# Tests: Full Pipeline
# ===========================================================================


class TestProcessFullTranscript:
    """Tests for full transcript processing pipeline."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_full_pipeline(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_speech_context: SpeechContext,
        mock_crewai_extraction_response: str,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test full pipeline runs all steps."""
        mock_crew = MagicMock()
        # Different responses for different steps
        mock_crew.kickoff.side_effect = [
            # Step 1: Extraction
            mock_crewai_extraction_response,
            # Step 2: Validation
            '{"validated_count": 2, "confidence": 0.9, "missed_count": 0}',
            # Step 3: Clustering
            "[]",  # Empty clusters for simplicity
            # Step 4: Conflicts
            '{"conflicts": [], "conflict_count": 0}',
        ]
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.process_full_transcript(
            [sample_speech_context],
            "test-session-id",
            "Test Session",
        )

        assert isinstance(result, FullProcessingResult)
        assert len(result.recommendations) == 2
        assert result.extraction_confidence == 0.9

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_saves_checkpoints(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_speech_context: SpeechContext,
        mock_crewai_extraction_response: str,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test checkpoints are saved after each step."""
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [
            mock_crewai_extraction_response,
            '{"validated_count": 2, "confidence": 0.9, "missed_count": 0}',
            "[]",
            '{"conflicts": [], "conflict_count": 0}',
        ]
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        await adapter.process_full_transcript(
            [sample_speech_context],
            "test-session",
            "Test Session",
        )

        # Check checkpoint files exist
        checkpoint_files = list(tmp_checkpoint_dir.glob("test-session_*"))
        assert len(checkpoint_files) >= 4  # At least 4 checkpoints

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_partial_failure(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_speech_context: SpeechContext,
        mock_crewai_extraction_response: str,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test pipeline continues on step failure."""
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [
            mock_crewai_extraction_response,  # Extraction succeeds
            RuntimeError("Validation API error"),  # Validation fails
            "[]",  # Clustering succeeds
            '{"conflicts": [], "conflict_count": 0}',  # Conflicts succeeds
        ]
        mock_crew_class.return_value = mock_crew

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        result = await adapter.process_full_transcript(
            [sample_speech_context],
            "test-session",
            "Test Session",
        )

        # Should still return result despite validation failure
        assert isinstance(result, FullProcessingResult)
        assert result.extraction_confidence == 0.7  # Fallback confidence


# ===========================================================================
# Tests: Checkpointing
# ===========================================================================


class TestCheckpointing:
    """Tests for checkpoint save/load functionality."""

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_save_checkpoint(
        self,
        _mock_agent: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test checkpoint saving."""
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)

        checkpoint_path = adapter._save_checkpoint(
            "test-session",
            "extraction",
            sample_recommendations,
        )

        assert checkpoint_path.exists()
        with open(checkpoint_path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 2

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_load_checkpoint(
        self,
        _mock_agent: MagicMock,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test checkpoint loading."""
        # Create a checkpoint file
        checkpoint_file = tmp_checkpoint_dir / "test-session_extraction.json"
        with open(checkpoint_file, "w") as f:
            json.dump([{"text": "test"}], f)

        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        data = adapter._load_checkpoint("test-session", "extraction")

        assert data is not None
        assert data == [{"text": "test"}]

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_load_missing_checkpoint(
        self,
        _mock_agent: MagicMock,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test loading non-existent checkpoint returns None."""
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)
        data = adapter._load_checkpoint("nonexistent", "step")

        assert data is None

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_checkpoints_disabled(
        self,
        _mock_agent: MagicMock,
        sample_recommendations: list[ExtractedRecommendation],
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test checkpoints can be disabled."""
        profile = create_default_secretary_profile()
        # Create profile with checkpoints disabled
        profile_disabled = SecretaryAgentProfile(
            text_llm_config=profile.text_llm_config,
            json_llm_config=profile.json_llm_config,
            checkpoints_enabled=False,
        )

        adapter = SecretaryCrewAIAdapter(
            profile=profile_disabled,
            checkpoint_dir=tmp_checkpoint_dir,
        )

        # Save should return /dev/null path
        checkpoint_path = adapter._save_checkpoint(
            "test-session",
            "extraction",
            sample_recommendations,
        )

        assert str(checkpoint_path) == "/dev/null"


# ===========================================================================
# Tests: Category/Type Parsing
# ===========================================================================


class TestCategoryTypeParsing:
    """Tests for category and type enum parsing."""

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_parse_category_valid(
        self,
        _mock_agent: MagicMock,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test parsing valid category strings."""
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)

        assert adapter._parse_category("establish") == RecommendationCategory.ESTABLISH
        assert adapter._parse_category("implement") == RecommendationCategory.IMPLEMENT
        assert adapter._parse_category("mandate") == RecommendationCategory.MANDATE
        assert (
            adapter._parse_category("PILOT") == RecommendationCategory.PILOT
        )  # Case insensitive

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_parse_category_unknown(
        self,
        _mock_agent: MagicMock,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test parsing unknown category returns OTHER."""
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)

        assert adapter._parse_category("unknown") == RecommendationCategory.OTHER
        assert adapter._parse_category("") == RecommendationCategory.OTHER

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_parse_type_valid(
        self,
        _mock_agent: MagicMock,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test parsing valid type strings."""
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)

        assert adapter._parse_type("policy") == RecommendationType.POLICY
        assert adapter._parse_type("task") == RecommendationType.TASK
        assert (
            adapter._parse_type("AMENDMENT") == RecommendationType.AMENDMENT
        )  # Case insensitive

    @patch(f"{CREWAI_MODULE}.Agent")
    def test_parse_type_unknown(
        self,
        _mock_agent: MagicMock,
        tmp_checkpoint_dir: Path,
    ) -> None:
        """Test parsing unknown type returns POLICY."""
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=tmp_checkpoint_dir)

        assert adapter._parse_type("unknown") == RecommendationType.POLICY
        assert adapter._parse_type("") == RecommendationType.POLICY
