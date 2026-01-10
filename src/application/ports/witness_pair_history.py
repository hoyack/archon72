"""Witness pair history port definition (FR60).

Defines the abstract interface for witness pair history operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR60: No witness pair SHALL appear consecutively more than once per 24-hour period
"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.models.witness_pair import WitnessPair


class WitnessPairHistoryProtocol(ABC):
    """Abstract protocol for witness pair history operations.

    All witness pair history implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific storage implementations.

    Constitutional Constraint (FR60):
    No witness pair SHALL appear consecutively more than once per 24-hour period.

    Implementations may include:
    - InMemoryWitnessPairHistory: For testing
    - RedisPairHistory: For production with distributed state
    - DatabasePairHistory: For production with Supabase
    """

    @abstractmethod
    async def has_appeared_in_24h(self, pair: WitnessPair) -> bool:
        """Check if pair has appeared in last 24 hours (FR60).

        Args:
            pair: The witness pair to check.

        Returns:
            True if this pair has appeared within the 24-hour rotation window,
            False if it's allowed to appear again.
        """
        ...

    @abstractmethod
    async def record_pair(self, pair: WitnessPair) -> None:
        """Record a new pair appearance.

        Records the pair with its timestamp for rotation tracking.
        If the pair already exists, updates the timestamp.

        Args:
            pair: The witness pair to record.
        """
        ...

    @abstractmethod
    async def get_pair_last_appearance(self, pair_key: str) -> datetime | None:
        """Get the last appearance time for a pair.

        Args:
            pair_key: The canonical pair key (e.g., "WITNESS:abc:WITNESS:xyz").

        Returns:
            The datetime of last appearance, or None if never recorded.
        """
        ...

    @abstractmethod
    async def prune_old_pairs(self) -> int:
        """Remove pairs older than the rotation window.

        Cleans up storage by removing pairs that are no longer
        relevant for rotation enforcement (older than 24 hours).

        Returns:
            Number of pairs removed.
        """
        ...

    @abstractmethod
    async def count_tracked_pairs(self) -> int:
        """Get the number of currently tracked pairs.

        Used for monitoring and diagnostics.

        Returns:
            The count of pairs currently being tracked.
        """
        ...
