"""Unit tests for deadlock handler service (Story 2B.3, FR-11.10).

Tests the DeadlockHandlerService for correct deadlock detection, round
transitions, and auto-ESCALATE behavior.

Constitutional Constraints:
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment - deadlock is collective conclusion
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.services.deadlock_handler_service import (
    DeadlockHandlerService,
)
from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    SINGLE_ROUND_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.errors.deliberation import SessionAlreadyCompleteError
from src.domain.events.deadlock import (
    CrossExamineRoundTriggeredEvent,
    DeadlockDetectedEvent,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)


def _create_test_session(
    phase: DeliberationPhase = DeliberationPhase.VOTE,
    round_count: int = 1,
) -> DeliberationSession:
    """Create a test deliberation session in specified phase."""
    archon1, archon2, archon3 = uuid4(), uuid4(), uuid4()
    session = DeliberationSession.create(
        session_id=uuid4(),
        petition_id=uuid4(),
        assigned_archons=(archon1, archon2, archon3),
    )
    # Transition through phases to reach target phase
    if phase in (
        DeliberationPhase.POSITION,
        DeliberationPhase.CROSS_EXAMINE,
        DeliberationPhase.VOTE,
    ):
        session = session.with_phase(DeliberationPhase.POSITION)
    if phase in (DeliberationPhase.CROSS_EXAMINE, DeliberationPhase.VOTE):
        session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)
    if phase == DeliberationPhase.VOTE:
        session = session.with_phase(DeliberationPhase.VOTE)

    # Set round_count if > 1
    if round_count > 1:
        # Simulate previous rounds by adding vote history
        for _ in range(round_count - 1):
            vote_dist = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}
            session = session.with_new_round(vote_dist)
            # Return to VOTE phase for testing
            session = session.with_phase(DeliberationPhase.VOTE)

    return session


class TestIsDeadlockVotePattern:
    """Tests for is_deadlock_vote_pattern method."""

    def test_1_1_1_split_is_deadlock(self) -> None:
        """1-1-1 vote split (all different) is a deadlock pattern."""
        service = DeadlockHandlerService()

        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}
        assert service.is_deadlock_vote_pattern(vote_distribution) is True

    def test_2_1_split_is_not_deadlock(self) -> None:
        """2-1 vote split is NOT a deadlock (supermajority reached)."""
        service = DeadlockHandlerService()

        vote_distribution = {"ACKNOWLEDGE": 2, "REFER": 1}
        assert service.is_deadlock_vote_pattern(vote_distribution) is False

    def test_3_0_unanimous_is_not_deadlock(self) -> None:
        """3-0 unanimous vote is NOT a deadlock."""
        service = DeadlockHandlerService()

        vote_distribution = {"ESCALATE": 3}
        assert service.is_deadlock_vote_pattern(vote_distribution) is False

    def test_wrong_total_votes_is_not_deadlock(self) -> None:
        """Vote distribution not summing to 3 is not deadlock."""
        service = DeadlockHandlerService()

        # Only 2 votes
        assert service.is_deadlock_vote_pattern({"A": 1, "B": 1}) is False

        # 4 votes
        assert service.is_deadlock_vote_pattern({"A": 2, "B": 1, "C": 1}) is False

    def test_empty_distribution_is_not_deadlock(self) -> None:
        """Empty vote distribution is not deadlock."""
        service = DeadlockHandlerService()

        assert service.is_deadlock_vote_pattern({}) is False

    def test_two_outcomes_with_1_1_is_not_deadlock(self) -> None:
        """1-1 with only 2 outcomes is not deadlock (not 3 votes)."""
        service = DeadlockHandlerService()

        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1}
        assert service.is_deadlock_vote_pattern(vote_distribution) is False


class TestCanContinueDeliberation:
    """Tests for can_continue_deliberation method."""

    def test_round_1_can_continue(self) -> None:
        """Round 1 of 3 can continue to more rounds."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)

        assert service.can_continue_deliberation(session, max_rounds=3) is True

    def test_round_2_can_continue(self) -> None:
        """Round 2 of 3 can continue to round 3."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=2)

        assert service.can_continue_deliberation(session, max_rounds=3) is True

    def test_round_3_cannot_continue(self) -> None:
        """Round 3 of 3 cannot continue (max reached)."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)

        assert service.can_continue_deliberation(session, max_rounds=3) is False

    def test_uses_config_max_rounds_by_default(self) -> None:
        """Uses configured max_rounds when not specified."""
        config = DeliberationConfig(timeout_seconds=300, max_rounds=5)
        service = DeadlockHandlerService(config=config)
        session = _create_test_session(round_count=4)

        # Round 4 of 5 can continue
        assert service.can_continue_deliberation(session) is True

    def test_round_at_max_cannot_continue(self) -> None:
        """Round at max_rounds cannot continue."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)

        assert service.can_continue_deliberation(session, max_rounds=3) is False


class TestHandleNoConsensus:
    """Tests for handle_no_consensus method."""

    @pytest.mark.asyncio
    async def test_triggers_new_round_when_under_max(self) -> None:
        """Triggers new round when round_count < max_rounds."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        # Should be CrossExamineRoundTriggeredEvent
        assert isinstance(event, CrossExamineRoundTriggeredEvent)
        assert event.round_number == 2
        assert updated.phase == DeliberationPhase.CROSS_EXAMINE
        assert updated.round_count == 2
        assert updated.is_deadlocked is False

    @pytest.mark.asyncio
    async def test_triggers_deadlock_when_at_max(self) -> None:
        """Triggers deadlock escalation when round_count >= max_rounds."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        # Should be DeadlockDetectedEvent
        assert isinstance(event, DeadlockDetectedEvent)
        assert event.reason == "DEADLOCK_MAX_ROUNDS_EXCEEDED"
        assert updated.outcome == DeliberationOutcome.ESCALATE
        assert updated.is_deadlocked is True
        assert updated.deadlock_reason == "DEADLOCK_MAX_ROUNDS_EXCEEDED"

    @pytest.mark.asyncio
    async def test_rejects_non_deadlock_pattern(self) -> None:
        """Raises ValueError for non-deadlock vote patterns."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        # 2-1 is not a deadlock pattern
        vote_distribution = {"ACKNOWLEDGE": 2, "REFER": 1}

        with pytest.raises(ValueError, match="not a deadlock pattern"):
            await service.handle_no_consensus(session, vote_distribution, max_rounds=3)

    @pytest.mark.asyncio
    async def test_rejects_completed_session(self) -> None:
        """Raises SessionAlreadyCompleteError for completed sessions."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        # Complete the session
        session = session.with_votes(
            {
                session.assigned_archons[0]: DeliberationOutcome.ACKNOWLEDGE,
                session.assigned_archons[1]: DeliberationOutcome.ACKNOWLEDGE,
                session.assigned_archons[2]: DeliberationOutcome.REFER,
            }
        )
        session = session.with_outcome()  # Now COMPLETE

        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        with pytest.raises(SessionAlreadyCompleteError):
            await service.handle_no_consensus(session, vote_distribution, max_rounds=3)


class TestTriggerNewRound:
    """Tests for trigger_new_round method."""

    @pytest.mark.asyncio
    async def test_increments_round_count(self) -> None:
        """New round increments round_count."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_new_round(session, vote_distribution)

        assert updated.round_count == 2

    @pytest.mark.asyncio
    async def test_returns_to_cross_examine_phase(self) -> None:
        """New round returns to CROSS_EXAMINE phase."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_new_round(session, vote_distribution)

        assert updated.phase == DeliberationPhase.CROSS_EXAMINE

    @pytest.mark.asyncio
    async def test_records_vote_history(self) -> None:
        """New round records previous votes in history."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_new_round(session, vote_distribution)

        assert len(updated.votes_by_round) == 1
        assert updated.votes_by_round[0] == vote_distribution

    @pytest.mark.asyncio
    async def test_clears_current_votes(self) -> None:
        """New round clears current votes for fresh voting."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        # Add some votes first
        session = session.with_votes(
            {
                session.assigned_archons[0]: DeliberationOutcome.ACKNOWLEDGE,
                session.assigned_archons[1]: DeliberationOutcome.REFER,
                session.assigned_archons[2]: DeliberationOutcome.ESCALATE,
            }
        )
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_new_round(session, vote_distribution)

        assert len(updated.votes) == 0

    @pytest.mark.asyncio
    async def test_emits_cross_examine_round_triggered_event(self) -> None:
        """Emits CrossExamineRoundTriggeredEvent with correct data."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_new_round(session, vote_distribution)

        assert isinstance(event, CrossExamineRoundTriggeredEvent)
        assert event.session_id == session.session_id
        assert event.petition_id == session.petition_id
        assert event.round_number == 2
        assert event.previous_vote_distribution == vote_distribution
        assert event.participating_archons == session.assigned_archons


