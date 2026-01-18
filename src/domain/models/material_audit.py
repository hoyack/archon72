"""Material audit domain models (Story 9.3, FR57).

Quarterly material audit tracking for emergence governance.
Audits re-scan all public materials to catch prohibited
language that may have slipped through initial scanning.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
- ADR-11: Emergence governance under complexity control
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final

# Audit ID prefix for consistent identification
AUDIT_ID_PREFIX: Final[str] = "audit"

# Remediation deadline in days (consistent with breach escalation)
REMEDIATION_DEADLINE_DAYS: Final[int] = 7


class AuditStatus(str, Enum):
    """Status of a quarterly material audit (FR57).

    Tracks the lifecycle of an audit from scheduling through completion.
    """

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RemediationStatus(str, Enum):
    """Status of violation remediation (FR57).

    Tracks how a detected violation is being addressed.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WAIVED = "waived"


@dataclass(frozen=True, eq=True)
class AuditQuarter:
    """Quarter identifier for audit scheduling (FR57).

    Represents a specific quarter in a year for audit tracking.
    Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec.

    Attributes:
        year: The calendar year.
        quarter: The quarter number (1-4).
    """

    year: int
    quarter: int

    def __post_init__(self) -> None:
        """Validate quarter constraints per FR57.

        Raises:
            ValueError: If quarter is not 1-4 or year is invalid.
        """
        if not 1 <= self.quarter <= 4:
            raise ValueError(f"FR57: quarter must be 1-4, got {self.quarter}")
        if self.year < 2020:
            raise ValueError(f"FR57: year must be >= 2020, got {self.year}")

    def __str__(self) -> str:
        """Format as YYYY-Q# for display."""
        return f"{self.year}-Q{self.quarter}"

    @classmethod
    def from_datetime(cls, dt: datetime) -> AuditQuarter:
        """Create quarter from datetime.

        Args:
            dt: The datetime to extract quarter from.

        Returns:
            AuditQuarter for the given datetime.
        """
        quarter = (dt.month - 1) // 3 + 1
        return cls(year=dt.year, quarter=quarter)

    def next_quarter(self) -> AuditQuarter:
        """Get the next quarter.

        Returns:
            The following quarter (wraps to next year from Q4).
        """
        if self.quarter == 4:
            return AuditQuarter(year=self.year + 1, quarter=1)
        return AuditQuarter(year=self.year, quarter=self.quarter + 1)

    def previous_quarter(self) -> AuditQuarter:
        """Get the previous quarter.

        Returns:
            The preceding quarter (wraps to previous year from Q1).
        """
        if self.quarter == 1:
            return AuditQuarter(year=self.year - 1, quarter=4)
        return AuditQuarter(year=self.year, quarter=self.quarter - 1)


