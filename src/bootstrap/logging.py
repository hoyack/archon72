"""Bootstrap wiring for logging configuration."""

from __future__ import annotations

from src.infrastructure.observability import configure_structlog as _configure_structlog


def configure_structlog(environment: str) -> None:
    """Configure structlog for the given environment."""
    _configure_structlog(environment=environment)


__all__ = ["configure_structlog"]
