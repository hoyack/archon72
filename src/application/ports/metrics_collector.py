"""Metrics collector port definition.

Defines the abstract interface for metrics collection. This port enables
the application layer to collect metrics without depending on infrastructure.

Architecture Note:
This port allows the application layer to remain independent of the
specific metrics implementation (Prometheus, StatsD, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MetricsCollectorProtocol(ABC):
    """Abstract interface for metrics collection.

    All metrics implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific metrics implementations.
    """

    @abstractmethod
    def get_uptime_seconds(self, service_name: str) -> float:
        """Get service uptime in seconds.

        Args:
            service_name: Name of the service.

        Returns:
            Uptime in seconds since service startup.
        """
        ...

    @abstractmethod
    def record_startup(self, service_name: str) -> None:
        """Record service startup time.

        Args:
            service_name: Name of the service.
        """
        ...

    @abstractmethod
    def increment_counter(self, name: str, value: int = 1, **labels: str) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name.
            value: Value to increment by.
            labels: Additional labels for the metric.
        """
        ...

    @abstractmethod
    def observe_histogram(self, name: str, value: float, **labels: str) -> None:
        """Record a histogram observation.

        Args:
            name: Metric name.
            value: Value to observe.
            labels: Additional labels for the metric.
        """
        ...

    @abstractmethod
    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge metric value.

        Args:
            name: Metric name.
            value: Value to set.
            labels: Additional labels for the metric.
        """
        ...
