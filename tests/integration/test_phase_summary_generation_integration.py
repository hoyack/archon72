"""Integration tests for Phase Summary Generation (Story 7.5, FR-7.4).

Tests the integration between PhaseSummaryGenerationService and
PhaseWitnessBatchingService to ensure summaries flow correctly
into witness events for Observer consumption.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - mediated, not raw
- FR-7.4: System SHALL provide deliberation summary to Observer
- AC-1: Summary includes themes, duration, convergence indicator
- AC-2: Summary metadata flows to PhaseWitnessEvent.phase_metadata
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from src.application.services.phase_summary_generation_service import (
    PhaseSummaryGenerationService,
)
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.stubs.phase_witness_batching_stub import (
    PhaseWitnessBatchingStub,
)
from src.infrastructure.stubs.transcript_store_stub import TranscriptStoreStub


def _create_session(petition_id: UUID | None = None) -> DeliberationSession:
    """Create a test deliberation session."""
    return DeliberationSession.create(
        petition_id=petition_id or uuid4(),
        assigned_archons=(uuid4(), uuid4(), uuid4()),
    )


class TestPhaseSummaryWitnessIntegration:
    """Integration tests for summary generation to witness flow (AC-1, AC-2)."""

    @pytest_asyncio.fixture
    async def summary_service(self) -> PhaseSummaryGenerationService:
        """Create the summary generation service."""
        return PhaseSummaryGenerationService()

    @pytest_asyncio.fixture
    async def witness_service(self) -> PhaseWitnessBatchingStub:
        """Create the witness batching stub with transcript store."""
        return PhaseWitnessBatchingStub(
            transcript_store=TranscriptStoreStub(),
        )

    @pytest.mark.asyncio
    async def test_summary_flows_to_witness_metadata_ac2(
        self,
        summary_service: PhaseSummaryGenerationService,
        witness_service: PhaseWitnessBatchingStub,
    ) -> None:
        """AC-2: Summary metadata flows to PhaseWitnessEvent.phase_metadata."""
        session = _create_session()
        transcript = """
        Archon Alpha: Upon review of this governance petition,
        the transparency measures are comprehensive. Security
        considerations are well-addressed. I agree this merits attention.

        Archon Beta: I concur with the assessment. The accountability
        provisions are solid. Transparency is a key theme.

        Archon Gamma: I align with my colleagues. This petition
        addresses governance concerns effectively.
        """
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        # Generate summary
        summary = await summary_service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        # Witness phase with summary in metadata
        witness_event = await witness_service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata=summary,
            start_timestamp=start_time,
            end_timestamp=end_time,
        )

        # Verify summary fields are in witness metadata
        assert "themes" in witness_event.phase_metadata
        assert isinstance(witness_event.phase_metadata["themes"], list)
        assert len(witness_event.phase_metadata["themes"]) >= 1

        assert "convergence_reached" in witness_event.phase_metadata
        assert "challenge_count" in witness_event.phase_metadata

    @pytest.mark.asyncio
    async def test_augment_metadata_combines_with_existing_ac2(
        self,
        summary_service: PhaseSummaryGenerationService,
        witness_service: PhaseWitnessBatchingStub,
    ) -> None:
        """AC-2: augment_phase_metadata combines summary with existing metadata."""
        session = _create_session()

        # Use ASSESS phase to avoid witness chain requirement
        transcript = """
        Archon Alpha: This petition concerns governance reform.
        Archon Beta: I agree governance needs attention. Security is key.
        Archon Gamma: I concur. Transparency is important.
        """

        # Existing metadata from phase execution
        existing_metadata: dict[str, Any] = {
            "archon_count": 3,
            "phase_duration_ms": 1500,
            "custom_field": "value",
        }

        # Augment with summary
        augmented = await summary_service.augment_phase_metadata(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            existing_metadata=existing_metadata,
        )

        # Witness with augmented metadata
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)

        witness_event = await witness_service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata=augmented,
            start_timestamp=start_time,
            end_timestamp=end_time,
        )

        # Verify both original and summary fields present
        metadata = witness_event.phase_metadata
        assert metadata["archon_count"] == 3
        assert metadata["phase_duration_ms"] == 1500
        assert metadata["custom_field"] == "value"
        assert "themes" in metadata
        assert "convergence_reached" in metadata


class TestFullDeliberationSummaryFlow:
    """Integration tests for complete deliberation summary flow."""

    @pytest_asyncio.fixture
    async def summary_service(self) -> PhaseSummaryGenerationService:
        """Create the summary generation service."""
        return PhaseSummaryGenerationService()

    @pytest_asyncio.fixture
    async def witness_service(self) -> PhaseWitnessBatchingStub:
        """Create the witness batching stub."""
        return PhaseWitnessBatchingStub(
            transcript_store=TranscriptStoreStub(),
        )

    @pytest.mark.asyncio
    async def test_all_phases_generate_appropriate_summaries(
        self,
        summary_service: PhaseSummaryGenerationService,
        witness_service: PhaseWitnessBatchingStub,
    ) -> None:
        """Test complete 4-phase deliberation generates correct summaries."""
        session = _create_session()

        phases_and_transcripts = [
            (
                DeliberationPhase.ASSESS,
                """
                Archon Alpha: This petition concerns governance reform.
                The security implications are significant. Transparency is key.
                Archon Beta: Independent assessment confirms governance needs.
                Security provisions are adequate. Accountability measures strong.
                Archon Gamma: My review highlights governance and transparency.
                """,
            ),
            (
                DeliberationPhase.POSITION,
                """
                Archon Alpha: My position is ACKNOWLEDGE. I agree with the approach.
                Archon Beta: I concur. ACKNOWLEDGE is appropriate. We align on this.
                Archon Gamma: I support ACKNOWLEDGE. There is consensus here.
                """,
            ),
            (
                DeliberationPhase.CROSS_EXAMINE,
                """
                Archon Alpha: I challenge the timeline assumption.
                Archon Beta: I question whether resources are adequate.
                Archon Alpha: I disagree with that interpretation.
                Archon Gamma: However, I agree we can proceed.
                """,
            ),
            (
                DeliberationPhase.VOTE,
                """
                Archon Alpha: ACKNOWLEDGE. Final vote cast.
                Archon Beta: ACKNOWLEDGE. We are unanimous.
                Archon Gamma: ACKNOWLEDGE. Consensus achieved.
                """,
            ),
        ]

        witness_events = []
        for phase, transcript in phases_and_transcripts:
            # Generate summary
            summary = await summary_service.generate_phase_summary(
                phase=phase,
                transcript=transcript,
            )

            # Witness phase
            start_time = datetime.now(timezone.utc)
            end_time = datetime.now(timezone.utc)

            event = await witness_service.witness_phase(
                session=session,
                phase=phase,
                transcript=transcript,
                metadata=summary,
                start_timestamp=start_time,
                end_timestamp=end_time,
            )
            witness_events.append(event)

            # Advance session phase for next iteration (except VOTE->COMPLETE)
            if phase != DeliberationPhase.VOTE:
                next_phase = phase.next_phase()
                if next_phase is not None:
                    session = session.with_phase(next_phase)

        # Verify we have all 4 witness events
        assert len(witness_events) == 4

        # Verify ASSESS phase
        assess_event = witness_events[0]
        assert assess_event.phase == DeliberationPhase.ASSESS
        assert "themes" in assess_event.phase_metadata
        assert assess_event.phase_metadata["convergence_reached"] is None
        assert assess_event.phase_metadata["challenge_count"] is None

        # Verify POSITION phase
        position_event = witness_events[1]
        assert position_event.phase == DeliberationPhase.POSITION
        assert isinstance(position_event.phase_metadata["convergence_reached"], bool)
        assert position_event.phase_metadata["challenge_count"] is None

        # Verify CROSS_EXAMINE phase
        cross_event = witness_events[2]
        assert cross_event.phase == DeliberationPhase.CROSS_EXAMINE
        assert isinstance(cross_event.phase_metadata["convergence_reached"], bool)
        assert isinstance(cross_event.phase_metadata["challenge_count"], int)
        assert cross_event.phase_metadata["challenge_count"] >= 1  # We had challenges

        # Verify VOTE phase
        vote_event = witness_events[3]
        assert vote_event.phase == DeliberationPhase.VOTE
        assert isinstance(vote_event.phase_metadata["convergence_reached"], bool)
        assert vote_event.phase_metadata["challenge_count"] is None


class TestSummaryConsistencyAcrossPhases:
    """Tests for summary consistency across deliberation phases."""

    @pytest_asyncio.fixture
    async def summary_service(self) -> PhaseSummaryGenerationService:
        """Create the summary generation service."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_themes_reflect_transcript_content(
        self,
        summary_service: PhaseSummaryGenerationService,
    ) -> None:
        """Test that themes extracted reflect actual transcript content."""
        # Transcript with clear theme words
        transcript = """
        This deliberation focuses on cybersecurity threats.
        The encryption standards must be strengthened.
        Network protection is paramount. Cybersecurity
        remains our top priority. Encryption is key.
        """

        result = await summary_service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        themes = result["themes"]

        # At least one security-related term should appear
        security_terms = {"cybersecurity", "encryption", "network", "protection"}
        found_security_theme = any(t in security_terms for t in themes)
        assert found_security_theme, f"Expected security themes, got: {themes}"

    @pytest.mark.asyncio
    async def test_convergence_reflects_agreement_level(
        self,
        summary_service: PhaseSummaryGenerationService,
    ) -> None:
        """Test that convergence indicator reflects actual agreement in transcript."""
        # Transcript with strong agreement
        agreement_transcript = """
        I agree completely with this assessment.
        I concur with the previous speaker.
        We are aligned on this matter.
        There is clear consensus here.
        I support this position unanimously.
        """

        agreement_result = await summary_service.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript=agreement_transcript,
        )
        assert agreement_result["convergence_reached"] is True

        # Transcript with strong disagreement
        disagreement_transcript = """
        I disagree strongly with this position.
        I oppose this recommendation.
        My view differs fundamentally.
        I challenge the underlying assumptions.
        There is significant dispute here.
        """

        disagreement_result = await summary_service.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript=disagreement_transcript,
        )
        assert disagreement_result["convergence_reached"] is False


