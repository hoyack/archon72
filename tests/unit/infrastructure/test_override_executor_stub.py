"""Unit tests for OverrideExecutorStub (Story 5.1, FR23).

Tests the stub implementation of OverrideExecutorPort used for
testing the override flow.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.override_event import ActionType, OverrideEventPayload
from src.infrastructure.stubs.override_executor_stub import (
    ExecutedOverride,
    OverrideExecutorStub,
)


@pytest.fixture
def override_payload() -> OverrideEventPayload:
    """Create a valid override payload for testing."""
    return OverrideEventPayload(
        keeper_id="keeper-001",
        scope="config.parameter",
        duration=3600,
        reason="Test override",
        action_type=ActionType.CONFIG_CHANGE,
        initiated_at=datetime.now(timezone.utc),
    )


class TestOverrideExecutorStub:
    """Tests for OverrideExecutorStub."""

    @pytest.mark.asyncio
    async def test_execute_override_success(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test successful override execution."""
        stub = OverrideExecutorStub()
        event_id = uuid4()

        result = await stub.execute_override(override_payload, event_id)

        assert result.success is True
        assert result.event_id == event_id
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_tracks_executed_overrides(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that stub tracks executed overrides."""
        stub = OverrideExecutorStub()
        event_id = uuid4()

        await stub.execute_override(override_payload, event_id)

        assert len(stub.executed_overrides) == 1
        executed = stub.executed_overrides[0]
        assert executed.payload == override_payload
        assert executed.event_id == event_id

    @pytest.mark.asyncio
    async def test_tracks_multiple_overrides(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test tracking multiple overrides."""
        stub = OverrideExecutorStub()

        event_id_1 = uuid4()
        event_id_2 = uuid4()

        await stub.execute_override(override_payload, event_id_1)
        await stub.execute_override(override_payload, event_id_2)

        assert len(stub.executed_overrides) == 2
        assert stub.executed_overrides[0].event_id == event_id_1
        assert stub.executed_overrides[1].event_id == event_id_2

    @pytest.mark.asyncio
    async def test_configured_to_fail(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test stub configured to fail."""
        stub = OverrideExecutorStub(should_fail=True, failure_message="Config error")
        event_id = uuid4()

        result = await stub.execute_override(override_payload, event_id)

        assert result.success is False
        assert result.event_id == event_id
        assert result.error_message == "Config error"

    @pytest.mark.asyncio
    async def test_set_should_fail(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test dynamically setting failure mode."""
        stub = OverrideExecutorStub()
        event_id = uuid4()

        # First execution succeeds
        result1 = await stub.execute_override(override_payload, event_id)
        assert result1.success is True

        # Configure to fail
        stub.set_should_fail(True, "Runtime error")

        # Second execution fails
        result2 = await stub.execute_override(override_payload, event_id)
        assert result2.success is False
        assert result2.error_message == "Runtime error"

    @pytest.mark.asyncio
    async def test_clear_executed(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test clearing executed overrides."""
        stub = OverrideExecutorStub()
        event_id = uuid4()

        await stub.execute_override(override_payload, event_id)
        assert len(stub.executed_overrides) == 1

        stub.clear_executed()
        assert len(stub.executed_overrides) == 0

    @pytest.mark.asyncio
    async def test_failed_execution_not_tracked(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test that failed executions are not tracked."""
        stub = OverrideExecutorStub(should_fail=True)
        event_id = uuid4()

        await stub.execute_override(override_payload, event_id)

        # Failed executions should not be in the list
        assert len(stub.executed_overrides) == 0

    def test_executed_overrides_returns_copy(self) -> None:
        """Test that executed_overrides returns a copy."""
        stub = OverrideExecutorStub()

        list1 = stub.executed_overrides
        list2 = stub.executed_overrides

        # Should be different list objects
        assert list1 is not list2


class TestExecutedOverride:
    """Tests for ExecutedOverride dataclass."""

    def test_create_executed_override(
        self,
        override_payload: OverrideEventPayload,
    ) -> None:
        """Test creating ExecutedOverride record."""
        event_id = uuid4()

        executed = ExecutedOverride(
            payload=override_payload,
            event_id=event_id,
        )

        assert executed.payload == override_payload
        assert executed.event_id == event_id
