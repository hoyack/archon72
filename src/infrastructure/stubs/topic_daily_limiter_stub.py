"""Topic daily limiter stub (Story 6.9, FR118).

In-memory implementation for testing and development.

Constitutional Constraints:
- FR118: External topic rate limiting (10/day)
- CT-12: Witnessing creates accountability -> signable audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from src.application.ports.topic_daily_limiter import (
    DAILY_TOPIC_LIMIT,
    TopicDailyLimiterProtocol,
)


@dataclass
class DailySubmissionRecord:
    """Record of a topic submission for daily tracking."""

    source_id: str
    topic_id: str
    submitted_at: datetime


@dataclass
class TopicDailyLimiterStub(TopicDailyLimiterProtocol):
    """In-memory stub for daily topic rate limiting.

    Tracks topic submissions per source per day.
    Supports configurable daily limits for testing.

    FR118: External topic rate limiting (10/day).
    """

    # Storage for submissions
    _submissions: list[DailySubmissionRecord] = field(default_factory=list)

    # Configurable external sources
    _external_sources: set[str] = field(default_factory=set)

    # Configurable daily limit (default from port)
    _daily_limit: int = DAILY_TOPIC_LIMIT

    async def check_daily_limit(
        self,
        source_id: str,
    ) -> bool:
        """Check if source is within daily limit.

        Args:
            source_id: Source to check.

        Returns:
            True if within daily limit, False if exceeded.
        """
        today_count = await self.get_daily_count(source_id)
        return today_count < self._daily_limit

    async def get_daily_count(
        self,
        source_id: str,
    ) -> int:
        """Get number of topics submitted today by source.

        Args:
            source_id: Source to query.

        Returns:
            Number of topics submitted today.
        """
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        count = sum(
            1
            for s in self._submissions
            if s.source_id == source_id and s.submitted_at >= today_start
        )
        return count

    async def record_daily_submission(
        self,
        source_id: str,
    ) -> int:
        """Record a topic submission and return new count.

        Args:
            source_id: Source making submission.

        Returns:
            New total count for today.
        """
        self._submissions.append(
            DailySubmissionRecord(
                source_id=source_id,
                topic_id=f"topic_{len(self._submissions) + 1}",  # auto-generated for tracking
                submitted_at=datetime.now(timezone.utc),
            )
        )
        return await self.get_daily_count(source_id)

    async def get_daily_limit(self) -> int:
        """Get configured daily limit.

        Returns:
            Daily topic limit per source.
        """
        return self._daily_limit

    async def get_limit_reset_time(
        self,
        source_id: str,
    ) -> datetime:
        """Get when daily limit resets for source.

        Args:
            source_id: Source to query.

        Returns:
            Datetime when limit resets (midnight UTC).
        """
        # Limit resets at midnight UTC
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        return tomorrow

    async def is_external_source(
        self,
        source_id: str,
    ) -> bool:
        """Check if source is external (subject to rate limiting).

        Args:
            source_id: Source to check.

        Returns:
            True if external, False if internal.
        """
        return source_id in self._external_sources

    # Test helper methods

    def set_daily_limit(self, limit: int) -> None:
        """Set daily limit for testing.

        Args:
            limit: New daily limit.
        """
        self._daily_limit = limit

    def add_external_source(self, source_id: str) -> None:
        """Mark a source as external.

        Args:
            source_id: Source to mark as external.
        """
        self._external_sources.add(source_id)

    def remove_external_source(self, source_id: str) -> None:
        """Mark a source as internal.

        Args:
            source_id: Source to mark as internal.
        """
        self._external_sources.discard(source_id)

    def add_submission(
        self,
        source_id: str,
        topic_id: str,
        submitted_at: datetime | None = None,
    ) -> None:
        """Add a submission record directly for testing.

        Args:
            source_id: Source ID.
            topic_id: Topic ID.
            submitted_at: When submitted (defaults to now).
        """
        self._submissions.append(
            DailySubmissionRecord(
                source_id=source_id,
                topic_id=topic_id,
                submitted_at=submitted_at or datetime.now(timezone.utc),
            )
        )

    def get_submissions(self) -> list[DailySubmissionRecord]:
        """Get all submission records.

        Returns:
            List of all submissions.
        """
        return list(self._submissions)

    def get_submissions_for_source(
        self,
        source_id: str,
    ) -> list[DailySubmissionRecord]:
        """Get submissions for a specific source.

        Args:
            source_id: Source to query.

        Returns:
            List of submissions from that source.
        """
        return [s for s in self._submissions if s.source_id == source_id]

    def clear(self) -> None:
        """Clear all stored data for test isolation."""
        self._submissions.clear()
        self._external_sources.clear()
        self._daily_limit = DAILY_TOPIC_LIMIT