@dataclass(frozen=True, eq=True)
class MaterialViolation:
    """A violation found during material audit (FR57).

    Records details about prohibited content found in a material
    during quarterly audit, including remediation tracking.

    Attributes:
        material_id: ID of the violating material.
        material_type: Type of material (publication, document, etc.).
        title: Title of the material for context.
        matched_terms: Prohibited terms that were detected.
        flagged_at: When the violation was flagged.
        remediation_status: Current remediation state.
    """

    material_id: str
    material_type: str
    title: str
    matched_terms: tuple[str, ...]
    flagged_at: datetime
    remediation_status: RemediationStatus = RemediationStatus.PENDING

    def __post_init__(self) -> None:
        """Validate violation per FR57.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        if not self.material_id:
            raise ValueError("FR57: material_id is required")
        if not self.material_type:
            raise ValueError("FR57: material_type is required")
        if not self.title:
            raise ValueError("FR57: title is required")
        if not self.matched_terms:
            raise ValueError("FR57: matched_terms is required for violation")

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "material_id": self.material_id,
            "material_type": self.material_type,
            "title": self.title,
            "matched_terms": list(self.matched_terms),
            "flagged_at": self.flagged_at.isoformat(),
            "remediation_status": self.remediation_status.value,
        }

    def with_remediation_status(self, status: RemediationStatus) -> MaterialViolation:
        """Create copy with updated remediation status.

        Args:
            status: The new remediation status.

        Returns:
            New MaterialViolation with updated status.
        """
        return MaterialViolation(
            material_id=self.material_id,
            material_type=self.material_type,
            title=self.title,
            matched_terms=self.matched_terms,
            flagged_at=self.flagged_at,
            remediation_status=status,
        )


@dataclass(frozen=True, eq=True)
class MaterialAudit:
    """A quarterly material audit per FR57.

    Represents a complete audit of all public materials for
    prohibited language. Tracks materials scanned, violations
    found, and remediation deadlines.

    Attributes:
        audit_id: Unique identifier (format: audit-YYYY-Q#).
        quarter: Which quarter this audit covers.
        status: Current audit status.
        materials_scanned: Count of materials scanned.
        violations_found: Count of violations detected.
        violation_details: Detailed violation records.
        started_at: When audit started.
        completed_at: When audit completed (None if in progress).
        remediation_deadline: Deadline for Conclave response.
    """

    audit_id: str
    quarter: AuditQuarter
    status: AuditStatus
    materials_scanned: int
    violations_found: int
    violation_details: tuple[MaterialViolation, ...]
    started_at: datetime
    completed_at: datetime | None = None
    remediation_deadline: datetime | None = None

    def __post_init__(self) -> None:
        """Validate audit per FR57.

        Raises:
            ValueError: If validation fails with FR57 reference.
        """
        if not self.audit_id:
            raise ValueError("FR57: audit_id is required")

        if not self.audit_id.startswith(AUDIT_ID_PREFIX):
            raise ValueError(f"FR57: audit_id must start with '{AUDIT_ID_PREFIX}'")

        # Violations count must match details
        if self.violations_found != len(self.violation_details):
            raise ValueError(
                f"FR57: violations_found ({self.violations_found}) must match "
                f"violation_details count ({len(self.violation_details)})"
            )

        # Materials scanned must be non-negative
        if self.materials_scanned < 0:
            raise ValueError("FR57: materials_scanned cannot be negative")

        # Completed audits must have completed_at
        if self.status == AuditStatus.COMPLETED and self.completed_at is None:
            raise ValueError("FR57: completed audit must have completed_at timestamp")

        # Audits with violations must have remediation_deadline
        if (
            self.status == AuditStatus.COMPLETED
            and self.violations_found > 0
            and self.remediation_deadline is None
        ):
            raise ValueError(
                "FR57: audit with violations must have remediation_deadline"
            )

    @property
    def is_complete(self) -> bool:
        """Check if audit has completed."""
        return self.status == AuditStatus.COMPLETED

    @property
    def is_in_progress(self) -> bool:
        """Check if audit is currently running."""
        return self.status == AuditStatus.IN_PROGRESS

    @property
    def has_violations(self) -> bool:
        """Check if audit found violations."""
        return self.violations_found > 0

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "audit_id": self.audit_id,
            "quarter": str(self.quarter),
            "status": self.status.value,
            "materials_scanned": self.materials_scanned,
            "violations_found": self.violations_found,
            "violation_details": [v.to_dict() for v in self.violation_details],
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "remediation_deadline": (
                self.remediation_deadline.isoformat()
                if self.remediation_deadline
                else None
            ),
        }

    @classmethod
    def create_in_progress(
        cls,
        audit_id: str,
        quarter: AuditQuarter,
        started_at: datetime,
    ) -> MaterialAudit:
        """Create a new in-progress audit.

        Args:
            audit_id: Unique audit identifier.
            quarter: Quarter being audited.
            started_at: When the audit started.

        Returns:
            New MaterialAudit in IN_PROGRESS status.
        """
        return cls(
            audit_id=audit_id,
            quarter=quarter,
            status=AuditStatus.IN_PROGRESS,
            materials_scanned=0,
            violations_found=0,
            violation_details=(),
            started_at=started_at,
        )

    def complete(
        self,
        materials_scanned: int,
        violation_details: tuple[MaterialViolation, ...],
        completed_at: datetime,
        remediation_deadline: datetime | None = None,
    ) -> MaterialAudit:
        """Complete the audit with results.

        Args:
            materials_scanned: Total materials scanned.
            violation_details: All violations found.
            completed_at: When audit completed.
            remediation_deadline: Deadline for remediation (required if violations).

        Returns:
            New MaterialAudit in COMPLETED status.
        """
        return MaterialAudit(
            audit_id=self.audit_id,
            quarter=self.quarter,
            status=AuditStatus.COMPLETED,
            materials_scanned=materials_scanned,
            violations_found=len(violation_details),
            violation_details=violation_details,
            started_at=self.started_at,
            completed_at=completed_at,
            remediation_deadline=remediation_deadline,
        )

    def fail(self, completed_at: datetime) -> MaterialAudit:
        """Mark audit as failed.

        Args:
            completed_at: When the failure occurred.

        Returns:
            New MaterialAudit in FAILED status.
        """
        return MaterialAudit(
            audit_id=self.audit_id,
            quarter=self.quarter,
            status=AuditStatus.FAILED,
            materials_scanned=self.materials_scanned,
            violations_found=self.violations_found,
            violation_details=self.violation_details,
            started_at=self.started_at,
            completed_at=completed_at,
        )


def generate_audit_id(quarter: AuditQuarter) -> str:
    """Generate audit ID for a quarter.

    Args:
        quarter: The quarter to generate ID for.

    Returns:
        Audit ID in format: audit-YYYY-Q#
    """
    return f"{AUDIT_ID_PREFIX}-{quarter.year}-Q{quarter.quarter}"
