"""Unit tests for DissentRecorderStub (Story 2B.1, AC-7).

Tests the in-memory stub implementation of DissentRecorderProtocol.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import blake3
import pytest
from uuid6 import uuid7

from src.domain.models.consensus_result import ConsensusResult, ConsensusStatus
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.dissent_record import DissentRecord
from src.infrastructure.stubs.dissent_recorder_stub import (
    DissentRecorderOperation,
    DissentRecorderStub,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _compute_rationale_hash(rationale: str) -> bytes:
    """Compute Blake3 hash of rationale text."""
    return blake3.blake3(rationale.encode("utf-8")).digest()


def _create_2_1_session_and_result(
    winning_outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
    dissent_outcome: DeliberationOutcome = DeliberationOutcome.REFER,
) -> tuple[DeliberationSession, ConsensusResult]:
    """Create a test session and consensus result with 2-1 vote."""
    session_id = uuid7()
    petition_id = uuid7()
    archon_ids = (uuid4(), uuid4(), uuid4())

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
    """Create a test session and consensus result with unanimous 3-0 vote."""
    session_id = uuid7()
    petition_id = uuid7()
    archon_ids = (uuid4(), uuid4(), uuid4())

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


class TestDissentRecorderStubCreation:
    """Tests for DissentRecorderStub initialization."""

    def test_create_stub(self) -> None:
        """Should create stub with empty state."""
        stub = DissentRecorderStub()

        assert stub.get_dissent_count() == 0
        assert stub.get_operations() == []
        assert stub.get_emitted_events() == []


class TestDissentRecorderStubOperations:
    """Tests for DissentRecorderOperation enum."""

    def test_operation_enum_values(self) -> None:
        """Enum should have all required operations."""
        assert DissentRecorderOperation.RECORD_DISSENT is not None
        assert DissentRecorderOperation.GET_BY_PETITION is not None
        assert DissentRecorderOperation.GET_BY_ARCHON is not None
        assert DissentRecorderOperation.GET_BY_SESSION is not None
        assert DissentRecorderOperation.HAS_DISSENT is not None


class TestRecordDissentStub:
    """Tests for stub record_dissent method."""

    @pytest.mark.asyncio
    async def test_record_2_1_dissent(self) -> None:
        """Should record dissent for 2-1 vote."""
        session, result = _create_2_1_session_and_result()
        stub = DissentRecorderStub()

        dissent = await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test rationale.",
        )

        assert dissent is not None
        assert dissent.session_id == session.session_id
        assert dissent.petition_id == session.petition_id
        assert stub.get_dissent_count() == 1

    @pytest.mark.asyncio
    async def test_no_dissent_for_unanimous(self) -> None:
        """Should return None for unanimous vote."""
        session, result = _create_unanimous_session_and_result()
        stub = DissentRecorderStub()

        dissent = await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Unused.",
        )

        assert dissent is None
        assert stub.get_dissent_count() == 0

    @pytest.mark.asyncio
    async def test_records_operation(self) -> None:
        """Should record RECORD_DISSENT operation."""
        session, result = _create_2_1_session_and_result()
        stub = DissentRecorderStub()

        await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        operations = stub.get_operations()
        assert len(operations) == 1
        assert operations[0][0] == DissentRecorderOperation.RECORD_DISSENT
        assert operations[0][1]["session_id"] == session.session_id

    @pytest.mark.asyncio
    async def test_emits_event(self) -> None:
        """Should emit DissentRecordedEvent."""
        session, result = _create_2_1_session_and_result()
        stub = DissentRecorderStub()

        await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test rationale.",
        )

        events = stub.get_emitted_events()
        assert len(events) == 1
        assert events[0].session_id == session.session_id
        assert events[0].petition_id == session.petition_id


class TestGetDissentByPetitionStub:
    """Tests for stub get_dissent_by_petition method."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown(self) -> None:
        """Should return None for unknown petition."""
        stub = DissentRecorderStub()

        result = await stub.get_dissent_by_petition(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dissent_for_known(self) -> None:
        """Should return dissent for known petition."""
        session, result = _create_2_1_session_and_result()
        stub = DissentRecorderStub()

        await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        retrieved = await stub.get_dissent_by_petition(session.petition_id)

        assert retrieved is not None
        assert retrieved.petition_id == session.petition_id

    @pytest.mark.asyncio
    async def test_records_operation(self) -> None:
        """Should record GET_BY_PETITION operation."""
        stub = DissentRecorderStub()
        petition_id = uuid7()

        await stub.get_dissent_by_petition(petition_id)

        operations = stub.get_operations()
        assert len(operations) == 1
        assert operations[0][0] == DissentRecorderOperation.GET_BY_PETITION
        assert operations[0][1]["petition_id"] == petition_id


class TestGetDissentsByArchonStub:
    """Tests for stub get_dissents_by_archon method."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown(self) -> None:
        """Should return empty list for unknown archon."""
        stub = DissentRecorderStub()

        result = await stub.get_dissents_by_archon(uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_dissents_for_archon(self) -> None:
        """Should return dissents for known archon."""
        stub = DissentRecorderStub()
        dissent_archon_id = uuid4()

        # Create 2 dissents for this archon
        for i in range(2):
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

            await stub.record_dissent(
                session=session,
                consensus_result=consensus_result,
                dissent_rationale=f"Rationale {i}",
            )

        dissents = await stub.get_dissents_by_archon(dissent_archon_id)

        assert len(dissents) == 2

    @pytest.mark.asyncio
    async def test_records_operation(self) -> None:
        """Should record GET_BY_ARCHON operation."""
        stub = DissentRecorderStub()
        archon_id = uuid4()

        await stub.get_dissents_by_archon(archon_id, limit=10, offset=5)

        operations = stub.get_operations()
        assert len(operations) == 1
        assert operations[0][0] == DissentRecorderOperation.GET_BY_ARCHON
        assert operations[0][1]["archon_id"] == archon_id
        assert operations[0][1]["limit"] == 10
        assert operations[0][1]["offset"] == 5


class TestHasDissentStub:
    """Tests for stub has_dissent method."""

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown(self) -> None:
        """Should return False for unknown session."""
        stub = DissentRecorderStub()

        result = await stub.has_dissent(uuid7())

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_known(self) -> None:
        """Should return True for session with dissent."""
        session, result = _create_2_1_session_and_result()
        stub = DissentRecorderStub()

        await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        assert await stub.has_dissent(session.session_id) is True

    @pytest.mark.asyncio
    async def test_records_operation(self) -> None:
        """Should record HAS_DISSENT operation."""
        stub = DissentRecorderStub()
        session_id = uuid7()

        await stub.has_dissent(session_id)

        operations = stub.get_operations()
        assert len(operations) == 1
        assert operations[0][0] == DissentRecorderOperation.HAS_DISSENT
        assert operations[0][1]["session_id"] == session_id


class TestGetDissentBySessionStub:
    """Tests for stub get_dissent_by_session method."""

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown(self) -> None:
        """Should return None for unknown session."""
        stub = DissentRecorderStub()

        result = await stub.get_dissent_by_session(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dissent_for_known(self) -> None:
        """Should return dissent for known session."""
        session, result = _create_2_1_session_and_result()
        stub = DissentRecorderStub()

        await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        retrieved = await stub.get_dissent_by_session(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_records_operation(self) -> None:
        """Should record GET_BY_SESSION operation."""
        stub = DissentRecorderStub()
        session_id = uuid7()

        await stub.get_dissent_by_session(session_id)

        operations = stub.get_operations()
        assert len(operations) == 1
        assert operations[0][0] == DissentRecorderOperation.GET_BY_SESSION
        assert operations[0][1]["session_id"] == session_id


class TestStubHelperMethods:
    """Tests for stub helper methods."""

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Should clear all state."""
        session, result = _create_2_1_session_and_result()
        stub = DissentRecorderStub()

        await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Test.",
        )

        assert stub.get_dissent_count() == 1
        assert len(stub.get_operations()) == 1
        assert len(stub.get_emitted_events()) == 1

        stub.clear()

        assert stub.get_dissent_count() == 0
        assert stub.get_operations() == []
        assert stub.get_emitted_events() == []

    @pytest.mark.asyncio
    async def test_get_dissent_count(self) -> None:
        """Should return total dissent count."""
        stub = DissentRecorderStub()

        for i in range(3):
            session, result = _create_2_1_session_and_result()
            await stub.record_dissent(
                session=session,
                consensus_result=result,
                dissent_rationale=f"Rationale {i}",
            )

        assert stub.get_dissent_count() == 3

    @pytest.mark.asyncio
    async def test_get_dissent_count_by_archon(self) -> None:
        """Should return dissent count for specific archon."""
        stub = DissentRecorderStub()
        dissent_archon_id = uuid4()

        # Create 2 dissents for this archon
        for i in range(2):
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

            await stub.record_dissent(
                session=session,
                consensus_result=consensus_result,
                dissent_rationale=f"Rationale {i}",
            )

        # Add another dissent with different archon
        session, result = _create_2_1_session_and_result()
        await stub.record_dissent(
            session=session,
            consensus_result=result,
            dissent_rationale="Other archon.",
        )

        assert stub.get_dissent_count_by_archon(dissent_archon_id) == 2
        assert stub.get_dissent_count_by_archon(uuid4()) == 0  # Unknown

    def test_inject_dissent(self) -> None:
        """Should inject dissent record for testing."""
        stub = DissentRecorderStub()

        dissent = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.REFER,
            dissent_rationale="Injected rationale.",
            rationale_hash=_compute_rationale_hash("Injected rationale."),
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )

        stub.inject_dissent(dissent)

        assert stub.get_dissent_count() == 1

    @pytest.mark.asyncio
    async def test_inject_dissent_retrievable(self) -> None:
        """Injected dissent should be retrievable."""
        stub = DissentRecorderStub()

        dissent = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale="Injected rationale.",
            rationale_hash=_compute_rationale_hash("Injected rationale."),
            majority_disposition=DeliberationOutcome.REFER,
        )

        stub.inject_dissent(dissent)

        # Retrieve by petition
        by_petition = await stub.get_dissent_by_petition(dissent.petition_id)
        assert by_petition is not None
        assert by_petition.dissent_id == dissent.dissent_id

        # Retrieve by session
        by_session = await stub.get_dissent_by_session(dissent.session_id)
        assert by_session is not None
        assert by_session.dissent_id == dissent.dissent_id

        # Retrieve by archon
        by_archon = await stub.get_dissents_by_archon(dissent.dissent_archon_id)
        assert len(by_archon) == 1
        assert by_archon[0].dissent_id == dissent.dissent_id

    def test_get_emitted_events_returns_copy(self) -> None:
        """get_emitted_events should return a copy."""
        stub = DissentRecorderStub()

        events1 = stub.get_emitted_events()
        events2 = stub.get_emitted_events()

        assert events1 is not events2

    def test_get_operations_returns_copy(self) -> None:
        """get_operations should return a copy."""
        stub = DissentRecorderStub()

        ops1 = stub.get_operations()
        ops2 = stub.get_operations()

        assert ops1 is not ops2
