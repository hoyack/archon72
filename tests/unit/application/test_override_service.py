"""Unit tests for OverrideService (Story 5.1, FR23; Story 5.4, FR26).

Tests the override service orchestration ensuring that:
- Override events are written BEFORE execution (FR23)
- Failed writes block override execution (AC3)
- Halt state is checked first (CT-11)
- Constitution validation runs before event write (FR26)

Constitutional Constraints Tested:
- FR23: Override actions must be logged before they take effect
- FR26: Overrides cannot suppress witnessing (Constitution Supremacy)
- CT-11: Silent failure destroys legitimacy -> HALT FIRST
- AC1: Override event written first, only then execute
- AC3: Failed log blocks override execution
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.override_executor import OverrideResult
from src.application.services.override_service import OverrideService
from src.domain.errors.override import (
    OverrideLoggingFailedError,
    WitnessSuppressionAttemptError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.override_event import ActionType, OverrideEventPayload
from src.infrastructure.stubs.constitution_validator_stub import (
    ConstitutionValidatorStub,
)


@pytest.fixture
def override_payload() -> OverrideEventPayload:
    """Create a valid override payload for testing."""
    return OverrideEventPayload(
        keeper_id="keeper-001",
        scope="config.parameter",
        duration=3600,
        reason="Emergency maintenance",
        action_type=ActionType.CONFIG_CHANGE,
        initiated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer."""
    writer = AsyncMock()
    mock_event = MagicMock()
    mock_event.event_id = uuid4()
    mock_event.sequence = 42
    writer.write_event.return_value = mock_event
    return writer


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create a mock halt checker (not halted by default)."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    checker.get_halt_reason.return_value = None
    return checker


@pytest.fixture
def mock_override_executor() -> AsyncMock:
    """Create a mock override executor."""
    executor = AsyncMock()
    executor.execute_override.return_value = OverrideResult(
        success=True,
        event_id=uuid4(),
        error_message=None,
    )
    return executor


@pytest.fixture
def override_service(
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
    mock_override_executor: AsyncMock,
) -> OverrideService:
    """Create OverrideService with mocked dependencies."""
    return OverrideService(
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
        override_executor=mock_override_executor,
    )


class TestOverrideServiceHaltCheck:
    """Tests for HALT FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_halt_check_runs_first(
        self,
        override_service: OverrideService,
        mock_halt_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that halt check runs before any other operation."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Test halt"

        with pytest.raises(SystemHaltedError, match="CT-11"):
            await override_service.initiate_override(override_payload)

        # Halt checker was called
        mock_halt_checker.is_halted.assert_called_once()

        # Event writer was NOT called (halt check stops processing)
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_halt_check_passes_when_not_halted(
        self,
        override_service: OverrideService,
        mock_halt_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that processing continues when not halted."""
        mock_halt_checker.is_halted.return_value = False

        await override_service.initiate_override(override_payload)

        # Halt checker was called
        mock_halt_checker.is_halted.assert_called_once()

        # Event writer was called (processing continued)
        mock_event_writer.write_event.assert_called_once()


