"""Complexity Budget Escalation Service (Story 8.6, RT-6, AC4).

This service manages automatic escalation of complexity budget breaches
when they remain unresolved beyond the escalation period.

Constitutional Constraints:
- RT-6: Red Team hardening - breaches without approval trigger escalation.
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST.
- CT-12: Witnessing creates accountability -> All escalation events MUST be witnessed.

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every write operation
2. WITNESS EVERYTHING - All escalation events must be witnessed
3. FAIL LOUD - Never silently ignore unresolved breaches
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.complexity_budget_repository import (
    ComplexityBudgetRepositoryPort,
)
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.complexity_budget import (
    COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE,
    ComplexityBudgetBreachedPayload,
    ComplexityBudgetEscalatedPayload,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()

# System agent ID for complexity escalation events
COMPLEXITY_ESCALATION_SYSTEM_AGENT_ID: str = "complexity_escalation_system"

# Escalation period in days (AC4)
ESCALATION_PERIOD_DAYS: int = 7

# Second-level escalation period
SECOND_ESCALATION_PERIOD_DAYS: int = 14


class ComplexityBudgetEscalationService:
    """Manages automatic escalation of complexity budget breaches (RT-6, AC4).

    This service provides:
    1. Check for pending breaches that need escalation (AC4)
    2. Escalate breaches that remain unresolved (AC4, RT-6)
    3. Resolution tracking (AC4)

    Constitutional Constraints:
    - RT-6: Breaches without approval within escalation period trigger escalation.
    - CT-11: HALT CHECK FIRST at every write operation.
    - CT-12: All escalation events MUST be witnessed.

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every write operation checks halt state
    2. WITNESS EVERYTHING - All events are witnessed via EventWriterService
    3. FAIL LOUD - Raise specific errors for failures
    """

    def __init__(
        self,
        repository: ComplexityBudgetRepositoryPort,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
        escalation_period_days: int = ESCALATION_PERIOD_DAYS,
    ) -> None:
        """Initialize the Complexity Budget Escalation Service.

        Args:
            repository: Repository for complexity data storage and queries.
            event_writer: Service for writing witnessed events (CT-12).
            halt_checker: Interface to check system halt state (CT-11).
            escalation_period_days: Days before escalation (default: 7).
        """
        self._repository = repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker
        self._escalation_period_days = escalation_period_days

    async def check_pending_breaches(
        self,
    ) -> list[ComplexityBudgetBreachedPayload]:
        """Check for breaches pending escalation (AC4).

        Returns breaches that have been unresolved for longer than
        the escalation period.

        Returns:
            List of breaches pending escalation.
        """
        log = logger.bind(
            operation="check_pending_breaches",
            escalation_period_days=self._escalation_period_days,
        )

        unresolved = await self._repository.get_unresolved_breaches()

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self._escalation_period_days
        )

        pending = [breach for breach in unresolved if breach.breached_at < cutoff]

        log.info(
            "pending_breaches_checked",
            total_unresolved=len(unresolved),
            pending_escalation=len(pending),
        )

        return pending

    async def get_days_since_breach(
        self,
        breach: ComplexityBudgetBreachedPayload,
    ) -> int:
        """Calculate days since a breach was recorded.

        Args:
            breach: The breach to check.

        Returns:
            Number of days since the breach.
        """
        now = datetime.now(timezone.utc)
        delta = now - breach.breached_at
        return delta.days

    async def escalate_breach(
        self,
        breach_id: UUID,
    ) -> ComplexityBudgetEscalatedPayload:
        """Escalate an unresolved breach (AC4, RT-6, CT-12).

        Creates an escalation event when a breach remains unresolved
        beyond the escalation period.

        Constitutional Constraints:
        - RT-6: Automatic escalation for unresolved breaches
        - CT-11: HALT CHECK FIRST
        - CT-12: Event is witnessed via EventWriterService

        Args:
            breach_id: The ID of the breach to escalate.

        Returns:
            The created escalation event payload.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            ValueError: If breach not found.
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
        # Get breach details
        # =====================================================================
        breach = await self._repository.get_breach_by_id(breach_id)
        if breach is None:
            log.error("breach_not_found")
            raise ValueError(f"Breach not found: {breach_id}")

        days_since = await self.get_days_since_breach(breach)

        # Determine escalation level based on time elapsed
        escalation_level = 2 if days_since >= SECOND_ESCALATION_PERIOD_DAYS else 1

        # =====================================================================
        # Create escalation payload (RT-6)
        # =====================================================================
        escalation_id = uuid4()
        escalated_at = datetime.now(timezone.utc)

        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=escalation_id,
            breach_id=breach_id,
            dimension=breach.dimension,
            original_breach_at=breach.breached_at,
            escalated_at=escalated_at,
            days_without_resolution=days_since,
            escalation_level=escalation_level,
        )

        log = log.bind(
            escalation_id=str(escalation_id),
            escalation_level=escalation_level,
            days_without_resolution=days_since,
        )

        # =====================================================================
        # Write witnessed event (CT-12)
        # =====================================================================
        event_payload: dict[str, Any] = {
            "escalation_id": str(payload.escalation_id),
            "breach_id": str(payload.breach_id),
            "dimension": payload.dimension.value,
            "escalation_level": payload.escalation_level,
            "days_without_resolution": payload.days_without_resolution,
            "escalated_at": payload.escalated_at.isoformat(),
        }

        await self._event_writer.write_event(
            event_type=COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE,
            payload=event_payload,
            agent_id=COMPLEXITY_ESCALATION_SYSTEM_AGENT_ID,
            local_timestamp=escalated_at,
        )

        # =====================================================================
        # Save to repository for queries
        # =====================================================================
        await self._repository.save_escalation(payload)

        severity = "CRITICAL" if escalation_level >= 2 else "ELEVATED"
        log.warning(
            "breach_escalated",
            message=f"[{severity}] Complexity breach escalated (RT-6)",
            dimension=breach.dimension.value,
        )

        return payload

    async def escalate_all_pending(
        self,
    ) -> list[ComplexityBudgetEscalatedPayload]:
        """Escalate all pending breaches (AC4).

        Checks for pending breaches and escalates each one.

        Constitutional Constraints:
        - RT-6: Automatic escalation for unresolved breaches
        - CT-11: HALT CHECK FIRST
        - CT-12: All events witnessed

        Returns:
            List of escalation payloads for escalated breaches.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="escalate_all_pending")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "escalation_all_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        pending = await self.check_pending_breaches()
        escalations: list[ComplexityBudgetEscalatedPayload] = []

        for breach in pending:
            try:
                escalation = await self.escalate_breach(breach.breach_id)
                escalations.append(escalation)
            except SystemHaltedError:
                # Re-raise halt errors immediately
                raise
            except Exception as e:
                log.error(
                    "escalation_failed",
                    breach_id=str(breach.breach_id),
                    error=str(e),
                )
                # Continue with other breaches

        log.info(
            "pending_breaches_escalated",
            escalated_count=len(escalations),
        )

        return escalations

    async def is_breach_resolved(
        self,
        breach_id: UUID,
    ) -> bool:
        """Check if a breach has been resolved via governance ceremony (AC4).

        Args:
            breach_id: The breach ID to check.

        Returns:
            True if breach is resolved, False otherwise.
        """
        return await self._repository.is_breach_resolved(breach_id)

    async def resolve_breach(
        self,
        breach_id: UUID,
    ) -> bool:
        """Mark a breach as resolved via governance ceremony (AC4, RT-6).

        This should be called when a governance ceremony approves
        proceeding with the breached budget.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before write.

        Args:
            breach_id: The breach ID to mark as resolved.

        Returns:
            True if breach was found and marked, False otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(
            operation="resolve_breach",
            breach_id=str(breach_id),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "resolution_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        result = await self._repository.mark_breach_resolved(breach_id)

        if result:
            log.info(
                "breach_resolved",
                message="Complexity breach resolved via governance ceremony",
            )
        else:
            log.warning(
                "breach_not_found",
                message="Breach not found for resolution",
            )

        return result

    async def get_escalations_for_breach(
        self,
        breach_id: UUID,
    ) -> list[ComplexityBudgetEscalatedPayload]:
        """Get all escalations for a specific breach.

        Args:
            breach_id: The breach ID to find escalations for.

        Returns:
            List of escalation events for the breach.
        """
        return await self._repository.get_escalations_for_breach(breach_id)

    async def get_all_escalations(
        self,
    ) -> list[ComplexityBudgetEscalatedPayload]:
        """Get all escalation events.

        Returns:
            List of all escalation events.
        """
        return await self._repository.get_all_escalations()

    async def get_pending_escalations_count(self) -> int:
        """Get count of breaches pending escalation.

        Returns:
            Number of breaches that should be escalated.
        """
        pending = await self.check_pending_breaches()
        return len(pending)
