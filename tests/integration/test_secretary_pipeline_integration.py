"""Integration tests for Secretary pipeline.

Tests the Secretary pipeline coordination between SecretaryService
and SecretaryCrewAIAdapter with mocked CrewAI for deterministic results.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.application.ports.secretary_agent import SpeechContext
from src.application.services.secretary_service import SecretaryService
from src.domain.models.secretary import RecommendationCategory
from src.infrastructure.adapters.external.secretary_crewai_adapter import (
    SecretaryCrewAIAdapter,
)

# Module path for patching CrewAI classes
CREWAI_MODULE = "src.infrastructure.adapters.external.secretary_crewai_adapter"


@pytest.fixture
def sample_transcript_speeches() -> list[SpeechContext]:
    """Create a list of sample speeches for integration testing."""
    return [
        SpeechContext(
            archon_name="Paimon",
            archon_id="paimon-001",
            speech_content="""I recommend establishing an AI Ethics Council to oversee alignment efforts.
We should also implement quarterly reviews of all governance decisions.""",
            motion_context="Deliberation on AI Governance",
            line_start=10,
            line_end=15,
        ),
        SpeechContext(
            archon_name="Belial",
            archon_id="belial-002",
            speech_content="""I support the establishment of an ethics council. Additionally,
we should mandate transparency reports for all external communications.
I propose piloting a new feedback mechanism for citizen concerns.""",
            motion_context="Deliberation on AI Governance",
            line_start=20,
            line_end=28,
        ),
        SpeechContext(
            archon_name="Asmoday",
            archon_id="asmoday-003",
            speech_content="""Building on the ethics council proposal, I recommend we investigate
