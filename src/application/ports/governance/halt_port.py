"""Halt Port - Abstract interface for three-channel halt circuit.

This port defines the contract for the emergency safety halt circuit.
Implementations must provide a three-channel design:
1. Primary (In-Memory): Fast, synchronous, no dependencies
2. Secondary (Redis): Cross-instance propagation
3. Tertiary (Ledger): Permanent audit record

Constitutional Context:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-13: Integrity outranks availability → Halt preserves integrity
- NFR-PERF-01: Halt completes in ≤100ms
- NFR-REL-01: Primary halt works without external dependencies
- AC5: Primary halt works even if Redis/DB unavailable

Story: consent-gov-4.1 (Halt Circuit Port & Adapter)
Requirements: FR22-FR27, NFR-PERF-01, NFR-REL-01, NFR-ATOMIC-01
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, TypeVar
from uuid import UUID

from src.domain.governance.halt import HaltedException, HaltReason, HaltStatus

T = TypeVar("T")


class HaltPort(ABC):
    """Abstract interface for halt circuit operations.

    The halt circuit is the emergency safety mechanism that stops
    all governance operations when triggered. It uses a three-channel
    design to ensure halts propagate reliably even when infrastructure fails.

    Performance Requirements:
        - is_halted(): MUST complete in <1ms (in-memory only)
        - trigger_halt(): MUST complete in ≤100ms

    Reliability Requirements:
        - Primary halt MUST work even if Redis/DB unavailable
        - Halt flag MUST be checked before EVERY I/O operation

    Example Usage:
        >>> halt_port = get_halt_port()
        >>> if halt_port.is_halted():
        ...     raise HaltedException(halt_port.get_halt_status())
        >>> # Proceed with operation...

    Three-Channel Design:
        Primary (In-Memory):
            - Process-local atomic flag
            - No external dependencies
            - Checked synchronously (no async)
            - This ALWAYS works

        Secondary (Redis):
            - Propagates halt to other instances
            - Async broadcast
            - Failure is tolerated (primary still works)

        Tertiary (Ledger):
            - Permanent record for audit
            - Best-effort, AFTER halt is established
            - Failure does NOT block halt
    """

    @abstractmethod
    def is_halted(self) -> bool:
        """Check if system is halted.

        This method MUST be:
        - Fast (<1ms) - uses in-memory primary channel only
        - Synchronous - no async/await
        - Called before EVERY I/O operation

        Returns:
            True if system is halted, False otherwise.

        Performance:
            MUST complete in <1ms. Uses only in-memory flag.
        """
        ...

    @abstractmethod
    async def trigger_halt(
        self,
        reason: HaltReason,
        message: str,
        operator_id: Optional[UUID] = None,
        trace_id: Optional[str] = None,
    ) -> HaltStatus:
        """Trigger system halt.

        Propagates halt through all three channels:
        1. Primary: Set in-memory flag (instant)
        2. Secondary: Publish to Redis (best-effort)
        3. Tertiary: Record to ledger (best-effort)

        Args:
            reason: Why the system is being halted.
            message: Human-readable description of the halt.
            operator_id: ID of operator triggering halt (None if system).
            trace_id: Trace ID for audit correlation.

        Returns:
            HaltStatus with full halt context.

        Performance:
            MUST complete in ≤100ms (NFR-PERF-01).

        Reliability:
            Primary halt MUST succeed even if Redis/DB unavailable.
            Secondary/tertiary failures are logged but do not block.
        """
        ...

    @abstractmethod
    def get_halt_status(self) -> HaltStatus:
        """Get current halt status with full details.

        Returns:
            HaltStatus with is_halted, reason, message, timestamp, etc.
        """
        ...

    def check_or_raise(self) -> None:
        """Check if halted and raise HaltedException if so.

        Convenience method for services to check halt status
        before performing operations.

        Raises:
            HaltedException: If system is halted.
        """
        if self.is_halted():
            raise HaltedException(self.get_halt_status())


class HaltChecker:
    """Utility for checking halt status before operations.

    This utility wraps a HaltPort and provides convenient methods
    for checking halt status. It should be injected into all services
    that perform I/O operations.

    AC6: Halt flag checked before every I/O operation.

    Example Usage:
        >>> class TaskActivationService:
        ...     def __init__(self, halt_checker: HaltChecker) -> None:
        ...         self._halt = halt_checker
        ...
        ...     async def create_activation(self, ...) -> ...:
        ...         self._halt.check_or_raise()  # Check BEFORE any operation
        ...         # ... proceed with activation
    """

    def __init__(self, halt_port: HaltPort) -> None:
        """Initialize HaltChecker with halt port.

        Args:
            halt_port: Port for halt circuit operations.
        """
        self._halt_port = halt_port

    def is_halted(self) -> bool:
        """Check if system is halted.

        Returns:
            True if halted, False otherwise.
        """
        return self._halt_port.is_halted()

    def check_or_raise(self) -> None:
        """Check if halted and raise HaltedException if so.

        This method should be called at the START of every
        service method that performs I/O operations.

        Raises:
            HaltedException: If system is halted.
        """
        self._halt_port.check_or_raise()

    def get_status(self) -> HaltStatus:
        """Get current halt status with full details.

        Returns:
            HaltStatus with full context.
        """
        return self._halt_port.get_halt_status()

    def wrap_sync(self, operation: Callable[..., T]) -> Callable[..., T]:
        """Decorator to check halt before synchronous operation.

        Args:
            operation: Function to wrap.

        Returns:
            Wrapped function that checks halt first.

        Example:
            >>> @halt_checker.wrap_sync
            ... def my_operation(...):
            ...     # Will raise HaltedException if halted
            ...     ...
        """

        def wrapper(*args, **kwargs) -> T:
            self.check_or_raise()
            return operation(*args, **kwargs)

        return wrapper
