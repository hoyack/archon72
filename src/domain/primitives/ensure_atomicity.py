"""Constitutional primitive: Ensure atomic operations (FR81).

This module provides an async context manager that ensures atomic operations
with rollback capability. If an exception occurs within the context, all
registered rollback handlers are executed before the exception is re-raised.

Constitutional Constraint (FR81):
    All constitutional operations must be atomic - complete success
    or complete rollback, never partial state.

Constitutional Truths Honored:
    - CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
    - CT-13: Integrity outranks availability

Usage:
    async with AtomicOperationContext() as ctx:
        ctx.add_rollback(cleanup_function)
        await do_operation()
        # On exception: cleanup_function called, exception re-raised
"""

import asyncio
import inspect
from collections.abc import Callable, Coroutine
from types import TracebackType
from typing import Any

import structlog

log = structlog.get_logger()

# Type alias for rollback handlers - can be sync or async
RollbackHandler = Callable[[], None] | Callable[[], Coroutine[Any, Any, None]]


class AtomicOperationContext:
    """Context manager ensuring atomic operations with rollback.

    Constitutional Constraint (FR81):
    All constitutional operations must be atomic - complete success
    or complete rollback, never partial state.

    This context manager allows registering rollback handlers that will
    be called in reverse order (LIFO) if an exception occurs. After all
    rollback handlers have been executed, the original exception is re-raised.

    Supports both synchronous and asynchronous rollback handlers.

    Example:
        >>> async def example():
        ...     async with AtomicOperationContext() as ctx:
        ...         ctx.add_rollback(lambda: print("Rolling back"))
        ...         # Do some operation
        ...         raise ValueError("Something went wrong")
        # Output: Rolling back
        # Then ValueError is re-raised

    Attributes:
        _rollback_handlers: List of registered rollback handlers (LIFO order)
    """

    def __init__(self) -> None:
        """Initialize the atomic operation context."""
        self._rollback_handlers: list[RollbackHandler] = []

    def add_rollback(self, handler: RollbackHandler) -> None:
        """Register a rollback handler to be called on failure.

        Handlers are called in reverse order (LIFO) - the last handler
        added is the first to be called during rollback.

        Args:
            handler: A callable (sync or async) that performs cleanup.
                     Must take no arguments.
        """
        self._rollback_handlers.append(handler)

    async def __aenter__(self) -> "AtomicOperationContext":
        """Enter the async context.

        Returns:
            Self, to allow adding rollback handlers.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the async context, executing rollbacks on exception.

        If an exception occurred (exc_val is not None), executes all
        registered rollback handlers in reverse order. Any exceptions
        from rollback handlers are logged but do not prevent other
        rollback handlers from running.

        Args:
            exc_type: The exception type, if an exception was raised.
            exc_val: The exception instance, if an exception was raised.
            exc_tb: The traceback, if an exception was raised.

        Returns:
            False - always re-raises the original exception if one occurred.
        """
        if exc_val is not None:
            # Execute rollback handlers in reverse order (LIFO)
            log.info(
                "atomic_operation_failed",
                error=str(exc_val),
                error_type=exc_type.__name__ if exc_type else "Unknown",
                rollback_count=len(self._rollback_handlers),
            )

            for handler in reversed(self._rollback_handlers):
                try:
                    # Check if handler is async using inspect
                    if asyncio.iscoroutinefunction(handler) or (
                        inspect.ismethod(handler)
                        and asyncio.iscoroutinefunction(handler.__func__)
                    ):
                        await handler()
                    else:
                        # Sync handler - call directly
                        result = handler()
                        # Handle case where sync function returns a coroutine
                        if asyncio.iscoroutine(result):
                            await result
                except Exception as rollback_error:
                    # Log rollback errors but continue with other handlers
                    log.error(
                        "rollback_handler_failed",
                        rollback_error=str(rollback_error),
                        rollback_error_type=type(rollback_error).__name__,
                    )

            # Re-raise the original exception
            return False

        # No exception - nothing to do
        return False
