"""Pre-operational verification errors (Story 8.5, FR146, NFR35).

Domain errors for pre-operational verification failures.

Constitutional Constraints:
- FR146: Startup SHALL execute verification checklist. Blocked until pass.
- NFR35: System startup SHALL complete verification checklist before operation.
- CT-13: Integrity outranks availability - startup failure preferable to unverified state.

Usage:
    from src.domain.errors.pre_operational import (
        PreOperationalVerificationError,
        VerificationCheckError,
        BypassNotAllowedError,
    )

    # Raise on verification failure
    if result.status == VerificationStatus.FAILED:
        raise PreOperationalVerificationError(
            failed_checks=result.failed_checks,
            result=result,
        )
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.verification_result import (
        VerificationCheck,
        VerificationResult,
    )


class PreOperationalVerificationError(Exception):
    """Raised when pre-operational verification fails.

    Constitutional Constraint (FR146):
    Startup is blocked if verification fails. This error should
    be raised during application startup to prevent the system
    from entering ready state.

    Constitutional Constraint (CT-13):
    This error represents an integrity protection mechanism.
    The system MUST NOT start if this error is raised.

    Attributes:
        failed_checks: Tuple of failed verification checks.
        result: The complete verification result.
        message: Human-readable error message.
    """

    def __init__(
        self,
        failed_checks: tuple["VerificationCheck", ...],
        result: "VerificationResult",
        message: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            failed_checks: The checks that failed.
            result: The complete verification result.
            message: Optional custom message.
        """
        self.failed_checks = failed_checks
        self.result = result

        if message is None:
            check_names = [c.name for c in failed_checks]
            message = (
                f"Pre-operational verification failed: {len(failed_checks)} check(s) failed "
                f"[{', '.join(check_names)}]. System cannot start. "
                f"FR146/NFR35: Startup blocked until verification passes."
            )

        self.message = message
        super().__init__(self.message)

    def get_remediation_hints(self) -> list[str]:
        """Get remediation hints for each failed check.

        Returns:
            List of human-readable remediation suggestions.
        """
        hints = []
        for check in self.failed_checks:
            if check.name == "hash_chain":
                hints.append(
                    "Hash chain verification failed. Check event store integrity. "
                    "This may indicate data corruption or tampering."
                )
            elif check.name == "witness_pool":
                hints.append(
                    "Witness pool check failed. Ensure minimum witnesses (6) are available. "
                    "Check witness service health and network connectivity."
                )
            elif check.name == "keeper_keys":
                hints.append(
                    "Keeper key verification failed. Ensure at least one valid "
                    "Keeper key is registered and not expired."
                )
            elif check.name == "checkpoint_anchors":
                hints.append(
                    "Checkpoint anchor check failed. System requires at least one "
                    "checkpoint for recovery capability. Create a checkpoint first."
                )
            elif check.name == "halt_state":
                hints.append(
                    "System is in halted state. Resolve the halt condition before "
                    "restarting. Check halt reason in logs."
                )
            elif check.name == "replica_sync":
                hints.append(
                    "Replica synchronization failed. Check replication lag and "
                    "ensure all replicas are healthy."
                )
            else:
                hints.append(f"Check '{check.name}' failed: {check.details}")
        return hints


@dataclass(frozen=True)
class VerificationCheckError(Exception):
    """Raised when a specific verification check fails internally.

    This error is used internally during verification and should be
    caught by the verification service to create VerificationCheck results.

    Attributes:
        check_name: Name of the check that failed.
        reason: Reason for the failure.
        error_code: Error code for categorization.
    """

    check_name: str
    reason: str
    error_code: str

    def __str__(self) -> str:
        """Return string representation."""
        return f"[{self.error_code}] {self.check_name}: {self.reason}"


class BypassNotAllowedError(Exception):
    """Raised when verification bypass is not allowed.

    Constitutional Constraint (FR146 MVP Note):
    Bypass is only allowed for continuous restart scenarios and is
    NEVER allowed post-halt. This error is raised when bypass is
    attempted in a forbidden context.

    Attributes:
        reason: Why bypass is not allowed.
        is_post_halt: Whether this is a post-halt recovery attempt.
    """

    def __init__(
        self,
        reason: str,
        is_post_halt: bool = False,
    ) -> None:
        """Initialize the error.

        Args:
            reason: Why bypass is not allowed.
            is_post_halt: True if this is post-halt recovery.
        """
        self.reason = reason
        self.is_post_halt = is_post_halt

        message = f"Verification bypass not allowed: {reason}"
        if is_post_halt:
            message += " (post-halt recovery requires full verification)"

        super().__init__(message)


class PostHaltVerificationRequiredError(Exception):
    """Raised when post-halt verification is required but not performed.

    Constitutional Constraint (AC5):
    Post-halt verification must be more stringent than normal startup.
    This error is raised if the system attempts to start after a halt
    without proper post-halt verification.

    Attributes:
        halt_reason: The reason for the previous halt.
    """

    def __init__(self, halt_reason: str | None = None) -> None:
        """Initialize the error.

        Args:
            halt_reason: Optional reason for the previous halt.
        """
        self.halt_reason = halt_reason

        message = (
            "Post-halt verification required. System was previously halted"
            f"{f': {halt_reason}' if halt_reason else ''}. "
            "Full verification with stringent mode is required before restart."
        )

        super().__init__(message)
