"""No Preview constraint errors (Story 2.1, FR9).

This module defines error types for FR9 (No Preview constraint) violations.
FR9 requires all agent outputs to be recorded before any human views them.

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- CT-11: Silent failure destroys legitimacy → Violations HALT system
- CT-13: Integrity outranks availability → Better to deny than serve modified content
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class FR9ViolationError(ConstitutionalViolationError):
    """Raised when No Preview constraint (FR9) is violated.

    FR9 violations indicate an attempt to access agent output before
    it has been recorded in the event store, or a content hash mismatch.

    This is a CRITICAL constitutional violation that must NEVER be
    silently ignored.

    Examples:
        - Attempting to view uncommitted output
        - Content hash mismatch (potential tampering)

    Usage:
        raise FR9ViolationError(
            "FR9: Output must be recorded before viewing"
        )
    """

    pass
