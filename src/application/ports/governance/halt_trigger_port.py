"""Halt Trigger Port - Abstract interface for triggering system halts.

This port defines the contract for triggering system halts with proper
authorization, event emission, and execution coordination.

Story: consent-gov-4.2: Halt Trigger & Execution

Constitutional Context:
- FR22: Human Operator can trigger system halt
- FR23: System can execute halt operation
- NFR-PERF-01: Halt completes in ≤100ms
- NFR-REL-01: Dedicated execution path for halt

The HaltTriggerPort orchestrates:
1. Authorization check (only authorized operators can halt)
2. Two-phase event emission (intent → commit/failure)
3. Halt circuit execution via HaltPort
4. Execution confirmation

Authorized Actors:
- Human Operators (designated role with halt_system permission)
- System (automatic fault detection)
- Knight (integrity violation detection)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.halt import HaltReason, HaltStatus


@dataclass(frozen=True)
class HaltExecutionResult:
    """Result of halt execution.

    Attributes:
        success: Whether halt was established.
        status: Full HaltStatus with context.
        triggered_at: When halt was triggered.
        executed_at: When halt execution completed.
        execution_ms: Time to execute halt in milliseconds.
        channels_reached: Which channels successfully propagated halt.
        operator_id: ID of operator who triggered halt.
    """

    success: bool
    status: HaltStatus
    triggered_at: datetime
    executed_at: datetime
    execution_ms: float
    channels_reached: list[str]
    operator_id: UUID | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for event payload."""
        return {
            "success": self.success,
            "triggered_at": self.triggered_at.isoformat(),
            "executed_at": self.executed_at.isoformat(),
            "execution_ms": self.execution_ms,
            "channels_reached": self.channels_reached,
            "operator_id": str(self.operator_id) if self.operator_id else None,
            "reason": self.status.reason.value if self.status.reason else None,
            "message": self.status.message,
        }


class UnauthorizedHaltError(Exception):
    """Raised when an unauthorized actor attempts to trigger halt.

    Per FR22: Only authorized operators can trigger halt.
    Unauthorized attempts are logged and rejected.

    Attributes:
        actor_id: ID of actor who attempted halt.
        reason: Why the attempt was denied.
    """

    def __init__(self, actor_id: UUID, reason: str) -> None:
        self.actor_id = actor_id
        self.reason = reason
        super().__init__(f"Unauthorized halt attempt by {actor_id}: {reason}")


class HaltMessageRequiredError(Exception):
    """Raised when halt message is missing or empty.

    Per AC7: Halt reason and message are required.
    """

    def __init__(self) -> None:
        super().__init__("Halt message is required and cannot be empty")


class HaltTriggerPort(ABC):
    """Abstract interface for triggering system halts.

    This port orchestrates the halt trigger flow:
    1. Verify operator authorization
    2. Emit constitutional.halt.triggered event
    3. Execute halt through HaltPort
    4. Emit constitutional.halt.executed event

    Thread Safety:
        - trigger_halt() is async and uses proper locking
        - Multiple concurrent triggers are serialized

    Performance:
        - Must complete in ≤100ms (NFR-PERF-01)

    Example:
        >>> halt_trigger = get_halt_trigger()
        >>> result = await halt_trigger.trigger_halt(
        ...     operator_id=operator.id,
        ...     reason=HaltReason.OPERATOR,
        ...     message="Emergency maintenance required",
        ... )
        >>> if result.success:
        ...     print(f"Halt established in {result.execution_ms}ms")
    """

    @abstractmethod
    async def trigger_halt(
        self,
        operator_id: UUID,
        reason: HaltReason,
        message: str,
        trace_id: str | None = None,
    ) -> HaltExecutionResult:
        """Trigger system halt.

        Must be called by an authorized operator. This method:
        1. Verifies operator has halt_system permission
        2. Emits constitutional.halt.triggered event
        3. Executes halt through all three channels
        4. Emits constitutional.halt.executed event

        Args:
            operator_id: ID of operator triggering halt.
            reason: Why the system is being halted.
            message: Human-readable description (required).
            trace_id: Optional trace ID for correlation.

        Returns:
            HaltExecutionResult with execution details.

        Raises:
            UnauthorizedHaltError: If operator lacks halt_system permission.
            HaltMessageRequiredError: If message is empty.

        Performance:
            MUST complete in ≤100ms (NFR-PERF-01).
        """
        ...

    @abstractmethod
    async def trigger_system_halt(
        self,
        reason: HaltReason,
        message: str,
        trace_id: str | None = None,
    ) -> HaltExecutionResult:
        """Trigger halt as system (no operator authorization required).

        Used for automatic fault detection and integrity violations.
        Does NOT require operator authorization.

        Args:
            reason: Why the system is being halted.
            message: Human-readable description (required).
            trace_id: Optional trace ID for correlation.

        Returns:
            HaltExecutionResult with execution details.

        Raises:
            HaltMessageRequiredError: If message is empty.
        """
        ...

    @abstractmethod
    async def is_authorized_to_halt(self, actor_id: UUID) -> bool:
        """Check if an actor is authorized to trigger halt.

        Args:
            actor_id: ID of actor to check.

        Returns:
            True if authorized, False otherwise.
        """
        ...
