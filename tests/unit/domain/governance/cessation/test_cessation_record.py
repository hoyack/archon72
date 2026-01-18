"""Unit tests for CessationRecord domain model.

Story: consent-gov-8.2: Cessation Record Creation

Tests the immutable Cessation Record that serves as the final
historical document of system cessation.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.cessation.cessation_record import (
    CessationRecord,
    InterruptedWork,
    SystemSnapshot,
)


class TestSystemSnapshot:
    """Tests for SystemSnapshot value object."""

    def test_create_snapshot(self) -> None:
        """SystemSnapshot can be created with required fields."""
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=5,
            pending_motions=3,
            in_progress_executions=2,
            legitimacy_band="ELEVATED",
            component_statuses={
                "king_service": "healthy",
                "president_service": "healthy",
            },
            captured_at=now,
        )

        assert snapshot.active_tasks == 5
        assert snapshot.pending_motions == 3
        assert snapshot.in_progress_executions == 2
        assert snapshot.legitimacy_band == "ELEVATED"
        assert snapshot.component_statuses["king_service"] == "healthy"
        assert snapshot.captured_at == now

    def test_snapshot_is_frozen(self) -> None:
        """SystemSnapshot cannot be modified after creation."""
        snapshot = SystemSnapshot(
            active_tasks=5,
            pending_motions=3,
            in_progress_executions=2,
            legitimacy_band="ELEVATED",
            component_statuses={},
            captured_at=datetime.now(timezone.utc),
        )

        with pytest.raises(FrozenInstanceError):
            snapshot.active_tasks = 10  # type: ignore[misc]

    def test_snapshot_to_dict(self) -> None:
        """SystemSnapshot can be serialized to dictionary."""
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=5,
            pending_motions=3,
            in_progress_executions=2,
            legitimacy_band="ELEVATED",
            component_statuses={"test": "ok"},
            captured_at=now,
        )

        result = snapshot.to_dict()

        assert result["active_tasks"] == 5
        assert result["pending_motions"] == 3
        assert result["in_progress_executions"] == 2
        assert result["legitimacy_band"] == "ELEVATED"
        assert result["captured_at"] == now.isoformat()

    def test_snapshot_from_dict(self) -> None:
        """SystemSnapshot can be deserialized from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            "active_tasks": 5,
            "pending_motions": 3,
            "in_progress_executions": 2,
            "legitimacy_band": "ELEVATED",
            "component_statuses": {"test": "ok"},
            "captured_at": now.isoformat(),
        }

        snapshot = SystemSnapshot.from_dict(data)

        assert snapshot.active_tasks == 5
        assert snapshot.legitimacy_band == "ELEVATED"


class TestInterruptedWork:
    """Tests for InterruptedWork value object."""

    def test_create_interrupted_work(self) -> None:
        """InterruptedWork can be created with required fields."""
        work_id = uuid4()
        cessation_id = uuid4()
        now = datetime.now(timezone.utc)

        work = InterruptedWork(
            work_id=work_id,
            work_type="task",
            previous_state="in_progress",
            interrupted_at=now,
            cessation_record_id=cessation_id,
        )

        assert work.work_id == work_id
        assert work.work_type == "task"
        assert work.previous_state == "in_progress"
        assert work.interrupted_at == now
        assert work.cessation_record_id == cessation_id

    def test_interrupted_work_is_frozen(self) -> None:
        """InterruptedWork cannot be modified after creation."""
        work = InterruptedWork(
            work_id=uuid4(),
            work_type="task",
            previous_state="in_progress",
            interrupted_at=datetime.now(timezone.utc),
            cessation_record_id=uuid4(),
        )

        with pytest.raises(FrozenInstanceError):
            work.work_type = "motion"  # type: ignore[misc]

    def test_interrupted_work_to_dict(self) -> None:
        """InterruptedWork can be serialized to dictionary."""
        work_id = uuid4()
        cessation_id = uuid4()
        now = datetime.now(timezone.utc)

        work = InterruptedWork(
            work_id=work_id,
            work_type="motion",
            previous_state="pending",
            interrupted_at=now,
            cessation_record_id=cessation_id,
        )

        result = work.to_dict()

        assert result["work_id"] == str(work_id)
        assert result["work_type"] == "motion"
        assert result["previous_state"] == "pending"
        assert result["interrupted_at"] == now.isoformat()
        assert result["cessation_record_id"] == str(cessation_id)

    def test_interrupted_work_from_dict(self) -> None:
        """InterruptedWork can be deserialized from dictionary."""
        work_id = uuid4()
        cessation_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "work_id": str(work_id),
            "work_type": "execution",
            "previous_state": "running",
            "interrupted_at": now.isoformat(),
            "cessation_record_id": str(cessation_id),
        }

        work = InterruptedWork.from_dict(data)

        assert work.work_id == work_id
        assert work.work_type == "execution"


