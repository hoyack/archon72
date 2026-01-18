"""Audit events (Story 9.3, FR57).

Domain events for recording quarterly material audit results.
All audit events are witnessed per CT-12 for constitutional
accountability.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
- ADR-11: Emergence governance under complexity control
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

# Event type constants (FR57)
AUDIT_STARTED_EVENT_TYPE: Final[str] = "audit.started"
AUDIT_COMPLETED_EVENT_TYPE: Final[str] = "audit.completed"
MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE: Final[str] = "audit.violation.flagged"

# System agent ID for audit operations (follows existing pattern)
AUDIT_SYSTEM_AGENT_ID: Final[str] = "system:quarterly_audit"

# Audit status literal type
AuditResultStatus = Literal["clean", "violations_found", "failed"]


@dataclass(frozen=True, eq=True)
class AuditStartedEventPayload:
    """Payload for audit started event (FR57).

    Records when a quarterly audit begins. This event is witnessed
    to provide accountability for audit initiation.

    Attributes:
        audit_id: Unique identifier of the audit.
        quarter: Quarter being audited (e.g., "2026-Q1").
        scheduled_at: When the audit was scheduled.
        started_at: When the audit actually started.
    """

    audit_id: str
    quarter: str
    scheduled_at: datetime
    started_at: datetime

    def __post_init__(self) -> None:
        """Validate payload per FR57.

        Raises:
            ValueError: If validation fails with FR57 reference.
        """
        if not self.audit_id:
            raise ValueError("FR57: audit_id is required")
        if not self.quarter:
            raise ValueError("FR57: quarter is required")

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization and event storage.
        """
        return {
            "audit_id": self.audit_id,
            "quarter": self.quarter,
            "scheduled_at": self.scheduled_at.isoformat(),
            "started_at": self.started_at.isoformat(),
        }

    def signable_content(self) -> bytes:
        """Generate deterministic bytes for CT-12 witnessing.

        Creates a canonical byte representation of this event payload
        suitable for signing. The representation is deterministic
        (same payload always produces same bytes).

        Returns:
            Bytes suitable for cryptographic signing.
        """
        canonical = (
            f"audit_started:"
            f"audit_id={self.audit_id}:"
            f"quarter={self.quarter}:"
            f"scheduled_at={self.scheduled_at.isoformat()}:"
            f"started_at={self.started_at.isoformat()}"
        )
        return canonical.encode("utf-8")

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex-encoded SHA-256 hash of the signable content.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()


