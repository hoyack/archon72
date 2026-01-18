"""TwoPhaseExecution async context manager.

Story: consent-gov-1.6: Two-Phase Event Emission

This context manager encapsulates the two-phase event emission pattern
for automatic intent/outcome handling. It guarantees:

1. Intent is ALWAYS emitted before operation begins
2. Commit is emitted on successful exit
3. Failure is emitted on exception

Constitutional Guarantees:
- Intent is ALWAYS emitted before operation begins
- Outcome (commit/failure) is ALWAYS emitted after operation
- No orphaned intents - automatic resolution on exception

References:
- AD-3: Two-phase event emission
- AC5: No orphaned intents allowed
- AC9: TwoPhaseEventEmitter service encapsulates the two-phase pattern
- NFR-CONST-07: Witness statements cannot be suppressed
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from types import TracebackType

    from src.application.ports.governance.two_phase_emitter_port import (
        TwoPhaseEventEmitterPort,
    )


class TwoPhaseExecution:
    """Async context manager for two-phase event emission.

    Guarantees the two-phase emission pattern:
    - Intent emitted on __aenter__ (BEFORE operation begins)
    - Commit emitted on successful __aexit__ (when no exception)
    - Failure emitted on exception in __aexit__

    Usage:
        async with TwoPhaseExecution(
            emitter=two_phase_emitter,
            operation_type="task.accept",
            actor_id=actor_id,
            target_entity_id=task_id,
            intent_payload={"earl_id": earl_id},
        ) as execution:
            # Intent already emitted at this point
            # Knight can observe intent immediately

            result = await perform_task_acceptance(task_id)
            execution.set_result({"new_state": result.state})

        # Commit emitted automatically on successful exit
        # Failure emitted automatically on exception

    Attributes:
        correlation_id: The correlation ID linking intent to outcome.
                       Available after __aenter__ returns.

    Example with error handling:
        try:
            async with TwoPhaseExecution(...) as execution:
                result = await risky_operation()
                execution.set_result(result)
        except OperationError as e:
            # Failure already emitted automatically
            logger.error(f"Operation failed: {e}")
            # Handle cleanup
    """

    def __init__(
        self,
        emitter: TwoPhaseEventEmitterPort,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict[str, Any],
    ) -> None:
        """Initialize the TwoPhaseExecution context manager.

        Args:
            emitter: The TwoPhaseEventEmitter for emitting events.
            operation_type: The type of operation being performed.
            actor_id: The actor performing the operation.
            target_entity_id: The target entity of the operation.
            intent_payload: Additional data for the intent event.
        """
        self._emitter = emitter
        self._operation_type = operation_type
        self._actor_id = actor_id
        self._target_entity_id = target_entity_id
        self._intent_payload = intent_payload
        self._correlation_id: UUID | None = None
        self._result_payload: dict[str, Any] = {}

    async def __aenter__(self) -> TwoPhaseExecution:
        """Enter the context and emit intent event.

        This emits the intent event BEFORE the operation body executes,
        ensuring Knight observers can see the intent immediately.

        Returns:
            Self for use in the context body.
        """
        self._correlation_id = await self._emitter.emit_intent(
            operation_type=self._operation_type,
            actor_id=self._actor_id,
            target_entity_id=self._target_entity_id,
            intent_payload=self._intent_payload,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the context and emit outcome event.

        Emits commit on success, failure on exception.

        Args:
            exc_type: Exception type if exception occurred.
            exc_val: Exception value if exception occurred.
            exc_tb: Exception traceback if exception occurred.

        Returns:
            False to allow exceptions to propagate.
        """
        if exc_type is None:
            # Success path - emit commit
            await self._emitter.emit_commit(
                correlation_id=self._correlation_id,
                result_payload=self._result_payload,
            )
        else:
            # Failure path - emit failure
            try:
                await self._emitter.emit_failure(
                    correlation_id=self._correlation_id,
                    failure_reason=str(exc_val),
                    failure_details={
                        "exception_type": exc_type.__name__,
                        "exception_message": str(exc_val),
                    },
                )
            except Exception:
                # If emit_failure itself fails, we still propagate the original exception
                pass

        # Never suppress exceptions
        return False

    def set_result(self, result_payload: dict[str, Any]) -> None:
        """Set the result payload for the commit event.

        Call this in the context body to set the result data that
        will be included in the commit event on successful exit.

        Args:
            result_payload: The result data to include in commit.
        """
        self._result_payload = result_payload

    @property
    def correlation_id(self) -> UUID:
        """Get the correlation ID for this execution.

        The correlation ID links the intent to its outcome (commit/failure).

        Returns:
            The correlation ID assigned during __aenter__.

        Raises:
            RuntimeError: If accessed before context entry.
        """
        if self._correlation_id is None:
            raise RuntimeError(
                "correlation_id is not available before context entry. "
                "Use 'async with TwoPhaseExecution(...) as execution:' to access."
            )
        return self._correlation_id
