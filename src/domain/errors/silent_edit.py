"""No Silent Edits constraint errors (Story 2.5, FR13).

This module defines error types for FR13 (No Silent Edits constraint) violations.
FR13 requires that published hash always equals the canonical hash stored in
the event store, preventing post-recording content modification.

Constitutional Constraints:
- FR13: Published hash must equal canonical hash
- CT-11: Silent failure destroys legitimacy → Violations HALT system
- CT-13: Integrity outranks availability → Block publish on mismatch
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class FR13ViolationError(ConstitutionalViolationError):
    """Raised when No Silent Edits constraint (FR13) is violated.

    FR13 violations indicate an attempt to publish content that differs
    from the originally recorded content (hash mismatch). This represents
    a potential tampering attempt or data corruption.

    This is a CRITICAL constitutional violation that must NEVER be
    silently ignored. Silent edits would undermine observer trust
    and system integrity.

    Examples:
        - Publishing content with hash different from stored hash
        - Attempting to serve modified content to external systems

    Usage:
        raise FR13ViolationError(
            "FR13: Silent edit detected - hash mismatch"
        )
    """

    pass