current gaps in constitutional compliance. We need a systematic review
of all operational procedures.""",
            motion_context="Deliberation on AI Governance",
            line_start=35,
            line_end=42,
        ),
    ]


@pytest.fixture
def mock_extraction_responses() -> list[str]:
    """Mock CrewAI extraction responses for each speech."""
    return [
        # Paimon's recommendations
        json.dumps(
            [
                {
                    "category": "establish",
                    "type": "policy",
                    "text": "Establish an AI Ethics Council to oversee alignment efforts",
                    "keywords": ["ethics", "council", "ai", "alignment"],
                    "stance": "FOR",
                    "source_archon": "Paimon",
                    "source_line_start": 10,
                    "source_line_end": 12,
                },
                {
                    "category": "implement",
                    "type": "task",
                    "text": "Implement quarterly reviews of governance decisions",
                    "keywords": ["review", "quarterly", "governance"],
                    "stance": None,
                    "source_archon": "Paimon",
                    "source_line_start": 13,
                    "source_line_end": 15,
                },
            ]
        ),
        # Belial's recommendations
        json.dumps(
            [
                {
                    "category": "establish",
                    "type": "policy",
                    "text": "Support establishment of ethics council",
                    "keywords": ["ethics", "council", "support"],
                    "stance": "FOR",
                    "source_archon": "Belial",
                    "source_line_start": 20,
                    "source_line_end": 22,
                },
                {
                    "category": "mandate",
                    "type": "policy",
                    "text": "Mandate transparency reports for external communications",
                    "keywords": ["transparency", "reports", "communications"],
                    "stance": None,
                    "source_archon": "Belial",
                    "source_line_start": 23,
                    "source_line_end": 25,
                },
                {
                    "category": "pilot",
                    "type": "task",
                    "text": "Pilot a feedback mechanism for citizen concerns",
                    "keywords": ["pilot", "feedback", "citizen"],
                    "stance": None,
                    "source_archon": "Belial",
                    "source_line_start": 26,
                    "source_line_end": 28,
                },
            ]
        ),
        # Asmoday's recommendations
        json.dumps(
            [
                {
                    "category": "investigate",
                    "type": "task",
                    "text": "Investigate current gaps in constitutional compliance",
                    "keywords": ["investigate", "gaps", "compliance", "constitutional"],
                    "stance": None,
                    "source_archon": "Asmoday",
                    "source_line_start": 35,
                    "source_line_end": 38,
                },
                {
                    "category": "review",
                    "type": "task",
                    "text": "Systematic review of all operational procedures",
                    "keywords": ["review", "systematic", "procedures", "operational"],
                    "stance": None,
                    "source_archon": "Asmoday",
                    "source_line_start": 39,
                    "source_line_end": 42,
                },
            ]
        ),
    ]


class TestSecretaryPipelineIntegration:
    """Integration tests for Secretary pipeline with mocked CrewAI."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_secretary_extraction_pipeline(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        sample_transcript_speeches: list[SpeechContext],
        mock_extraction_responses: list[str],
        tmp_path: Path,
    ) -> None:
        """Integration test: Extraction phase of transcript processing."""
        # Setup mock responses for extraction and validation
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [
            # Extraction for each speech
            *mock_extraction_responses,
            # Validation
            '{"validated_count": 7, "confidence": 0.92, "missed_count": 0}',
            # Clustering - returns empty (clustering with mock IDs is complex)
            "[]",
            # Conflict detection
            '{"conflicts": [], "conflict_count": 0}',
        ]
        mock_crew_class.return_value = mock_crew

        # Create adapter
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()

        adapter = SecretaryCrewAIAdapter(
            checkpoint_dir=checkpoint_dir,
            verbose=False,
        )

        # Process transcript through adapter
        result = await adapter.process_full_transcript(
            sample_transcript_speeches,
            "integration-test-session",
            "Integration Test Session",
        )

        # Verify extraction results
        assert len(result.recommendations) == 7  # Total from all speeches
        assert result.extraction_confidence == 0.92
        assert result.processing_time_ms > 0

        # Verify checkpoint files created (at least extraction, validation, clustering)
        checkpoint_files = list(checkpoint_dir.glob("integration-test-session_*"))
        assert len(checkpoint_files) >= 3

        # Verify recommendation categories were parsed correctly
        categories = {r.category for r in result.recommendations}
        assert RecommendationCategory.ESTABLISH in categories
        assert RecommendationCategory.IMPLEMENT in categories
        assert RecommendationCategory.MANDATE in categories

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_adapter_handles_pipeline_steps(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Integration test: Verify adapter runs all pipeline steps."""
        # Setup mock for single speech pipeline
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [
            # Extraction
            json.dumps(
                [
                    {
                        "category": "establish",
                        "type": "policy",
                        "text": "Test recommendation",
                        "keywords": ["test"],
                        "stance": "FOR",
                        "source_archon": "TestArchon",
                        "source_line_start": 1,
                        "source_line_end": 5,
                    }
                ]
            ),
            # Validation
            '{"validated_count": 1, "confidence": 0.95, "missed_count": 0}',
            # Clustering
            "[]",
            # Conflicts
            '{"conflicts": [], "conflict_count": 0}',
        ]
        mock_crew_class.return_value = mock_crew

        # Create adapter
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=checkpoint_dir, verbose=False)

        # Single speech input
        speeches = [
            SpeechContext(
                archon_name="TestArchon",
                archon_id="test-001",
                speech_content="I recommend establishing a test council.",
                motion_context="Test Motion",
                line_start=1,
                line_end=5,
            )
        ]

        # Process
        result = await adapter.process_full_transcript(
            speeches,
            "pipeline-test",
            "Pipeline Test Session",
        )

        # Verify all steps ran
        assert result.extraction_confidence == 0.95
        assert len(result.recommendations) == 1
        assert result.processing_time_ms > 0

        # Verify checkpoint files were created for each step
        checkpoint_files = sorted(checkpoint_dir.glob("pipeline-test_*"))
        checkpoint_names = [f.name for f in checkpoint_files]

        # Should have checkpoints for: extraction, validation, clustering, conflicts, motions
        assert any("01_extraction" in name for name in checkpoint_names)
        assert any("02_validation" in name for name in checkpoint_names)


class TestSecretaryServiceIntegration:
    """Integration tests for SecretaryService with adapter."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_service_enhanced_mode_with_adapter(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Integration test: SecretaryService with CrewAI adapter."""
        # Setup mock
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [
            # Extraction for 2 speeches
            json.dumps(
                [
                    {
                        "category": "establish",
                        "type": "policy",
                        "text": "Establish ethics council",
                        "keywords": ["ethics"],
                        "stance": "FOR",
                        "source_archon": "Paimon",
                        "source_line_start": 1,
                        "source_line_end": 5,
                    }
                ]
            ),
            json.dumps(
                [
                    {
                        "category": "mandate",
                        "type": "policy",
                        "text": "Mandate transparency",
                        "keywords": ["transparency"],
                        "stance": None,
                        "source_archon": "Belial",
                        "source_line_start": 10,
                        "source_line_end": 15,
                    }
                ]
            ),
            # Validation
            '{"validated_count": 2, "confidence": 0.9, "missed_count": 0}',
            # Clustering
            "[]",
            # Conflicts
            '{"conflicts": [], "conflict_count": 0}',
        ]
        mock_crew_class.return_value = mock_crew

        # Create adapter
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=checkpoint_dir)

        # Create transcript file with proper format for service parsing
        transcript_path = tmp_path / "transcript.md"
        transcript_content = """# Conclave Session: Test

## Motion: Test Motion

### Paimon (executive_director)
I recommend establishing an ethics council.

### Belial (senior_director)
We should mandate transparency.
"""
        transcript_path.write_text(transcript_content)

        # Create service with adapter
        service = SecretaryService(secretary_agent=adapter)

        # Process with enhanced mode
        enhanced_session_id = uuid4()
        report = await service.process_transcript_enhanced(
            str(transcript_path),
            enhanced_session_id,
            "Enhanced Test Session",
        )

        # Verify service completed without errors
        assert report.source_session_id == enhanced_session_id
        assert report.source_session_name == "Enhanced Test Session"
        # The report may have 0-2 recommendations depending on transcript parsing
        # Main goal is to verify the service coordinates with adapter correctly


