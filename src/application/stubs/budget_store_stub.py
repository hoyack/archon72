"""In-memory promotion budget store for application-level testing."""

from __future__ import annotations

import threading

from src.application.ports.promotion_budget_store import PromotionBudgetStore


class PromotionBudgetExceededError(Exception):
    """Raised when promotion budget is exceeded."""

    def __init__(self, king_id: str, cycle_id: str, budget: int, used: int):
        self.king_id = king_id
        self.cycle_id = cycle_id
        self.budget = budget
        self.used = used
        super().__init__(
            f"King {king_id} budget exceeded for cycle {cycle_id}: used {used}/{budget}"
        )


class InMemoryBudgetStore(PromotionBudgetStore):
    """In-memory budget store for testing.

    WARNING: Not suitable for production - budget resets on restart.
    """

    def __init__(self, default_budget: int = 3):
        self.default_budget = default_budget
        self._custom_budgets: dict[str, int] = {}
        self._usage: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def set_king_budget(self, king_id: str, budget: int) -> None:
        """Set custom budget for a King."""
        self._custom_budgets[king_id] = budget

    def get_budget(self, king_id: str) -> int:
        """Get budget for a King."""
        return self._custom_budgets.get(king_id, self.default_budget)

    def get_usage(self, king_id: str, cycle_id: str) -> int:
        """Get current usage."""
        return self._usage.get((king_id, cycle_id), 0)

    def can_promote(self, king_id: str, cycle_id: str, count: int = 1) -> bool:
        """Check if promotion is allowed."""
        with self._lock:
            used = self.get_usage(king_id, cycle_id)
            budget = self.get_budget(king_id)
            return used + count <= budget

    def consume(self, king_id: str, cycle_id: str, count: int = 1) -> int:
        """Atomically consume budget."""
        with self._lock:
            used = self.get_usage(king_id, cycle_id)
            budget = self.get_budget(king_id)

            if used + count > budget:
                raise PromotionBudgetExceededError(
                    king_id=king_id,
                    cycle_id=cycle_id,
                    budget=budget,
                    used=used + count,
                )

            new_used = used + count
            self._usage[(king_id, cycle_id)] = new_used
            return new_used


__all__ = [
    "InMemoryBudgetStore",
    "PromotionBudgetExceededError",
    "PromotionBudgetStore",
]
