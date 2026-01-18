"""Cessation Consideration Service (Story 6.3, FR32).

This service manages automatic cessation consideration triggers and
Conclave decisions per FR32.

Constitutional Constraints:
- FR32: >10 unacknowledged breaches in 90 days SHALL trigger cessation consideration
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All cessation events must be witnessed
3. FAIL LOUD - Never silently swallow cessation detection
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.breach_repository import BreachRepositoryProtocol
from src.application.ports.cessation_repository import CessationRepositoryProtocol
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.cessation import (
    CessationConsiderationNotFoundError,
    InvalidCessationDecisionError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.cessation import (
    CESSATION_CONSIDERATION_EVENT_TYPE,
    CESSATION_DECISION_EVENT_TYPE,
    CessationConsiderationEventPayload,
    CessationDecision,
    CessationDecisionEventPayload,
)
from src.domain.models.breach_count_status import (
    CESSATION_THRESHOLD,
    CESSATION_WINDOW_DAYS,
    WARNING_THRESHOLD,
    BreachCountStatus,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()

# System agent ID for cessation events
CESSATION_SYSTEM_AGENT_ID: str = "cessation_system"


class CessationConsiderationService:
    """Manages cessation consideration triggers and decisions (FR32).

    This service provides:
    1. Automatic cessation trigger when >10 unacknowledged breaches in 90 days (FR32)
    2. Conclave decision recording for cessation considerations (FR32)
    3. Breach count status queries with trajectory (FR32)
    4. Halt-aware operations (CT-11)

    Constitutional Constraints:
    - FR32: >10 unacknowledged breaches in 90 days SHALL trigger cessation
    - CT-11: HALT CHECK FIRST at every operation
    - CT-12: All cessation events MUST be witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - All events are witnessed via EventWriterService
    3. FAIL LOUD - Raise specific errors for failures
    """

    def __init__(
        self,
        breach_repository: BreachRepositoryProtocol,
        cessation_repository: CessationRepositoryProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Cessation Consideration Service.

        Args:
            breach_repository: Repository for breach queries.
            cessation_repository: Repository for cessation storage.
            event_writer: Service for writing witnessed events (CT-12).
            halt_checker: Interface to check system halt state (CT-11).
        """
        self._breach_repository = breach_repository
        self._cessation_repository = cessation_repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def check_and_trigger_cessation(
        self,
    ) -> CessationConsiderationEventPayload | None:
        """Check thresholds and trigger cessation consideration if exceeded (FR32).

        This method is designed to be called periodically (e.g., daily).
        It is idempotent - calling multiple times will not create duplicate
        considerations.

        Constitutional Constraints:
        - FR32: Triggers at >10 unacknowledged breaches in 90 days
        - CT-11: HALT CHECK FIRST
        - CT-12: Creates witnessed event via EventWriterService

        Returns:
            CessationConsiderationEventPayload if consideration triggered,
            None if below threshold or consideration already active.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="check_and_trigger_cessation")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "cessation_check_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Check for existing active consideration (FR32)
        # =====================================================================
        active_consideration = (
            await self._cessation_repository.get_active_consideration()
        )
        if active_consideration is not None:
            log.info(
                "cessation_check_skipped_active_exists",
                consideration_id=str(active_consideration.consideration_id),
            )
            return None

        # =====================================================================
        # Get unacknowledged breach count (FR32)
        # =====================================================================
        count = await self._breach_repository.count_unacknowledged_in_window(
            CESSATION_WINDOW_DAYS
        )

        log.info(
            "cessation_check_started",
            unacknowledged_count=count,
            threshold=CESSATION_THRESHOLD,
            window_days=CESSATION_WINDOW_DAYS,
        )

        # =====================================================================
        # Check threshold (FR32: >10 means 11+ triggers)
        # =====================================================================
        if count <= CESSATION_THRESHOLD:
            log.debug(
                "cessation_threshold_not_exceeded",
                current_count=count,
                threshold=CESSATION_THRESHOLD,
            )
            return None

        # =====================================================================
        # Trigger cessation consideration (FR32, CT-12)
        # =====================================================================
        breaches = await self._breach_repository.get_unacknowledged_in_window(
            CESSATION_WINDOW_DAYS
        )
        breach_ids = tuple(b.breach_id for b in breaches)

        consideration_id = uuid4()
        trigger_timestamp = datetime.now(timezone.utc)

        payload = CessationConsiderationEventPayload(
            consideration_id=consideration_id,
            trigger_timestamp=trigger_timestamp,
            breach_count=count,
            window_days=CESSATION_WINDOW_DAYS,
            unacknowledged_breach_ids=breach_ids,
            agenda_placement_reason=f"FR32: >{CESSATION_THRESHOLD} unacknowledged breaches in {CESSATION_WINDOW_DAYS} days",
        )

        # =====================================================================
        # Write witnessed event (CT-12)
        # =====================================================================
        await self._event_writer.write_event(
            event_type=CESSATION_CONSIDERATION_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=CESSATION_SYSTEM_AGENT_ID,
            local_timestamp=trigger_timestamp,
        )

        # Save to repository
        await self._cessation_repository.save_consideration(payload)

        log.warning(
            "fr32_cessation_consideration_triggered",
            consideration_id=str(consideration_id),
            breach_count=count,
            window_days=CESSATION_WINDOW_DAYS,
            agenda_placement_reason=payload.agenda_placement_reason,
        )

        return payload

    async def record_cessation_decision(
        self,
        consideration_id: UUID,
        decision: CessationDecision,
        decided_by: str,
        rationale: str,
    ) -> CessationDecisionEventPayload:
        """Record a Conclave decision on a cessation consideration (FR32).

        Constitutional Constraints:
        - FR32: Decision must be recorded for accountability
        - CT-11: HALT CHECK FIRST
        - CT-12: Creates witnessed event via EventWriterService

        Args:
            consideration_id: The ID of the consideration being decided.
            decision: The decision choice (PROCEED_TO_VOTE, DISMISS, DEFER).
            decided_by: Attribution of decision maker.
            rationale: Reason for the decision.

        Returns:
            CessationDecisionEventPayload for the recorded decision.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            CessationConsiderationNotFoundError: If consideration doesn't exist.
            InvalidCessationDecisionError: If decision already recorded.
        """
        log = logger.bind(
            operation="record_cessation_decision",
            consideration_id=str(consideration_id),
            decision=decision.value,
            decided_by=decided_by,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "decision_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Validate consideration exists (FR32)
        # =====================================================================
        consideration = await self._cessation_repository.get_consideration_by_id(
            consideration_id
        )
        if consideration is None:
            log.warning("decision_rejected_consideration_not_found")
            raise CessationConsiderationNotFoundError(consideration_id)

        # =====================================================================
        # Check no decision already recorded (FR32)
        # =====================================================================
        existing_decision = (
            await self._cessation_repository.get_decision_for_consideration(
                consideration_id
            )
        )
        if existing_decision is not None:
            log.warning(
                "decision_rejected_already_recorded",
                existing_decision_id=str(existing_decision.decision_id),
            )
            raise InvalidCessationDecisionError(
                consideration_id,
                reason="Decision already recorded",
            )

        # =====================================================================
        # Validate inputs (FR32)
        # =====================================================================
        if not decided_by or not decided_by.strip():
            log.warning("decision_rejected_empty_attribution")
            raise InvalidCessationDecisionError(
                consideration_id,
                reason="decided_by cannot be empty",
            )

        if not rationale or not rationale.strip():
            log.warning("decision_rejected_empty_rationale")
            raise InvalidCessationDecisionError(
                consideration_id,
                reason="rationale cannot be empty",
            )

        # =====================================================================
        # Create decision (FR32, CT-12)
        # =====================================================================
        decision_id = uuid4()
        decision_timestamp = datetime.now(timezone.utc)

        payload = CessationDecisionEventPayload(
            decision_id=decision_id,
            consideration_id=consideration_id,
            decision=decision,
            decision_timestamp=decision_timestamp,
            decided_by=decided_by.strip(),
            rationale=rationale.strip(),
        )

        # =====================================================================
        # Write witnessed event (CT-12)
        # =====================================================================
        await self._event_writer.write_event(
            event_type=CESSATION_DECISION_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=CESSATION_SYSTEM_AGENT_ID,
            local_timestamp=decision_timestamp,
        )

        # Save to repository
        await self._cessation_repository.save_decision(payload)

        log.info(
            "fr32_cessation_decision_recorded",
            decision_id=str(decision_id),
            decision=decision.value,
            decided_by=decided_by,
        )

        return payload

    async def get_breach_count_status(self) -> BreachCountStatus:
        """Get current unacknowledged breach count status (FR32).

        Constitutional Constraints:
        - FR32: Provides visibility into breach counts
        - CT-11: HALT CHECK FIRST

        Returns:
            BreachCountStatus with count, trajectory, and alert thresholds.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="get_breach_count_status")

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

        # =====================================================================
        # Get unacknowledged breaches (FR32)
        # =====================================================================
        breaches = await self._breach_repository.get_unacknowledged_in_window(
            CESSATION_WINDOW_DAYS
        )

        status = BreachCountStatus.from_breaches(breaches)

        log.info(
            "breach_count_status_retrieved",
            current_count=status.current_count,
            trajectory=status.trajectory.value,
            urgency_level=status.urgency_level,
        )

        return status

    async def get_breach_alert_status(self) -> str | None:
        """Get breach alert status if at warning or critical level (FR32).

        Constitutional Constraints:
        - FR32: Alert at warning (8+) and critical (>10) thresholds
        - CT-11: HALT CHECK FIRST

        Returns:
            "CRITICAL" if count > 10,
            "WARNING" if count >= 8,
            None if below warning threshold.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="get_breach_alert_status")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "alert_query_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Get breach count (FR32)
        # =====================================================================
        count = await self._breach_repository.count_unacknowledged_in_window(
            CESSATION_WINDOW_DAYS
        )

        if count > CESSATION_THRESHOLD:
            log.warning(
                "fr32_breach_alert_critical",
                count=count,
                threshold=CESSATION_THRESHOLD,
            )
            return "CRITICAL"

        if count >= WARNING_THRESHOLD:
            log.warning(
                "fr32_breach_alert_warning",
                count=count,
                warning_threshold=WARNING_THRESHOLD,
            )
            return "WARNING"

        return None

    async def is_cessation_consideration_active(self) -> bool:
        """Check if a cessation consideration is currently active (FR32).

        A consideration is active if it exists and has not received
        a Conclave decision yet.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            True if an active consideration exists, False otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        active = await self._cessation_repository.get_active_consideration()
        return active is not None

    async def get_active_consideration(
        self,
    ) -> CessationConsiderationEventPayload | None:
        """Get the currently active cessation consideration (FR32).

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            The active consideration or None if no active consideration.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        return await self._cessation_repository.get_active_consideration()
