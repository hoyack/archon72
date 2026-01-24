"""Bootstrap wiring for status token registry dependencies."""

from __future__ import annotations

from src.application.ports.status_token_registry import StatusTokenRegistryProtocol
from src.infrastructure.stubs.status_token_registry_stub import (
    get_status_token_registry as _get_stub_registry,
)
from src.infrastructure.stubs.status_token_registry_stub import (
    reset_status_token_registry as _reset_stub_registry,
)


async def get_status_token_registry() -> StatusTokenRegistryProtocol:
    """Get status token registry singleton."""
    return await _get_stub_registry()


def reset_status_token_registry() -> None:
    """Reset status token registry singleton."""
    _reset_stub_registry()
