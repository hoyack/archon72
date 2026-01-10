"""Override Daily Threshold Monitor (Story 8.4, FR145).

This service monitors daily override counts and triggers incident reports
when the threshold is exceeded (>3 overrides in a single day).

Constitutional Constraints:
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- CT-11: HALT CHECK FIRST - Check halt state before write operations
- CT-12: All incident events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating incidents
2. WITNESS EVERYTHING - Incident creation events must be witnessed
3. FAIL LOUD - Never silently swallow monitoring errors
4. NO DUPLICATES - Don't create duplicate incidents for same day
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from structlog import get_logger

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.override_trend_repository import (
    OverrideTrendRepositoryProtocol,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.incident_report import (
    DAILY_OVERRIDE_THRESHOLD,
    IncidentReport,
    IncidentType,
    TimelineEntry,
)

if TYPE_CHECKING:
    from src.application.ports.incident_report_repository import (
        IncidentReportRepositoryPort,
    )
    from src.application.services.incident_reporting_service import (
        IncidentReportingService,
    )

logger = get_logger()

# System agent ID for the monitor
OVERRIDE_MONITOR_SYSTEM_AGENT_ID: str = "system.override_daily_monitor"


@dataclass(frozen=True)
class DailyOverrideCheckResult:
    """Result of daily override threshold check.

    Attributes:
        date: The date checked (UTC).
        override_count: Number of overrides on that date.
        threshold: The threshold value (3 by default).
        threshold_exceeded: Whether the threshold was exceeded.
        incident_created: Whether a new incident was created.
        existing_incident_id: ID of existing incident if one already exists.
    """

    date: datetime
    override_count: int
    threshold: int
    threshold_exceeded: bool
    incident_created: bool
    existing_incident_id: Optional[str]


class OverrideDailyThresholdMonitor:
    """Monitors daily override counts and triggers incident reports (FR145).

    This service checks if the daily override count exceeds the threshold
    (>3 per FR145) and creates incident reports when necessary.

    Constitutional Constraints:
    - FR145: >3 overrides/day requires incident report
    - CT-11: HALT CHECK FIRST - Check halt state before write operations
    - CT-12: All incident events MUST be witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Check halt state before creating incidents
    2. WITNESS EVERYTHING - Incident events are witnessed via IncidentReportingService
    3. FAIL LOUD - Never suppress monitoring errors
    4. NO DUPLICATES - Check for existing incident before creating new one
    """

    def __init__(
        self,
        override_repository: OverrideTrendRepositoryProtocol,
        incident_repository: IncidentReportRepositoryPort,
        incident_service: IncidentReportingService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the daily threshold monitor.

        Args:
            override_repository: Repository for querying override history.
            incident_repository: Repository for checking existing incidents.
            incident_service: Service for creating incident reports.
            halt_checker: Service for checking halt state.
        """
        self._override_repository = override_repository
        self._incident_repository = incident_repository
        self._incident_service = incident_service
        self._halt_checker = halt_checker
        self._log = logger.bind(service="OverrideDailyThresholdMonitor")

    async def check_daily_threshold(
        self,
        date: Optional[datetime] = None,
    ) -> DailyOverrideCheckResult:
        """Check if daily override threshold is exceeded (FR145).

        This method checks the override count for a specific date and creates
        an incident report if the threshold (>3) is exceeded.

        Developer Golden Rule: HALT CHECK FIRST (CT-11 pattern)

        Args:
            date: The date to check (defaults to today UTC).

        Returns:
            DailyOverrideCheckResult with check details and incident status.

        Raises:
            SystemHaltedError: If system is halted and incident creation needed.
        """
        check_date = date or datetime.now(timezone.utc)
        log = self._log.bind(
            operation="check_daily_threshold",
            date=check_date.date().isoformat(),
            threshold=DAILY_OVERRIDE_THRESHOLD,
        )

        log.info("checking_daily_override_threshold")

        # Get override count for the date
        start_of_day = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = check_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        override_count = await self._override_repository.get_override_count_for_period(
            start_date=start_of_day,
            end_date=end_of_day,
        )

        threshold_exceeded = override_count > DAILY_OVERRIDE_THRESHOLD

        log.info(
            "daily_threshold_check_complete",
            override_count=override_count,
            threshold_exceeded=threshold_exceeded,
        )

        if not threshold_exceeded:
            return DailyOverrideCheckResult(
                date=check_date,
                override_count=override_count,
                threshold=DAILY_OVERRIDE_THRESHOLD,
                threshold_exceeded=False,
                incident_created=False,
                existing_incident_id=None,
            )

        # Threshold exceeded - check for existing incident for this date
        existing_count = await self._incident_repository.count_by_type_and_date(
            incident_type=IncidentType.OVERRIDE_THRESHOLD,
            date=check_date,
        )

        if existing_count > 0:
            log.info(
                "incident_already_exists_for_date",
                existing_count=existing_count,
            )
            return DailyOverrideCheckResult(
                date=check_date,
                override_count=override_count,
                threshold=DAILY_OVERRIDE_THRESHOLD,
                threshold_exceeded=True,
                incident_created=False,
                existing_incident_id="(existing)",  # Simplified - actual ID lookup could be added
            )

        # HALT CHECK FIRST (CT-11 pattern)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.warning(
                "incident_creation_blocked_system_halted",
                reason=reason,
            )
            raise SystemHaltedError(
                f"CT-11: System is halted, cannot create incident report: {reason}"
            )

        # Create incident report for threshold exceedance
        log.info(
            "creating_override_threshold_incident",
            override_count=override_count,
        )

        # Create timeline entry for the detection
        timeline = [
            TimelineEntry(
                timestamp=datetime.now(timezone.utc),
                description=f"Override daily threshold ({DAILY_OVERRIDE_THRESHOLD}) exceeded with {override_count} overrides",
                actor=OVERRIDE_MONITOR_SYSTEM_AGENT_ID,
            ),
        ]

        # Note: We need to get the actual override event IDs for this date
        # For now, we create the incident without specific event IDs
        # The incident service will populate with empty list if not provided
        incident = await self._incident_service.create_override_threshold_incident(
            override_event_ids=[],  # Would need to query for actual event IDs
            keeper_ids=[],  # Would need to extract from overrides
            timeline=timeline,
        )

        log.info(
            "override_threshold_incident_created",
            incident_id=str(incident.incident_id),
        )

        return DailyOverrideCheckResult(
            date=check_date,
            override_count=override_count,
            threshold=DAILY_OVERRIDE_THRESHOLD,
            threshold_exceeded=True,
            incident_created=True,
            existing_incident_id=str(incident.incident_id),
        )

    async def run_monitoring_cycle(self) -> DailyOverrideCheckResult:
        """Run a single monitoring cycle for today's date.

        This is a convenience method for scheduled monitoring.

        Returns:
            DailyOverrideCheckResult for today's check.

        Raises:
            SystemHaltedError: If system is halted and incident creation needed.
        """
        log = self._log.bind(operation="run_monitoring_cycle")
        log.info("starting_monitoring_cycle")

        result = await self.check_daily_threshold()

        log.info(
            "monitoring_cycle_complete",
            threshold_exceeded=result.threshold_exceeded,
            incident_created=result.incident_created,
        )

        return result

    async def get_current_daily_count(self) -> int:
        """Get the current override count for today (read-only).

        This method works during halt (CT-13: reads always allowed).

        Returns:
            Current override count for today.
        """
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        return await self._override_repository.get_override_count_for_period(
            start_date=start_of_day,
            end_date=end_of_day,
        )
