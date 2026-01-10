"""Health check DTOs for application layer.

Application-layer DTOs for health check operations. These are used by
the HealthService and mapped to API Pydantic models by the routes.

Architecture Note:
Application layer defines its own DTOs to maintain independence
from the API layer. API routes convert these DTOs to Pydantic response models.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class DependencyCheckDTO:
    """Individual dependency health check result.

    Attributes:
        name: Dependency name (e.g., "database", "redis").
        healthy: Whether the dependency is healthy.
        latency_ms: Check latency in milliseconds.
        error: Error message if unhealthy.
    """

    name: str
    healthy: bool
    latency_ms: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class HealthResponseDTO:
    """Liveness check response DTO (operational health).

    Attributes:
        status: Health status string (e.g., "healthy").
        uptime_seconds: Seconds since service startup.
        health_type: Type of health check (always "operational").
        constitutional_health_url: URL to constitutional health endpoint.
    """

    status: str
    uptime_seconds: float = 0.0
    health_type: Literal["operational"] = "operational"
    constitutional_health_url: str = "/health/constitutional"


@dataclass(frozen=True)
class ReadyResponseDTO:
    """Readiness check response DTO (operational health).

    Attributes:
        status: Ready status string (e.g., "ready" or "not-ready").
        checks: Dictionary of dependency checks.
        health_type: Type of health check (always "operational").
        constitutional_health_url: URL to constitutional health endpoint.
    """

    status: str
    checks: dict[str, DependencyCheckDTO] = field(default_factory=dict)
    health_type: Literal["operational"] = "operational"
    constitutional_health_url: str = "/health/constitutional"
