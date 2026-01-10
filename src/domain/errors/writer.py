"""Writer-specific errors for Archon 72 (Story 1.6).

This module provides exception classes for Event Writer Service failures.
These are constitutional violations that indicate critical system issues.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-13: Integrity outranks availability → Availability may be sacrificed

ADR-1 References:
- Single canonical writer constraint
- Writer self-verification (GAP-CHAOS-001)
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class SystemHaltedError(ConstitutionalViolationError):
    """Raised when write is attempted while system is halted.

    Constitutional Constraint (CT-11):
    Halt is integrity protection, not transient failure.
    NEVER retry after SystemHaltedError.

    Usage:
        raise SystemHaltedError("System is halted: Integrity breach detected")
    """

    pass


class WriterInconsistencyError(ConstitutionalViolationError):
    """Raised when Writer detects head hash mismatch with DB (GAP-CHAOS-001).

    This is a CRITICAL error indicating possible data corruption
    or split-brain scenario. System must halt immediately.

    This error should NEVER be caught and retried - it indicates
    fundamental integrity issues requiring human intervention.

    Usage:
        raise WriterInconsistencyError(
            f"ADR-1: Head hash mismatch - local={local_hash}, db={db_hash}"
        )
    """

    pass


class WriterLockNotHeldError(ConstitutionalViolationError):
    """Raised when write is attempted without holding writer lock (ADR-1).

    Single-writer constraint violated. Indicates either:
    - Programming error (forgot to acquire lock)
    - Lock expiration without renewal
    - Lock stolen by another instance

    Usage:
        raise WriterLockNotHeldError("ADR-1: Writer lock not held - cannot write")
    """

    pass


class WriterNotVerifiedError(ConstitutionalViolationError):
    """Raised when write is attempted before startup verification.

    GAP-CHAOS-001 requires writer self-verification on startup.
    Writes must not be accepted until verification passes.

    Usage:
        raise WriterNotVerifiedError(
            "GAP-CHAOS-001: Writer not verified - call verify_startup() first"
        )
    """

    pass