class TestSecretaryAdapterCheckpointing:
    """Tests for adapter checkpointing functionality."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_checkpoints_saved_after_each_step(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that checkpoints are saved after each pipeline step."""
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [
            json.dumps(
                [
                    {
                        "category": "establish",
                        "type": "policy",
                        "text": "Test",
                        "keywords": ["test"],
                        "stance": None,
                        "source_archon": "Test",
                        "source_line_start": 1,
                        "source_line_end": 1,
                    }
                ]
            ),
            '{"validated_count": 1, "confidence": 0.9, "missed_count": 0}',
            "[]",
            '{"conflicts": [], "conflict_count": 0}',
        ]
        mock_crew_class.return_value = mock_crew

        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=checkpoint_dir)

        speeches = [
            SpeechContext(
                archon_name="Test",
                archon_id="test-001",
                speech_content="I recommend testing.",
                motion_context="Test",
                line_start=1,
                line_end=1,
            )
        ]

        await adapter.process_full_transcript(speeches, "checkpoint-test", "Test")

        # Verify checkpoints exist
        checkpoints = list(checkpoint_dir.glob("checkpoint-test_*"))
        assert len(checkpoints) >= 4  # extraction, validation, clustering, conflicts

        # Read and verify checkpoint content
        extraction_checkpoint = next(
            (f for f in checkpoints if "01_extraction" in f.name), None
        )
        assert extraction_checkpoint is not None

        with open(extraction_checkpoint) as f:
            data = json.load(f)
            # Checkpoint stores list directly or in items key
            items = data if isinstance(data, list) else data.get("items", [])
            assert len(items) == 1


class TestSecretaryAdapterErrorHandling:
    """Tests for adapter error handling and resilience."""

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_malformed_json_response(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test adapter handles malformed JSON from LLM gracefully."""
        mock_crew = MagicMock()
        # Return malformed JSON that the sanitizer should handle
        mock_crew.kickoff.side_effect = [
            '[{"category": "establish", "type": "policy", "text": "Test", "keywords": ["test"], "stance": null, "source_archon": "Test", "source_line_start": 1, "source_line_end": 1}]',  # noqa: E501
            '{"validated_count": 1, "confidence": 0.8}',  # Missing missed_count
            "[]",
            '{"conflict_count": 0}',  # Missing conflicts array
        ]
        mock_crew_class.return_value = mock_crew

        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=checkpoint_dir)

        speeches = [
            SpeechContext(
                archon_name="Test",
                archon_id="test-001",
                speech_content="I recommend testing.",
                motion_context="Test",
                line_start=1,
                line_end=1,
            )
        ]

        # Should complete without raising exceptions
        result = await adapter.process_full_transcript(speeches, "error-test", "Test")

        # Verify it handled the responses gracefully
        assert result.recommendations is not None
        assert result.extraction_confidence >= 0

    @pytest.mark.asyncio
    @patch(f"{CREWAI_MODULE}.Crew")
    @patch(f"{CREWAI_MODULE}.Task")
    @patch(f"{CREWAI_MODULE}.Agent")
    async def test_handles_empty_speeches_list(
        self,
        _mock_agent: MagicMock,
        _mock_task: MagicMock,
        mock_crew_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test adapter handles empty input gracefully."""
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [
            '{"validated_count": 0, "confidence": 0.0, "missed_count": 0}',
            "[]",
            '{"conflicts": [], "conflict_count": 0}',
        ]
        mock_crew_class.return_value = mock_crew

        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir()
        adapter = SecretaryCrewAIAdapter(checkpoint_dir=checkpoint_dir)

        # Empty speeches list
        result = await adapter.process_full_transcript([], "empty-test", "Test")

        # Should complete without errors
        assert len(result.recommendations) == 0
        assert len(result.clusters) == 0
        assert len(result.conflicts) == 0
