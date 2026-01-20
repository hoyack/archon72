"""Unit tests for deadlock handler stub (Story 2B.3, AC-6).

Tests the DeadlockHandlerStub in-memory implementation for correct
deadlock detection and handling behavior.

Constitutional Constraints:
- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- AT-1: Every petition terminates in exactly one of Three Fates
"""

from __future__ import annotations

from uuid import uuid4

import pytest

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
from src.infrastructure.stubs.deadlock_handler_stub import (
    DeadlockHandlerStub,
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
        for _ in range(round_count - 1):
            vote_dist = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}
            session = session.with_new_round(vote_dist)
            session = session.with_phase(DeliberationPhase.VOTE)

    return session


class TestDeadlockHandlerStubBasics:
    """Basic tests for DeadlockHandlerStub."""

    def test_stub_initializes_with_defaults(self) -> None:
        """Stub initializes with default configuration."""
        stub = DeadlockHandlerStub()

        assert stub.max_rounds == DEFAULT_DELIBERATION_CONFIG.max_rounds

    def test_stub_accepts_custom_config(self) -> None:
        """Stub accepts custom configuration."""
        config = DeliberationConfig(timeout_seconds=300, max_rounds=5)
        stub = DeadlockHandlerStub(config=config)

        assert stub.max_rounds == 5

    def test_stub_can_register_session(self) -> None:
        """Stub can register sessions for tracking."""
        stub = DeadlockHandlerStub()
        session = _create_test_session()

        stub.register_session(session)

        assert stub.get_session(session.session_id) == session

    def test_stub_clear_resets_state(self) -> None:
        """Stub clear method resets all state."""
        stub = DeadlockHandlerStub()
        session = _create_test_session()
        stub.register_session(session)

        stub.clear()

        assert stub.get_session(session.session_id) is None
        assert len(stub.get_deadlocks()) == 0
        assert len(stub.get_new_rounds()) == 0
        assert len(stub.get_emitted_events()) == 0


class TestStubIsDeadlockVotePattern:
    """Tests for stub is_deadlock_vote_pattern."""

    def test_1_1_1_is_deadlock(self) -> None:
        """1-1-1 split is deadlock pattern."""
        stub = DeadlockHandlerStub()

        assert stub.is_deadlock_vote_pattern({"A": 1, "B": 1, "C": 1}) is True

    def test_2_1_is_not_deadlock(self) -> None:
        """2-1 split is not deadlock pattern."""
        stub = DeadlockHandlerStub()

        assert stub.is_deadlock_vote_pattern({"A": 2, "B": 1}) is False

    def test_3_0_is_not_deadlock(self) -> None:
        """3-0 unanimous is not deadlock pattern."""
        stub = DeadlockHandlerStub()

        assert stub.is_deadlock_vote_pattern({"A": 3}) is False


class TestStubHandleNoConsensus:
    """Tests for stub handle_no_consensus."""

    @pytest.mark.asyncio
    async def test_triggers_new_round_when_under_max(self) -> None:
        """Triggers new round when under max rounds."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await stub.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        assert isinstance(event, CrossExamineRoundTriggeredEvent)
        assert updated.round_count == 2
        assert updated.phase == DeliberationPhase.CROSS_EXAMINE

    @pytest.mark.asyncio
    async def test_triggers_deadlock_when_at_max(self) -> None:
        """Triggers deadlock when at max rounds."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await stub.handle_no_consensus(
            session, vote_distribution, max_rounds=3
        )

        assert isinstance(event, DeadlockDetectedEvent)
        assert updated.is_deadlocked is True
        assert updated.outcome == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_rejects_non_deadlock_pattern(self) -> None:
        """Rejects non-deadlock vote patterns."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 2, "REFER": 1}

        with pytest.raises(ValueError, match="not a deadlock pattern"):
            await stub.handle_no_consensus(session, vote_distribution, max_rounds=3)

    @pytest.mark.asyncio
    async def test_rejects_completed_session(self) -> None:
        """Rejects already completed sessions."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=1)
        # Complete the session
        session = session.with_votes(
            {
                session.assigned_archons[0]: DeliberationOutcome.ACKNOWLEDGE,
                session.assigned_archons[1]: DeliberationOutcome.ACKNOWLEDGE,
                session.assigned_archons[2]: DeliberationOutcome.REFER,
            }
        )
        session = session.with_outcome()
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        with pytest.raises(SessionAlreadyCompleteError):
            await stub.handle_no_consensus(session, vote_distribution, max_rounds=3)


class TestStubTracking:
    """Tests for stub tracking features."""

    @pytest.mark.asyncio
    async def test_tracks_new_rounds(self) -> None:
        """Stub tracks new rounds triggered."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        await stub.handle_no_consensus(session, vote_distribution, max_rounds=3)

        rounds = stub.get_new_rounds()
        assert len(rounds) == 1
        assert rounds[0] == (session.session_id, 2)

    @pytest.mark.asyncio
    async def test_tracks_deadlocks(self) -> None:
        """Stub tracks deadlocks detected."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=3)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        await stub.handle_no_consensus(session, vote_distribution, max_rounds=3)

        deadlocks = stub.get_deadlocks()
        assert session.session_id in deadlocks

    @pytest.mark.asyncio
    async def test_tracks_emitted_events(self) -> None:
        """Stub tracks all emitted events."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        await stub.handle_no_consensus(session, vote_distribution, max_rounds=3)

        events = stub.get_emitted_events()
        assert len(events) == 1
        assert isinstance(events[0], CrossExamineRoundTriggeredEvent)


class TestStubStatusMethods:
    """Tests for stub status query methods."""

    @pytest.mark.asyncio
    async def test_get_deadlock_status(self) -> None:
        """Stub returns correct deadlock status."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=2)
        stub.register_session(session)

        is_deadlocked, current_round, max_rounds = await stub.get_deadlock_status(
            session.session_id
        )

        assert is_deadlocked is False
        assert current_round == 2
        assert max_rounds == 3

    @pytest.mark.asyncio
    async def test_get_vote_history(self) -> None:
        """Stub returns correct vote history."""
        stub = DeadlockHandlerStub()
        session = _create_test_session(round_count=3)
        stub.register_session(session)

        history = await stub.get_vote_history(session.session_id)

        # round_count=3 means 2 previous rounds in history
        assert len(history) == 2


class TestStubSingleRoundConfig:
    """Tests for stub with single-round configuration."""

    @pytest.mark.asyncio
    async def test_immediate_deadlock_on_first_split(self) -> None:
        """Single round config causes immediate deadlock."""
        config = SINGLE_ROUND_DELIBERATION_CONFIG
        stub = DeadlockHandlerStub(config=config)
        session = _create_test_session(round_count=1)
        vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

        updated, event = await stub.handle_no_consensus(
            session, vote_distribution, max_rounds=config.max_rounds
        )

        assert isinstance(event, DeadlockDetectedEvent)
        assert updated.is_deadlocked is True
