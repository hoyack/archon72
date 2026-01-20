"""ArchonAssignmentService stub for testing (Story 2A.2, AC-7).

This module provides an in-memory stub implementation of the
ArchonAssignmentServiceProtocol for testing purposes. It supports
operation tracking and configurable behavior.

Developer Golden Rules:
1. OPERATION_TRACKING - Records all operations for test assertions
2. CONFIGURABLE - Supports custom responses and failure injection
3. DETERMINISTIC - Maintains idempotency guarantees
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from uuid6 import uuid7

from src.application.ports.archon_assignment import (
    ArchonsAssignedEventPayload,
    AssignmentResult,
)
from src.domain.errors.deliberation import (
    ArchonPoolExhaustedError,
    InvalidPetitionStateError,
)
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)

if TYPE_CHECKING:
    from src.domain.models.fate_archon import FateArchon


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass
class ArchonAssignmentOperation:
    """Record of an operation performed on the stub."""

    operation: str
    timestamp: datetime
    petition_id: UUID | None = None
    session_id: UUID | None = None
    archon_names: list[str] | None = None
    seed: int | None = None
    is_new_assignment: bool | None = None
    error: str | None = None


@dataclass
class AssignmentRecord:
    """Record of an archon assignment stored in the stub."""

    session: DeliberationSession
    archons: tuple[FateArchon, FateArchon, FateArchon]
    assigned_at: datetime
    petition_id: UUID


class ArchonAssignmentServiceStub:
    """In-memory stub for ArchonAssignmentService for testing.

    This stub implements the ArchonAssignmentServiceProtocol interface with:
    - Operation tracking for test assertions
    - Configurable archon responses
    - Error injection for testing failure paths
    - Idempotency simulation

    Usage:
        stub = ArchonAssignmentServiceStub(archon_pool)

        # Configure fixed archons
        stub.set_archons(archon1, archon2, archon3)

        # Inject errors for testing
        stub.set_error_on_next_call(PetitionNotFoundError("test"))

        # Query operations after test
        ops = stub.get_operations_by_type("assign_archons")
    """

    def __init__(
        self,
        archon_pool: tuple[FateArchon, FateArchon, FateArchon] | None = None,
    ) -> None:
        """Initialize the stub.

        Args:
            archon_pool: Optional fixed archon pool. If None, raises error
                        when assign_archons is called without setting archons.
        """
        self._archon_pool = archon_pool
        self._assignments: dict[UUID, AssignmentRecord] = {}
        self._operations: list[ArchonAssignmentOperation] = []
        self._next_error: Exception | None = None
        self._petition_not_found_ids: set[UUID] = set()
        self._invalid_state_ids: dict[UUID, str] = {}

    def _record_operation(
        self,
        operation: str,
        petition_id: UUID | None = None,
        session_id: UUID | None = None,
        archon_names: list[str] | None = None,
        seed: int | None = None,
        is_new_assignment: bool | None = None,
        error: str | None = None,
    ) -> None:
        """Record an operation for test assertions."""
        self._operations.append(
            ArchonAssignmentOperation(
                operation=operation,
                timestamp=_utc_now(),
                petition_id=petition_id,
                session_id=session_id,
                archon_names=archon_names,
                seed=seed,
                is_new_assignment=is_new_assignment,
                error=error,
            )
        )

    async def assign_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> AssignmentResult:
        """Assign archons to a petition for deliberation.

        This stub implementation:
        1. Returns existing assignment if already assigned (idempotency)
        2. Creates new assignment using configured archons
        3. Supports error injection for testing

        Args:
            petition_id: UUID of the petition requiring deliberation.
            seed: Optional seed for deterministic selection.

        Returns:
            AssignmentResult containing the session and assigned archons.

        Raises:
            PetitionNotFoundError: If petition marked as not found.
            InvalidPetitionStateError: If petition marked as invalid state.
            ArchonPoolExhaustedError: If no archons configured.
        """
        # Check for injected error
        if self._next_error is not None:
            error = self._next_error
            self._next_error = None
            self._record_operation(
                "assign_archons",
                petition_id=petition_id,
                seed=seed,
                error=str(error),
            )
            raise error

        # Check for petition not found
        if petition_id in self._petition_not_found_ids:
            self._record_operation(
                "assign_archons",
                petition_id=petition_id,
                seed=seed,
                error="PetitionNotFoundError",
            )
            raise PetitionNotFoundError(str(petition_id))

        # Check for invalid state
        if petition_id in self._invalid_state_ids:
            current_state = self._invalid_state_ids[petition_id]
            self._record_operation(
                "assign_archons",
                petition_id=petition_id,
                seed=seed,
                error=f"InvalidPetitionStateError: {current_state}",
            )
            raise InvalidPetitionStateError(
                petition_id=str(petition_id),
                current_state=current_state,
            )

        # Check for existing assignment (idempotency)
        if petition_id in self._assignments:
            record = self._assignments[petition_id]
            self._record_operation(
                "assign_archons",
                petition_id=petition_id,
                session_id=record.session.id,
                archon_names=[a.name for a in record.archons],
                seed=seed,
                is_new_assignment=False,
            )
            return AssignmentResult(
                session=record.session,
                assigned_archons=record.archons,
                is_new_assignment=False,
                assigned_at=record.assigned_at,
            )

        # Check archon pool
        if self._archon_pool is None:
            self._record_operation(
                "assign_archons",
                petition_id=petition_id,
                seed=seed,
                error="ArchonPoolExhaustedError",
            )
            raise ArchonPoolExhaustedError(available_count=0)

        # Create new assignment
        now = _utc_now()
        archon_ids = tuple(a.id for a in self._archon_pool)

        session = DeliberationSession.create(
            petition_id=petition_id,
            archon_ids=archon_ids,
        )

        record = AssignmentRecord(
            session=session,
            archons=self._archon_pool,
            assigned_at=now,
            petition_id=petition_id,
        )
        self._assignments[petition_id] = record

        self._record_operation(
            "assign_archons",
            petition_id=petition_id,
            session_id=session.id,
            archon_names=[a.name for a in self._archon_pool],
            seed=seed,
            is_new_assignment=True,
        )

        return AssignmentResult(
            session=session,
            assigned_archons=self._archon_pool,
            is_new_assignment=True,
            assigned_at=now,
        )

    async def get_session_by_petition(
        self,
        petition_id: UUID,
    ) -> DeliberationSession | None:
        """Get existing deliberation session for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            DeliberationSession if exists, None otherwise.
        """
        self._record_operation(
            "get_session_by_petition",
            petition_id=petition_id,
        )

        record = self._assignments.get(petition_id)
        return record.session if record else None

    async def get_assigned_archons(
        self,
        petition_id: UUID,
    ) -> tuple[FateArchon, FateArchon, FateArchon] | None:
        """Get assigned archons for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            Tuple of 3 FateArchons if assigned, None otherwise.
        """
        self._record_operation(
            "get_assigned_archons",
            petition_id=petition_id,
        )

        record = self._assignments.get(petition_id)
        return record.archons if record else None

    # ═══════════════════════════════════════════════════════════════════════════
    # TESTING HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def set_archons(
        self,
        archon1: FateArchon,
        archon2: FateArchon,
        archon3: FateArchon,
    ) -> None:
        """Set the archon pool for assignments.

        Args:
            archon1: First Fate Archon.
            archon2: Second Fate Archon.
            archon3: Third Fate Archon.
        """
        self._archon_pool = (archon1, archon2, archon3)

    def set_error_on_next_call(self, error: Exception) -> None:
        """Configure an error to be raised on the next assign_archons call.

        Args:
            error: Exception to raise.
        """
        self._next_error = error

    def mark_petition_not_found(self, petition_id: UUID) -> None:
        """Mark a petition ID as not found.

        Args:
            petition_id: UUID to mark as not found.
        """
        self._petition_not_found_ids.add(petition_id)

    def mark_petition_invalid_state(
        self,
        petition_id: UUID,
        current_state: str,
    ) -> None:
        """Mark a petition as being in invalid state.

        Args:
            petition_id: UUID of petition.
            current_state: Current state to report in error.
        """
        self._invalid_state_ids[petition_id] = current_state

    def add_existing_assignment(
        self,
        petition_id: UUID,
        session: DeliberationSession,
        archons: tuple[FateArchon, FateArchon, FateArchon],
    ) -> None:
        """Add a pre-existing assignment for idempotency testing.

        Args:
            petition_id: UUID of petition.
            session: Existing session.
            archons: Assigned archons.
        """
        self._assignments[petition_id] = AssignmentRecord(
            session=session,
            archons=archons,
            assigned_at=_utc_now(),
            petition_id=petition_id,
        )

    def clear(self) -> None:
        """Clear all state."""
        self._assignments.clear()
        self._operations.clear()
        self._next_error = None
        self._petition_not_found_ids.clear()
        self._invalid_state_ids.clear()

    def clear_operations(self) -> None:
        """Clear only operation history."""
        self._operations.clear()

    def get_assignment_count(self) -> int:
        """Get count of assignments."""
        return len(self._assignments)

    def get_operation_count(self) -> int:
        """Get total count of recorded operations."""
        return len(self._operations)

    def get_all_operations(self) -> list[ArchonAssignmentOperation]:
        """Get all recorded operations."""
        return list(self._operations)

    def get_operations_by_type(
        self, operation_type: str
    ) -> list[ArchonAssignmentOperation]:
        """Get operations filtered by type.

        Args:
            operation_type: Type of operation to filter for.

        Returns:
            List of operations matching the type.
        """
        return [op for op in self._operations if op.operation == operation_type]

    def was_petition_assigned(self, petition_id: UUID) -> bool:
        """Check if assignment was made for a petition.

        Args:
            petition_id: UUID of petition to check.

        Returns:
            True if assign_archons was called for this petition.
        """
        return any(
            op.operation == "assign_archons" and op.petition_id == petition_id
            for op in self._operations
        )

    def get_new_assignment_count(self) -> int:
        """Get count of new assignments (not idempotent returns)."""
        return sum(
            1
            for op in self._operations
            if op.operation == "assign_archons" and op.is_new_assignment is True
        )

    def get_emitted_events(self) -> list[ArchonsAssignedEventPayload]:
        """Get all event payloads that would be emitted.

        Returns:
            List of ArchonsAssignedEventPayload for new assignments.
        """
        events = []
        for op in self._operations:
            if (
                op.operation == "assign_archons"
                and op.is_new_assignment
                and op.petition_id
                and op.session_id
            ):
                record = self._assignments.get(op.petition_id)
                if record:
                    events.append(
                        ArchonsAssignedEventPayload(
                            session_id=op.session_id,
                            petition_id=op.petition_id,
                            archon_ids=tuple(a.id for a in record.archons),
                            archon_names=tuple(a.name for a in record.archons),
                            assigned_at=record.assigned_at,
                        )
                    )
        return events