class TestNoVerbatimQuotesInWitness:
    """Tests ensuring no verbatim quotes in witness metadata."""

    @pytest_asyncio.fixture
    async def summary_service(self) -> PhaseSummaryGenerationService:
        """Create the summary generation service."""
        return PhaseSummaryGenerationService()

    @pytest_asyncio.fixture
    async def witness_service(self) -> PhaseWitnessBatchingStub:
        """Create the witness batching stub."""
        return PhaseWitnessBatchingStub(
            transcript_store=TranscriptStoreStub(),
        )

    @pytest.mark.asyncio
    async def test_witness_metadata_contains_no_verbatim_quotes(
        self,
        summary_service: PhaseSummaryGenerationService,
        witness_service: PhaseWitnessBatchingStub,
    ) -> None:
        """Test that witness metadata doesn't contain verbatim transcript quotes."""
        session = _create_session()

        # Unique phrases that should not appear in output
        transcript = """
        Archon Alpha stated: "This particular governance mechanism
        requires extraordinary scrutiny and careful deliberation
        before we can proceed with implementation."

        Archon Beta responded: "I wholeheartedly agree that the
        implementation timeline must accommodate proper review periods."
        """

        # Generate summary and witness
        summary = await summary_service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        witness_event = await witness_service.witness_phase(
            session=session,
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            metadata=summary,
            start_timestamp=datetime.now(timezone.utc),
            end_timestamp=datetime.now(timezone.utc),
        )

        # Convert metadata to string for checking
        metadata_str = str(witness_event.phase_metadata)

        # Unique phrases from transcript should NOT appear
        forbidden_phrases = [
            "This particular governance mechanism",
            "requires extraordinary scrutiny",
            "wholeheartedly agree",
            "implementation timeline must accommodate",
        ]

        for phrase in forbidden_phrases:
            assert phrase not in metadata_str, (
                f"Verbatim phrase found in metadata: '{phrase}'"
            )

        # But themes (single words) SHOULD be present
        assert "themes" in witness_event.phase_metadata
        themes = witness_event.phase_metadata["themes"]
        assert len(themes) >= 1
