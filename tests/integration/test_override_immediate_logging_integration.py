"""Integration tests for Override Immediate Logging (Story 5.1, FR23).

Tests the end-to-end override flow ensuring that:
- Override events are written BEFORE execution (FR23)
- Failed writes block override execution (AC3)
- System halt blocks override initiation (CT-11)

NOTE ON TEST STRATEGY:
    These tests use stubs and mocks to test the full override flow
    without requiring actual database connections. They verify:
    1. OverrideService orchestration
    2. Event logging before execution
    3. Error handling for failed writes
    4. Halt state checking

Constitutional Constraints Tested:
- FR23: Override actions must be logged before they take effect
- CT-11: Silent failure destroys legitimacy -> HALT FIRST
- CT-12: Witnessing creates accountability

Acceptance Criteria Tested:
- AC1: Override event written FIRST, then execution
- AC3: Failed log blocks override execution
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.event_writer_service import EventWriterService
from src.application.services.override_service import OverrideService
from src.domain.errors.override import OverrideLoggingFailedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.override_event import ActionType, OverrideEventPayload
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.override_executor_stub import OverrideExecutorStub
from src.infrastructure.stubs.writer_lock_stub import WriterLockStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a HaltCheckerStub (not halted by default)."""
    return HaltCheckerStub()


@pytest.fixture
def writer_lock() -> WriterLockStub:
    """Create a WriterLockStub with lock acquired."""
    stub = WriterLockStub()
    stub._held = True  # Simulate lock acquisition for testing
    return stub


@pytest.fixture
def override_executor() -> OverrideExecutorStub:
    """Create an OverrideExecutorStub."""
    return OverrideExecutorStub()


@pytest.fixture
def mock_atomic_writer() -> AsyncMock:
    """Create a mock AtomicEventWriter that simulates successful writes."""
    writer = AsyncMock()
    sequence_counter = [0]

    def create_mock_event(*args, **kwargs) -> MagicMock:
        sequence_counter[0] += 1
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.sequence = sequence_counter[0]
        mock_event.content_hash = "c" * 64
        mock_event.event_type = kwargs.get("event_type", "test.event")
        mock_event.local_timestamp = kwargs.get("local_timestamp", datetime.now(timezone.utc))
        mock_event.authority_timestamp = datetime.now(timezone.utc)
        return mock_event

    writer.write_event = AsyncMock(side_effect=create_mock_event)
    return writer


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create a mock EventStorePort."""
    store = AsyncMock()
    store.get_latest_event = AsyncMock(return_value=None)
    store.append_event = AsyncMock()
    return store


@pytest.fixture
def event_writer_service(
    mock_atomic_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
    writer_lock: WriterLockStub,
    mock_event_store: AsyncMock,
) -> EventWriterService:
    """Create an EventWriterService with mock/stub dependencies."""
    service = EventWriterService(
        atomic_writer=mock_atomic_writer,
        halt_checker=halt_checker,
        writer_lock=writer_lock,
        event_store=mock_event_store,
    )
    # Mark as verified for testing
    service._verified = True
    return service


@pytest.fixture
def override_service(
    event_writer_service: EventWriterService,
    halt_checker: HaltCheckerStub,
    override_executor: OverrideExecutorStub,
) -> OverrideService:
    """Create an OverrideService with stub/mock dependencies."""
    return OverrideService(
        event_writer=event_writer_service,
        halt_checker=halt_checker,
        override_executor=override_executor,
    )


@pytest.fixture
def override_payload() -> OverrideEventPayload:
    """Create a valid override payload for testing."""
    return OverrideEventPayload(
        keeper_id="keeper-001",
        scope="config.parameter",
        duration=3600,
        reason="Integration test override",
        action_type=ActionType.CONFIG_CHANGE,
        initiated_at=datetime.now(timezone.utc),
    )


class TestEndToEndOverrideFlow:
    """Integration tests for the end-to-end override flow (AC1)."""

    @pytest.mark.asyncio
    async def test_override_initiated_writes_event_then_executes(
        self,
        override_service: OverrideService,
        mock_atomic_writer: AsyncMock,
        override_executor: OverrideExecutorStub,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that override event is written, then execution happens (AC1)."""
        result = await override_service.initiate_override(override_payload)

        # Verify success
        assert result.success is True

        # Verify event was written
        mock_atomic_writer.write_event.assert_called_once()
        call_kwargs = mock_atomic_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == "override.initiated"
        assert call_kwargs["payload"]["keeper_id"] == "keeper-001"
        assert call_kwargs["payload"]["scope"] == "config.parameter"

        # Verify execution happened
        assert len(override_executor.executed_overrides) == 1
        executed = override_executor.executed_overrides[0]
        assert executed.payload == override_payload

    @pytest.mark.asyncio
    async def test_multiple_overrides_tracked(
        self,
        override_service: OverrideService,
        override_executor: OverrideExecutorStub,
    ) -> None:
        """Test that multiple overrides are tracked independently."""
        now = datetime.now(timezone.utc)

        payloads = [
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.timeout",
                duration=1800,
                reason="Adjust timeout",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            ),
            OverrideEventPayload(
                keeper_id="keeper-002",
                scope="ceremony.health_check",
                duration=7200,
                reason="Maintenance window",
                action_type=ActionType.CEREMONY_OVERRIDE,
                initiated_at=now,
            ),
        ]

        for payload in payloads:
            await override_service.initiate_override(payload)

        assert len(override_executor.executed_overrides) == 2


