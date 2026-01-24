"""Unit tests for King Acknowledgment (Story 6.5).

Story: 6.5 - Escalation Acknowledgment by King
FR-5.8: King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.errors.acknowledgment import (
    AcknowledgmentAlreadyExistsError,
    PetitionNotFoundError,
)
from src.domain.errors.petition import (
    PetitionNotEscalatedError,
    RealmMismatchError,
)
from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.acknowledgment_execution_stub import (
    AcknowledgmentExecutionStub,
)


@pytest.fixture
def stub() -> AcknowledgmentExecutionStub:
    """Create a fresh stub for each test."""
    return AcknowledgmentExecutionStub()


@pytest.fixture
def king_id() -> UUID:
    """King UUID for tests."""
    return uuid4()


@pytest.fixture
def escalated_petition() -> PetitionSubmission:
    """Create a petition in ESCALATED state."""
    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="Test escalated petition requiring King decision",
        submitter_id=uuid4(),
        content_hash=b"a" * 32,
        realm="governance",
        state=PetitionState.ESCALATED,
        escalated_to_realm="governance",
        escalated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def deliberating_petition() -> PetitionSubmission:
    """Create a petition in DELIBERATING state (not escalated)."""
    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test deliberating petition",
        submitter_id=uuid4(),
        content_hash=b"b" * 32,
        realm="governance",
        state=PetitionState.DELIBERATING,
    )


@pytest.fixture
def valid_rationale() -> str:
    """Valid King rationale (>= 100 chars)."""
    return (
        "I have carefully reviewed this petition and the concerns raised by "
        "the co-signers. While I appreciate their dedication to system governance, "
        "the specific concerns have been addressed in recent policy updates."
    )


class TestKingAcknowledgeHappyPath:
    """Tests for successful King acknowledgment execution."""

    @pytest.mark.asyncio
    async def test_king_acknowledge_noted_success(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Successfully acknowledge escalated petition with NOTED reason (Story 6.5 AC1)."""
        stub.add_petition(escalated_petition)

        _ = await stub.execute_king_acknowledge(
            petition_id=escalated_petition.id,
            king_id=king_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            rationale=valid_rationale,
            realm_id="governance",
        )

        assert ack.petition_id == escalated_petition.id
        assert ack.acknowledged_by_king_id == king_id
        assert ack.reason_code == AcknowledgmentReasonCode.NOTED
        assert ack.rationale == valid_rationale
        assert len(ack.acknowledging_archon_ids) == 0  # Empty for King acknowledgments
        assert stub.was_executed(escalated_petition.id)

    @pytest.mark.asyncio
    async def test_king_acknowledge_out_of_scope_success(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Successfully acknowledge with OUT_OF_SCOPE reason (Story 6.5 AC1)."""
        stub.add_petition(escalated_petition)

        _ = await stub.execute_king_acknowledge(
            petition_id=escalated_petition.id,
            king_id=king_id,
            reason_code=AcknowledgmentReasonCode.OUT_OF_SCOPE,
            rationale=valid_rationale,
            realm_id="governance",
        )

        assert ack.reason_code == AcknowledgmentReasonCode.OUT_OF_SCOPE
        assert ack.acknowledged_by_king_id == king_id

    @pytest.mark.asyncio
    async def test_king_id_recorded_separately(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """King ID is recorded in acknowledged_by_king_id, not archon IDs (Story 6.5 AC6)."""
        stub.add_petition(escalated_petition)

        _ = await stub.execute_king_acknowledge(
            petition_id=escalated_petition.id,
            king_id=king_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            rationale=valid_rationale,
            realm_id="governance",
        )

        assert ack.acknowledged_by_king_id == king_id
        assert ack.acknowledging_archon_ids == ()
        # Verify these are mutually exclusive
        assert (ack.acknowledged_by_king_id is not None) != (
            len(ack.acknowledging_archon_ids) > 0
        )


class TestRationaleValidation:
    """Tests for rationale length validation (Story 6.5 AC2)."""

    @pytest.mark.asyncio
    async def test_rationale_too_short_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
    ) -> None:
        """Rationale < 100 chars fails validation (Story 6.5 AC2)."""
        stub.add_petition(escalated_petition)

        short_rationale = "Too short"  # < 100 chars
        with pytest.raises(ValueError, match="rationale >= 100 chars"):
            await stub.execute_king_acknowledge(
                petition_id=escalated_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale=short_rationale,
                realm_id="governance",
            )

    @pytest.mark.asyncio
    async def test_rationale_exactly_100_chars_succeeds(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
    ) -> None:
        """Rationale with exactly 100 chars succeeds (Story 6.5 AC2)."""
        stub.add_petition(escalated_petition)

        # Exactly 100 characters
        rationale_100 = "X" * 100
        _ = await stub.execute_king_acknowledge(
            petition_id=escalated_petition.id,
            king_id=king_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            rationale=rationale_100,
            realm_id="governance",
        )

        assert ack.rationale == rationale_100
        assert len(ack.rationale) == 100

    @pytest.mark.asyncio
    async def test_empty_rationale_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
    ) -> None:
        """Empty rationale fails validation (Story 6.5 AC2)."""
        stub.add_petition(escalated_petition)

        with pytest.raises(ValueError, match="rationale >= 100 chars"):
            await stub.execute_king_acknowledge(
                petition_id=escalated_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale="",
                realm_id="governance",
            )

    @pytest.mark.asyncio
    async def test_whitespace_only_rationale_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
    ) -> None:
        """Whitespace-only rationale fails validation (Story 6.5 AC2)."""
        stub.add_petition(escalated_petition)

        whitespace_rationale = " " * 120  # 120 spaces
        with pytest.raises(ValueError, match="rationale >= 100 chars"):
            await stub.execute_king_acknowledge(
                petition_id=escalated_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale=whitespace_rationale,
                realm_id="governance",
            )


class TestPetitionMustBeEscalated:
    """Tests for petition state validation (Story 6.5 AC3)."""

    @pytest.mark.asyncio
    async def test_deliberating_petition_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        deliberating_petition: PetitionSubmission,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Cannot acknowledge DELIBERATING petition (Story 6.5 AC3)."""
        stub.add_petition(deliberating_petition)

        with pytest.raises(PetitionNotEscalatedError) as exc_info:
            await stub.execute_king_acknowledge(
                petition_id=deliberating_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale=valid_rationale,
                realm_id="governance",
            )

        assert exc_info.value.petition_id == deliberating_petition.id
        assert exc_info.value.current_state == PetitionState.DELIBERATING.value

    @pytest.mark.asyncio
    async def test_received_petition_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Cannot acknowledge RECEIVED petition (Story 6.5 AC3)."""
        received_petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test received petition",
            submitter_id=uuid4(),
            content_hash=b"c" * 32,
            realm="governance",
            state=PetitionState.RECEIVED,
        )
        stub.add_petition(received_petition)

        with pytest.raises(PetitionNotEscalatedError):
            await stub.execute_king_acknowledge(
                petition_id=received_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale=valid_rationale,
                realm_id="governance",
            )

    @pytest.mark.asyncio
    async def test_acknowledged_petition_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Cannot acknowledge ACKNOWLEDGED petition (Story 6.5 AC3)."""
        acknowledged_petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test acknowledged petition",
            submitter_id=uuid4(),
            content_hash=b"d" * 32,
            realm="governance",
            state=PetitionState.ACKNOWLEDGED,
        )
        stub.add_petition(acknowledged_petition)

        with pytest.raises(PetitionNotEscalatedError):
            await stub.execute_king_acknowledge(
                petition_id=acknowledged_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale=valid_rationale,
                realm_id="governance",
            )


