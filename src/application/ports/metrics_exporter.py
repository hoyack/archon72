"""Metrics exporter port for operational metrics output."""

from __future__ import annotations

from typing import Protocol


class MetricsExporterPort(Protocol):
    """Protocol for exporting operational metrics (e.g., Prometheus)."""

    @property
    def content_type(self) -> str:
        """Content type for metrics output."""
        ...

    def generate_metrics(self) -> bytes:
        """Generate metrics output in exporter format."""
        ...


__all__ = ["MetricsExporterPort"]