class TestTriggerDeadlockEscalation:
    """Tests for trigger_deadlock_escalation method."""

    @pytest.mark.asyncio
    async def test_sets_escalate_outcome(self) -> None:
        """Deadlock sets ESCALATE outcome per FR-11.10."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_deadlock_escalation(
            session, vote_distribution
        )

        assert updated.outcome == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_sets_is_deadlocked_flag(self) -> None:
        """Deadlock sets is_deadlocked=True."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_deadlock_escalation(
            session, vote_distribution
        )

        assert updated.is_deadlocked is True

    @pytest.mark.asyncio
    async def test_sets_deadlock_reason(self) -> None:
        """Deadlock sets deadlock_reason."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_deadlock_escalation(
            session, vote_distribution
        )

        assert updated.deadlock_reason == "DEADLOCK_MAX_ROUNDS_EXCEEDED"

    @pytest.mark.asyncio
    async def test_transitions_to_complete_phase(self) -> None:
        """Deadlock transitions to COMPLETE phase."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_deadlock_escalation(
            session, vote_distribution
        )

        assert updated.phase == DeliberationPhase.COMPLETE

    @pytest.mark.asyncio
    async def test_emits_deadlock_detected_event(self) -> None:
        """Emits DeadlockDetectedEvent with correct data."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_deadlock_escalation(
            session, vote_distribution
        )

        assert isinstance(event, DeadlockDetectedEvent)
        assert event.session_id == session.session_id
        assert event.petition_id == session.petition_id
        assert event.round_count == 3
        assert event.final_vote_distribution == vote_distribution
        assert event.reason == "DEADLOCK_MAX_ROUNDS_EXCEEDED"
        assert event.participating_archons == session.assigned_archons

    @pytest.mark.asyncio
    async def test_includes_all_vote_history(self) -> None:
        """Deadlock event includes complete vote history."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        final_vote = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.trigger_deadlock_escalation(session, final_vote)

        # Should have 3 rounds of votes (2 from history + 1 final)
        # Note: _create_test_session adds (round_count-1) to history
        assert len(event.votes_by_round) == 3


