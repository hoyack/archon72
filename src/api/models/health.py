"""Health check response models (Story 8.1, Task 4; Story 8.10).

Models for liveness (/health) and readiness (/ready) endpoints.

NFR28 Requirements:
- /health for liveness (is process running?)
- /ready for readiness (are dependencies connected?)
- Kubernetes probe compatible responses

Constitutional Health Separation (Story 8.10, AC3):
- Operational health: /health (liveness), /ready (dependencies)
- Constitutional health: /health/constitutional (governance metrics)
- Both domains visible, neither masks the other
"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness check response model (operational health).

    Attributes:
        status: Health status string (e.g., "healthy").
        uptime_seconds: Seconds since service startup.
        health_type: Type of health check (always "operational").
        constitutional_health_url: URL to constitutional health endpoint.
    """

    status: str = Field(description="Health status: healthy or unhealthy")
    uptime_seconds: float = Field(
        default=0.0, description="Seconds since service startup"
    )
    health_type: Literal["operational"] = Field(
        default="operational",
        description="Type of health check (operational vs constitutional)",
    )
    constitutional_health_url: str = Field(
        default="/health/constitutional",
        description="URL to check constitutional health (governance metrics)",
    )


class DependencyCheck(BaseModel):
    """Individual dependency health check result.

    Attributes:
        name: Dependency name (e.g., "database", "redis").
        healthy: Whether the dependency is healthy.
        latency_ms: Check latency in milliseconds.
        error: Error message if unhealthy.
    """

    name: str = Field(description="Dependency name")
    healthy: bool = Field(description="Whether dependency is healthy")
    latency_ms: float | None = Field(
        default=None, description="Check latency in milliseconds"
    )
    error: str | None = Field(default=None, description="Error message if unhealthy")


class ReadyResponse(BaseModel):
    """Readiness check response model (operational health).

    Attributes:
        status: Ready status string (e.g., "ready" or "not-ready").
        checks: Dictionary of dependency checks.
        health_type: Type of health check (always "operational").
        constitutional_health_url: URL to constitutional health endpoint.
    """

    status: str = Field(description="Readiness status: ready or not-ready")
    checks: dict[str, DependencyCheck] = Field(
        default_factory=dict, description="Dependency check results"
    )
    health_type: Literal["operational"] = Field(
        default="operational",
        description="Type of health check (operational vs constitutional)",
    )
    constitutional_health_url: str = Field(
        default="/health/constitutional",
        description="URL to check constitutional health (governance metrics)",
    )
