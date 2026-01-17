"""Unit tests for HaltStatus domain model.

Story: consent-gov-4.1 (Halt Circuit Port & Adapter)
Tests: Task 2 - HaltStatus domain model
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.halt import HaltedException, HaltReason, HaltStatus


class TestHaltReason:
    """Tests for HaltReason enum."""

    def test_operator_reason(self) -> None:
        """OPERATOR reason exists for human-triggered halts."""
        assert HaltReason.OPERATOR.value == "operator"

    def test_system_fault_reason(self) -> None:
        """SYSTEM_FAULT reason exists for detected faults."""
        assert HaltReason.SYSTEM_FAULT.value == "system_fault"

    def test_integrity_violation_reason(self) -> None:
        """INTEGRITY_VIOLATION reason exists for hash chain breaks etc."""
        assert HaltReason.INTEGRITY_VIOLATION.value == "integrity_violation"

    def test_consensus_failure_reason(self) -> None:
        """CONSENSUS_FAILURE reason exists for quorum loss etc."""
        assert HaltReason.CONSENSUS_FAILURE.value == "consensus_failure"

    def test_constitutional_breach_reason(self) -> None:
        """CONSTITUTIONAL_BREACH reason exists for CT violations."""
        assert HaltReason.CONSTITUTIONAL_BREACH.value == "constitutional_breach"

    def test_all_reasons_have_unique_values(self) -> None:
        """All HaltReason values are unique."""
        values = [r.value for r in HaltReason]
        assert len(values) == len(set(values))


class TestHaltStatusNotHalted:
    """Tests for HaltStatus.not_halted() factory."""

    def test_not_halted_is_false(self) -> None:
        """not_halted() returns status with is_halted=False."""
        status = HaltStatus.not_halted()
        assert status.is_halted is False

    def test_not_halted_has_no_timestamp(self) -> None:
        """not_halted() has no halted_at timestamp."""
        status = HaltStatus.not_halted()
        assert status.halted_at is None

    def test_not_halted_has_no_reason(self) -> None:
        """not_halted() has no reason."""
        status = HaltStatus.not_halted()
        assert status.reason is None

    def test_not_halted_has_no_operator_id(self) -> None:
        """not_halted() has no operator_id."""
        status = HaltStatus.not_halted()
        assert status.operator_id is None

    def test_not_halted_has_no_message(self) -> None:
        """not_halted() has no message."""
        status = HaltStatus.not_halted()
        assert status.message is None

    def test_not_halted_has_no_trace_id(self) -> None:
        """not_halted() has no trace_id."""
        status = HaltStatus.not_halted()
        assert status.trace_id is None


class TestHaltStatusHalted:
    """Tests for HaltStatus.halted() factory."""

    def test_halted_is_true(self) -> None:
        """halted() returns status with is_halted=True."""
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test halt",
            halted_at=datetime.now(timezone.utc),
        )
        assert status.is_halted is True

    def test_halted_has_timestamp(self) -> None:
        """halted() includes provided timestamp."""
        timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test halt",
            halted_at=timestamp,
        )
        assert status.halted_at == timestamp

    def test_halted_has_reason(self) -> None:
        """halted() includes provided reason."""
        status = HaltStatus.halted(
            reason=HaltReason.INTEGRITY_VIOLATION,
            message="Hash chain break",
            halted_at=datetime.now(timezone.utc),
        )
        assert status.reason == HaltReason.INTEGRITY_VIOLATION

    def test_halted_has_message(self) -> None:
        """halted() includes provided message."""
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Emergency maintenance window",
            halted_at=datetime.now(timezone.utc),
        )
        assert status.message == "Emergency maintenance window"

    def test_halted_with_operator_id(self) -> None:
        """halted() can include operator_id."""
        operator_id = uuid4()
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test halt",
            halted_at=datetime.now(timezone.utc),
            operator_id=operator_id,
        )
        assert status.operator_id == operator_id

    def test_halted_without_operator_id(self) -> None:
        """halted() operator_id defaults to None (system-triggered)."""
        status = HaltStatus.halted(
            reason=HaltReason.SYSTEM_FAULT,
            message="Detected fault",
            halted_at=datetime.now(timezone.utc),
        )
        assert status.operator_id is None

    def test_halted_with_trace_id(self) -> None:
        """halted() can include trace_id for audit."""
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test halt",
            halted_at=datetime.now(timezone.utc),
            trace_id="abc-123-def",
        )
        assert status.trace_id == "abc-123-def"


class TestHaltStatusImmutability:
    """Tests for HaltStatus immutability (frozen dataclass)."""

    def test_status_is_frozen(self) -> None:
        """HaltStatus is immutable (frozen dataclass)."""
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test",
            halted_at=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            status.is_halted = False  # type: ignore

    def test_status_is_hashable(self) -> None:
        """HaltStatus is hashable (can be used in sets/dicts)."""
        status = HaltStatus.not_halted()
        # Should not raise
        hash(status)

    def test_equal_statuses_are_equal(self) -> None:
        """Equal HaltStatus objects compare equal."""
        timestamp = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        status1 = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test",
            halted_at=timestamp,
        )
        status2 = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test",
            halted_at=timestamp,
        )
        assert status1 == status2


class TestHaltStatusSerialization:
    """Tests for HaltStatus serialization (to_dict/from_dict)."""

    def test_to_dict_not_halted(self) -> None:
        """to_dict() serializes not_halted status correctly."""
        status = HaltStatus.not_halted()
        data = status.to_dict()

        assert data["is_halted"] is False
        assert data["halted_at"] is None
        assert data["reason"] is None
        assert data["operator_id"] is None
        assert data["message"] is None
        assert data["trace_id"] is None

    def test_to_dict_halted(self) -> None:
        """to_dict() serializes halted status correctly."""
        operator_id = uuid4()
        timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        status = HaltStatus.halted(
            reason=HaltReason.INTEGRITY_VIOLATION,
            message="Hash chain break detected",
            halted_at=timestamp,
            operator_id=operator_id,
            trace_id="trace-123",
        )
        data = status.to_dict()

        assert data["is_halted"] is True
        assert data["halted_at"] == "2026-01-15T10:30:00+00:00"
        assert data["reason"] == "integrity_violation"
        assert data["operator_id"] == str(operator_id)
        assert data["message"] == "Hash chain break detected"
        assert data["trace_id"] == "trace-123"

    def test_from_dict_not_halted(self) -> None:
        """from_dict() reconstructs not_halted status."""
        data = {
            "is_halted": False,
            "halted_at": None,
            "reason": None,
            "operator_id": None,
            "message": None,
            "trace_id": None,
        }
        status = HaltStatus.from_dict(data)

        assert status.is_halted is False
        assert status == HaltStatus.not_halted()

    def test_from_dict_halted(self) -> None:
        """from_dict() reconstructs halted status."""
        operator_id = uuid4()
        data = {
            "is_halted": True,
            "halted_at": "2026-01-15T10:30:00+00:00",
            "reason": "integrity_violation",
            "operator_id": str(operator_id),
            "message": "Hash chain break",
            "trace_id": "trace-456",
        }
        status = HaltStatus.from_dict(data)

        assert status.is_halted is True
        assert status.halted_at == datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert status.reason == HaltReason.INTEGRITY_VIOLATION
        assert status.operator_id == operator_id
        assert status.message == "Hash chain break"
        assert status.trace_id == "trace-456"

    def test_roundtrip_serialization(self) -> None:
        """to_dict() and from_dict() are inverse operations."""
        original = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test roundtrip",
            halted_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            operator_id=uuid4(),
            trace_id="roundtrip-test",
        )

        data = original.to_dict()
        reconstructed = HaltStatus.from_dict(data)

        assert reconstructed.is_halted == original.is_halted
        assert reconstructed.halted_at == original.halted_at
        assert reconstructed.reason == original.reason
        assert reconstructed.operator_id == original.operator_id
        assert reconstructed.message == original.message
        assert reconstructed.trace_id == original.trace_id


class TestHaltedException:
    """Tests for HaltedException."""

    def test_exception_has_status(self) -> None:
        """HaltedException includes the HaltStatus."""
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Emergency halt",
            halted_at=datetime.now(timezone.utc),
        )
        exc = HaltedException(status)

        assert exc.status is status

    def test_exception_message_includes_reason(self) -> None:
        """HaltedException message includes the reason."""
        status = HaltStatus.halted(
            reason=HaltReason.INTEGRITY_VIOLATION,
            message="Hash chain break",
            halted_at=datetime.now(timezone.utc),
        )
        exc = HaltedException(status)

        assert "integrity_violation" in str(exc)

    def test_exception_message_includes_description(self) -> None:
        """HaltedException message includes the halt message."""
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Emergency maintenance window",
            halted_at=datetime.now(timezone.utc),
        )
        exc = HaltedException(status)

        assert "Emergency maintenance window" in str(exc)

    def test_exception_repr(self) -> None:
        """HaltedException has informative repr."""
        status = HaltStatus.halted(
            reason=HaltReason.SYSTEM_FAULT,
            message="Fault detected",
            halted_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        exc = HaltedException(status)

        repr_str = repr(exc)
        assert "HaltedException" in repr_str
        assert "SYSTEM_FAULT" in repr_str

    def test_exception_is_catchable(self) -> None:
        """HaltedException can be caught and handled."""
        status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Test",
            halted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(HaltedException) as exc_info:
            raise HaltedException(status)

        assert exc_info.value.status == status
