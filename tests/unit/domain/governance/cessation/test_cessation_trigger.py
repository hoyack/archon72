"""Unit tests for CessationTrigger domain model.

Story: consent-gov-8.1: System Cessation Trigger
AC1: Human Operator can trigger cessation (FR47)
AC4: Cessation requires Human Operator authentication
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.cessation import CessationTrigger


class TestCessationTriggerCreation:
    """Tests for CessationTrigger creation."""

    def test_create_valid_trigger(self) -> None:
        """Can create a valid CessationTrigger."""
        trigger_id = uuid4()
        operator_id = uuid4()
        now = datetime.now(timezone.utc)

        trigger = CessationTrigger(
            trigger_id=trigger_id,
            operator_id=operator_id,
            triggered_at=now,
            reason="Planned system retirement",
        )

        assert trigger.trigger_id == trigger_id
        assert trigger.operator_id == operator_id
        assert trigger.triggered_at == now
        assert trigger.reason == "Planned system retirement"

    def test_trigger_is_immutable(self) -> None:
        """CessationTrigger is immutable (frozen dataclass)."""
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason="Test reason",
        )

        with pytest.raises(AttributeError):
            trigger.reason = "Modified reason"  # type: ignore

    def test_reason_is_required(self) -> None:
        """Reason field is required and cannot be empty."""
        with pytest.raises(ValueError, match="reason is required"):
            CessationTrigger(
                trigger_id=uuid4(),
                operator_id=uuid4(),
                triggered_at=datetime.now(timezone.utc),
                reason="",
            )

    def test_whitespace_only_reason_rejected(self) -> None:
        """Whitespace-only reason is rejected."""
        with pytest.raises(ValueError, match="reason is required"):
            CessationTrigger(
                trigger_id=uuid4(),
                operator_id=uuid4(),
                triggered_at=datetime.now(timezone.utc),
                reason="   ",
            )


class TestCessationTriggerSerialization:
    """Tests for CessationTrigger serialization."""

    def test_to_dict(self) -> None:
        """Can serialize trigger to dictionary."""
        trigger_id = uuid4()
        operator_id = uuid4()
        now = datetime.now(timezone.utc)

        trigger = CessationTrigger(
            trigger_id=trigger_id,
            operator_id=operator_id,
            triggered_at=now,
            reason="Planned shutdown",
        )

        data = trigger.to_dict()

        assert data["trigger_id"] == str(trigger_id)
        assert data["operator_id"] == str(operator_id)
        assert data["triggered_at"] == now.isoformat()
        assert data["reason"] == "Planned shutdown"

    def test_from_dict(self) -> None:
        """Can deserialize trigger from dictionary."""
        trigger_id = uuid4()
        operator_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "trigger_id": str(trigger_id),
            "operator_id": str(operator_id),
            "triggered_at": now.isoformat(),
            "reason": "Planned shutdown",
        }

        trigger = CessationTrigger.from_dict(data)

        assert trigger.trigger_id == trigger_id
        assert trigger.operator_id == operator_id
        assert trigger.triggered_at == now
        assert trigger.reason == "Planned shutdown"

    def test_round_trip_serialization(self) -> None:
        """Serialization round-trip preserves all data."""
        original = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason="Round trip test",
        )

        data = original.to_dict()
        restored = CessationTrigger.from_dict(data)

        assert restored.trigger_id == original.trigger_id
        assert restored.operator_id == original.operator_id
        assert restored.triggered_at == original.triggered_at
        assert restored.reason == original.reason


class TestCessationTriggerIrreversibility:
    """Tests ensuring trigger has no cancellation fields."""

    def test_no_cancelled_at_field(self) -> None:
        """No cancelled_at field exists (irreversible)."""
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason="Test",
        )

        assert not hasattr(trigger, "cancelled_at")

    def test_no_revoked_by_field(self) -> None:
        """No revoked_by field exists (irreversible)."""
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason="Test",
        )

        assert not hasattr(trigger, "revoked_by")

    def test_no_status_field(self) -> None:
        """No status field on trigger (status is in CessationState)."""
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason="Test",
        )

        assert not hasattr(trigger, "status")


class TestCessationTriggerOperatorRequirement:
    """Tests ensuring operator is required (AC4, FR47)."""

    def test_operator_id_required(self) -> None:
        """Operator ID is a required field."""
        # This should work (operator provided)
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason="Test",
        )
        assert trigger.operator_id is not None

    def test_operator_id_is_uuid(self) -> None:
        """Operator ID must be a UUID."""
        operator_id = uuid4()
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=operator_id,
            triggered_at=datetime.now(timezone.utc),
            reason="Test",
        )
        assert isinstance(trigger.operator_id, type(operator_id))
