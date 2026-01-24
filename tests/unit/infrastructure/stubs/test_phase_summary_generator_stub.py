"""Unit tests for PhaseSummaryGeneratorStub (Story 7.5).

Tests the test stub implementation of PhaseSummaryGeneratorProtocol
used in unit and integration tests.
"""

import pytest
import pytest_asyncio

from src.domain.models.deliberation_session import DeliberationPhase
from src.infrastructure.stubs.phase_summary_generator_stub import (
    DEFAULT_THEMES,
    PhaseSummaryGeneratorStub,
)


class TestPhaseSummaryGeneratorStubInit:
    """Tests for stub initialization."""

    def test_initializes_with_defaults(self) -> None:
        """Test stub initializes with default values."""
        stub = PhaseSummaryGeneratorStub()

        assert stub._themes is None
        assert stub._convergence_reached is None
        assert stub._challenge_count is None
        assert stub._raise_error is None
        assert stub.calls == []

    def test_initializes_with_custom_themes(self) -> None:
        """Test stub initializes with custom themes."""
        custom_themes = ["custom", "themes"]
        stub = PhaseSummaryGeneratorStub(themes=custom_themes)

        assert stub._themes == custom_themes

    def test_initializes_with_custom_convergence(self) -> None:
        """Test stub initializes with custom convergence value."""
        stub = PhaseSummaryGeneratorStub(convergence_reached=True)

        assert stub._convergence_reached is True

    def test_initializes_with_custom_challenge_count(self) -> None:
        """Test stub initializes with custom challenge count."""
        stub = PhaseSummaryGeneratorStub(challenge_count=5)

        assert stub._challenge_count == 5

    def test_initializes_with_raise_error(self) -> None:
        """Test stub initializes with error to raise."""
        error = ValueError("Test error")
        stub = PhaseSummaryGeneratorStub(raise_error=error)

        assert stub._raise_error is error


class TestGeneratePhaseSummary:
    """Tests for generate_phase_summary method."""

    @pytest_asyncio.fixture
    async def stub(self) -> PhaseSummaryGeneratorStub:
        """Create stub instance."""
        return PhaseSummaryGeneratorStub()

    @pytest.mark.asyncio
    async def test_records_calls(self, stub: PhaseSummaryGeneratorStub) -> None:
        """Test stub records calls for assertions."""
        transcript = "Test transcript"
        await stub.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
        )

        assert len(stub.calls) == 1
        assert stub.calls[0] == (DeliberationPhase.ASSESS, transcript)

    @pytest.mark.asyncio
    async def test_raises_configured_error(self) -> None:
        """Test stub raises configured error."""
        error = ValueError("Test error")
        stub = PhaseSummaryGeneratorStub(raise_error=error)

        with pytest.raises(ValueError, match="Test error"):
            await stub.generate_phase_summary(
                phase=DeliberationPhase.ASSESS,
                transcript="Test",
            )

    @pytest.mark.asyncio
    async def test_raises_on_empty_transcript(
        self, stub: PhaseSummaryGeneratorStub
    ) -> None:
        """Test stub raises on empty transcript like real service."""
        with pytest.raises(ValueError, match="Transcript cannot be empty"):
            await stub.generate_phase_summary(
                phase=DeliberationPhase.ASSESS,
                transcript="",
            )

    @pytest.mark.asyncio
    async def test_raises_on_complete_phase(
        self, stub: PhaseSummaryGeneratorStub
    ) -> None:
        """Test stub raises on COMPLETE phase like real service."""
        with pytest.raises(ValueError, match="Cannot generate summary for COMPLETE"):
            await stub.generate_phase_summary(
                phase=DeliberationPhase.COMPLETE,
                transcript="Test",
            )


class TestPhaseSummaryResponses:
    """Tests for phase-specific responses."""

    @pytest.mark.asyncio
    async def test_assess_returns_themes_only(self) -> None:
        """Test ASSESS returns themes with None convergence/challenges."""
        stub = PhaseSummaryGeneratorStub()

        result = await stub.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript="Test transcript",
        )

        assert result["themes"] == DEFAULT_THEMES
        assert result["convergence_reached"] is None
        assert result["challenge_count"] is None

    @pytest.mark.asyncio
    async def test_position_returns_themes_and_convergence(self) -> None:
        """Test POSITION returns themes and convergence (default True)."""
        stub = PhaseSummaryGeneratorStub()

        result = await stub.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript="Test transcript",
        )

        assert result["themes"] == DEFAULT_THEMES
        assert result["convergence_reached"] is True
        assert result["challenge_count"] is None

    @pytest.mark.asyncio
    async def test_cross_examine_returns_all_fields(self) -> None:
        """Test CROSS_EXAMINE returns themes, convergence (False), and challenges."""
        stub = PhaseSummaryGeneratorStub()

        result = await stub.generate_phase_summary(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript="Test transcript",
        )

        assert result["themes"] == DEFAULT_THEMES
        assert result["convergence_reached"] is False
        assert result["challenge_count"] == 3  # Default

    @pytest.mark.asyncio
    async def test_vote_returns_themes_and_convergence(self) -> None:
        """Test VOTE returns themes and convergence (default True)."""
        stub = PhaseSummaryGeneratorStub()

        result = await stub.generate_phase_summary(
            phase=DeliberationPhase.VOTE,
            transcript="Test transcript",
        )

        assert result["themes"] == DEFAULT_THEMES
        assert result["convergence_reached"] is True
        assert result["challenge_count"] is None


