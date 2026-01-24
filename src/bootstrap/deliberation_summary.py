"""Bootstrap wiring for deliberation summary dependencies."""

from __future__ import annotations

from src.application.ports.deliberation_summary import (
    DeliberationSummaryRepositoryProtocol,
)
from src.infrastructure.stubs.deliberation_summary_repository_stub import (
    DeliberationSummaryRepositoryStub,
)

_deliberation_summary_repo: DeliberationSummaryRepositoryProtocol | None = None


def get_deliberation_summary_repository() -> DeliberationSummaryRepositoryProtocol:
    """Get deliberation summary repository instance."""
    global _deliberation_summary_repo
    if _deliberation_summary_repo is None:
        _deliberation_summary_repo = DeliberationSummaryRepositoryStub()
    return _deliberation_summary_repo


def set_deliberation_summary_repository(
    repo: DeliberationSummaryRepositoryProtocol,
) -> None:
    """Set custom deliberation summary repository (testing override)."""
    global _deliberation_summary_repo
    _deliberation_summary_repo = repo


def reset_deliberation_summary_repository() -> None:
    """Reset deliberation summary repository singleton."""
    global _deliberation_summary_repo
    _deliberation_summary_repo = None
