"""Adoption ratio domain models (Story 8.6, PREVENT-7).

This module defines the domain models for tracking petition adoption ratios
per realm to detect excessive petition-to-Motion conversion patterns.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio to detect budget contention
- CT-11: "Speech is unlimited. Agenda is scarce." - Adoption is scarce
- CT-12: Witnessing creates accountability -> Frozen dataclass
- ADR-P4: Budget consumption prevents budget laundering
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AdoptionRatioMetrics:
    """Adoption ratio metrics per realm per cycle (Story 8.6, PREVENT-7).

    Tracks the ratio of adopted petitions to escalated petitions for a realm
    within a governance cycle. Used to detect excessive adoption patterns
    that may indicate "rubber-stamping" of escalated petitions.

    Constitutional Requirements:
    - PREVENT-7: Alert when adoption ratio > 50%
    - ASM-7: Monitor adoption vs organic ratio
    - CT-11: Adoption is a scarce resource (like agenda)

    Attributes:
        metrics_id: Unique identifier for this metrics record
        realm_id: Realm identifier
        cycle_id: Governance cycle identifier (format: YYYY-Wnn)
        escalation_count: Petitions escalated to this realm this cycle
        adoption_count: Petitions adopted by this realm's King this cycle
        adoption_ratio: adoption_count / escalation_count (None if no escalations)
        adopting_kings: List of King UUIDs who performed adoptions this cycle
        computed_at: When these metrics were computed (UTC)
    """

    metrics_id: UUID
    realm_id: str
    cycle_id: str
    escalation_count: int
    adoption_count: int
    adoption_ratio: float | None
    adopting_kings: tuple[UUID, ...]
    computed_at: datetime

    @classmethod
    def compute(
        cls,
        realm_id: str,
        cycle_id: str,
        escalation_count: int,
        adoption_count: int,
        adopting_kings: list[UUID] | tuple[UUID, ...],
    ) -> AdoptionRatioMetrics:
        """Compute adoption ratio metrics for a realm/cycle (PREVENT-7).

        Args:
            realm_id: Realm identifier
            cycle_id: Governance cycle identifier (e.g., "2026-W04")
            escalation_count: Count of petitions escalated to this realm
            adoption_count: Count of petitions adopted by this realm's King
            adopting_kings: List of King UUIDs who performed adoptions

        Returns:
            AdoptionRatioMetrics instance with computed ratio.
        """
        # Compute adoption ratio (PREVENT-7: None if no escalations)
        ratio = None if escalation_count == 0 else adoption_count / escalation_count

        return cls(
            metrics_id=uuid4(),
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=escalation_count,
            adoption_count=adoption_count,
            adoption_ratio=ratio,
            adopting_kings=tuple(adopting_kings),
            computed_at=datetime.now(timezone.utc),
        )

    def exceeds_threshold(self, threshold: float = 0.50) -> bool:
        """Check if adoption ratio exceeds alert threshold (PREVENT-7).

        Args:
            threshold: Maximum acceptable adoption ratio (default: 0.50)

        Returns:
            True if ratio > threshold, False otherwise.
            Returns False if no ratio (no escalations).
        """
        if self.adoption_ratio is None:
            return False
        return self.adoption_ratio > threshold

    def severity(self) -> str | None:
        """Get alert severity based on adoption ratio (PREVENT-7).

        Returns:
            None if ratio <= 0.50 or no data
            "WARN" if 0.50 < ratio <= 0.70
            "CRITICAL" if ratio > 0.70
        """
        if self.adoption_ratio is None or self.adoption_ratio <= 0.50:
            return None
        elif self.adoption_ratio <= 0.70:
            return "WARN"
        else:
            return "CRITICAL"

    def health_status(self) -> str:
        """Get health status based on adoption ratio (for dashboard).

        Returns:
            "NO_DATA" if no escalations
            "HEALTHY" if ratio <= 0.50
            "WARN" if 0.50 < ratio <= 0.70
            "CRITICAL" if ratio > 0.70
        """
        if self.adoption_ratio is None:
            return "NO_DATA"
        elif self.adoption_ratio <= 0.50:
            return "HEALTHY"
        elif self.adoption_ratio <= 0.70:
            return "WARN"
        else:
            return "CRITICAL"


@dataclass(frozen=True)
class AdoptionRatioAlert:
    """Alert for excessive adoption ratio (Story 8.6, PREVENT-7).

    Raised when a realm's adoption ratio exceeds the 50% threshold.
    Alert severity escalates based on the ratio:
    - WARN: 50% < ratio <= 70%
    - CRITICAL: ratio > 70%

    Constitutional Requirements:
    - PREVENT-7: Alert on excessive adoption ratio
    - CT-12: Events witnessed and immutable

    Attributes:
        alert_id: Unique alert identifier
        realm_id: Realm with excessive adoption ratio
        cycle_id: Governance cycle when detected
        adoption_count: Number of adoptions in the cycle
        escalation_count: Number of escalations in the cycle
        adoption_ratio: The computed ratio (0.0 to 1.0)
        threshold: Threshold that was exceeded (0.50)
        adopting_kings: Kings who performed adoptions
        severity: WARN (50-70%) or CRITICAL (>70%)
        trend_delta: Change from previous cycle (positive = increasing)
        created_at: When alert was created (UTC)
        resolved_at: When alert was resolved (if applicable)
        status: ACTIVE or RESOLVED
    """

    alert_id: UUID
    realm_id: str
    cycle_id: str
    adoption_count: int
    escalation_count: int
    adoption_ratio: float
    threshold: float
    adopting_kings: tuple[UUID, ...]
    severity: str  # "WARN" or "CRITICAL"
    trend_delta: float | None
    created_at: datetime
    resolved_at: datetime | None
    status: str  # "ACTIVE" or "RESOLVED"

    @classmethod
    def create(
        cls,
        realm_id: str,
        cycle_id: str,
        metrics: AdoptionRatioMetrics,
        trend_delta: float | None = None,
        threshold: float = 0.50,
    ) -> AdoptionRatioAlert:
        """Create a new adoption ratio alert from metrics (PREVENT-7).

        Args:
            realm_id: Realm identifier
            cycle_id: Governance cycle identifier
            metrics: Computed adoption ratio metrics
            trend_delta: Change from previous cycle (optional)
            threshold: Alert threshold (default: 0.50)

        Returns:
            AdoptionRatioAlert instance.

        Raises:
            ValueError: If metrics do not exceed threshold.
        """
        if metrics.adoption_ratio is None:
            raise ValueError("Cannot create alert: no adoption ratio data")

        if not metrics.exceeds_threshold(threshold):
            raise ValueError(
                f"Cannot create alert: ratio {metrics.adoption_ratio} "
                f"does not exceed threshold {threshold}"
            )

        severity = metrics.severity()
        if severity is None:
            severity = "WARN"  # Default fallback

        return cls(
            alert_id=uuid4(),
            realm_id=realm_id,
            cycle_id=cycle_id,
            adoption_count=metrics.adoption_count,
            escalation_count=metrics.escalation_count,
            adoption_ratio=metrics.adoption_ratio,
            threshold=threshold,
            adopting_kings=metrics.adopting_kings,
            severity=severity,
            trend_delta=trend_delta,
            created_at=datetime.now(timezone.utc),
            resolved_at=None,
            status="ACTIVE",
        )

    def resolve(self, resolved_at: datetime | None = None) -> AdoptionRatioAlert:
        """Create a resolved copy of this alert.

        Args:
            resolved_at: When the alert was resolved (defaults to now)

        Returns:
            New AdoptionRatioAlert instance with RESOLVED status.
        """
        if resolved_at is None:
            resolved_at = datetime.now(timezone.utc)

        return AdoptionRatioAlert(
            alert_id=self.alert_id,
            realm_id=self.realm_id,
            cycle_id=self.cycle_id,
            adoption_count=self.adoption_count,
            escalation_count=self.escalation_count,
            adoption_ratio=self.adoption_ratio,
            threshold=self.threshold,
            adopting_kings=self.adopting_kings,
            severity=self.severity,
            trend_delta=self.trend_delta,
            created_at=self.created_at,
            resolved_at=resolved_at,
            status="RESOLVED",
        )

    def alert_duration_seconds(self, resolved_at: datetime | None = None) -> int:
        """Calculate alert duration in seconds.

        Args:
            resolved_at: When the alert was resolved (defaults to now)

        Returns:
            Duration in seconds the alert was active.
        """
        if resolved_at is None:
            resolved_at = datetime.now(timezone.utc)

        duration = resolved_at - self.created_at
        return int(duration.total_seconds())

    @property
    def is_active(self) -> bool:
        """Check if alert is currently active."""
        return self.status == "ACTIVE"
