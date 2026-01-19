"""In-memory budget store stub for testing.

Provides a simple in-memory implementation of PromotionBudgetStore
for use in tests and development. Not suitable for production.
"""

from src.infrastructure.adapters.persistence.budget_store import InMemoryBudgetStore

__all__ = ["InMemoryBudgetStore"]
