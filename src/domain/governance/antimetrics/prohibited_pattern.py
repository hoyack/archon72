"""Prohibited Patterns for Anti-Metrics Enforcement.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

This module defines the patterns that are prohibited by anti-metrics constraints.
These patterns cover:
1. Table names that suggest metric storage
2. Column names that suggest metric tracking
3. Pattern categories for violation classification

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer
"""

from enum import Enum


class ProhibitedPattern(Enum):
    """Patterns that are prohibited by anti-metrics.

    These patterns represent categories of data that MUST NOT
    be stored or tracked by the system.

    Constitutional References:
    - PARTICIPANT_PERFORMANCE: Prohibited by FR61
    - COMPLETION_RATE: Prohibited by FR62
    - ENGAGEMENT_TRACKING: Prohibited by FR63
    - RETENTION_METRICS: Prohibited by FR63
    - SESSION_TRACKING: Prohibited by FR63
    - RESPONSE_TIME_PER_PARTICIPANT: Prohibited by FR61
    """

    PARTICIPANT_PERFORMANCE = "participant_performance"
    COMPLETION_RATE = "completion_rate"
    ENGAGEMENT_TRACKING = "engagement_tracking"
    RETENTION_METRICS = "retention_metrics"
    SESSION_TRACKING = "session_tracking"
    RESPONSE_TIME_PER_PARTICIPANT = "response_time_per_participant"

    def __str__(self) -> str:
        """Return human-readable pattern name."""
        return self.value.replace("_", " ").title()


# Regex patterns for prohibited table names
# These tables CANNOT be created in the database
PROHIBITED_TABLE_PATTERNS: list[str] = [
    r".*_metrics$",  # Any table ending in _metrics
    r".*_performance$",  # Any table ending in _performance
    r".*_engagement$",  # Any table ending in _engagement
    r".*_retention$",  # Any table ending in _retention
    r".*_analytics$",  # Any table ending in _analytics
    r"^participant_scores$",  # Participant scoring table
    r"^completion_rates$",  # Completion rate tracking
    r"^session_tracking$",  # Session tracking table
    r"^login_history$",  # Login tracking
    r"^user_activity$",  # User activity tracking
    r"^engagement_scores$",  # Engagement scoring
    r"^performance_scores$",  # Performance scoring
]

# Regex patterns for prohibited column names
# These columns CANNOT be added to any table
PROHIBITED_COLUMN_PATTERNS: list[str] = [
    r"^completion_rate$",  # Per-participant completion rate
    r"^success_rate$",  # Per-participant success rate
    r"^failure_rate$",  # Per-participant failure rate
    r"^performance_score$",  # Performance score
    r"^engagement_score$",  # Engagement score
    r"^retention_score$",  # Retention score
    r"^session_count$",  # Session counting
    r"^login_count$",  # Login counting
    r"^activity_score$",  # Activity scoring
    r"^response_time_avg$",  # Response time tracking
    r"^task_completion_count$",  # Task completion counting
    r"^last_active$",  # Activity tracking
    r"^engagement_level$",  # Engagement level tracking
]
