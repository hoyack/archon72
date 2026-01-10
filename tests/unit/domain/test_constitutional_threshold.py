"""Unit tests for ConstitutionalThreshold model (Story 6.4, FR33).

Tests the ConstitutionalThreshold frozen dataclass and ConstitutionalThresholdRegistry.
"""

import pytest

from src.domain.errors.threshold import ConstitutionalFloorViolationError
from src.domain.models.constitutional_threshold import (
    ConstitutionalThreshold,
    ConstitutionalThresholdRegistry,
)


class TestConstitutionalThreshold:
    """Tests for ConstitutionalThreshold model."""

    def test_create_valid_threshold(self) -> None:
        """Test creating a valid threshold with required fields (AC1)."""
        threshold = ConstitutionalThreshold(
            threshold_name="test_threshold",
            constitutional_floor=10,
            current_value=15,
            is_constitutional=True,
            description="Test threshold description",
            fr_reference="FR33",
        )

        assert threshold.threshold_name == "test_threshold"
        assert threshold.constitutional_floor == 10
        assert threshold.current_value == 15
        assert threshold.is_constitutional is True
        assert threshold.description == "Test threshold description"
        assert threshold.fr_reference == "FR33"

    def test_is_valid_returns_true_when_current_at_floor(self) -> None:
        """Test is_valid returns True when current equals floor."""
        threshold = ConstitutionalThreshold(
            threshold_name="test",
            constitutional_floor=10,
            current_value=10,  # Exactly at floor
            is_constitutional=True,
            description="Test",
            fr_reference="FR33",
        )

        assert threshold.is_valid is True

    def test_is_valid_returns_true_when_current_above_floor(self) -> None:
        """Test is_valid returns True when current exceeds floor."""
        threshold = ConstitutionalThreshold(
            threshold_name="test",
            constitutional_floor=10,
            current_value=15,  # Above floor
            is_constitutional=True,
            description="Test",
            fr_reference="FR33",
        )

        assert threshold.is_valid is True

    def test_validate_passes_when_valid(self) -> None:
        """Test validate() passes without raising when threshold is valid."""
        threshold = ConstitutionalThreshold(
            threshold_name="test",
            constitutional_floor=10,
            current_value=10,
            is_constitutional=True,
            description="Test",
            fr_reference="FR33",
        )

        # Should not raise
        threshold.validate()

    def test_post_init_rejects_below_floor_value(self) -> None:
        """Test __post_init__ raises ConstitutionalFloorViolationError for invalid values (AC2)."""
        with pytest.raises(ConstitutionalFloorViolationError) as exc_info:
            ConstitutionalThreshold(
                threshold_name="test",
                constitutional_floor=10,
                current_value=5,  # Below floor
                is_constitutional=True,
                description="Test",
                fr_reference="FR33",
            )

        assert "FR33: Constitutional floor violation" in str(exc_info.value)
        assert exc_info.value.threshold_name == "test"
        assert exc_info.value.attempted_value == 5
        assert exc_info.value.constitutional_floor == 10

    def test_to_dict_returns_expected_structure(self) -> None:
        """Test to_dict() returns a dict with all fields."""
        threshold = ConstitutionalThreshold(
            threshold_name="test",
            constitutional_floor=10,
            current_value=15,
            is_constitutional=True,
            description="Test description",
            fr_reference="FR33",
        )

        result = threshold.to_dict()

        assert isinstance(result, dict)
        assert result["threshold_name"] == "test"
        assert result["constitutional_floor"] == 10
        assert result["current_value"] == 15
        assert result["is_constitutional"] is True
        assert result["description"] == "Test description"
        assert result["fr_reference"] == "FR33"

    def test_threshold_is_frozen_immutable(self) -> None:
        """Test threshold is immutable (frozen dataclass)."""
        threshold = ConstitutionalThreshold(
            threshold_name="test",
            constitutional_floor=10,
            current_value=15,
            is_constitutional=True,
            description="Test",
            fr_reference="FR33",
        )

        with pytest.raises(AttributeError):
            threshold.current_value = 20  # type: ignore[misc]

    def test_threshold_with_float_values(self) -> None:
        """Test threshold works with float values."""
        threshold = ConstitutionalThreshold(
            threshold_name="diversity",
            constitutional_floor=0.30,
            current_value=0.35,
            is_constitutional=True,
            description="Diversity threshold",
            fr_reference="FR73",
        )

        assert threshold.constitutional_floor == 0.30
        assert threshold.current_value == 0.35
        assert threshold.is_valid is True


