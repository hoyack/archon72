"""Bootstrap wiring for petition submission dependencies."""

from __future__ import annotations

import os

from structlog import get_logger

from src.application.ports.content_hash_service import ContentHashServiceProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.petition_event_emitter import PetitionEventEmitterPort
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.ports.rate_limiter import RateLimiterPort
from src.application.ports.realm_registry import RealmRegistryProtocol
from src.application.services.content_hash_service import Blake3ContentHashService
from src.config.petition_config import PetitionQueueConfig, PetitionRateLimitConfig
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.petition_event_emitter_stub import (
    PetitionEventEmitterStub,
)
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.rate_limiter_stub import RateLimiterStub
from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub

logger = get_logger()

_petition_submission_repository: PetitionSubmissionRepositoryProtocol | None = None
_content_hash_service: ContentHashServiceProtocol | None = None
_realm_registry: RealmRegistryProtocol | None = None
_halt_checker: HaltChecker | None = None
_petition_queue_config: PetitionQueueConfig | None = None
_rate_limiter: RateLimiterPort | None = None
_rate_limit_config: PetitionRateLimitConfig | None = None
_event_emitter: PetitionEventEmitterPort | None = None


def get_petition_submission_repository() -> PetitionSubmissionRepositoryProtocol:
    """Get petition submission repository instance.

    Returns PostgreSQL repository if DATABASE_URL is configured,
    otherwise falls back to in-memory stub for testing.

    Constitutional Compliance:
    - FR-2.4: PostgreSQL repository uses atomic CAS for fate assignment
    - NFR-3.2: Database-level atomic fate assignment guarantee
    - CT-11: Repository selection logged for audit trail
    """
    global _petition_submission_repository
    if _petition_submission_repository is None:
        # Check if DATABASE_URL is configured for PostgreSQL
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            try:
                from src.bootstrap.database import get_session_factory
                from src.infrastructure.adapters.persistence.petition_submission_repository import (
                    PostgresPetitionSubmissionRepository,
                )

                session_factory = get_session_factory()
                _petition_submission_repository = PostgresPetitionSubmissionRepository(
                    session_factory=session_factory
                )
                logger.info(
                    "petition_repository_initialized",
                    repository_type="PostgreSQL",
                    message="Using PostgreSQL repository for petition persistence",
                )
            except Exception as e:
                logger.error(
                    "postgres_repository_init_failed",
                    error=str(e),
                    message="Falling back to in-memory stub",
                )
                _petition_submission_repository = PetitionSubmissionRepositoryStub()
        else:
            logger.warning(
                "petition_repository_initialized",
                repository_type="InMemoryStub",
                message="DATABASE_URL not set - using in-memory stub (data will not persist)",
            )
            _petition_submission_repository = PetitionSubmissionRepositoryStub()
    return _petition_submission_repository


def get_content_hash_service() -> ContentHashServiceProtocol:
    """Get content hash service instance."""
    global _content_hash_service
    if _content_hash_service is None:
        _content_hash_service = Blake3ContentHashService()
    return _content_hash_service


def get_realm_registry() -> RealmRegistryProtocol:
    """Get realm registry instance."""
    global _realm_registry
    if _realm_registry is None:
        _realm_registry = RealmRegistryStub(populate_canonical=True)
    return _realm_registry


def get_petition_halt_checker() -> HaltChecker:
    """Get halt checker instance for petition submissions."""
    global _halt_checker
    if _halt_checker is None:
        _halt_checker = HaltCheckerStub()
    return _halt_checker


def get_petition_queue_config() -> PetitionQueueConfig:
    """Get petition queue configuration."""
    global _petition_queue_config
    if _petition_queue_config is None:
        _petition_queue_config = PetitionQueueConfig.from_environment()
    return _petition_queue_config


def get_rate_limit_config() -> PetitionRateLimitConfig:
    """Get petition rate limit configuration."""
    global _rate_limit_config
    if _rate_limit_config is None:
        _rate_limit_config = PetitionRateLimitConfig.from_environment()
    return _rate_limit_config


def get_rate_limiter() -> RateLimiterPort:
    """Get rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        config = get_rate_limit_config()
        _rate_limiter = RateLimiterStub(
            limit=config.limit_per_hour,
            window_minutes=config.window_minutes,
        )
    return _rate_limiter


def reset_petition_submission_dependencies() -> None:
    """Reset petition submission dependency singletons."""
    global _petition_submission_repository
    global _content_hash_service
    global _realm_registry
    global _halt_checker
    global _petition_queue_config
    global _rate_limiter
    global _rate_limit_config
    global _event_emitter

    _petition_submission_repository = None
    _content_hash_service = None
    _realm_registry = None
    _halt_checker = None
    _petition_queue_config = None
    _rate_limiter = None
    _rate_limit_config = None
    _event_emitter = None


def set_petition_submission_repository(
    repo: PetitionSubmissionRepositoryProtocol,
) -> None:
    """Set custom petition repository for testing."""
    global _petition_submission_repository
    _petition_submission_repository = repo


def set_halt_checker(checker: HaltChecker) -> None:
    """Set custom halt checker for testing."""
    global _halt_checker
    _halt_checker = checker


def set_realm_registry(registry: RealmRegistryProtocol) -> None:
    """Set custom realm registry for testing."""
    global _realm_registry
    _realm_registry = registry


def set_petition_queue_config(config: PetitionQueueConfig) -> None:
    """Set custom petition queue config for testing."""
    global _petition_queue_config
    _petition_queue_config = config


def set_rate_limiter(limiter: RateLimiterPort) -> None:
    """Set custom rate limiter for testing."""
    global _rate_limiter
    _rate_limiter = limiter


def set_rate_limit_config(config: PetitionRateLimitConfig) -> None:
    """Set custom rate limit config for testing."""
    global _rate_limit_config
    _rate_limit_config = config


def get_event_emitter() -> PetitionEventEmitterPort:
    """Get event emitter instance for petition lifecycle events."""
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = PetitionEventEmitterStub()
    return _event_emitter


def set_event_emitter(emitter: PetitionEventEmitterPort) -> None:
    """Set custom event emitter for testing."""
    global _event_emitter
    _event_emitter = emitter