class TestRealmAuthorization:
    """Tests for realm authorization (Story 6.5 AC4, RULING-3)."""

    @pytest.mark.asyncio
    async def test_realm_mismatch_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Cannot acknowledge petition from different realm (Story 6.5 AC4)."""
        # Petition is escalated to "governance", King is from "knowledge"
        stub.add_petition(escalated_petition)

        with pytest.raises(RealmMismatchError) as exc_info:
            await stub.execute_king_acknowledge(
                petition_id=escalated_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale=valid_rationale,
                realm_id="knowledge",  # Different realm
            )

        assert "governance" in str(exc_info.value).lower()
        assert "knowledge" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_matching_realm_succeeds(
        self,
        stub: AcknowledgmentExecutionStub,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """King can acknowledge petition from matching realm (Story 6.5 AC4)."""
        # Create petition escalated to "security" realm
        security_petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.CESSATION,
            text="Test security petition",
            submitter_id=uuid4(),
            content_hash=b"e" * 32,
            realm="security",
            state=PetitionState.ESCALATED,
            escalated_to_realm="security",
            escalated_at=datetime.now(timezone.utc),
        )
        stub.add_petition(security_petition)

        # King from "security" realm can acknowledge
        _ = await stub.execute_king_acknowledge(
            petition_id=security_petition.id,
            king_id=king_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            rationale=valid_rationale,
            realm_id="security",  # Matching realm
        )

        assert ack.petition_id == security_petition.id


class TestPetitionNotFound:
    """Tests for petition not found error (Story 6.5)."""

    @pytest.mark.asyncio
    async def test_nonexistent_petition_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Cannot acknowledge nonexistent petition."""
        nonexistent_id = uuid4()

        with pytest.raises(PetitionNotFoundError) as exc_info:
            await stub.execute_king_acknowledge(
                petition_id=nonexistent_id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                rationale=valid_rationale,
                realm_id="governance",
            )

        assert exc_info.value.petition_id == nonexistent_id


