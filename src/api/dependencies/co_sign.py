"""Co-Sign API dependencies (Story 5.2, Story 5.3, Story 5.4, Story 5.5, Story 5.6, FR-6.1, FR-6.5, FR-6.6).

Dependency injection setup for co-sign submission components.
Provides stub implementations for development and testing.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.2: Escalation thresholds: CESSATION=100, GRIEVANCE=50
- FR-5.3: System SHALL emit EscalationTriggered event with co-signer_count [P0]
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.2: System SHALL reject duplicate co-signature (NFR-3.5)
- FR-6.3: System SHALL reject co-sign after fate assignment
- FR-6.4: System SHALL increment co-signer count atomically
- FR-6.5: System SHALL check escalation threshold on each co-sign
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- CON-5: CESSATION auto-escalation threshold is immutable (100)
- NFR-5.1: Rate limiting per identity: Configurable per type
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability - all escalation events witnessed
- CT-13: Halt rejects writes, allows reads
- CT-14: Silence must be expensive - auto-escalation ensures King attention
- SYBIL-1: Identity verification + rate limiting per verified identity

Note: These are stub implementations. Production would use:
- Supabase-backed CoSignRepository
- Supabase-backed PetitionSubmissionRepository
- Real HaltChecker with dual-channel support
- Real IdentityStore with OAuth/SSO integration
- PostgreSQL time-bucket rate limiter (D4)
- Real AutoEscalationExecutorService with event witnessing
"""

from src.application.ports.auto_escalation_executor import (
    AutoEscalationExecutorProtocol,
)
from src.application.ports.co_sign_rate_limiter import CoSignRateLimiterProtocol
from src.application.ports.co_sign_submission import CoSignRepositoryProtocol
from src.application.ports.escalation_threshold import (
    EscalationThresholdCheckerProtocol,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.identity_verification import IdentityStoreProtocol
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.services.co_sign_count_verification_service import (
    CoSignCountVerificationService,
)
from src.application.services.co_sign_submission_service import (
    CoSignSubmissionService,
)
from src.application.services.escalation_threshold_service import (
    EscalationThresholdService,
)
from src.infrastructure.stubs.auto_escalation_executor_stub import (
    AutoEscalationExecutorStub,
)
from src.infrastructure.stubs.co_sign_rate_limiter_stub import CoSignRateLimiterStub
from src.infrastructure.stubs.co_sign_repository_stub import CoSignRepositoryStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.identity_store_stub import IdentityStoreStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)

# Singleton instances for stubs
# In production, these would be configured via environment-based factory

_co_sign_repository: CoSignRepositoryProtocol | None = None
_petition_repository: PetitionSubmissionRepositoryProtocol | None = None
_halt_checker: HaltChecker | None = None
_identity_store: IdentityStoreProtocol | None = None
_rate_limiter: CoSignRateLimiterProtocol | None = None
_threshold_checker: EscalationThresholdCheckerProtocol | None = None
_auto_escalation_executor: AutoEscalationExecutorProtocol | None = None
_co_sign_submission_service: CoSignSubmissionService | None = None
_co_sign_count_verification_service: CoSignCountVerificationService | None = None


def get_co_sign_repository() -> CoSignRepositoryProtocol:
    """Get co-sign repository instance.

    Returns singleton CoSignRepositoryStub for development.
    In production, this would return a Supabase-backed implementation.

    Returns:
        CoSignRepositoryProtocol implementation.
    """
    global _co_sign_repository
    if _co_sign_repository is None:
        _co_sign_repository = CoSignRepositoryStub()
    return _co_sign_repository


def get_petition_repository() -> PetitionSubmissionRepositoryProtocol:
    """Get petition repository instance.

    Returns singleton PetitionSubmissionRepositoryStub for development.
    In production, this would return a Supabase-backed implementation.

    Returns:
        PetitionSubmissionRepositoryProtocol implementation.
    """
    global _petition_repository
    if _petition_repository is None:
        _petition_repository = PetitionSubmissionRepositoryStub()
    return _petition_repository


