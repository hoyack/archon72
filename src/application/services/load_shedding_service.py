"""Load Shedding Service (Story 8.8, FR107).

This service manages load shedding decisions, ensuring that constitutional
events are NEVER shed while allowing operational telemetry to be deprioritized.

Constitutional Constraints:
- FR107: System SHALL NOT shed constitutional events under load;
         operational telemetry may be deprioritized but canonical events never dropped.

Developer Golden Rules:
1. CONSTITUTIONAL EVENTS NEVER SHED - This is non-negotiable
2. LOG ALL DECISIONS - All shedding decisions must be logged
3. FAIL LOUD - Never silently drop constitutional events
"""

from __future__ import annotations

from typing import Any

from src.application.services.base import LoggingMixin
from src.domain.errors.failure_prevention import (
    ConstitutionalEventSheddingError,
    LoadSheddingDecisionError,
)
from src.domain.models.load_status import (
    LoadSheddingDecision,
    LoadStatus,
)

# Default capacity threshold for shedding activation
DEFAULT_CAPACITY_THRESHOLD: float = 80.0


class LoadSheddingService(LoggingMixin):
    """Manages load shedding decisions (FR107).

    This service provides:
    1. Load evaluation and status tracking (AC5)
    2. Shedding decision making (AC5)
    3. Constitutional event protection (AC5 - CRITICAL)
    4. Shedding decision logging (AC5)

    Constitutional Constraint (FR107):
    Constitutional events are NEVER shed. This is enforced at every
    decision point with explicit checks and errors.

    Developer Golden Rules:
    1. CONSTITUTIONAL EVENTS NEVER SHED - Hardcoded check in every method
    2. LOG ALL DECISIONS - Every shedding decision is logged
    3. FAIL LOUD - Raise ConstitutionalEventSheddingError if attempted
    """

    def __init__(
        self,
        capacity_threshold: float = DEFAULT_CAPACITY_THRESHOLD,
    ) -> None:
        """Initialize the Load Shedding Service.

        Args:
            capacity_threshold: Threshold percentage for shedding activation.
        """
        self._init_logger(component="operational")
        self._capacity_threshold = capacity_threshold
        self._current_load: float = 0.0
        self._baseline_load: float | None = None
        self._decisions: list[LoadSheddingDecision] = []
        self._telemetry_shed_count: int = 0

    async def set_baseline_load(self, baseline: float) -> None:
        """Set the baseline load for extreme load detection (NFR43).

        Args:
            baseline: The baseline load percentage.
        """
        log = self._log_operation("set_baseline_load", baseline=baseline)

        if baseline < 0:
            raise LoadSheddingDecisionError(
                reason=f"Baseline load cannot be negative, got {baseline}",
            )

        self._baseline_load = baseline
        log.info("baseline_load_set")

    async def update_load(self, current_load: float) -> LoadStatus:
        """Update current load and get status.

        Args:
            current_load: Current load as percentage.

        Returns:
            LoadStatus with current state.
        """
        log = self._log_operation("update_load", current_load=current_load)

        if current_load < 0:
            raise LoadSheddingDecisionError(
                reason=f"Current load cannot be negative, got {current_load}",
                current_load=current_load,
            )

        self._current_load = current_load

        status = LoadStatus.create(
            current_load=current_load,
            capacity_threshold=self._capacity_threshold,
            baseline_load=self._baseline_load,
        )

        log.info(
            "load_updated",
            load_level=status.load_level.value,
            shedding_active=status.shedding_active,
        )

        return status

    async def evaluate_load(self) -> LoadStatus:
        """Evaluate current load status.

        Returns:
            LoadStatus with current state.
        """
        return LoadStatus.create(
            current_load=self._current_load,
            capacity_threshold=self._capacity_threshold,
            baseline_load=self._baseline_load,
        )

    async def should_shed_telemetry(self) -> bool:
        """Determine if operational telemetry should be shed.

        Constitutional Constraint (FR107):
        This method ONLY applies to operational telemetry.
        Constitutional events bypass this check entirely.

        Returns:
            True if telemetry shedding is advised.
        """
        status = await self.evaluate_load()
        return status.should_shed_telemetry

    async def make_shedding_decision(
        self,
        item_type: str,
        is_constitutional: bool,
    ) -> LoadSheddingDecision:
        """Make a load shedding decision for an item.

        Constitutional Constraint (FR107):
        Constitutional events are NEVER shed. If is_constitutional=True,
        the decision will always be was_shed=False.

        Args:
            item_type: Type of item being considered for shedding.
            is_constitutional: Whether the item is a constitutional event.

        Returns:
            LoadSheddingDecision with the outcome.

        Raises:
            ConstitutionalEventSheddingError: If attempting to force-shed
                a constitutional event (should never happen in normal flow).
        """
        log = self._log_operation(
            "make_shedding_decision",
            item_type=item_type,
            is_constitutional=is_constitutional,
        )

        status = await self.evaluate_load()

        # =====================================================================
        # CONSTITUTIONAL EVENTS NEVER SHED (FR107 - CRITICAL)
        # =====================================================================
        if is_constitutional:
            decision = LoadSheddingDecision.create(
                load_status=status,
                item_type=item_type,
                is_constitutional=True,
                reason="FR107: Constitutional events NEVER shed",
            )

            log.info(
                "constitutional_event_protected",
                item_type=item_type,
            )
        else:
            # Operational telemetry can be shed
            decision = LoadSheddingDecision.create(
                load_status=status,
                item_type=item_type,
                is_constitutional=False,
            )

            if decision.was_shed:
                self._telemetry_shed_count += 1
                log.info(
                    "telemetry_shed",
                    item_type=item_type,
                    load_level=status.load_level.value,
                )
            else:
                log.debug(
                    "telemetry_retained",
                    item_type=item_type,
                )

        # Record decision
        self._decisions.append(decision)

        # Keep only last 10000 decisions
        if len(self._decisions) > 10000:
            self._decisions = self._decisions[-10000:]

        return decision

    async def log_shedding_decision(
        self,
        reason: str,
        item_type: str = "unknown",
        is_constitutional: bool = False,
    ) -> None:
        """Log a shedding decision for audit trail.

        Args:
            reason: Reason for the shedding decision.
            item_type: Type of item.
            is_constitutional: Whether item is constitutional.
        """
        log = self._log_operation(
            "log_shedding_decision",
            item_type=item_type,
            is_constitutional=is_constitutional,
        )

        log.info(
            "shedding_decision_logged",
            reason=reason,
        )

    async def raise_if_shedding_constitutional(
        self,
        item_type: str,
    ) -> None:
        """Raise error if attempting to shed a constitutional event.

        This method should be called as a safety check before any
        operation that might skip or drop a constitutional event.

        Args:
            item_type: Type of constitutional event.

        Raises:
            ConstitutionalEventSheddingError: Always raises if called
                because constitutional events should NEVER be shed.
        """
        raise ConstitutionalEventSheddingError(
            event_type=item_type,
            reason="Attempted to shed constitutional event",
        )

    async def get_load_status(self) -> dict[str, Any]:
        """Get current load status summary.

        Returns:
            Dictionary with load status information.
        """
        status = await self.evaluate_load()

        return {
            "current_load": self._current_load,
            "capacity_threshold": self._capacity_threshold,
            "baseline_load": self._baseline_load,
            "load_level": status.load_level.value,
            "shedding_active": status.shedding_active,
            "should_shed_telemetry": status.should_shed_telemetry,
            "is_extreme_load": status.is_extreme_load,
            "headroom_percent": status.headroom_percent,
            "utilization_percent": status.utilization_percent,
        }

    async def get_shedding_stats(self) -> dict[str, Any]:
        """Get shedding statistics.

        Returns:
            Dictionary with shedding statistics.
        """
        log = self._log_operation("get_shedding_stats")

        total_decisions = len(self._decisions)
        constitutional_protected = sum(
            1 for d in self._decisions if d.is_constitutional
        )
        telemetry_shed = sum(
            1 for d in self._decisions if d.was_shed and not d.is_constitutional
        )
        telemetry_retained = sum(
            1 for d in self._decisions if not d.was_shed and not d.is_constitutional
        )

        stats = {
            "total_decisions": total_decisions,
            "constitutional_protected": constitutional_protected,
            "telemetry_shed": telemetry_shed,
            "telemetry_retained": telemetry_retained,
            "total_telemetry_shed_count": self._telemetry_shed_count,
            "current_load": self._current_load,
            "capacity_threshold": self._capacity_threshold,
        }

        log.info(
            "shedding_stats_retrieved",
            total_decisions=total_decisions,
            constitutional_protected=constitutional_protected,
            telemetry_shed=telemetry_shed,
        )

        return stats

    async def get_recent_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent shedding decisions.

        Args:
            limit: Maximum number of decisions to return.

        Returns:
            List of recent decision records.
        """
        recent = self._decisions[-limit:]

        return [
            {
                "decision_id": str(d.decision_id),
                "item_type": d.item_type,
                "is_constitutional": d.is_constitutional,
                "was_shed": d.was_shed,
                "reason": d.reason,
                "load_level": d.load_status.load_level.value,
                "current_load": d.load_status.current_load,
                "timestamp": d.timestamp.isoformat(),
            }
            for d in recent
        ]
