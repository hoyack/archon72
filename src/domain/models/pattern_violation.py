"""Pattern violation model for FMEA detection (Story 8.8, AC6).

Domain model for pattern violations from the FMEA risk matrix.

Constitutional Constraints:
- PV-001: Raw string event type (EventType enum required)
- PV-002: Plain string hash (ContentRef validation required)
- PV-003: Missing HaltGuard (base class requirement)

Usage:
    from src.domain.models.pattern_violation import (
        PatternViolation,
        PatternViolationType,
    )

    violation = PatternViolation.create(
        violation_type=PatternViolationType.RAW_STRING_EVENT_TYPE,
        location="src/domain/events/foo.py:42",
        description="Event type 'user_created' should use EventType enum",
    )
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class PatternViolationType(str, Enum):
    """Types of pattern violations from FMEA risk matrix.

    These violations represent code patterns that could cause
    constitutional integrity failures if not corrected.
    """

    RAW_STRING_EVENT_TYPE = "PV-001"  # Raw string event type (orphan events)
    PLAIN_STRING_HASH = "PV-002"  # Plain string hash (invalid refs)
    MISSING_HALT_GUARD = "PV-003"  # Missing HaltGuard (operations during halt)


class ViolationSeverity(str, Enum):
    """Severity of pattern violations.

    Severity determines the urgency of remediation:
    - CRITICAL: Must fix immediately, blocks deployment
    - HIGH: Should fix before next release
    - MEDIUM: Should fix in near term
    - LOW: Technical debt, fix when convenient
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Default severities from FMEA risk matrix
VIOLATION_SEVERITIES: dict[PatternViolationType, ViolationSeverity] = {
    PatternViolationType.RAW_STRING_EVENT_TYPE: ViolationSeverity.HIGH,
    PatternViolationType.PLAIN_STRING_HASH: ViolationSeverity.CRITICAL,
    PatternViolationType.MISSING_HALT_GUARD: ViolationSeverity.CRITICAL,
}

# Default remediations from FMEA risk matrix
VIOLATION_REMEDIATIONS: dict[PatternViolationType, str] = {
    PatternViolationType.RAW_STRING_EVENT_TYPE: (
        "Use EventType enum from src.domain.events instead of raw strings. "
        "Run mypy with strict mode to catch type violations."
    ),
    PatternViolationType.PLAIN_STRING_HASH: (
        "Use ContentRef type with create_content_ref() function. "
        "Never use plain strings for content hashes."
    ),
    PatternViolationType.MISSING_HALT_GUARD: (
        "All constitutional services must check halt state before operations. "
        "Use HaltGuard base class or inject HaltChecker dependency."
    ),
}