def get_halt_checker() -> HaltChecker:
    """Get halt checker instance for co-sign operations.

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


def get_identity_store() -> IdentityStoreProtocol:
    """Get identity store instance for co-sign operations (NFR-5.2, LEGIT-1).

    Returns singleton IdentityStoreStub for development.
    In production, this would return a real identity store with
    OAuth/SSO integration.

    Returns:
        IdentityStoreProtocol implementation.
    """
    global _identity_store
    if _identity_store is None:
        _identity_store = IdentityStoreStub()
    return _identity_store


def get_co_sign_rate_limiter() -> CoSignRateLimiterProtocol:
    """Get co-sign rate limiter instance (FR-6.6, SYBIL-1).

    Returns singleton CoSignRateLimiterStub for development.
    In production, this would return a PostgreSQL time-bucket
    implementation per architecture decision D4.

    Configuration via environment variables:
    - CO_SIGN_RATE_LIMIT: Default 50 co-signs per window
    - CO_SIGN_RATE_WINDOW_MINUTES: Default 60 minute window

    Returns:
        CoSignRateLimiterProtocol implementation.
    """
    global _rate_limiter
    if _rate_limiter is None:
        # In production, read from environment:
        # limit = int(os.getenv("CO_SIGN_RATE_LIMIT", "50"))
        # window = int(os.getenv("CO_SIGN_RATE_WINDOW_MINUTES", "60"))
        _rate_limiter = CoSignRateLimiterStub(limit=50, window_minutes=60)
    return _rate_limiter


def get_escalation_threshold_checker() -> EscalationThresholdCheckerProtocol:
    """Get escalation threshold checker instance (FR-5.2, FR-6.5, Story 5.5).

    Returns singleton EscalationThresholdService for threshold checking.
    The service is a pure calculation service that compares co-signer
    counts against configured thresholds.

    Thresholds (FR-5.2, CON-5):
    - CESSATION: 100 co-signers (immutable per CON-5)
    - GRIEVANCE: 50 co-signers
    - GENERAL: No threshold (None)
    - COLLABORATION: No threshold (None)

    Configuration via environment variables:
    - ESCALATION_THRESHOLD_CESSATION: Default 100 (CON-5 immutable)
    - ESCALATION_THRESHOLD_GRIEVANCE: Default 50

    Returns:
        EscalationThresholdCheckerProtocol implementation.
    """
    global _threshold_checker
    if _threshold_checker is None:
        # In production, could read from environment but CON-5 makes
        # CESSATION threshold immutable at 100:
        # cessation = int(os.getenv("ESCALATION_THRESHOLD_CESSATION", "100"))
        # grievance = int(os.getenv("ESCALATION_THRESHOLD_GRIEVANCE", "50"))
        _threshold_checker = EscalationThresholdService()
    return _threshold_checker


def get_auto_escalation_executor() -> AutoEscalationExecutorProtocol:
    """Get auto-escalation executor instance (FR-5.1, FR-5.3, Story 5.6).

    Returns singleton AutoEscalationExecutorStub for development.
    In production, this would return an AutoEscalationExecutorService
    with real petition repository and event witnessing.

    The executor handles:
    - Atomic state transition (RECEIVED → ESCALATED)
    - EscalationTriggered event emission (FR-5.3)
    - Idempotency (already escalated detection)
    - Witnessing via CT-12 compliance

    Constitutional Constraints:
    - FR-5.1: System SHALL ESCALATE petition when threshold reached
    - FR-5.3: System SHALL emit EscalationTriggered event
    - CT-12: Witnessing creates accountability
    - CT-14: Silence must be expensive

    Returns:
        AutoEscalationExecutorProtocol implementation.
    """
    global _auto_escalation_executor
    if _auto_escalation_executor is None:
        _auto_escalation_executor = AutoEscalationExecutorStub()
    return _auto_escalation_executor


def get_co_sign_submission_service() -> CoSignSubmissionService:
    """Get co-sign submission service instance.

    Creates the service with proper dependencies:
    - CoSignRepository (stub)
    - PetitionSubmissionRepository (stub)
    - HaltChecker (stub)
    - IdentityStore (stub) - for NFR-5.2 identity verification
    - RateLimiter (stub) - for FR-6.6 SYBIL-1 rate limiting
    - ThresholdChecker - for FR-6.5 escalation threshold checking
    - AutoEscalationExecutor (stub) - for FR-5.1 auto-escalation (Story 5.6)

    Returns:
        CoSignSubmissionService instance.
    """
    global _co_sign_submission_service
    if _co_sign_submission_service is None:
        _co_sign_submission_service = CoSignSubmissionService(
            co_sign_repo=get_co_sign_repository(),
            petition_repo=get_petition_repository(),
            halt_checker=get_halt_checker(),
            identity_store=get_identity_store(),
            rate_limiter=get_co_sign_rate_limiter(),
            threshold_checker=get_escalation_threshold_checker(),
            auto_escalation_executor=get_auto_escalation_executor(),
        )
    return _co_sign_submission_service


# Testing helper functions


def reset_co_sign_dependencies() -> None:
    """Reset all singleton instances for testing.

    Call this in test fixtures to ensure clean state between tests.
    """
    global _co_sign_repository
    global _petition_repository
    global _halt_checker
    global _identity_store
    global _rate_limiter
    global _threshold_checker
    global _auto_escalation_executor
    global _co_sign_submission_service
    global _co_sign_count_verification_service

    _co_sign_repository = None
    _petition_repository = None
    _halt_checker = None
    _identity_store = None
    _rate_limiter = None
    _threshold_checker = None
    _auto_escalation_executor = None
    _co_sign_submission_service = None
    _co_sign_count_verification_service = None


def set_co_sign_repository(repo: CoSignRepositoryProtocol) -> None:
    """Set custom co-sign repository for testing.

    Args:
        repo: Custom repository implementation.
    """
    global _co_sign_repository, _co_sign_submission_service
    _co_sign_repository = repo
    _co_sign_submission_service = None  # Force service recreation


def set_petition_repository(repo: PetitionSubmissionRepositoryProtocol) -> None:
    """Set custom petition repository for testing.

    Args:
        repo: Custom repository implementation.
    """
    global _petition_repository, _co_sign_submission_service
    _petition_repository = repo
    _co_sign_submission_service = None  # Force service recreation


def set_halt_checker(checker: HaltChecker) -> None:
    """Set custom halt checker for testing.

    Args:
        checker: Custom halt checker implementation.
    """
    global _halt_checker, _co_sign_submission_service
    _halt_checker = checker
    _co_sign_submission_service = None  # Force service recreation


def set_identity_store(store: IdentityStoreProtocol) -> None:
    """Set custom identity store for testing (NFR-5.2).

    Args:
        store: Custom identity store implementation.
    """
    global _identity_store, _co_sign_submission_service
    _identity_store = store
    _co_sign_submission_service = None  # Force service recreation


def set_co_sign_rate_limiter(limiter: CoSignRateLimiterProtocol) -> None:
    """Set custom rate limiter for testing (FR-6.6, SYBIL-1).

    Args:
        limiter: Custom rate limiter implementation.
    """
    global _rate_limiter, _co_sign_submission_service
    _rate_limiter = limiter
    _co_sign_submission_service = None  # Force service recreation


def set_escalation_threshold_checker(
    checker: EscalationThresholdCheckerProtocol,
) -> None:
    """Set custom threshold checker for testing (FR-6.5, Story 5.5).

    Args:
        checker: Custom threshold checker implementation.
    """
    global _threshold_checker, _co_sign_submission_service
    _threshold_checker = checker
    _co_sign_submission_service = None  # Force service recreation


def set_auto_escalation_executor(
    executor: AutoEscalationExecutorProtocol,
) -> None:
    """Set custom auto-escalation executor for testing (FR-5.1, FR-5.3, Story 5.6).

    Args:
        executor: Custom executor implementation.
    """
    global _auto_escalation_executor, _co_sign_submission_service
    _auto_escalation_executor = executor
    _co_sign_submission_service = None  # Force service recreation


def set_co_sign_submission_service(service: CoSignSubmissionService) -> None:
    """Set custom co-sign submission service for testing.

    Args:
        service: Custom service implementation.
    """
    global _co_sign_submission_service
    _co_sign_submission_service = service


def get_co_sign_count_verification_service() -> CoSignCountVerificationService | None:
    """Get co-sign count verification service instance (Story 5.8, AC5).

    Returns the verification service if a database session factory is available.
    For stub-based testing, this returns None and the endpoint should handle gracefully.

    Note: This service requires a real database session factory to work.
    In development/testing without database, returns None.

    Returns:
        CoSignCountVerificationService instance or None if no DB available.
    """
    global _co_sign_count_verification_service
    # For now, return None as we need database session factory
    # In production, this would be initialized with the session factory
    return _co_sign_count_verification_service


def set_co_sign_count_verification_service(
    service: CoSignCountVerificationService | None,
) -> None:
    """Set custom count verification service for testing (Story 5.8, AC5).

    Args:
        service: Custom verification service implementation or None.
    """
    global _co_sign_count_verification_service
    _co_sign_count_verification_service = service
