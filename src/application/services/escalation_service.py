"""Escalation Service (Story 6.2, FR31).

This service manages breach escalation and acknowledgment for the 7-day
escalation mechanism per FR31.

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All escalation events must be witnessed
3. FAIL LOUD - Never silently swallow escalation detection
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.breach_repository import BreachRepositoryProtocol
from src.application.ports.escalation_repository import EscalationRepositoryProtocol
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.escalation import (
    BreachAlreadyAcknowledgedError,
    BreachAlreadyEscalatedError,
    BreachNotFoundError,
    InvalidAcknowledgmentError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import BreachEventPayload
from src.domain.events.escalation import (
    BREACH_ACKNOWLEDGED_EVENT_TYPE,
    ESCALATION_EVENT_TYPE,
    BreachAcknowledgedEventPayload,
    EscalationEventPayload,
    ResponseChoice,
)
from src.domain.models.pending_escalation import (
    ESCALATION_THRESHOLD_DAYS,
    PendingEscalation,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()

# System agent ID for escalation events
ESCALATION_SYSTEM_AGENT_ID: str = "escalation_system"


class EscalationService:
    """Manages breach escalation and acknowledgment (FR31).

    This service provides:
    1. Automatic escalation check for breaches > 7 days old (FR31)
    2. Breach acknowledgment to stop escalation timer (FR31)
    3. Pending escalation queries with time remaining (FR31)
    4. Halt-aware operations (CT-11)

    Constitutional Constraints:
    - FR31: Unacknowledged breaches after 7 days SHALL escalate
    - CT-11: HALT CHECK FIRST at every operation
    - CT-12: All escalation events MUST be witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - All events are witnessed via EventWriterService
    3. FAIL LOUD - Raise specific errors for failures
    """

    def __init__(
        self,
        breach_repository: BreachRepositoryProtocol,
        escalation_repository: EscalationRepositoryProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Escalation Service.

        Args:
            breach_repository: Repository for breach queries.
            escalation_repository: Repository for escalation/acknowledgment storage.
            event_writer: Service for writing witnessed events (CT-12).
            halt_checker: Interface to check system halt state (CT-11).
        """
        self._breach_repository = breach_repository
        self._escalation_repository = escalation_repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def check_and_escalate_breaches(self) -> list[EscalationEventPayload]:
        """Check all breaches and escalate those > 7 days old (FR31).

        This method is designed to be called periodically (e.g., hourly or daily).
        It is idempotent - calling multiple times will not create duplicate
        escalations.

        Constitutional Constraints:
        - FR31: Unacknowledged breaches after 7 days SHALL escalate
        - CT-11: HALT CHECK FIRST
        - CT-12: Escalation events MUST be witnessed

        Returns:
            List of newly created EscalationEventPayload.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="check_and_escalate_breaches")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "escalation_check_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Get all breaches (FR31)
        # =====================================================================
        all_breaches = await self._breach_repository.list_all()
        now = datetime.now(timezone.utc)
        threshold = timedelta(days=ESCALATION_THRESHOLD_DAYS)
        escalated: list[EscalationEventPayload] = []

        log.info(
            "escalation_check_started",
            total_breaches=len(all_breaches),
            threshold_days=ESCALATION_THRESHOLD_DAYS,
        )

        for breach in all_breaches:
            # Check age
            age = now - breach.detection_timestamp
            if age < threshold:
                continue  # Not old enough to escalate

            # Check if already acknowledged
            ack = await self._escalation_repository.get_acknowledgment_for_breach(
                breach.breach_id
            )
            if ack is not None:
                continue  # Already acknowledged

            # Check if already escalated
            existing = await self._escalation_repository.get_escalation_for_breach(
                breach.breach_id
            )
            if existing is not None:
                continue  # Already escalated

            # =====================================================================
            # Create escalation (FR31, CT-12)
            # =====================================================================
            try:
                escalation = await self._escalate_breach_internal(breach, age)
                escalated.append(escalation)
            except Exception as e:
                log.error(
                    "escalation_failed",
                    breach_id=str(breach.breach_id),
                    error=str(e),
                )
                # Continue processing other breaches (fail loud for this one, but continue)
                continue

        log.info(
            "escalation_check_completed",
            escalated_count=len(escalated),
            total_checked=len(all_breaches),
        )

        return escalated

    async def _escalate_breach_internal(
        self,
        breach: BreachEventPayload,
        age: timedelta,
    ) -> EscalationEventPayload:
        """Internal method to escalate a single breach.

        Args:
            breach: The breach to escalate.
            age: Time since breach detection.

        Returns:
            The created EscalationEventPayload.
        """
        log = logger.bind(
            operation="escalate_breach",
            breach_id=str(breach.breach_id),
            breach_type=breach.breach_type.value,
            days_old=age.days,
        )

        escalation_id = uuid4()
        escalation_timestamp = datetime.now(timezone.utc)
        days_since = age.days

        payload = EscalationEventPayload(
            escalation_id=escalation_id,
            breach_id=breach.breach_id,
            breach_type=breach.breach_type,
            escalation_timestamp=escalation_timestamp,
            days_since_breach=days_since,
            agenda_placement_reason=f"7-day unacknowledged breach per FR31 (actual: {days_since} days)",
        )

        # =====================================================================
        # Write witnessed event (CT-12)
        # =====================================================================
        await self._event_writer.write_event(
            event_type=ESCALATION_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=ESCALATION_SYSTEM_AGENT_ID,
            local_timestamp=escalation_timestamp,
        )

        # Save to repository
        await self._escalation_repository.save_escalation(payload)

        log.warning(
            "fr31_breach_escalated_to_agenda",
            escalation_id=str(escalation_id),
            days_since_breach=days_since,
            agenda_placement_reason=payload.agenda_placement_reason,
        )

        return payload

    async def escalate_breach(self, breach_id: UUID) -> EscalationEventPayload:
        """Manually escalate a specific breach to Conclave agenda (FR31).

        CRITICAL: Must check halt state before operation (CT-11).
        CRITICAL: Event MUST be witnessed (CT-12).

        Args:
            breach_id: UUID of the breach to escalate.

        Returns:
            The created EscalationEventPayload.

        Raises:
            BreachNotFoundError: If breach does not exist.
            BreachAlreadyEscalatedError: If breach was already escalated.
            SystemHaltedError: If system is in halted state.
        """
        log = logger.bind(
            operation="escalate_breach",
            breach_id=str(breach_id),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "escalation_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Validate breach exists (FR31)
        # =====================================================================
        breach = await self._breach_repository.get_by_id(breach_id)
        if breach is None:
            log.warning("escalation_rejected_breach_not_found")
            raise BreachNotFoundError(breach_id)

        # Check if already escalated
        existing = await self._escalation_repository.get_escalation_for_breach(
            breach_id
        )
        if existing is not None:
            log.warning("escalation_rejected_already_escalated")
            raise BreachAlreadyEscalatedError(breach_id)

        # Calculate age
        now = datetime.now(timezone.utc)
        age = now - breach.detection_timestamp

        return await self._escalate_breach_internal(breach, age)

    async def acknowledge_breach(
        self,
        breach_id: UUID,
        acknowledged_by: str,
        response_choice: ResponseChoice,
    ) -> BreachAcknowledgedEventPayload:
        """Acknowledge a breach, stopping escalation timer (FR31).

        Constitutional Constraint (FR31):
        Acknowledgment stops the 7-day escalation timer.

        CRITICAL: Must check halt state before operation (CT-11).
        CRITICAL: Event MUST be witnessed (CT-12).

        Args:
            breach_id: UUID of the breach to acknowledge.
            acknowledged_by: Attribution of who is acknowledging.
            response_choice: The type of response taken.

        Returns:
            The created BreachAcknowledgedEventPayload.

        Raises:
            BreachNotFoundError: If breach does not exist.
            BreachAlreadyAcknowledgedError: If breach was already acknowledged.
            InvalidAcknowledgmentError: If acknowledgment details are invalid.
            SystemHaltedError: If system is in halted state.
        """
        log = logger.bind(
            operation="acknowledge_breach",
            breach_id=str(breach_id),
            acknowledged_by=acknowledged_by,
            response_choice=response_choice.value,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "acknowledgment_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Validate inputs (FR31)
        # =====================================================================
        if not acknowledged_by or not acknowledged_by.strip():
            log.warning("acknowledgment_rejected_empty_attribution")
            raise InvalidAcknowledgmentError("acknowledged_by cannot be empty")

        # =====================================================================
        # Validate breach exists (FR31)
        # =====================================================================
        breach = await self._breach_repository.get_by_id(breach_id)
        if breach is None:
            log.warning("acknowledgment_rejected_breach_not_found")
            raise BreachNotFoundError(breach_id)

        # Check if already acknowledged
        existing = await self._escalation_repository.get_acknowledgment_for_breach(
            breach_id
        )
        if existing is not None:
            log.warning("acknowledgment_rejected_already_acknowledged")
            raise BreachAlreadyAcknowledgedError(breach_id)

        # =====================================================================
        # Create acknowledgment (FR31, CT-12)
        # =====================================================================
        acknowledgment_id = uuid4()
        acknowledgment_timestamp = datetime.now(timezone.utc)

        payload = BreachAcknowledgedEventPayload(
            acknowledgment_id=acknowledgment_id,
            breach_id=breach_id,
            acknowledged_by=acknowledged_by.strip(),
            acknowledgment_timestamp=acknowledgment_timestamp,
            response_choice=response_choice,
        )

        # =====================================================================
        # Write witnessed event (CT-12)
        # =====================================================================
        await self._event_writer.write_event(
            event_type=BREACH_ACKNOWLEDGED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=ESCALATION_SYSTEM_AGENT_ID,
            local_timestamp=acknowledgment_timestamp,
        )

        # Save to repository
        await self._escalation_repository.save_acknowledgment(payload)

        log.info(
            "fr31_breach_acknowledged",
            acknowledgment_id=str(acknowledgment_id),
            response_choice=response_choice.value,
        )

        return payload

    async def get_pending_escalations(self) -> list[PendingEscalation]:
        """Get all breaches approaching 7-day escalation deadline (FR31).

        Constitutional Constraint (FR31):
        Query pending escalations to see breaches approaching deadline
        and time remaining.

        CRITICAL: Must check halt state before operation (CT-11).

        Returns:
            List of PendingEscalation sorted by urgency (least time remaining first).

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        log = logger.bind(operation="get_pending_escalations")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "pending_query_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Get pending escalations (FR31)
        # =====================================================================
        all_breaches = await self._breach_repository.list_all()
        now = datetime.now(timezone.utc)
        pending: list[PendingEscalation] = []

        for breach in all_breaches:
            # Check if already acknowledged
            ack = await self._escalation_repository.get_acknowledgment_for_breach(
                breach.breach_id
            )
            if ack is not None:
                continue  # Already acknowledged

            # Check if already escalated
            existing = await self._escalation_repository.get_escalation_for_breach(
                breach.breach_id
            )
            if existing is not None:
                continue  # Already escalated

            # Create pending escalation with time remaining
            pending_esc = PendingEscalation.from_breach(
                breach_id=breach.breach_id,
                breach_type=breach.breach_type,
                detection_timestamp=breach.detection_timestamp,
                current_time=now,
            )
            pending.append(pending_esc)

        # Sort by urgency (least time remaining first = most urgent)
        pending.sort(key=lambda p: p.hours_remaining)

        log.info(
            "pending_escalations_retrieved",
            count=len(pending),
        )

        return pending

    async def is_breach_acknowledged(self, breach_id: UUID) -> bool:
        """Check if a breach has been acknowledged (FR31).

        Args:
            breach_id: UUID of the breach to check.

        Returns:
            True if breach has been acknowledged, False otherwise.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        ack = await self._escalation_repository.get_acknowledgment_for_breach(breach_id)
        return ack is not None

    async def is_breach_escalated(self, breach_id: UUID) -> bool:
        """Check if a breach has been escalated (FR31).

        Args:
            breach_id: UUID of the breach to check.

        Returns:
            True if breach has been escalated, False otherwise.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        esc = await self._escalation_repository.get_escalation_for_breach(breach_id)
        return esc is not None

    async def get_breach_status(self, breach_id: UUID) -> dict[str, Any] | None:
        """Get the escalation/acknowledgment status of a breach (FR31).

        Args:
            breach_id: UUID of the breach to check.

        Returns:
            Dict with keys: is_acknowledged, is_escalated,
            acknowledgment_details, escalation_details.
            None if breach not found.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        log = logger.bind(
            operation="get_breach_status",
            breach_id=str(breach_id),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "status_query_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # Check if breach exists
        breach = await self._breach_repository.get_by_id(breach_id)
        if breach is None:
            return None

        # Get acknowledgment and escalation
        ack = await self._escalation_repository.get_acknowledgment_for_breach(breach_id)
        esc = await self._escalation_repository.get_escalation_for_breach(breach_id)

        return {
            "is_acknowledged": ack is not None,
            "is_escalated": esc is not None,
            "acknowledgment_details": {
                "acknowledgment_id": str(ack.acknowledgment_id),
                "acknowledged_by": ack.acknowledged_by,
                "acknowledgment_timestamp": ack.acknowledgment_timestamp.isoformat(),
                "response_choice": ack.response_choice.value,
            }
            if ack
            else None,
            "escalation_details": {
                "escalation_id": str(esc.escalation_id),
                "escalation_timestamp": esc.escalation_timestamp.isoformat(),
                "days_since_breach": esc.days_since_breach,
                "agenda_placement_reason": esc.agenda_placement_reason,
            }
            if esc
            else None,
        }
