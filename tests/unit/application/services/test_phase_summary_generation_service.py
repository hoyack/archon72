"""Unit tests for PhaseSummaryGenerationService (Story 7.5, FR-7.4).

Tests the service that generates phase summaries during deliberation.
Phase summaries provide Observer-tier access to deliberation content
without exposing raw transcript text per Ruling-2.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - mediated, not raw
- FR-7.4: System SHALL provide deliberation summary to Observer
- AC-1 through AC-6: Phase-specific content requirements
- NO VERBATIM QUOTES: Summary must be derived, not excerpted
"""

import pytest
import pytest_asyncio

from src.application.services.phase_summary_generation_service import (
    PhaseSummaryGenerationService,
)
from src.domain.models.deliberation_session import DeliberationPhase


class TestPhaseSummaryGenerationServiceInit:
    """Tests for service initialization."""

    def test_service_initializes_successfully(self) -> None:
        """Test service initializes without dependencies."""
        service = PhaseSummaryGenerationService()

        # Should have compiled regex patterns
        assert len(service._agreement_patterns) > 0
        assert len(service._disagreement_patterns) > 0
        assert len(service._challenge_patterns) > 0


class TestGeneratePhaseSummary:
    """Tests for generate_phase_summary method (AC-1)."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_raises_on_empty_transcript(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test raises ValueError for empty transcript."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            await service.generate_phase_summary(
                phase=DeliberationPhase.ASSESS,
                transcript="",
            )

    @pytest.mark.asyncio
    async def test_raises_on_whitespace_only_transcript(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test raises ValueError for whitespace-only transcript."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            await service.generate_phase_summary(
                phase=DeliberationPhase.ASSESS,
                transcript="   \n\t  ",
            )

    @pytest.mark.asyncio
    async def test_raises_on_complete_phase(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test raises ValueError for COMPLETE phase."""
        with pytest.raises(ValueError, match="Cannot generate summary for COMPLETE"):
            await service.generate_phase_summary(
                phase=DeliberationPhase.COMPLETE,
                transcript="Some transcript",
            )


class TestAssessPhase:
    """Tests for ASSESS phase summary generation (AC-3)."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_assess_phase_returns_themes_only_ac3(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """AC-3: ASSESS phase includes themes only, no convergence or challenge count."""
        transcript = """
        Archon Alpha: Upon review of this petition regarding governance reform,
        I note several concerns about transparency and accountability.
        The proposal addresses resource allocation effectively.

        Archon Beta: My independent assessment focuses on the constitutional
        implications. The governance structures proposed require careful review.
        Transparency measures are well-defined.

        Archon Gamma: This petition raises valid questions about accountability
        in resource management. The transparency provisions are comprehensive.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        # Should have themes
        assert "themes" in result
        assert isinstance(result["themes"], list)
        assert len(result["themes"]) >= 1

        # Should have no convergence (None for ASSESS)
        assert result["convergence_reached"] is None

        # Should have no challenge count
        assert result["challenge_count"] is None

    @pytest.mark.asyncio
    async def test_assess_extracts_meaningful_themes(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test that ASSESS extracts meaningful theme keywords."""
        transcript = """
        Archon Alpha: The governance framework needs enhancement.
        Security provisions are inadequate for the proposed expansion.
        Budget allocation requires restructuring.

        Archon Beta: Security concerns are paramount. The governance
        model lacks proper oversight. Budget constraints are real.

        Archon Gamma: I concur that security and governance require attention.
        The budget implications are significant for implementation.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        themes = result["themes"]

        # Should extract governance, security, budget as frequent terms
        theme_set = set(themes)
        # At least one domain-relevant word should appear
        assert any(t in theme_set for t in ["governance", "security", "budget"])


class TestPositionPhase:
    """Tests for POSITION phase summary generation (AC-4)."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_position_phase_includes_themes_and_convergence_ac4(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """AC-4: POSITION phase includes themes and convergence indicator."""
        transcript = """
        Archon Alpha: My position is to ACKNOWLEDGE this petition.
        The governance improvements are sound. I agree with the overall approach.

        Archon Beta: I align with Alpha's assessment. The transparency
        measures support ACKNOWLEDGMENT. I concur on the governance points.

        Archon Gamma: I also support ACKNOWLEDGMENT. We share the view
        that this petition merits positive recognition.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript=transcript,
        )

        # Should have themes
        assert "themes" in result
        assert isinstance(result["themes"], list)

        # Should have convergence indicator (not None)
        assert "convergence_reached" in result
        assert isinstance(result["convergence_reached"], bool)

        # Should have no challenge count
        assert result["challenge_count"] is None

    @pytest.mark.asyncio
    async def test_position_detects_convergence_on_agreement(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test POSITION detects convergence when agreement markers present."""
        transcript = """
        Archon Alpha: I support the petition.
        Archon Beta: I agree with Alpha. We are aligned on this.
        Archon Gamma: I concur. There is consensus here.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript=transcript,
        )

        assert result["convergence_reached"] is True

    @pytest.mark.asyncio
    async def test_position_detects_no_convergence_on_disagreement(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test POSITION detects no convergence when disagreement markers present."""
        transcript = """
        Archon Alpha: I support ACKNOWLEDGMENT.
        Archon Beta: I disagree with Alpha. I oppose this approach.
        Archon Gamma: My position differs. I challenge the rationale.
        There is fundamental dispute on this matter.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript=transcript,
        )

        assert result["convergence_reached"] is False


