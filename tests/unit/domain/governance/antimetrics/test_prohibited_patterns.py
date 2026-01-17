"""Tests for prohibited pattern definitions.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

These tests verify that:
1. All required prohibited patterns are defined
2. Patterns match expected table/column names
3. Pattern classification is correct
"""

import re

import pytest

from src.domain.governance.antimetrics import (
    PROHIBITED_COLUMN_PATTERNS,
    PROHIBITED_TABLE_PATTERNS,
    ProhibitedPattern,
)


class TestProhibitedPatternEnum:
    """Tests for ProhibitedPattern enumeration."""

    def test_all_patterns_defined(self) -> None:
        """All required patterns are defined."""
        assert ProhibitedPattern.PARTICIPANT_PERFORMANCE.value == "participant_performance"
        assert ProhibitedPattern.COMPLETION_RATE.value == "completion_rate"
        assert ProhibitedPattern.ENGAGEMENT_TRACKING.value == "engagement_tracking"
        assert ProhibitedPattern.RETENTION_METRICS.value == "retention_metrics"
        assert ProhibitedPattern.SESSION_TRACKING.value == "session_tracking"
        assert ProhibitedPattern.RESPONSE_TIME_PER_PARTICIPANT.value == "response_time_per_participant"

    def test_pattern_count(self) -> None:
        """Expected number of patterns defined."""
        assert len(ProhibitedPattern) == 6

    def test_str_representation(self) -> None:
        """String representation is human-readable."""
        assert str(ProhibitedPattern.PARTICIPANT_PERFORMANCE) == "Participant Performance"
        assert str(ProhibitedPattern.COMPLETION_RATE) == "Completion Rate"


class TestProhibitedTablePatterns:
    """Tests for prohibited table patterns."""

    @pytest.mark.parametrize(
        "table_name",
        [
            "cluster_metrics",
            "task_metrics",
            "user_metrics",
            "participant_metrics",
        ],
    )
    def test_metrics_suffix_blocked(self, table_name: str) -> None:
        """Tables ending in _metrics are blocked."""
        assert self._matches_any_pattern(table_name, PROHIBITED_TABLE_PATTERNS)

    @pytest.mark.parametrize(
        "table_name",
        [
            "task_performance",
            "cluster_performance",
            "agent_performance",
        ],
    )
    def test_performance_suffix_blocked(self, table_name: str) -> None:
        """Tables ending in _performance are blocked."""
        assert self._matches_any_pattern(table_name, PROHIBITED_TABLE_PATTERNS)

    @pytest.mark.parametrize(
        "table_name",
        [
            "user_engagement",
            "participant_engagement",
            "cluster_engagement",
        ],
    )
    def test_engagement_suffix_blocked(self, table_name: str) -> None:
        """Tables ending in _engagement are blocked."""
        assert self._matches_any_pattern(table_name, PROHIBITED_TABLE_PATTERNS)

    @pytest.mark.parametrize(
        "table_name",
        [
            "user_retention",
            "participant_retention",
        ],
    )
    def test_retention_suffix_blocked(self, table_name: str) -> None:
        """Tables ending in _retention are blocked."""
        assert self._matches_any_pattern(table_name, PROHIBITED_TABLE_PATTERNS)

    @pytest.mark.parametrize(
        "table_name",
        [
            "user_analytics",
            "task_analytics",
            "cluster_analytics",
        ],
    )
    def test_analytics_suffix_blocked(self, table_name: str) -> None:
        """Tables ending in _analytics are blocked."""
        assert self._matches_any_pattern(table_name, PROHIBITED_TABLE_PATTERNS)

    @pytest.mark.parametrize(
        "table_name",
        [
            "participant_scores",
            "completion_rates",
            "session_tracking",
        ],
    )
    def test_specific_tables_blocked(self, table_name: str) -> None:
        """Specific prohibited tables are blocked."""
        assert self._matches_any_pattern(table_name, PROHIBITED_TABLE_PATTERNS)

    @pytest.mark.parametrize(
        "table_name",
        [
            "tasks",
            "clusters",
            "participants",
            "events",
            "governance_events",
            "witness_statements",
            "panel_findings",
            "task_assignments",
            "consent_records",
        ],
    )
    def test_legitimate_tables_allowed(self, table_name: str) -> None:
        """Legitimate governance tables are allowed."""
        assert not self._matches_any_pattern(table_name, PROHIBITED_TABLE_PATTERNS)

    def _matches_any_pattern(self, name: str, patterns: list[str]) -> bool:
        """Check if name matches any pattern."""
        return any(re.match(pattern, name) for pattern in patterns)


