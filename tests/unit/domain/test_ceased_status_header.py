"""Unit tests for CeasedStatusHeader (Story 7.4, FR41).

Tests the CeasedStatusHeader value object that indicates system
has permanently ceased operations.

Constitutional Constraints Tested:
- FR41: Freeze on new actions except record preservation
- CT-11: Status header provides transparency to observers
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestCeasedStatusHeaderConstants:
    """Test status constants for ceased state."""

    def test_system_status_ceased_constant_value(self) -> None:
        """SYSTEM_STATUS_CEASED should be 'CEASED'."""
        from src.domain.models.ceased_status_header import SYSTEM_STATUS_CEASED

        assert SYSTEM_STATUS_CEASED == "CEASED"

    def test_system_status_ceased_is_string(self) -> None:
        """SYSTEM_STATUS_CEASED should be a string."""
        from src.domain.models.ceased_status_header import SYSTEM_STATUS_CEASED

        assert isinstance(SYSTEM_STATUS_CEASED, str)


class TestCeasedStatusHeaderCreation:
    """Test CeasedStatusHeader creation."""

    def test_create_with_all_fields(self) -> None:
        """Should create header with all required fields."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        header = CeasedStatusHeader(
            system_status="CEASED",
            ceased_at=ceased_at,
            final_sequence_number=12345,
            cessation_reason="Unanimous vote for cessation",
        )

        assert header.system_status == "CEASED"
        assert header.ceased_at == ceased_at
        assert header.final_sequence_number == 12345
        assert header.cessation_reason == "Unanimous vote for cessation"

    def test_header_is_frozen(self) -> None:
        """CeasedStatusHeader should be immutable (frozen dataclass)."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        ceased_at = datetime.now(timezone.utc)
        header = CeasedStatusHeader(
            system_status="CEASED",
            ceased_at=ceased_at,
            final_sequence_number=100,
            cessation_reason="Test",
        )

        with pytest.raises(AttributeError):
            header.system_status = "OPERATIONAL"  # type: ignore[misc]


class TestCeasedStatusHeaderFactoryMethods:
    """Test CeasedStatusHeader factory methods."""

    def test_ceased_factory_creates_correct_header(self) -> None:
        """ceased() factory should create header with CEASED status."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        header = CeasedStatusHeader.ceased(
            ceased_at=ceased_at,
            final_sequence_number=500,
            reason="Integrity failure",
        )

        assert header.system_status == "CEASED"
        assert header.ceased_at == ceased_at
        assert header.final_sequence_number == 500
        assert header.cessation_reason == "Integrity failure"

    def test_ceased_factory_defaults_to_now_if_no_timestamp(self) -> None:
        """ceased() should default ceased_at to current time if not provided."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        before = datetime.now(timezone.utc)
        header = CeasedStatusHeader.ceased(
            final_sequence_number=100,
            reason="Test cessation",
        )
        after = datetime.now(timezone.utc)

        assert before <= header.ceased_at <= after

    def test_from_cessation_details_creates_header(self) -> None:
        """from_cessation_details() should create header from details object."""
        from src.domain.models.ceased_status_header import (
            CeasedStatusHeader,
            CessationDetails,
        )

        details = CessationDetails(
            ceased_at=datetime(2024, 6, 15, tzinfo=timezone.utc),
            final_sequence_number=999,
            reason="Breach threshold exceeded",
            cessation_event_id=uuid4(),
        )

        header = CeasedStatusHeader.from_cessation_details(details)

        assert header.system_status == "CEASED"
        assert header.ceased_at == details.ceased_at
        assert header.final_sequence_number == 999
        assert header.cessation_reason == "Breach threshold exceeded"


class TestCeasedStatusHeaderProperties:
    """Test CeasedStatusHeader computed properties."""

    def test_is_ceased_returns_true(self) -> None:
        """is_ceased property should return True for ceased header."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        header = CeasedStatusHeader.ceased(
            final_sequence_number=100,
            reason="Test",
        )

        assert header.is_ceased is True

    def test_is_permanent_returns_true(self) -> None:
        """is_permanent property should return True (cessation is irreversible)."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        header = CeasedStatusHeader.ceased(
            final_sequence_number=100,
            reason="Test",
        )

        assert header.is_permanent is True


class TestCeasedStatusHeaderSerialization:
    """Test CeasedStatusHeader serialization."""

    def test_to_dict_returns_correct_structure(self) -> None:
        """to_dict() should return dictionary for JSON serialization."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        ceased_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        header = CeasedStatusHeader(
            system_status="CEASED",
            ceased_at=ceased_at,
            final_sequence_number=12345,
            cessation_reason="Unanimous vote",
        )

        result = header.to_dict()

        assert result["system_status"] == "CEASED"
        assert result["ceased_at"] == "2024-06-15T12:30:00+00:00"
        assert result["final_sequence_number"] == 12345
        assert result["cessation_reason"] == "Unanimous vote"

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict() should include all header fields."""
        from src.domain.models.ceased_status_header import CeasedStatusHeader

        header = CeasedStatusHeader.ceased(
            final_sequence_number=100,
            reason="Test",
        )

        result = header.to_dict()

        assert "system_status" in result
        assert "ceased_at" in result
        assert "final_sequence_number" in result
        assert "cessation_reason" in result


class TestCessationDetails:
    """Test CessationDetails value object."""

    def test_create_cessation_details(self) -> None:
        """Should create CessationDetails with all fields."""
        from src.domain.models.ceased_status_header import CessationDetails

        event_id = uuid4()
        ceased_at = datetime.now(timezone.utc)

        details = CessationDetails(
            ceased_at=ceased_at,
            final_sequence_number=500,
            reason="Test",
            cessation_event_id=event_id,
        )

        assert details.ceased_at == ceased_at
        assert details.final_sequence_number == 500
        assert details.reason == "Test"
        assert details.cessation_event_id == event_id

    def test_cessation_details_is_frozen(self) -> None:
        """CessationDetails should be immutable."""
        from src.domain.models.ceased_status_header import CessationDetails

        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        with pytest.raises(AttributeError):
            details.reason = "Changed"  # type: ignore[misc]


class TestExportFromInit:
    """Test exports from domain.models.__init__.py."""

    def test_ceased_status_header_exported(self) -> None:
        """CeasedStatusHeader should be exported from domain.models."""
        from src.domain.models import CeasedStatusHeader

        assert CeasedStatusHeader is not None

    def test_system_status_ceased_constant_exported(self) -> None:
        """SYSTEM_STATUS_CEASED should be exported from domain.models."""
        from src.domain.models import SYSTEM_STATUS_CEASED

        assert SYSTEM_STATUS_CEASED == "CEASED"

    def test_cessation_details_exported(self) -> None:
        """CessationDetails should be exported from domain.models."""
        from src.domain.models import CessationDetails

        assert CessationDetails is not None
