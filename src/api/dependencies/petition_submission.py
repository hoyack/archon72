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

from functools import lru_cache

from src.application.ports.content_hash_service import ContentHashServiceProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.ports.rate_limiter import RateLimiterPort
from src.application.ports.realm_registry import RealmRegistryProtocol
from src.application.services.content_hash_service import Blake3ContentHashService
from src.application.services.petition_submission_service import (
    PetitionSubmissionService,
)
from src.application.services.queue_capacity_service import QueueCapacityService
from src.application.services.rate_limit_service import RateLimitService
from src.config.petition_config import PetitionQueueConfig, PetitionRateLimitConfig
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.rate_limiter_stub import RateLimiterStub
from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub

# Singleton instances for stubs
# In production, these would be configured via environment-based factory

_petition_submission_repository: PetitionSubmissionRepositoryStub | None = None
_content_hash_service: Blake3ContentHashService | None = None
_realm_registry: RealmRegistryStub | None = None
_halt_checker: HaltCheckerStub | None = None
_petition_submission_service: PetitionSubmissionService | None = None
_queue_capacity_service: QueueCapacityService | None = None
_petition_queue_config: PetitionQueueConfig | None = None
_rate_limiter: RateLimiterStub | None = None
_rate_limit_config: PetitionRateLimitConfig | None = None


def get_petition_submission_repository() -> PetitionSubmissionRepositoryProtocol:
    """Get petition submission repository instance.

    Returns singleton PetitionSubmissionRepositoryStub for development.
    In production, this would return a Supabase-backed implementation.

    Returns:
        PetitionSubmissionRepositoryProtocol implementation.
    """
    global _petition_submission_repository
    if _petition_submission_repository is None:
        _petition_submission_repository = PetitionSubmissionRepositoryStub()
    return _petition_submission_repository


@lru_cache(maxsize=1)
def get_content_hash_service() -> ContentHashServiceProtocol:
    """Get content hash service instance.

    Returns singleton Blake3ContentHashService.
    This is the real implementation (not a stub).

    Returns:
        ContentHashServiceProtocol implementation.
    """
    return Blake3ContentHashService()


def get_realm_registry() -> RealmRegistryProtocol:
    """Get realm registry instance.

    Returns singleton RealmRegistryStub for development.
    In production, this would return RealmRegistryService with Supabase.

    Returns:
        RealmRegistryProtocol implementation.
    """
    global _realm_registry
    if _realm_registry is None:
        _realm_registry = RealmRegistryStub(populate_canonical=True)
    return _realm_registry


def get_petition_halt_checker() -> HaltChecker:
    """Get halt checker instance for petition submissions.

    Returns singleton HaltCheckerStub for development.
    In production, this would return a real halt checker with
    dual-channel support (Redis + DB flag).

    Returns:
        HaltChecker implementation.
    """
    global _halt_checker
    if _halt_checker is None:
        _halt_checker = HaltCheckerStub()
    return _halt_checker


def get_petition_queue_config() -> PetitionQueueConfig:
    """Get petition queue configuration (Story 1.3, AC2).

    Returns singleton PetitionQueueConfig loaded from environment.
    Uses defaults if environment variables not set.

    Returns:
        PetitionQueueConfig instance.
    """
    global _petition_queue_config
    if _petition_queue_config is None:
        _petition_queue_config = PetitionQueueConfig.from_environment()
    return _petition_queue_config


def get_rate_limit_config() -> PetitionRateLimitConfig:
    """Get petition rate limit configuration (Story 1.4, AC5).

    Returns singleton PetitionRateLimitConfig loaded from environment.
    Uses defaults if environment variables not set.

    Returns:
        PetitionRateLimitConfig instance.
    """
    global _rate_limit_config
    if _rate_limit_config is None:
        _rate_limit_config = PetitionRateLimitConfig.from_environment()
    return _rate_limit_config


def get_rate_limiter() -> RateLimiterPort:
    """Get rate limiter instance (Story 1.4, FR-1.5, HC-4).

    Returns singleton RateLimiterStub for development.
    In production, this would return RateLimitService with PostgresRateLimitStore.

    Constitutional Constraints:
    - FR-1.5: Enforce rate limits per submitter_id
    - HC-4: 10 petitions/user/hour (configurable)
    - D4: PostgreSQL time-bucket counters

    Returns:
        RateLimiterPort implementation.
    """
    global _rate_limiter
    if _rate_limiter is None:
        config = get_rate_limit_config()
        _rate_limiter = RateLimiterStub(
            limit=config.limit_per_hour,
            window_minutes=config.window_minutes,
        )
    return _rate_limiter


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
    global _petition_submission_repository
    global _content_hash_service
    global _realm_registry
    global _halt_checker
    global _petition_submission_service
    global _queue_capacity_service
    global _petition_queue_config
    global _rate_limiter
    global _rate_limit_config

    _petition_submission_repository = None
    _content_hash_service = None
    _realm_registry = None
    _halt_checker = None
    _petition_submission_service = None
    _queue_capacity_service = None
    _petition_queue_config = None
    _rate_limiter = None
    _rate_limit_config = None

    # Also clear lru_cache
    get_content_hash_service.cache_clear()


def set_petition_submission_repository(
    repo: PetitionSubmissionRepositoryProtocol,
) -> None:
    """Set custom repository for testing.

    Args:
        repo: Custom repository implementation.
    """
    global _petition_submission_repository, _petition_submission_service
    _petition_submission_repository = repo  # type: ignore[assignment]
    _petition_submission_service = None  # Force service recreation


def set_halt_checker(checker: HaltChecker) -> None:
    """Set custom halt checker for testing.

    Args:
        checker: Custom halt checker implementation.
    """
    global _halt_checker, _petition_submission_service
    _halt_checker = checker  # type: ignore[assignment]
    _petition_submission_service = None  # Force service recreation


def set_realm_registry(registry: RealmRegistryProtocol) -> None:
    """Set custom realm registry for testing.

    Args:
        registry: Custom realm registry implementation.
    """
    global _realm_registry, _petition_submission_service
    _realm_registry = registry  # type: ignore[assignment]
    _petition_submission_service = None  # Force service recreation


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
    global _petition_queue_config, _queue_capacity_service
    _petition_queue_config = config
    _queue_capacity_service = None  # Force service recreation


def set_rate_limiter(limiter: RateLimiterPort) -> None:
    """Set custom rate limiter for testing (Story 1.4).

    Args:
        limiter: Custom rate limiter implementation.
    """
    global _rate_limiter
    _rate_limiter = limiter  # type: ignore[assignment]


def set_rate_limit_config(config: PetitionRateLimitConfig) -> None:
    """Set custom rate limit config for testing (Story 1.4, AC5).

    Args:
        config: Custom rate limit configuration.
    """
    global _rate_limit_config, _rate_limiter
    _rate_limit_config = config
    _rate_limiter = None  # Force limiter recreation
