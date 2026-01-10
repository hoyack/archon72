"""Unit tests for HaltStatusHeader value object (Story 3.5, Task 3.5).

Tests the HaltStatusHeader that is included in read responses
to indicate system halt state.
"""

from datetime import datetime, timezone

import pytest

from src.domain.models.halt_status_header import (
    SYSTEM_STATUS_HALTED,
    SYSTEM_STATUS_OPERATIONAL,
    HaltStatusHeader,
)


class TestHaltStatusHeaderOperational:
    """Tests for operational (not halted) status."""

    def test_operational_factory_creates_correct_status(self) -> None:
        """Verify operational() returns OPERATIONAL status."""
        header = HaltStatusHeader.operational()
        assert header.system_status == SYSTEM_STATUS_OPERATIONAL
        assert header.system_status == "OPERATIONAL"

    def test_operational_has_no_halt_reason(self) -> None:
        """Verify operational status has no halt reason."""
        header = HaltStatusHeader.operational()
        assert header.halt_reason is None

    def test_operational_has_no_halted_at(self) -> None:
        """Verify operational status has no halted_at timestamp."""
        header = HaltStatusHeader.operational()
        assert header.halted_at is None

    def test_operational_is_halted_property_returns_false(self) -> None:
        """Verify is_halted property returns False for operational."""
        header = HaltStatusHeader.operational()
        assert header.is_halted is False


class TestHaltStatusHeaderHalted:
    """Tests for halted status."""

    def test_halted_factory_creates_correct_status(self) -> None:
        """Verify halted() returns HALTED status."""
        header = HaltStatusHeader.halted(reason="test")
        assert header.system_status == SYSTEM_STATUS_HALTED
        assert header.system_status == "HALTED"

    def test_halted_preserves_reason(self) -> None:
        """Verify halted status preserves halt reason."""
        reason = "FR17: Fork detected"
        header = HaltStatusHeader.halted(reason=reason)
        assert header.halt_reason == reason

    def test_halted_with_explicit_timestamp(self) -> None:
        """Verify halted status uses explicit timestamp when provided."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        header = HaltStatusHeader.halted(reason="test", halted_at=timestamp)
        assert header.halted_at == timestamp

    def test_halted_without_timestamp_uses_now(self) -> None:
        """Verify halted status generates timestamp if not provided."""
        before = datetime.now(timezone.utc)
        header = HaltStatusHeader.halted(reason="test")
        after = datetime.now(timezone.utc)

        assert header.halted_at is not None
        assert before <= header.halted_at <= after

    def test_halted_is_halted_property_returns_true(self) -> None:
        """Verify is_halted property returns True for halted."""
        header = HaltStatusHeader.halted(reason="test")
        assert header.is_halted is True


class TestHaltStatusHeaderFromHaltState:
    """Tests for from_halt_state factory method."""

    def test_from_halt_state_false_creates_operational(self) -> None:
        """Verify from_halt_state(False) creates operational header."""
        header = HaltStatusHeader.from_halt_state(is_halted=False)
        assert header.system_status == "OPERATIONAL"
        assert header.halt_reason is None

    def test_from_halt_state_true_creates_halted(self) -> None:
        """Verify from_halt_state(True) creates halted header."""
        header = HaltStatusHeader.from_halt_state(
            is_halted=True,
            reason="Fork detected",
        )
        assert header.system_status == "HALTED"
        assert header.halt_reason == "Fork detected"

    def test_from_halt_state_true_without_reason_uses_unknown(self) -> None:
        """Verify from_halt_state(True) without reason uses 'Unknown'."""
        header = HaltStatusHeader.from_halt_state(is_halted=True)
        assert header.halt_reason == "Unknown"

    def test_from_halt_state_with_timestamp(self) -> None:
        """Verify from_halt_state passes through timestamp."""
        timestamp = datetime(2024, 1, 15, tzinfo=timezone.utc)
        header = HaltStatusHeader.from_halt_state(
            is_halted=True,
            reason="test",
            halted_at=timestamp,
        )
        assert header.halted_at == timestamp

    def test_from_halt_state_ignores_reason_when_not_halted(self) -> None:
        """Verify reason is ignored when is_halted=False."""
        header = HaltStatusHeader.from_halt_state(
            is_halted=False,
            reason="This should be ignored",
        )
        assert header.halt_reason is None


class TestHaltStatusHeaderImmutability:
    """Tests for immutability (frozen dataclass)."""

    def test_cannot_modify_system_status(self) -> None:
        """Verify system_status cannot be modified."""
        header = HaltStatusHeader.operational()
        with pytest.raises(AttributeError):
            header.system_status = "HALTED"  # type: ignore

    def test_cannot_modify_halt_reason(self) -> None:
        """Verify halt_reason cannot be modified."""
        header = HaltStatusHeader.halted(reason="original")
        with pytest.raises(AttributeError):
            header.halt_reason = "modified"  # type: ignore

    def test_cannot_modify_halted_at(self) -> None:
        """Verify halted_at cannot be modified."""
        header = HaltStatusHeader.halted(reason="test")
        with pytest.raises(AttributeError):
            header.halted_at = datetime.now(timezone.utc)  # type: ignore


class TestHaltStatusHeaderToDict:
    """Tests for to_dict serialization."""

    def test_operational_to_dict(self) -> None:
        """Verify operational header serializes correctly."""
        header = HaltStatusHeader.operational()
        result = header.to_dict()

        assert result == {
            "system_status": "OPERATIONAL",
            "halt_reason": None,
            "halted_at": None,
        }

    def test_halted_to_dict(self) -> None:
        """Verify halted header serializes correctly."""
        timestamp = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        header = HaltStatusHeader.halted(
            reason="FR17: Fork detected",
            halted_at=timestamp,
        )
        result = header.to_dict()

        assert result == {
            "system_status": "HALTED",
            "halt_reason": "FR17: Fork detected",
            "halted_at": "2024-01-15T12:30:45+00:00",
        }

    def test_halted_to_dict_with_none_timestamp(self) -> None:
        """Verify to_dict handles auto-generated timestamp."""
        header = HaltStatusHeader.halted(reason="test")
        result = header.to_dict()

        assert result["system_status"] == "HALTED"
        assert result["halt_reason"] == "test"
        # halted_at should be an ISO string, not None
        assert result["halted_at"] is not None
        assert isinstance(result["halted_at"], str)


class TestHaltStatusHeaderConstants:
    """Tests for module constants."""

    def test_system_status_operational_value(self) -> None:
        """Verify SYSTEM_STATUS_OPERATIONAL constant."""
        assert SYSTEM_STATUS_OPERATIONAL == "OPERATIONAL"

    def test_system_status_halted_value(self) -> None:
        """Verify SYSTEM_STATUS_HALTED constant."""
        assert SYSTEM_STATUS_HALTED == "HALTED"


class TestHaltStatusHeaderExports:
    """Tests verifying proper exports from package."""

    def test_halt_status_header_exported_from_models(self) -> None:
        """Verify HaltStatusHeader is exported from models __init__."""
        from src.domain.models import HaltStatusHeader as ExportedClass
        assert ExportedClass is HaltStatusHeader

    def test_constants_exported_from_models(self) -> None:
        """Verify constants are exported from models __init__."""
        from src.domain.models import SYSTEM_STATUS_HALTED as H
        from src.domain.models import SYSTEM_STATUS_OPERATIONAL as O
        assert H == "HALTED"
        assert O == "OPERATIONAL"
