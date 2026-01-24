"""Bootstrap wiring for cessation dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

if TYPE_CHECKING:
    from src.application.ports.freeze_checker import FreezeCheckerProtocol


_freeze_checker: FreezeCheckerProtocol | None = None


def get_freeze_checker() -> FreezeCheckerProtocol:
    """Get the freeze checker instance.

    Returns:
        FreezeCheckerProtocol implementation.
    """
    global _freeze_checker
    if _freeze_checker is None:
        _freeze_checker = FreezeCheckerStub()
    return _freeze_checker


def set_freeze_checker(checker: FreezeCheckerProtocol) -> None:
    """Set the freeze checker instance (for production use).

    Args:
        checker: FreezeCheckerProtocol implementation.
    """
    global _freeze_checker
    _freeze_checker = checker
