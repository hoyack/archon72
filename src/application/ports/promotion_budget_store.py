"""Promotion Budget Store port definition.

Defines the abstract interface for King promotion budget storage.
Infrastructure adapters must implement this protocol.

Per Promotion Budget Durability Spec (P1-P4):
- P1: PromotionBudgetStore protocol (stable contract)
- P2: File-backed store with atomic writes
- P3: Atomicity via lockfile
- P4: Redis store (optional, for horizontal scaling)

Constitutional Constraints:
- H1: Kings have limited promotion budget per cycle
- Growth equation: O(kings × promotion_budget) = 27 max motions/cycle

The invariant: budget consumption is atomic - under concurrent promotion
attempts, exactly N promotions succeed for budget N.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PromotionBudgetStore(Protocol):
    """Protocol for promotion budget storage (P1).

    All implementations must provide atomic check+consume semantics.
    """

    def can_promote(self, king_id: str, cycle_id: str, count: int = 1) -> bool:
        """Check if a King can promote within their budget.

        Args:
            king_id: The King's archon ID.
            cycle_id: The cycle identifier.
            count: Number of promotions to check.

        Returns:
            True if the King has sufficient budget remaining.
        """
        ...

    def consume(self, king_id: str, cycle_id: str, count: int = 1) -> int:
        """Atomically consume promotion budget.

        This must be atomic: concurrent calls must not exceed budget.

        Args:
            king_id: The King's archon ID.
            cycle_id: The cycle identifier.
            count: Number of promotions to consume.

        Returns:
            New total used count after consumption.

        Raises:
            PromotionBudgetExceededError: If budget would be exceeded.
        """
        ...

    def get_usage(self, king_id: str, cycle_id: str) -> int:
        """Get current usage count for a King in a cycle.

        Args:
            king_id: The King's archon ID.
            cycle_id: The cycle identifier.

        Returns:
            Number of promotions already consumed.
        """
        ...

    def get_budget(self, king_id: str) -> int:
        """Get the promotion budget for a King.

        Args:
            king_id: The King's archon ID.

        Returns:
            The King's promotion budget.
        """
        ...
