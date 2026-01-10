"""Unit tests for PublicTriggersService (Story 7.7, FR134).

Tests the application service for public access to cessation trigger conditions.

Constitutional Constraints Tested:
- FR134: Public documentation of cessation trigger conditions
- FR33: Threshold definitions SHALL be constitutional, not operational
- CT-11: Silent failure destroys legitimacy -> Service must be reliable
- CT-13: Integrity outranks availability -> Cache must not serve stale data
"""

import pytest
from datetime import datetime, timezone

from src.application.services.public_triggers_service import PublicTriggersService
from src.domain.models.cessation_trigger_condition import CessationTriggerConditionSet


class TestPublicTriggersService:
    """Tests for PublicTriggersService."""

    def test_get_trigger_conditions_returns_condition_set(self) -> None:
        """Test that get_trigger_conditions returns a CessationTriggerConditionSet."""
        service = PublicTriggersService()

        result = service.get_trigger_conditions()

        assert isinstance(result, CessationTriggerConditionSet)

    def test_get_trigger_conditions_returns_five_conditions(self) -> None:
        """Test that get_trigger_conditions returns exactly 5 conditions (FR134)."""
        service = PublicTriggersService()

        result = service.get_trigger_conditions()

        assert len(result.conditions) == 5

    def test_get_trigger_conditions_caches_result(self) -> None:
        """Test that get_trigger_conditions caches the result."""
        service = PublicTriggersService()

        result1 = service.get_trigger_conditions()
        result2 = service.get_trigger_conditions()

        # Should return the same cached instance
        assert result1 is result2

    def test_get_trigger_condition_returns_specific_condition(self) -> None:
        """Test that get_trigger_condition returns a specific condition."""
        service = PublicTriggersService()

        result = service.get_trigger_condition("breach_threshold")

        assert result is not None
        assert result.trigger_type == "breach_threshold"
        assert result.threshold == 10
        assert result.fr_reference == "FR32"

    def test_get_trigger_condition_returns_none_for_unknown_type(self) -> None:
        """Test that get_trigger_condition returns None for unknown types."""
        service = PublicTriggersService()

        result = service.get_trigger_condition("nonexistent_type")

        assert result is None

    def test_invalidate_cache_clears_cached_conditions(self) -> None:
        """Test that invalidate_cache clears the cached conditions (CT-11)."""
        service = PublicTriggersService()

        # Populate cache
        _ = service.get_trigger_conditions()
        assert service._cached_conditions is not None

        # Invalidate
        service.invalidate_cache()

        assert service._cached_conditions is None
        assert service._cache_timestamp is None

    def test_invalidate_cache_causes_refresh_on_next_access(self) -> None:
        """Test that invalidate_cache causes a refresh on next access."""
        service = PublicTriggersService()

        # Populate cache
        result1 = service.get_trigger_conditions()
        cache_timestamp1 = service._cache_timestamp

        # Invalidate
        service.invalidate_cache()

        # Access again - should refresh
        result2 = service.get_trigger_conditions()
        cache_timestamp2 = service._cache_timestamp

        # Should be a new instance with a new timestamp
        assert result1 is not result2
        assert cache_timestamp2 > cache_timestamp1  # type: ignore[operator]

    def test_get_cache_status_returns_correct_info_when_empty(self) -> None:
        """Test that get_cache_status returns correct info when cache is empty."""
        service = PublicTriggersService()

        status = service.get_cache_status()

        assert status["cache_populated"] is False
        assert status["cache_age_seconds"] is None
        assert status["condition_count"] == 0

    def test_get_cache_status_returns_correct_info_when_populated(self) -> None:
        """Test that get_cache_status returns correct info when cache is populated."""
        service = PublicTriggersService()

        # Populate cache
        _ = service.get_trigger_conditions()

        status = service.get_cache_status()

        assert status["cache_populated"] is True
        assert isinstance(status["cache_age_seconds"], float)
        assert status["cache_age_seconds"] >= 0
        assert status["condition_count"] == 5

    def test_service_returns_conditions_from_registry(self) -> None:
        """Test that service returns conditions sourced from registry (FR33)."""
        service = PublicTriggersService()

        result = service.get_trigger_conditions()

        # Check all expected trigger types are present
        trigger_types = {c.trigger_type for c in result.conditions}
        expected = {
            "consecutive_failures",
            "rolling_window",
            "anti_success_sustained",
            "petition_threshold",
            "breach_threshold",
        }
        assert trigger_types == expected

    def test_service_returns_constitutional_floors(self) -> None:
        """Test that conditions include constitutional floors (FR33)."""
        service = PublicTriggersService()

        result = service.get_trigger_conditions()

        for condition in result.conditions:
            assert condition.constitutional_floor is not None
            assert condition.threshold >= condition.constitutional_floor


class TestPublicTriggersServiceTriggerTypes:
    """Tests for specific trigger types returned by PublicTriggersService."""

    def test_consecutive_failures_matches_fr37(self) -> None:
        """Test consecutive_failures matches FR37 requirements."""
        service = PublicTriggersService()

        condition = service.get_trigger_condition("consecutive_failures")

        assert condition is not None
        assert condition.threshold == 3
        assert condition.window_days == 30
        assert condition.fr_reference == "FR37"
        assert condition.constitutional_floor == 3

    def test_rolling_window_matches_rt4(self) -> None:
        """Test rolling_window matches RT-4 requirements."""
        service = PublicTriggersService()

        condition = service.get_trigger_condition("rolling_window")

        assert condition is not None
        assert condition.threshold == 5
        assert condition.window_days == 90
        assert condition.fr_reference == "RT-4"
        assert condition.constitutional_floor == 5

    def test_anti_success_sustained_matches_fr38(self) -> None:
        """Test anti_success_sustained matches FR38 requirements."""
        service = PublicTriggersService()

        condition = service.get_trigger_condition("anti_success_sustained")

        assert condition is not None
        assert condition.threshold == 90  # 90 days
        assert condition.window_days is None  # Not a rolling window
        assert condition.fr_reference == "FR38"
        assert condition.constitutional_floor == 90

    def test_petition_threshold_matches_fr39(self) -> None:
        """Test petition_threshold matches FR39 requirements."""
        service = PublicTriggersService()

        condition = service.get_trigger_condition("petition_threshold")

        assert condition is not None
        assert condition.threshold == 100  # 100 co-signers
        assert condition.window_days is None  # Not a rolling window
        assert condition.fr_reference == "FR39"
        assert condition.constitutional_floor == 100

    def test_breach_threshold_matches_fr32(self) -> None:
        """Test breach_threshold matches FR32 requirements."""
        service = PublicTriggersService()

        condition = service.get_trigger_condition("breach_threshold")

        assert condition is not None
        assert condition.threshold == 10  # >10 breaches
        assert condition.window_days == 90
        assert condition.fr_reference == "FR32"
        assert condition.constitutional_floor == 10
