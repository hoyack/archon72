"""CessationRecordService for creating immutable cessation records.

Story: consent-gov-8.2: Cessation Record Creation

This service creates the immutable Cessation Record when the governance
system ceases. The record is the final historical document.

IMPORTANT: This service intentionally has NO:
- update_record()
- delete_record()
- modify_record()

Records are IMMUTABLE once created.

Constitutional Context:
- FR48: System can create immutable Cessation Record on cessation
- FR51: System can preserve all records on cessation
- FR52: System can label in-progress work as `interrupted_by_cessation`
- NFR-REL-05: Cessation Record creation is atomic
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from src.application.ports.governance.cessation_record_port import CessationRecordPort
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.domain.governance.cessation import (
    CessationRecord,
    CessationRecordAlreadyExistsError,
    CessationRecordCreationError,
    CessationTrigger,
    InterruptedWork,
    SystemSnapshot,
)
from src.domain.ports.time_authority import TimeAuthorityProtocol


class LedgerPort(Protocol):
    """Port for ledger operations."""

    async def get_final_state(self) -> tuple[str, int]:
        """Get final ledger hash and sequence number."""
        ...


class InProgressWorkPort(Protocol):
    """Port for in-progress work operations."""

    async def get_in_progress(self) -> list[dict]:
        """Get all in-progress work items."""
        ...

    async def label_interrupted(
        self,
        work_id: UUID,
        cessation_record_id: UUID,
        interrupted_at: datetime,
        previous_state: str,
        work_type: str,
    ) -> InterruptedWork:
        """Label work as interrupted by cessation."""
        ...

    async def count_active(self) -> int:
        """Count active tasks."""
        ...

    async def count_in_progress(self) -> int:
        """Count in-progress executions."""
        ...


class MotionPort(Protocol):
    """Port for motion operations."""

    async def count_pending(self) -> int:
        """Count pending motions."""
        ...


class LegitimacyPort(Protocol):
    """Port for legitimacy operations."""

    async def get_current_band(self) -> str:
        """Get current legitimacy band."""
        ...


class ComponentStatusPort(Protocol):
    """Port for component status operations."""

    async def get_all_statuses(self) -> dict[str, str]:
        """Get all component statuses."""
        ...


class CessationRecordService:
    """Creates immutable Cessation Records.

    This service creates the final historical document when the
    governance system ceases. The record is IMMUTABLE - no modify
    or delete methods exist.

    Creation is ATOMIC (NFR-REL-05):
    - Either complete record is created
    - Or nothing is changed (fails entirely)

    Example:
        service = CessationRecordService(...)
        record = await service.create_record(trigger=trigger)
        # Record is now permanently stored

    Note: There are intentionally NO methods for:
    - Updating the record
    - Deleting the record
    - Modifying the record
    """

    def __init__(
        self,
        cessation_record_port: CessationRecordPort,
        ledger_port: LedgerPort,
        work_port: InProgressWorkPort,
        motion_port: MotionPort,
        event_emitter: TwoPhaseEventEmitterPort,
        time_authority: TimeAuthorityProtocol,
        legitimacy_port: LegitimacyPort,
        component_status_port: ComponentStatusPort,
    ) -> None:
        """Initialize CessationRecordService.

        Args:
            cessation_record_port: Port for record persistence.
            ledger_port: Port for ledger state.
            work_port: Port for in-progress work.
            motion_port: Port for motion queries.
            event_emitter: Port for two-phase events.
            time_authority: TimeAuthority for timestamps.
            legitimacy_port: Port for legitimacy queries.
            component_status_port: Port for component status.
        """
        self._records = cessation_record_port
        self._ledger = ledger_port
        self._work = work_port
        self._motions = motion_port
        self._event_emitter = event_emitter
        self._time = time_authority
        self._legitimacy = legitimacy_port
        self._components = component_status_port

    async def create_record(
        self,
        trigger: CessationTrigger,
    ) -> CessationRecord:
        """Create immutable Cessation Record.

        This operation is ATOMIC (NFR-REL-05):
        - Either complete record is created
        - Or nothing is changed (fails entirely)

        The record contains:
        - Trigger reference
        - Final ledger hash
        - System snapshot
        - List of interrupted work

        Args:
            trigger: The cessation trigger that initiated this.

        Returns:
            CessationRecord (immutable).

        Raises:
            CessationRecordAlreadyExistsError: If record already exists.
            CessationRecordCreationError: If creation fails.
        """
        now = self._time.utcnow()
        record_id = uuid4()

        # Check for existing record first
        existing = await self._records.get_record()
        if existing is not None:
            raise CessationRecordAlreadyExistsError(
                existing_record_id=existing.record_id,
            )

        # Emit two-phase event: intent
        correlation_id = await self._event_emitter.emit_intent(
            operation_type="constitutional.cessation.record_created",
            actor_id=str(trigger.operator_id),
            target_entity_id=str(record_id),
            intent_payload={
                "record_id": str(record_id),
                "trigger_id": str(trigger.trigger_id),
                "operator_id": str(trigger.operator_id),
                "created_at": now.isoformat(),
            },
        )

        try:
            # Collect system snapshot (AC6)
            snapshot = await self._collect_snapshot(now)

            # Get final ledger state (AC3)
            final_hash, final_seq = await self._ledger.get_final_state()

            # Label interrupted work (AC4)
            interrupted_ids = await self._label_interrupted_work(
                record_id=record_id,
                timestamp=now,
            )

            # Create record (AC1)
            record = CessationRecord(
                record_id=record_id,
                trigger_id=trigger.trigger_id,
                operator_id=trigger.operator_id,
                created_at=now,
                final_ledger_hash=final_hash,
                final_sequence_number=final_seq,
                system_snapshot=snapshot,
                interrupted_work_ids=interrupted_ids,
                reason=trigger.reason,
            )

            # Atomic creation (AC2)
            await self._records.create_record_atomic(record)

            # Emit two-phase event: commit (AC5)
            await self._event_emitter.emit_commit(
                correlation_id=correlation_id,
                outcome_payload={
                    "record_id": str(record.record_id),
                    "trigger_id": str(trigger.trigger_id),
                    "final_ledger_hash": final_hash,
                    "final_sequence_number": final_seq,
                    "interrupted_work_count": len(interrupted_ids),
                },
            )

            return record

        except CessationRecordAlreadyExistsError:
            # Re-raise without wrapping
            raise

        except Exception as e:
            # Emit two-phase event: failure
            await self._event_emitter.emit_failure(
                correlation_id=correlation_id,
                failure_reason=str(e),
                failure_details={
                    "record_id": str(record_id),
                    "trigger_id": str(trigger.trigger_id),
                    "error_type": type(e).__name__,
                },
            )
            raise CessationRecordCreationError(
                message=f"Failed to create cessation record: {e}",
                cause=e,
                trigger_id=trigger.trigger_id,
            ) from e

    async def get_record(self) -> CessationRecord | None:
        """Get the cessation record if it exists.

        Returns:
            The cessation record if exists, None otherwise.
        """
        return await self._records.get_record()

    async def _collect_snapshot(self, timestamp: datetime) -> SystemSnapshot:
        """Collect system state snapshot (AC6).

        Args:
            timestamp: Timestamp for the snapshot.

        Returns:
            SystemSnapshot with current state.
        """
        active_tasks = await self._work.count_active()
        pending_motions = await self._motions.count_pending()
        in_progress_executions = await self._work.count_in_progress()
        legitimacy_band = await self._legitimacy.get_current_band()
        component_statuses = await self._components.get_all_statuses()

        return SystemSnapshot(
            active_tasks=active_tasks,
            pending_motions=pending_motions,
            in_progress_executions=in_progress_executions,
            legitimacy_band=legitimacy_band,
            component_statuses=component_statuses,
            captured_at=timestamp,
        )

    async def _label_interrupted_work(
        self,
        record_id: UUID,
        timestamp: datetime,
    ) -> list[UUID]:
        """Label all in-progress work as interrupted (AC4).

        Args:
            record_id: ID of the cessation record.
            timestamp: When interruption occurred.

        Returns:
            List of interrupted work IDs.
        """
        interrupted_ids: list[UUID] = []

        # Get all in-progress work
        in_progress = await self._work.get_in_progress()

        for work in in_progress:
            work_id = work["id"]
            work_type = work.get("type", "unknown")
            previous_state = work.get("state", "unknown")

            await self._work.label_interrupted(
                work_id=work_id,
                cessation_record_id=record_id,
                interrupted_at=timestamp,
                previous_state=previous_state,
                work_type=work_type,
            )
            interrupted_ids.append(work_id)

        return interrupted_ids

    # ==========================================================================
    # INTENTIONALLY NON-EXISTENT METHODS
    # ==========================================================================
    # These methods do NOT exist because cessation records are IMMUTABLE:
    #
    # async def update_record(self, ...): ...
    # async def delete_record(self, ...): ...
    # async def modify_record(self, ...): ...
    # async def remove_record(self, ...): ...
    #
    # Once created, the record is permanent.
    # ==========================================================================
