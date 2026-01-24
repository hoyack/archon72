"""Bootstrap wiring for realm health dependencies."""

from __future__ import annotations

from src.application.ports.realm_health_repository import RealmHealthRepositoryProtocol
from src.infrastructure.stubs.realm_health_repository_stub import (
    RealmHealthRepositoryStub,
)

_realm_health_repo: RealmHealthRepositoryProtocol | None = None


def get_realm_health_repository() -> RealmHealthRepositoryProtocol:
    """Get realm health repository instance."""
    global _realm_health_repo
    if _realm_health_repo is None:
        _realm_health_repo = RealmHealthRepositoryStub()
    return _realm_health_repo


def set_realm_health_repository(repo: RealmHealthRepositoryProtocol) -> None:
    """Set custom realm health repository (testing override)."""
    global _realm_health_repo
    _realm_health_repo = repo


def reset_realm_health_repository() -> None:
    """Reset realm health repository singleton."""
    global _realm_health_repo
    _realm_health_repo = None
