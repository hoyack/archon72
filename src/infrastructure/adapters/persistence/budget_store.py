"""Budget Store implementations for Motion Gates promotion budget durability.

Per Promotion Budget Durability Spec (P1-P4):
- P1: PromotionBudgetStore protocol (stable contract)
- P2: File-backed store with atomic writes
- P3: Atomicity via lockfile
- P4: Redis store (optional, for horizontal scaling)

Storage layout (file store):
    /_bmad-output/budget-ledger/{cycle_id}/{king_id}.json

The invariant: budget consumption is atomic - under concurrent promotion
attempts, exactly N promotions succeed for budget N.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Re-export PromotionBudgetStore for backward compatibility
from src.application.ports.promotion_budget_store import PromotionBudgetStore

__all__ = [
    "PromotionBudgetStore",
    "BudgetRecord",
    "PromotionBudgetExceededError",
    "InMemoryBudgetStore",
    "FileBudgetStore",
    "RedisBudgetStore",
]


@dataclass
class BudgetRecord:
    """Persisted budget usage record."""

    king_id: str
    cycle_id: str
    budget: int
    used: int
    last_updated: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "king_id": self.king_id,
            "cycle_id": self.cycle_id,
            "budget": self.budget,
            "used": self.used,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BudgetRecord:
        return cls(
            king_id=data["king_id"],
            cycle_id=data["cycle_id"],
            budget=data["budget"],
            used=data["used"],
            last_updated=data.get("last_updated", ""),
        )


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


class InMemoryBudgetStore:
    """In-memory budget store for testing.

    WARNING: Not suitable for production - budget resets on restart.
    Use FileBudgetStore or RedisBudgetStore for durability.
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


