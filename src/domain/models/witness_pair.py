"""Witness pair tracking domain models (FR60).

Provides domain models for tracking witness pairs to enforce
rotation constraints.

Constitutional Constraints:
- FR60: No witness pair SHALL appear consecutively more than once per 24-hour period
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

# FR60: Rotation window in hours
ROTATION_WINDOW_HOURS: int = 24


@dataclass(frozen=True)
class WitnessPair:
    """Witness pair for rotation tracking (FR60).

    Represents a pair of witnesses that appeared together (either as
    event witness + previous event witness, or primary + secondary).

    Constitutional Constraint (FR60):
    No witness pair SHALL appear consecutively more than once per 24-hour period.

    Pairs are symmetric: (A,B) == (B,A) for rotation tracking purposes.

    Attributes:
        witness_a_id: First witness ID
        witness_b_id: Second witness ID (can be same as A for single witness case)
        paired_at: When this pair was recorded
    """

    witness_a_id: str
    witness_b_id: str
    paired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def canonical_key(self) -> str:
        """Get canonical key for pair comparison.

        Pairs are symmetric: (A,B) == (B,A).
        Canonical form: sorted IDs joined with colon.

        Returns:
            Canonical string key like "WITNESS:abc:WITNESS:xyz"
        """
        ids = sorted([self.witness_a_id, self.witness_b_id])
        return f"{ids[0]}:{ids[1]}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize pair for storage/transmission."""
        return {
            "witness_a_id": self.witness_a_id,
            "witness_b_id": self.witness_b_id,
            "paired_at": self.paired_at.isoformat(),
            "canonical_key": self.canonical_key(),
        }


class WitnessPairHistory:
    """Track witness pairs for FR60 rotation enforcement.

    Maintains a record of recent witness pairs and checks whether
    a given pair has appeared within the rotation window.

    Constitutional Constraint (FR60):
    No witness pair SHALL appear consecutively more than once per 24-hour period.

    This class is NOT frozen as it maintains mutable state.
    For persistent storage, use WitnessPairHistoryProtocol implementations.
    """

    def __init__(self) -> None:
        """Initialize empty pair history."""
        self._recent_pairs: dict[str, datetime] = {}

    def has_appeared_in_24h(self, pair: WitnessPair) -> bool:
        """Check if pair has appeared in last 24 hours (FR60).

        Args:
            pair: The witness pair to check.

        Returns:
            True if this pair has appeared within the rotation window,
            False if it's allowed to appear again.
        """
        key = pair.canonical_key()
        if key not in self._recent_pairs:
            return False

        last_time = self._recent_pairs[key]
        now = datetime.now(timezone.utc)
        window = timedelta(hours=ROTATION_WINDOW_HOURS)

        return (now - last_time) < window

    def record_pair(self, pair: WitnessPair) -> None:
        """Record a new pair appearance.

        Updates or adds the pair's timestamp in the history.

        Args:
            pair: The witness pair to record.
        """
        key = pair.canonical_key()
        self._recent_pairs[key] = pair.paired_at

    def get_last_appearance(self, pair_key: str) -> datetime | None:
        """Get the last appearance time for a pair.

        Args:
            pair_key: The canonical pair key.

        Returns:
            The datetime of last appearance, or None if never seen.
        """
        return self._recent_pairs.get(pair_key)

    def prune_old_pairs(self) -> int:
        """Remove pairs older than the rotation window.

        Cleans up memory by removing pairs that are no longer
        relevant for rotation enforcement.

        Returns:
            Number of pairs removed.
        """
        now = datetime.now(timezone.utc)
        window = timedelta(hours=ROTATION_WINDOW_HOURS)
        cutoff = now - window

        old_keys = [
            key for key, timestamp in self._recent_pairs.items() if timestamp < cutoff
        ]

        for key in old_keys:
            del self._recent_pairs[key]

        return len(old_keys)

    def clear(self) -> None:
        """Clear all pair history.

        Used primarily for testing.
        """
        self._recent_pairs.clear()

    @property
    def pair_count(self) -> int:
        """Get the number of tracked pairs."""
        return len(self._recent_pairs)
