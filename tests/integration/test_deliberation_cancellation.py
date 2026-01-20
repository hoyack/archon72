"""Integration tests for deliberation cancellation (Story 5.6, AC4).

Tests that deliberation is cancelled gracefully when auto-escalation occurs
due to co-signer thresholds being reached.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- CT-12: All outputs through witnessing pipeline
- CT-14: Silence must be expensive - auto-escalation ensures King attention
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.auto_escalation_executor_service import (
    AutoEscalationExecutorService,
)
from src.domain.events.deliberation_cancelled import (
    CancelReason,
    DeliberationCancelledEvent,
)
from src.domain.models.petition_submission import PetitionState, PetitionType


class FakePetition:
    """Fake petition for testing."""

    def __init__(
        self,
        petition_id: UUID,
        state: PetitionState = PetitionState.DELIBERATING,
        petition_type: PetitionType = PetitionType.CESSATION,
        realm: str = "default",
    ) -> None:
        """Initialize fake petition."""
        self.id = petition_id
        self.state = state
        self.type = petition_type
        self.realm = realm


@pytest.fixture
def petition_id() -> UUID:
    """Return a test petition ID."""
    return uuid4()


@pytest.fixture
def signer_id() -> UUID:
    """Return a test signer ID."""
    return uuid4()


@pytest.fixture
def mock_halt_checker() -> MagicMock:
    """Return a mock halt checker that is not halted."""
    checker = MagicMock()
    checker.is_halted = AsyncMock(return_value=False)
    return checker


class TestDeliberationCancellationOnEscalation:
    """Test deliberation cancellation when auto-escalation occurs (AC4)."""

    @pytest.mark.asyncio
    async def test_escalation_from_deliberating_state_succeeds(
        self,
        petition_id: UUID,
        signer_id: UUID,
        mock_halt_checker: MagicMock,
    ) -> None:
        """Petition in DELIBERATING state can be escalated (AC4)."""
        # Setup: Petition in DELIBERATING state
        petition = FakePetition(petition_id, PetitionState.DELIBERATING)

        mock_petition_repo = MagicMock()
        mock_petition_repo.get = AsyncMock(return_value=petition)
        mock_petition_repo.assign_fate_cas = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        # Act: Execute auto-escalation
        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_by=signer_id,
        )

        # Assert: Escalation successful
        assert result.triggered is True
        assert result.escalation_id is not None
        assert result.already_escalated is False

        # Verify state transition from DELIBERATING
        mock_petition_repo.assign_fate_cas.assert_awaited_once_with(
            submission_id=petition_id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ESCALATED,
        )

    @pytest.mark.asyncio
    async def test_escalation_from_received_state_succeeds(
        self,
        petition_id: UUID,
        signer_id: UUID,
        mock_halt_checker: MagicMock,
    ) -> None:
        """Petition in RECEIVED state can be escalated (normal path)."""
        # Setup: Petition in RECEIVED state
        petition = FakePetition(petition_id, PetitionState.RECEIVED)

        mock_petition_repo = MagicMock()
        mock_petition_repo.get = AsyncMock(return_value=petition)
        mock_petition_repo.assign_fate_cas = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        # Act: Execute auto-escalation
        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_by=signer_id,
        )

        # Assert: Escalation successful
        assert result.triggered is True

        # Verify state transition from RECEIVED
        mock_petition_repo.assign_fate_cas.assert_awaited_once_with(
            submission_id=petition_id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ESCALATED,
        )


class TestDeliberationCancelledEvent:
    """Test DeliberationCancelledEvent creation (AC4)."""

    def test_event_creation_for_auto_escalation(self) -> None:
        """DeliberationCancelledEvent can be created for AUTO_ESCALATED reason."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        escalation_id = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=cancelled_at,
            escalation_id=escalation_id,
            transcript_preserved=True,
        )

        assert event.cancel_reason == CancelReason.AUTO_ESCALATED
        assert event.escalation_id == escalation_id
        assert event.transcript_preserved is True

    def test_event_requires_escalation_id_for_auto_escalated(self) -> None:
        """AUTO_ESCALATED reason requires escalation_id."""
        with pytest.raises(ValueError, match="escalation_id is required"):
            DeliberationCancelledEvent(
                event_id=uuid4(),
                session_id=uuid4(),
                petition_id=uuid4(),
                cancel_reason=CancelReason.AUTO_ESCALATED,
                cancelled_at=datetime.now(timezone.utc),
                escalation_id=None,  # Missing required for AUTO_ESCALATED
            )

    def test_event_with_participating_archons(self) -> None:
        """Event records participating archons for notification."""
        archon1 = uuid4()
        archon2 = uuid4()
        archon3 = uuid4()

        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=datetime.now(timezone.utc),
            escalation_id=uuid4(),
            participating_archons=(archon1, archon2, archon3),
        )

        assert len(event.participating_archons) == 3
        assert archon1 in event.participating_archons
        assert archon2 in event.participating_archons
        assert archon3 in event.participating_archons


