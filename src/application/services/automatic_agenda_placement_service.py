"""Automatic agenda placement service (Story 7.1, FR37-FR38, RT-4).

This module implements automatic cessation agenda placement when:
- FR37: 3 consecutive integrity failures occur in 30 days
- FR38: Anti-success alert is sustained for 90 days
- RT-4: 5 non-consecutive failures occur in any 90-day rolling window

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All agenda events must be witnessed
3. FAIL LOUD - Never silently swallow trigger detection
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import structlog

from src.application.ports.anti_success_alert_repository import (
    AntiSuccessAlertRepositoryProtocol,
)
from src.application.ports.cessation_agenda_repository import (
    CessationAgendaRepositoryProtocol,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.integrity_failure_repository import (
    IntegrityFailureRepositoryProtocol,
)
from src.application.services.event_writer_service import EventWriterService
from src.domain.errors import SystemHaltedError
from src.domain.events.cessation_agenda import (
    CESSATION_AGENDA_PLACEMENT_EVENT_TYPE,
    AgendaTriggerType,
    CessationAgendaPlacementEventPayload,
)

log = structlog.get_logger()

# System agent ID for automatic agenda placement
AGENDA_PLACEMENT_SYSTEM_AGENT_ID: str = "system.automatic_agenda_placement"

# Constitutional thresholds (FR37, FR38, RT-4)
CONSECUTIVE_FAILURE_THRESHOLD: int = 3
CONSECUTIVE_FAILURE_WINDOW_DAYS: int = 30
ROLLING_WINDOW_THRESHOLD: int = 5
ROLLING_WINDOW_DAYS: int = 90
ANTI_SUCCESS_SUSTAINED_THRESHOLD_DAYS: int = 90


@dataclass(frozen=True)
class AgendaPlacementResult:
    """Result of an agenda placement trigger evaluation.

    Attributes:
        triggered: Whether a trigger condition was met.
        trigger_type: The type of trigger that fired (if triggered).
        placement_id: The ID of the new or existing placement.
        was_idempotent: True if placement already existed (no new event created).
    """

    triggered: bool
    trigger_type: AgendaTriggerType | None
    placement_id: UUID | None
    was_idempotent: bool


class AutomaticAgendaPlacementService:
    """Service for automatic cessation agenda placement (FR37-FR38, RT-4).

    This service monitors for trigger conditions and automatically places
    cessation on the Conclave agenda when thresholds are reached.

    Constitutional Constraints:
    - CT-11: HALT CHECK FIRST - All operations check halt state first
    - CT-12: All events MUST be witnessed via EventWriterService
    - CT-13: Integrity outranks availability

    Triggers:
    - FR37: 3 consecutive integrity failures in 30 days
    - RT-4: 5 non-consecutive failures in 90-day rolling window
    - FR38: Anti-success alert sustained 90 days
    """

    def __init__(
        self,
        integrity_failure_repo: IntegrityFailureRepositoryProtocol,
        anti_success_repo: AntiSuccessAlertRepositoryProtocol,
        cessation_agenda_repo: CessationAgendaRepositoryProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            integrity_failure_repo: Repository for integrity failure tracking.
            anti_success_repo: Repository for anti-success alert tracking.
            cessation_agenda_repo: Repository for agenda placement storage.
            event_writer: Service for writing witnessed events.
            halt_checker: Service for checking halt state.
        """
        self._integrity_failure_repo = integrity_failure_repo
        self._anti_success_repo = anti_success_repo
        self._cessation_agenda_repo = cessation_agenda_repo
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def _check_halt_state(self) -> None:
        """Check halt state and raise if halted (CT-11).

        Constitutional Constraint (CT-11):
        Silent failure destroys legitimacy. We must fail loud
        if the system is halted.

        Raises:
            SystemHaltedError: If the system is in halted state.
        """
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical("operation_rejected_system_halted", halt_reason=reason)
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

    async def check_consecutive_failures(self) -> AgendaPlacementResult:
        """Check for FR37 trigger: 3 consecutive failures in 30 days.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - Always check halt state before proceeding.

        Returns:
            AgendaPlacementResult indicating whether trigger fired.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        await self._check_halt_state()

        log.info(
            "checking_consecutive_failures",
            threshold=CONSECUTIVE_FAILURE_THRESHOLD,
            window_days=CONSECUTIVE_FAILURE_WINDOW_DAYS,
        )

        # Check for idempotency first (AC4)
        existing = await self._cessation_agenda_repo.has_active_placement_for_trigger(
            AgendaTriggerType.CONSECUTIVE_FAILURES
        )
        if existing:
            placement = await self._cessation_agenda_repo.get_placement_by_trigger(
                AgendaTriggerType.CONSECUTIVE_FAILURES
            )
            log.info(
                "consecutive_failures_already_on_agenda",
                placement_id=str(placement.placement_id) if placement else None,
            )
            return AgendaPlacementResult(
                triggered=True,
                trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
                placement_id=placement.placement_id if placement else None,
                was_idempotent=True,
            )

        # Count consecutive failures
        count = await self._integrity_failure_repo.count_consecutive_in_window(
            window_days=CONSECUTIVE_FAILURE_WINDOW_DAYS,
        )

        if count >= CONSECUTIVE_FAILURE_THRESHOLD:
            failures = (
                await self._integrity_failure_repo.get_consecutive_failures_in_window(
                    window_days=CONSECUTIVE_FAILURE_WINDOW_DAYS,
                )
            )
            failure_event_ids = tuple(
                f.event_id for f in failures[:CONSECUTIVE_FAILURE_THRESHOLD]
            )

            placement = await self._create_agenda_placement(
                trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
                failure_count=count,
                window_days=CONSECUTIVE_FAILURE_WINDOW_DAYS,
                consecutive=True,
                failure_event_ids=failure_event_ids,
                reason=f"FR37: {CONSECUTIVE_FAILURE_THRESHOLD} consecutive integrity failures in {CONSECUTIVE_FAILURE_WINDOW_DAYS} days",
            )

            return AgendaPlacementResult(
                triggered=True,
                trigger_type=AgendaTriggerType.CONSECUTIVE_FAILURES,
                placement_id=placement.placement_id,
                was_idempotent=False,
            )

        log.info(
            "consecutive_failures_below_threshold",
            count=count,
            threshold=CONSECUTIVE_FAILURE_THRESHOLD,
        )

        return AgendaPlacementResult(
            triggered=False,
            trigger_type=None,
            placement_id=None,
            was_idempotent=False,
        )

    async def check_rolling_window_failures(self) -> AgendaPlacementResult:
        """Check for RT-4 trigger: 5 failures in 90-day rolling window.

        This trigger prevents "wait and reset" timing attacks by
        triggering on total failures, not just consecutive ones.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - Always check halt state before proceeding.

        Returns:
            AgendaPlacementResult indicating whether trigger fired.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        await self._check_halt_state()

        log.info(
            "checking_rolling_window_failures",
            threshold=ROLLING_WINDOW_THRESHOLD,
            window_days=ROLLING_WINDOW_DAYS,
        )

        # Check for idempotency first (AC4)
        existing = await self._cessation_agenda_repo.has_active_placement_for_trigger(
            AgendaTriggerType.ROLLING_WINDOW
        )
        if existing:
            placement = await self._cessation_agenda_repo.get_placement_by_trigger(
                AgendaTriggerType.ROLLING_WINDOW
            )
            log.info(
                "rolling_window_already_on_agenda",
                placement_id=str(placement.placement_id) if placement else None,
            )
            return AgendaPlacementResult(
                triggered=True,
                trigger_type=AgendaTriggerType.ROLLING_WINDOW,
                placement_id=placement.placement_id if placement else None,
                was_idempotent=True,
            )

        # Count all failures in window
        count = await self._integrity_failure_repo.count_in_rolling_window(
            window_days=ROLLING_WINDOW_DAYS,
        )

        if count >= ROLLING_WINDOW_THRESHOLD:
            failures = await self._integrity_failure_repo.get_failures_in_window(
                window_days=ROLLING_WINDOW_DAYS,
            )
            failure_event_ids = tuple(
                f.event_id for f in failures[:ROLLING_WINDOW_THRESHOLD]
            )

            placement = await self._create_agenda_placement(
                trigger_type=AgendaTriggerType.ROLLING_WINDOW,
                failure_count=count,
                window_days=ROLLING_WINDOW_DAYS,
                consecutive=False,
                failure_event_ids=failure_event_ids,
                reason=f"RT-4: {ROLLING_WINDOW_THRESHOLD} integrity failures in {ROLLING_WINDOW_DAYS}-day rolling window",
            )

            return AgendaPlacementResult(
                triggered=True,
                trigger_type=AgendaTriggerType.ROLLING_WINDOW,
                placement_id=placement.placement_id,
                was_idempotent=False,
            )

        log.info(
            "rolling_window_failures_below_threshold",
            count=count,
            threshold=ROLLING_WINDOW_THRESHOLD,
        )

        return AgendaPlacementResult(
            triggered=False,
            trigger_type=None,
            placement_id=None,
            was_idempotent=False,
        )

    async def check_anti_success_sustained(self) -> AgendaPlacementResult:
        """Check for FR38 trigger: Anti-success alert sustained 90 days.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - Always check halt state before proceeding.

        Returns:
            AgendaPlacementResult indicating whether trigger fired.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        await self._check_halt_state()

        log.info(
            "checking_anti_success_sustained",
            threshold_days=ANTI_SUCCESS_SUSTAINED_THRESHOLD_DAYS,
        )

        # Check for idempotency first (AC4)
        existing = await self._cessation_agenda_repo.has_active_placement_for_trigger(
            AgendaTriggerType.ANTI_SUCCESS_SUSTAINED
        )
        if existing:
            placement = await self._cessation_agenda_repo.get_placement_by_trigger(
                AgendaTriggerType.ANTI_SUCCESS_SUSTAINED
            )
            log.info(
                "anti_success_already_on_agenda",
                placement_id=str(placement.placement_id) if placement else None,
            )
            return AgendaPlacementResult(
                triggered=True,
                trigger_type=AgendaTriggerType.ANTI_SUCCESS_SUSTAINED,
                placement_id=placement.placement_id if placement else None,
                was_idempotent=True,
            )

        # Check if threshold is reached
        reached = await self._anti_success_repo.is_threshold_reached(
            threshold_days=ANTI_SUCCESS_SUSTAINED_THRESHOLD_DAYS,
        )

        if reached:
            alert_info = await self._anti_success_repo.get_sustained_alert_duration()
            if alert_info is None:
                log.error("anti_success_threshold_reached_but_no_info")
                return AgendaPlacementResult(
                    triggered=False,
                    trigger_type=None,
                    placement_id=None,
                    was_idempotent=False,
                )

            placement = await self._create_agenda_placement(
                trigger_type=AgendaTriggerType.ANTI_SUCCESS_SUSTAINED,
                failure_count=0,  # Not failure-based
                window_days=ANTI_SUCCESS_SUSTAINED_THRESHOLD_DAYS,
                consecutive=False,
                failure_event_ids=(),  # Not failure-based
                reason=f"FR38: Anti-success alert sustained {ANTI_SUCCESS_SUSTAINED_THRESHOLD_DAYS} days",
                sustained_days=alert_info.sustained_days,
                first_alert_date=alert_info.first_alert_date,
                alert_event_ids=alert_info.alert_event_ids,
            )

            return AgendaPlacementResult(
                triggered=True,
                trigger_type=AgendaTriggerType.ANTI_SUCCESS_SUSTAINED,
                placement_id=placement.placement_id,
                was_idempotent=False,
            )

        log.info("anti_success_below_threshold")

        return AgendaPlacementResult(
            triggered=False,
            trigger_type=None,
            placement_id=None,
            was_idempotent=False,
        )

    async def evaluate_all_triggers(self) -> list[AgendaPlacementResult]:
        """Evaluate all automatic agenda placement triggers.

        This method checks all triggers in order of priority:
        1. Consecutive failures (FR37)
        2. Rolling window failures (RT-4)
        3. Anti-success sustained (FR38)

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - All individual checks verify halt state.

        Returns:
            List of results for each trigger evaluated.

        Raises:
            SystemHaltedError: If system is in halted state.
        """
        await self._check_halt_state()

        log.info("evaluating_all_agenda_triggers")

        results: list[AgendaPlacementResult] = []

        # Check all triggers
        results.append(await self.check_consecutive_failures())
        results.append(await self.check_rolling_window_failures())
        results.append(await self.check_anti_success_sustained())

        triggered_count = sum(
            1 for r in results if r.triggered and not r.was_idempotent
        )
        log.info(
            "agenda_trigger_evaluation_complete",
            triggers_fired=triggered_count,
            idempotent_count=sum(1 for r in results if r.was_idempotent),
        )

        return results

    async def _create_agenda_placement(
        self,
        trigger_type: AgendaTriggerType,
        failure_count: int,
        window_days: int,
        consecutive: bool,
        failure_event_ids: tuple[UUID, ...],
        reason: str,
        sustained_days: int | None = None,
        first_alert_date: datetime | None = None,
        alert_event_ids: tuple[UUID, ...] = (),
    ) -> CessationAgendaPlacementEventPayload:
        """Create and persist an agenda placement event.

        Constitutional Constraint (CT-12):
        All events MUST be witnessed via EventWriterService.

        Args:
            trigger_type: The type of trigger that fired.
            failure_count: Number of failures (for failure-based triggers).
            window_days: The window size in days.
            consecutive: Whether failures were consecutive.
            failure_event_ids: References to triggering failure events.
            reason: Human-readable reason for placement.
            sustained_days: Days sustained (for anti-success trigger).
            first_alert_date: When alert period began (for anti-success trigger).
            alert_event_ids: Alert event references (for anti-success trigger).

        Returns:
            The created agenda placement payload.
        """
        trigger_timestamp = datetime.now(timezone.utc)
        placement_id = uuid4()

        payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=trigger_type,
            trigger_timestamp=trigger_timestamp,
            failure_count=failure_count,
            window_days=window_days,
            consecutive=consecutive,
            failure_event_ids=failure_event_ids,
            agenda_placement_reason=reason,
            sustained_days=sustained_days,
            first_alert_date=first_alert_date,
            alert_event_ids=alert_event_ids,
        )

        # Write witnessed event (CT-12)
        await self._event_writer.write_event(
            event_type=CESSATION_AGENDA_PLACEMENT_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=AGENDA_PLACEMENT_SYSTEM_AGENT_ID,
            local_timestamp=trigger_timestamp,
        )

        # Persist to repository
        await self._cessation_agenda_repo.save_agenda_placement(payload)

        log.info(
            "cessation_placed_on_agenda",
            placement_id=str(placement_id),
            trigger_type=trigger_type.value,
            failure_count=failure_count,
            reason=reason,
        )

        return payload
