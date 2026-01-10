"""TopicOriginService application service (Story 2.7, FR15/FR71-73).

This service orchestrates topic origin tracking, rate limiting,
and diversity enforcement.

Constitutional Constraints:
- FR15: Topic origins SHALL be tracked with metadata
- FR71: Rate limit rapid submissions (>10/hour from single source)
- FR72: Excess topics SHALL be queued, not rejected
- FR73: No single origin type SHALL exceed 30% over rolling 30-day window

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> All operations traceable
- CT-13: Integrity outranks availability -> Topics queued, not dropped

Architecture Pattern:
    TopicOriginService orchestrates FR15/FR71-73 compliance:

    record_topic(topic, source_id):
      ├─ halt_checker.is_halted()          # HALT FIRST rule
      ├─ limiter.check_rate_limit()        # FR71 check
      ├─ If rate limited:
      │    ├─ limiter.queue_topic()        # FR72 - queue, don't reject
      │    └─ Create TopicRateLimitEvent
      └─ If within limit:
           └─ tracker.record_topic_origin() # FR15 - track origin

    check_diversity_compliance():
      ├─ tracker.get_diversity_stats()     # FR73 - 30-day window
      └─ If exceeds threshold:
           └─ Create TopicDiversityAlertEvent
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.topic_origin_tracker import (
    DIVERSITY_THRESHOLD,
    DIVERSITY_WINDOW_DAYS,
    TopicOriginTrackerPort,
)
from src.application.ports.topic_rate_limiter import (
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_WINDOW_SECONDS,
    TopicRateLimiterPort,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.topic_diversity_alert import TopicDiversityAlertPayload
from src.domain.events.topic_rate_limit import TopicRateLimitPayload
from src.domain.models.topic_origin import TopicOrigin

logger = structlog.get_logger()


@dataclass
class RecordTopicResult:
    """Result of recording a topic.

    Attributes:
        recorded: Whether the topic was recorded directly.
        queued: Whether the topic was queued due to rate limiting.
        queue_position: Position in queue if queued.
        rate_limit_event: Event created if rate limited.
    """

    recorded: bool
    queued: bool
    queue_position: int | None = None
    rate_limit_event: TopicRateLimitPayload | None = None


@dataclass
class DiversityCheckResult:
    """Result of diversity compliance check.

    Attributes:
        compliant: Whether diversity is within threshold.
        alert_event: Event created if threshold exceeded.
    """

    compliant: bool
    alert_event: TopicDiversityAlertPayload | None = None


class TopicOriginService:
    """Application service for topic origin tracking (FR15/FR71-73).

    This service provides the primary interface for:
    - Recording topic origins with metadata (FR15)
    - Rate limiting topic submissions (FR71)
    - Queuing excess topics (FR72)
    - Checking diversity compliance (FR73)

    HALT FIRST Rule:
        Every operation checks halt state before proceeding.
        Never retry after SystemHaltedError.

    Attributes:
        _halt_checker: Interface for checking halt state.
        _tracker: Interface for tracking topic origins.
        _limiter: Interface for rate limiting.
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        tracker: TopicOriginTrackerPort,
        limiter: TopicRateLimiterPort,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            halt_checker: Interface for checking halt state.
            tracker: Interface for tracking topic origins.
            limiter: Interface for rate limiting.

        Raises:
            TypeError: If any required dependency is None.
        """
        if halt_checker is None:
            raise TypeError("halt_checker is required")
        if tracker is None:
            raise TypeError("tracker is required")
        if limiter is None:
            raise TypeError("limiter is required")

        self._halt_checker = halt_checker
        self._tracker = tracker
        self._limiter = limiter

    async def record_topic(
        self,
        topic: TopicOrigin,
        source_id: str,
    ) -> RecordTopicResult:
        """Record a topic with origin tracking and rate limiting.

        This is the primary method for FR15/FR71-72 compliance.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Check rate limit for source (FR71)
            3. If rate limited: queue topic (FR72), create event
            4. If within limit: record topic origin (FR15)

        Args:
            topic: The topic to record.
            source_id: The source submitting the topic.

        Returns:
            RecordTopicResult with recording status.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "topic_recording_blocked_halted",
                topic_id=str(topic.topic_id),
                source_id=source_id,
            )
            raise SystemHaltedError("System halted - cannot record topic")

        # Check rate limit (FR71)
        within_limit = await self._limiter.check_rate_limit(source_id)

        if not within_limit:
            # Queue topic (FR72 - queue, don't reject)
            queue_position = await self._limiter.queue_topic(topic)

            # Record submission even when queued
            submission_count = await self._limiter.record_submission(source_id)

            # Create rate limit event
            rate_limit_event = TopicRateLimitPayload(
                source_id=source_id,
                topics_submitted=submission_count,
                limit=RATE_LIMIT_PER_HOUR,
                queued_count=queue_position,
                rate_limit_start=datetime.now(timezone.utc),
                rate_limit_duration_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )

            logger.warning(
                "topic_rate_limited",
                topic_id=str(topic.topic_id),
                source_id=source_id,
                queue_position=queue_position,
                submissions_this_hour=submission_count,
                limit=RATE_LIMIT_PER_HOUR,
            )

            return RecordTopicResult(
                recorded=False,
                queued=True,
                queue_position=queue_position,
                rate_limit_event=rate_limit_event,
            )

        # Record topic origin (FR15)
        await self._tracker.record_topic_origin(topic)
        await self._limiter.record_submission(source_id)

        logger.info(
            "topic_origin_recorded",
            topic_id=str(topic.topic_id),
            origin_type=topic.origin_type.value,
            source_id=source_id,
            created_by=topic.created_by,
        )

        return RecordTopicResult(recorded=True, queued=False)

    async def check_diversity_compliance(
        self,
        window_days: int = DIVERSITY_WINDOW_DAYS,
        threshold: float = DIVERSITY_THRESHOLD,
    ) -> DiversityCheckResult:
        """Check topic diversity compliance (FR73).

        Analyzes topic distribution over a rolling window and
        creates an alert if any origin type exceeds threshold.

        Args:
            window_days: Days for rolling window (default 30).
            threshold: Maximum allowed percentage (default 0.30).

        Returns:
            DiversityCheckResult with compliance status.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning("diversity_check_blocked_halted")
            raise SystemHaltedError("System halted - cannot check diversity")

        # Get diversity statistics
        stats = await self._tracker.get_diversity_stats(window_days=window_days)

        # Check if any type exceeds threshold
        violating_type = stats.exceeds_threshold(threshold=threshold)

        if violating_type is None:
            logger.debug(
                "diversity_check_compliant",
                window_days=window_days,
                total_topics=stats.total_topics,
                autonomous_pct=stats.autonomous_pct,
                petition_pct=stats.petition_pct,
                scheduled_pct=stats.scheduled_pct,
            )
            return DiversityCheckResult(compliant=True)

        # Create diversity alert event
        current_pct = {
            "autonomous": stats.autonomous_pct,
            "petition": stats.petition_pct,
            "scheduled": stats.scheduled_pct,
        }.get(violating_type.value, 0.0)

        alert_event = TopicDiversityAlertPayload(
            violation_type=violating_type,
            current_percentage=current_pct,
            threshold=threshold,
            window_start=stats.window_start,
            window_end=stats.window_end,
            total_topics=stats.total_topics,
        )

        logger.warning(
            "diversity_threshold_exceeded",
            violation_type=violating_type.value,
            current_percentage=current_pct,
            threshold=threshold,
            window_days=window_days,
            total_topics=stats.total_topics,
        )

        return DiversityCheckResult(compliant=False, alert_event=alert_event)

    async def get_topic_origin(self, topic_id: UUID) -> TopicOrigin | None:
        """Get a topic origin by ID.

        Args:
            topic_id: The topic's unique identifier.

        Returns:
            TopicOrigin if found, None otherwise.
        """
        return await self._tracker.get_topic_origin(topic_id)

    async def process_queued_topics(self) -> int:
        """Process queued topics that are no longer rate limited.

        This method should be called periodically to process
        topics that were queued due to rate limiting.

        Returns:
            Number of topics processed.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST - Check before processing
        if await self._halt_checker.is_halted():
            logger.warning("queue_processing_blocked_halted")
            raise SystemHaltedError("System halted - cannot process queue")

        processed = 0

        while True:
            # Check if we can process more
            topic = await self._limiter.dequeue_topic()
            if topic is None:
                break

            # Check rate limit for dequeued topic
            within_limit = await self._limiter.check_rate_limit(topic.created_by)
            if not within_limit:
                # Still rate limited, re-queue
                await self._limiter.queue_topic(topic)
                break

            # Record topic
            await self._tracker.record_topic_origin(topic)
            processed += 1

            logger.info(
                "queued_topic_processed",
                topic_id=str(topic.topic_id),
                created_by=topic.created_by,
            )

        if processed > 0:
            logger.info(
                "queue_processing_complete",
                topics_processed=processed,
            )

        return processed
