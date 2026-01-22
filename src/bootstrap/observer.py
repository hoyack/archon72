"""Bootstrap wiring for observer dependencies."""

from __future__ import annotations

from src.application.ports.checkpoint_repository import CheckpointRepository
from src.application.ports.final_deliberation_recorder import FinalDeliberationRecorder
from src.application.ports.halt_checker import HaltChecker
from src.application.services.integrity_case_service import IntegrityCaseService
from src.infrastructure.stubs.checkpoint_repository_stub import CheckpointRepositoryStub
from src.infrastructure.stubs.final_deliberation_recorder_stub import (
    FinalDeliberationRecorderStub,
)
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.integrity_case_repository_stub import (
    IntegrityCaseRepositoryStub,
)

_freeze_checker: FreezeCheckerStub | None = None
_halt_checker: HaltChecker | None = None
_checkpoint_repo: CheckpointRepository | None = None
_deliberation_recorder: FinalDeliberationRecorder | None = None
_integrity_case_service: IntegrityCaseService | None = None


def get_freeze_checker() -> FreezeCheckerStub:
    """Get freeze checker instance for observer service."""
    global _freeze_checker
    if _freeze_checker is None:
        _freeze_checker = FreezeCheckerStub()
    return _freeze_checker


def get_halt_checker() -> HaltChecker:
    """Get halt checker instance for observer service."""
    global _halt_checker
    if _halt_checker is None:
        _halt_checker = HaltCheckerStub()
    return _halt_checker


def get_checkpoint_repo() -> CheckpointRepository:
    """Get checkpoint repository instance."""
    global _checkpoint_repo
    if _checkpoint_repo is None:
        _checkpoint_repo = CheckpointRepositoryStub()
    return _checkpoint_repo


def get_deliberation_recorder() -> FinalDeliberationRecorder:
    """Get deliberation recorder instance (singleton)."""
    global _deliberation_recorder
    if _deliberation_recorder is None:
        _deliberation_recorder = FinalDeliberationRecorderStub()
    return _deliberation_recorder


def get_integrity_case_service() -> IntegrityCaseService:
    """Get integrity case service instance (singleton)."""
    global _integrity_case_service
    if _integrity_case_service is None:
        repository = IntegrityCaseRepositoryStub()
        _integrity_case_service = IntegrityCaseService(repository=repository)
    return _integrity_case_service
