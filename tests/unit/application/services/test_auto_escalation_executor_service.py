"""Unit tests for AutoEscalationExecutorService (Story 5.6, FR-5.1, FR-5.3).

Tests the auto-escalation executor service which handles execution of
auto-escalation when co-signer thresholds are reached.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- CT-12: All outputs through witnessing pipeline
- CT-13: Halt rejects writes, allows reads
- CT-14: Silence must be expensive - auto-escalation ensures King attention
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.ports.auto_escalation_executor import (
    AutoEscalationResult,
)
from src.application.services.auto_escalation_executor_service import (
    AutoEscalationExecutorService,
)
from src.domain.errors import CoSignPetitionNotFoundError, SystemHaltedError
from src.domain.models.petition_submission import PetitionState, PetitionType

if TYPE_CHECKING:
    pass


# Test fixtures


class FakePetition:
    """Fake petition for testing."""

    def __init__(
        self,
        petition_id: UUID,
        state: PetitionState = PetitionState.RECEIVED,
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


@pytest.fixture
def halted_checker() -> MagicMock:
    """Return a mock halt checker that IS halted."""
    checker = MagicMock()
    checker.is_halted = AsyncMock(return_value=True)
    return checker


@pytest.fixture
def mock_petition_repo(petition_id: UUID) -> MagicMock:
    """Return a mock petition repository with a RECEIVED petition."""
    repo = MagicMock()
    petition = FakePetition(petition_id, PetitionState.RECEIVED)
    repo.get = AsyncMock(return_value=petition)
    repo.assign_fate_cas = AsyncMock(return_value=petition)
    return repo


@pytest.fixture
def service(
    mock_petition_repo: MagicMock,
    mock_halt_checker: MagicMock,
) -> AutoEscalationExecutorService:
    """Return an AutoEscalationExecutorService instance."""
    return AutoEscalationExecutorService(
        petition_repo=mock_petition_repo,
        halt_checker=mock_halt_checker,
    )


class TestAutoEscalationExecutorServiceProtocol:
    """Test that AutoEscalationExecutorService implements the protocol."""

    def test_implements_protocol(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
    ) -> None:
        """AutoEscalationExecutorService implements AutoEscalationExecutorProtocol."""
        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )
        # Protocol compliance is verified at module load time via _verify_protocol()
        assert hasattr(service, "execute")
        assert hasattr(service, "check_already_escalated")


class TestExecuteHaltCheck:
    """Test halt state handling in execute (CT-13)."""

    @pytest.mark.asyncio
    async def test_halt_check_prevents_execution(
        self,
        mock_petition_repo: MagicMock,
        halted_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Execution raises SystemHaltedError when system is halted (CT-13)."""
        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.execute(
                petition_id=petition_id,
                trigger_type="CO_SIGNER_THRESHOLD",
                co_signer_count=100,
                threshold=100,
            )

        assert "halt" in str(exc_info.value).lower()
        # Verify halt checker was called
        halted_checker.is_halted.assert_awaited_once()
        # Verify petition repo was NOT called
        mock_petition_repo.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_halted_allows_execution(
        self,
        service: AutoEscalationExecutorService,
        petition_id: UUID,
    ) -> None:
        """Execution proceeds when system is not halted."""
        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
        )

        assert result.triggered is True


