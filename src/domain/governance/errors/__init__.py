"""Governance error types.

This package contains domain-specific error types for the consent-based
governance system.
"""

from src.domain.governance.errors.validation_errors import (
    HashChainBreakError,
    IllegalStateTransitionError,
    UnknownActorError,
    UnknownEventTypeError,
    WriteTimeValidationError,
)

__all__ = [
    "WriteTimeValidationError",
    "IllegalStateTransitionError",
    "HashChainBreakError",
    "UnknownEventTypeError",
    "UnknownActorError",
]
