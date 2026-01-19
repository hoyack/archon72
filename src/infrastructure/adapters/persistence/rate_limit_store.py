"""PostgreSQL Rate Limit Store adapter (Story 1.4, AC3, D4).

This module provides the production PostgreSQL implementation of
RateLimitStorePort for time-bucket based rate limiting.

Constitutional Constraints:
- D4: PostgreSQL time-bucket counters (minute buckets summed over sliding window)
- HC-4: 10 petitions/user/hour (configurable)
- CT-11: Silent failure destroys legitimacy → All operations logged
- NFR-5.1: Rate limiting per identity
- FR-1.5: Enforce rate limits per submitter_id

Architecture:
- Uses minute-granularity buckets for sliding window calculation
- UPSERT pattern for atomic bucket increment (ON CONFLICT DO UPDATE)
- Efficient SUM query for submission count within window
- TTL cleanup for expired buckets (older than 2 hours)

Database Table: petition_rate_limit_buckets (migration 016)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.application.ports.rate_limit_store import RateLimitStorePort

logger = get_logger()


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class PostgresRateLimitStore(RateLimitStorePort):
    """PostgreSQL implementation of RateLimitStorePort (Story 1.4, AC3, D4).

    Uses the petition_rate_limit_buckets table created by
    migration 016_create_rate_limit_buckets.sql.

    Constitutional Compliance:
    - D4: Time-bucket counters with minute granularity
    - HC-4: Supports configurable rate limits (default 10/hour)
    - NFR-5.1: Per-identity rate limiting

    Query Patterns:
    - get_submission_count: SUM(count) WHERE bucket_minute > window_start
    - increment_bucket: INSERT ON CONFLICT DO UPDATE SET count = count + 1
    - get_oldest_bucket_expiry: MIN(bucket_minute) + window for reset time
    - cleanup_expired_buckets: DELETE WHERE bucket_minute < cutoff

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the PostgreSQL rate limit store.

        Args:
            session_factory: SQLAlchemy async session factory for DB access.
        """
        self._session_factory = session_factory

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
        log = logger.bind(
            submitter_id=str(submitter_id),
            since=since.isoformat(),
        )

        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT COALESCE(SUM(count), 0) as total
                    FROM petition_rate_limit_buckets
                    WHERE submitter_id = :submitter_id
                      AND bucket_minute > :since
                """),
                {
                    "submitter_id": submitter_id,
                    "since": since,
                },
            )
            count = result.scalar() or 0

        log.debug(
            "submission_count_queried",
            count=count,
        )
        return int(count)

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
        log = logger.bind(
            submitter_id=str(submitter_id),
            bucket_minute=bucket_minute.isoformat(),
        )

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("""
                        INSERT INTO petition_rate_limit_buckets (
                            submitter_id, bucket_minute, count, created_at
                        )
                        VALUES (
                            :submitter_id, :bucket_minute, 1, :created_at
                        )
                        ON CONFLICT (submitter_id, bucket_minute)
                        DO UPDATE SET count = petition_rate_limit_buckets.count + 1
                    """),
                    {
                        "submitter_id": submitter_id,
                        "bucket_minute": bucket_minute,
                        "created_at": _utc_now(),
                    },
                )

        log.debug("bucket_incremented")

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
        log = logger.bind(
            submitter_id=str(submitter_id),
            since=since.isoformat(),
        )

        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT bucket_minute
                    FROM petition_rate_limit_buckets
                    WHERE submitter_id = :submitter_id
                      AND bucket_minute > :since
                    ORDER BY bucket_minute ASC
                    LIMIT 1
                """),
                {
                    "submitter_id": submitter_id,
                    "since": since,
                },
            )
            row = result.fetchone()

        if row:
            # Calculate expiry: bucket_minute + 60 minutes (window size)
            # Note: The window size is passed from the service layer
            oldest_bucket = row[0]
            expiry = oldest_bucket + timedelta(minutes=60)
            log.debug(
                "oldest_bucket_found",
                oldest_bucket=oldest_bucket.isoformat(),
                expiry=expiry.isoformat(),
            )
            return expiry

        log.debug("no_buckets_found")
        return None

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
        log = logger.bind(older_than=older_than.isoformat())

        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    text("""
                        DELETE FROM petition_rate_limit_buckets
                        WHERE bucket_minute < :older_than
                    """),
                    {"older_than": older_than},
                )
                deleted = result.rowcount

        log.info(
            "expired_buckets_cleaned",
            deleted_count=deleted,
            message="D4: TTL cleanup of expired rate limit buckets",
        )
        return deleted