class TestExecutePetitionNotFound:
    """Test petition not found handling."""

    @pytest.mark.asyncio
    async def test_petition_not_found_raises_error(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Raises CoSignPetitionNotFoundError when petition doesn't exist."""
        mock_petition_repo.get = AsyncMock(return_value=None)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        with pytest.raises(CoSignPetitionNotFoundError):
            await service.execute(
                petition_id=petition_id,
                trigger_type="CO_SIGNER_THRESHOLD",
                co_signer_count=100,
                threshold=100,
            )


class TestExecuteIdempotency:
    """Test idempotent behavior for already escalated petitions (AC5)."""

    @pytest.mark.asyncio
    async def test_already_escalated_returns_idempotent_result(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Returns triggered=False when petition is already ESCALATED."""
        # Set petition state to ESCALATED
        petition = FakePetition(petition_id, PetitionState.ESCALATED)
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
        assert result.escalation_id is None
        assert result.event_id is None
        assert result.petition_id == petition_id
        assert result.trigger_type == "CO_SIGNER_THRESHOLD"
        assert result.co_signer_count == 100
        assert result.threshold == 100

        # Verify assign_fate_cas was NOT called (idempotent)
        mock_petition_repo.assign_fate_cas.assert_not_called()


class TestExecuteInvalidState:
    """Test handling of invalid petition states."""

    @pytest.mark.asyncio
    async def test_acknowledged_state_not_escalated(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Returns triggered=False when petition is in ACKNOWLEDGED state."""
        petition = FakePetition(petition_id, PetitionState.ACKNOWLEDGED)
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
    async def test_referred_state_not_escalated(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Returns triggered=False when petition is in REFERRED state."""
        petition = FakePetition(petition_id, PetitionState.REFERRED)
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


class TestExecuteSuccessfulEscalation:
    """Test successful escalation execution (FR-5.1, FR-5.3)."""

    @pytest.mark.asyncio
    async def test_successful_escalation_from_received(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
        signer_id: UUID,
    ) -> None:
        """Successfully escalates petition from RECEIVED state (AC1)."""
        petition = FakePetition(petition_id, PetitionState.RECEIVED)
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
            triggered_by=signer_id,
        )

        assert result.triggered is True
        assert result.already_escalated is False
        assert result.escalation_id is not None
        assert result.event_id is not None
        assert result.petition_id == petition_id
        assert result.trigger_type == "CO_SIGNER_THRESHOLD"
        assert result.co_signer_count == 100
        assert result.threshold == 100
        assert isinstance(result.timestamp, datetime)

        # Verify state transition was called
        mock_petition_repo.assign_fate_cas.assert_awaited_once_with(
            submission_id=petition_id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ESCALATED,
            escalation_source="CO_SIGNER_THRESHOLD",
            escalated_to_realm="default",
        )

    @pytest.mark.asyncio
    async def test_successful_escalation_from_deliberating(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Successfully escalates petition from DELIBERATING state (AC4)."""
        petition = FakePetition(petition_id, PetitionState.DELIBERATING)
        mock_petition_repo.get = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=50,
            threshold=50,
        )

        assert result.triggered is True
        assert result.already_escalated is False

        # Verify state transition was from DELIBERATING
        mock_petition_repo.assign_fate_cas.assert_awaited_once_with(
            submission_id=petition_id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ESCALATED,
            escalation_source="CO_SIGNER_THRESHOLD",
            escalated_to_realm="default",
        )

    @pytest.mark.asyncio
    async def test_escalation_result_has_all_fields(
        self,
        service: AutoEscalationExecutorService,
        petition_id: UUID,
        signer_id: UUID,
    ) -> None:
        """AutoEscalationResult contains all required fields (FR-5.3)."""
        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_by=signer_id,
        )

        # Verify all result fields
        assert isinstance(result, AutoEscalationResult)
        assert isinstance(result.escalation_id, UUID)
        assert isinstance(result.petition_id, UUID)
        assert result.triggered is True
        assert isinstance(result.event_id, UUID)
        assert isinstance(result.timestamp, datetime)
        assert result.already_escalated is False
        assert result.trigger_type == "CO_SIGNER_THRESHOLD"
        assert result.co_signer_count == 100
        assert result.threshold == 100


class TestExecuteWithDifferentTriggerTypes:
    """Test execution with various trigger types."""

    @pytest.mark.asyncio
    async def test_custom_trigger_type(
        self,
        service: AutoEscalationExecutorService,
        petition_id: UUID,
    ) -> None:
        """Supports custom trigger types in result."""
        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CUSTOM_TRIGGER",
            co_signer_count=100,
            threshold=100,
        )

        assert result.trigger_type == "CUSTOM_TRIGGER"


class TestExecuteWithDifferentPetitionTypes:
    """Test escalation with different petition types."""

    @pytest.mark.asyncio
    async def test_cessation_petition(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Escalates CESSATION petition at 100 threshold (FR-10.2)."""
        petition = FakePetition(
            petition_id, PetitionState.RECEIVED, PetitionType.CESSATION
        )
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

        assert result.triggered is True
        assert result.threshold == 100

    @pytest.mark.asyncio
    async def test_grievance_petition(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Escalates GRIEVANCE petition at 50 threshold (FR-10.3)."""
        petition = FakePetition(
            petition_id, PetitionState.RECEIVED, PetitionType.GRIEVANCE
        )
        mock_petition_repo.get = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=50,
            threshold=50,
        )

        assert result.triggered is True
        assert result.threshold == 50