@dataclass(frozen=True)
class PatternViolation:
    """A detected pattern violation from FMEA analysis.

    Represents a code pattern that violates constitutional constraints
    and should be remediated.

    Attributes:
        violation_id: Unique identifier for this violation.
        violation_type: Which pattern violation type (PV-001, PV-002, PV-003).
        location: File path and optional line number (e.g., "src/foo.py:42").
        description: Human-readable description of the violation.
        severity: How severe this violation is.
        remediation: How to fix the violation.
        detected_at: When this violation was detected.
        is_resolved: Whether the violation has been fixed.
        resolved_at: When the violation was resolved.
        resolved_by: Who resolved the violation.
    """

    violation_id: UUID
    violation_type: PatternViolationType
    location: str
    description: str
    severity: ViolationSeverity
    remediation: str
    detected_at: datetime
    is_resolved: bool
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]

    def __post_init__(self) -> None:
        """Validate violation data."""
        if not self.location:
            raise ValueError("location cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if not self.remediation:
            raise ValueError("remediation cannot be empty")

    @classmethod
    def create(
        cls,
        violation_type: PatternViolationType,
        location: str,
        description: str,
        severity: Optional[ViolationSeverity] = None,
        remediation: Optional[str] = None,
    ) -> "PatternViolation":
        """Factory method to create a pattern violation.

        Args:
            violation_type: Which type of violation.
            location: File path and line number.
            description: What the violation is.
            severity: Optional override for default severity.
            remediation: Optional override for default remediation.

        Returns:
            A new PatternViolation with generated ID and timestamp.
        """
        return cls(
            violation_id=uuid4(),
            violation_type=violation_type,
            location=location,
            description=description,
            severity=severity or VIOLATION_SEVERITIES[violation_type],
            remediation=remediation or VIOLATION_REMEDIATIONS[violation_type],
            detected_at=datetime.now(timezone.utc),
            is_resolved=False,
            resolved_at=None,
            resolved_by=None,
        )

    def resolve(self, resolved_by: str) -> "PatternViolation":
        """Create resolved version of this violation.

        Args:
            resolved_by: Who resolved the violation.

        Returns:
            New PatternViolation marked as resolved.
        """
        return PatternViolation(
            violation_id=self.violation_id,
            violation_type=self.violation_type,
            location=self.location,
            description=self.description,
            severity=self.severity,
            remediation=self.remediation,
            detected_at=self.detected_at,
            is_resolved=True,
            resolved_at=datetime.now(timezone.utc),
            resolved_by=resolved_by,
        )

    @property
    def is_critical(self) -> bool:
        """Check if this violation is critical severity.

        Returns:
            True if severity is CRITICAL.
        """
        return self.severity == ViolationSeverity.CRITICAL

    @property
    def blocks_deployment(self) -> bool:
        """Check if this violation should block deployment.

        Returns:
            True if unresolved and CRITICAL or HIGH severity.
        """
        if self.is_resolved:
            return False
        return self.severity in (ViolationSeverity.CRITICAL, ViolationSeverity.HIGH)

    def to_summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Summary string suitable for logging or display.
        """
        severity_emoji = {
            ViolationSeverity.CRITICAL: "🚨",
            ViolationSeverity.HIGH: "🔴",
            ViolationSeverity.MEDIUM: "🟡",
            ViolationSeverity.LOW: "🟢",
        }
        emoji = severity_emoji[self.severity]
        status = "✅ Resolved" if self.is_resolved else "❌ Unresolved"

        return (
            f"{emoji} [{self.violation_type.value}] {self.description}\n"
            f"   Location: {self.location}\n"
            f"   Severity: {self.severity.value}\n"
            f"   Status: {status}\n"
            f"   Remediation: {self.remediation}"
        )


@dataclass(frozen=True)
class ViolationScan:
    """Results of a pattern violation scan.

    Represents the outcome of scanning code for pattern violations.

    Attributes:
        scan_id: Unique identifier for this scan.
        violations: List of detected violations.
        files_scanned: Number of files scanned.
        scan_duration_ms: How long the scan took.
        scanned_at: When the scan was performed.
    """

    scan_id: UUID
    violations: tuple[PatternViolation, ...]
    files_scanned: int
    scan_duration_ms: int
    scanned_at: datetime

    @classmethod
    def create(
        cls,
        violations: list[PatternViolation],
        files_scanned: int,
        scan_duration_ms: int,
    ) -> "ViolationScan":
        """Factory method to create scan results.

        Args:
            violations: List of detected violations.
            files_scanned: Number of files scanned.
            scan_duration_ms: Scan duration in milliseconds.

        Returns:
            A new ViolationScan with generated ID and timestamp.
        """
        return cls(
            scan_id=uuid4(),
            violations=tuple(violations),
            files_scanned=files_scanned,
            scan_duration_ms=scan_duration_ms,
            scanned_at=datetime.now(timezone.utc),
        )

    @property
    def has_violations(self) -> bool:
        """Check if any violations were found.

        Returns:
            True if at least one violation detected.
        """
        return len(self.violations) > 0

    @property
    def critical_count(self) -> int:
        """Count critical violations.

        Returns:
            Number of CRITICAL severity violations.
        """
        return sum(1 for v in self.violations if v.is_critical)

    @property
    def blocking_count(self) -> int:
        """Count deployment-blocking violations.

        Returns:
            Number of violations that block deployment.
        """
        return sum(1 for v in self.violations if v.blocks_deployment)

    @property
    def blocks_deployment(self) -> bool:
        """Check if scan results should block deployment.

        Returns:
            True if any violation blocks deployment.
        """
        return self.blocking_count > 0

    def to_summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Summary string suitable for logging or display.
        """
        status = "🚨 BLOCKING" if self.blocks_deployment else "✅ PASS"
        return (
            f"{status} Pattern Violation Scan\n"
            f"   Files scanned: {self.files_scanned}\n"
            f"   Duration: {self.scan_duration_ms}ms\n"
            f"   Violations: {len(self.violations)} "
            f"({self.critical_count} critical, {self.blocking_count} blocking)"
        )
