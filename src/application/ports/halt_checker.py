"""Halt Checker port - interface for halt state checking (Story 1.6, Task 2).

This is a STUB interface for Epic 1 that will be fully implemented in Epic 3.
The Writer must check halt state before every write (HALT FIRST rule).

Constitutional Constraint (CT-11):
Silent failure destroys legitimacy. Halt is integrity protection,
not transient failure. NEVER retry after SystemHaltedError.

ADR-3: Partition Behavior + Halt Durability
- Dual-channel halt (Redis + DB flag)
- Sticky halt semantics
- 48-hour recovery waiting period

TODO: Epic 3 (Story 3.1 - Story 3.4) will implement:
- Dual-channel halt transport
- Halt reason tracking
- Recovery waiting period
- Witnessed halt events
"""

from abc import ABC, abstractmethod


class HaltChecker(ABC):
    """Abstract interface for halt state checking.

    Developer Golden Rule: HALT FIRST
    Always check halt state before any write operation.

    Epic 3 will implement the real HaltChecker with:
    - Dual-channel halt (Redis + DB flag) per ADR-3
    - Halt reason tracking with attribution
    - 48-hour recovery waiting period
    - Sticky halt semantics (once halted, stays halted)

    For Epic 1, use HaltCheckerStub which always returns False.
    This allows the Writer service to be developed without
    depending on Epic 3 infrastructure.
    """

    @abstractmethod
    async def is_halted(self) -> bool:
        """Check if the system is halted.

        This method MUST be called before every write operation.
        If halted, raise SystemHaltedError and do NOT retry.

        Returns:
            True if system is halted, False otherwise.
        """
        ...

    @abstractmethod
    async def get_halt_reason(self) -> str | None:
        """Get the reason for the current halt.

        Returns:
            Halt reason string if halted, None otherwise.
            Reason should include attribution (who triggered halt).
        """
        ...
