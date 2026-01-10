"""Constitutional health service (Story 8.10, ADR-10).

Provides unified access to constitutional health metrics, distinct from
operational health. Aggregates data from multiple sources:
- Breach count from BreachRepository
- Override rate from OverrideTrendRepository
- Dissent health from DissentMetricsPort
- Witness coverage from WitnessPoolMonitor

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- System health = worst component health (conservative)

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Constitutional actions require attribution
3. FAIL LOUD - Never catch SystemHaltedError
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.application.ports.breach_repository import BreachRepositoryProtocol
from src.application.ports.constitutional_health import ConstitutionalHealthPort
from src.application.ports.dissent_metrics import DissentMetricsPort
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.override_trend_repository import (
    OverrideTrendRepositoryProtocol,
)
from src.application.ports.witness_pool_monitor import WitnessPoolMonitorProtocol
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.constitutional_health import (
    ConstitutionalHealthMetric,
    ConstitutionalHealthSnapshot,
    ConstitutionalHealthStatus,
)
from src.domain.models.breach_count_status import (
    CESSATION_WINDOW_DAYS,
)


class ConstitutionalHealthService(ConstitutionalHealthPort):
    """Service for constitutional health metrics (ADR-10).

    Aggregates constitutional health data from multiple sources and
    provides a unified view distinct from operational health.

    Constitutional Pattern:
    1. HALT CHECK FIRST at every public operation (CT-11)
    2. Aggregate metrics from existing ports
    3. Calculate overall status: worst component health (conservative)
    4. Block ceremonies when UNHEALTHY

    Attributes:
        _halt_checker: For HALT CHECK FIRST pattern.
        _breach_repository: For breach count metrics.
        _override_trend_repository: For override rate metrics.
        _dissent_metrics: For dissent health metrics.
        _witness_pool_monitor: For witness coverage metrics.

    Example:
        service = ConstitutionalHealthService(
            halt_checker=halt_checker,
            breach_repository=breach_repo,
            override_trend_repository=override_repo,
            dissent_metrics=dissent_port,
            witness_pool_monitor=witness_monitor,
        )

        # Get full health snapshot
        health = await service.get_constitutional_health()
        if health.ceremonies_blocked:
            # Cannot proceed with ceremonies
            reasons = health.blocking_reasons
            ...
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        breach_repository: BreachRepositoryProtocol,
        override_trend_repository: OverrideTrendRepositoryProtocol,
        dissent_metrics: DissentMetricsPort,
        witness_pool_monitor: WitnessPoolMonitorProtocol,
    ) -> None:
        """Initialize the constitutional health service.

        Args:
            halt_checker: For CT-11 halt check before operations.
            breach_repository: For breach count metrics.
            override_trend_repository: For override rate metrics.
            dissent_metrics: For dissent health metrics.
            witness_pool_monitor: For witness coverage metrics.
        """
        self._halt_checker = halt_checker
        self._breach_repository = breach_repository
        self._override_trend_repository = override_trend_repository
        self._dissent_metrics = dissent_metrics
        self._witness_pool_monitor = witness_pool_monitor

    async def _check_halt(self) -> None:
        """Check halt state and raise if halted (CT-11).

        Raises:
            SystemHaltedError: If system is halted.
        """
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

    async def get_constitutional_health(self) -> ConstitutionalHealthSnapshot:
        """Get full constitutional health snapshot (AC1).

        Aggregates all constitutional metrics into a single snapshot.
        Calculates overall status per ADR-10: worst component health.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Collect all metrics from ports
        3. Build snapshot with calculated status

        Returns:
            ConstitutionalHealthSnapshot with all metrics and status.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        # Collect metrics from all sources
        breach_count = await self.get_breach_count()
        override_rate = await self.get_override_rate()
        dissent_health = await self.get_dissent_health()
        witness_coverage = await self.get_witness_coverage()

        return ConstitutionalHealthSnapshot(
            breach_count=breach_count,
            override_rate_daily=override_rate,
            dissent_health_percent=dissent_health,
            witness_coverage=witness_coverage,
            calculated_at=datetime.now(timezone.utc),
        )

    async def get_breach_count(self) -> int:
        """Get unacknowledged breach count in 90-day window (FR32).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Query breach repository for unacknowledged breaches

        Returns:
            Number of unacknowledged breaches.
            WARNING at 8, CRITICAL at >10.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        return await self._breach_repository.count_unacknowledged_in_window(
            window_days=CESSATION_WINDOW_DAYS
        )

    async def get_override_rate(self) -> int:
        """Get daily override rate (Story 8.4).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Query override trend repository for today's count

        Returns:
            Number of overrides today.
            WARNING at 3 (incident threshold), CRITICAL at 6.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        trend_data = await self._override_trend_repository.get_trend_data()
        return trend_data.daily_count

    async def get_dissent_health(self) -> float:
        """Get rolling 30-day average dissent percentage (NFR-023).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Query dissent metrics for rolling average

        Returns:
            Dissent percentage (0.0-100.0).
            WARNING if <10%, CRITICAL if <5%.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        return await self._dissent_metrics.get_rolling_average(days=30)

    async def get_witness_coverage(self) -> int:
        """Get effective witness pool size (FR117).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Query witness pool monitor for effective count

        Returns:
            Number of available witnesses.
            WARNING if <12, CRITICAL if <6.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        pool_status = await self._witness_pool_monitor.check_pool_health()
        return pool_status.effective_count

    async def get_overall_status(self) -> ConstitutionalHealthStatus:
        """Get overall constitutional health status (ADR-10).

        Per ADR-10 resolution: System health = worst component health.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get full snapshot
        3. Return overall status from snapshot

        Returns:
            UNHEALTHY if any metric is critical,
            WARNING if any metric is at warning,
            HEALTHY if all metrics are within acceptable ranges.

        Raises:
            SystemHaltedError: If system is halted.
        """
        snapshot = await self.get_constitutional_health()
        return snapshot.overall_status

    async def is_blocking_ceremonies(self) -> bool:
        """Check if ceremonies are blocked (AC4).

        Per ADR-10: Ceremonies are blocked when constitutional
        health is UNHEALTHY. Emergency override required to proceed.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get overall status
        3. Return True if UNHEALTHY

        Returns:
            True if ceremonies cannot proceed due to health status.

        Raises:
            SystemHaltedError: If system is halted.
        """
        status = await self.get_overall_status()
        return status == ConstitutionalHealthStatus.UNHEALTHY

    async def check_ceremony_allowed(self) -> tuple[bool, Optional[str]]:
        """Check if a ceremony can proceed (AC4).

        Provides detailed information about ceremony blocking status.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get full snapshot
        3. Check for blocking metrics
        4. Build reason string if blocked

        Returns:
            Tuple of (allowed, reason):
            - (True, None) if ceremony can proceed
            - (False, reason_string) if blocked with explanation

        Raises:
            SystemHaltedError: If system is halted.
        """
        snapshot = await self.get_constitutional_health()

        if not snapshot.ceremonies_blocked:
            return (True, None)

        # Build detailed blocking reason
        reasons = snapshot.blocking_reasons
        if reasons:
            reason_text = "; ".join(reasons)
            return (False, f"Constitutional health blocking ceremonies: {reason_text}")
        else:
            return (False, "Constitutional health is UNHEALTHY")

    async def get_blocking_metrics(self) -> list[ConstitutionalHealthMetric]:
        """Get list of metrics that are currently blocking ceremonies.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get all metrics from snapshot
        3. Filter for blocking (UNHEALTHY) metrics

        Returns:
            List of ConstitutionalHealthMetric that have is_blocking=True.

        Raises:
            SystemHaltedError: If system is halted.
        """
        snapshot = await self.get_constitutional_health()
        return [m for m in snapshot.get_all_metrics() if m.is_blocking]

    async def get_warning_metrics(self) -> list[ConstitutionalHealthMetric]:
        """Get list of metrics that are at warning level.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get all metrics from snapshot
        3. Filter for warning metrics

        Returns:
            List of ConstitutionalHealthMetric at WARNING status.

        Raises:
            SystemHaltedError: If system is halted.
        """
        snapshot = await self.get_constitutional_health()
        return [
            m
            for m in snapshot.get_all_metrics()
            if m.status == ConstitutionalHealthStatus.WARNING
        ]
