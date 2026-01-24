"""Unit tests for DeliberationSummary domain model (Story 7.4, FR-7.4).

Tests the deliberation summary model that provides mediated access
to deliberation outcomes per Ruling-2 (Tiered Transcript Access).

Constitutional Constraints:
- Ruling-2: Tiered transcript access
- FR-7.4: System SHALL provide deliberation summary
- CT-12: Hash references prove witnessing
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
)
from src.domain.models.deliberation_summary import (
    DeliberationSummary,
    EscalationTrigger,
    PhaseSummaryItem,
)


class TestPhaseSummaryItem:
    """Tests for PhaseSummaryItem dataclass."""

    def test_create_basic_phase_summary(self) -> None:
        """Test creating a basic phase summary item."""
        summary = PhaseSummaryItem(
            phase=DeliberationPhase.ASSESS,
            duration_seconds=120,
            transcript_hash_hex="a" * 64,
        )

        assert summary.phase == DeliberationPhase.ASSESS
        assert summary.duration_seconds == 120
        assert summary.transcript_hash_hex == "a" * 64
        assert summary.themes == ()
        assert summary.convergence_reached is None

    def test_create_phase_summary_with_themes(self) -> None:
        """Test creating phase summary with themes (metadata, not content)."""
        summary = PhaseSummaryItem(
            phase=DeliberationPhase.POSITION,
            duration_seconds=180,
            transcript_hash_hex="b" * 64,
            themes=("constitutional", "procedural"),
        )

        assert summary.themes == ("constitutional", "procedural")

    def test_create_phase_summary_with_convergence(self) -> None:
        """Test creating phase summary with convergence indicator."""
        summary = PhaseSummaryItem(
            phase=DeliberationPhase.CROSS_EXAMINE,
            duration_seconds=240,
            transcript_hash_hex="c" * 64,
            convergence_reached=True,
        )

        assert summary.convergence_reached is True

    def test_phase_summary_to_dict(self) -> None:
        """Test serialization to dictionary with schema_version."""
        summary = PhaseSummaryItem(
            phase=DeliberationPhase.VOTE,
            duration_seconds=60,
            transcript_hash_hex="d" * 64,
            themes=("consensus",),
            convergence_reached=True,
        )

        result = summary.to_dict()

        assert result["phase"] == "VOTE"
        assert result["duration_seconds"] == 60
        assert result["transcript_hash_hex"] == "d" * 64
        assert result["themes"] == ["consensus"]
        assert result["convergence_reached"] is True
        assert result["schema_version"] == 1

    def test_phase_summary_to_dict_minimal(self) -> None:
        """Test to_dict without optional fields."""
        summary = PhaseSummaryItem(
            phase=DeliberationPhase.ASSESS,
            duration_seconds=100,
            transcript_hash_hex="e" * 64,
        )

        result = summary.to_dict()

        assert "themes" not in result  # Empty tuple omitted
        assert "convergence_reached" not in result  # None omitted


class TestDeliberationSummary:
    """Tests for DeliberationSummary dataclass."""

    @pytest.fixture
    def basic_phase_summaries(self) -> tuple[PhaseSummaryItem, ...]:
        """Create basic phase summaries for testing."""
        return (
            PhaseSummaryItem(
                phase=DeliberationPhase.ASSESS,
                duration_seconds=120,
                transcript_hash_hex="a" * 64,
            ),
            PhaseSummaryItem(
                phase=DeliberationPhase.POSITION,
                duration_seconds=180,
                transcript_hash_hex="b" * 64,
            ),
            PhaseSummaryItem(
                phase=DeliberationPhase.CROSS_EXAMINE,
                duration_seconds=240,
                transcript_hash_hex="c" * 64,
            ),
            PhaseSummaryItem(
                phase=DeliberationPhase.VOTE,
                duration_seconds=60,
                transcript_hash_hex="d" * 64,
            ),
        )

    def test_create_acknowledge_summary(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test creating summary for ACKNOWLEDGE outcome (AC-1)."""
        petition_id = uuid4()
        completed_at = datetime.now(timezone.utc)

        summary = DeliberationSummary(
            petition_id=petition_id,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            vote_breakdown="3-0",
            has_dissent=False,
            phase_summaries=basic_phase_summaries,
            duration_seconds=600,
            completed_at=completed_at,
        )

        assert summary.petition_id == petition_id
        assert summary.outcome == DeliberationOutcome.ACKNOWLEDGE
        assert summary.vote_breakdown == "3-0"
        assert summary.has_dissent is False
        assert len(summary.phase_summaries) == 4
        assert summary.escalation_trigger is None
        assert summary.escalation_reason is None

    def test_create_refer_summary_with_dissent(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test creating summary for REFER with dissent (AC-1)."""
        petition_id = uuid4()

        summary = DeliberationSummary(
            petition_id=petition_id,
            outcome=DeliberationOutcome.REFER,
            vote_breakdown="2-1",
            has_dissent=True,
            phase_summaries=basic_phase_summaries,
            duration_seconds=700,
            completed_at=datetime.now(timezone.utc),
        )

        assert summary.outcome == DeliberationOutcome.REFER
        assert summary.vote_breakdown == "2-1"
        assert summary.has_dissent is True

    def test_create_escalate_summary_with_trigger(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test creating summary for ESCALATE with trigger (AC-6, AC-7)."""
        petition_id = uuid4()

        summary = DeliberationSummary(
            petition_id=petition_id,
            outcome=DeliberationOutcome.ESCALATE,
            vote_breakdown="2-1",
            has_dissent=True,
            phase_summaries=basic_phase_summaries,
            duration_seconds=800,
            completed_at=datetime.now(timezone.utc),
            escalation_trigger=EscalationTrigger.DELIBERATION,
        )

        assert summary.outcome == DeliberationOutcome.ESCALATE
        assert summary.escalation_trigger == EscalationTrigger.DELIBERATION

    def test_invalid_escalation_trigger_for_non_escalate(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test escalation_trigger must be None for non-ESCALATE outcomes."""
        with pytest.raises(ValueError, match="escalation_trigger should be None"):
            DeliberationSummary(
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                vote_breakdown="3-0",
                has_dissent=False,
                phase_summaries=basic_phase_summaries,
                duration_seconds=600,
                completed_at=datetime.now(timezone.utc),
                escalation_trigger=EscalationTrigger.DELIBERATION,  # Invalid!
            )

    def test_missing_escalation_trigger_for_escalate(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test escalation_trigger required for ESCALATE outcome."""
        with pytest.raises(ValueError, match="escalation_trigger is required"):
            DeliberationSummary(
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ESCALATE,
                vote_breakdown="2-1",
                has_dissent=True,
                phase_summaries=basic_phase_summaries,
                duration_seconds=600,
                completed_at=datetime.now(timezone.utc),
                # Missing escalation_trigger!
            )

    def test_invalid_vote_breakdown_format(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test vote_breakdown must be in X-Y format."""
        with pytest.raises(ValueError, match="format"):
            DeliberationSummary(
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                vote_breakdown="invalid",  # Wrong format
                has_dissent=False,
                phase_summaries=basic_phase_summaries,
                duration_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )

    def test_invalid_vote_breakdown_sum(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test vote_breakdown must sum to 3."""
        with pytest.raises(ValueError, match="must sum to 3"):
            DeliberationSummary(
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                vote_breakdown="2-2",  # Sums to 4, not 3
                has_dissent=False,
                phase_summaries=basic_phase_summaries,
                duration_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )

    def test_vote_breakdown_majority_minority(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test vote_breakdown majority >= minority."""
        with pytest.raises(ValueError, match="majority must be >= minority"):
            DeliberationSummary(
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                vote_breakdown="1-2",  # Minority > majority
                has_dissent=False,
                phase_summaries=basic_phase_summaries,
                duration_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )

    def test_naive_datetime_rejected(
        self, basic_phase_summaries: tuple[PhaseSummaryItem, ...]
    ) -> None:
        """Test completed_at must be timezone-aware."""
        with pytest.raises(ValueError, match="timezone-aware"):
            DeliberationSummary(
                petition_id=uuid4(),
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                vote_breakdown="3-0",
                has_dissent=False,
                phase_summaries=basic_phase_summaries,
                duration_seconds=600,
                completed_at=datetime.now(),  # Naive datetime!
            )


class TestDeliberationSummaryFactoryMethods:
    """Tests for DeliberationSummary factory methods."""

    def test_from_auto_escalation(self) -> None:
        """Test creating summary for auto-escalated petition (AC-2)."""
        petition_id = uuid4()

        summary = DeliberationSummary.from_auto_escalation(
            petition_id=petition_id,
            escalation_reason="Co-signer threshold reached",
        )

        assert summary.petition_id == petition_id
        assert summary.outcome == DeliberationOutcome.ESCALATE
        assert summary.vote_breakdown == "0-0"  # No votes
        assert summary.has_dissent is False
        assert summary.phase_summaries == ()  # No phases
        assert summary.duration_seconds == 0
        assert summary.escalation_trigger == EscalationTrigger.AUTO_ESCALATED
        assert summary.escalation_reason == "Co-signer threshold reached"
        assert summary.rounds_attempted == 0

    def test_from_auto_escalation_with_timestamp(self) -> None:
        """Test auto-escalation with custom timestamp."""
        petition_id = uuid4()
        completed_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        summary = DeliberationSummary.from_auto_escalation(
            petition_id=petition_id,
            escalation_reason="Threshold reached",
            completed_at=completed_at,
        )

        assert summary.completed_at == completed_at

    def test_from_timeout(self) -> None:
        """Test creating summary for timeout escalation (AC-6)."""
        petition_id = uuid4()
        phase_summaries = (
            PhaseSummaryItem(
                phase=DeliberationPhase.ASSESS,
                duration_seconds=120,
                transcript_hash_hex="a" * 64,
            ),
            PhaseSummaryItem(
                phase=DeliberationPhase.POSITION,
                duration_seconds=180,
                transcript_hash_hex="b" * 64,
            ),
        )
        completed_at = datetime.now(timezone.utc)

        summary = DeliberationSummary.from_timeout(
            petition_id=petition_id,
            phase_summaries=phase_summaries,
            duration_seconds=300,
            completed_at=completed_at,
        )

        assert summary.outcome == DeliberationOutcome.ESCALATE
        assert summary.escalation_trigger == EscalationTrigger.TIMEOUT
        assert summary.timed_out is True
        assert len(summary.phase_summaries) == 2  # Partial phases

    def test_from_deadlock(self) -> None:
        """Test creating summary for deadlock escalation (AC-7)."""
        petition_id = uuid4()
        phase_summaries = (
            PhaseSummaryItem(
                phase=DeliberationPhase.ASSESS,
                duration_seconds=120,
                transcript_hash_hex="a" * 64,
            ),
        )
        completed_at = datetime.now(timezone.utc)

        summary = DeliberationSummary.from_deadlock(
            petition_id=petition_id,
            phase_summaries=phase_summaries,
            duration_seconds=900,
            completed_at=completed_at,
            rounds_attempted=3,
        )

        assert summary.outcome == DeliberationOutcome.ESCALATE
        assert summary.escalation_trigger == EscalationTrigger.DEADLOCK
        assert summary.timed_out is False
        assert summary.rounds_attempted == 3
        assert "3" in (summary.escalation_reason or "")


class TestDeliberationSummarySerialization:
    """Tests for DeliberationSummary serialization."""

    def test_to_dict_basic(self) -> None:
        """Test to_dict includes all fields with schema_version."""
        petition_id = uuid4()
        completed_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        phase_summaries = (
            PhaseSummaryItem(
                phase=DeliberationPhase.ASSESS,
                duration_seconds=120,
                transcript_hash_hex="a" * 64,
            ),
        )

        summary = DeliberationSummary(
            petition_id=petition_id,
            outcome=DeliberationOutcome.ACKNOWLEDGE,
            vote_breakdown="3-0",
            has_dissent=False,
            phase_summaries=phase_summaries,
            duration_seconds=120,
            completed_at=completed_at,
        )

        result = summary.to_dict()

        assert result["petition_id"] == str(petition_id)
        assert result["outcome"] == "ACKNOWLEDGE"
        assert result["vote_breakdown"] == "3-0"
        assert result["has_dissent"] is False
        assert len(result["phase_summaries"]) == 1
        assert result["duration_seconds"] == 120
        assert result["timed_out"] is False
        assert result["rounds_attempted"] == 1
        assert result["schema_version"] == 1
        assert "escalation_trigger" not in result  # None omitted
        assert "escalation_reason" not in result  # None omitted

    def test_to_dict_with_escalation(self) -> None:
        """Test to_dict includes escalation fields when present."""
        summary = DeliberationSummary.from_timeout(
            petition_id=uuid4(),
            phase_summaries=(),
            duration_seconds=300,
            completed_at=datetime.now(timezone.utc),
        )

        result = summary.to_dict()

        assert result["escalation_trigger"] == "TIMEOUT"
        assert "escalation_reason" in result
