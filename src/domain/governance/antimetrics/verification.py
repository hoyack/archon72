"""Anti-Metrics Verification Domain Models.

Story: consent-gov-10.2: Anti-Metrics Verification

This module defines the domain models for anti-metrics verification.
Verification provides independent confirmation that anti-metrics constraints
are being enforced.

Purpose:
    Trust but verify:
    - Anti-metrics guard should prevent violations
    - Verification confirms prevention worked
    - Auditors can independently check
    - Defense in depth

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class VerificationCheck(Enum):
    """Type of verification check performed.

    Each check type corresponds to a specific anti-metrics constraint.
    """

    SCHEMA_TABLES = "schema_tables"
    SCHEMA_COLUMNS = "schema_columns"
    API_ENDPOINTS = "api_endpoints"
    PROHIBITED_PATTERNS = "prohibited_patterns"

    def __str__(self) -> str:
        """Return human-readable check name."""
        return self.value.replace("_", " ").title()


class VerificationStatus(Enum):
    """Status of verification result.

    PASS: No violations found
    FAIL: One or more violations found
    """

    PASS = "pass"
    FAIL = "fail"

    def __str__(self) -> str:
        """Return status name."""
        return self.value.upper()


@dataclass(frozen=True)
class CheckResult:
    """Result of a single verification check.

    Immutable record of what was checked and what was found.

    Attributes:
        check_type: Type of verification check performed
        status: PASS or FAIL result
        items_checked: Number of items examined
        violations_found: List of violation descriptions
    """

    check_type: VerificationCheck
    status: VerificationStatus
    items_checked: int
    violations_found: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate check result consistency."""
        # Ensure status matches violations
        has_violations = len(self.violations_found) > 0
        if has_violations and self.status == VerificationStatus.PASS:
            raise ValueError("Cannot have PASS status with violations found")
        if not has_violations and self.status == VerificationStatus.FAIL:
            raise ValueError("Cannot have FAIL status without violations")


@dataclass(frozen=True)
class VerificationReport:
    """Complete verification report.

    Immutable, comprehensive report of all verification checks.
    Can be generated independently by auditors.

    Attributes:
        report_id: Unique identifier for this report
        verified_at: When verification was performed
        overall_status: PASS if all checks pass, FAIL if any fail
        checks: List of individual check results
        total_violations: Sum of all violations found
        verification_duration_ms: Time taken to verify
        verifier_id: Optional ID of who/what ran verification
    """

    report_id: UUID
    verified_at: datetime
    overall_status: VerificationStatus
    checks: tuple[CheckResult, ...]
    total_violations: int
    verification_duration_ms: int
    verifier_id: UUID | None = None

    def __post_init__(self) -> None:
        """Validate report consistency."""
        # Calculate expected total violations
        expected_total = sum(len(c.violations_found) for c in self.checks)
        if expected_total != self.total_violations:
            raise ValueError(
                f"total_violations ({self.total_violations}) does not match "
                f"sum of check violations ({expected_total})"
            )

        # Validate overall status
        any_failed = any(c.status == VerificationStatus.FAIL for c in self.checks)
        if any_failed and self.overall_status == VerificationStatus.PASS:
            raise ValueError("Cannot have PASS overall status with failed checks")
        if not any_failed and self.overall_status == VerificationStatus.FAIL:
            raise ValueError("Cannot have FAIL overall status with all checks passing")

    def has_violations(self) -> bool:
        """Check if any violations were found."""
        return self.total_violations > 0

    def get_check_result(self, check_type: VerificationCheck) -> CheckResult | None:
        """Get result for a specific check type."""
        for check in self.checks:
            if check.check_type == check_type:
                return check
        return None


class VerificationFailedError(ValueError):
    """Raised when verification finds violations.

    This error indicates the system has metric-related
    infrastructure that should not exist.

    Attributes:
        report: The verification report with details
    """

    def __init__(
        self,
        message: str,
        report: VerificationReport | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error message
            report: Optional verification report with details
        """
        super().__init__(message)
        self.report = report

    def __str__(self) -> str:
        """Return error message with violation count."""
        if self.report:
            return f"{super().__str__()} [{self.report.total_violations} violations]"
        return super().__str__()