class TestConstitutionalThresholdRegistry:
    """Tests for ConstitutionalThresholdRegistry."""

    def test_get_all_thresholds_returns_tuple(self) -> None:
        """Test get_all_thresholds returns tuple of thresholds."""
        t1 = ConstitutionalThreshold(
            threshold_name="t1",
            constitutional_floor=10,
            current_value=10,
            is_constitutional=True,
            description="Test 1",
            fr_reference="FR33",
        )
        t2 = ConstitutionalThreshold(
            threshold_name="t2",
            constitutional_floor=5,
            current_value=5,
            is_constitutional=True,
            description="Test 2",
            fr_reference="FR34",
        )

        registry = ConstitutionalThresholdRegistry(thresholds=(t1, t2))

        result = registry.get_all_thresholds()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert t1 in result
        assert t2 in result

    def test_get_threshold_returns_correct_threshold(self) -> None:
        """Test get_threshold returns threshold with matching name."""
        t1 = ConstitutionalThreshold(
            threshold_name="target",
            constitutional_floor=10,
            current_value=10,
            is_constitutional=True,
            description="Target threshold",
            fr_reference="FR33",
        )
        t2 = ConstitutionalThreshold(
            threshold_name="other",
            constitutional_floor=5,
            current_value=5,
            is_constitutional=True,
            description="Other threshold",
            fr_reference="FR34",
        )

        registry = ConstitutionalThresholdRegistry(thresholds=(t1, t2))

        result = registry.get_threshold("target")

        assert result == t1

    def test_get_threshold_raises_for_unknown_name(self) -> None:
        """Test get_threshold raises KeyError for unknown threshold."""
        t1 = ConstitutionalThreshold(
            threshold_name="known",
            constitutional_floor=10,
            current_value=10,
            is_constitutional=True,
            description="Known threshold",
            fr_reference="FR33",
        )

        registry = ConstitutionalThresholdRegistry(thresholds=(t1,))

        with pytest.raises(KeyError) as exc_info:
            registry.get_threshold("unknown")

        assert "unknown" in str(exc_info.value)

    def test_validate_all_passes_with_valid_thresholds(self) -> None:
        """Test validate_all passes when all thresholds are valid."""
        t1 = ConstitutionalThreshold(
            threshold_name="t1",
            constitutional_floor=10,
            current_value=10,
            is_constitutional=True,
            description="Test 1",
            fr_reference="FR33",
        )
        t2 = ConstitutionalThreshold(
            threshold_name="t2",
            constitutional_floor=5,
            current_value=8,
            is_constitutional=True,
            description="Test 2",
            fr_reference="FR34",
        )

        registry = ConstitutionalThresholdRegistry(thresholds=(t1, t2))

        # Should not raise
        registry.validate_all()

    def test_registry_len(self) -> None:
        """Test __len__ returns number of thresholds."""
        t1 = ConstitutionalThreshold(
            threshold_name="t1",
            constitutional_floor=10,
            current_value=10,
            is_constitutional=True,
            description="Test 1",
            fr_reference="FR33",
        )
        t2 = ConstitutionalThreshold(
            threshold_name="t2",
            constitutional_floor=5,
            current_value=5,
            is_constitutional=True,
            description="Test 2",
            fr_reference="FR34",
        )

        registry = ConstitutionalThresholdRegistry(thresholds=(t1, t2))

        assert len(registry) == 2

    def test_registry_iteration(self) -> None:
        """Test registry can be iterated."""
        t1 = ConstitutionalThreshold(
            threshold_name="t1",
            constitutional_floor=10,
            current_value=10,
            is_constitutional=True,
            description="Test 1",
            fr_reference="FR33",
        )

        registry = ConstitutionalThresholdRegistry(thresholds=(t1,))

        iterated = list(registry)

        assert iterated == [t1]
