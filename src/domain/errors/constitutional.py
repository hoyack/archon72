"""Constitutional violation errors for Archon 72.

This module provides exception classes for constitutional constraint violations.
Constitutional violations are NEVER silently ignored - they represent fundamental
breaches of system integrity.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → Unwitnessed actions are invalid
- CT-13: Integrity outranks availability → Availability may be sacrificed
"""

from src.domain.exceptions import ConclaveError


class ConstitutionalViolationError(ConclaveError):
    """Raised when a constitutional constraint is violated.

    Constitutional violations are NEVER silently ignored.
    They represent fundamental breaches of system integrity.

    Error messages MUST include the FR reference (e.g., "FR80: ...").

    Examples:
        - FR80 violation: Attempt to delete a constitutional entity
        - FR81 violation: Partial state persisted (atomicity broken)

    Usage:
        raise ConstitutionalViolationError(
            "FR80: Deletion prohibited - constitutional entities are immutable"
        )
    """

    pass
