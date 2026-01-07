"""Recovery domain errors for Archon 72 (Story 3.6, FR21).

This module provides exception classes for recovery waiting period failures.
These are constitutional violations that enforce the 48-hour waiting period.

Constitutional Truths Honored:
- FR21: Mandatory 48-hour waiting period with public notification
- NFR41: Minimum 48 hours (constitutional floor)
- CT-11: Silent failure destroys legitimacy → Errors include FR reference
- CT-13: Integrity outranks availability → Time is constitutional

FR21 Requirements:
- Recovery timer starts on initiation
- Early recovery attempts rejected with remaining time
- Recovery allowed only after 48 hours elapsed
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class RecoveryWaitingPeriodNotElapsedError(ConstitutionalViolationError):
    """Raised when recovery attempted before 48 hours elapsed (FR21).

    The error message includes remaining time to help Keepers
    understand when recovery will be possible.

    Constitutional Constraint (FR21, NFR41):
    The 48-hour waiting period is a constitutional floor that
    cannot be reduced. Early recovery attempts MUST fail loudly.

    Usage:
        remaining = timedelta(hours=23, minutes=45)
        raise RecoveryWaitingPeriodNotElapsedError(
            f"FR21: 48-hour waiting period not elapsed. Remaining: {remaining}"
        )
    """

    pass


class RecoveryWaitingPeriodNotStartedError(ConstitutionalViolationError):
    """Raised when completing recovery without active waiting period.

    Recovery must go through the full process: initiate -> wait 48h -> complete.
    Attempting to complete without starting is a constitutional violation.

    Constitutional Constraint (FR21):
    The waiting period is mandatory. Cannot skip directly to completion.

    Usage:
        raise RecoveryWaitingPeriodNotStartedError(
            "No recovery waiting period active"
        )
    """

    pass


class RecoveryAlreadyInProgressError(ConstitutionalViolationError):
    """Raised when initiating recovery while one is already active.

    Only one recovery process can be active at a time.
    Multiple concurrent recoveries would create constitutional ambiguity.

    Usage:
        raise RecoveryAlreadyInProgressError(
            f"Recovery already in progress, ends at {existing.ends_at}"
        )
    """

    pass


class RecoveryNotPermittedError(ConstitutionalViolationError):
    """Raised when attempting recovery operations on non-halted system.

    Recovery is only meaningful when system is in halted state.
    Cannot recover from a state that doesn't need recovery.

    Constitutional Constraint (FR17):
    Recovery requires prior halt. Operating normally means no recovery needed.

    Usage:
        raise RecoveryNotPermittedError(
            "Cannot initiate recovery - system not halted"
        )
    """

    pass
