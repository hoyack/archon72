"""FastAPI application entry point for Archon 72."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.middleware.logging_middleware import LoggingMiddleware
from src.api.middleware.metrics_middleware import MetricsMiddleware
from src.api.routes.complexity_budget import router as complexity_budget_router
from src.api.routes.configuration_health import router as configuration_health_router
from src.api.routes.constitutional_health import router as constitutional_health_router
from src.api.routes.health import router as health_router
from src.api.routes.metrics import router as metrics_router
from src.api.routes.observer import router as observer_router
from src.api.routes.override import router as override_router
from src.api.routes.petition_submission import router as petition_submission_router
from src.api.routes.co_sign import router as co_sign_router
from src.api.startup import (
    configure_logging,
    record_service_startup,
    run_pre_operational_verification,
    validate_configuration_floors_at_startup,
    validate_hsm_security_boundary,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager with startup validation.

    Constitutional Constraints:
    - NFR27: Structured logging configured first (Story 8.7)
    - H1 Fix: HSM security boundary validated before any HSM operations
    - NFR39: Configuration floors are validated at startup. Application will not
             start if any configuration is below its constitutional floor.
    - FR146: Pre-operational verification checklist runs after floor validation.
             Startup blocked if any verification check fails.
    - NFR35: Verification checklist must complete before accepting requests.

    Operational (Story 8.1):
    Records startup time for uptime metrics tracking.
    """
    # Startup: Configure structured logging first (Story 8.7, NFR27)
    configure_logging()
    # Startup: Validate HSM security boundary (H1 fix - security audit)
    # MUST be early, before any HSM operations
    validate_hsm_security_boundary()
    # Startup: Validate configuration floors (NFR39, AC1)
    await validate_configuration_floors_at_startup()
    # Startup: Run pre-operational verification (FR146, NFR35)
    await run_pre_operational_verification()
    # Startup: Record service startup for metrics (Story 8.1, AC2)
    record_service_startup()
    yield
    # Shutdown: No cleanup needed


app = FastAPI(
    title="Archon 72 Conclave API",
    description="Constitutional AI Governance System",
    version="0.1.0",
    lifespan=lifespan,
)

# Add logging middleware for correlation ID propagation (Story 8.7, AC2)
# LoggingMiddleware must be added first (outermost) to ensure correlation ID
# is set before MetricsMiddleware runs, enabling correlation in metrics logs
app.add_middleware(LoggingMiddleware)
# Add metrics middleware for request instrumentation (Story 8.1, NFR27)
app.add_middleware(MetricsMiddleware)

app.include_router(complexity_budget_router)
app.include_router(configuration_health_router)
app.include_router(constitutional_health_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(observer_router)
app.include_router(override_router)
app.include_router(petition_submission_router)
app.include_router(co_sign_router)