class TestTranscriptPreservation:
    """Test that deliberation transcript is preserved on cancellation."""

    def test_transcript_preserved_defaults_true(self) -> None:
        """transcript_preserved defaults to True."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        assert event.transcript_preserved is True

    def test_transcript_preserved_explicit_true(self) -> None:
        """transcript_preserved can be explicitly set to True."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=datetime.now(timezone.utc),
            escalation_id=uuid4(),
            transcript_preserved=True,
        )

        assert event.transcript_preserved is True

    def test_transcript_preserved_explicit_false(self) -> None:
        """transcript_preserved can be set to False if needed."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.MANUAL,
            cancelled_at=datetime.now(timezone.utc),
            transcript_preserved=False,
        )

        assert event.transcript_preserved is False


class TestCancelReasonVariants:
    """Test all cancel reason variants."""

    def test_timeout_cancellation(self) -> None:
        """TIMEOUT cancellation creates valid event."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.TIMEOUT,
            cancelled_at=datetime.now(timezone.utc),
        )

        assert event.cancel_reason == CancelReason.TIMEOUT
        assert event.escalation_id is None

    def test_manual_cancellation(self) -> None:
        """MANUAL cancellation creates valid event."""
        admin_id = uuid4()

        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.MANUAL,
            cancelled_at=datetime.now(timezone.utc),
            cancelled_by=admin_id,
        )

        assert event.cancel_reason == CancelReason.MANUAL
        assert event.cancelled_by == admin_id

    def test_petition_withdrawn_cancellation(self) -> None:
        """PETITION_WITHDRAWN cancellation creates valid event."""
        submitter_id = uuid4()

        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.PETITION_WITHDRAWN,
            cancelled_at=datetime.now(timezone.utc),
            cancelled_by=submitter_id,
        )

        assert event.cancel_reason == CancelReason.PETITION_WITHDRAWN


class TestDeliberationCancellationWitnessing:
    """Test CT-12 witnessing compliance for cancellation events."""

    def test_signable_content_includes_cancel_reason(self) -> None:
        """signable_content includes cancel_reason for witnessing."""
        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=datetime.now(timezone.utc),
            escalation_id=uuid4(),
        )

        content = event.signable_content()
        assert b"AUTO_ESCALATED" in content

    def test_signable_content_includes_escalation_id(self) -> None:
        """signable_content includes escalation_id for traceability."""
        escalation_id = uuid4()

        event = DeliberationCancelledEvent(
            event_id=uuid4(),
            session_id=uuid4(),
            petition_id=uuid4(),
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=datetime.now(timezone.utc),
            escalation_id=escalation_id,
        )

        content = event.signable_content()
        assert str(escalation_id).encode() in content

    def test_to_dict_includes_all_fields_for_storage(self) -> None:
        """to_dict includes all fields for event storage."""
        event_id = uuid4()
        session_id = uuid4()
        petition_id = uuid4()
        escalation_id = uuid4()
        archon_id = uuid4()
        cancelled_at = datetime.now(timezone.utc)

        event = DeliberationCancelledEvent(
            event_id=event_id,
            session_id=session_id,
            petition_id=petition_id,
            cancel_reason=CancelReason.AUTO_ESCALATED,
            cancelled_at=cancelled_at,
            escalation_id=escalation_id,
            participating_archons=(archon_id,),
        )

        result = event.to_dict()

        assert result["event_id"] == str(event_id)
        assert result["session_id"] == str(session_id)
        assert result["petition_id"] == str(petition_id)
        assert result["cancel_reason"] == "AUTO_ESCALATED"
        assert result["cancelled_at"] == cancelled_at.isoformat()
        assert result["escalation_id"] == str(escalation_id)
        assert result["participating_archons"] == [str(archon_id)]
        assert result["schema_version"] == 1


class TestInvalidStateEscalation:
    """Test escalation behavior for invalid petition states."""

    @pytest.mark.asyncio
    async def test_acknowledged_petition_not_escalated(
        self,
        petition_id: UUID,
        mock_halt_checker: MagicMock,
    ) -> None:
        """Petition in ACKNOWLEDGED state cannot be escalated."""
        petition = FakePetition(petition_id, PetitionState.ACKNOWLEDGED)

        mock_petition_repo = MagicMock()
        mock_petition_repo.get = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
        )

        assert result.triggered is False
        assert result.already_escalated is False
        mock_petition_repo.assign_fate_cas.assert_not_called()

    @pytest.mark.asyncio
    async def test_referred_petition_not_escalated(
        self,
        petition_id: UUID,
        mock_halt_checker: MagicMock,
    ) -> None:
        """Petition in REFERRED state cannot be escalated."""
        petition = FakePetition(petition_id, PetitionState.REFERRED)

        mock_petition_repo = MagicMock()
        mock_petition_repo.get = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
        )

        assert result.triggered is False
        assert result.already_escalated is False
        mock_petition_repo.assign_fate_cas.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_escalated_petition_idempotent(
        self,
        petition_id: UUID,
        mock_halt_checker: MagicMock,
    ) -> None:
        """Petition already in ESCALATED state returns idempotent result."""
        petition = FakePetition(petition_id, PetitionState.ESCALATED)

        mock_petition_repo = MagicMock()
        mock_petition_repo.get = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
        )

        assert result.triggered is False
        assert result.already_escalated is True
        mock_petition_repo.assign_fate_cas.assert_not_called()
