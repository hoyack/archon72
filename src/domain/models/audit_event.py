"""Audit event domain models (Story 9.5, FR108).

Domain models for querying and analyzing audit events from the
constitutional record. These models transform raw event store data
into domain-specific objects for external observers and trend analysis.

Constitutional Constraints:
- FR108: Audit results logged as events
- CT-11: HALT CHECK FIRST on all operations
- CT-12: Audit events are witnessed when written

References:
- Story 9.3: QuarterlyAuditService writes audit events
- Story 9.5: AuditEventQueryService reads audit events (this story)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final, Literal

# Event type constants matching those in src/domain/events/audit.py
AUDIT_STARTED_EVENT_TYPE: Final[str] = "audit.started"
AUDIT_COMPLETED_EVENT_TYPE: Final[str] = "audit.completed"
AUDIT_VIOLATION_FLAGGED_EVENT_TYPE: Final[str] = "audit.violation.flagged"

# Prefix for audit event type filtering
AUDIT_EVENT_TYPE_PREFIX: Final[str] = "audit."


class AuditEventType(str, Enum):
    """Types of audit events (FR108).

    These map directly to the event type strings stored in the event store.
    Used for type-safe filtering and comparison.
    """

    STARTED = "audit.started"
    """Quarterly audit began (Story 9.3)."""

    COMPLETED = "audit.completed"
    """Audit finished (status in payload: clean/violations_found/failed)."""

    VIOLATION_FLAGGED = "audit.violation.flagged"
    """Material violation detected during audit."""


# Status literals for type safety
AuditCompletionStatus = Literal["clean", "violations_found", "failed", "not_run"]


@dataclass(frozen=True, eq=True)
class AuditEvent:
    """Audit event from the constitutional record (FR108).

    Represents a single audit-related event retrieved from the event store.
    This is a read model - events are written by QuarterlyAuditService.

    Attributes:
        event_id: Unique event identifier from event store.
        event_type: Event type string (e.g., "audit.completed").
        audit_id: Audit identifier from payload.
        quarter: Quarter being audited (e.g., "2026-Q1"), None if N/A.
        timestamp: When the event was created.
        payload: Full event payload for detailed analysis.
    """

    event_id: str
    event_type: str
    audit_id: str
    quarter: str | None
    timestamp: datetime
    payload: dict[str, object]

    def __post_init__(self) -> None:
        """Validate audit event per FR108.

        Raises:
            ValueError: If validation fails with FR108 reference.
        """
        if not self.event_id:
            raise ValueError("FR108: event_id is required")
        if not self.event_type:
            raise ValueError("FR108: event_type is required")
        if not self.audit_id:
            raise ValueError("FR108: audit_id is required")

    @property
    def is_started(self) -> bool:
        """Check if this is an audit started event."""
        return self.event_type == AuditEventType.STARTED.value

    @property
    def is_completed(self) -> bool:
        """Check if this is an audit completed event."""
        return self.event_type == AuditEventType.COMPLETED.value

    @property
    def is_violation_flagged(self) -> bool:
        """Check if this is a violation flagged event."""
        return self.event_type == AuditEventType.VIOLATION_FLAGGED.value

    @property
    def completion_status(self) -> str | None:
        """Get completion status from payload if this is a completed event.

        Returns:
            Status string ("clean", "violations_found", "failed") or None.
        """
        if self.is_completed and "status" in self.payload:
            return str(self.payload["status"])
        return None

    @property
    def violations_found(self) -> int:
        """Get violations count from payload if available.

        Returns:
            Number of violations found, or 0 if not in payload.
        """
        if "violations_found" in self.payload:
            value = self.payload["violations_found"]
            if isinstance(value, int):
                return value
        return 0

    @property
    def materials_scanned(self) -> int:
        """Get materials scanned count from payload if available.

        Returns:
            Number of materials scanned, or 0 if not in payload.
        """
        if "materials_scanned" in self.payload:
            value = self.payload["materials_scanned"]
            if isinstance(value, int):
                return value
        return 0


@dataclass(frozen=True, eq=True)
class QuarterStats:
    """Statistics for a single quarter (FR108).

    Aggregated data about audits in a specific quarter for trend analysis.

    Attributes:
        quarter: Quarter identifier (e.g., "2026-Q1").
        audits: Number of audits completed in this quarter.
        violations: Total violations found across all audits.
        status: Overall status of the quarter's audits.
    """

    quarter: str
    audits: int
    violations: int
    status: AuditCompletionStatus

    def __post_init__(self) -> None:
        """Validate quarter stats per FR108.

        Raises:
            ValueError: If validation fails with FR108 reference.
        """
        if not self.quarter:
            raise ValueError("FR108: quarter is required")
        if self.audits < 0:
            raise ValueError("FR108: audits cannot be negative")
        if self.violations < 0:
            raise ValueError("FR108: violations cannot be negative")


@dataclass(frozen=True, eq=True)
class AuditTrend:
    """Audit trend analysis over multiple quarters (FR108).

    Aggregated statistics for trend analysis by external observers.
    Enables detection of patterns and compliance monitoring.

    Attributes:
        quarters: Quarters included in analysis (chronological order).
        total_audits: Total number of audits in the period.
        total_violations: Total violations found across all audits.
        clean_audits: Number of audits with no violations.
        violation_audits: Number of audits that found violations.
        failed_audits: Number of audits that failed.
        average_violations_per_audit: Average violations per audit for trending.
        quarter_breakdown: Per-quarter statistics for detailed analysis.
    """

    quarters: tuple[str, ...]
    total_audits: int
    total_violations: int
    clean_audits: int
    violation_audits: int
    failed_audits: int
    average_violations_per_audit: float
    quarter_breakdown: tuple[QuarterStats, ...]

    def __post_init__(self) -> None:
        """Validate audit trend per FR108.

        Raises:
            ValueError: If validation fails with FR108 reference.
        """
        if self.total_audits < 0:
            raise ValueError("FR108: total_audits cannot be negative")
        if self.total_violations < 0:
            raise ValueError("FR108: total_violations cannot be negative")
        if self.clean_audits < 0:
            raise ValueError("FR108: clean_audits cannot be negative")
        if self.violation_audits < 0:
            raise ValueError("FR108: violation_audits cannot be negative")
        if self.failed_audits < 0:
            raise ValueError("FR108: failed_audits cannot be negative")
        if self.average_violations_per_audit < 0:
            raise ValueError("FR108: average_violations_per_audit cannot be negative")

        # Consistency check
        sum_audits = self.clean_audits + self.violation_audits + self.failed_audits
        if sum_audits != self.total_audits:
            raise ValueError(
                f"FR108: audit counts inconsistent - "
                f"{sum_audits} != {self.total_audits}"
            )

    @property
    def has_violations(self) -> bool:
        """Check if any violations were found in the trend period."""
        return self.total_violations > 0

    @property
    def violation_rate(self) -> float:
        """Calculate percentage of audits that found violations.

        Returns:
            Percentage (0-100) of audits with violations.
        """
        if self.total_audits == 0:
            return 0.0
        return (self.violation_audits / self.total_audits) * 100

    @property
    def quarters_count(self) -> int:
        """Get number of quarters in trend analysis."""
        return len(self.quarters)

    @classmethod
    def empty(cls) -> AuditTrend:
        """Create an empty trend for cases with no audit data.

        Returns:
            AuditTrend with all zeros.
        """
        return cls(
            quarters=(),
            total_audits=0,
            total_violations=0,
            clean_audits=0,
            violation_audits=0,
            failed_audits=0,
            average_violations_per_audit=0.0,
            quarter_breakdown=(),
        )