@dataclass(frozen=True, eq=True)
class AuditCompletedEventPayload:
    """Payload for audit completed event (FR57, AC5).

    Records when a quarterly audit completes with results.
    This event is witnessed per CT-12 and includes comprehensive
    audit statistics.

    Attributes:
        audit_id: Unique identifier of the audit.
        quarter: Quarter that was audited (e.g., "2026-Q1").
        status: Result status ("clean", "violations_found", or "failed").
        materials_scanned: Total count of materials scanned.
        violations_found: Count of violations detected.
        started_at: When the audit started.
        completed_at: When the audit completed.
        remediation_deadline: Deadline for Conclave response (if violations).
    """

    audit_id: str
    quarter: str
    status: AuditResultStatus
    materials_scanned: int
    violations_found: int
    started_at: datetime
    completed_at: datetime
    remediation_deadline: datetime | None = None

    def __post_init__(self) -> None:
        """Validate payload per FR57.

        Raises:
            ValueError: If validation fails with FR57 reference.
        """
        if not self.audit_id:
            raise ValueError("FR57: audit_id is required")
        if not self.quarter:
            raise ValueError("FR57: quarter is required")
        if self.status not in ("clean", "violations_found", "failed"):
            raise ValueError(
                f"FR57: status must be 'clean', 'violations_found', or 'failed', "
                f"got '{self.status}'"
            )
        if self.materials_scanned < 0:
            raise ValueError("FR57: materials_scanned cannot be negative")
        if self.violations_found < 0:
            raise ValueError("FR57: violations_found cannot be negative")

        # Violations found status must have at least one violation
        if self.status == "violations_found" and self.violations_found == 0:
            raise ValueError(
                "FR57: status 'violations_found' requires violations_found > 0"
            )

        # Clean status must have zero violations
        if self.status == "clean" and self.violations_found > 0:
            raise ValueError("FR57: status 'clean' cannot have violations_found > 0")

        # Violations require remediation deadline (AC3: clock starts for Conclave)
        if self.status == "violations_found" and self.remediation_deadline is None:
            raise ValueError("FR57: violations require remediation_deadline (AC3)")

    @property
    def is_clean(self) -> bool:
        """Check if audit completed with no violations."""
        return self.status == "clean"

    @property
    def has_violations(self) -> bool:
        """Check if audit found violations."""
        return self.status == "violations_found"

    @property
    def is_failed(self) -> bool:
        """Check if audit failed."""
        return self.status == "failed"

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization and event storage.
        """
        return {
            "audit_id": self.audit_id,
            "quarter": self.quarter,
            "status": self.status,
            "materials_scanned": self.materials_scanned,
            "violations_found": self.violations_found,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "remediation_deadline": (
                self.remediation_deadline.isoformat()
                if self.remediation_deadline
                else None
            ),
        }

    def signable_content(self) -> bytes:
        """Generate deterministic bytes for CT-12 witnessing.

        Creates a canonical byte representation of this event payload
        suitable for signing. The representation is deterministic
        (same payload always produces same bytes).

        Returns:
            Bytes suitable for cryptographic signing.
        """
        deadline_str = (
            self.remediation_deadline.isoformat()
            if self.remediation_deadline
            else "none"
        )
        canonical = (
            f"audit_completed:"
            f"audit_id={self.audit_id}:"
            f"quarter={self.quarter}:"
            f"status={self.status}:"
            f"materials_scanned={self.materials_scanned}:"
            f"violations_found={self.violations_found}:"
            f"started_at={self.started_at.isoformat()}:"
            f"completed_at={self.completed_at.isoformat()}:"
            f"remediation_deadline={deadline_str}"
        )
        return canonical.encode("utf-8")

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex-encoded SHA-256 hash of the signable content.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()

    @classmethod
    def clean_audit(
        cls,
        audit_id: str,
        quarter: str,
        materials_scanned: int,
        started_at: datetime,
        completed_at: datetime,
    ) -> AuditCompletedEventPayload:
        """Create payload for a clean audit result.

        Args:
            audit_id: Unique audit identifier.
            quarter: Quarter audited.
            materials_scanned: Number of materials scanned.
            started_at: When audit started.
            completed_at: When audit completed.

        Returns:
            AuditCompletedEventPayload for a clean audit.
        """
        return cls(
            audit_id=audit_id,
            quarter=quarter,
            status="clean",
            materials_scanned=materials_scanned,
            violations_found=0,
            started_at=started_at,
            completed_at=completed_at,
        )

    @classmethod
    def violations_audit(
        cls,
        audit_id: str,
        quarter: str,
        materials_scanned: int,
        violations_found: int,
        started_at: datetime,
        completed_at: datetime,
        remediation_deadline: datetime,
    ) -> AuditCompletedEventPayload:
        """Create payload for an audit with violations.

        Args:
            audit_id: Unique audit identifier.
            quarter: Quarter audited.
            materials_scanned: Number of materials scanned.
            violations_found: Number of violations found.
            started_at: When audit started.
            completed_at: When audit completed.
            remediation_deadline: Deadline for remediation.

        Returns:
            AuditCompletedEventPayload for an audit with violations.
        """
        return cls(
            audit_id=audit_id,
            quarter=quarter,
            status="violations_found",
            materials_scanned=materials_scanned,
            violations_found=violations_found,
            started_at=started_at,
            completed_at=completed_at,
            remediation_deadline=remediation_deadline,
        )

    @classmethod
    def failed_audit(
        cls,
        audit_id: str,
        quarter: str,
        materials_scanned: int,
        started_at: datetime,
        completed_at: datetime,
    ) -> AuditCompletedEventPayload:
        """Create payload for a failed audit.

        Args:
            audit_id: Unique audit identifier.
            quarter: Quarter audited.
            materials_scanned: Materials scanned before failure.
            started_at: When audit started.
            completed_at: When failure occurred.

        Returns:
            AuditCompletedEventPayload for a failed audit.
        """
        return cls(
            audit_id=audit_id,
            quarter=quarter,
            status="failed",
            materials_scanned=materials_scanned,
            violations_found=0,
            started_at=started_at,
            completed_at=completed_at,
        )


@dataclass(frozen=True, eq=True)
class ViolationFlaggedEventPayload:
    """Payload for material violation flagged event (FR57, AC3).

    Records when a specific material is flagged for prohibited
    content during quarterly audit. This starts the clock for
    Conclave response per AC3.

    Attributes:
        audit_id: ID of the audit that found the violation.
        material_id: ID of the violating material.
        material_type: Type of material (publication, document, etc.).
        title: Title of the material for context.
        matched_terms: Prohibited terms that were detected.
        flagged_at: When the violation was flagged.
    """

    audit_id: str
    material_id: str
    material_type: str
    title: str
    matched_terms: tuple[str, ...]
    flagged_at: datetime

    def __post_init__(self) -> None:
        """Validate payload per FR57.

        Raises:
            ValueError: If validation fails with FR57 reference.
        """
        if not self.audit_id:
            raise ValueError("FR57: audit_id is required")
        if not self.material_id:
            raise ValueError("FR57: material_id is required")
        if not self.material_type:
            raise ValueError("FR57: material_type is required")
        if not self.title:
            raise ValueError("FR57: title is required")
        if not self.matched_terms:
            raise ValueError("FR57: matched_terms is required for violation")

    @property
    def terms_count(self) -> int:
        """Get the number of matched terms."""
        return len(self.matched_terms)

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization and event storage.
        """
        return {
            "audit_id": self.audit_id,
            "material_id": self.material_id,
            "material_type": self.material_type,
            "title": self.title,
            "matched_terms": list(self.matched_terms),
            "flagged_at": self.flagged_at.isoformat(),
            "terms_count": self.terms_count,
        }

    def signable_content(self) -> bytes:
        """Generate deterministic bytes for CT-12 witnessing.

        Creates a canonical byte representation of this event payload
        suitable for signing. The representation is deterministic
        (same payload always produces same bytes).

        Returns:
            Bytes suitable for cryptographic signing.
        """
        # Sort matched_terms for determinism
        sorted_terms = tuple(sorted(self.matched_terms))
        canonical = (
            f"violation_flagged:"
            f"audit_id={self.audit_id}:"
            f"material_id={self.material_id}:"
            f"material_type={self.material_type}:"
            f"title={self.title}:"
            f"matched_terms={','.join(sorted_terms)}:"
            f"flagged_at={self.flagged_at.isoformat()}"
        )
        return canonical.encode("utf-8")

    def content_hash(self) -> str:
        """Generate SHA-256 hash of signable content.

        Returns:
            Hex-encoded SHA-256 hash of the signable content.
        """
        return hashlib.sha256(self.signable_content()).hexdigest()
