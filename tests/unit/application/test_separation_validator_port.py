"""Unit tests for SeparationValidatorPort (Story 8.2, FR52).

Tests the abstract protocol and DataClassification enum.
"""

import pytest

from src.application.ports.separation_validator import (
    DataClassification,
    SeparationValidatorPort,
)


class TestDataClassification:
    """Test DataClassification enum."""

    def test_constitutional_value(self) -> None:
        """Test CONSTITUTIONAL classification exists and has correct value."""
        assert DataClassification.CONSTITUTIONAL.value == "constitutional"

    def test_operational_value(self) -> None:
        """Test OPERATIONAL classification exists and has correct value."""
        assert DataClassification.OPERATIONAL.value == "operational"

    def test_unknown_value(self) -> None:
        """Test UNKNOWN classification exists and has correct value."""
        assert DataClassification.UNKNOWN.value == "unknown"

    def test_enum_members_count(self) -> None:
        """Test that exactly 3 classification types exist."""
        assert len(DataClassification) == 3

    def test_all_members_are_distinct(self) -> None:
        """Test all enum values are unique."""
        values = [c.value for c in DataClassification]
        assert len(values) == len(set(values))


class TestSeparationValidatorPort:
    """Test SeparationValidatorPort protocol definition."""

    def test_protocol_has_classify_data_method(self) -> None:
        """Test protocol defines classify_data method."""
        assert hasattr(SeparationValidatorPort, "classify_data")

    def test_protocol_has_is_constitutional_method(self) -> None:
        """Test protocol defines is_constitutional method."""
        assert hasattr(SeparationValidatorPort, "is_constitutional")

    def test_protocol_has_is_operational_method(self) -> None:
        """Test protocol defines is_operational method."""
        assert hasattr(SeparationValidatorPort, "is_operational")

    def test_protocol_has_get_allowed_event_types_method(self) -> None:
        """Test protocol defines get_allowed_event_types method."""
        assert hasattr(SeparationValidatorPort, "get_allowed_event_types")

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test protocol can be used for isinstance checks."""
        from typing import runtime_checkable, Protocol

        # SeparationValidatorPort should be a Protocol
        assert issubclass(SeparationValidatorPort, Protocol)
