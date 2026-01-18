"""CessationTriggerService for system lifecycle management.

Story: consent-gov-8.1: System Cessation Trigger

This service handles system cessation triggering. Cessation is the permanent,
irreversible shutdown of the governance system.

IMPORTANT: Cessation is IRREVERSIBLE. This service intentionally has NO:
- cancel_cessation()
- undo_cessation()
- rollback_cessation()
- resume_operations()

Constitutional Context:
- FR47: Human Operator can trigger cessation
- FR49: System can block new motions on cessation
- FR50: System can halt execution on cessation
- AC4: Cessation requires Human Operator authentication
- AC5: Event `constitutional.cessation.triggered` emitted
- AC6: Cessation trigger is irreversible (no "undo")

Design Principles:
- Irreversibility is structural, not policy
- Graceful shutdown where possible
- Honor in-flight commitments
- Full audit trail via events
"""

from uuid import UUID, uuid4

from src.application.ports.governance.cessation_port import (
    CessationPort,
    ExecutionHalterPort,
    MotionBlockerPort,
)
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.cessation import (
    CessationAlreadyTriggeredError,
    CessationState,
    CessationStatus,
    CessationTrigger,
)

# Default grace period for in-flight operations (60 seconds)
DEFAULT_GRACE_PERIOD_SECONDS = 60


