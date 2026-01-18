"""Failure Prevention Service (Story 8.8, FR106-FR107).

This service manages pre-mortem operational failure prevention,
including failure mode tracking, early warning generation, and
health monitoring.

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All warnings witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every write operation
2. WITNESS EVERYTHING - All early warnings must be witnessed
3. FAIL LOUD - Never silently swallow failure mode violations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.ports.failure_mode_registry import (
    FailureModeRegistryPort,
    HealthSummary,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.services.base import LoggingMixin
from src.domain.errors.failure_prevention import (
    FailureModeViolationError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.failure_mode import (
    DEFAULT_FAILURE_MODES,
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeStatus,
    FailureModeThreshold,
)

if TYPE_CHECKING:
    pass

# System agent ID for failure prevention events
FAILURE_PREVENTION_SYSTEM_AGENT_ID: str = "failure_prevention_system"


class FailurePreventionService(LoggingMixin):
    """Manages pre-mortem failure prevention and early warning (FR106-FR107).

    This service provides:
    1. Failure mode registration and retrieval (AC1)
    2. Early warning generation when thresholds approached (AC2)
    3. Health status monitoring across all failure modes (AC3)
    4. Metric recording and historical tracking

    Constitutional Constraints:
    - FR106: Historical queries within 30 seconds for <10k events
    - FR107: Constitutional events NEVER shed
    - CT-11: HALT CHECK FIRST at every write operation
    - CT-12: All early warnings MUST be witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every write operation checks halt state
    2. WITNESS EVERYTHING - Early warnings witnessed via event store
    3. FAIL LOUD - Raise specific errors for failures
    """

    def __init__(
        self,
        registry: FailureModeRegistryPort,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Failure Prevention Service.

        Args:
            registry: Port for failure mode storage and queries.
            halt_checker: Interface to check system halt state (CT-11).
        """
        self._registry = registry
        self._halt_checker = halt_checker
        self._init_logger(component="constitutional")

    async def initialize_default_failure_modes(self) -> int:
        """Initialize the registry with default failure modes from architecture.

        Registers all failure modes identified during pre-mortem analysis
        (VAL-*) and pattern violation risk matrix (PV-*).

        Returns:
            Number of failure modes registered.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = self._log_operation("initialize_default_failure_modes")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "initialization_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        count = 0
        for mode_id, mode in DEFAULT_FAILURE_MODES.items():
            try:
                await self._registry.register_failure_mode(mode)
                count += 1
                log.debug("failure_mode_registered", mode_id=mode_id.value)
            except RuntimeError as e:
                # Mode may already exist, log and continue
                log.debug(
                    "failure_mode_already_exists",
                    mode_id=mode_id.value,
                    error=str(e),
                )

        log.info(
            "default_failure_modes_initialized",
            registered_count=count,
            total_modes=len(DEFAULT_FAILURE_MODES),
        )

        return count

    async def get_failure_mode(self, mode_id: FailureModeId) -> FailureMode | None:
        """Get a specific failure mode by ID (AC1).

        Args:
            mode_id: The failure mode identifier.

        Returns:
            The FailureMode if found, None otherwise.
        """
        return await self._registry.get_failure_mode(mode_id)

    async def get_all_failure_modes(self) -> list[FailureMode]:
        """Get all registered failure modes (AC1).

        Returns:
            List of all registered FailureMode objects.
        """
        return await self._registry.get_all_failure_modes()

    async def check_failure_mode(self, mode_id: FailureModeId) -> FailureModeStatus:
        """Check current status for a specific failure mode (AC1).

        Args:
            mode_id: The failure mode identifier.

        Returns:
            Current FailureModeStatus (HEALTHY, WARNING, or CRITICAL).
        """
        log = self._log_operation("check_failure_mode", mode_id=mode_id.value)

        status = await self._registry.get_mode_status(mode_id)

        log.info(
            "failure_mode_checked",
            status=status.value,
        )

        return status

    async def record_metric(
        self,
        mode_id: FailureModeId,
        metric_name: str,
        value: float,
    ) -> FailureModeStatus:
        """Record a new metric value for a failure mode (AC3).

        Updates the metric value and may generate early warnings if
        thresholds are breached.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before write.

        Args:
            mode_id: The failure mode identifier.
            metric_name: Name of the metric being updated.
            value: The new metric value.

        Returns:
            The resulting FailureModeStatus after the update.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = self._log_operation(
            "record_metric",
            mode_id=mode_id.value,
            metric_name=metric_name,
            value=value,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "metric_record_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # Update metric and get resulting status
        status = await self._registry.update_mode_metrics(mode_id, metric_name, value)

        # Check if we need to generate an early warning
        threshold = await self._registry.get_threshold(mode_id, metric_name)
        if threshold and status in (
            FailureModeStatus.WARNING,
            FailureModeStatus.CRITICAL,
        ):
            # Generate and record early warning
            warning = await self._generate_early_warning(
                mode_id=mode_id,
                metric_name=metric_name,
                current_value=value,
                threshold=threshold,
            )
            await self._registry.record_warning(warning)

            log.warning(
                "early_warning_generated",
                warning_id=str(warning.warning_id),
                threshold_type=warning.threshold_type,
            )

        log.info(
            "metric_recorded",
            status=status.value,
        )

        return status

    async def _generate_early_warning(
        self,
        mode_id: FailureModeId,
        metric_name: str,
        current_value: float,
        threshold: FailureModeThreshold,
    ) -> EarlyWarning:
        """Generate an early warning for threshold breach (AC2).

        Args:
            mode_id: The failure mode that triggered the warning.
            metric_name: Name of the metric.
            current_value: Current value that triggered the warning.
            threshold: The threshold configuration.

        Returns:
            The generated EarlyWarning.
        """
        # Determine threshold type based on which was breached
        if threshold.is_critical:
            threshold_type = "critical"
            threshold_value = threshold.critical_value
        else:
            threshold_type = "warning"
            threshold_value = threshold.warning_value

        # Get the failure mode for recommended action
        mode = await self._registry.get_failure_mode(mode_id)
        recommended_action = (
            mode.mitigation if mode else "Review failure mode mitigation strategy"
        )

        return EarlyWarning.create(
            mode_id=mode_id,
            current_value=current_value,
            threshold=threshold_value,
            threshold_type=threshold_type,
            recommended_action=recommended_action,
            metric_name=metric_name,
        )

    async def get_early_warnings(self) -> list[EarlyWarning]:
        """Get all active (unacknowledged) early warnings (AC2).

        Returns:
            List of active EarlyWarning objects.
        """
        return await self._registry.get_active_warnings()

    async def acknowledge_warning(
        self,
        warning_id: str,
        acknowledged_by: str,
    ) -> bool:
        """Acknowledge that a warning has been addressed (AC2).

        Args:
            warning_id: The warning to acknowledge.
            acknowledged_by: Who acknowledged the warning.

        Returns:
            True if warning was found and acknowledged.
        """
        log = self._log_operation(
            "acknowledge_warning",
            warning_id=warning_id,
            acknowledged_by=acknowledged_by,
        )

        from uuid import UUID

        result = await self._registry.acknowledge_warning(
            UUID(warning_id),
            acknowledged_by,
        )

        if result:
            log.info("warning_acknowledged")
        else:
            log.warning("warning_not_found")

        return result

    async def get_health_summary(self) -> HealthSummary:
        """Get overall health summary across all failure modes (AC3).

        Constitutional Constraint (FR106-FR107):
        Provides visibility into system health to enable preventive action.

        Returns:
            HealthSummary with overall status and per-mode breakdown.
        """
        log = self._log_operation("get_health_summary")

        summary = await self._registry.get_health_summary()

        log.info(
            "health_summary_retrieved",
            overall_status=summary.overall_status.value,
            warning_count=summary.warning_count,
            critical_count=summary.critical_count,
            healthy_count=summary.healthy_count,
        )

        return summary

    async def configure_threshold(
        self,
        mode_id: FailureModeId,
        metric_name: str,
        warning_value: float,
        critical_value: float,
        comparison: str = "greater",
    ) -> FailureModeThreshold:
        """Configure threshold for a failure mode metric (AC3).

        Args:
            mode_id: The failure mode identifier.
            metric_name: Name of the metric.
            warning_value: Value at which WARNING is triggered.
            critical_value: Value at which CRITICAL is triggered.
            comparison: "greater" or "less" for comparison direction.

        Returns:
            The created threshold configuration.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = self._log_operation(
            "configure_threshold",
            mode_id=mode_id.value,
            metric_name=metric_name,
            warning_value=warning_value,
            critical_value=critical_value,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "threshold_config_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        threshold = FailureModeThreshold.create(
            mode_id=mode_id,
            metric_name=metric_name,
            warning_value=warning_value,
            critical_value=critical_value,
            comparison=comparison,
        )

        await self._registry.set_threshold(mode_id, threshold)

        log.info("threshold_configured")

        return threshold

    async def get_dashboard_data(self) -> dict[str, Any]:
        """Get failure prevention dashboard data (AC1, AC3).

        Returns:
            Dictionary with all dashboard data including:
            - All registered failure modes
            - Current status for each mode
            - Active warning count
            - Overall health status
        """
        log = self._log_operation("get_dashboard_data")

        modes = await self._registry.get_all_failure_modes()
        summary = await self._registry.get_health_summary()
        warnings = await self._registry.get_active_warnings()

        mode_data = []
        for mode in modes:
            status = await self._registry.get_mode_status(mode.id)
            thresholds = await self._registry.get_all_thresholds(mode.id)

            mode_data.append(
                {
                    "id": mode.id.value,
                    "description": mode.description,
                    "severity": mode.severity.value,
                    "mitigation": mode.mitigation,
                    "adr_reference": mode.adr_reference,
                    "owner": mode.owner,
                    "status": status.value,
                    "threshold_count": len(thresholds),
                }
            )

        warning_data = [
            {
                "id": str(w.warning_id),
                "mode_id": w.mode_id.value,
                "metric_name": w.metric_name,
                "current_value": w.current_value,
                "threshold": w.threshold,
                "threshold_type": w.threshold_type,
                "recommended_action": w.recommended_action,
                "timestamp": w.timestamp.isoformat(),
            }
            for w in warnings
        ]

        log.info(
            "dashboard_data_retrieved",
            mode_count=len(modes),
            warning_count=len(warnings),
        )

        return {
            "failure_modes": mode_data,
            "active_warnings": warning_data,
            "overall_status": summary.overall_status.value,
            "warning_count": summary.warning_count,
            "critical_count": summary.critical_count,
            "healthy_count": summary.healthy_count,
            "last_updated": summary.timestamp.isoformat(),
        }

    async def raise_if_mode_critical(self, mode_id: FailureModeId) -> None:
        """Raise error if failure mode is in CRITICAL state.

        Use this method to enforce failure mode health before
        proceeding with operations that depend on that mode.

        Args:
            mode_id: The failure mode to check.

        Raises:
            FailureModeViolationError: If mode is CRITICAL.
        """
        status = await self._registry.get_mode_status(mode_id)

        if status == FailureModeStatus.CRITICAL:
            mode = await self._registry.get_failure_mode(mode_id)
            description = mode.description if mode else "Unknown failure mode"
            mitigation = mode.mitigation if mode else "Check failure mode documentation"

            raise FailureModeViolationError(
                mode_id=mode_id,
                violation_description=f"Failure mode {mode_id.value} is in CRITICAL state: {description}",
                remediation=mitigation,
            )

    async def warn_if_mode_warning(self, mode_id: FailureModeId) -> EarlyWarning | None:
        """Return early warning if failure mode is in WARNING state.

        Use this method to check failure mode health and get warning
        details without blocking operations.

        Args:
            mode_id: The failure mode to check.

        Returns:
            EarlyWarning if mode is in WARNING state, None otherwise.
        """
        status = await self._registry.get_mode_status(mode_id)

        if status == FailureModeStatus.WARNING:
            warnings = await self._registry.get_warnings_for_mode(mode_id)
            if warnings:
                return warnings[-1]  # Return most recent warning

        return None
