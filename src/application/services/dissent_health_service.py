"""Dissent health service (Story 2.4, FR12).

Application service for tracking and alerting on dissent health metrics.
FR12 requires monitoring dissent trends to detect potential groupthink.

Constitutional Constraints:
- FR12: Dissent percentages visible in every vote tally
- NFR-023: Alerts fire if dissent drops below 10% over 30 days
- CT-11: Silent failure destroys legitimacy

Golden Rules:
- HALT FIRST: Check halt state before every operation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.application.ports.dissent_metrics import DissentMetricsPort
from src.application.ports.halt_checker import HaltChecker

logger = structlog.get_logger()


# Default threshold and period per NFR-023
DEFAULT_DISSENT_THRESHOLD: float = 10.0
DEFAULT_PERIOD_DAYS: int = 30


@dataclass(frozen=True)
class DissentHealthStatus:
    """Status of dissent health metrics.

    Represents the current health status based on rolling average
    dissent percentage over a configurable period.

    Attributes:
        rolling_average: Average dissent percentage over the period.
        period_days: Number of days in the rolling period.
        record_count: Number of dissent records in the period.
        is_healthy: True if dissent is above threshold (healthy disagreement).
    """

    rolling_average: float
    period_days: int
    record_count: int
    is_healthy: bool


@dataclass(frozen=True)
class DissentAlert:
    """Alert for low dissent (potential groupthink).

    Created when rolling average dissent drops below threshold,
    indicating potential groupthink that should be investigated.

    Attributes:
        threshold: Dissent percentage threshold that was violated.
        actual_average: Actual rolling average dissent percentage.
        period_days: Number of days in the rolling period.
        alert_type: Type of alert (DISSENT_BELOW_THRESHOLD).
    """

    threshold: float
    actual_average: float
    period_days: int
    alert_type: str


class DissentHealthService:
    """Application service for dissent health monitoring (FR12).

    Tracks dissent metrics over time and generates alerts when
    dissent drops below threshold, indicating potential groupthink.

    Follows HALT FIRST golden rule: checks halt state before
    every operation.

    Attributes:
        _halt_checker: Halt state checker.
        _metrics_port: Dissent metrics storage port.

    Example:
        >>> service = DissentHealthService(halt_checker, metrics_port)
        >>> await service.record_dissent(output_id, 15.5)
        >>> status = await service.get_health_status()
        >>> alert = await service.check_alert_condition()
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        metrics_port: DissentMetricsPort,
    ) -> None:
        """Initialize dissent health service.

        Args:
            halt_checker: Halt state checker for HALT FIRST pattern.
            metrics_port: Port for dissent metrics storage.
        """
        self._halt_checker = halt_checker
        self._metrics_port = metrics_port

    async def record_dissent(
        self,
        output_id: UUID,
        dissent_percentage: float,
    ) -> None:
        """Record dissent percentage for a collective output.

        HALT FIRST: Checks halt state before recording.

        Args:
            output_id: UUID of the collective output.
            dissent_percentage: Calculated dissent percentage (0.0-100.0).

        Raises:
            SystemHaltedError: If system is halted.
            ValueError: If dissent_percentage is invalid.
        """
        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            from src.domain.errors.writer import SystemHaltedError

            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(reason or "System halted")

        recorded_at = datetime.now(timezone.utc)

        await self._metrics_port.record_vote_dissent(
            output_id=output_id,
            dissent_percentage=dissent_percentage,
            recorded_at=recorded_at,
        )

        logger.info(
            "dissent_recorded",
            output_id=str(output_id),
            dissent_percentage=dissent_percentage,
        )

    async def get_health_status(
        self,
        days: int = DEFAULT_PERIOD_DAYS,
        threshold: float = DEFAULT_DISSENT_THRESHOLD,
    ) -> DissentHealthStatus:
        """Get current dissent health status.

        HALT FIRST: Checks halt state before querying.

        Args:
            days: Number of days for rolling average (default 30).
            threshold: Dissent threshold for health (default 10.0).

        Returns:
            DissentHealthStatus with current metrics.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            from src.domain.errors.writer import SystemHaltedError

            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(reason or "System halted")

        rolling_average = await self._metrics_port.get_rolling_average(days)
        history = await self._metrics_port.get_dissent_history(days)
        is_below = await self._metrics_port.is_below_threshold(threshold, days)

        return DissentHealthStatus(
            rolling_average=rolling_average,
            period_days=days,
            record_count=len(history),
            is_healthy=not is_below,
        )

    async def check_alert_condition(
        self,
        threshold: float = DEFAULT_DISSENT_THRESHOLD,
        days: int = DEFAULT_PERIOD_DAYS,
    ) -> DissentAlert | None:
        """Check if dissent is below threshold and generate alert.

        Per NFR-023, alerts fire if dissent drops below 10% over 30 days.

        HALT FIRST: Checks halt state before checking.

        Args:
            threshold: Dissent percentage threshold (default 10.0).
            days: Number of days to consider (default 30).

        Returns:
            DissentAlert if below threshold, None otherwise.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            from src.domain.errors.writer import SystemHaltedError

            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(reason or "System halted")

        is_below = await self._metrics_port.is_below_threshold(threshold, days)

        if not is_below:
            return None

        rolling_average = await self._metrics_port.get_rolling_average(days)

        alert = DissentAlert(
            threshold=threshold,
            actual_average=rolling_average,
            period_days=days,
            alert_type="DISSENT_BELOW_THRESHOLD",
        )

        logger.warning(
            "dissent_alert_triggered",
            threshold=threshold,
            actual_average=rolling_average,
            period_days=days,
        )

        return alert
