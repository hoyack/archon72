"""Rate Limit Store Port for PostgreSQL time-bucket persistence (Story 1.4, D4).

This module defines the abstract interface for rate limit bucket storage
using PostgreSQL time-bucket counters per architecture decision D4.

Constitutional Constraints:
- D4: PostgreSQL time-bucket counters with minute buckets
- Rate limit state must be persistent and distributed-safe
- Bounded by periodic TTL cleanup (buckets older than 2 hours)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class RateLimitStorePort(Protocol):
    """Protocol for rate limit bucket storage (Story 1.4, D4).

    Implementations must use PostgreSQL with minute-granularity buckets.
    The store handles bucket creation, increment, and expiry queries.

    Architecture Decision D4:
    - Minute buckets summed over last hour for sliding window
    - Persistent and distributed-safe via PostgreSQL
    - Bounded by periodic TTL cleanup
    """

    async def get_submission_count(
        self,
        submitter_id: UUID,
        since: datetime,
    ) -> int:
        """Get total submission count in sliding window.

        SQL Pattern:
            SELECT COALESCE(SUM(count), 0) as total
            FROM petition_rate_limit_buckets
            WHERE submitter_id = $1
              AND bucket_minute > $2

        Args:
            submitter_id: UUID of the submitter to query.
            since: Start of sliding window (e.g., NOW() - INTERVAL '60 minutes').

        Returns:
            Total count of submissions in the window.
        """
        ...

    async def increment_bucket(
        self,
        submitter_id: UUID,
        bucket_minute: datetime,
    ) -> None:
        """Increment or create a minute bucket for submitter.

        Uses UPSERT pattern for atomic increment:
            INSERT INTO petition_rate_limit_buckets (submitter_id, bucket_minute, count)
            VALUES ($1, $2, 1)
            ON CONFLICT (submitter_id, bucket_minute)
            DO UPDATE SET count = petition_rate_limit_buckets.count + 1

        Args:
            submitter_id: UUID of the submitter.
            bucket_minute: Minute boundary timestamp (truncated to minute).
        """
        ...

    async def get_oldest_bucket_expiry(
        self,
        submitter_id: UUID,
        since: datetime,
    ) -> Optional[datetime]:
        """Get expiry time of the oldest bucket in window.

        Used to calculate the reset_at time for rate limit responses.

        SQL Pattern:
            SELECT bucket_minute + INTERVAL '60 minutes' as expires_at
            FROM petition_rate_limit_buckets
            WHERE submitter_id = $1
              AND bucket_minute > $2
            ORDER BY bucket_minute ASC
            LIMIT 1

        Args:
            submitter_id: UUID of the submitter to query.
            since: Start of sliding window.

        Returns:
            Datetime when the oldest bucket expires, or None if no buckets exist.
        """
        ...

    async def cleanup_expired_buckets(
        self,
        older_than: datetime,
    ) -> int:
        """Delete buckets older than the specified time.

        Called by TTL cleanup job to remove expired buckets.

        SQL Pattern:
            DELETE FROM petition_rate_limit_buckets
            WHERE bucket_minute < $1

        Args:
            older_than: Delete buckets with bucket_minute before this time.

        Returns:
            Number of buckets deleted.
        """
        ...