class TestCustomResponses:
    """Tests for custom configured responses."""

    @pytest.mark.asyncio
    async def test_uses_custom_themes(self) -> None:
        """Test stub uses configured custom themes."""
        custom_themes = ["security", "privacy"]
        stub = PhaseSummaryGeneratorStub(themes=custom_themes)

        result = await stub.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
        )

        assert result["themes"] == custom_themes

    @pytest.mark.asyncio
    async def test_uses_custom_convergence(self) -> None:
        """Test stub uses configured convergence value."""
        stub = PhaseSummaryGeneratorStub(convergence_reached=False)

        result = await stub.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript="Test",
        )

        assert result["convergence_reached"] is False

    @pytest.mark.asyncio
    async def test_uses_custom_challenge_count(self) -> None:
        """Test stub uses configured challenge count."""
        stub = PhaseSummaryGeneratorStub(challenge_count=10)

        result = await stub.generate_phase_summary(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript="Test",
        )

        assert result["challenge_count"] == 10


class TestHelperMethods:
    """Tests for stub helper methods."""

    @pytest.mark.asyncio
    async def test_reset_clears_calls(self) -> None:
        """Test reset() clears call history."""
        stub = PhaseSummaryGeneratorStub()
        await stub.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
        )

        assert stub.call_count == 1

        stub.reset()

        assert stub.call_count == 0
        assert stub.calls == []

    @pytest.mark.asyncio
    async def test_call_count_property(self) -> None:
        """Test call_count property returns correct count."""
        stub = PhaseSummaryGeneratorStub()

        assert stub.call_count == 0

        await stub.generate_phase_summary(DeliberationPhase.ASSESS, "Test 1")
        assert stub.call_count == 1

        await stub.generate_phase_summary(DeliberationPhase.POSITION, "Test 2")
        assert stub.call_count == 2

    @pytest.mark.asyncio
    async def test_was_called_with_phase(self) -> None:
        """Test was_called_with_phase() helper."""
        stub = PhaseSummaryGeneratorStub()

        await stub.generate_phase_summary(DeliberationPhase.ASSESS, "Test")

        assert stub.was_called_with_phase(DeliberationPhase.ASSESS) is True
        assert stub.was_called_with_phase(DeliberationPhase.POSITION) is False

    @pytest.mark.asyncio
    async def test_get_transcript_for_phase(self) -> None:
        """Test get_transcript_for_phase() helper."""
        stub = PhaseSummaryGeneratorStub()

        await stub.generate_phase_summary(
            phase=DeliberationPhase.ASSESS,
            transcript="ASSESS transcript",
        )
        await stub.generate_phase_summary(
            phase=DeliberationPhase.POSITION,
            transcript="POSITION transcript",
        )

        assert (
            stub.get_transcript_for_phase(DeliberationPhase.ASSESS)
            == "ASSESS transcript"
        )
        assert (
            stub.get_transcript_for_phase(DeliberationPhase.POSITION)
            == "POSITION transcript"
        )
        assert stub.get_transcript_for_phase(DeliberationPhase.VOTE) is None


class TestAugmentPhaseMetadata:
    """Tests for augment_phase_metadata method."""

    @pytest.mark.asyncio
    async def test_augments_empty_metadata(self) -> None:
        """Test augments when no existing metadata provided."""
        stub = PhaseSummaryGeneratorStub()

        result = await stub.augment_phase_metadata(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
        )

        assert "themes" in result
        assert "convergence_reached" in result
        assert "challenge_count" in result

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self) -> None:
        """Test preserves existing metadata fields."""
        stub = PhaseSummaryGeneratorStub()
        existing = {"custom_field": "value", "count": 42}

        result = await stub.augment_phase_metadata(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
            existing_metadata=existing,
        )

        assert result["custom_field"] == "value"
        assert result["count"] == 42
        assert "themes" in result

    @pytest.mark.asyncio
    async def test_records_call(self) -> None:
        """Test augment records the call."""
        stub = PhaseSummaryGeneratorStub()

        await stub.augment_phase_metadata(
            phase=DeliberationPhase.ASSESS,
            transcript="Test",
        )

        assert stub.call_count == 1
        assert stub.was_called_with_phase(DeliberationPhase.ASSESS)
