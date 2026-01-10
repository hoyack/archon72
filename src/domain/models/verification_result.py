"""Verification result models for pre-operational verification (Story 8.5, FR146, NFR35).

Domain models for representing pre-operational verification outcomes.

Constitutional Constraints:
- FR146: Startup SHALL execute verification checklist: hash chain, witness pool,
         Keeper keys, checkpoint anchors. Blocked until pass.
- NFR35: System startup SHALL complete verification checklist before operation.
- CT-13: Integrity outranks availability - startup failure preferable to unverified state.

Usage:
    from src.domain.models.verification_result import (
        VerificationCheck,
        VerificationResult,
        VerificationStatus,
    )

    # Single check result
    check = VerificationCheck(
        name="hash_chain",
        passed=True,
        details="Verified 1000 events",
        duration_ms=150.5,
    )

    # Overall verification result
    result = VerificationResult(
        status=VerificationStatus.PASSED,
        checks=(check,),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class VerificationStatus(str, Enum):
    """Status of pre-operational verification.

    Constitutional Constraint (FR146):
    - PASSED: All checks passed, system can start
    - FAILED: One or more checks failed, startup blocked
    - BYPASSED: Verification bypassed (continuous restart scenario only)
    """

    PASSED = "passed"
    FAILED = "failed"
    BYPASSED = "bypassed"


@dataclass(frozen=True)
class VerificationCheck:
    """Result of a single verification check.

    Each verification check represents one aspect of the pre-operational
    verification checklist (FR146):
    - hash_chain: Hash chain integrity
    - witness_pool: Witness pool availability
    - keeper_keys: Keeper key availability
    - checkpoint_anchors: Checkpoint anchors existence
    - halt_state: Current halt status (informational, not blocking)
    - replica_sync: Replica synchronization status

    Attributes:
        name: Identifier for the check (snake_case).
        passed: True if check passed, False if failed.
        details: Human-readable description of the check outcome.
        duration_ms: Time taken for the check in milliseconds.
        error_code: Optional error code for failed checks.
        metadata: Optional additional context (counts, IDs, etc.).
    """

    name: str
    passed: bool
    details: str
    duration_ms: float
    error_code: Optional[str] = None
    metadata: Optional[dict[str, object]] = None

    def __post_init__(self) -> None:
        """Validate check data."""
        if not self.name:
            raise ValueError("name cannot be empty")
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms must be non-negative, got {self.duration_ms}")
        if not self.passed and not self.error_code:
            # Default error code for failed checks
            object.__setattr__(self, "error_code", f"{self.name}_failed")


@dataclass(frozen=True)
class VerificationResult:
    """Result of the complete pre-operational verification checklist.

    Constitutional Constraint (FR146):
    Aggregates all individual check results and determines overall
    verification status. Startup is blocked if status is FAILED.

    Constitutional Constraint (CT-13):
    Integrity outranks availability. A failed verification means the
    system cannot start, even if this affects availability.

    Attributes:
        status: Overall verification status.
        checks: Tuple of all individual check results.
        started_at: When verification began.
        completed_at: When verification completed.
        is_post_halt: True if this is post-halt recovery verification.
        bypass_reason: Reason for bypass (if status is BYPASSED).
        bypass_count: Number of bypasses in current window (if applicable).
    """

    status: VerificationStatus
    checks: tuple[VerificationCheck, ...]
    started_at: datetime
    completed_at: datetime
    is_post_halt: bool = False
    bypass_reason: Optional[str] = None
    bypass_count: int = 0

    def __post_init__(self) -> None:
        """Validate result consistency."""
        if self.status == VerificationStatus.BYPASSED and not self.bypass_reason:
            raise ValueError("bypass_reason required when status is BYPASSED")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        if self.bypass_count < 0:
            raise ValueError(f"bypass_count must be non-negative, got {self.bypass_count}")

    @property
    def failed_checks(self) -> tuple[VerificationCheck, ...]:
        """Get all failed checks.

        Returns:
            Tuple of checks where passed is False.
        """
        return tuple(c for c in self.checks if not c.passed)

    @property
    def passed_checks(self) -> tuple[VerificationCheck, ...]:
        """Get all passed checks.

        Returns:
            Tuple of checks where passed is True.
        """
        return tuple(c for c in self.checks if c.passed)

    @property
    def duration_ms(self) -> float:
        """Get total verification duration in milliseconds.

        Returns:
            Duration from started_at to completed_at in milliseconds.
        """
        return (self.completed_at - self.started_at).total_seconds() * 1000

    @property
    def check_count(self) -> int:
        """Get total number of checks run.

        Returns:
            Count of all verification checks.
        """
        return len(self.checks)

    @property
    def failure_count(self) -> int:
        """Get count of failed checks.

        Returns:
            Number of checks where passed is False.
        """
        return len(self.failed_checks)

    def get_check_by_name(self, name: str) -> Optional[VerificationCheck]:
        """Get a specific check by name.

        Args:
            name: The check name to find.

        Returns:
            VerificationCheck if found, None otherwise.
        """
        for check in self.checks:
            if check.name == name:
                return check
        return None

    def to_summary(self) -> str:
        """Generate a human-readable summary.

        Returns:
            Summary string suitable for logging.
        """
        lines = [
            f"Pre-Operational Verification: {self.status.value.upper()}",
            f"Duration: {self.duration_ms:.1f}ms",
            f"Checks: {len(self.passed_checks)}/{self.check_count} passed",
        ]

        if self.is_post_halt:
            lines.append("Mode: Post-Halt Recovery (stringent)")

        if self.status == VerificationStatus.BYPASSED:
            lines.append(f"Bypass: {self.bypass_reason} (count: {self.bypass_count})")

        if self.failed_checks:
            lines.append("Failed checks:")
            for check in self.failed_checks:
                lines.append(f"  - {check.name}: {check.details}")

        return "\n".join(lines)
