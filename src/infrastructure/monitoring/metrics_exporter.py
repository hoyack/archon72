"""Metrics exporter adapter for Prometheus output."""

from __future__ import annotations

from src.application.ports.metrics_exporter import MetricsExporterPort
from src.infrastructure.monitoring.metrics import METRICS_CONTENT_TYPE, generate_metrics


class PrometheusMetricsExporter(MetricsExporterPort):
    """Prometheus metrics exporter adapter."""

    @property
    def content_type(self) -> str:
        return METRICS_CONTENT_TYPE

    def generate_metrics(self) -> bytes:
        return generate_metrics()
