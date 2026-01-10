"""Complexity Budget Service (Story 8.6, CT-14, RT-6, SC-3).

This service manages complexity budget tracking, breach detection, and
governance ceremony requirements.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event, not just alert.
        Exceeding limits requires governance ceremony to proceed.
- SC-3: Self-consistency finding - complexity budget dashboard required.
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST.
- CT-12: Witnessing creates accountability -> All breach events MUST be witnessed.

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every write operation
2. WITNESS EVERYTHING - All breach events must be witnessed
3. FAIL LOUD - Never silently swallow breach detection
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from structlog import get_logger

from src.application.ports.complexity_budget_repository import (
    ComplexityBudgetRepositoryPort,
)
from src.application.ports.complexity_calculator import ComplexityCalculatorPort
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.complexity_budget import (
    ComplexityBudgetApprovalRequiredError,
    ComplexityBudgetBreachedError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.complexity_budget import (
    COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE,
    ComplexityBudgetBreachedPayload,
)
from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
    WARNING_THRESHOLD_PERCENT,
    ComplexityBudget,
    ComplexityBudgetStatus,
    ComplexityDimension,
    ComplexitySnapshot,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()

# System agent ID for complexity budget events
COMPLEXITY_BUDGET_SYSTEM_AGENT_ID: str = "complexity_budget_system"


class ComplexityBudgetService:
    """Manages complexity budget tracking and breach detection (CT-14, RT-6, SC-3).

    This service provides:
    1. Complexity snapshot calculation (AC1)
    2. Budget status checking with breach detection (AC1, AC2)
    3. Breach event creation with witnessing (AC2, CT-12)
    4. Governance ceremony requirement enforcement (AC3, RT-6)

    Constitutional Constraints:
    - CT-14: Complexity is a failure vector. Complexity must be budgeted.
    - RT-6: Breach = constitutional event. Governance ceremony required to proceed.
    - CT-11: HALT CHECK FIRST at every write operation.
    - CT-12: All breach events MUST be witnessed.

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every write operation checks halt state
    2. WITNESS EVERYTHING - All events are witnessed via EventWriterService
    3. FAIL LOUD - Raise specific errors for failures
    """

    def __init__(
        self,
        calculator: ComplexityCalculatorPort,
        repository: ComplexityBudgetRepositoryPort,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Complexity Budget Service.

        Args:
            calculator: Port for calculating complexity metrics.
            repository: Repository for complexity data storage and queries.
            event_writer: Service for writing witnessed events (CT-12).
            halt_checker: Interface to check system halt state (CT-11).
        """
        self._calculator = calculator
        self._repository = repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def check_all_budgets(
        self,
        triggered_by: Optional[str] = None,
    ) -> ComplexitySnapshot:
        """Check all complexity budgets and record snapshot (AC1).

        Creates a snapshot of current complexity metrics across all dimensions.
        This is a read operation, so halt check is not required.

        Args:
            triggered_by: Optional identifier of what triggered this check.

        Returns:
            ComplexitySnapshot with current values for all dimensions.
        """
        log = logger.bind(
            operation="check_all_budgets",
            triggered_by=triggered_by,
        )

        snapshot = await self._calculator.calculate_snapshot(triggered_by)

        adr_budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
        ceremony_budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
        deps_budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)

        log.info(
            "complexity_budgets_checked",
            adr_count=snapshot.adr_count,
            ceremony_types=snapshot.ceremony_types,
            cross_component_deps=snapshot.cross_component_deps,
            adr_status=adr_budget.status.value,
            ceremony_status=ceremony_budget.status.value,
            deps_status=deps_budget.status.value,
        )

        return snapshot

    async def record_snapshot(
        self,
        snapshot: ComplexitySnapshot,
    ) -> None:
        """Record a complexity snapshot (AC1, AC5).

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before write.

        Args:
            snapshot: The snapshot to record.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(
            operation="record_snapshot",
            snapshot_id=str(snapshot.snapshot_id),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "snapshot_record_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        await self._repository.save_snapshot(snapshot)

        log.info("complexity_snapshot_recorded")

    async def get_budget_status(
        self,
    ) -> dict[ComplexityDimension, ComplexityBudgetStatus]:
        """Get the status of all complexity budgets (AC1).

        Returns:
            Dictionary mapping each dimension to its current status.
        """
        snapshot = await self._calculator.calculate_snapshot()

        return {
            ComplexityDimension.ADR_COUNT: snapshot.get_budget(ComplexityDimension.ADR_COUNT).status,
            ComplexityDimension.CEREMONY_TYPES: snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES).status,
            ComplexityDimension.CROSS_COMPONENT_DEPS: snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS).status,
        }

    async def is_budget_breached(
        self,
        dimension: ComplexityDimension,
    ) -> bool:
        """Check if a specific dimension budget is breached (AC2).

        Args:
            dimension: The dimension to check.

        Returns:
            True if the dimension is breached (at or over limit).
        """
        snapshot = await self._calculator.calculate_snapshot()
        return snapshot.get_budget(dimension).is_breached

    async def is_any_budget_breached(self) -> bool:
        """Check if any complexity budget is breached (AC2).

        Returns:
            True if any dimension is breached.
        """
        snapshot = await self._calculator.calculate_snapshot()
        return snapshot.has_breaches

    async def get_breached_dimensions(self) -> list[ComplexityDimension]:
        """Get all dimensions that are currently breached (AC2).

        Returns:
            List of dimensions that are at or over their limits.
        """
        snapshot = await self._calculator.calculate_snapshot()
        return list(snapshot.breached_dimensions)

    async def record_breach(
        self,
        dimension: ComplexityDimension,
        limit: int,
        actual_value: int,
    ) -> ComplexityBudgetBreachedPayload:
        """Record a complexity breach event (AC2, RT-6, CT-12).

        Creates and persists a breach event when a complexity limit is exceeded.
        The event is witnessed per CT-12.

        Constitutional Constraints:
        - RT-6: Breach = constitutional event, requires governance ceremony
        - CT-11: HALT CHECK FIRST
        - CT-12: Event is witnessed via EventWriterService

        Args:
            dimension: Which dimension was breached.
            limit: The configured limit.
            actual_value: The actual value that triggered breach.

        Returns:
            The created breach event payload.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(
            operation="record_breach",
            dimension=dimension.value,
            limit=limit,
            actual_value=actual_value,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "breach_record_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Create breach payload (RT-6)
        # =====================================================================
        breach_id = uuid4()
        breached_at = datetime.now(timezone.utc)

        payload = ComplexityBudgetBreachedPayload(
            breach_id=breach_id,
            dimension=dimension,
            limit=limit,
            actual_value=actual_value,
            breached_at=breached_at,
            requires_governance_ceremony=True,  # RT-6
        )

        log = log.bind(breach_id=str(breach_id))

        # =====================================================================
        # Write witnessed event (CT-12)
        # =====================================================================
        event_payload: dict[str, Any] = {
            "breach_id": str(payload.breach_id),
            "dimension": payload.dimension.value,
            "limit": payload.limit,
            "actual_value": payload.actual_value,
            "breached_at": payload.breached_at.isoformat(),
            "requires_governance_ceremony": payload.requires_governance_ceremony,
        }

        await self._event_writer.write_event(
            event_type=COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE,
            payload=event_payload,
            agent_id=COMPLEXITY_BUDGET_SYSTEM_AGENT_ID,
            local_timestamp=breached_at,
        )

        # =====================================================================
        # Save to repository for queries
        # =====================================================================
        await self._repository.save_breach(payload)

        log.warning(
            "complexity_budget_breached",
            message="Complexity budget breach recorded (RT-6, CT-14)",
            overage=actual_value - limit,
        )

        return payload

    async def detect_and_record_breaches(
        self,
        triggered_by: Optional[str] = None,
    ) -> list[ComplexityBudgetBreachedPayload]:
        """Detect and record any current breaches (AC2).

        Calculates current complexity snapshot and records breach events
        for any dimensions that exceed their limits.

        Constitutional Constraints:
        - CT-14: Complexity must be budgeted
        - RT-6: Breaches are constitutional events
        - CT-11: HALT CHECK FIRST
        - CT-12: All breaches witnessed

        Args:
            triggered_by: Optional identifier of what triggered detection.

        Returns:
            List of breach payloads for any detected breaches.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(
            operation="detect_and_record_breaches",
            triggered_by=triggered_by,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "breach_detection_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        snapshot = await self._calculator.calculate_snapshot(triggered_by)
        breaches: list[ComplexityBudgetBreachedPayload] = []

        # Check each dimension for breach
        adr_budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
        ceremony_budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
        deps_budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)

        if adr_budget.is_breached:
            breach = await self.record_breach(
                dimension=ComplexityDimension.ADR_COUNT,
                limit=ADR_LIMIT,
                actual_value=snapshot.adr_count,
            )
            breaches.append(breach)

        if ceremony_budget.is_breached:
            breach = await self.record_breach(
                dimension=ComplexityDimension.CEREMONY_TYPES,
                limit=CEREMONY_TYPE_LIMIT,
                actual_value=snapshot.ceremony_types,
            )
            breaches.append(breach)

        if deps_budget.is_breached:
            breach = await self.record_breach(
                dimension=ComplexityDimension.CROSS_COMPONENT_DEPS,
                limit=CROSS_COMPONENT_DEP_LIMIT,
                actual_value=snapshot.cross_component_deps,
            )
            breaches.append(breach)

        if breaches:
            log.warning(
                "breaches_detected",
                breach_count=len(breaches),
                dimensions=[b.dimension.value for b in breaches],
            )
        else:
            log.info("no_breaches_detected")

        return breaches

    async def require_governance_approval(
        self,
        dimension: ComplexityDimension,
    ) -> None:
        """Enforce governance ceremony requirement for breach (AC3, RT-6).

        This method should be called when an operation would proceed
        with a breached budget. It checks if the breach has been
        approved via governance ceremony.

        Args:
            dimension: The dimension that is breached.

        Raises:
            ComplexityBudgetApprovalRequiredError: If no approval exists.
        """
        log = logger.bind(
            operation="require_governance_approval",
            dimension=dimension.value,
        )

        # Check for unresolved breaches in this dimension
        unresolved = await self._repository.get_unresolved_breaches()

        for breach in unresolved:
            if breach.dimension == dimension:
                log.warning(
                    "governance_approval_required",
                    breach_id=str(breach.breach_id),
                    message="RT-6: Governance ceremony required to proceed",
                )
                raise ComplexityBudgetApprovalRequiredError(
                    dimension=dimension,
                    breach_id=breach.breach_id,
                )

        log.info(
            "governance_approval_not_required",
            message="No unresolved breaches for this dimension",
        )

    async def get_latest_snapshot(self) -> Optional[ComplexitySnapshot]:
        """Get the most recent recorded snapshot (AC5).

        Returns:
            The most recent snapshot if any exist, None otherwise.
        """
        return await self._repository.get_latest_snapshot()

    async def get_snapshots_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[ComplexitySnapshot]:
        """Get snapshots within a date range (AC5).

        Args:
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).

        Returns:
            List of snapshots within the range.
        """
        return await self._repository.get_snapshots_in_range(start, end)

    async def get_all_breaches(self) -> list[ComplexityBudgetBreachedPayload]:
        """Get all recorded breach events (AC5).

        Returns:
            List of all breach events.
        """
        return await self._repository.get_all_breaches()

    async def get_unresolved_breaches(self) -> list[ComplexityBudgetBreachedPayload]:
        """Get all unresolved breach events (AC5, RT-6).

        Returns:
            List of breaches not yet approved via governance ceremony.
        """
        return await self._repository.get_unresolved_breaches()

    async def get_dashboard_data(self) -> dict[str, Any]:
        """Get complexity dashboard data (AC1).

        Returns:
            Dictionary with all dashboard data including:
            - Current values and limits for each dimension
            - Utilization percentages
            - Status for each dimension
            - Overall status
            - Active breaches count
        """
        snapshot = await self._calculator.calculate_snapshot()
        unresolved = await self._repository.get_unresolved_breaches()

        adr_budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
        ceremony_budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
        deps_budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)

        return {
            "adr_count": snapshot.adr_count,
            "adr_limit": ADR_LIMIT,
            "adr_utilization": adr_budget.utilization_percent,
            "adr_status": adr_budget.status.value,
            "ceremony_types": snapshot.ceremony_types,
            "ceremony_type_limit": CEREMONY_TYPE_LIMIT,
            "ceremony_type_utilization": ceremony_budget.utilization_percent,
            "ceremony_type_status": ceremony_budget.status.value,
            "cross_component_deps": snapshot.cross_component_deps,
            "cross_component_dep_limit": CROSS_COMPONENT_DEP_LIMIT,
            "cross_component_dep_utilization": deps_budget.utilization_percent,
            "cross_component_dep_status": deps_budget.status.value,
            "overall_status": snapshot.overall_status.value,
            "active_breaches": len(unresolved),
            "last_updated": snapshot.timestamp.isoformat(),
        }