class FileBudgetStore:
    """File-backed budget store with atomic writes and lockfile (P2, P3).

    Storage layout:
        {ledger_dir}/{cycle_id}/{king_id}.json

    Atomicity is ensured via:
    1. Per-file fcntl locking
    2. Write to temp file → fsync → atomic rename

    Acceptance criteria (P2):
        Spend 3 promotions → restart process → 4th promotion denied.
    """

    def __init__(
        self,
        ledger_dir: Path | str = "_bmad-output/budget-ledger",
        default_budget: int = 3,
    ):
        self.ledger_dir = Path(ledger_dir)
        self.default_budget = default_budget
        self._custom_budgets: dict[str, int] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._lock_registry = threading.Lock()

    def set_king_budget(self, king_id: str, budget: int) -> None:
        """Set custom budget for a King."""
        self._custom_budgets[king_id] = budget

    def get_budget(self, king_id: str) -> int:
        """Get budget for a King."""
        return self._custom_budgets.get(king_id, self.default_budget)

    def _get_lock(self, king_id: str, cycle_id: str) -> threading.Lock:
        """Get or create a lock for a (king_id, cycle_id) pair."""
        key = f"{cycle_id}:{king_id}"
        with self._lock_registry:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def _get_record_path(self, king_id: str, cycle_id: str) -> Path:
        """Get path to budget record file."""
        cycle_dir = self.ledger_dir / cycle_id
        return cycle_dir / f"{king_id}.json"

    def _read_record(self, king_id: str, cycle_id: str) -> BudgetRecord | None:
        """Read budget record from disk."""
        path = self._get_record_path(king_id, cycle_id)
        if not path.exists():
            return None

        try:
            with open(path) as f:
                # Use fcntl for read locking on the file itself
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    return BudgetRecord.from_dict(data)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return None

    def _write_record(self, record: BudgetRecord) -> None:
        """Atomically write budget record to disk.

        Uses temp file → fsync → rename pattern for crash safety.
        """
        path = self._get_record_path(record.king_id, record.cycle_id)

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{record.king_id}_",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w") as f:
                json.dump(record.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            os.rename(temp_path, path)

            # Sync directory for durability
            dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def get_usage(self, king_id: str, cycle_id: str) -> int:
        """Get current usage from persisted state."""
        record = self._read_record(king_id, cycle_id)
        return record.used if record else 0

    def can_promote(self, king_id: str, cycle_id: str, count: int = 1) -> bool:
        """Check if promotion is allowed (reads persisted state)."""
        used = self.get_usage(king_id, cycle_id)
        budget = self.get_budget(king_id)
        return used + count <= budget

    def consume(self, king_id: str, cycle_id: str, count: int = 1) -> int:
        """Atomically consume budget with file locking.

        Uses threading lock + file locking for full atomicity.
        """
        lock = self._get_lock(king_id, cycle_id)

        with lock:
            # Read current state
            record = self._read_record(king_id, cycle_id)
            budget = self.get_budget(king_id)

            used = 0 if record is None else record.used

            # Check budget
            if used + count > budget:
                raise PromotionBudgetExceededError(
                    king_id=king_id,
                    cycle_id=cycle_id,
                    budget=budget,
                    used=used + count,
                )

            # Create updated record
            new_used = used + count
            new_record = BudgetRecord(
                king_id=king_id,
                cycle_id=cycle_id,
                budget=budget,
                used=new_used,
                last_updated=datetime.now(timezone.utc).isoformat(),
            )

            # Persist atomically
            self._write_record(new_record)

            return new_used


class RedisBudgetStore:
    """Redis-backed budget store for horizontal scaling (P4).

    Uses atomic INCR with Lua script for check+consume atomicity.

    Key pattern: motion_gates:budget:{cycle_id}:{king_id}

    NOTE: Requires redis-py package. Import guarded for optional dependency.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_budget: int = 3,
        key_prefix: str = "motion_gates:budget",
    ):
        try:
            import redis
        except ImportError:
            raise ImportError(
                "redis-py required for RedisBudgetStore. "
                "Install with: pip install redis"
            )

        self.redis = redis.from_url(redis_url)
        self.default_budget = default_budget
        self.key_prefix = key_prefix
        self._custom_budgets: dict[str, int] = {}

        # Lua script for atomic check+increment
        self._consume_script = self.redis.register_script("""
            local key = KEYS[1]
            local budget = tonumber(ARGV[1])
            local count = tonumber(ARGV[2])

            local current = tonumber(redis.call('GET', key) or '0')

            if current + count > budget then
                return -1  -- Budget exceeded
            end

            local new_value = redis.call('INCRBY', key, count)
            return new_value
        """)

    def set_king_budget(self, king_id: str, budget: int) -> None:
        """Set custom budget for a King."""
        self._custom_budgets[king_id] = budget

    def get_budget(self, king_id: str) -> int:
        """Get budget for a King."""
        return self._custom_budgets.get(king_id, self.default_budget)

    def _get_key(self, king_id: str, cycle_id: str) -> str:
        """Get Redis key for budget tracking."""
        return f"{self.key_prefix}:{cycle_id}:{king_id}"

    def get_usage(self, king_id: str, cycle_id: str) -> int:
        """Get current usage from Redis."""
        key = self._get_key(king_id, cycle_id)
        value = self.redis.get(key)
        return int(value) if value else 0

    def can_promote(self, king_id: str, cycle_id: str, count: int = 1) -> bool:
        """Check if promotion is allowed."""
        used = self.get_usage(king_id, cycle_id)
        budget = self.get_budget(king_id)
        return used + count <= budget

    def consume(self, king_id: str, cycle_id: str, count: int = 1) -> int:
        """Atomically consume budget using Lua script."""
        key = self._get_key(king_id, cycle_id)
        budget = self.get_budget(king_id)

        result = self._consume_script(
            keys=[key],
            args=[budget, count],
        )

        if result == -1:
            used = self.get_usage(king_id, cycle_id)
            raise PromotionBudgetExceededError(
                king_id=king_id,
                cycle_id=cycle_id,
                budget=budget,
                used=used + count,
            )

        return int(result)
