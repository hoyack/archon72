"""Failure mode registry stub implementation (Story 8.8, FR106-FR107).

This module provides an in-memory stub implementation of FailureModeRegistryPort
for testing and development purposes.

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load

Usage:
    from src.infrastructure.stubs.failure_mode_registry_stub import (
        FailureModeRegistryStub,
    )

    stub = FailureModeRegistryStub()
    stub.pre_populate_default_modes()  # Load all VAL-* and PV-* modes
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.failure_mode_registry import (
    FailureModeRegistryPort,
    HealthSummary,
)
from src.domain.models.failure_mode import (
    DEFAULT_FAILURE_MODES,
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeStatus,
    FailureModeThreshold,
)


class FailureModeRegistryStub(FailureModeRegistryPort):
    """In-memory stub for failure mode registry (testing only).

    This stub provides an in-memory implementation of FailureModeRegistryPort
    suitable for unit and integration tests.

    Constitutional Constraint (FR106-FR107):
    Pre-populates with all VAL-* and PV-* failure modes from architecture.md
    to ensure test coverage of all pre-mortem failure scenarios.

    The stub stores:
    - Failure modes in a dict keyed by FailureModeId
    - Thresholds in a dict keyed by (mode_id, metric_name) tuple
    - Early warnings in a list
    - Metric history as a list of (timestamp, value) tuples per mode/metric
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._modes: dict[FailureModeId, FailureMode] = {}
        self._thresholds: dict[tuple[FailureModeId, str], FailureModeThreshold] = {}
        self._warnings: list[EarlyWarning] = []
        self._acknowledged_warnings: set[UUID] = set()
        self._metric_history: dict[
            tuple[FailureModeId, str], list[tuple[datetime, float]]
        ] = {}

    def pre_populate_default_modes(self) -> None:
        """Pre-populate with all default failure modes from architecture.

        Loads all VAL-* and PV-* failure modes defined in DEFAULT_FAILURE_MODES.
        Call this after construction to set up realistic test scenarios.
        """
        for mode_id, mode in DEFAULT_FAILURE_MODES.items():
            self._modes[mode_id] = mode

    def clear(self) -> None:
        """Clear all stored data (for test cleanup)."""
        self._modes.clear()
        self._thresholds.clear()
        self._warnings.clear()
        self._acknowledged_warnings.clear()
        self._metric_history.clear()

    # Failure mode retrieval

    async def get_failure_mode(self, mode_id: FailureModeId) -> FailureMode | None:
        """Get a specific failure mode by ID.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            The FailureMode if found, None otherwise.
        """
        return self._modes.get(mode_id)

    async def get_all_failure_modes(self) -> list[FailureMode]:
        """Get all registered failure modes.

        Returns:
            List of all FailureMode objects.
        """
        return list(self._modes.values())

    async def register_failure_mode(self, mode: FailureMode) -> None:
        """Register a new failure mode.

        Args:
            mode: The failure mode to register.

        Raises:
            RuntimeError: If the mode already exists.
        """
        if mode.id in self._modes:
            raise RuntimeError(f"Failure mode {mode.id.value} already registered")
        self._modes[mode.id] = mode

    # Status and metrics

    async def get_mode_status(self, mode_id: FailureModeId) -> FailureModeStatus:
        """Get current health status for a failure mode.

        Calculates the status based on the worst threshold status
        for this failure mode.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            Current FailureModeStatus (HEALTHY, WARNING, or CRITICAL).

        Raises:
            ValueError: If mode_id is not found.
        """
        if mode_id not in self._modes:
            raise ValueError(f"Failure mode {mode_id.value} not found")

        # Find worst status among thresholds for this mode
        worst_status = FailureModeStatus.HEALTHY
        for (m_id, _), threshold in self._thresholds.items():
            if m_id == mode_id:
                if threshold.status == FailureModeStatus.CRITICAL:
                    return FailureModeStatus.CRITICAL
                elif threshold.status == FailureModeStatus.WARNING:
                    worst_status = FailureModeStatus.WARNING

        return worst_status

    async def update_mode_metrics(
        self,
        mode_id: FailureModeId,
        metric_name: str,
        value: float,
    ) -> FailureModeStatus:
        """Record a new metric value for a failure mode.

        Updates the threshold's current value and records in history.

        Args:
            mode_id: The failure mode identifier.
            metric_name: Name of the metric being updated.
            value: The new metric value.

        Returns:
            The resulting FailureModeStatus after the update.

        Raises:
            ValueError: If mode_id is not found.
        """
        if mode_id not in self._modes:
            raise ValueError(f"Failure mode {mode_id.value} not found")

        key = (mode_id, metric_name)
        now = datetime.now(timezone.utc)

        # Update threshold if it exists
        if key in self._thresholds:
            old_threshold = self._thresholds[key]
            # Create new immutable threshold with updated value
            self._thresholds[key] = FailureModeThreshold(
                threshold_id=old_threshold.threshold_id,
                mode_id=old_threshold.mode_id,
                metric_name=old_threshold.metric_name,
                warning_value=old_threshold.warning_value,
                critical_value=old_threshold.critical_value,
                current_value=value,
                last_updated=now,
                comparison=old_threshold.comparison,
            )

        # Record in history
        if key not in self._metric_history:
            self._metric_history[key] = []
        self._metric_history[key].append((now, value))

        return await self.get_mode_status(mode_id)

    # Threshold configuration

    async def get_threshold(
        self,
        mode_id: FailureModeId,
        metric_name: str,
    ) -> FailureModeThreshold | None:
        """Get threshold configuration for a mode and metric.

        Args:
            mode_id: The failure mode identifier.
            metric_name: Name of the metric.

        Returns:
            The threshold configuration if found, None otherwise.
        """
        return self._thresholds.get((mode_id, metric_name))

    async def get_all_thresholds(
        self,
        mode_id: FailureModeId,
    ) -> list[FailureModeThreshold]:
        """Get all threshold configurations for a failure mode.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            List of all thresholds configured for the mode.
        """
        return [
            threshold
            for (m_id, _), threshold in self._thresholds.items()
            if m_id == mode_id
        ]

    async def set_threshold(
        self,
        mode_id: FailureModeId,
        threshold: FailureModeThreshold,
    ) -> None:
        """Configure threshold for a failure mode metric.

        Args:
            mode_id: The failure mode identifier.
            threshold: The threshold configuration.

        Raises:
            ValueError: If mode_id is not found.
        """
        if mode_id not in self._modes:
            raise ValueError(f"Failure mode {mode_id.value} not found")

        key = (mode_id, threshold.metric_name)
        self._thresholds[key] = threshold

    # Early warnings

    async def get_active_warnings(self) -> list[EarlyWarning]:
        """Get all active (unacknowledged) early warnings.

        Returns:
            List of EarlyWarning objects that have not been acknowledged.
        """
        return [
            w for w in self._warnings if w.warning_id not in self._acknowledged_warnings
        ]

    async def get_warnings_for_mode(
        self,
        mode_id: FailureModeId,
    ) -> list[EarlyWarning]:
        """Get all early warnings for a specific failure mode.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            List of EarlyWarning objects for the mode.
        """
        return [w for w in self._warnings if w.mode_id == mode_id]

    async def record_warning(self, warning: EarlyWarning) -> None:
        """Record a new early warning.

        Args:
            warning: The early warning to record.
        """
        self._warnings.append(warning)

    async def acknowledge_warning(
        self,
        warning_id: UUID,
        acknowledged_by: str,
    ) -> bool:
        """Acknowledge that a warning has been addressed.

        Args:
            warning_id: The warning to acknowledge.
            acknowledged_by: Who acknowledged the warning.

        Returns:
            True if warning was found and acknowledged, False if not found.
        """
        for warning in self._warnings:
            if warning.warning_id == warning_id:
                self._acknowledged_warnings.add(warning_id)
                return True
        return False

    # Health summary

    async def get_health_summary(self) -> HealthSummary:
        """Get overall health summary across all failure modes.

        Constitutional Constraint (FR106-FR107):
        Provides visibility into system health to enable preventive action.

        Returns:
            HealthSummary with overall status and per-mode breakdown.
        """
        mode_statuses: dict[FailureModeId, FailureModeStatus] = {}
        warning_count = 0
        critical_count = 0
        healthy_count = 0

        for mode_id in self._modes:
            status = await self.get_mode_status(mode_id)
            mode_statuses[mode_id] = status
            if status == FailureModeStatus.CRITICAL:
                critical_count += 1
            elif status == FailureModeStatus.WARNING:
                warning_count += 1
            else:
                healthy_count += 1

        # Overall status is the worst status
        if critical_count > 0:
            overall_status = FailureModeStatus.CRITICAL
        elif warning_count > 0:
            overall_status = FailureModeStatus.WARNING
        else:
            overall_status = FailureModeStatus.HEALTHY

        return HealthSummary(
            overall_status=overall_status,
            mode_statuses=mode_statuses,
            warning_count=warning_count,
            critical_count=critical_count,
            healthy_count=healthy_count,
            timestamp=datetime.now(timezone.utc),
        )

    # Historical data (FR106)

    async def get_metric_history(
        self,
        mode_id: FailureModeId,
        metric_name: str,
        start: datetime,
        end: datetime,
        limit: int = 10000,
    ) -> list[tuple[datetime, float]]:
        """Get historical metric values for trend analysis.

        Constitutional Constraint (FR106):
        For ranges up to 10,000 events, must complete within 30 seconds.

        Args:
            mode_id: The failure mode identifier.
            metric_name: Name of the metric.
            start: Start of the date range.
            end: End of the date range.
            limit: Maximum number of data points (default 10,000).

        Returns:
            List of (timestamp, value) tuples.
        """
        key = (mode_id, metric_name)
        if key not in self._metric_history:
            return []

        # Filter by date range and apply limit
        filtered = [
            (ts, val) for ts, val in self._metric_history[key] if start <= ts <= end
        ]
        return filtered[:limit]

    # Test helper methods (not part of protocol)

    def get_mode_count(self) -> int:
        """Get total number of registered failure modes."""
        return len(self._modes)

    def get_threshold_count(self) -> int:
        """Get total number of configured thresholds."""
        return len(self._thresholds)

    def get_warning_count(self) -> int:
        """Get total number of recorded warnings."""
        return len(self._warnings)

    def get_active_warning_count(self) -> int:
        """Get number of unacknowledged warnings."""
        return len(
            [
                w
                for w in self._warnings
                if w.warning_id not in self._acknowledged_warnings
            ]
        )

    def get_acknowledged_count(self) -> int:
        """Get number of acknowledged warnings."""
        return len(self._acknowledged_warnings)

    def add_mode(self, mode: FailureMode) -> None:
        """Synchronously add a failure mode (for test setup)."""
        self._modes[mode.id] = mode

    def add_threshold(self, threshold: FailureModeThreshold) -> None:
        """Synchronously add a threshold (for test setup)."""
        self._thresholds[(threshold.mode_id, threshold.metric_name)] = threshold

    def add_warning(self, warning: EarlyWarning) -> None:
        """Synchronously add a warning (for test setup)."""
        self._warnings.append(warning)

    def add_metric_point(
        self,
        mode_id: FailureModeId,
        metric_name: str,
        timestamp: datetime,
        value: float,
    ) -> None:
        """Synchronously add a metric history point (for test setup)."""
        key = (mode_id, metric_name)
        if key not in self._metric_history:
            self._metric_history[key] = []
        self._metric_history[key].append((timestamp, value))
