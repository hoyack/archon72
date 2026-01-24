"""Legitimacy alert state domain model (Story 8.2, FR-8.3, NFR-7.2).

This module defines the domain model for tracking active legitimacy alert
state to prevent alert flapping and manage alert lifecycle.

Constitutional Constraints:
- FR-8.3: System SHALL alert on decay below 0.85 threshold [P1]
- NFR-7.2: Legitimacy decay alerting - Alert at < 0.85 threshold
- CT-12: Witnessing creates accountability -> Alert events are witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.events.legitimacy_alert import AlertSeverity


@dataclass(frozen=False)
class LegitimacyAlertState:
    """Alert state tracker to prevent flapping (Story 8.2, FR-8.3).

    Tracks the current state of legitimacy alerting to ensure:
    1. Only one active alert at a time (no duplicates)
    2. Hysteresis prevents flapping from fluctuating scores
    3. Alert duration is tracked for recovery notifications

    This is a mutable aggregate (not frozen) because it tracks state
    across multiple cycles and is updated as metrics are computed.

    Constitutional Requirements:
    - FR-8.3: Alert triggering and recovery
    - NFR-7.2: Alert within 1 minute of trigger

    Attributes:
        alert_id: Unique identifier for the current alert (None if no alert active)
        is_active: Whether an alert is currently active
        severity: Current alert severity (WARNING or CRITICAL)
        triggered_at: When the current alert was first triggered (UTC)
        last_updated: When this state was last updated (UTC)
        consecutive_breaches: Count of consecutive cycles below threshold
        triggered_cycle_id: Cycle ID when alert was triggered
        triggered_score: Score that triggered the alert
    """

    alert_id: UUID | None
    is_active: bool
    severity: AlertSeverity | None
    triggered_at: datetime | None
    last_updated: datetime
    consecutive_breaches: int
    triggered_cycle_id: str | None
    triggered_score: float | None

    @classmethod
    def no_alert(cls, last_updated: datetime) -> LegitimacyAlertState:
        """Create an alert state with no active alert.

        Args:
            last_updated: Timestamp for this state snapshot (UTC)

        Returns:
            LegitimacyAlertState with is_active=False.
        """
        return cls(
            alert_id=None,
            is_active=False,
            severity=None,
            triggered_at=None,
            last_updated=last_updated,
            consecutive_breaches=0,
            triggered_cycle_id=None,
            triggered_score=None,
        )

    @classmethod
    def active_alert(
        cls,
        alert_id: UUID,
        severity: AlertSeverity,
        triggered_at: datetime,
        triggered_cycle_id: str,
        triggered_score: float,
        consecutive_breaches: int = 1,
    ) -> LegitimacyAlertState:
        """Create an alert state with an active alert.

        Args:
            alert_id: Unique identifier for this alert
            severity: Alert severity (WARNING or CRITICAL)
            triggered_at: When the alert was triggered (UTC)
            triggered_cycle_id: Cycle ID that triggered the alert
            triggered_score: Score that triggered the alert
            consecutive_breaches: Count of consecutive breaches (default: 1)

        Returns:
            LegitimacyAlertState with is_active=True.
        """
        return cls(
            alert_id=alert_id,
            is_active=True,
            severity=severity,
            triggered_at=triggered_at,
            last_updated=triggered_at,
            consecutive_breaches=consecutive_breaches,
            triggered_cycle_id=triggered_cycle_id,
            triggered_score=triggered_score,
        )

    def update_breach_count(
        self, new_score: float, new_severity: AlertSeverity, updated_at: datetime
    ) -> None:
        """Update consecutive breach count for an active alert.

        Args:
            new_score: The latest legitimacy score
            new_severity: The new severity level (for logging, not persisted)
            updated_at: When this update occurred (UTC)

        Note:
            Severity is NOT updated - an alert maintains its original severity
            until recovery. This prevents alert "downgrade" confusion where a
            CRITICAL alert becomes WARNING as the score improves.
        """
        if not self.is_active:
            raise ValueError("Cannot update breach count when no alert is active")

        self.consecutive_breaches += 1
        # Note: Do NOT update self.severity - alert maintains original severity until recovery
        # Note: Do NOT update self.triggered_score - preserve original trigger score
        self.last_updated = updated_at

    def clear_alert(self, recovered_at: datetime) -> None:
        """Clear the active alert (recovery).

        Args:
            recovered_at: When the alert was resolved (UTC)
        """
        if not self.is_active:
            raise ValueError("Cannot clear alert when no alert is active")

        self.is_active = False
        self.last_updated = recovered_at

    def alert_duration_seconds(self, recovered_at: datetime) -> int:
        """Calculate alert duration in seconds.

        Args:
            recovered_at: When the alert was resolved (UTC)

        Returns:
            Duration in seconds the alert was active.

        Raises:
            ValueError: If no alert is active or triggered_at is None.
        """
        if not self.is_active or self.triggered_at is None:
            raise ValueError("Cannot calculate duration when no alert is active")

        duration = recovered_at - self.triggered_at
        return int(duration.total_seconds())