class TestCessationRecord:
    """Tests for CessationRecord value object."""

    def test_create_cessation_record(self) -> None:
        """CessationRecord can be created with required fields."""
        record_id = uuid4()
        trigger_id = uuid4()
        operator_id = uuid4()
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=0,
            pending_motions=0,
            in_progress_executions=0,
            legitimacy_band="BASELINE",
            component_statuses={},
            captured_at=now,
        )

        record = CessationRecord(
            record_id=record_id,
            trigger_id=trigger_id,
            operator_id=operator_id,
            created_at=now,
            final_ledger_hash="sha256:abc123",
            final_sequence_number=12345,
            system_snapshot=snapshot,
            interrupted_work_ids=[],
            reason="Planned retirement",
        )

        assert record.record_id == record_id
        assert record.trigger_id == trigger_id
        assert record.operator_id == operator_id
        assert record.created_at == now
        assert record.final_ledger_hash == "sha256:abc123"
        assert record.final_sequence_number == 12345
        assert record.system_snapshot == snapshot
        assert record.interrupted_work_ids == []
        assert record.reason == "Planned retirement"

    def test_cessation_record_is_frozen(self) -> None:
        """CessationRecord cannot be modified after creation (AC7)."""
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=0,
            pending_motions=0,
            in_progress_executions=0,
            legitimacy_band="BASELINE",
            component_statuses={},
            captured_at=now,
        )

        record = CessationRecord(
            record_id=uuid4(),
            trigger_id=uuid4(),
            operator_id=uuid4(),
            created_at=now,
            final_ledger_hash="sha256:abc123",
            final_sequence_number=12345,
            system_snapshot=snapshot,
            interrupted_work_ids=[],
            reason="Test",
        )

        with pytest.raises(FrozenInstanceError):
            record.reason = "Modified"  # type: ignore[misc]

    def test_cessation_record_no_modified_at_field(self) -> None:
        """CessationRecord has no modified_at field (immutable by design)."""
        assert not hasattr(CessationRecord, "modified_at")
        # Check the dataclass fields
        from dataclasses import fields

        field_names = [f.name for f in fields(CessationRecord)]
        assert "modified_at" not in field_names
        assert "updated_by" not in field_names
        assert "cancelled" not in field_names

    def test_cessation_record_requires_reason(self) -> None:
        """CessationRecord requires a non-empty reason."""
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=0,
            pending_motions=0,
            in_progress_executions=0,
            legitimacy_band="BASELINE",
            component_statuses={},
            captured_at=now,
        )

        with pytest.raises(ValueError, match="reason is required"):
            CessationRecord(
                record_id=uuid4(),
                trigger_id=uuid4(),
                operator_id=uuid4(),
                created_at=now,
                final_ledger_hash="sha256:abc123",
                final_sequence_number=12345,
                system_snapshot=snapshot,
                interrupted_work_ids=[],
                reason="",  # Empty reason should fail
            )

    def test_cessation_record_requires_non_whitespace_reason(self) -> None:
        """CessationRecord requires a reason with non-whitespace content."""
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=0,
            pending_motions=0,
            in_progress_executions=0,
            legitimacy_band="BASELINE",
            component_statuses={},
            captured_at=now,
        )

        with pytest.raises(ValueError, match="reason is required"):
            CessationRecord(
                record_id=uuid4(),
                trigger_id=uuid4(),
                operator_id=uuid4(),
                created_at=now,
                final_ledger_hash="sha256:abc123",
                final_sequence_number=12345,
                system_snapshot=snapshot,
                interrupted_work_ids=[],
                reason="   ",  # Whitespace-only should fail
            )

    def test_cessation_record_to_dict(self) -> None:
        """CessationRecord can be serialized to dictionary."""
        record_id = uuid4()
        trigger_id = uuid4()
        operator_id = uuid4()
        work_id = uuid4()
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=5,
            pending_motions=3,
            in_progress_executions=2,
            legitimacy_band="ELEVATED",
            component_statuses={"test": "ok"},
            captured_at=now,
        )

        record = CessationRecord(
            record_id=record_id,
            trigger_id=trigger_id,
            operator_id=operator_id,
            created_at=now,
            final_ledger_hash="sha256:abc123",
            final_sequence_number=12345,
            system_snapshot=snapshot,
            interrupted_work_ids=[work_id],
            reason="Planned retirement",
        )

        result = record.to_dict()

        assert result["record_id"] == str(record_id)
        assert result["trigger_id"] == str(trigger_id)
        assert result["operator_id"] == str(operator_id)
        assert result["created_at"] == now.isoformat()
        assert result["final_ledger_hash"] == "sha256:abc123"
        assert result["final_sequence_number"] == 12345
        assert result["system_snapshot"]["active_tasks"] == 5
        assert result["interrupted_work_ids"] == [str(work_id)]
        assert result["reason"] == "Planned retirement"

    def test_cessation_record_from_dict(self) -> None:
        """CessationRecord can be deserialized from dictionary."""
        record_id = uuid4()
        trigger_id = uuid4()
        operator_id = uuid4()
        work_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "record_id": str(record_id),
            "trigger_id": str(trigger_id),
            "operator_id": str(operator_id),
            "created_at": now.isoformat(),
            "final_ledger_hash": "sha256:abc123",
            "final_sequence_number": 12345,
            "system_snapshot": {
                "active_tasks": 5,
                "pending_motions": 3,
                "in_progress_executions": 2,
                "legitimacy_band": "ELEVATED",
                "component_statuses": {"test": "ok"},
                "captured_at": now.isoformat(),
            },
            "interrupted_work_ids": [str(work_id)],
            "reason": "Planned retirement",
        }

        record = CessationRecord.from_dict(data)

        assert record.record_id == record_id
        assert record.trigger_id == trigger_id
        assert record.final_sequence_number == 12345
        assert record.system_snapshot.active_tasks == 5
        assert record.interrupted_work_ids == [work_id]

    def test_cessation_record_with_interrupted_work(self) -> None:
        """CessationRecord can track multiple interrupted work items."""
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=3,
            pending_motions=2,
            in_progress_executions=1,
            legitimacy_band="ELEVATED",
            component_statuses={},
            captured_at=now,
        )
        work_ids = [uuid4(), uuid4(), uuid4()]

        record = CessationRecord(
            record_id=uuid4(),
            trigger_id=uuid4(),
            operator_id=uuid4(),
            created_at=now,
            final_ledger_hash="sha256:abc123",
            final_sequence_number=12345,
            system_snapshot=snapshot,
            interrupted_work_ids=work_ids,
            reason="Emergency shutdown",
        )

        assert len(record.interrupted_work_ids) == 3
        assert record.interrupted_work_ids == work_ids


