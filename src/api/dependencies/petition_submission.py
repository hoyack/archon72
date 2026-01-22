"""Petition Submission API dependencies (Story 1.1, FR-1.1, Story 1.3, FR-1.4, Story 1.4, FR-1.5).

Dependency injection setup for petition submission components.
Provides stub implementations for development and testing.

Constitutional Constraints:
- FR-1.1: Accept petition submissions via REST API
- FR-1.4: Return HTTP 503 on queue overflow (Story 1.3)
- FR-1.5: Enforce rate limits per submitter_id (Story 1.4)
- FR-1.6: Set initial state to RECEIVED
- HC-4: 10 petitions/user/hour (configurable)
- D4: PostgreSQL time-bucket counters
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- HP-2: Content hashing for duplicate detection
- HP-3: Realm registry for petition routing
- NFR-3.1: No silent petition loss
- NFR-5.1: Rate limiting per identity

Note: These are stub implementations. Production would use:
- Supabase-backed PetitionSubmissionRepository
- Blake3ContentHashService (already real implementation)
- Supabase-backed RealmRegistryService
- Real HaltChecker with dual-channel support
- QueueCapacityService with real repository
- RateLimitService with PostgresRateLimitStore
"""

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.ports.rate_limiter import RateLimiterPort
from src.application.ports.realm_registry import RealmRegistryProtocol
from src.application.services.petition_submission_service import (
    PetitionSubmissionService,
)
from src.application.services.queue_capacity_service import QueueCapacityService
from src.bootstrap.petition_submission import (
    get_content_hash_service,
    get_petition_halt_checker,
    get_petition_queue_config,
    get_petition_submission_repository,
    get_rate_limit_config,
    get_rate_limiter,
    get_realm_registry,
    reset_petition_submission_dependencies as _reset_petition_submission_dependencies,
    set_halt_checker as _set_halt_checker,
    set_petition_queue_config as _set_petition_queue_config,
    set_petition_submission_repository as _set_petition_submission_repository,
    set_rate_limit_config as _set_rate_limit_config,
    set_rate_limiter as _set_rate_limiter,
    set_realm_registry as _set_realm_registry,
)
from src.config.petition_config import PetitionQueueConfig, PetitionRateLimitConfig

_petition_submission_service: PetitionSubmissionService | None = None
_queue_capacity_service: QueueCapacityService | None = None
"""Bootstrap wiring provides dependency instances for petition submissions."""


"""Dependency instances are provided by bootstrap wiring."""


def get_queue_capacity_service() -> QueueCapacityService:
    """Get queue capacity service instance (Story 1.3, FR-1.4).

    Creates the service with proper dependencies:
    - PetitionSubmissionRepository for queue depth queries
    - PetitionQueueConfig for threshold/hysteresis settings

    Returns:
        QueueCapacityService instance.
    """
    global _queue_capacity_service
    if _queue_capacity_service is None:
        config = get_petition_queue_config()
        _queue_capacity_service = QueueCapacityService(
            repository=get_petition_submission_repository(),
            threshold=config.threshold,
            hysteresis=config.hysteresis,
            cache_ttl_seconds=config.cache_ttl_seconds,
            retry_after_seconds=config.retry_after_seconds,
        )
    return _queue_capacity_service


def get_petition_submission_service() -> PetitionSubmissionService:
    """Get petition submission service instance.

    Creates the service with proper dependencies:
    - PetitionSubmissionRepository (stub)
    - ContentHashService (Blake3)
    - RealmRegistry (stub with canonical realms)
    - HaltChecker (stub)

    Returns:
        PetitionSubmissionService instance.
    """
    global _petition_submission_service
    if _petition_submission_service is None:
        _petition_submission_service = PetitionSubmissionService(
            repository=get_petition_submission_repository(),
            hash_service=get_content_hash_service(),
            realm_registry=get_realm_registry(),
            halt_checker=get_petition_halt_checker(),
        )
    return _petition_submission_service


# Testing helper functions


def reset_petition_submission_dependencies() -> None:
    """Reset all singleton instances for testing.

    Call this in test fixtures to ensure clean state between tests.
    """
    global _petition_submission_service
    global _queue_capacity_service

    _reset_petition_submission_dependencies()
    _petition_submission_service = None
    _queue_capacity_service = None


def set_petition_submission_repository(
    repo: PetitionSubmissionRepositoryProtocol,
) -> None:
    """Set custom repository for testing.

    Args:
        repo: Custom repository implementation.
    """
    global _petition_submission_service, _queue_capacity_service
    _set_petition_submission_repository(repo)
    _petition_submission_service = None
    _queue_capacity_service = None


def set_halt_checker(checker: HaltChecker) -> None:
    """Set custom halt checker for testing.

    Args:
        checker: Custom halt checker implementation.
    """
    global _petition_submission_service
    _set_halt_checker(checker)
    _petition_submission_service = None


def set_realm_registry(registry: RealmRegistryProtocol) -> None:
    """Set custom realm registry for testing.

    Args:
        registry: Custom realm registry implementation.
    """
    global _petition_submission_service
    _set_realm_registry(registry)
    _petition_submission_service = None


def set_queue_capacity_service(service: QueueCapacityService) -> None:
    """Set custom queue capacity service for testing (Story 1.3).

    Args:
        service: Custom queue capacity service implementation.
    """
    global _queue_capacity_service
    _queue_capacity_service = service


def set_petition_queue_config(config: PetitionQueueConfig) -> None:
    """Set custom petition queue config for testing (Story 1.3, AC2).

    Args:
        config: Custom queue configuration.
    """
    global _queue_capacity_service
    _set_petition_queue_config(config)
    _queue_capacity_service = None


def set_rate_limiter(limiter: RateLimiterPort) -> None:
    """Set custom rate limiter for testing (Story 1.4).

    Args:
        limiter: Custom rate limiter implementation.
    """
    _set_rate_limiter(limiter)


def set_rate_limit_config(config: PetitionRateLimitConfig) -> None:
    """Set custom rate limit config for testing (Story 1.4, AC5).

    Args:
        config: Custom rate limit configuration.
    """
    _set_rate_limit_config(config)