class TestCrossExaminePhase:
    """Tests for CROSS_EXAMINE phase summary generation (AC-5)."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_cross_examine_includes_themes_convergence_and_challenges_ac5(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """AC-5: CROSS_EXAMINE includes themes, convergence, and challenge count."""
        transcript = """
        Archon Alpha: I challenge the premise that governance reform is needed.
        Archon Beta: I question that assumption. How do you explain the failures?
        Archon Alpha: I disagree with that characterization.
        Archon Gamma: I challenge this entire line of reasoning.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript=transcript,
        )

        # Should have themes
        assert "themes" in result
        assert isinstance(result["themes"], list)

        # Should have convergence indicator
        assert "convergence_reached" in result
        assert isinstance(result["convergence_reached"], bool)

        # Should have challenge count (positive integer)
        assert "challenge_count" in result
        assert isinstance(result["challenge_count"], int)
        assert result["challenge_count"] >= 0

    @pytest.mark.asyncio
    async def test_cross_examine_counts_challenges(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test CROSS_EXAMINE correctly counts challenge patterns."""
        transcript = """
        Archon Alpha: I challenge the validity of this proposal.
        Archon Beta: I question your methodology. Can you justify your position?
        Archon Alpha: I disagree with your interpretation.
        Archon Gamma: I object to that characterization. How do you explain this?
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript=transcript,
        )

        # Should detect multiple challenges
        assert result["challenge_count"] >= 3

    @pytest.mark.asyncio
    async def test_cross_examine_zero_challenges_when_none(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test CROSS_EXAMINE returns 0 when no challenge patterns found."""
        transcript = """
        Archon Alpha: I appreciate the thoughtful analysis.
        Archon Beta: Thank you for clarifying. I understand your point.
        Archon Gamma: This discussion has been productive.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript=transcript,
        )

        assert result["challenge_count"] == 0


class TestVotePhase:
    """Tests for VOTE phase summary generation (AC-6)."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_vote_phase_includes_themes_and_convergence_ac6(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """AC-6: VOTE phase includes themes and convergence indicator."""
        transcript = """
        Archon Alpha: My vote is ACKNOWLEDGE. Final governance decision rendered.
        Archon Beta: I also vote ACKNOWLEDGE. We are unanimous.
        Archon Gamma: ACKNOWLEDGE. Consensus achieved.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.VOTE,
            transcript=transcript,
        )

        # Should have themes
        assert "themes" in result
        assert isinstance(result["themes"], list)

        # Should have convergence indicator
        assert "convergence_reached" in result
        assert isinstance(result["convergence_reached"], bool)

        # Should have no challenge count
        assert result["challenge_count"] is None

    @pytest.mark.asyncio
    async def test_vote_detects_unanimous_convergence(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test VOTE detects convergence when votes are unanimous."""
        transcript = """
        Archon Alpha: ACKNOWLEDGE. We all agree.
        Archon Beta: ACKNOWLEDGE. I concur with the consensus.
        Archon Gamma: ACKNOWLEDGE. Unanimous decision.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.VOTE,
            transcript=transcript,
        )

        assert result["convergence_reached"] is True


