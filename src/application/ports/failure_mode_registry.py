"""Failure Mode Registry port definition (Story 8.8, FR106-FR107).

Defines the abstract interface for storing and querying failure modes,
thresholds, and early warnings. Infrastructure adapters must implement
this protocol.

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load

Usage:
    from src.application.ports.failure_mode_registry import (
        FailureModeRegistryPort,
        HealthSummary,
    )

    class MyFailureModeRegistry(FailureModeRegistryPort):
        async def get_failure_mode(self, mode_id: FailureModeId) -> Optional[FailureMode]:
            # Implementation...
            pass
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.domain.models.failure_mode import (
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeStatus,
    FailureModeThreshold,
)


@dataclass(frozen=True)
class HealthSummary:
    """Summary of all failure mode health statuses.

    Provides an overview of the health state across all failure modes,
    including which modes are in warning or critical state.

    Attributes:
        overall_status: The worst status across all modes.
        mode_statuses: Dict mapping mode ID to its current status.
        warning_count: Number of modes in WARNING state.
        critical_count: Number of modes in CRITICAL state.
        healthy_count: Number of modes in HEALTHY state.
        timestamp: When this summary was generated.
    """

    overall_status: FailureModeStatus
    mode_statuses: dict[FailureModeId, FailureModeStatus]
    warning_count: int
    critical_count: int
    healthy_count: int
    timestamp: datetime


class FailureModeRegistryPort(ABC):
    """Abstract protocol for failure mode registry operations.

    All failure mode registry implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific storage implementations.

    Constitutional Constraint (FR106-FR107):
    The registry tracks failure modes identified during pre-mortem analysis
    and enables early warning before failures impact constitutional operations.

    Methods:
        get_failure_mode: Get a specific failure mode by ID
        get_all_failure_modes: Get all registered failure modes
        get_mode_status: Get current status for a failure mode
        update_mode_metrics: Record new metric values for a mode
        get_threshold: Get threshold configuration for a mode
        set_threshold: Configure threshold for a mode
        get_early_warnings: Get all active early warnings
        record_early_warning: Record a new early warning
        acknowledge_warning: Acknowledge a warning was addressed
        get_health_summary: Get overall health summary
    """

    # Failure mode retrieval

    @abstractmethod
    async def get_failure_mode(self, mode_id: FailureModeId) -> Optional[FailureMode]:
        """Get a specific failure mode by ID.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            The FailureMode if found, None otherwise.

        Raises:
            RuntimeError: If retrieval operation fails.
        """
        ...

    @abstractmethod
    async def get_all_failure_modes(self) -> list[FailureMode]:
        """Get all registered failure modes.

        Returns:
            List of all FailureMode objects.

        Raises:
            RuntimeError: If retrieval operation fails.
        """
        ...

    @abstractmethod
    async def register_failure_mode(self, mode: FailureMode) -> None:
        """Register a new failure mode.

        Args:
            mode: The failure mode to register.

        Raises:
            RuntimeError: If the mode already exists or storage fails.
        """
        ...

    # Status and metrics

    @abstractmethod
    async def get_mode_status(self, mode_id: FailureModeId) -> FailureModeStatus:
        """Get current health status for a failure mode.

        Calculates the status based on the latest metric values
        compared to configured thresholds.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            Current FailureModeStatus (HEALTHY, WARNING, or CRITICAL).

        Raises:
            ValueError: If mode_id is not found.
            RuntimeError: If status calculation fails.
        """
        ...

    @abstractmethod
    async def update_mode_metrics(
        self,
        mode_id: FailureModeId,
        metric_name: str,
        value: float,
    ) -> FailureModeStatus:
        """Record a new metric value for a failure mode.

        Updates the current value for the specified metric and returns
        the resulting status. May trigger early warning generation.

        Args:
            mode_id: The failure mode identifier.
            metric_name: Name of the metric being updated.
            value: The new metric value.

        Returns:
            The resulting FailureModeStatus after the update.

        Raises:
            ValueError: If mode_id is not found.
            RuntimeError: If update fails.
        """
        ...

    # Threshold configuration

    @abstractmethod
    async def get_threshold(
        self,
        mode_id: FailureModeId,
        metric_name: str,
    ) -> Optional[FailureModeThreshold]:
        """Get threshold configuration for a mode and metric.

        Args:
            mode_id: The failure mode identifier.
            metric_name: Name of the metric.

        Returns:
            The threshold configuration if found, None otherwise.

        Raises:
            RuntimeError: If retrieval fails.
        """
        ...

    @abstractmethod
    async def get_all_thresholds(
        self,
        mode_id: FailureModeId,
    ) -> list[FailureModeThreshold]:
        """Get all threshold configurations for a failure mode.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            List of all thresholds configured for the mode.

        Raises:
            RuntimeError: If retrieval fails.
        """
        ...

    @abstractmethod
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
            RuntimeError: If configuration fails.
        """
        ...

    # Early warnings

    @abstractmethod
    async def get_active_warnings(self) -> list[EarlyWarning]:
        """Get all active (unacknowledged) early warnings.

        Returns:
            List of EarlyWarning objects that have not been acknowledged.

        Raises:
            RuntimeError: If retrieval fails.
        """
        ...

    @abstractmethod
    async def get_warnings_for_mode(
        self,
        mode_id: FailureModeId,
    ) -> list[EarlyWarning]:
        """Get all early warnings for a specific failure mode.

        Args:
            mode_id: The failure mode identifier.

        Returns:
            List of EarlyWarning objects for the mode.

        Raises:
            RuntimeError: If retrieval fails.
        """
        ...

    @abstractmethod
    async def record_warning(self, warning: EarlyWarning) -> None:
        """Record a new early warning.

        Args:
            warning: The early warning to record.

        Raises:
            RuntimeError: If recording fails.
        """
        ...

    @abstractmethod
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

        Raises:
            RuntimeError: If acknowledgment fails.
        """
        ...

    # Health summary

    @abstractmethod
    async def get_health_summary(self) -> HealthSummary:
        """Get overall health summary across all failure modes.

        Constitutional Constraint (FR106-FR107):
        Provides visibility into system health to enable preventive action.

        Returns:
            HealthSummary with overall status and per-mode breakdown.

        Raises:
            RuntimeError: If summary generation fails.
        """
        ...

    # Historical data (FR106)

    @abstractmethod
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

        Raises:
            RuntimeError: If retrieval fails.
        """
        ...
