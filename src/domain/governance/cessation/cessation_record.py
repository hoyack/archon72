"""Cessation record domain model for system lifecycle management.

Story: consent-gov-8.2: Cessation Record Creation

This module defines the immutable Cessation Record - the final historical
document created when the governance system ceases.

Key Design:
- Immutable (frozen dataclass) - cannot be modified after creation (AC7)
- Contains complete system snapshot at cessation (AC6)
- References trigger, captures final ledger state (AC3)
- Tracks all interrupted work (AC4)

Constitutional Context:
- FR48: System can create immutable Cessation Record on cessation
- FR51: System can preserve all records on cessation
- FR52: System can label in-progress work as `interrupted_by_cessation`
- NFR-REL-05: Cessation Record creation is atomic

Note: There are intentionally NO fields for:
- modified_at: Records are never modified
- updated_by: Records are never updated
- cancelled: Cessation cannot be cancelled
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SystemSnapshot:
    """Snapshot of system state at cessation.

    Captures the state of the governance system at the moment of
    cessation for historical record and audit purposes.

    Attributes:
        active_tasks: Number of tasks in active state.
        pending_motions: Number of motions awaiting processing.
        in_progress_executions: Number of executions currently running.
        legitimacy_band: Current legitimacy band (e.g., "ELEVATED", "BASELINE").
        component_statuses: Status of each system component.
        captured_at: Timestamp when snapshot was taken.

    Example:
        >>> from datetime import datetime, timezone
        >>> snapshot = SystemSnapshot(
        ...     active_tasks=5,
        ...     pending_motions=3,
        ...     in_progress_executions=2,
        ...     legitimacy_band="ELEVATED",
        ...     component_statuses={"king_service": "healthy"},
        ...     captured_at=datetime.now(timezone.utc),
        ... )
    """

    active_tasks: int
    """Number of tasks in active state."""

    pending_motions: int
    """Number of motions awaiting processing."""

    in_progress_executions: int
    """Number of executions currently running."""

    legitimacy_band: str
    """Current legitimacy band at cessation."""

    component_statuses: dict[str, str]
    """Status of each system component at cessation."""

    captured_at: datetime
    """Timestamp when snapshot was taken."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/event payloads.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "active_tasks": self.active_tasks,
            "pending_motions": self.pending_motions,
            "in_progress_executions": self.in_progress_executions,
            "legitimacy_band": self.legitimacy_band,
            "component_statuses": self.component_statuses,
            "captured_at": self.captured_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemSnapshot":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict() or event payload.

        Returns:
            Reconstructed SystemSnapshot.
        """
        return cls(
            active_tasks=data["active_tasks"],
            pending_motions=data["pending_motions"],
            in_progress_executions=data["in_progress_executions"],
            legitimacy_band=data["legitimacy_band"],
            component_statuses=data["component_statuses"],
            captured_at=datetime.fromisoformat(data["captured_at"]),
        )


@dataclass(frozen=True)
class InterruptedWork:
    """Record of work interrupted by cessation.

    Created for each in-progress work item when cessation occurs.
    Labels the work with `interrupted_by_cessation` per FR52.

    Attributes:
        work_id: Unique identifier of the interrupted work.
        work_type: Type of work ("task", "motion", "execution").
        previous_state: State before interruption (e.g., "in_progress").
        interrupted_at: Timestamp when interruption occurred.
        cessation_record_id: Reference to the cessation record.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> work = InterruptedWork(
        ...     work_id=uuid4(),
        ...     work_type="task",
        ...     previous_state="in_progress",
        ...     interrupted_at=datetime.now(timezone.utc),
        ...     cessation_record_id=uuid4(),
        ... )
    """

    work_id: UUID
    """Unique identifier of the interrupted work."""

    work_type: str
    """Type of work: "task", "motion", or "execution"."""

    previous_state: str
    """State the work was in before interruption."""

    interrupted_at: datetime
    """Timestamp when interruption occurred."""

    cessation_record_id: UUID
    """Reference to the parent cessation record."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/event payloads.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "work_id": str(self.work_id),
            "work_type": self.work_type,
            "previous_state": self.previous_state,
            "interrupted_at": self.interrupted_at.isoformat(),
            "cessation_record_id": str(self.cessation_record_id),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterruptedWork":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict() or event payload.

        Returns:
            Reconstructed InterruptedWork.
        """
        return cls(
            work_id=UUID(data["work_id"]),
            work_type=data["work_type"],
            previous_state=data["previous_state"],
            interrupted_at=datetime.fromisoformat(data["interrupted_at"]),
            cessation_record_id=UUID(data["cessation_record_id"]),
        )


@dataclass(frozen=True)
class CessationRecord:
    """Immutable record of system cessation.

    Created atomically when cessation occurs. Cannot be modified after creation.
    This is the final historical document for this system instance.

    The Cessation Record serves as:
    - Proof that cessation happened properly
    - Complete system state at cessation
    - Final ledger hash for verification
    - List of interrupted work items

    Attributes:
        record_id: Unique identifier for this cessation record.
        trigger_id: Reference to the CessationTrigger that initiated cessation.
        operator_id: The Human Operator who triggered cessation.
        created_at: Timestamp when this record was created.
        final_ledger_hash: Hash of the final ledger state.
        final_sequence_number: Last sequence number in the ledger.
        system_snapshot: Complete system state at cessation.
        interrupted_work_ids: UUIDs of all interrupted work items.
        reason: Documentation of why cessation was triggered.

    Note: There are intentionally NO fields for:
    - modified_at: Records are never modified
    - updated_by: Records are never updated
    - cancelled: Cessation cannot be cancelled

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> record = CessationRecord(
        ...     record_id=uuid4(),
        ...     trigger_id=uuid4(),
        ...     operator_id=uuid4(),
        ...     created_at=datetime.now(timezone.utc),
        ...     final_ledger_hash="sha256:abc123",
        ...     final_sequence_number=12345,
        ...     system_snapshot=snapshot,
        ...     interrupted_work_ids=[],
        ...     reason="Planned system retirement",
        ... )

    Constitutional Context:
        - FR48: System can create immutable Cessation Record on cessation
        - FR51: System can preserve all records on cessation
        - NFR-REL-05: Cessation Record creation is atomic
    """

    record_id: UUID
    """Unique identifier for this cessation record."""

    trigger_id: UUID
    """Reference to the CessationTrigger that initiated cessation."""

    operator_id: UUID
    """The Human Operator who triggered cessation."""

    created_at: datetime
    """Timestamp when this record was created."""

    final_ledger_hash: str
    """Hash of the final ledger state (proof of integrity)."""

    final_sequence_number: int
    """Last sequence number in the ledger."""

    system_snapshot: SystemSnapshot
    """Complete system state at cessation."""

    interrupted_work_ids: list[UUID]
    """UUIDs of all work items interrupted by cessation."""

    reason: str
    """Documentation of why cessation was triggered."""

    # Explicitly NOT included (immutable by design):
    # modified_at: datetime  - Records are never modified
    # updated_by: UUID       - Records are never updated
    # cancelled: bool        - Cessation cannot be cancelled

    def __post_init__(self) -> None:
        """Validate record fields."""
        if not self.reason or not self.reason.strip():
            raise ValueError("Cessation reason is required and cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/event payloads.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "record_id": str(self.record_id),
            "trigger_id": str(self.trigger_id),
            "operator_id": str(self.operator_id),
            "created_at": self.created_at.isoformat(),
            "final_ledger_hash": self.final_ledger_hash,
            "final_sequence_number": self.final_sequence_number,
            "system_snapshot": self.system_snapshot.to_dict(),
            "interrupted_work_ids": [str(uid) for uid in self.interrupted_work_ids],
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CessationRecord":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict() or event payload.

        Returns:
            Reconstructed CessationRecord.
        """
        return cls(
            record_id=UUID(data["record_id"]),
            trigger_id=UUID(data["trigger_id"]),
            operator_id=UUID(data["operator_id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            final_ledger_hash=data["final_ledger_hash"],
            final_sequence_number=data["final_sequence_number"],
            system_snapshot=SystemSnapshot.from_dict(data["system_snapshot"]),
            interrupted_work_ids=[UUID(uid) for uid in data["interrupted_work_ids"]],
            reason=data["reason"],
        )
