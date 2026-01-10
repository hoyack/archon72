"""Halt Flag Repository adapter (Story 3.3, Task 2; Story 3.4 for protected clear).

Provides infrastructure adapter for durable halt state storage.
This is the DB channel of the dual-channel halt transport.

ADR-3: Partition Behavior + Halt Durability
- DB halt flag is the canonical source of truth
- If Redis is down, DB halt flag is authoritative
- Singleton pattern: only one halt state row exists
- Halt is **sticky** - clearing requires witnessed ceremony (Story 3.4)

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> DB errors MUST be logged
- CT-12: Witnessing creates accountability -> crisis_event_id links to trigger
- CT-13: Integrity outranks availability -> DB is canonical

Developer Golden Rule: DB IS CANONICAL
- When Redis and DB disagree, trust DB
- CEREMONY IS KING - No backdoors for clearing halt
"""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.application.ports.dual_channel_halt import HaltFlagState
from src.domain.errors.halt_clear import HaltClearDeniedError


class HaltFlagRepository(ABC):
    """Abstract interface for halt flag persistence.

    This interface defines the contract for storing and retrieving
    the halt state from a durable storage (typically PostgreSQL).

    Implementations:
    - InMemoryHaltFlagRepository: For testing/development
    - PostgresHaltFlagRepository: For production (uses SQLAlchemy)
    """

    @abstractmethod
    async def get_halt_flag(self) -> HaltFlagState:
        """Get the current halt flag state.

        Returns:
            HaltFlagState with current halt information.
        """
        ...

    @abstractmethod
    async def set_halt_flag(
        self,
        halted: bool,
        reason: Optional[str],
        crisis_event_id: Optional[UUID],
        ceremony_id: Optional[UUID] = None,
    ) -> None:
        """Set the halt flag state.

        This is an atomic upsert operation on the singleton halt state row.

        Args:
            halted: Whether the system is halted.
            reason: Human-readable reason for the halt (required when halted=True).
            crisis_event_id: UUID of the triggering crisis event.
            ceremony_id: UUID of clearing ceremony (required when halted=False
                        and currently halted). Story 3.4, ADR-3.

        Note:
            In production, clearing halt (halted=False) requires a witnessed
            ceremony (Story 3.4). Without ceremony_id, clear attempts are rejected
            with HaltClearDeniedError.
        """
        ...

    @abstractmethod
    async def clear_halt_with_ceremony(
        self,
        ceremony_id: UUID,
        reason: str,
    ) -> None:
        """Clear halt flag using ceremony authorization (Story 3.4, ADR-3).

        This is the ONLY authorized way to clear the halt flag.
        The ceremony_id provides audit trail linking to the witnessed
        HaltClearedEvent that authorized this clear.

        Constitutional Constraints:
        - ADR-3: Halt is sticky - clearing requires witnessed ceremony
        - CT-12: Witnessing creates accountability

        Args:
            ceremony_id: UUID of the clearing ceremony (REQUIRED).
            reason: Human-readable reason for clearing (e.g., "Recovery ceremony completed").

        Raises:
            HaltClearDeniedError: If ceremony_id is None.
        """
        ...


class InMemoryHaltFlagRepository(HaltFlagRepository):
    """In-memory halt flag repository for testing and development.

    NOT FOR PRODUCTION USE. State is stored in memory and will be
    lost when the process exits.

    This implementation maintains the same semantics as the PostgreSQL
    implementation, including:
    - Singleton pattern (only one halt state)
    - Atomic upsert operations
    - Immutable HaltFlagState return values
    """

    def __init__(self) -> None:
        """Initialize with not-halted state."""
        self._state = HaltFlagState(
            is_halted=False,
            reason=None,
            crisis_event_id=None,
        )

    async def get_halt_flag(self) -> HaltFlagState:
        """Get the current halt flag state.

        Returns:
            HaltFlagState with current halt information.
        """
        return self._state

    async def set_halt_flag(
        self,
        halted: bool,
        reason: Optional[str],
        crisis_event_id: Optional[UUID],
        ceremony_id: Optional[UUID] = None,
    ) -> None:
        """Set the halt flag state.

        Args:
            halted: Whether the system is halted.
            reason: Human-readable reason for the halt.
            crisis_event_id: UUID of the triggering crisis event.
            ceremony_id: UUID of clearing ceremony (required when clearing halt).

        Raises:
            HaltClearDeniedError: If attempting to clear halt without ceremony_id.
        """
        # ADR-3: Halt is sticky - clearing requires ceremony
        if self._state.is_halted and not halted:
            if ceremony_id is None:
                raise HaltClearDeniedError(
                    "ADR-3: Halt flag protected - ceremony required"
                )

        self._state = HaltFlagState(
            is_halted=halted,
            reason=reason,
            crisis_event_id=crisis_event_id,
        )

    async def clear_halt_with_ceremony(
        self,
        ceremony_id: UUID,
        reason: str,
    ) -> None:
        """Clear halt flag using ceremony authorization.

        Args:
            ceremony_id: UUID of the clearing ceremony.
            reason: Human-readable reason for clearing.

        Raises:
            HaltClearDeniedError: If ceremony_id is None.
        """
        if ceremony_id is None:
            raise HaltClearDeniedError(
                "ADR-3: Halt flag protected - ceremony required"
            )

        self._state = HaltFlagState(
            is_halted=False,
            reason=reason,
            crisis_event_id=None,
        )

    def clear_for_testing(self) -> None:
        """Reset to initial state (for testing only).

        WARNING: This bypasses ceremony requirements and should only
        be used in test fixtures. Named explicitly to indicate
        this is NOT for production use.
        """
        self._state = HaltFlagState(
            is_halted=False,
            reason=None,
            crisis_event_id=None,
        )
