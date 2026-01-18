"""Unit tests for SemanticScanResult and SemanticScannerProtocol (Story 9.7, FR110).

Tests the port interface definitions and result class behavior.
"""

from __future__ import annotations

import pytest

from src.application.ports.semantic_scanner import (
    DEFAULT_ANALYSIS_METHOD,
    SemanticScanResult,
)


class TestSemanticScanResultNoSuspicion:
    """Tests for SemanticScanResult.no_suspicion() factory method."""

    def test_no_suspicion_default_method(self) -> None:
        """Test no_suspicion uses default analysis method."""
        result = SemanticScanResult.no_suspicion()

        assert result.violation_suspected is False
        assert result.suspected_patterns == ()
        assert result.confidence_score == 0.0
        assert result.analysis_method == DEFAULT_ANALYSIS_METHOD
        assert result.analysis_method == "pattern_analysis"

    def test_no_suspicion_custom_method(self) -> None:
        """Test no_suspicion with custom analysis method."""
        result = SemanticScanResult.no_suspicion(method="custom_method")

        assert result.violation_suspected is False
        assert result.suspected_patterns == ()
        assert result.confidence_score == 0.0
        assert result.analysis_method == "custom_method"

    def test_no_suspicion_pattern_count_zero(self) -> None:
        """Test that pattern_count is 0 for no suspicion result."""
        result = SemanticScanResult.no_suspicion()

        assert result.pattern_count == 0


class TestSemanticScanResultWithSuspicion:
    """Tests for SemanticScanResult.with_suspicion() factory method."""

    def test_with_suspicion_single_pattern(self) -> None:
        """Test with_suspicion with single pattern."""
        result = SemanticScanResult.with_suspicion(
            patterns=("we think",),
            confidence=0.7,
        )

        assert result.violation_suspected is True
        assert result.suspected_patterns == ("we think",)
        assert result.confidence_score == 0.7
        assert result.analysis_method == DEFAULT_ANALYSIS_METHOD
        assert result.pattern_count == 1

    def test_with_suspicion_multiple_patterns(self) -> None:
        """Test with_suspicion with multiple patterns."""
        patterns = ("we think", "we feel", "we believe")
        result = SemanticScanResult.with_suspicion(
            patterns=patterns,
            confidence=0.9,
        )

        assert result.violation_suspected is True
        assert result.suspected_patterns == patterns
        assert result.confidence_score == 0.9
        assert result.pattern_count == 3

    def test_with_suspicion_custom_method(self) -> None:
        """Test with_suspicion with custom analysis method."""
        result = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.5,
            method="ml_classifier",
        )

        assert result.analysis_method == "ml_classifier"

    def test_with_suspicion_min_confidence(self) -> None:
        """Test with_suspicion at minimum valid confidence (0.0)."""
        result = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.0,
        )

        assert result.confidence_score == 0.0
        assert (
            result.violation_suspected is True
        )  # Still suspicious, just low confidence

    def test_with_suspicion_max_confidence(self) -> None:
        """Test with_suspicion at maximum confidence (1.0)."""
        result = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=1.0,
        )

        assert result.confidence_score == 1.0


class TestSemanticScanResultValidation:
    """Tests for SemanticScanResult validation."""

    def test_with_suspicion_empty_patterns_raises(self) -> None:
        """Test that empty patterns raises ValueError."""
        with pytest.raises(ValueError, match="FR110: patterns cannot be empty"):
            SemanticScanResult.with_suspicion(
                patterns=(),
                confidence=0.7,
            )

    def test_with_suspicion_negative_confidence_raises(self) -> None:
        """Test that negative confidence raises ValueError."""
        with pytest.raises(ValueError, match="FR110: confidence must be between"):
            SemanticScanResult.with_suspicion(
                patterns=("pattern",),
                confidence=-0.1,
            )

    def test_with_suspicion_confidence_above_one_raises(self) -> None:
        """Test that confidence > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="FR110: confidence must be between"):
            SemanticScanResult.with_suspicion(
                patterns=("pattern",),
                confidence=1.1,
            )

    def test_with_suspicion_confidence_way_above_one_raises(self) -> None:
        """Test that confidence way above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="FR110: confidence must be between"):
            SemanticScanResult.with_suspicion(
                patterns=("pattern",),
                confidence=5.0,
            )


