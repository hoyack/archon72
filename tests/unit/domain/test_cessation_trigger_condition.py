"""Unit tests for CessationTriggerCondition domain model (Story 7.7, FR134).

Tests the domain model for public cessation trigger conditions.

Constitutional Constraints Tested:
- FR134: Public documentation of cessation trigger conditions
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR37: 3 consecutive failures in 30 days
- FR38: Anti-success alert sustained 90 days
- FR39: External observer petition with 100+ co-signers
- FR32: >10 unacknowledged breaches in 90-day window
- RT-4: 5 non-consecutive failures in 90-day rolling window
"""

from datetime import datetime

import pytest

from src.domain.models.cessation_trigger_condition import (
    CESSATION_TRIGGER_JSON_LD_CONTEXT,
    CessationTriggerCondition,
    CessationTriggerConditionSet,
)


class TestCessationTriggerCondition:
    """Tests for CessationTriggerCondition domain model."""

    def test_create_trigger_condition_with_window(self) -> None:
        """Test creating a trigger condition with a rolling window."""
        condition = CessationTriggerCondition(
            trigger_type="breach_threshold",
            threshold=10,
            window_days=90,
            description="Test description",
            fr_reference="FR32",
            constitutional_floor=10,
        )

        assert condition.trigger_type == "breach_threshold"
        assert condition.threshold == 10
        assert condition.window_days == 90
        assert condition.description == "Test description"
        assert condition.fr_reference == "FR32"
        assert condition.constitutional_floor == 10

    def test_create_trigger_condition_without_window(self) -> None:
        """Test creating a trigger condition without a rolling window (FR38)."""
        condition = CessationTriggerCondition(
            trigger_type="anti_success_sustained",
            threshold=90,
            window_days=None,
            description="Anti-success alert sustained for 90 days",
            fr_reference="FR38",
            constitutional_floor=90,
        )

        assert condition.trigger_type == "anti_success_sustained"
        assert condition.threshold == 90
        assert condition.window_days is None
        assert condition.fr_reference == "FR38"

    def test_trigger_condition_is_immutable(self) -> None:
        """Test that trigger conditions are immutable (frozen dataclass)."""
        condition = CessationTriggerCondition(
            trigger_type="test",
            threshold=5,
            window_days=30,
            description="Test",
            fr_reference="TEST",
            constitutional_floor=5,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            condition.threshold = 10  # type: ignore[misc]

    def test_trigger_condition_to_dict(self) -> None:
        """Test converting trigger condition to dict for JSON serialization."""
        condition = CessationTriggerCondition(
            trigger_type="breach_threshold",
            threshold=10,
            window_days=90,
            description="Test description",
            fr_reference="FR32",
            constitutional_floor=10,
        )

        result = condition.to_dict()

        assert result["trigger_type"] == "breach_threshold"
        assert result["threshold"] == 10
        assert result["window_days"] == 90
        assert result["description"] == "Test description"
        assert result["fr_reference"] == "FR32"
        assert result["constitutional_floor"] == 10

    def test_trigger_condition_to_dict_omits_none_window(self) -> None:
        """Test that to_dict omits window_days when None."""
        condition = CessationTriggerCondition(
            trigger_type="petition_threshold",
            threshold=100,
            window_days=None,
            description="100+ co-signers",
            fr_reference="FR39",
            constitutional_floor=100,
        )

        result = condition.to_dict()

        assert "window_days" not in result

    def test_trigger_condition_to_json_ld(self) -> None:
        """Test converting trigger condition to JSON-LD format (FR134 AC5)."""
        condition = CessationTriggerCondition(
            trigger_type="breach_threshold",
            threshold=10,
            window_days=90,
            description="Test description",
            fr_reference="FR32",
            constitutional_floor=10,
        )

        result = condition.to_json_ld()

        assert result["@type"] == "cessation:TriggerCondition"
        assert result["trigger_type"] == "breach_threshold"
        assert result["threshold"] == 10

    def test_trigger_condition_equality(self) -> None:
        """Test that equal conditions are equal."""
        condition1 = CessationTriggerCondition(
            trigger_type="test",
            threshold=5,
            window_days=30,
            description="Test",
            fr_reference="TEST",
            constitutional_floor=5,
        )
        condition2 = CessationTriggerCondition(
            trigger_type="test",
            threshold=5,
            window_days=30,
            description="Test",
            fr_reference="TEST",
            constitutional_floor=5,
        )

        assert condition1 == condition2


class TestCessationTriggerConditionSet:
    """Tests for CessationTriggerConditionSet domain model."""

    def test_from_registry_creates_five_conditions(self) -> None:
        """Test that from_registry() creates exactly 5 trigger conditions (FR134)."""
        condition_set = CessationTriggerConditionSet.from_registry()

        assert len(condition_set.conditions) == 5
        assert len(condition_set) == 5

    def test_from_registry_includes_consecutive_failures(self) -> None:
        """Test that from_registry includes consecutive_failures (FR37)."""
        condition_set = CessationTriggerConditionSet.from_registry()

        condition = condition_set.get_condition("consecutive_failures")

        assert condition is not None
        assert condition.threshold == 3
        assert condition.window_days == 30
        assert condition.fr_reference == "FR37"

    def test_from_registry_includes_rolling_window(self) -> None:
        """Test that from_registry includes rolling_window (RT-4)."""
        condition_set = CessationTriggerConditionSet.from_registry()

        condition = condition_set.get_condition("rolling_window")

        assert condition is not None
        assert condition.threshold == 5
        assert condition.window_days == 90
        assert condition.fr_reference == "RT-4"

    def test_from_registry_includes_anti_success_sustained(self) -> None:
        """Test that from_registry includes anti_success_sustained (FR38)."""
        condition_set = CessationTriggerConditionSet.from_registry()

        condition = condition_set.get_condition("anti_success_sustained")

        assert condition is not None
        assert condition.threshold == 90  # 90 days sustained
        assert condition.window_days is None  # Not a rolling window
        assert condition.fr_reference == "FR38"

    def test_from_registry_includes_petition_threshold(self) -> None:
        """Test that from_registry includes petition_threshold (FR39)."""
        condition_set = CessationTriggerConditionSet.from_registry()

        condition = condition_set.get_condition("petition_threshold")

        assert condition is not None
        assert condition.threshold == 100  # 100+ co-signers
        assert condition.window_days is None  # Not a rolling window
        assert condition.fr_reference == "FR39"

    def test_from_registry_includes_breach_threshold(self) -> None:
        """Test that from_registry includes breach_threshold (FR32)."""
        condition_set = CessationTriggerConditionSet.from_registry()

        condition = condition_set.get_condition("breach_threshold")

        assert condition is not None
        assert condition.threshold == 10  # >10 unacknowledged breaches
        assert condition.window_days == 90
        assert condition.fr_reference == "FR32"

    def test_get_condition_returns_none_for_unknown_type(self) -> None:
        """Test that get_condition returns None for unknown types."""
        condition_set = CessationTriggerConditionSet.from_registry()

        result = condition_set.get_condition("nonexistent_type")

        assert result is None

    def test_condition_set_has_version_metadata(self) -> None:
        """Test that condition set includes version metadata."""
        condition_set = CessationTriggerConditionSet.from_registry()

        assert condition_set.schema_version == "1.0.0"
        assert condition_set.constitution_version == "1.0.0"
        assert isinstance(condition_set.effective_date, datetime)
        assert isinstance(condition_set.last_updated, datetime)

    def test_condition_set_to_dict(self) -> None:
        """Test converting condition set to dict for JSON serialization."""
        condition_set = CessationTriggerConditionSet.from_registry()

        result = condition_set.to_dict()

        assert "schema_version" in result
        assert "constitution_version" in result
        assert "effective_date" in result
        assert "last_updated" in result
        assert "trigger_conditions" in result
        assert len(result["trigger_conditions"]) == 5

    def test_condition_set_to_json_ld(self) -> None:
        """Test converting condition set to JSON-LD format (FR134 AC5)."""
        condition_set = CessationTriggerConditionSet.from_registry()

        result = condition_set.to_json_ld()

        assert "@context" in result
        assert result["@type"] == "cessation:TriggerConditionSet"
        assert "trigger_conditions" in result

        # Check that trigger conditions have @type annotations
        for condition in result["trigger_conditions"]:
            assert condition["@type"] == "cessation:TriggerCondition"

    def test_condition_set_iterable(self) -> None:
        """Test that condition set is iterable."""
        condition_set = CessationTriggerConditionSet.from_registry()

        trigger_types = [c.trigger_type for c in condition_set]

        assert len(trigger_types) == 5
        assert "consecutive_failures" in trigger_types
        assert "rolling_window" in trigger_types
        assert "anti_success_sustained" in trigger_types
        assert "petition_threshold" in trigger_types
        assert "breach_threshold" in trigger_types


class TestCessationTriggerJsonLdContext:
    """Tests for JSON-LD context constant."""

    def test_json_ld_context_has_required_vocabulary(self) -> None:
        """Test that JSON-LD context defines required vocabulary."""
        context = CESSATION_TRIGGER_JSON_LD_CONTEXT["@context"]

        assert "cessation" in context
        assert "trigger_type" in context
        assert "threshold" in context
        assert "window_days" in context
        assert "description" in context
        assert "fr_reference" in context
        assert "constitutional_floor" in context
        assert "TriggerCondition" in context
        assert "TriggerConditionSet" in context

    def test_json_ld_context_uses_archon72_namespace(self) -> None:
        """Test that JSON-LD context uses archon72.org namespace."""
        context = CESSATION_TRIGGER_JSON_LD_CONTEXT["@context"]

        assert "archon72.org" in context["cessation"]
