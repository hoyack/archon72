"""Permission enforcement adapters.

This module provides concrete implementations of the PermissionEnforcerProtocol
for validating rank-based permissions in the governance system.
"""

from src.infrastructure.adapters.permissions.permission_enforcer_adapter import (
    PermissionEnforcerAdapter,
    create_permission_enforcer,
)

__all__ = [
    "PermissionEnforcerAdapter",
    "create_permission_enforcer",
]