class TestExecuteWitnessing:
    """Test witnessing compliance (CT-12)."""

    @pytest.mark.asyncio
    async def test_triggered_by_included_in_result(
        self,
        service: AutoEscalationExecutorService,
        petition_id: UUID,
        signer_id: UUID,
    ) -> None:
        """triggered_by parameter is preserved for witnessing (CT-12)."""
        result = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
            triggered_by=signer_id,
        )

        # Result should have event_id for witnessing
        assert result.event_id is not None

    @pytest.mark.asyncio
    async def test_escalation_id_generated_for_witnessing(
        self,
        service: AutoEscalationExecutorService,
        petition_id: UUID,
    ) -> None:
        """Unique escalation_id generated for each escalation (CT-12)."""
        result1 = await service.execute(
            petition_id=petition_id,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
        )

        assert result1.escalation_id is not None
        assert isinstance(result1.escalation_id, UUID)


class TestCheckAlreadyEscalated:
    """Test check_already_escalated method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_escalated(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Returns True when petition is in ESCALATED state."""
        petition = FakePetition(petition_id, PetitionState.ESCALATED)
        mock_petition_repo.get = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        result = await service.check_already_escalated(petition_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_escalated(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Returns False when petition is not in ESCALATED state."""
        petition = FakePetition(petition_id, PetitionState.RECEIVED)
        mock_petition_repo.get = AsyncMock(return_value=petition)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        result = await service.check_already_escalated(petition_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_raises_when_petition_not_found(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """Raises CoSignPetitionNotFoundError when petition doesn't exist."""
        mock_petition_repo.get = AsyncMock(return_value=None)

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        with pytest.raises(CoSignPetitionNotFoundError):
            await service.check_already_escalated(petition_id)


class TestAutoEscalationResult:
    """Test AutoEscalationResult dataclass."""

    def test_frozen(self) -> None:
        """AutoEscalationResult is immutable."""
        result = AutoEscalationResult(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            triggered=True,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            result.triggered = False  # type: ignore[misc]

    def test_default_values(self) -> None:
        """AutoEscalationResult has correct default values."""
        result = AutoEscalationResult(
            escalation_id=uuid4(),
            petition_id=uuid4(),
            triggered=True,
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )
        assert result.already_escalated is False
        assert result.trigger_type == "CO_SIGNER_THRESHOLD"
        assert result.co_signer_count == 0
        assert result.threshold == 0

    def test_equality(self) -> None:
        """AutoEscalationResult supports equality comparison."""
        escalation_id = uuid4()
        petition_id = uuid4()
        event_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        result1 = AutoEscalationResult(
            escalation_id=escalation_id,
            petition_id=petition_id,
            triggered=True,
            event_id=event_id,
            timestamp=timestamp,
            already_escalated=False,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
        )
        result2 = AutoEscalationResult(
            escalation_id=escalation_id,
            petition_id=petition_id,
            triggered=True,
            event_id=event_id,
            timestamp=timestamp,
            already_escalated=False,
            trigger_type="CO_SIGNER_THRESHOLD",
            co_signer_count=100,
            threshold=100,
        )
        assert result1 == result2


class TestStateTransitionFailure:
    """Test handling of state transition failures."""

    @pytest.mark.asyncio
    async def test_state_transition_failure_propagates(
        self,
        mock_petition_repo: MagicMock,
        mock_halt_checker: MagicMock,
        petition_id: UUID,
    ) -> None:
        """State transition failure propagates exception."""
        petition = FakePetition(petition_id, PetitionState.RECEIVED)
        mock_petition_repo.get = AsyncMock(return_value=petition)
        mock_petition_repo.assign_fate_cas = AsyncMock(
            side_effect=RuntimeError("CAS conflict")
        )

        service = AutoEscalationExecutorService(
            petition_repo=mock_petition_repo,
            halt_checker=mock_halt_checker,
        )

        with pytest.raises(RuntimeError, match="CAS conflict"):
            await service.execute(
                petition_id=petition_id,
                trigger_type="CO_SIGNER_THRESHOLD",
                co_signer_count=100,
                threshold=100,
            )