class TestProhibitedColumnPatterns:
    """Tests for prohibited column patterns."""

    @pytest.mark.parametrize(
        "column_name",
        [
            "completion_rate",
            "success_rate",
            "failure_rate",
        ],
    )
    def test_rate_columns_blocked(self, column_name: str) -> None:
        """Rate tracking columns are blocked."""
        assert self._matches_any_pattern(column_name, PROHIBITED_COLUMN_PATTERNS)

    @pytest.mark.parametrize(
        "column_name",
        [
            "performance_score",
            "engagement_score",
            "retention_score",
            "activity_score",
        ],
    )
    def test_score_columns_blocked(self, column_name: str) -> None:
        """Score tracking columns are blocked."""
        assert self._matches_any_pattern(column_name, PROHIBITED_COLUMN_PATTERNS)

    @pytest.mark.parametrize(
        "column_name",
        [
            "session_count",
            "login_count",
            "task_completion_count",
        ],
    )
    def test_count_columns_blocked(self, column_name: str) -> None:
        """Count tracking columns are blocked."""
        assert self._matches_any_pattern(column_name, PROHIBITED_COLUMN_PATTERNS)

    @pytest.mark.parametrize(
        "column_name",
        [
            "last_active",
            "engagement_level",
            "response_time_avg",
        ],
    )
    def test_tracking_columns_blocked(self, column_name: str) -> None:
        """Activity tracking columns are blocked."""
        assert self._matches_any_pattern(column_name, PROHIBITED_COLUMN_PATTERNS)

    @pytest.mark.parametrize(
        "column_name",
        [
            "id",
            "created_at",
            "updated_at",
            "cluster_id",
            "task_id",
            "participant_id",
            "status",
            "content",
            "description",
            "name",
            "event_type",
            "actor",
        ],
    )
    def test_legitimate_columns_allowed(self, column_name: str) -> None:
        """Legitimate governance columns are allowed."""
        assert not self._matches_any_pattern(column_name, PROHIBITED_COLUMN_PATTERNS)

    def _matches_any_pattern(self, name: str, patterns: list[str]) -> bool:
        """Check if name matches any pattern."""
        return any(re.match(pattern, name) for pattern in patterns)


class TestPatternCoverage:
    """Tests for pattern coverage of constitutional requirements."""

    def test_fr61_coverage(self) -> None:
        """FR61: No participant-level performance metrics.

        Patterns must block:
        - Performance tables
        - Performance score columns
        - Response time tracking
        """
        # Tables
        assert self._matches_any_pattern("participant_performance", PROHIBITED_TABLE_PATTERNS)
        assert self._matches_any_pattern("cluster_metrics", PROHIBITED_TABLE_PATTERNS)
        assert self._matches_any_pattern("participant_scores", PROHIBITED_TABLE_PATTERNS)

        # Columns
        assert self._matches_any_pattern("performance_score", PROHIBITED_COLUMN_PATTERNS)
        assert self._matches_any_pattern("response_time_avg", PROHIBITED_COLUMN_PATTERNS)

    def test_fr62_coverage(self) -> None:
        """FR62: No completion rates per participant.

        Patterns must block:
        - Completion rate tables
        - Success/failure rate columns
        """
        # Tables
        assert self._matches_any_pattern("completion_rates", PROHIBITED_TABLE_PATTERNS)

        # Columns
        assert self._matches_any_pattern("completion_rate", PROHIBITED_COLUMN_PATTERNS)
        assert self._matches_any_pattern("success_rate", PROHIBITED_COLUMN_PATTERNS)
        assert self._matches_any_pattern("failure_rate", PROHIBITED_COLUMN_PATTERNS)

    def test_fr63_coverage(self) -> None:
        """FR63: No engagement or retention tracking.

        Patterns must block:
        - Engagement tables
        - Retention tables
        - Session tracking tables
        - Activity tracking columns
        """
        # Tables
        assert self._matches_any_pattern("user_engagement", PROHIBITED_TABLE_PATTERNS)
        assert self._matches_any_pattern("participant_retention", PROHIBITED_TABLE_PATTERNS)
        assert self._matches_any_pattern("session_tracking", PROHIBITED_TABLE_PATTERNS)

        # Columns
        assert self._matches_any_pattern("engagement_score", PROHIBITED_COLUMN_PATTERNS)
        assert self._matches_any_pattern("retention_score", PROHIBITED_COLUMN_PATTERNS)
        assert self._matches_any_pattern("session_count", PROHIBITED_COLUMN_PATTERNS)
        assert self._matches_any_pattern("login_count", PROHIBITED_COLUMN_PATTERNS)
        assert self._matches_any_pattern("last_active", PROHIBITED_COLUMN_PATTERNS)

    def _matches_any_pattern(self, name: str, patterns: list[str]) -> bool:
        """Check if name matches any pattern."""
        return any(re.match(pattern, name) for pattern in patterns)