class TestIdempotency:
    """Tests for acknowledgment idempotency."""

    @pytest.mark.asyncio
    async def test_duplicate_acknowledgment_fails(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """Cannot acknowledge same petition twice (idempotency)."""
        stub.add_petition(escalated_petition)

        # First acknowledgment succeeds
        ack1 = await stub.execute_king_acknowledge(
            petition_id=escalated_petition.id,
            king_id=king_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            rationale=valid_rationale,
            realm_id="governance",
        )

        # Second acknowledgment fails
        with pytest.raises(AcknowledgmentAlreadyExistsError) as exc_info:
            await stub.execute_king_acknowledge(
                petition_id=escalated_petition.id,
                king_id=king_id,
                reason_code=AcknowledgmentReasonCode.OUT_OF_SCOPE,
                rationale=valid_rationale,
                realm_id="governance",
            )

        assert exc_info.value.petition_id == escalated_petition.id
        assert exc_info.value.existing_acknowledgment_id == ack1.id


class TestEventEmission:
    """Tests for event emission (Story 6.5 AC7)."""

    @pytest.mark.asyncio
    async def test_king_acknowledged_escalation_event_emitted(
        self,
        stub: AcknowledgmentExecutionStub,
        escalated_petition: PetitionSubmission,
        king_id: UUID,
        valid_rationale: str,
    ) -> None:
        """KingAcknowledgedEscalation event is emitted (Story 6.5 AC7)."""
        stub.add_petition(escalated_petition)

        _ = await stub.execute_king_acknowledge(
            petition_id=escalated_petition.id,
            king_id=king_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            rationale=valid_rationale,
            realm_id="governance",
        )

        # Verify event was emitted (stub tracks this)
        events = stub.get_emitted_events()
        assert len(events) > 0

        # Find the KingAcknowledgedEscalation event
        king_ack_events = [
            e
            for e in events
            if e.get("event_type") == "petition.escalation.acknowledged_by_king"
        ]
        assert len(king_ack_events) == 1

        event = king_ack_events[0]
        assert event["petition_id"] == escalated_petition.id
        assert event["king_id"] == king_id
        assert event["reason_code"] == AcknowledgmentReasonCode.NOTED.value
        assert event["realm_id"] == "governance"