class TestFailedWriteBlocksExecution:
    """Integration tests for failed write blocking execution (AC3)."""

    @pytest.mark.asyncio
    async def test_event_write_failure_prevents_execution(
        self,
        override_service: OverrideService,
        mock_atomic_writer: AsyncMock,
        override_executor: OverrideExecutorStub,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that failed event write prevents override execution (AC3)."""
        # Configure the atomic writer to fail
        mock_atomic_writer.write_event.side_effect = Exception("Database unavailable")

        with pytest.raises(OverrideLoggingFailedError, match="FR23"):
            await override_service.initiate_override(override_payload)

        # Verify NO execution occurred
        assert len(override_executor.executed_overrides) == 0

    @pytest.mark.asyncio
    async def test_error_message_returned_to_keeper(
        self,
        override_service: OverrideService,
        mock_atomic_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that error message is returned to Keeper on failure (AC3)."""
        mock_atomic_writer.write_event.side_effect = Exception("Connection timeout")

        with pytest.raises(OverrideLoggingFailedError) as exc_info:
            await override_service.initiate_override(override_payload)

        error_message = str(exc_info.value)
        assert "FR23" in error_message
        assert "Connection timeout" in error_message


class TestHaltStateBlocksOverride:
    """Integration tests for halt state blocking override (CT-11)."""

    @pytest.mark.asyncio
    async def test_system_halted_rejects_override(
        self,
        override_service: OverrideService,
        halt_checker: HaltCheckerStub,
        mock_atomic_writer: AsyncMock,
        override_executor: OverrideExecutorStub,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that system halt rejects override with SystemHaltedError."""
        # Set system to halted state
        halt_checker.set_halted(True, "Fork detected - investigation required")

        with pytest.raises(SystemHaltedError, match="CT-11"):
            await override_service.initiate_override(override_payload)

        # Verify NO event write attempted
        mock_atomic_writer.write_event.assert_not_called()

        # Verify NO execution occurred
        assert len(override_executor.executed_overrides) == 0

    @pytest.mark.asyncio
    async def test_override_proceeds_when_not_halted(
        self,
        override_service: OverrideService,
        halt_checker: HaltCheckerStub,
        mock_atomic_writer: AsyncMock,
        override_executor: OverrideExecutorStub,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that override proceeds when system is not halted."""
        # Ensure system is NOT halted
        halt_checker.set_halted(False)

        result = await override_service.initiate_override(override_payload)

        # Verify success
        assert result.success is True
        mock_atomic_writer.write_event.assert_called_once()
        assert len(override_executor.executed_overrides) == 1


class TestOverrideExecutionFailure:
    """Integration tests for override execution failure handling."""

    @pytest.mark.asyncio
    async def test_execution_failure_after_logging(
        self,
        override_service: OverrideService,
        override_executor: OverrideExecutorStub,
        mock_atomic_writer: AsyncMock,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that execution failure is handled after event is logged."""
        # Configure executor to fail
        override_executor.set_should_fail(True, "Config service unavailable")

        result = await override_service.initiate_override(override_payload)

        # Event was still logged (write succeeded)
        mock_atomic_writer.write_event.assert_called_once()

        # But execution failed
        assert result.success is False
        assert "Config service unavailable" in (result.error_message or "")

        # Event ID is still returned (for auditing)
        assert result.event_id is not None


class TestOverridePayloadValidation:
    """Integration tests for override payload validation."""

    @pytest.mark.asyncio
    async def test_all_action_types_work(
        self,
        override_service: OverrideService,
        override_executor: OverrideExecutorStub,
    ) -> None:
        """Test that all ActionTypes can be used in overrides."""
        now = datetime.now(timezone.utc)

        for action_type in ActionType:
            override_executor.clear_executed()

            payload = OverrideEventPayload(
                keeper_id="keeper-001",
                scope="test.scope",
                duration=3600,
                reason=f"Testing {action_type.value}",
                action_type=action_type,
                initiated_at=now,
            )

            result = await override_service.initiate_override(payload)
            assert result.success is True
            assert len(override_executor.executed_overrides) == 1
