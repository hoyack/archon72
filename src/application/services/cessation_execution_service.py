"""Cessation Execution Service (Story 7.4, FR41; Story 7.6, FR43; Story 7.8, FR135).

This service handles the execution of cessation, which is the
permanent termination of the system. Once executed, no further
events can be written.

Constitutional Constraints:
- FR41: Freeze on new actions except record preservation
- FR43: Cessation as final recorded event (Story 7.6)
- FR135: Final deliberation SHALL be recorded before cessation (Story 7.8)
- CT-11: Silent failure destroys legitimacy -> Log ALL execution details
- CT-12: Witnessing creates accountability -> Cessation must be witnessed
- CT-13: Integrity outranks availability -> Permanent termination
- ADR-3: Dual-channel pattern -> Set flag in both Redis and DB

Responsibilities:
1. Record final deliberation (FR135) - BEFORE cessation event
2. Write the cessation event (FINAL event - FR43)
3. Set dual-channel cessation flag atomically (ADR-3)
4. Log execution with full context (CT-11)
5. Ensure witness attribution (CT-12)

This service is called by the deliberation system when a
cessation vote passes (FR37, FR38, FR39 triggers).

CRITICAL: This is a ONE-WAY operation. Once execute_cessation()
succeeds, the system is permanently terminated.

Story 7.6 FR43 Compliance:
- Cessation event is the FINAL event in the event store
- final_sequence in payload IS the cessation event's sequence
- Event is written BEFORE freeze flag is set (atomic sequence)
- If event write fails, no freeze flag is set
- If freeze flag fails, CRITICAL log is emitted for human intervention

Story 7.8 FR135 Compliance:
- Final deliberation is recorded BEFORE cessation event
- If deliberation recording fails, that failure is the final event
- All 72 Archon votes must be recorded
- Dissent percentage visible (FR12)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.domain.events.cessation_executed import (
    CESSATION_EXECUTED_EVENT_TYPE,
    CessationExecutedEventPayload,
)
from src.domain.models.ceased_status_header import CessationDetails

if TYPE_CHECKING:
    from src.application.ports.cessation_flag_repository import (
        CessationFlagRepositoryProtocol,
    )
    from src.application.ports.event_store import EventStorePort
    from src.application.services.event_writer_service import EventWriterService
    from src.application.services.final_deliberation_service import (
        FinalDeliberationService,
    )
    from src.domain.events.cessation_deliberation import ArchonDeliberation
    from src.domain.events.event import Event

logger = get_logger()


class CessationExecutionError(Exception):
    """Error during cessation execution.

    This error indicates a failure during the cessation process.
    Depending on the stage, the system may be in an inconsistent state.
    Human intervention is required.
    """

    pass


class CessationExecutionService:
    """Service for executing system cessation (FR41, AC1, AC8).

    This service coordinates the permanent termination of the system:
    1. Retrieves the current head event for final hash
    2. Creates the cessation event payload
    3. Writes the cessation event via EventWriterService
    4. Sets the dual-channel cessation flag

    Constitutional Constraint (CT-12):
    The cessation event MUST be witnessed. This is handled by
    EventWriterService which delegates to AtomicEventWriter.

    Developer Golden Rules:
    1. ONE-WAY - Cessation is irreversible
    2. WITNESS EVERYTHING - CT-12 requires witness attribution
    3. LOG EVERYTHING - CT-11 requires full context logging
    4. FAIL LOUD - Any failure requires human intervention

    Attributes:
        _event_writer: Service for writing events (handles witnessing).
        _event_store: Direct access to read current head.
        _cessation_flag_repo: Dual-channel cessation flag storage.
    """

    def __init__(
        self,
        event_writer: EventWriterService,
        event_store: EventStorePort,
        cessation_flag_repo: CessationFlagRepositoryProtocol,
        final_deliberation_service: FinalDeliberationService | None = None,
    ) -> None:
        """Initialize CessationExecutionService.

        Args:
            event_writer: Service for writing events (handles witnessing).
            event_store: Direct access to read current head event.
            cessation_flag_repo: Dual-channel cessation flag storage.
            final_deliberation_service: Optional service for recording final
                deliberation (FR135). If provided, execute_cessation_with_deliberation()
                will record the deliberation before the cessation event.
        """
        self._event_writer = event_writer
        self._event_store = event_store
        self._cessation_flag_repo = cessation_flag_repo
        self._final_deliberation_service = final_deliberation_service

    async def execute_cessation(
        self,
        *,
        triggering_event_id: UUID,
        reason: str,
        agent_id: str = "SYSTEM:CESSATION",
    ) -> Event:
        """Execute system cessation (IRREVERSIBLE).

        This is a ONE-WAY operation. Once this method succeeds:
        - The cessation event is written (last event ever)
        - The dual-channel cessation flag is set
        - No further events can be written

        Constitutional Constraints:
        - CT-11: Log all execution details
        - CT-12: Cessation event is witnessed
        - CT-13: Integrity > availability (terminate permanently)
        - FR41: Freeze all writes after cessation
        - ADR-3: Set flag in both Redis and database

        Args:
            triggering_event_id: The event that triggered cessation
                (e.g., agenda placement event from FR37/FR38/FR39).
            reason: Human-readable reason for cessation.
            agent_id: Agent executing cessation (default: SYSTEM:CESSATION).

        Returns:
            The cessation Event (last event ever).

        Raises:
            CessationExecutionError: If cessation fails at any stage.
        """
        log = logger.bind(
            operation="execute_cessation",
            triggering_event_id=str(triggering_event_id),
            agent_id=agent_id,
        )

        log.info(
            "cessation_execution_starting",
            reason=reason,
            message="CT-11: Starting irreversible cessation process",
        )

        try:
            # Step 1: Get current head event for final hash
            log.debug("fetching_head_event")
            head_event = await self._event_store.get_latest_event()

            if head_event is None:
                # Cannot cease an empty system - this shouldn't happen
                log.error(
                    "cessation_execution_failed_empty_store",
                    message="Cannot execute cessation on empty event store",
                )
                raise CessationExecutionError(
                    "Cannot execute cessation: event store is empty"
                )

            final_sequence = head_event.sequence
            final_hash = head_event.content_hash

            log.info(
                "cessation_head_event_retrieved",
                final_sequence=final_sequence,
                final_hash=final_hash[:16] + "...",
            )

            # Step 2: Create cessation event payload
            execution_timestamp = datetime.now(timezone.utc)
            cessation_id = uuid4()

            payload = CessationExecutedEventPayload.create(
                cessation_id=cessation_id,
                execution_timestamp=execution_timestamp,
                final_sequence_number=final_sequence,
                final_hash=final_hash,
                reason=reason,
                triggering_event_id=triggering_event_id,
            )

            log.info(
                "cessation_payload_created",
                cessation_id=str(cessation_id),
                execution_timestamp=execution_timestamp.isoformat(),
                is_terminal=payload.is_terminal,
            )

            # Step 3: Write the cessation event
            # This will be the LAST event ever written
            log.info(
                "cessation_event_writing",
                message="CT-12: Writing witnessed cessation event (last event ever)",
            )

            cessation_event = await self._event_writer.write_event(
                event_type=CESSATION_EXECUTED_EVENT_TYPE,
                payload=payload.to_dict(),
                agent_id=agent_id,
                local_timestamp=execution_timestamp,
            )

            log.info(
                "cessation_event_written",
                event_id=str(cessation_event.event_id),
                sequence=cessation_event.sequence,
                content_hash=cessation_event.content_hash[:16] + "...",
                message="FR43: Cessation event is now the FINAL event in the store",
            )

            # FR43: Log that this is the terminal event
            log.info(
                "fr43_final_event_confirmed",
                final_sequence=cessation_event.sequence,
                is_terminal=True,
                message="FR43: No further events may be appended after this point",
            )

            # Step 4: Set the dual-channel cessation flag (ADR-3)
            log.info(
                "cessation_flag_setting",
                message="ADR-3: Setting dual-channel cessation flag",
            )

            cessation_details = CessationDetails(
                ceased_at=execution_timestamp,
                final_sequence_number=cessation_event.sequence,
                reason=reason,
                cessation_event_id=cessation_event.event_id,
            )

            try:
                await self._cessation_flag_repo.set_ceased(cessation_details)

                log.info(
                    "cessation_flag_set",
                    ceased_at=execution_timestamp.isoformat(),
                    final_sequence=cessation_event.sequence,
                    message="Dual-channel cessation flag set successfully",
                )
            except Exception as flag_error:
                # FR43 AC5: If freeze flag fails after event write, log CRITICAL
                # The cessation event EXISTS - it is the source of truth
                # Human intervention is required to set the freeze flag
                log.critical(
                    "cessation_flag_set_failed_after_event_written",
                    cessation_event_id=str(cessation_event.event_id),
                    cessation_sequence=cessation_event.sequence,
                    flag_error=str(flag_error),
                    message=(
                        "FR43 AC5: Cessation event written successfully, but freeze flag "
                        "setting FAILED. The cessation event is the source of truth. "
                        "HUMAN INTERVENTION REQUIRED to set freeze flag. "
                        "System may accept writes until flag is set."
                    ),
                )
                # Wrap in CessationExecutionError for consistent error typing (Finding 6 fix)
                raise CessationExecutionError(
                    f"Cessation event written (seq={cessation_event.sequence}) but "
                    f"flag setting failed: {flag_error}. "
                    f"HUMAN INTERVENTION REQUIRED to set freeze flag."
                ) from flag_error

            # Step 5: Final confirmation log
            log.critical(
                "cessation_execution_complete",
                cessation_id=str(cessation_id),
                cessation_event_id=str(cessation_event.event_id),
                final_sequence=cessation_event.sequence,
                reason=reason,
                message=(
                    "CT-11: SYSTEM CESSATION COMPLETE. "
                    "No further events will be accepted. "
                    "This is IRREVERSIBLE."
                ),
            )

            return cessation_event

        except CessationExecutionError:
            raise
        except Exception as e:
            log.critical(
                "cessation_execution_failed",
                error=str(e),
                error_type=type(e).__name__,
                message=(
                    "CT-11: Cessation execution failed. "
                    "HUMAN INTERVENTION REQUIRED. "
                    "System may be in inconsistent state."
                ),
            )
            raise CessationExecutionError(f"Cessation execution failed: {e}") from e

    async def execute_cessation_with_deliberation(
        self,
        *,
        deliberation_id: UUID,
        deliberation_started_at: datetime,
        deliberation_ended_at: datetime,
        archon_deliberations: list[ArchonDeliberation],
        triggering_event_id: UUID,
        reason: str,
        agent_id: str = "SYSTEM:CESSATION",
    ) -> Event:
        """Execute cessation with final deliberation recording (FR135).

        This method records the final deliberation BEFORE executing cessation.
        Per FR135: Final deliberation SHALL be recorded and immutable;
        if recording fails, that failure is the final event.

        CRITICAL: If deliberation recording fails, the failure event becomes
        the final event and cessation is NOT executed.

        Args:
            deliberation_id: Unique ID for the deliberation.
            deliberation_started_at: When deliberation began (UTC).
            deliberation_ended_at: When deliberation concluded (UTC).
            archon_deliberations: All 72 Archon deliberations.
            triggering_event_id: Event that triggered cessation.
            reason: Human-readable reason for cessation.
            agent_id: Agent executing cessation.

        Returns:
            The cessation Event (last event ever).

        Raises:
            CessationExecutionError: If deliberation service not configured
                or cessation fails.
        """
        log = logger.bind(
            operation="execute_cessation_with_deliberation",
            deliberation_id=str(deliberation_id),
            triggering_event_id=str(triggering_event_id),
        )

        if self._final_deliberation_service is None:
            log.error(
                "final_deliberation_service_not_configured",
                message="FR135: Cannot execute cessation with deliberation - service not configured",
            )
            raise CessationExecutionError(
                "FR135: FinalDeliberationService not configured"
            )

        log.info(
            "fr135_recording_deliberation",
            archon_count=len(archon_deliberations),
            message="FR135: Recording final deliberation before cessation",
        )

        # Step 1: Record the final deliberation (FR135)
        from src.application.services.final_deliberation_service import (
            DeliberationRecordingCompleteFailure,
        )

        try:
            deliberation_result = (
                await self._final_deliberation_service.record_and_proceed(
                    deliberation_id=deliberation_id,
                    started_at=deliberation_started_at,
                    ended_at=deliberation_ended_at,
                    archon_deliberations=archon_deliberations,
                )
            )

            log.info(
                "fr135_deliberation_recorded",
                event_id=str(deliberation_result.event_id),
                success=deliberation_result.success,
                message="FR135: Final deliberation recorded successfully",
            )

        except DeliberationRecordingCompleteFailure as e:
            # FR135: If recording fails completely, system must HALT
            log.critical(
                "fr135_complete_failure",
                error_code=e.error_code,
                error_message=e.error_message,
                message=(
                    "FR135 VIOLATED: Cannot record deliberation OR failure event. "
                    "SYSTEM MUST HALT. HUMAN INTERVENTION REQUIRED."
                ),
            )
            raise CessationExecutionError(
                f"FR135: Complete deliberation recording failure - {e.error_code}"
            ) from e

        # Step 2: Now execute cessation
        log.info(
            "cessation_proceeding_after_deliberation",
            message="FR135 satisfied - proceeding with cessation",
        )

        return await self.execute_cessation(
            triggering_event_id=triggering_event_id,
            reason=reason,
            agent_id=agent_id,
        )