class TestThemeExtraction:
    """Tests for theme extraction logic."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_extracts_between_3_and_5_themes(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test extracts appropriate number of themes (3-5)."""
        transcript = """
        Governance reform requires careful consideration of security,
        transparency, accountability, efficiency, and sustainability.
        The constitutional framework must balance these concerns.
        Implementation will require significant resources and planning.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        themes = result["themes"]
        assert 1 <= len(themes) <= 5

    @pytest.mark.asyncio
    async def test_filters_stopwords(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test filters common stopwords from themes."""
        transcript = """
        The petition is about the proposal and the implementation.
        This is a very important matter that we must consider carefully.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        themes = result["themes"]
        # Common stopwords should not appear as themes
        for stopword in ["the", "is", "and", "a", "that", "we"]:
            assert stopword not in themes

    @pytest.mark.asyncio
    async def test_returns_lowercase_themes(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test themes are returned in lowercase."""
        transcript = """
        GOVERNANCE Reform SECURITY Enhancement TRANSPARENCY Measures
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        themes = result["themes"]
        for theme in themes:
            assert theme == theme.lower()


class TestAugmentPhaseMetadata:
    """Tests for augment_phase_metadata method (AC-1, AC-2)."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_augments_empty_metadata(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test augments when no existing metadata provided."""
        transcript = "Governance and security discussions continued."

        result = await service.augment_phase_metadata(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        assert "themes" in result
        assert "convergence_reached" in result
        assert "challenge_count" in result

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test preserves existing metadata fields."""
        transcript = "Governance and security discussions continued."
        existing = {
            "archon_count": 3,
            "custom_field": "value",
        }

        result = await service.augment_phase_metadata(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            existing_metadata=existing,
        )

        # Should preserve existing fields
        assert result["archon_count"] == 3
        assert result["custom_field"] == "value"

        # Should add summary fields
        assert "themes" in result
        assert "convergence_reached" in result

    @pytest.mark.asyncio
    async def test_summary_fields_override_existing_if_present(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test summary fields override existing same-named fields."""
        transcript = "Governance and security discussions with agreement and consensus."
        existing = {
            "themes": ["old_theme"],
            "convergence_reached": False,
        }

        result = await service.augment_phase_metadata(
            phase=DeliberationPhase.POSITION,
            transcript=transcript,
            existing_metadata=existing,
        )

        # Summary fields should be from new generation, not old values
        assert result["themes"] != ["old_theme"]

    @pytest.mark.asyncio
    async def test_augment_raises_on_empty_transcript(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test augment raises ValueError for empty transcript."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            await service.augment_phase_metadata(
                phase=DeliberationPhase.ASSESS,
                transcript="",
            )


class TestNoVerbatimQuotes:
    """Tests ensuring no verbatim quotes in output (AC-7 implicit)."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    async def test_themes_are_single_words_not_phrases(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test themes are single keywords, not multi-word phrases."""
        transcript = """
        The governance reform proposal includes several key components.
        Security enhancement measures are well-defined in this petition.
        Budget allocation strategies require careful consideration.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        themes = result["themes"]
        for theme in themes:
            # Each theme should be a single word (no spaces)
            assert " " not in theme

    @pytest.mark.asyncio
    async def test_result_contains_no_transcript_text(
        self, service: PhaseSummaryGenerationService
    ) -> None:
        """Test result doesn't contain verbatim transcript substrings > 10 chars."""
        transcript = """
        This is a very specific and unique phrase that should not appear
        in the output summary because we don't include verbatim quotes.
        Another uniquely crafted sentence for testing purposes only.
        """

        result = await service.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        # Convert result to string to check for verbatim content
        result_str = str(result)

        # Check that long transcript phrases don't appear verbatim
        test_phrases = [
            "very specific and unique phrase",
            "uniquely crafted sentence",
            "should not appear in the output",
        ]
        for phrase in test_phrases:
            assert phrase not in result_str


class TestAllPhasesSupported:
    """Tests ensuring all phases are properly supported."""

    @pytest_asyncio.fixture
    async def service(self) -> PhaseSummaryGenerationService:
        """Create service instance."""
        return PhaseSummaryGenerationService()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "phase",
        [
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        ],
    )
    async def test_all_non_complete_phases_return_valid_summary(
        self, service: PhaseSummaryGenerationService, phase: DeliberationPhase
    ) -> None:
        """Test all non-COMPLETE phases return valid summary structure."""
        transcript = "Sample governance discussion with themes of security and transparency."

        result = await service.generate_phase_summary(
            phase=phase,
            transcript=transcript,
        )

        # All phases should have themes
        assert "themes" in result
        assert isinstance(result["themes"], list)

        # All phases should have convergence_reached key
        assert "convergence_reached" in result

        # All phases should have challenge_count key
        assert "challenge_count" in result

        # Only CROSS_EXAMINE should have non-None challenge_count
        if phase == DeliberationPhase.CROSS_EXAMINE:
            assert isinstance(result["challenge_count"], int)
        else:
            assert result["challenge_count"] is None

        # Only ASSESS should have None convergence_reached
        if phase == DeliberationPhase.ASSESS:
            assert result["convergence_reached"] is None
        else:
            assert isinstance(result["convergence_reached"], bool)