class TestSemanticScanResultImmutability:
    """Tests for SemanticScanResult frozen dataclass behavior."""

    def test_result_is_immutable(self) -> None:
        """Test that result fields cannot be modified."""
        result = SemanticScanResult.no_suspicion()

        with pytest.raises(AttributeError):
            result.violation_suspected = True  # type: ignore

    def test_result_patterns_tuple_immutable(self) -> None:
        """Test that patterns tuple is immutable."""
        result = SemanticScanResult.with_suspicion(
            patterns=("a", "b"),
            confidence=0.5,
        )

        # Tuples are immutable by design
        assert isinstance(result.suspected_patterns, tuple)


class TestSemanticScanResultEquality:
    """Tests for SemanticScanResult equality comparison."""

    def test_equal_no_suspicion_results(self) -> None:
        """Test that identical no_suspicion results are equal."""
        result1 = SemanticScanResult.no_suspicion()
        result2 = SemanticScanResult.no_suspicion()

        assert result1 == result2

    def test_equal_suspicion_results(self) -> None:
        """Test that identical suspicion results are equal."""
        result1 = SemanticScanResult.with_suspicion(
            patterns=("p1", "p2"),
            confidence=0.8,
            method="test",
        )
        result2 = SemanticScanResult.with_suspicion(
            patterns=("p1", "p2"),
            confidence=0.8,
            method="test",
        )

        assert result1 == result2

    def test_different_confidence_not_equal(self) -> None:
        """Test that different confidence scores make results unequal."""
        result1 = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.7,
        )
        result2 = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.8,
        )

        assert result1 != result2

    def test_different_patterns_not_equal(self) -> None:
        """Test that different patterns make results unequal."""
        result1 = SemanticScanResult.with_suspicion(
            patterns=("a",),
            confidence=0.7,
        )
        result2 = SemanticScanResult.with_suspicion(
            patterns=("b",),
            confidence=0.7,
        )

        assert result1 != result2


class TestSemanticScanResultPatternCount:
    """Tests for pattern_count property."""

    def test_pattern_count_zero(self) -> None:
        """Test pattern_count is 0 for no suspicion."""
        result = SemanticScanResult.no_suspicion()
        assert result.pattern_count == 0

    def test_pattern_count_one(self) -> None:
        """Test pattern_count for single pattern."""
        result = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.5,
        )
        assert result.pattern_count == 1

    def test_pattern_count_many(self) -> None:
        """Test pattern_count for many patterns."""
        result = SemanticScanResult.with_suspicion(
            patterns=("a", "b", "c", "d", "e"),
            confidence=0.5,
        )
        assert result.pattern_count == 5


class TestDefaultAnalysisMethod:
    """Tests for DEFAULT_ANALYSIS_METHOD constant."""

    def test_default_method_value(self) -> None:
        """Test that default analysis method is 'pattern_analysis'."""
        assert DEFAULT_ANALYSIS_METHOD == "pattern_analysis"

    def test_default_used_in_no_suspicion(self) -> None:
        """Test default method used in no_suspicion factory."""
        result = SemanticScanResult.no_suspicion()
        assert result.analysis_method == DEFAULT_ANALYSIS_METHOD

    def test_default_used_in_with_suspicion(self) -> None:
        """Test default method used in with_suspicion factory."""
        result = SemanticScanResult.with_suspicion(
            patterns=("test",),
            confidence=0.5,
        )
        assert result.analysis_method == DEFAULT_ANALYSIS_METHOD
