"""Unit tests for CessationDeliberationEventPayload (Story 7.8, FR135).

Tests the cessation deliberation event payload which captures the final
deliberation before cessation including all 72 Archon votes and reasoning.

Constitutional Constraints:
- FR135: Before cessation, final deliberation SHALL be recorded and immutable
- FR12: Dissent percentages visible in every vote tally
- CT-12: Witnessing creates accountability

Test Coverage:
- ArchonPosition enum values
- ArchonDeliberation dataclass validation
- CessationDeliberationEventPayload validation
- 72-archon requirement enforcement
- Vote counts matching positions
- signable_content() determinism
- to_dict() serialization
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.cessation_deliberation import (
    CESSATION_DELIBERATION_EVENT_TYPE,
    ArchonDeliberation,
    ArchonPosition,
    CessationDeliberationEventPayload,
)
from src.domain.events.collective_output import VoteCounts


class TestArchonPosition:
    """Tests for ArchonPosition enum."""

    def test_support_cessation_value(self) -> None:
        """ArchonPosition should have SUPPORT_CESSATION."""
        assert ArchonPosition.SUPPORT_CESSATION.value == "SUPPORT_CESSATION"

    def test_oppose_cessation_value(self) -> None:
        """ArchonPosition should have OPPOSE_CESSATION."""
        assert ArchonPosition.OPPOSE_CESSATION.value == "OPPOSE_CESSATION"

    def test_abstain_value(self) -> None:
        """ArchonPosition should have ABSTAIN."""
        assert ArchonPosition.ABSTAIN.value == "ABSTAIN"

    def test_all_positions_exist(self) -> None:
        """All three position types should exist."""
        assert len(ArchonPosition) == 3


class TestArchonDeliberation:
    """Tests for ArchonDeliberation dataclass."""

    def test_create_support_deliberation(self) -> None:
        """Should create a support deliberation with reasoning."""
        timestamp = datetime.now(timezone.utc)
        deliberation = ArchonDeliberation(
            archon_id="archon-001",
            position=ArchonPosition.SUPPORT_CESSATION,
            reasoning="The system has violated constitutional constraints.",
            statement_timestamp=timestamp,
        )
        assert deliberation.archon_id == "archon-001"
        assert deliberation.position == ArchonPosition.SUPPORT_CESSATION
        assert (
            deliberation.reasoning
            == "The system has violated constitutional constraints."
        )
        assert deliberation.statement_timestamp == timestamp

    def test_create_oppose_deliberation(self) -> None:
        """Should create an oppose deliberation with reasoning."""
        timestamp = datetime.now(timezone.utc)
        deliberation = ArchonDeliberation(
            archon_id="archon-002",
            position=ArchonPosition.OPPOSE_CESSATION,
            reasoning="I believe the issues can be resolved without cessation.",
            statement_timestamp=timestamp,
        )
        assert deliberation.position == ArchonPosition.OPPOSE_CESSATION

    def test_create_abstain_deliberation_with_empty_reasoning(self) -> None:
        """Abstain may have empty reasoning."""
        timestamp = datetime.now(timezone.utc)
        deliberation = ArchonDeliberation(
            archon_id="archon-003",
            position=ArchonPosition.ABSTAIN,
            reasoning="",
            statement_timestamp=timestamp,
        )
        assert deliberation.position == ArchonPosition.ABSTAIN
        assert deliberation.reasoning == ""

    def test_deliberation_is_frozen(self) -> None:
        """ArchonDeliberation should be immutable (frozen)."""
        timestamp = datetime.now(timezone.utc)
        deliberation = ArchonDeliberation(
            archon_id="archon-001",
            position=ArchonPosition.SUPPORT_CESSATION,
            reasoning="Test",
            statement_timestamp=timestamp,
        )
        with pytest.raises(AttributeError):
            deliberation.archon_id = "modified"  # type: ignore[misc]

    def test_to_dict_serialization(self) -> None:
        """to_dict should serialize deliberation correctly."""
        timestamp = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        deliberation = ArchonDeliberation(
            archon_id="archon-001",
            position=ArchonPosition.SUPPORT_CESSATION,
            reasoning="Test reasoning",
            statement_timestamp=timestamp,
        )
        result = deliberation.to_dict()
        assert result["archon_id"] == "archon-001"
        assert result["position"] == "SUPPORT_CESSATION"
        assert result["reasoning"] == "Test reasoning"
        assert result["statement_timestamp"] == "2026-01-08T12:00:00+00:00"


class TestCessationDeliberationEventPayload:
    """Tests for CessationDeliberationEventPayload."""

    def _create_72_deliberations(
        self,
        yes_count: int = 50,
        no_count: int = 20,
        abstain_count: int = 2,
    ) -> tuple[ArchonDeliberation, ...]:
        """Helper to create exactly 72 Archon deliberations.

        Args:
            yes_count: Number of SUPPORT_CESSATION votes.
            no_count: Number of OPPOSE_CESSATION votes.
            abstain_count: Number of ABSTAIN votes.

        Returns:
            Tuple of 72 ArchonDeliberation instances.
        """
        assert yes_count + no_count + abstain_count == 72, "Must total 72"

        deliberations = []
        timestamp = datetime.now(timezone.utc)

        for i in range(yes_count):
            deliberations.append(
                ArchonDeliberation(
                    archon_id=f"archon-{i + 1:03d}",
                    position=ArchonPosition.SUPPORT_CESSATION,
                    reasoning=f"Support reasoning from archon {i + 1}",
                    statement_timestamp=timestamp,
                )
            )

        for i in range(no_count):
            deliberations.append(
                ArchonDeliberation(
                    archon_id=f"archon-{yes_count + i + 1:03d}",
                    position=ArchonPosition.OPPOSE_CESSATION,
                    reasoning=f"Oppose reasoning from archon {yes_count + i + 1}",
                    statement_timestamp=timestamp,
                )
            )

        for i in range(abstain_count):
            deliberations.append(
                ArchonDeliberation(
                    archon_id=f"archon-{yes_count + no_count + i + 1:03d}",
                    position=ArchonPosition.ABSTAIN,
                    reasoning="",
                    statement_timestamp=timestamp,
                )
            )

        return tuple(deliberations)

    def test_create_valid_payload(self) -> None:
        """Should create a valid payload with 72 archons."""
        deliberation_id = uuid4()
        started = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        recorded = datetime(2026, 1, 8, 12, 1, 0, tzinfo=timezone.utc)

        deliberations = self._create_72_deliberations(50, 20, 2)

        payload = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=recorded,
            duration_seconds=7200,  # 2 hours
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,  # (20+2)/72 minority
        )

        assert payload.deliberation_id == deliberation_id
        assert payload.deliberation_started_at == started
        assert payload.deliberation_ended_at == ended
        assert payload.vote_recorded_at == recorded
        assert payload.duration_seconds == 7200
        assert len(payload.archon_deliberations) == 72
        assert payload.vote_counts.total == 72
        assert payload.dissent_percentage == 30.56

    def test_event_type_constant(self) -> None:
        """Event type constant should be correctly defined."""
        assert CESSATION_DELIBERATION_EVENT_TYPE == "cessation.deliberation"

    def test_reject_less_than_72_archons(self) -> None:
        """Should reject payload with fewer than 72 archons."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        # Create only 71 deliberations
        deliberations = tuple(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning="Test",
                statement_timestamp=started,
            )
            for i in range(71)
        )

        with pytest.raises(ValueError, match="72 Archon"):
            CessationDeliberationEventPayload(
                deliberation_id=deliberation_id,
                deliberation_started_at=started,
                deliberation_ended_at=ended,
                vote_recorded_at=ended,
                duration_seconds=100,
                archon_deliberations=deliberations,
                vote_counts=VoteCounts(yes_count=71, no_count=0, abstain_count=0),
                dissent_percentage=0.0,
            )

    def test_reject_more_than_72_archons(self) -> None:
        """Should reject payload with more than 72 archons."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        # Create 73 deliberations
        deliberations = tuple(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning="Test",
                statement_timestamp=started,
            )
            for i in range(73)
        )

        with pytest.raises(ValueError, match="72 Archon"):
            CessationDeliberationEventPayload(
                deliberation_id=deliberation_id,
                deliberation_started_at=started,
                deliberation_ended_at=ended,
                vote_recorded_at=ended,
                duration_seconds=100,
                archon_deliberations=deliberations,
                vote_counts=VoteCounts(yes_count=73, no_count=0, abstain_count=0),
                dissent_percentage=0.0,
            )

    def test_vote_counts_must_match_positions(self) -> None:
        """Vote counts must match the positions in deliberations."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        # Create 72 deliberations with 50 yes, 20 no, 2 abstain
        deliberations = self._create_72_deliberations(50, 20, 2)

        # But provide mismatched vote counts
        with pytest.raises(ValueError, match="vote counts.*match"):
            CessationDeliberationEventPayload(
                deliberation_id=deliberation_id,
                deliberation_started_at=started,
                deliberation_ended_at=ended,
                vote_recorded_at=ended,
                duration_seconds=100,
                archon_deliberations=deliberations,
                vote_counts=VoteCounts(
                    yes_count=40, no_count=30, abstain_count=2
                ),  # Wrong!
                dissent_percentage=44.44,
            )

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content() should return identical bytes for same data."""
        deliberation_id = uuid4()
        started = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)

        deliberations = self._create_72_deliberations(50, 20, 2)

        payload1 = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=7200,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,
        )

        payload2 = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=7200,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_differs_for_different_data(self) -> None:
        """signable_content() should differ for different data."""
        started = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)

        deliberations = self._create_72_deliberations(50, 20, 2)

        payload1 = CessationDeliberationEventPayload(
            deliberation_id=uuid4(),  # Different ID
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=7200,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,
        )

        payload2 = CessationDeliberationEventPayload(
            deliberation_id=uuid4(),  # Different ID
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=7200,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,
        )

        assert payload1.signable_content() != payload2.signable_content()

    def test_to_dict_serialization(self) -> None:
        """to_dict should serialize the payload correctly."""
        deliberation_id = uuid4()
        started = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)

        deliberations = self._create_72_deliberations(50, 20, 2)

        payload = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=7200,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,
        )

        result = payload.to_dict()

        assert result["deliberation_id"] == str(deliberation_id)
        assert result["deliberation_started_at"] == "2026-01-08T10:00:00+00:00"
        assert result["deliberation_ended_at"] == "2026-01-08T12:00:00+00:00"
        assert result["duration_seconds"] == 7200
        assert len(result["archon_deliberations"]) == 72
        assert result["vote_counts"]["yes_count"] == 50
        assert result["vote_counts"]["no_count"] == 20
        assert result["vote_counts"]["abstain_count"] == 2
        assert result["dissent_percentage"] == 30.56

    def test_payload_is_frozen(self) -> None:
        """CessationDeliberationEventPayload should be immutable."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        deliberations = self._create_72_deliberations(50, 20, 2)

        payload = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=100,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,
        )

        with pytest.raises(AttributeError):
            payload.deliberation_id = uuid4()  # type: ignore[misc]

    def test_all_abstain_valid(self) -> None:
        """All 72 abstaining should be valid (unusual but allowed)."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        deliberations = self._create_72_deliberations(0, 0, 72)

        payload = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=100,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=0, no_count=0, abstain_count=72),
            dissent_percentage=0.0,  # No majority = 0% dissent
        )

        assert payload.vote_counts.total == 72

    def test_unanimous_support(self) -> None:
        """All 72 supporting cessation should be valid."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        deliberations = self._create_72_deliberations(72, 0, 0)

        payload = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started,
            deliberation_ended_at=ended,
            vote_recorded_at=ended,
            duration_seconds=100,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            dissent_percentage=0.0,  # Unanimous = 0% dissent
        )

        assert payload.vote_counts.yes_count == 72
        assert payload.dissent_percentage == 0.0

    def test_dissent_percentage_range(self) -> None:
        """Dissent percentage must be between 0 and 100."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        deliberations = self._create_72_deliberations(50, 20, 2)

        with pytest.raises(ValueError, match="dissent_percentage.*0.*100"):
            CessationDeliberationEventPayload(
                deliberation_id=deliberation_id,
                deliberation_started_at=started,
                deliberation_ended_at=ended,
                vote_recorded_at=ended,
                duration_seconds=100,
                archon_deliberations=deliberations,
                vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
                dissent_percentage=150.0,  # Invalid
            )

    def test_negative_duration_rejected(self) -> None:
        """Duration must be non-negative."""
        deliberation_id = uuid4()
        started = datetime.now(timezone.utc)
        ended = datetime.now(timezone.utc)

        deliberations = self._create_72_deliberations(50, 20, 2)

        with pytest.raises(ValueError, match="duration"):
            CessationDeliberationEventPayload(
                deliberation_id=deliberation_id,
                deliberation_started_at=started,
                deliberation_ended_at=ended,
                vote_recorded_at=ended,
                duration_seconds=-100,  # Invalid
                archon_deliberations=deliberations,
                vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
                dissent_percentage=30.56,
            )