class TestGetDeadlockStatus:
    """Tests for get_deadlock_status method."""

    @pytest.mark.asyncio
    async def test_returns_status_for_registered_session(self) -> None:
        """Returns correct status for registered session."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=2)
        service.register_session(session)

        is_deadlocked, current_round, max_rounds = await service.get_deadlock_status(
            session.session_id
        )

        assert is_deadlocked is False
        assert current_round == 2
        assert max_rounds == DEFAULT_DELIBERATION_CONFIG.max_rounds

    @pytest.mark.asyncio
    async def test_reflects_deadlock_after_escalation(self) -> None:
        """Status reflects deadlock after escalation."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        service.register_session(session)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        await service.trigger_deadlock_escalation(session, vote_distribution)

        is_deadlocked, _, _ = await service.get_deadlock_status(session.session_id)
        assert is_deadlocked is True


class TestGetVoteHistory:
    """Tests for get_vote_history method."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_first_round(self) -> None:
        """Returns empty history for first round."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=1)
        service.register_session(session)

        history = await service.get_vote_history(session.session_id)

        # First round has no completed rounds yet
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_returns_history_after_rounds(self) -> None:
        """Returns vote history after multiple rounds."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        service.register_session(session)

        history = await service.get_vote_history(session.session_id)

        # Should have history from previous rounds
        assert len(history) == 2  # round_count - 1


class TestSingleRoundConfig:
    """Tests for single-round configuration (immediate deadlock)."""

    @pytest.mark.asyncio
    async def test_immediate_deadlock_on_first_split(self) -> None:
        """Single round config causes immediate deadlock on first 1-1-1."""
        config = SINGLE_ROUND_DELIBERATION_CONFIG  # max_rounds=1
        service = DeadlockHandlerService(config=config)
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=config.max_rounds
        )

        # Should immediately deadlock
        assert isinstance(event, DeadlockDetectedEvent)
        assert updated.is_deadlocked is True
        assert updated.outcome == DeliberationOutcome.ESCALATE


class TestConstitutionalCompliance:
    """Tests verifying constitutional constraint compliance."""

    @pytest.mark.asyncio
    async def test_fr_11_10_auto_escalate_after_max_rounds(self) -> None:
        """FR-11.10: Auto-ESCALATE after 3 rounds without supermajority."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        # FR-11.10 requires auto-ESCALATE
        assert updated.outcome == DeliberationOutcome.ESCALATE
        assert updated.is_deadlocked is True

    @pytest.mark.asyncio
    async def test_ct_11_deadlock_must_terminate(self) -> None:
        """CT-11: Deadlock MUST terminate (no silent failure)."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        # CT-11: Session must reach terminal state
        assert updated.phase == DeliberationPhase.COMPLETE
        assert updated.outcome is not None

    @pytest.mark.asyncio
    async def test_at_1_petition_terminates_in_one_of_three_fates(self) -> None:
        """AT-1: Every petition terminates in one of Three Fates."""
        service = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await service.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        # AT-1: Outcome must be one of Three Fates
        assert updated.outcome in (
            DeliberationOutcome.ACKNOWLEDGE,
            DeliberationOutcome.REFER,
            DeliberationOutcome.ESCALATE,
        )

    @pytest.mark.asyncio
    async def test_nfr_10_3_deterministic_behavior(self) -> None:
        """NFR-10.3: Consensus determinism - 100% reproducible."""
        service1 = DeadlockHandlerService()
        service2 = DeadlockHandlerService()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated1, event1 = await service1.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )
        updated2, event2 = await service2.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        # NFR-10.3: Same inputs produce same outcome
        assert updated1.outcome == updated2.outcome
        assert updated1.is_deadlocked == updated2.is_deadlocked
        assert type(event1) is type(event2)
