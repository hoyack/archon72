"""Witness pair history stub for development and testing (FR60).

Provides in-memory pair history tracking for testing witness selection.

WARNING: This stub is NOT for production use.
Production implementations should use persistent storage
(Redis or database) for pair history.

Constitutional Constraints:
- FR60: No witness pair SHALL appear consecutively more than once per 24-hour period
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.application.ports.witness_pair_history import WitnessPairHistoryProtocol
from src.domain.models.witness_pair import ROTATION_WINDOW_HOURS, WitnessPair


class InMemoryWitnessPairHistory(WitnessPairHistoryProtocol):
    """In-memory implementation of WitnessPairHistoryProtocol for testing.

    Provides pair rotation tracking in memory for testing witness
    selection behavior without external dependencies.

    WARNING: This implementation loses data on restart and
    should NEVER be used in production environments.

    Features:
    - In-memory storage with automatic pruning
    - Manual time control for testing edge cases
    - Clear method for test isolation

    Example:
        history = InMemoryWitnessPairHistory()

        pair = WitnessPair(
            witness_a_id="WITNESS:abc",
            witness_b_id="WITNESS:xyz",
        )

        # First appearance - not in history
        appeared = await history.has_appeared_in_24h(pair)  # False

        # Record the pair
        await history.record_pair(pair)

        # Now it's in history
        appeared = await history.has_appeared_in_24h(pair)  # True
    """

    def __init__(self) -> None:
        """Initialize empty pair history."""
        self._pairs: dict[str, datetime] = {}

    async def has_appeared_in_24h(self, pair: WitnessPair) -> bool:
        """Check if pair has appeared in last 24 hours (FR60).

        Args:
            pair: The witness pair to check.

        Returns:
            True if pair appeared within rotation window, False otherwise.
        """
        key = pair.canonical_key()
        if key not in self._pairs:
            return False

        last_time = self._pairs[key]
        now = datetime.now(timezone.utc)
        window = timedelta(hours=ROTATION_WINDOW_HOURS)

        return (now - last_time) < window

    async def record_pair(self, pair: WitnessPair) -> None:
        """Record a new pair appearance.

        Args:
            pair: The witness pair to record.
        """
        key = pair.canonical_key()
        self._pairs[key] = pair.paired_at

    async def get_pair_last_appearance(self, pair_key: str) -> datetime | None:
        """Get the last appearance time for a pair.

        Args:
            pair_key: The canonical pair key.

        Returns:
            The datetime of last appearance, or None if never recorded.
        """
        return self._pairs.get(pair_key)

    async def prune_old_pairs(self) -> int:
        """Remove pairs older than the rotation window.

        Returns:
            Number of pairs removed.
        """
        now = datetime.now(timezone.utc)
        window = timedelta(hours=ROTATION_WINDOW_HOURS)
        cutoff = now - window

        old_keys = [key for key, timestamp in self._pairs.items() if timestamp < cutoff]

        for key in old_keys:
            del self._pairs[key]

        return len(old_keys)

    async def count_tracked_pairs(self) -> int:
        """Get the number of currently tracked pairs.

        Returns:
            The count of pairs in history.
        """
        return len(self._pairs)

    # Test control methods

    def clear(self) -> None:
        """Clear all pair history.

        Use this between tests to ensure isolation.
        """
        self._pairs.clear()

    def inject_pair(
        self,
        pair_key: str,
        timestamp: datetime,
    ) -> None:
        """Inject a pair directly for testing.

        Allows setting up specific test scenarios with
        controlled timestamps.

        Args:
            pair_key: The canonical pair key
            timestamp: The timestamp to record
        """
        self._pairs[pair_key] = timestamp

    def get_all_pairs(self) -> dict[str, datetime]:
        """Get all tracked pairs for test assertions.

        Returns:
            Copy of internal pairs dictionary.
        """
        return dict(self._pairs)

    @property
    def pair_count(self) -> int:
        """Get current pair count (sync, for test assertions)."""
        return len(self._pairs)
