"""Bootstrap wiring for operational metrics."""

from __future__ import annotations

from src.application.ports.metrics_collector import MetricsCollectorProtocol
from src.application.ports.metrics_exporter import MetricsExporterPort
from src.infrastructure.monitoring.metrics import (
    METRICS_CONTENT_TYPE,
    generate_metrics,
    get_metrics_collector as get_infra_metrics_collector,
)


class PrometheusMetricsExporter:
    """Prometheus metrics exporter implementation."""

    @property
    def content_type(self) -> str:
        return METRICS_CONTENT_TYPE

    def generate_metrics(self) -> bytes:
        return generate_metrics()


_metrics_collector: MetricsCollectorProtocol | None = None
_metrics_exporter: MetricsExporterPort | None = None


def get_metrics_collector() -> MetricsCollectorProtocol:
    """Get the metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = get_infra_metrics_collector()
    return _metrics_collector


def get_metrics_exporter() -> MetricsExporterPort:
    """Get the metrics exporter instance."""
    global _metrics_exporter
    if _metrics_exporter is None:
        _metrics_exporter = PrometheusMetricsExporter()
    return _metrics_exporter


def set_metrics_collector(collector: MetricsCollectorProtocol) -> None:
    """Set custom metrics collector (testing/override)."""
    global _metrics_collector
    _metrics_collector = collector


def set_metrics_exporter(exporter: MetricsExporterPort) -> None:
    """Set custom metrics exporter (testing/override)."""
    global _metrics_exporter
    _metrics_exporter = exporter


def reset_metrics() -> None:
    """Reset metrics singletons (testing cleanup)."""
    global _metrics_collector
    global _metrics_exporter
    _metrics_collector = None
    _metrics_exporter = None