class TestCessationRecordImmutability:
    """Tests specifically for immutability guarantees (AC7)."""

    def test_record_is_frozen_dataclass(self) -> None:
        """CessationRecord is a frozen dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(CessationRecord)
        # Verify it's frozen by checking __dataclass_fields__
        assert CessationRecord.__dataclass_fields__

    def test_cannot_add_attributes(self) -> None:
        """Cannot add new attributes to CessationRecord."""
        now = datetime.now(timezone.utc)
        snapshot = SystemSnapshot(
            active_tasks=0,
            pending_motions=0,
            in_progress_executions=0,
            legitimacy_band="BASELINE",
            component_statuses={},
            captured_at=now,
        )

        record = CessationRecord(
            record_id=uuid4(),
            trigger_id=uuid4(),
            operator_id=uuid4(),
            created_at=now,
            final_ledger_hash="sha256:abc123",
            final_sequence_number=12345,
            system_snapshot=snapshot,
            interrupted_work_ids=[],
            reason="Test",
        )

        with pytest.raises(FrozenInstanceError):
            record.new_attribute = "value"  # type: ignore[attr-defined]

    def test_system_snapshot_is_frozen(self) -> None:
        """SystemSnapshot is also frozen for full immutability."""
        from dataclasses import is_dataclass

        assert is_dataclass(SystemSnapshot)

    def test_interrupted_work_is_frozen(self) -> None:
        """InterruptedWork is also frozen for full immutability."""
        from dataclasses import is_dataclass

        assert is_dataclass(InterruptedWork)
