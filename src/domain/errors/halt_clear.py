"""Halt clear errors for Archon 72 (Story 3.4, ADR-3).

This module provides exception classes for halt clearing failures.
These are constitutional violations that enforce sticky halt semantics.

Constitutional Truths Honored:
- ADR-3: Halt is sticky - clearing requires witnessed ceremony
- ADR-6: Tier 1 ceremony requires 2 Keepers
- CT-11: Silent failure destroys legitimacy → FAIL LOUD
- CT-12: Witnessing creates accountability
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class HaltClearDeniedError(ConstitutionalViolationError):
    """Raised when halt clear is attempted without proper ceremony.

    Constitutional Constraint (ADR-3):
    Halt is sticky once set. Clearing requires a witnessed ceremony
    with proper approvals. Unauthorized clear attempts MUST fail loudly.

    Usage:
        raise HaltClearDeniedError("ADR-3: Halt flag protected - ceremony required")
    """

    pass


class InvalidCeremonyError(ConstitutionalViolationError):
    """Raised when ceremony evidence is invalid or malformed.

    Constitutional Constraint (ADR-6):
    Ceremony evidence must be valid with proper signatures.
    Invalid ceremonies MUST be rejected immediately.

    Usage:
        raise InvalidCeremonyError("Invalid signature from keeper-001")
    """

    pass


class InsufficientApproversError(ConstitutionalViolationError):
    """Raised when halt clear ceremony has fewer than 2 approvers.

    Constitutional Constraint (ADR-6 Tier 1):
    Halt clearing requires at least 2 Keeper approvers.
    Insufficient quorum MUST be rejected immediately.

    Usage:
        raise InsufficientApproversError(
            "ADR-6: Halt clear requires 2 Keepers, got 1"
        )
    """

    pass
