"""Topic manipulation domain errors (Story 6.9, FR118, FR124).

This module provides exception classes for topic manipulation defense
and seed validation failures.

Constitutional Constraints:
- FR118: External topic rate limiting (10/day per source)
- FR124: Seed independence verification

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Errors logged for audit
"""

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.exceptions import ConclaveError


class TopicManipulationDefenseError(ConclaveError):
    """Base class for topic manipulation defense errors.

    This is NOT a constitutional violation - it represents
    defense mechanisms operating correctly. Detection and rate
    limiting are expected behaviors, not failures.

    Subclasses:
    - DailyRateLimitExceededError: FR118 daily limit enforcement
    """

    pass


class DailyRateLimitExceededError(TopicManipulationDefenseError):
    """Raised when external source exceeds daily topic limit (FR118).

    FR118: External topic sources (non-autonomous) SHALL be rate-limited
           to 10 topics/day per source.

    This error indicates the defense is working correctly.
    The excess topic is rejected, not queued (unlike hourly limits).

    Attributes:
        source_id: The source that exceeded the limit.
        topics_today: Number of topics submitted today.
        daily_limit: Maximum allowed per day.
    """

    def __init__(
        self,
        source_id: str,
        topics_today: int,
        daily_limit: int,
    ) -> None:
        """Initialize the error with rate limit details.

        Args:
            source_id: The source that exceeded the limit.
            topics_today: Number of topics submitted today.
            daily_limit: Maximum allowed per day.
        """
        self.source_id = source_id
        self.topics_today = topics_today
        self.daily_limit = daily_limit

        message = (
            f"FR118: Daily topic limit exceeded - {source_id} submitted "
            f"{topics_today} topics (limit: {daily_limit})"
        )
        super().__init__(message)


class PredictableSeedError(ConstitutionalViolationError):
    """Raised when a seed is rejected due to predictability (FR124).

    FR124: Witness selection randomness SHALL combine hash chain state
           + external entropy source meeting independence criteria.

    This IS a constitutional violation - predictable seeds could
    enable manipulation of witness selection.

    Attributes:
        seed_purpose: What the seed was intended for.
        predictability_reason: Why the seed was detected as predictable.
    """

    def __init__(
        self,
        seed_purpose: str,
        predictability_reason: str,
    ) -> None:
        """Initialize the error with predictability details.

        Args:
            seed_purpose: What the seed was intended for.
            predictability_reason: Why the seed was detected as predictable.
        """
        self.seed_purpose = seed_purpose
        self.predictability_reason = predictability_reason

        message = (
            f"FR124: Predictable seed rejected - {seed_purpose}: "
            f"{predictability_reason}"
        )
        super().__init__(message)


class SeedSourceDependenceError(ConstitutionalViolationError):
    """Raised when seed source independence verification fails (FR124).

    FR124: External entropy sources MUST meet independence criteria.
    A dependent source could be manipulated to influence outcomes.

    This IS a constitutional violation - non-independent sources
    could enable manipulation of witness selection.

    Attributes:
        seed_purpose: What the seed was intended for.
        failed_source: The source that failed independence check.
    """

    def __init__(
        self,
        seed_purpose: str,
        failed_source: str,
    ) -> None:
        """Initialize the error with source dependence details.

        Args:
            seed_purpose: What the seed was intended for.
            failed_source: The source that failed independence check.
        """
        self.seed_purpose = seed_purpose
        self.failed_source = failed_source

        message = (
            f"FR124: Seed source independence verification failed for {seed_purpose}"
        )
        super().__init__(message)
