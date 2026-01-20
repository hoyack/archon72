"""Unit tests for DissentRecorderService (Story 2B.1, FR-11.8).

Tests the dissent recording service implementation.

Constitutional Constraints:
- FR-11.8: System SHALL record dissent opinions in 2-1 votes
- CT-12: Witnessing creates accountability
- AT-6: Deliberation is collective judgment
- NFR-6.5: Audit trail completeness
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from uuid6 import uuid7

from src.application.services.dissent_recorder_service import (
    DISSENT_RECORDER_SYSTEM_AGENT_ID,
    DissentRecorderService,
)
from src.domain.models.consensus_result import ConsensusResult, ConsensusStatus
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _create_2_1_session_and_result(
    winning_outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
    dissent_outcome: DeliberationOutcome = DeliberationOutcome.REFER,
) -> tuple[DeliberationSession, ConsensusResult]:
    """Create a test session and consensus result with 2-1 vote.

    Args:
        winning_outcome: The majority outcome (2 votes).
        dissent_outcome: The minority outcome (1 vote).

    Returns:
        Tuple of (session, consensus_result).
    """
    session_id = uuid7()
    petition_id = uuid7()
    archon_ids = (uuid4(), uuid4(), uuid4())

    # Create votes: 2 for winning, 1 for dissent
    votes = {
        archon_ids[0]: winning_outcome,
        archon_ids[1]: winning_outcome,
        archon_ids[2]: dissent_outcome,
    }

    session = DeliberationSession(
        session_id=session_id,
        petition_id=petition_id,
        assigned_archons=archon_ids,
        phase=DeliberationPhase.COMPLETE,
        votes=votes,
        outcome=winning_outcome,
        dissent_archon_id=archon_ids[2],
        completed_at=_utc_now(),
    )

    consensus_result = ConsensusResult(
        session_id=session_id,
        petition_id=petition_id,
        status=ConsensusStatus.ACHIEVED,
        winning_outcome=winning_outcome.value,
        vote_distribution={winning_outcome.value: 2, dissent_outcome.value: 1},
        majority_archon_ids=(archon_ids[0], archon_ids[1]),
        dissent_archon_id=archon_ids[2],
    )

    return session, consensus_result


def _create_unanimous_session_and_result(
    outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
) -> tuple[DeliberationSession, ConsensusResult]:
    """Create a test session and consensus result with unanimous 3-0 vote.

    Args:
        outcome: The unanimous outcome.

    Returns:
        Tuple of (session, consensus_result).
    """
    session_id = uuid7()
    petition_id = uuid7()
    archon_ids = (uuid4(), uuid4(), uuid4())

    # All 3 vote the same
    votes = {
        archon_ids[0]: outcome,
        archon_ids[1]: outcome,
        archon_ids[2]: outcome,
    }

    session = DeliberationSession(
        session_id=session_id,
        petition_id=petition_id,
        assigned_archons=archon_ids,
        phase=DeliberationPhase.COMPLETE,
        votes=votes,
        outcome=outcome,
        dissent_archon_id=None,
        completed_at=_utc_now(),
    )

    consensus_result = ConsensusResult(
        session_id=session_id,
        petition_id=petition_id,
        status=ConsensusStatus.UNANIMOUS,
        winning_outcome=outcome.value,
        vote_distribution={outcome.value: 3},
        majority_archon_ids=archon_ids,
        dissent_archon_id=None,
    )

    return session, consensus_result


class TestDissentRecorderServiceCreation:
    """Tests for DissentRecorderService initialization."""

    def test_create_without_event_emitter(self) -> None:
        """Should create service without event emitter."""
        service = DissentRecorderService()

        assert service._event_emitter is None
        assert service.get_total_dissent_count() == 0

    def test_system_agent_id_constant(self) -> None:
        """System agent ID constant should be correct."""
        assert DISSENT_RECORDER_SYSTEM_AGENT_ID == "system:dissent-recorder"


class TestRecordDissent:
    """Tests for record_dissent method (FR-11.8)."""

    @pytest.mark.asyncio
    async def test_record_2_1_dissent_acknowledge_vs_refer(self) -> None:
        """Should record dissent for 2-1 ACKNOWLEDGE vs REFER vote."""
        session, result = _create_2_1_session_and_result(
            winning_outcome=DeliberationOutcome.ACKNOWLEDGE,
            dissent_outcome=DeliberationOutcome.REFER,
        )
        service = DissentRecorderService()

        dissent = await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="I believe this petition requires Knight review.",
        )

        assert dissent is not None
        assert dissent.session_id == session.session_id
        assert dissent.petition_id == session.petition_id
        assert dissent.dissent_archon_id == result.dissent_archon_id
        assert dissent.dissent_disposition == DeliberationOutcome.REFER
        assert dissent.majority_disposition == DeliberationOutcome.ACKNOWLEDGE
        assert len(dissent.rationale_hash) == 32  # Blake3
        assert (
            dissent.dissent_rationale
            == "I believe this petition requires Knight review."
        )

    @pytest.mark.asyncio
    async def test_record_2_1_dissent_refer_vs_escalate(self) -> None:
        """Should record dissent for 2-1 REFER vs ESCALATE vote."""
        session, result = _create_2_1_session_and_result(
            winning_outcome=DeliberationOutcome.REFER,
            dissent_outcome=DeliberationOutcome.ESCALATE,
        )
        service = DissentRecorderService()

        dissent = await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="This petition warrants King consideration.",
        )

        assert dissent is not None
        assert dissent.dissent_disposition == DeliberationOutcome.ESCALATE
        assert dissent.majority_disposition == DeliberationOutcome.REFER

    @pytest.mark.asyncio
    async def test_no_dissent_for_unanimous(self) -> None:
        """Should return None for unanimous 3-0 vote (no dissent)."""
        session, result = _create_unanimous_session_and_result()
        service = DissentRecorderService()

        dissent = await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Should not be used.",
        )

        assert dissent is None
        assert service.get_total_dissent_count() == 0

    @pytest.mark.asyncio
    async def test_dissent_stored_by_petition(self) -> None:
        """Dissent should be retrievable by petition ID."""
        session, result = _create_2_1_session_and_result()
        service = DissentRecorderService()

        await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test rationale.",
        )

        retrieved = await service.get_dissent_by_petition(session.petition_id)
        assert retrieved is not None
        assert retrieved.petition_id == session.petition_id

    @pytest.mark.asyncio
    async def test_dissent_stored_by_session(self) -> None:
        """Dissent should be retrievable by session ID."""
        session, result = _create_2_1_session_and_result()
        service = DissentRecorderService()

        await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test rationale.",
        )

        retrieved = await service.get_dissent_by_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_dissent_stored_by_archon(self) -> None:
        """Dissent should be retrievable by archon ID."""
        session, result = _create_2_1_session_and_result()
        service = DissentRecorderService()

        await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test rationale.",
        )

        archon_id = result.dissent_archon_id
        assert archon_id is not None

        retrieved = await service.get_dissents_by_archon(archon_id)
        assert len(retrieved) == 1
        assert retrieved[0].dissent_archon_id == archon_id


class TestGetDissentByPetition:
    """Tests for get_dissent_by_petition method (AC-5)."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_petition(self) -> None:
        """Should return None for petition without recorded dissent."""
        service = DissentRecorderService()

        result = await service.get_dissent_by_petition(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dissent_for_known_petition(self) -> None:
        """Should return dissent for petition with recorded dissent."""
        session, result = _create_2_1_session_and_result()
        service = DissentRecorderService()

        await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        retrieved = await service.get_dissent_by_petition(session.petition_id)

        assert retrieved is not None
        assert retrieved.petition_id == session.petition_id


class TestGetDissentsByArchon:
    """Tests for get_dissents_by_archon method (AC-6)."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_archon(self) -> None:
        """Should return empty list for archon without recorded dissents."""
        service = DissentRecorderService()

        result = await service.get_dissents_by_archon(uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_multiple_dissents_for_archon(self) -> None:
        """Should return all dissents for an archon with multiple dissents."""
        service = DissentRecorderService()

        # Create a dissenting archon
        dissent_archon_id = uuid4()

        # Create multiple sessions with this archon dissenting
        for i in range(3):
            session_id = uuid7()
            petition_id = uuid7()
            archon_ids = (uuid4(), uuid4(), dissent_archon_id)

            votes = {
                archon_ids[0]: DeliberationOutcome.ACKNOWLEDGE,
                archon_ids[1]: DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id: DeliberationOutcome.REFER,
            }

            session = DeliberationSession(
                session_id=session_id,
                petition_id=petition_id,
                assigned_archons=archon_ids,
                phase=DeliberationPhase.COMPLETE,
                votes=votes,
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id=dissent_archon_id,
            )

            consensus_result = ConsensusResult(
                session_id=session_id,
                petition_id=petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="ACKNOWLEDGE",
                vote_distribution={"ACKNOWLEDGE": 2, "REFER": 1},
                majority_archon_ids=(archon_ids[0], archon_ids[1]),
                dissent_archon_id=dissent_archon_id,
            )

            await service.record_dissent(
                session=session,
                consensus_result=consensus_result,
                dissent_rationale=f"Rationale {i}",
            )

        dissents = await service.get_dissents_by_archon(dissent_archon_id)

        assert len(dissents) == 3

    @pytest.mark.asyncio
    async def test_pagination_limit(self) -> None:
        """Should respect limit parameter in get_dissents_by_archon."""
        service = DissentRecorderService()
        dissent_archon_id = uuid4()

        # Create 5 dissents
        for i in range(5):
            session_id = uuid7()
            petition_id = uuid7()
            archon_ids = (uuid4(), uuid4(), dissent_archon_id)

            votes = {
                archon_ids[0]: DeliberationOutcome.ACKNOWLEDGE,
                archon_ids[1]: DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id: DeliberationOutcome.REFER,
            }

            session = DeliberationSession(
                session_id=session_id,
                petition_id=petition_id,
                assigned_archons=archon_ids,
                phase=DeliberationPhase.COMPLETE,
                votes=votes,
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id=dissent_archon_id,
            )

            consensus_result = ConsensusResult(
                session_id=session_id,
                petition_id=petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="ACKNOWLEDGE",
                vote_distribution={"ACKNOWLEDGE": 2, "REFER": 1},
                majority_archon_ids=(archon_ids[0], archon_ids[1]),
                dissent_archon_id=dissent_archon_id,
            )

            await service.record_dissent(
                session=session,
                consensus_result=consensus_result,
                dissent_rationale=f"Rationale {i}",
            )

        # Request with limit
        dissents = await service.get_dissents_by_archon(dissent_archon_id, limit=2)

        assert len(dissents) == 2

    @pytest.mark.asyncio
    async def test_pagination_offset(self) -> None:
        """Should respect offset parameter in get_dissents_by_archon."""
        service = DissentRecorderService()
        dissent_archon_id = uuid4()

        # Create 5 dissents
        for i in range(5):
            session_id = uuid7()
            petition_id = uuid7()
            archon_ids = (uuid4(), uuid4(), dissent_archon_id)

            votes = {
                archon_ids[0]: DeliberationOutcome.ACKNOWLEDGE,
                archon_ids[1]: DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id: DeliberationOutcome.REFER,
            }

            session = DeliberationSession(
                session_id=session_id,
                petition_id=petition_id,
                assigned_archons=archon_ids,
                phase=DeliberationPhase.COMPLETE,
                votes=votes,
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id=dissent_archon_id,
            )

            consensus_result = ConsensusResult(
                session_id=session_id,
                petition_id=petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="ACKNOWLEDGE",
                vote_distribution={"ACKNOWLEDGE": 2, "REFER": 1},
                majority_archon_ids=(archon_ids[0], archon_ids[1]),
                dissent_archon_id=dissent_archon_id,
            )

            await service.record_dissent(
                session=session,
                consensus_result=consensus_result,
                dissent_rationale=f"Rationale {i}",
            )

        # Request with offset
        dissents = await service.get_dissents_by_archon(
            dissent_archon_id, limit=10, offset=3
        )

        assert len(dissents) == 2  # 5 total - 3 skipped = 2


class TestHasDissent:
    """Tests for has_dissent method."""

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_session(self) -> None:
        """Should return False for session without recorded dissent."""
        service = DissentRecorderService()

        result = await service.has_dissent(uuid7())

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_session_with_dissent(self) -> None:
        """Should return True for session with recorded dissent."""
        session, result = _create_2_1_session_and_result()
        service = DissentRecorderService()

        await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        assert await service.has_dissent(session.session_id) is True


class TestGetDissentBySession:
    """Tests for get_dissent_by_session method."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_session(self) -> None:
        """Should return None for session without recorded dissent."""
        service = DissentRecorderService()

        result = await service.get_dissent_by_session(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dissent_for_known_session(self) -> None:
        """Should return dissent for session with recorded dissent."""
        session, result = _create_2_1_session_and_result()
        service = DissentRecorderService()

        await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        retrieved = await service.get_dissent_by_session(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id


class TestDissentCounts:
    """Tests for dissent count methods."""

    @pytest.mark.asyncio
    async def test_get_dissent_count_by_archon(self) -> None:
        """Should count dissents by archon."""
        service = DissentRecorderService()
        dissent_archon_id = uuid4()

        # Create 3 dissents for this archon
        for i in range(3):
            session_id = uuid7()
            petition_id = uuid7()
            archon_ids = (uuid4(), uuid4(), dissent_archon_id)

            votes = {
                archon_ids[0]: DeliberationOutcome.ACKNOWLEDGE,
                archon_ids[1]: DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id: DeliberationOutcome.REFER,
            }

            session = DeliberationSession(
                session_id=session_id,
                petition_id=petition_id,
                assigned_archons=archon_ids,
                phase=DeliberationPhase.COMPLETE,
                votes=votes,
                outcome=DeliberationOutcome.ACKNOWLEDGE,
                dissent_archon_id=dissent_archon_id,
            )

            consensus_result = ConsensusResult(
                session_id=session_id,
                petition_id=petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="ACKNOWLEDGE",
                vote_distribution={"ACKNOWLEDGE": 2, "REFER": 1},
                majority_archon_ids=(archon_ids[0], archon_ids[1]),
                dissent_archon_id=dissent_archon_id,
            )

            await service.record_dissent(
                session=session,
                consensus_result=consensus_result,
                dissent_rationale=f"Rationale {i}",
            )

        assert service.get_dissent_count_by_archon(dissent_archon_id) == 3
        assert service.get_dissent_count_by_archon(uuid4()) == 0  # Unknown archon

    def test_get_total_dissent_count_empty(self) -> None:
        """Should return 0 when no dissents recorded."""
        service = DissentRecorderService()

        assert service.get_total_dissent_count() == 0

    @pytest.mark.asyncio
    async def test_get_total_dissent_count(self) -> None:
        """Should count total dissents."""
        service = DissentRecorderService()

        # Create 2 dissents with different archons
        for i in range(2):
            session, result = _create_2_1_session_and_result()
            await service.record_dissent(
                session=session,
                consensus_result=result,
                dissent_rationale=f"Rationale {i}",
            )

        assert service.get_total_dissent_count() == 2


class TestBlake3Hashing:
    """Tests for Blake3 rationale hashing."""

    @pytest.mark.asyncio
    async def test_rationale_hash_is_32_bytes(self) -> None:
        """Rationale hash should always be 32 bytes (Blake3)."""
        session, result = _create_2_1_session_and_result()
        service = DissentRecorderService()

        dissent = await service.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test rationale for hashing.",
        )

        assert dissent is not None
        assert len(dissent.rationale_hash) == 32

    @pytest.mark.asyncio
    async def test_different_rationales_different_hashes(self) -> None:
        """Different rationale texts should produce different hashes."""
        service = DissentRecorderService()

        # First dissent
        session1, result1 = _create_2_1_session_and_result()
        dissent1 = await service.record_dissent(
            session=session1,
            consensus_result=result1,
            dissent_rationale="First rationale text.",
        )

        # Second dissent with different rationale
        session2, result2 = _create_2_1_session_and_result()
        dissent2 = await service.record_dissent(
            session=session2,
            consensus_result=result2,
            dissent_rationale="Second different rationale text.",
        )

        assert dissent1 is not None
        assert dissent2 is not None
        assert dissent1.rationale_hash != dissent2.rationale_hash

    @pytest.mark.asyncio
    async def test_same_rationale_same_hash(self) -> None:
        """Same rationale text should produce same hash (deterministic)."""
        service = DissentRecorderService()
        rationale = "Identical rationale for deterministic hashing."

        # First dissent
        session1, result1 = _create_2_1_session_and_result()
        dissent1 = await service.record_dissent(
            session=session1,
            consensus_result=result1,
            dissent_rationale=rationale,
        )

        # Second dissent with same rationale
        session2, result2 = _create_2_1_session_and_result()
        dissent2 = await service.record_dissent(
            session=session2,
            consensus_result=result2,
            dissent_rationale=rationale,
        )

        assert dissent1 is not None
        assert dissent2 is not None
        assert dissent1.rationale_hash == dissent2.rationale_hash
