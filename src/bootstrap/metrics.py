"""Bootstrap wiring for metrics collector."""

from __future__ import annotations

from src.application.ports.metrics_exporter import MetricsExporterPort
from src.infrastructure.monitoring.metrics import get_metrics_collector
from src.infrastructure.monitoring.metrics_exporter import PrometheusMetricsExporter

_metrics_exporter: MetricsExporterPort | None = None


def get_metrics_exporter() -> MetricsExporterPort:
    """Get metrics exporter instance (Prometheus)."""
    global _metrics_exporter
    if _metrics_exporter is None:
        _metrics_exporter = PrometheusMetricsExporter()
    return _metrics_exporter


__all__ = ["get_metrics_collector", "get_metrics_exporter"]