class CessationTriggerService:
    """Handles system cessation triggering.

    Cessation is IRREVERSIBLE. No cancel/undo/rollback methods exist.

    This service:
    1. Validates system is not already ceased
    2. Creates the CessationTrigger record
    3. Emits constitutional.cessation.triggered event
    4. Blocks new motions
    5. Begins graceful execution halt
    6. Records trigger to cessation port

    Example:
        service = CessationTriggerService(...)
        trigger = await service.trigger_cessation(
            operator_id=operator_uuid,
            reason="Planned system retirement",
        )
        # System is now in CESSATION_TRIGGERED state
        # New motions blocked, existing operations completing

    Note: There are intentionally NO methods for:
    - Cancelling cessation
    - Undoing cessation
    - Rolling back cessation
    - Resuming operations
    """

    def __init__(
        self,
        cessation_port: CessationPort,
        motion_blocker: MotionBlockerPort,
        execution_halter: ExecutionHalterPort,
        event_emitter: TwoPhaseEventEmitterPort,
        time_authority: TimeAuthorityProtocol,
        grace_period_seconds: int = DEFAULT_GRACE_PERIOD_SECONDS,
    ) -> None:
        """Initialize CessationTriggerService.

        Args:
            cessation_port: Port for cessation state operations.
            motion_blocker: Port for blocking new motions.
            execution_halter: Port for halting execution.
            event_emitter: Port for emitting two-phase events.
            time_authority: TimeAuthority for timestamps.
            grace_period_seconds: Time allowed for graceful completion.
        """
        self._cessation = cessation_port
        self._motion_blocker = motion_blocker
        self._execution_halter = execution_halter
        self._event_emitter = event_emitter
        self._time = time_authority
        self._grace_period = grace_period_seconds

    async def trigger_cessation(
        self,
        operator_id: UUID,
        reason: str,
    ) -> CessationTrigger:
        """Trigger system cessation.

        This is IRREVERSIBLE. There is no cancel/undo method.

        When triggered:
        - New motions are blocked immediately
        - Existing in-progress operations continue (grace period)
        - Event `constitutional.cessation.triggered` is emitted
        - System transitions to CESSATION_TRIGGERED state

        Args:
            operator_id: The Human Operator triggering cessation.
            reason: Required documentation of why cessation is triggered.

        Returns:
            CessationTrigger record.

        Raises:
            CessationAlreadyTriggeredError: If cessation already in progress.
            ValueError: If reason is empty.
        """
        now = self._time.utcnow()

        # Validate reason is provided
        if not reason or not reason.strip():
            raise ValueError("Cessation reason is required and cannot be empty")

        # Check if already triggered
        current_state = await self._cessation.get_state()
        if current_state.status != CessationStatus.ACTIVE:
            if current_state.trigger is None:
                raise CessationAlreadyTriggeredError(
                    original_trigger_id=uuid4(),  # Unknown
                    original_triggered_at=now,
                    message="Cessation already in progress but trigger details unavailable",
                )
            raise CessationAlreadyTriggeredError(
                original_trigger_id=current_state.trigger.trigger_id,
                original_triggered_at=current_state.trigger.triggered_at,
                original_operator_id=current_state.trigger.operator_id,
            )

        # Create trigger record
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=operator_id,
            triggered_at=now,
            reason=reason.strip(),
        )

        # Emit two-phase event: intent
        correlation_id = await self._event_emitter.emit_intent(
            operation_type="constitutional.cessation.triggered",
            actor_id=str(operator_id),
            target_entity_id=str(trigger.trigger_id),
            intent_payload={
                "trigger_id": str(trigger.trigger_id),
                "operator_id": str(operator_id),
                "triggered_at": now.isoformat(),
                "reason": trigger.reason,
            },
        )

        try:
            # Block new motions
            await self._motion_blocker.block_new_motions(
                reason="cessation_triggered",
            )

            # Get current in-flight count
            in_flight_count = await self._execution_halter.get_in_flight_count()

            # Begin execution halt
            await self._execution_halter.begin_halt(
                trigger_id=str(trigger.trigger_id),
                grace_period_seconds=self._grace_period,
            )

            # Record trigger to cessation port
            await self._cessation.record_trigger(trigger)

            # Update in-flight count
            await self._cessation.update_in_flight_count(in_flight_count)

            # Emit two-phase event: commit
            await self._event_emitter.emit_commit(
                correlation_id=correlation_id,
                outcome_payload={
                    "trigger_id": str(trigger.trigger_id),
                    "motions_blocked": True,
                    "execution_halt_begun": True,
                    "in_flight_count": in_flight_count,
                    "grace_period_seconds": self._grace_period,
                },
            )

            return trigger

        except Exception as e:
            # Emit two-phase event: failure
            await self._event_emitter.emit_failure(
                correlation_id=correlation_id,
                failure_reason=str(e),
                failure_details={
                    "trigger_id": str(trigger.trigger_id),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def get_state(self) -> CessationState:
        """Get current cessation state.

        Returns:
            CessationState with status, trigger (if any), and operational flags.
        """
        return await self._cessation.get_state()

    async def check_and_finalize(self) -> bool:
        """Check if cessation is complete and finalize if so.

        Called periodically to check if all in-flight operations have
        completed. If so, marks the system as CEASED.

        Returns:
            True if system is now CEASED, False if still CESSATION_TRIGGERED.
        """
        current_state = await self._cessation.get_state()

        # Only finalize if in CESSATION_TRIGGERED state
        if current_state.status != CessationStatus.CESSATION_TRIGGERED:
            return current_state.status == CessationStatus.CEASED

        # Check if halt is complete
        if await self._execution_halter.is_halt_complete():
            await self._cessation.mark_ceased()
            return True

        # Update in-flight count
        count = await self._execution_halter.get_in_flight_count()
        await self._cessation.update_in_flight_count(count)

        return False

    async def force_finalize(self) -> int:
        """Force finalize cessation after grace period.

        Forcefully stops remaining operations and marks system as CEASED.

        Returns:
            Number of operations that were forcefully stopped.

        Note: This should only be called after the grace period has elapsed.
        """
        # Force halt remaining operations
        force_stopped = await self._execution_halter.force_halt()

        # Mark as ceased
        await self._cessation.mark_ceased()

        return force_stopped

    # ==========================================================================
    # INTENTIONALLY NON-EXISTENT METHODS
    # ==========================================================================
    # These methods do NOT exist because cessation is IRREVERSIBLE:
    #
    # async def cancel_cessation(self, ...): ...
    # async def undo_cessation(self, ...): ...
    # async def rollback_cessation(self, ...): ...
    # async def resume_operations(self, ...): ...
    # async def abort_cessation(self, ...): ...
    # async def revert_cessation(self, ...): ...
    #
    # If you want the system back:
    # - Create a NEW instance
    # - New legitimacy starts at baseline
    # - No claim to previous instance
    # - Fresh constitutional foundation
    # ==========================================================================
