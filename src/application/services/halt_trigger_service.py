"""Halt Trigger Application Service (FR17, Story 3.2/3.3/3.9, Task 4/7).

This service handles constitutional crisis responses by:
1. Creating a ConstitutionalCrisisEvent (RT-2: event BEFORE halt)
2. Writing witnessed event to event store (Story 3.9)
3. Triggering system-wide halt via dual-channel transport

Constitutional Constraints:
- FR17: System SHALL halt immediately when single fork detected
- CT-11: Silent failure destroys legitimacy -> Crisis MUST be logged
- CT-12: Witnessing creates accountability -> Crisis event MUST be witnessed
- CT-13: Integrity outranks availability -> Availability sacrificed
- RT-2: All halt signals must create witnessed halt event BEFORE system stops

Developer Golden Rules:
1. HALT FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Constitutional actions require attribution
3. FAIL LOUD - Never catch SystemHaltedError

ADR-3: Partition Behavior + Halt Durability (Story 3.3)
- Uses DualChannelHaltTransport for Redis Streams + DB halt flag
- If EITHER channel indicates halt -> component halts
- DB is canonical when channels disagree

Story 3.9: Witnessed Halt Event Before Stop (RT-2)
- Write witnessed ConstitutionalCrisisEvent BEFORE halt
- If write fails, create UnwitnessedHaltRecord and proceed with halt (CT-13)
- Unwitnessed halts can be reconciled later via ceremony

Note: This service is wired as a callback to ForkMonitoringService.
When a fork is detected, on_fork_detected is called, which:
1. Creates ConstitutionalCrisisEvent payload
2. Writes witnessed event to event store (Story 3.9)
3. Creates UnwitnessedHaltRecord if write fails (Story 3.9)
4. Triggers the halt via dual-channel transport
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.dual_channel_halt import DualChannelHaltTransport
from src.application.ports.halt_trigger import HaltTrigger
from src.application.ports.unwitnessed_halt_repository import UnwitnessedHaltRepository
from src.application.ports.witnessed_halt_writer import WitnessedHaltWriter
from src.domain.events.constitutional_crisis import (
    CONSTITUTIONAL_CRISIS_EVENT_TYPE,
    ConstitutionalCrisisPayload,
    CrisisType,
)
from src.domain.events.fork_detected import ForkDetectedPayload
from src.domain.models.unwitnessed_halt import UnwitnessedHaltRecord

if TYPE_CHECKING:
    pass

logger = get_logger()


class HaltTriggerService:
    """Application service for triggering constitutional crisis halt.

    This service orchestrates the halt process:
    1. Receives fork detection callback from ForkMonitoringService
    2. Creates ConstitutionalCrisisEvent with crisis details
    3. Records the event (with witness) BEFORE halt (RT-2)
    4. Triggers system-wide halt via dual-channel transport (ADR-3)

    Constitutional Constraints:
    - FR17: Immediate halt on fork detection
    - RT-2: Crisis event recorded BEFORE halt
    - CT-11: Silent failure destroys legitimacy

    ADR-3: Partition Behavior + Halt Durability (Story 3.3)
    - Supports both DualChannelHaltTransport (preferred) and legacy HaltTrigger
    - DualChannelHaltTransport writes to Redis Streams + DB halt flag
    - If EITHER channel indicates halt -> component halts

    Attributes:
        service_id: Identifier for this service instance

    Example (DualChannelHaltTransport - preferred):
        >>> service = HaltTriggerService(
        ...     dual_channel_halt=dual_channel_transport,
        ...     service_id="halt-trigger-001",
        ... )

    Example (Legacy HaltTrigger - backward compatible):
        >>> service = HaltTriggerService(
        ...     halt_trigger=halt_trigger,
        ...     service_id="halt-trigger-001",
        ... )
    """

    def __init__(
        self,
        *,
        dual_channel_halt: DualChannelHaltTransport | None = None,
        halt_trigger: HaltTrigger | None = None,
        witnessed_halt_writer: WitnessedHaltWriter | None = None,
        unwitnessed_halt_repository: UnwitnessedHaltRepository | None = None,
        service_id: str,
    ) -> None:
        """Initialize the halt trigger service.

        Args:
            dual_channel_halt: DualChannelHaltTransport for dual-channel halt (preferred).
            halt_trigger: Legacy HaltTrigger for backward compatibility.
            witnessed_halt_writer: Writer for witnessed halt events (Story 3.9, RT-2).
            unwitnessed_halt_repository: Repository for unwitnessed halts (Story 3.9).
            service_id: Identifier for this service instance.

        Raises:
            ValueError: If neither dual_channel_halt nor halt_trigger is provided.

        Note:
            If both dual_channel_halt and halt_trigger are provided, dual_channel_halt
            is used (preferred per ADR-3).

            Story 3.9 adds witnessed_halt_writer for RT-2 compliance:
            - If provided, writes witnessed event BEFORE halt
            - If write fails, creates UnwitnessedHaltRecord (requires repository)
            - Halt proceeds regardless (CT-13: integrity over availability)
        """
        if dual_channel_halt is None and halt_trigger is None:
            msg = "Either dual_channel_halt or halt_trigger must be provided"
            raise ValueError(msg)

        self._dual_channel_halt = dual_channel_halt
        self._halt_trigger = halt_trigger
        self._witnessed_halt_writer = witnessed_halt_writer
        self._unwitnessed_halt_repository = unwitnessed_halt_repository
        self._service_id = service_id
        self._log = logger.bind(service_id=service_id, service="HaltTriggerService")

        # Track if halt has been triggered to prevent duplicates
        self._halt_triggered = False
        self._crisis_event_id: UUID | None = None

    @property
    def service_id(self) -> str:
        """Get the service ID."""
        return self._service_id

    @property
    def halt_triggered(self) -> bool:
        """Check if halt has been triggered by this service."""
        return self._halt_triggered

    @property
    def crisis_event_id(self) -> UUID | None:
        """Get the crisis event ID (if halt was triggered)."""
        return self._crisis_event_id

    async def on_fork_detected(self, fork: ForkDetectedPayload) -> None:
        """Handle fork detection by triggering constitutional crisis halt.

        This is the callback wired to ForkMonitoringService.

        Constitutional Flow (RT-2):
        1. Create ConstitutionalCrisisEvent payload
        2. Record/log the crisis event (BEFORE halt)
        3. Trigger halt via HaltTrigger

        Args:
            fork: Fork detection details from ForkMonitoringService

        Note:
            Multiple fork detections only trigger halt once. Subsequent
            calls are logged but do not create duplicate events.
        """
        # Prevent duplicate halts
        if self._halt_triggered:
            self._log.warning(
                "halt_already_triggered",
                new_fork_prev_hash=fork.prev_hash,
                existing_crisis_event_id=str(self._crisis_event_id),
            )
            return

        self._log.warning(
            "fork_detected_triggering_halt",
            prev_hash=fork.prev_hash,
            conflicting_events=len(fork.conflicting_event_ids),
            detecting_service=fork.detecting_service_id,
        )

        # Step 1: Create crisis event payload
        detection_details = (
            f"FR17: Fork detected - {len(fork.conflicting_event_ids)} conflicting "
            f"events with prev_hash={fork.prev_hash[:16]}..."
        )

        crisis_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=fork.detection_timestamp,
            detection_details=detection_details,
            triggering_event_ids=fork.conflicting_event_ids,
            detecting_service_id=fork.detecting_service_id,
        )

        # Step 2: Write witnessed event (BEFORE halt) - RT-2 (Story 3.9)
        crisis_event_id = await self._write_witnessed_halt_event(crisis_payload)
        self._crisis_event_id = crisis_event_id

        self._log.critical(
            "constitutional_crisis_event_created",
            event_type=CONSTITUTIONAL_CRISIS_EVENT_TYPE,
            crisis_type=crisis_payload.crisis_type.value,
            detection_details=crisis_payload.detection_details,
            triggering_event_count=len(crisis_payload.triggering_event_ids),
            crisis_event_id=str(crisis_event_id),
        )

        # Step 3: Trigger halt (AFTER event is recorded)
        halt_reason = f"FR17: Constitutional crisis - {crisis_payload.detection_details}"

        self._log.critical(
            "triggering_system_halt",
            reason=halt_reason,
            crisis_event_id=str(crisis_event_id),
        )

        await self._write_halt(halt_reason, crisis_event_id)

        self._halt_triggered = True

        self._log.critical(
            "system_halted",
            halt_reason=halt_reason,
            crisis_event_id=str(crisis_event_id),
        )

    async def trigger_halt_for_crisis(
        self,
        crisis_type: CrisisType,
        detection_details: str,
        triggering_event_ids: tuple[UUID, ...] = (),
    ) -> UUID:
        """Directly trigger halt for a crisis (not via fork detection).

        This method allows triggering halt for other crisis types
        (future: signature verification failure, hash chain break, etc.)

        Args:
            crisis_type: Type of constitutional crisis
            detection_details: Human-readable description
            triggering_event_ids: UUIDs of events that triggered crisis

        Returns:
            UUID of the crisis event

        Raises:
            RuntimeError: If halt already triggered
        """
        if self._halt_triggered:
            msg = "Halt already triggered"
            raise RuntimeError(msg)

        crisis_payload = ConstitutionalCrisisPayload(
            crisis_type=crisis_type,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details=detection_details,
            triggering_event_ids=triggering_event_ids,
            detecting_service_id=self._service_id,
        )

        # Write witnessed event (BEFORE halt) - RT-2 (Story 3.9)
        crisis_event_id = await self._write_witnessed_halt_event(crisis_payload)
        self._crisis_event_id = crisis_event_id

        self._log.critical(
            "constitutional_crisis_event_created",
            event_type=CONSTITUTIONAL_CRISIS_EVENT_TYPE,
            crisis_type=crisis_payload.crisis_type.value,
            detection_details=crisis_payload.detection_details,
            crisis_event_id=str(crisis_event_id),
        )

        # Trigger halt
        halt_reason = f"FR17: Constitutional crisis - {detection_details}"
        await self._write_halt(halt_reason, crisis_event_id)

        self._halt_triggered = True

        return crisis_event_id

    async def _write_halt(self, reason: str, crisis_event_id: UUID) -> None:
        """Write halt signal via appropriate transport.

        Dispatches to DualChannelHaltTransport (preferred) or legacy HaltTrigger.

        Args:
            reason: Human-readable reason for halt.
            crisis_event_id: UUID of triggering crisis event.
        """
        if self._dual_channel_halt is not None:
            # Use dual-channel transport (preferred per ADR-3)
            self._log.info(
                "using_dual_channel_halt_transport",
                transport="DualChannelHaltTransport",
            )
            await self._dual_channel_halt.write_halt(
                reason=reason,
                crisis_event_id=crisis_event_id,
            )
        elif self._halt_trigger is not None:
            # Use legacy HaltTrigger (backward compatible)
            self._log.info(
                "using_legacy_halt_trigger",
                transport="HaltTrigger",
            )
            await self._halt_trigger.trigger_halt(
                reason=reason,
                crisis_event_id=crisis_event_id,
            )

    async def _write_witnessed_halt_event(
        self, crisis_payload: ConstitutionalCrisisPayload
    ) -> UUID:
        """Write witnessed halt event to event store (Story 3.9, RT-2).

        Attempts to write a witnessed ConstitutionalCrisisEvent BEFORE halt.
        If write fails, creates an UnwitnessedHaltRecord and continues.

        Constitutional Constraints:
        - RT-2: Event MUST be written BEFORE halt (attempted here)
        - CT-13: If write fails, halt proceeds anyway (integrity over availability)
        - CT-11: Failures are logged at CRITICAL level

        Args:
            crisis_payload: The crisis details to record.

        Returns:
            UUID of the crisis event (from written event or generated placeholder).
        """
        # If no writer configured, fall back to placeholder ID (backward compatible)
        if self._witnessed_halt_writer is None:
            self._log.warning(
                "witnessed_halt_writer_not_configured",
                message="Story 3.9: No witnessed_halt_writer - using placeholder ID",
            )
            return uuid4()

        # Attempt to write witnessed event (RT-2)
        self._log.info("writing_witnessed_halt_event")
        event = await self._witnessed_halt_writer.write_halt_event(crisis_payload)

        if event is not None:
            # Success - use the event's ID
            self._log.info(
                "witnessed_halt_event_written",
                event_id=str(event.event_id),
                sequence=event.sequence,
            )
            return event.event_id

        # Write failed - create UnwitnessedHaltRecord (CT-13: proceed anyway)
        self._log.critical(
            "witnessed_halt_event_write_failed",
            message="CT-13: Halt proceeds despite write failure",
        )

        halt_id = uuid4()
        await self._create_unwitnessed_halt_record(
            halt_id=halt_id,
            crisis_payload=crisis_payload,
            failure_reason="Event store write failed",
        )

        return halt_id

    async def _create_unwitnessed_halt_record(
        self,
        halt_id: UUID,
        crisis_payload: ConstitutionalCrisisPayload,
        failure_reason: str,
    ) -> None:
        """Create UnwitnessedHaltRecord for later reconciliation (Story 3.9).

        When witnessed event write fails, we still halt (CT-13) but create
        this record so the halt can be reconciled into the event store
        later via ceremony.

        Args:
            halt_id: UUID to use for this halt.
            crisis_payload: The crisis details.
            failure_reason: Why the witnessed write failed.
        """
        if self._unwitnessed_halt_repository is None:
            self._log.critical(
                "unwitnessed_halt_repository_not_configured",
                halt_id=str(halt_id),
                message="Cannot save unwitnessed halt record - repository not configured",
            )
            return

        record = UnwitnessedHaltRecord(
            halt_id=halt_id,
            crisis_payload=crisis_payload,
            failure_reason=failure_reason,
            fallback_timestamp=datetime.now(timezone.utc),
        )

        await self._unwitnessed_halt_repository.save(record)

        self._log.critical(
            "unwitnessed_halt_record_created",
            halt_id=str(halt_id),
            failure_reason=failure_reason,
            message="Halt will proceed - record saved for later reconciliation",
        )

    def reset(self) -> None:
        """Reset service state (for testing only).

        WARNING: This should NEVER be called in production.
        Halt state is sticky per ADR-3.
        """
        self._halt_triggered = False
        self._crisis_event_id = None
