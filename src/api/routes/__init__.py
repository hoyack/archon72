"""
API routes for Archon 72.

This module contains all FastAPI router definitions.
Routes are organized by domain concern.

Available routers:
- health: Health check endpoints (internal liveness/readiness)
- external_health: External monitoring endpoint (FR54 - no auth)
- observer: Public observer API (FR44 - no auth required)
- override: Public override visibility API (FR25 - no auth required)
- petition: External observer petition API (FR39 - public with signature)
- incident: Incident report API (FR145, FR147 - public read access)
- constitutional_health: Constitutional health metrics (ADR-10, Story 8.10)
- waiver: Constitutional waiver API (SC-4, SR-10, Story 9.8 - public read)
- compliance: Compliance documentation API (NFR31-34, Story 9.9 - public read)
- halt: Halt trigger API (FR22-23, Story 4-2 - requires auth)
- legitimacy: Legitimacy restoration API (FR30-32, Story 5-3 - auth for restore)
- petition_submission: Three Fates petition submission (Story 1.1, FR-1.1 - public)
- co_sign: Three Fates petition co-signing (Story 5.2, FR-6.1 - public)
"""

from src.api.routes.co_sign import router as co_sign_router
from src.api.routes.complexity_budget import router as complexity_budget_router
from src.api.routes.compliance import router as compliance_router
from src.api.routes.constitutional_health import router as constitutional_health_router
from src.api.routes.escalation import router as escalation_router
from src.api.routes.external_health import router as external_health_router
from src.api.routes.failure_prevention import router as failure_prevention_router
from src.api.routes.halt import router as halt_router
from src.api.routes.health import router as health_router
from src.api.routes.incident import router as incident_router
from src.api.routes.legitimacy import router as legitimacy_router
from src.api.routes.observer import router as observer_router
from src.api.routes.override import router as override_router
from src.api.routes.petition import router as petition_router
from src.api.routes.petition_submission import router as petition_submission_router
from src.api.routes.waiver import router as waiver_router

__all__: list[str] = [
    "health_router",
    "external_health_router",
    "observer_router",
    "override_router",
    "petition_router",
    "petition_submission_router",
    "incident_router",
    "complexity_budget_router",
    "failure_prevention_router",
    "constitutional_health_router",
    "waiver_router",
    "compliance_router",
    "halt_router",
    "legitimacy_router",
    # Co-Sign router (Story 5.2, FR-6.1)
    "co_sign_router",
    # Escalation router (Story 6.1, FR-5.4)
    "escalation_router",
]
