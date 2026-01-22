"""Legitimacy alerting service (Story 8.2, FR-8.3, NFR-7.2).

This service implements alert triggering, hysteresis, and flap detection
logic for legitimacy decay monitoring.

Constitutional Constraints:
- FR-8.3: System SHALL alert on decay below 0.85 threshold [P1]
- NFR-7.2: Alert delivery within 1 minute of trigger
- CT-12: Alert events are witnessed
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from src.domain.events.legitimacy_alert import (
    AlertSeverity,
    LegitimacyAlertRecoveredEvent,
    LegitimacyAlertTriggeredEvent,
)
from src.domain.models.legitimacy_alert_state import LegitimacyAlertState
from src.domain.models.legitimacy_metrics import LegitimacyMetrics


class PetitionRepositoryProtocol(Protocol):
    """Protocol for querying petition data."""

    async def count_stuck_petitions(self, cycle_id: str, sla_hours: int = 24) -> int:
        """Count petitions not fated within SLA for a cycle.

        Args:
            cycle_id: Governance cycle identifier (e.g., "2026-W04")
            sla_hours: SLA threshold in hours (default: 24)

        Returns:
            Count of petitions in non-terminal state beyond SLA.
        """
        ...


class LegitimacyAlertingService:
    """Service for legitimacy decay alerting (Story 8.2, FR-8.3).

    This service implements the core alerting logic including:
    1. Alert triggering when legitimacy score drops below thresholds
    2. Hysteresis to prevent flapping from fluctuating scores
    3. Flap detection via consecutive breach counting
    4. Alert recovery when score improves

    Constitutional Requirements:
    - FR-8.3: Alert at < 0.85 threshold (WARNING), < 0.70 (CRITICAL)
    - NFR-7.2: Alert delivery within 1 minute
    """

    def __init__(
        self,
        petition_repo: PetitionRepositoryProtocol,
        warning_threshold: float = 0.85,
        critical_threshold: float = 0.70,
        hysteresis_buffer: float = 0.02,
        min_consecutive_breaches: int = 1,
    ):
        """Initialize alerting service with configurable thresholds.

        Args:
            petition_repo: Repository for querying petition data
            warning_threshold: Score threshold for WARNING alert (default: 0.85)
            critical_threshold: Score threshold for CRITICAL alert (default: 0.70)
            hysteresis_buffer: Buffer for recovery (default: 0.02)
            min_consecutive_breaches: Minimum consecutive cycles below threshold
                                      before triggering alert (default: 1)

        Raises:
            ValueError: If thresholds are invalid (e.g., WARNING < CRITICAL)
        """
        if critical_threshold >= warning_threshold:
            raise ValueError(
                f"CRITICAL threshold ({critical_threshold}) must be less than "
                f"WARNING threshold ({warning_threshold})"
            )

        if hysteresis_buffer < 0 or hysteresis_buffer > 0.1:
            raise ValueError(f"Hysteresis buffer ({hysteresis_buffer}) must be between 0.0 and 0.1")

        if min_consecutive_breaches < 1:
            raise ValueError(f"min_consecutive_breaches ({min_consecutive_breaches}) must be >= 1")

        self.petition_repo = petition_repo
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.hysteresis_buffer = hysteresis_buffer
        self.min_consecutive_breaches = min_consecutive_breaches

    async def check_and_alert(
        self,
        metrics: LegitimacyMetrics,
        previous_state: LegitimacyAlertState | None,
    ) -> tuple[LegitimacyAlertTriggeredEvent | None, LegitimacyAlertRecoveredEvent | None]:
        """Check metrics and determine if alert should trigger or recover.

        This is the main entry point for alert processing. It implements:
        1. Alert trigger detection with severity determination
        2. Recovery detection with hysteresis
        3. Flap detection via consecutive breach counting
        4. Alert state updates

        Args:
            metrics: Computed legitimacy metrics for a cycle
            previous_state: Previous alert state (None if first run)

        Returns:
            Tuple of (trigger_event, recovery_event). One or both may be None.
            - trigger_event: Created when alert threshold is breached
            - recovery_event: Created when alert recovers above threshold

        Constitutional Requirements:
        - FR-8.3: Alert at < 0.85 (WARNING), < 0.70 (CRITICAL)
        - NFR-7.2: Check completes within 1 minute
        """
        now = datetime.now(timezone.utc)

        # If no previous state, initialize with no alert
        if previous_state is None:
            previous_state = LegitimacyAlertState.no_alert(last_updated=now)

        # Determine if score breaches threshold
        severity = self._determine_severity(metrics.legitimacy_score)
        breaches_threshold = severity is not None

        # Handle active alert - check for recovery or update
        if previous_state.is_active:
            return await self._handle_active_alert(
                metrics, previous_state, breaches_threshold, severity, now
            )

        # Handle no active alert - check for trigger
        if breaches_threshold:
            return await self._handle_alert_trigger(
                metrics, previous_state, severity, now
            )

        # No alert and no breach - reset state
        previous_state.consecutive_breaches = 0
        previous_state.last_updated = now
        return (None, None)

    async def _handle_active_alert(
        self,
        metrics: LegitimacyMetrics,
        state: LegitimacyAlertState,
        breaches_threshold: bool,
        severity: AlertSeverity | None,
        now: datetime,
    ) -> tuple[LegitimacyAlertTriggeredEvent | None, LegitimacyAlertRecoveredEvent | None]:
        """Handle alert logic when an alert is currently active.

        Args:
            metrics: Current legitimacy metrics
            state: Current alert state
            breaches_threshold: Whether score breaches threshold
            severity: Alert severity (None if no breach)
            now: Current timestamp

        Returns:
            Tuple of (trigger_event, recovery_event).
        """
        # Check for recovery with hysteresis
        if self._should_recover(metrics.legitimacy_score, state.severity):
            return await self._trigger_recovery(metrics, state, now)

        # Still breaching - update breach count and severity
        if breaches_threshold and severity is not None and metrics.legitimacy_score is not None:
            state.update_breach_count(metrics.legitimacy_score, severity, now)

        return (None, None)

    async def _handle_alert_trigger(
        self,
        metrics: LegitimacyMetrics,
        state: LegitimacyAlertState,
        severity: AlertSeverity | None,
        now: datetime,
    ) -> tuple[LegitimacyAlertTriggeredEvent | None, LegitimacyAlertRecoveredEvent | None]:
        """Handle alert trigger logic when no alert is currently active.

        Args:
            metrics: Current legitimacy metrics
            state: Current alert state
            severity: Alert severity
            now: Current timestamp

        Returns:
            Tuple of (trigger_event, None) if triggered, else (None, None).
        """
        if severity is None or metrics.legitimacy_score is None:
            return (None, None)

        # Increment consecutive breach count
        state.consecutive_breaches += 1
        state.last_updated = now

        # Check if we've met the flap detection threshold
        if state.consecutive_breaches < self.min_consecutive_breaches:
            # Not enough consecutive breaches - wait
            return (None, None)

        # Trigger alert
        alert_id = uuid4()
        stuck_count = await self.petition_repo.count_stuck_petitions(metrics.cycle_id)

        # Update state to active
        new_state = LegitimacyAlertState.active_alert(
            alert_id=alert_id,
            severity=severity,
            triggered_at=now,
            triggered_cycle_id=metrics.cycle_id,
            triggered_score=metrics.legitimacy_score,
            consecutive_breaches=state.consecutive_breaches,
        )

        # Copy new state back to previous state (mutate in place)
        state.alert_id = new_state.alert_id
        state.is_active = new_state.is_active
        state.severity = new_state.severity
        state.triggered_at = new_state.triggered_at
        state.last_updated = new_state.last_updated
        state.triggered_cycle_id = new_state.triggered_cycle_id
        state.triggered_score = new_state.triggered_score

        # Create trigger event
        trigger_event = LegitimacyAlertTriggeredEvent(
            alert_id=alert_id,
            cycle_id=metrics.cycle_id,
            current_score=metrics.legitimacy_score,
            threshold=self._get_threshold_for_severity(severity),
            severity=severity,
            stuck_petition_count=stuck_count,
            triggered_at=now,
        )

        return (trigger_event, None)

    async def _trigger_recovery(
        self,
        metrics: LegitimacyMetrics,
        state: LegitimacyAlertState,
        now: datetime,
    ) -> tuple[None, LegitimacyAlertRecoveredEvent]:
        """Trigger alert recovery.

        Args:
            metrics: Current legitimacy metrics
            state: Current alert state
            now: Current timestamp

        Returns:
            Tuple of (None, recovery_event).
        """
        if state.alert_id is None or state.triggered_score is None:
            raise ValueError("Cannot recover alert without alert_id and triggered_score")

        # Calculate alert duration
        alert_duration = state.alert_duration_seconds(now)

        # Create recovery event
        recovery_event = LegitimacyAlertRecoveredEvent(
            recovery_id=uuid4(),
            alert_id=state.alert_id,
            cycle_id=metrics.cycle_id,
            current_score=metrics.legitimacy_score or 0.0,
            previous_score=state.triggered_score,
            alert_duration_seconds=alert_duration,
            recovered_at=now,
        )

        # Clear alert state
        state.clear_alert(recovered_at=now)
        state.consecutive_breaches = 0

        return (None, recovery_event)

    def _determine_severity(self, score: float | None) -> AlertSeverity | None:
        """Determine alert severity based on legitimacy score.

        Args:
            score: Legitimacy score (0.0-1.0), or None if no petitions

        Returns:
            AlertSeverity (WARNING or CRITICAL) if threshold breached, else None.

        Constitutional Requirement:
        - FR-8.3: WARNING at < 0.85, CRITICAL at < 0.70
        """
        if score is None:
            # No petitions - treat as healthy (no alert)
            return None

        if score < self.critical_threshold:
            return AlertSeverity.CRITICAL
        elif score < self.warning_threshold:
            return AlertSeverity.WARNING
        else:
            return None

    def _should_recover(self, score: float | None, current_severity: AlertSeverity | None) -> bool:
        """Check if alert should recover (with hysteresis).

        Recovery requires score to exceed threshold + hysteresis_buffer to prevent flapping.

        Args:
            score: Current legitimacy score
            current_severity: Current alert severity

        Returns:
            True if alert should recover, False otherwise.
        """
        if score is None or current_severity is None:
            return False

        # Determine recovery threshold with hysteresis
        if current_severity == AlertSeverity.CRITICAL:
            recovery_threshold = self.critical_threshold + self.hysteresis_buffer
        else:  # WARNING
            recovery_threshold = self.warning_threshold + self.hysteresis_buffer

        return score >= recovery_threshold

    def _get_threshold_for_severity(self, severity: AlertSeverity) -> float:
        """Get the threshold value for a given severity.

        Args:
            severity: Alert severity

        Returns:
            Threshold value (0.85 for WARNING, 0.70 for CRITICAL).
        """
        if severity == AlertSeverity.CRITICAL:
            return self.critical_threshold
        else:  # WARNING
            return self.warning_threshold
