"""API dependencies for dependency injection."""

from src.api.dependencies.cessation import (
    get_freeze_checker,
    require_not_ceased,
    set_freeze_checker,
)
from src.api.dependencies.correlation import get_correlation_id_header
from src.api.dependencies.observer import (
    get_event_store,
    get_halt_checker,
    get_observer_service,
    get_rate_limiter,
)
from src.api.dependencies.petition_submission import (
    get_petition_submission_service,
    reset_petition_submission_dependencies,
)

__all__: list[str] = [
    "get_correlation_id_header",
    "get_event_store",
    "get_freeze_checker",
    "get_halt_checker",
    "get_observer_service",
    "get_petition_submission_service",
    "get_rate_limiter",
    "require_not_ceased",
    "reset_petition_submission_dependencies",
    "set_freeze_checker",
]
