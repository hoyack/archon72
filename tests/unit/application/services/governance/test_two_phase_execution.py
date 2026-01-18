"""Unit tests for TwoPhaseExecution context manager.

Story: consent-gov-1.6: Two-Phase Event Emission

Tests the TwoPhaseExecution async context manager that encapsulates
the two-phase event emission pattern for automatic intent/outcome handling.

Constitutional Reference:
- AD-3: Two-phase event emission
- AC5: No orphaned intents allowed
- AC9: TwoPhaseEventEmitter service encapsulates the two-phase pattern
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.governance.two_phase_execution import (
    TwoPhaseExecution,
)


@pytest.fixture
def mock_emitter() -> AsyncMock:
    """Create a mock TwoPhaseEventEmitter."""
    emitter = AsyncMock()
    emitter.emit_intent.return_value = uuid4()
    return emitter


class TestTwoPhaseExecution:
    """Tests for TwoPhaseExecution context manager (AC5, AC9)."""

    @pytest.mark.asyncio
    async def test_emits_intent_on_enter(self, mock_emitter: AsyncMock) -> None:
        """Intent should be emitted on context entry."""
        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        ):
            pass

        mock_emitter.emit_intent.assert_called_once_with(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        )

    @pytest.mark.asyncio
    async def test_emits_commit_on_success(self, mock_emitter: AsyncMock) -> None:
        """Commit should be emitted on successful exit."""
        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        ) as execution:
            execution.set_result({"new_state": "accepted"})

        mock_emitter.emit_commit.assert_called_once()
        call_args = mock_emitter.emit_commit.call_args
        assert call_args.kwargs["result_payload"] == {"new_state": "accepted"}

    @pytest.mark.asyncio
    async def test_emits_failure_on_exception(self, mock_emitter: AsyncMock) -> None:
        """Failure should be emitted when exception occurs."""
        with pytest.raises(ValueError):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise ValueError("Operation failed")

        mock_emitter.emit_failure.assert_called_once()
        mock_emitter.emit_commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_includes_exception_details(
        self, mock_emitter: AsyncMock
    ) -> None:
        """Failure event should include exception details."""
        with pytest.raises(RuntimeError):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise RuntimeError("Something went wrong")

        call_args = mock_emitter.emit_failure.call_args
        assert "RuntimeError" in str(call_args.kwargs["failure_details"])
        assert "Something went wrong" in call_args.kwargs["failure_reason"]

    @pytest.mark.asyncio
    async def test_exception_is_not_suppressed(self, mock_emitter: AsyncMock) -> None:
        """Exception should propagate after failure is emitted."""
        with pytest.raises(ValueError, match="specific error"):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise ValueError("specific error")

    @pytest.mark.asyncio
    async def test_correlation_id_available_in_context(
        self, mock_emitter: AsyncMock
    ) -> None:
        """Correlation ID should be available after entry."""
        correlation_id = uuid4()
        mock_emitter.emit_intent.return_value = correlation_id

        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        ) as execution:
            assert execution.correlation_id == correlation_id

    @pytest.mark.asyncio
    async def test_commit_uses_correlation_id(self, mock_emitter: AsyncMock) -> None:
        """Commit should use the correlation ID from intent."""
        correlation_id = uuid4()
        mock_emitter.emit_intent.return_value = correlation_id

        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        ) as execution:
            execution.set_result({"done": True})

        call_args = mock_emitter.emit_commit.call_args
        assert call_args.kwargs["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_failure_uses_correlation_id(self, mock_emitter: AsyncMock) -> None:
        """Failure should use the correlation ID from intent."""
        correlation_id = uuid4()
        mock_emitter.emit_intent.return_value = correlation_id

        with pytest.raises(ValueError):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise ValueError("error")

        call_args = mock_emitter.emit_failure.call_args
        assert call_args.kwargs["correlation_id"] == correlation_id


class TestIntentEmittedBeforeOperation:
    """Tests ensuring intent is emitted BEFORE operation starts (AC1)."""

    @pytest.mark.asyncio
    async def test_intent_emitted_before_body_executes(
        self, mock_emitter: AsyncMock
    ) -> None:
        """Intent should be emitted before context body runs."""
        call_order = []

        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        ):
            # Verify intent was already called
            assert mock_emitter.emit_intent.called
            call_order.append("body")

        call_order.append("exit")
        assert call_order == ["body", "exit"]

    @pytest.mark.asyncio
    async def test_intent_emitted_before_exception(
        self, mock_emitter: AsyncMock
    ) -> None:
        """Intent should be emitted even if body raises immediately."""
        with pytest.raises(RuntimeError):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                # Immediately raise
                raise RuntimeError("Immediate failure")

        # Intent was still emitted
        mock_emitter.emit_intent.assert_called_once()
        # And failure was recorded
        mock_emitter.emit_failure.assert_called_once()


class TestDefaultResultPayload:
    """Tests for default/empty result payload."""

    @pytest.mark.asyncio
    async def test_empty_result_if_not_set(self, mock_emitter: AsyncMock) -> None:
        """Commit should use empty dict if set_result not called."""
        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        ):
            pass  # Don't call set_result

        call_args = mock_emitter.emit_commit.call_args
        assert call_args.kwargs["result_payload"] == {}

    @pytest.mark.asyncio
    async def test_can_set_result_multiple_times(self, mock_emitter: AsyncMock) -> None:
        """Last set_result should be used for commit."""
        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        ) as execution:
            execution.set_result({"first": True})
            execution.set_result({"second": True})

        call_args = mock_emitter.emit_commit.call_args
        assert call_args.kwargs["result_payload"] == {"second": True}


class TestNestedExecution:
    """Tests for nested two-phase executions."""

    @pytest.mark.asyncio
    async def test_nested_executions_are_independent(
        self, mock_emitter: AsyncMock
    ) -> None:
        """Nested executions should have independent correlation IDs."""
        id1 = uuid4()
        id2 = uuid4()
        mock_emitter.emit_intent.side_effect = [id1, id2]

        async with (
            TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ) as outer,
            TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="judicial.panel.convene",
                actor_id="archon-42",
                target_entity_id="panel-001",
                intent_payload={},
            ) as inner,
        ):
            assert outer.correlation_id == id1
            assert inner.correlation_id == id2

        assert mock_emitter.emit_intent.call_count == 2
        assert mock_emitter.emit_commit.call_count == 2

    @pytest.mark.asyncio
    async def test_inner_failure_doesnt_affect_outer(
        self, mock_emitter: AsyncMock
    ) -> None:
        """Inner failure should not prevent outer commit."""
        mock_emitter.emit_intent.side_effect = [uuid4(), uuid4()]

        async with TwoPhaseExecution(
            emitter=mock_emitter,
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={},
        ):
            try:
                async with TwoPhaseExecution(
                    emitter=mock_emitter,
                    operation_type="judicial.panel.convene",
                    actor_id="archon-42",
                    target_entity_id="panel-001",
                    intent_payload={},
                ):
                    raise ValueError("Inner failure")
            except ValueError:
                pass  # Handle inner failure

        # Outer still commits, inner failed
        assert mock_emitter.emit_commit.call_count == 1
        assert mock_emitter.emit_failure.call_count == 1


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_handles_keyboard_interrupt(self, mock_emitter: AsyncMock) -> None:
        """KeyboardInterrupt should still emit failure."""
        with pytest.raises(KeyboardInterrupt):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise KeyboardInterrupt()

        mock_emitter.emit_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_system_exit(self, mock_emitter: AsyncMock) -> None:
        """SystemExit should still emit failure."""
        with pytest.raises(SystemExit):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise SystemExit(1)

        mock_emitter.emit_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_emitted_even_if_emit_fails(
        self, mock_emitter: AsyncMock
    ) -> None:
        """Original exception should propagate even if emit_failure fails."""
        mock_emitter.emit_failure.side_effect = RuntimeError("Emit failed")

        # Original exception should still propagate
        with pytest.raises(ValueError, match="original"):
            async with TwoPhaseExecution(
                emitter=mock_emitter,
                operation_type="executive.task.accept",
                actor_id="archon-42",
                target_entity_id="task-001",
                intent_payload={},
            ):
                raise ValueError("original error")