class TestOverrideEventLogging:
    """Tests for override event logging (FR23, AC1)."""

    @pytest.mark.asyncio
    async def test_override_event_written_before_execution(
        self,
        override_service: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that override event is written BEFORE execution (FR23, AC1)."""
        call_order = []

        async def track_write_event(*args, **kwargs):
            call_order.append("write_event")
            mock_event = MagicMock()
            mock_event.event_id = uuid4()
            mock_event.sequence = 42
            return mock_event

        async def track_execute_override(*args, **kwargs):
            call_order.append("execute_override")
            return OverrideResult(success=True, event_id=uuid4())

        mock_event_writer.write_event.side_effect = track_write_event
        mock_override_executor.execute_override.side_effect = track_execute_override

        await override_service.initiate_override(override_payload)

        # Verify order: write_event BEFORE execute_override
        assert call_order == ["write_event", "execute_override"]

    @pytest.mark.asyncio
    async def test_override_event_includes_required_fields(
        self,
        override_service: OverrideService,
        mock_event_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that override event includes all required fields (AC2)."""
        await override_service.initiate_override(override_payload)

        # Get the call arguments
        call_kwargs = mock_event_writer.write_event.call_args.kwargs

        assert call_kwargs["event_type"] == "override.initiated"
        assert call_kwargs["payload"]["keeper_id"] == override_payload.keeper_id
        assert call_kwargs["payload"]["scope"] == override_payload.scope
        assert call_kwargs["payload"]["duration"] == override_payload.duration
        assert call_kwargs["payload"]["reason"] == override_payload.reason
        assert (
            call_kwargs["payload"]["action_type"] == override_payload.action_type.value
        )

    @pytest.mark.asyncio
    async def test_event_id_passed_to_executor(
        self,
        override_service: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that event_id from write is passed to executor."""
        expected_event_id = uuid4()
        mock_event = MagicMock()
        mock_event.event_id = expected_event_id
        mock_event.sequence = 42
        mock_event_writer.write_event.return_value = mock_event

        await override_service.initiate_override(override_payload)

        # Verify executor received the event_id
        call_kwargs = mock_override_executor.execute_override.call_args.kwargs
        assert call_kwargs["event_id"] == expected_event_id


class TestOverrideLogFailure:
    """Tests for failed override logging (AC3)."""

    @pytest.mark.asyncio
    async def test_failed_write_blocks_execution(
        self,
        override_service: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that failed write blocks override execution (AC3)."""
        mock_event_writer.write_event.side_effect = Exception("Write failed")

        with pytest.raises(OverrideLoggingFailedError, match="FR23"):
            await override_service.initiate_override(override_payload)

        # Override executor was NOT called
        mock_override_executor.execute_override.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_write_returns_error_to_keeper(
        self,
        override_service: OverrideService,
        mock_event_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that failed write returns error (AC3)."""
        mock_event_writer.write_event.side_effect = Exception(
            "Database connection failed"
        )

        with pytest.raises(OverrideLoggingFailedError) as exc_info:
            await override_service.initiate_override(override_payload)

        assert "FR23" in str(exc_info.value)
        assert "Database connection failed" in str(exc_info.value)


class TestOverrideExecution:
    """Tests for successful override execution."""

    @pytest.mark.asyncio
    async def test_successful_override_returns_result(
        self,
        override_service: OverrideService,
        mock_override_executor: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that successful override returns OverrideResult."""
        result = await override_service.initiate_override(override_payload)

        assert result.success is True
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_execution_failure_returns_result_with_error(
        self,
        override_service: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that execution failure returns result with error message."""
        event_id = uuid4()
        mock_event = MagicMock()
        mock_event.event_id = event_id
        mock_event.sequence = 42
        mock_event_writer.write_event.return_value = mock_event

        mock_override_executor.execute_override.return_value = OverrideResult(
            success=False,
            event_id=event_id,
            error_message="Config service unavailable",
        )

        result = await override_service.initiate_override(override_payload)

        # Event was logged but execution failed
        assert result.success is False
        assert result.error_message == "Config service unavailable"
        assert result.event_id == event_id

    @pytest.mark.asyncio
    async def test_execution_exception_returns_failure_result(
        self,
        override_service: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that execution exception returns failure result (event still logged)."""
        event_id = uuid4()
        mock_event = MagicMock()
        mock_event.event_id = event_id
        mock_event.sequence = 42
        mock_event_writer.write_event.return_value = mock_event

        mock_override_executor.execute_override.side_effect = Exception(
            "Unexpected error"
        )

        result = await override_service.initiate_override(override_payload)

        # Event was logged, but execution failed with exception
        assert result.success is False
        assert "Unexpected error" in (result.error_message or "")
        assert result.event_id == event_id


class TestConstitutionValidation:
    """Tests for constitution validation (FR26, Story 5.4)."""

    @pytest.fixture
    def constitution_validator(self) -> ConstitutionValidatorStub:
        """Create a constitution validator stub."""
        return ConstitutionValidatorStub()

    @pytest.fixture
    def override_service_with_validator(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
        constitution_validator: ConstitutionValidatorStub,
    ) -> OverrideService:
        """Create OverrideService with constitution validator."""
        return OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=constitution_validator,
        )

    @pytest.mark.asyncio
    async def test_constitution_validation_called_before_event_write(
        self,
        override_service_with_validator: OverrideService,
        constitution_validator: ConstitutionValidatorStub,
        mock_event_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """FR26: Constitution validation must run before event write."""
        await override_service_with_validator.initiate_override(override_payload)

        # Verify validation was called with the scope
        assert override_payload.scope in constitution_validator.validation_calls

    @pytest.mark.asyncio
    async def test_witness_scope_override_rejected(
        self,
        override_service_with_validator: OverrideService,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """FR26: Override with 'witness' scope must be rejected."""
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="witness",  # FORBIDDEN
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError) as exc_info:
            await override_service_with_validator.initiate_override(payload)

        assert "FR26" in str(exc_info.value)

        # Event writer should NOT have been called
        mock_event_writer.write_event.assert_not_called()

        # Override executor should NOT have been called
        mock_override_executor.execute_override.assert_not_called()

    @pytest.mark.asyncio
    async def test_attestation_scope_override_rejected(
        self,
        override_service_with_validator: OverrideService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """FR26: Override with 'attestation' scope must be rejected."""
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="attestation.disable",  # FORBIDDEN
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service_with_validator.initiate_override(payload)

        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_scope_passes_validation(
        self,
        override_service_with_validator: OverrideService,
        mock_event_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Valid business scopes should pass validation."""
        # override_payload uses "config.parameter" which is valid
        await override_service_with_validator.initiate_override(override_payload)

        # Event writer should have been called
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_failure_prevents_any_execution(
        self,
        override_service_with_validator: OverrideService,
        mock_halt_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """FR26: Validation failure must prevent ALL downstream operations."""
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="witnessing",  # FORBIDDEN
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(WitnessSuppressionAttemptError):
            await override_service_with_validator.initiate_override(payload)

        # Halt check runs (it's before validation)
        mock_halt_checker.is_halted.assert_called_once()

        # Nothing else runs
        mock_event_writer.write_event.assert_not_called()
        mock_override_executor.execute_override.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_works_without_validator(
        self,
        mock_event_writer: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_override_executor: AsyncMock,
    ) -> None:
        """Service should work when validator is not provided (backward compatibility)."""
        service = OverrideService(
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker,
            override_executor=mock_override_executor,
            constitution_validator=None,  # No validator
        )

        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="witness",  # This WOULD be forbidden with validator
            duration=3600,
            reason="Emergency",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=datetime.now(timezone.utc),
        )

        # Without validator, this should pass (no validation)
        result = await service.initiate_override(payload)

        assert result.success is True
