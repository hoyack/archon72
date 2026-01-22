"""Bootstrap wiring for co-sign dependencies."""

from __future__ import annotations

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

_co_sign_repository: CoSignRepositoryProtocol | None = None
_petition_repository: PetitionSubmissionRepositoryProtocol | None = None
_halt_checker: HaltChecker | None = None
_identity_store: IdentityStoreProtocol | None = None
_rate_limiter: CoSignRateLimiterProtocol | None = None
_threshold_checker: EscalationThresholdCheckerProtocol | None = None
_auto_escalation_executor: AutoEscalationExecutorProtocol | None = None


def get_co_sign_repository() -> CoSignRepositoryProtocol:
    """Get co-sign repository instance."""
    global _co_sign_repository
    if _co_sign_repository is None:
        _co_sign_repository = CoSignRepositoryStub()
    return _co_sign_repository


def get_petition_repository() -> PetitionSubmissionRepositoryProtocol:
    """Get petition repository instance."""
    global _petition_repository
    if _petition_repository is None:
        _petition_repository = PetitionSubmissionRepositoryStub()
    return _petition_repository


def get_halt_checker() -> HaltChecker:
    """Get halt checker instance for co-sign operations."""
    global _halt_checker
    if _halt_checker is None:
        _halt_checker = HaltCheckerStub()
    return _halt_checker


def get_identity_store() -> IdentityStoreProtocol:
    """Get identity store instance for co-sign operations."""
    global _identity_store
    if _identity_store is None:
        _identity_store = IdentityStoreStub()
    return _identity_store


def get_co_sign_rate_limiter() -> CoSignRateLimiterProtocol:
    """Get co-sign rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = CoSignRateLimiterStub(limit=50, window_minutes=60)
    return _rate_limiter


def get_escalation_threshold_checker() -> EscalationThresholdCheckerProtocol:
    """Get escalation threshold checker instance."""
    global _threshold_checker
    if _threshold_checker is None:
        _threshold_checker = EscalationThresholdService()
    return _threshold_checker


def get_auto_escalation_executor() -> AutoEscalationExecutorProtocol:
    """Get auto-escalation executor instance."""
    global _auto_escalation_executor
    if _auto_escalation_executor is None:
        _auto_escalation_executor = AutoEscalationExecutorStub()
    return _auto_escalation_executor


def reset_co_sign_dependencies() -> None:
    """Reset all singleton instances for testing."""
    global _co_sign_repository
    global _petition_repository
    global _halt_checker
    global _identity_store
    global _rate_limiter
    global _threshold_checker
    global _auto_escalation_executor

    _co_sign_repository = None
    _petition_repository = None
    _halt_checker = None
    _identity_store = None
    _rate_limiter = None
    _threshold_checker = None
    _auto_escalation_executor = None


def set_co_sign_repository(repo: CoSignRepositoryProtocol) -> None:
    """Set custom co-sign repository for testing."""
    global _co_sign_repository
    _co_sign_repository = repo


def set_petition_repository(repo: PetitionSubmissionRepositoryProtocol) -> None:
    """Set custom petition repository for testing."""
    global _petition_repository
    _petition_repository = repo


def set_halt_checker(checker: HaltChecker) -> None:
    """Set custom halt checker for testing."""
    global _halt_checker
    _halt_checker = checker


def set_identity_store(store: IdentityStoreProtocol) -> None:
    """Set custom identity store for testing."""
    global _identity_store
    _identity_store = store


def set_co_sign_rate_limiter(limiter: CoSignRateLimiterProtocol) -> None:
    """Set custom rate limiter for testing."""
    global _rate_limiter
    _rate_limiter = limiter


def set_escalation_threshold_checker(
    checker: EscalationThresholdCheckerProtocol,
) -> None:
    """Set custom threshold checker for testing."""
    global _threshold_checker
    _threshold_checker = checker


def set_auto_escalation_executor(
    executor: AutoEscalationExecutorProtocol,
) -> None:
    """Set custom auto-escalation executor for testing."""
    global _auto_escalation_executor
    _auto_escalation_executor = executor
