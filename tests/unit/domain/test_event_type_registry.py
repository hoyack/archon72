"""Unit tests for EventTypeRegistry (Story 8.2, FR52).

Tests the centralized event type registry for constitutional/operational separation.
"""

import pytest

from src.domain.models.event_type_registry import EventTypeRegistry


class TestConstitutionalTypes:
    """Test CONSTITUTIONAL_TYPES frozenset."""

    def test_is_frozenset(self) -> None:
        """Test CONSTITUTIONAL_TYPES is a frozenset (immutable)."""
        assert isinstance(EventTypeRegistry.CONSTITUTIONAL_TYPES, frozenset)

    def test_is_non_empty(self) -> None:
        """Test CONSTITUTIONAL_TYPES is not empty."""
        assert len(EventTypeRegistry.CONSTITUTIONAL_TYPES) > 0

    def test_contains_deliberation_output(self) -> None:
        """Test contains deliberation_output event type."""
        assert "deliberation_output" in EventTypeRegistry.CONSTITUTIONAL_TYPES

    def test_contains_vote_cast(self) -> None:
        """Test contains vote_cast event type."""
        assert "vote_cast" in EventTypeRegistry.CONSTITUTIONAL_TYPES

    def test_contains_halt_triggered(self) -> None:
        """Test contains halt_triggered event type."""
        assert "halt_triggered" in EventTypeRegistry.CONSTITUTIONAL_TYPES

    def test_contains_fork_detected(self) -> None:
        """Test contains fork_detected event type."""
        assert "fork_detected" in EventTypeRegistry.CONSTITUTIONAL_TYPES

    def test_contains_cessation_executed(self) -> None:
        """Test contains cessation_executed event type."""
        assert "cessation_executed" in EventTypeRegistry.CONSTITUTIONAL_TYPES

    def test_contains_breach_declared(self) -> None:
        """Test contains breach_declared event type."""
        assert "breach_declared" in EventTypeRegistry.CONSTITUTIONAL_TYPES


class TestOperationalTypes:
    """Test OPERATIONAL_TYPES frozenset."""

    def test_is_frozenset(self) -> None:
        """Test OPERATIONAL_TYPES is a frozenset (immutable)."""
        assert isinstance(EventTypeRegistry.OPERATIONAL_TYPES, frozenset)

    def test_is_non_empty(self) -> None:
        """Test OPERATIONAL_TYPES is not empty."""
        assert len(EventTypeRegistry.OPERATIONAL_TYPES) > 0

    def test_contains_uptime_recorded(self) -> None:
        """Test contains uptime_recorded metric type."""
        assert "uptime_recorded" in EventTypeRegistry.OPERATIONAL_TYPES

    def test_contains_latency_measured(self) -> None:
        """Test contains latency_measured metric type."""
        assert "latency_measured" in EventTypeRegistry.OPERATIONAL_TYPES

    def test_contains_error_logged(self) -> None:
        """Test contains error_logged metric type."""
        assert "error_logged" in EventTypeRegistry.OPERATIONAL_TYPES

    def test_contains_health_check(self) -> None:
        """Test contains health_check metric type."""
        assert "health_check" in EventTypeRegistry.OPERATIONAL_TYPES


class TestNoOverlap:
    """Test that constitutional and operational types don't overlap."""

    def test_no_intersection(self) -> None:
        """Test constitutional and operational types have no overlap."""
        intersection = (
            EventTypeRegistry.CONSTITUTIONAL_TYPES
            & EventTypeRegistry.OPERATIONAL_TYPES
        )
        assert len(intersection) == 0, f"Overlap found: {intersection}"


class TestIsValidConstitutionalType:
    """Test is_valid_constitutional_type method."""

    def test_constitutional_type_returns_true(self) -> None:
        """Test constitutional type returns True."""
        assert EventTypeRegistry.is_valid_constitutional_type("deliberation_output")

    def test_operational_type_returns_false(self) -> None:
        """Test operational type returns False."""
        assert not EventTypeRegistry.is_valid_constitutional_type("uptime_recorded")

    def test_unknown_type_returns_false(self) -> None:
        """Test unknown type returns False."""
        assert not EventTypeRegistry.is_valid_constitutional_type("random_unknown")

    def test_empty_string_returns_false(self) -> None:
        """Test empty string returns False."""
        assert not EventTypeRegistry.is_valid_constitutional_type("")


class TestIsOperationalType:
    """Test is_operational_type method."""

    def test_operational_type_returns_true(self) -> None:
        """Test operational type returns True."""
        assert EventTypeRegistry.is_operational_type("uptime_recorded")

    def test_constitutional_type_returns_false(self) -> None:
        """Test constitutional type returns False."""
        assert not EventTypeRegistry.is_operational_type("deliberation_output")

    def test_unknown_type_returns_false(self) -> None:
        """Test unknown type returns False."""
        assert not EventTypeRegistry.is_operational_type("random_unknown")
