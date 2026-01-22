"""Bootstrap wiring for correlation utilities."""

from src.application.observability.correlation import (
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
)

__all__ = [
    "generate_correlation_id",
    "get_correlation_id",
    "set_correlation_id",
]
