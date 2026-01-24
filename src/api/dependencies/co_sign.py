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
from src.bootstrap.co_sign import (
    get_auto_escalation_executor,
    get_co_sign_rate_limiter,
    get_co_sign_repository,
    get_escalation_threshold_checker,
    get_halt_checker,
    get_identity_store,
    get_petition_repository,
)
from src.bootstrap.co_sign import (
    reset_co_sign_dependencies as _reset_co_sign_dependencies,
)
from src.bootstrap.co_sign import (
    set_auto_escalation_executor as _set_auto_escalation_executor,
)
from src.bootstrap.co_sign import (
    set_co_sign_rate_limiter as _set_co_sign_rate_limiter,
)
from src.bootstrap.co_sign import (
    set_co_sign_repository as _set_co_sign_repository,
)
from src.bootstrap.co_sign import (
    set_escalation_threshold_checker as _set_escalation_threshold_checker,
)
from src.bootstrap.co_sign import (
    set_halt_checker as _set_halt_checker,
)
from src.bootstrap.co_sign import (
    set_identity_store as _set_identity_store,
)
from src.bootstrap.co_sign import (
    set_petition_repository as _set_petition_repository,
)

_co_sign_submission_service: CoSignSubmissionService | None = None
_co_sign_count_verification_service: CoSignCountVerificationService | None = None


"""Bootstrap wiring provides dependency instances for co-sign operations."""


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
    global _co_sign_submission_service
    global _co_sign_count_verification_service

    _reset_co_sign_dependencies()
    _co_sign_submission_service = None
    _co_sign_count_verification_service = None


def set_co_sign_repository(repo: CoSignRepositoryProtocol) -> None:
    """Set custom co-sign repository for testing."""
    global _co_sign_submission_service
    _set_co_sign_repository(repo)
    _co_sign_submission_service = None


def set_petition_repository(repo: PetitionSubmissionRepositoryProtocol) -> None:
    """Set custom petition repository for testing."""
    global _co_sign_submission_service
    _set_petition_repository(repo)
    _co_sign_submission_service = None


def set_halt_checker(checker: HaltChecker) -> None:
    """Set custom halt checker for testing."""
    global _co_sign_submission_service
    _set_halt_checker(checker)
    _co_sign_submission_service = None


def set_identity_store(store: IdentityStoreProtocol) -> None:
    """Set custom identity store for testing (NFR-5.2)."""
    global _co_sign_submission_service
    _set_identity_store(store)
    _co_sign_submission_service = None


def set_co_sign_rate_limiter(limiter: CoSignRateLimiterProtocol) -> None:
    """Set custom rate limiter for testing (FR-6.6, SYBIL-1)."""
    global _co_sign_submission_service
    _set_co_sign_rate_limiter(limiter)
    _co_sign_submission_service = None


def set_escalation_threshold_checker(
    checker: EscalationThresholdCheckerProtocol,
) -> None:
    """Set custom threshold checker for testing (FR-6.5, Story 5.5)."""
    global _co_sign_submission_service
    _set_escalation_threshold_checker(checker)
    _co_sign_submission_service = None


def set_auto_escalation_executor(
    executor: AutoEscalationExecutorProtocol,
) -> None:
    """Set custom auto-escalation executor for testing (FR-5.1, FR-5.3)."""
    global _co_sign_submission_service
    _set_auto_escalation_executor(executor)
    _co_sign_submission_service = None


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
