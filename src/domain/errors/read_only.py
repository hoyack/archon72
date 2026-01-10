"""Read-only mode errors for Archon 72 (Story 3.5, FR20).

This module provides exception classes for read-only mode enforcement
during system halt. These errors indicate that write/provisional operations
were attempted while the system is halted.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Errors include FR reference
- CT-13: Integrity outranks availability → Writes blocked during halt

FR20 Requirements:
- Read operations succeed during halt with status header
- Write operations rejected with clear error
- Provisional operations rejected (no queueing)
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class WriteBlockedDuringHaltError(ConstitutionalViolationError):
    """Raised when write attempted during halt (FR20).

    This error is expected during halt. Do NOT retry.
    Wait for halt to be cleared via ceremony (Story 3.4).

    The error message must include "FR20: System halted - write operations blocked"
    per acceptance criteria AC2.

    Usage:
        raise WriteBlockedDuringHaltError(
            "FR20: System halted - write operations blocked. Reason: Fork detected"
        )
    """

    pass


class ProvisionalBlockedDuringHaltError(ConstitutionalViolationError):
    """Raised when provisional operation attempted during halt (FR20).

    Provisional operations cannot be queued during halt per AC3.
    System must return to operational state first.

    This includes:
    - Scheduled future writes
    - Queued operations
    - Delayed execution requests

    Usage:
        raise ProvisionalBlockedDuringHaltError(
            "FR20: System halted - provisional operations blocked"
        )
    """

    pass
