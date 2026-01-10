"""Override Trend Analysis Service (Story 5.5, FR27, RT-3, ADR-7).

This service analyzes override trends and triggers alerts when thresholds
are exceeded. It implements the Rules layer of the ADR-7 aggregate anomaly
detection system.

Constitutional Constraints:
- FR27: Override trend analysis with anti-success alerts
- RT-3: >20 overrides in 365-day window triggers governance review
- CT-11: HALT CHECK FIRST - Check halt state before any operation
- CT-12: All alert events MUST be witnessed
- ADR-7: Rules layer of aggregate anomaly detection

Threshold Definitions (from FR27 and RT-3):
- >50% increase in 30 days vs previous 30 days -> AntiSuccessAlert
- >5 overrides in any 30-day period -> AntiSuccessAlert (THRESHOLD_30_DAY)
- >20 overrides in 365-day rolling window -> GovernanceReviewRequired (RT-3)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from structlog import get_logger

# System agent ID for trend analysis events (automated system, not human agent)
TREND_ANALYSIS_SYSTEM_AGENT_ID: str = "system.trend_analysis"

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.override_trend_repository import (
    OverrideTrendData,
    OverrideTrendRepositoryProtocol,
)
from src.domain.errors.trend import InsufficientDataError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.anti_success_alert import (
    ANTI_SUCCESS_ALERT_EVENT_TYPE,
    AlertType,
    AntiSuccessAlertPayload,
)
from src.domain.events.governance_review_required import (
    GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE,
    GovernanceReviewRequiredPayload,
    RT3_THRESHOLD,
    RT3_WINDOW_DAYS,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()


@dataclass(frozen=True)
class AntiSuccessAnalysisResult:
    """Result of 50% increase analysis.

    Attributes:
        alert_triggered: Whether the threshold was exceeded.
        before_count: Override count in comparison period.
        after_count: Override count in current period.
        percentage_change: Calculated percentage change.
        event_written: Whether an alert event was written.
    """

    alert_triggered: bool
    before_count: int
    after_count: int
    percentage_change: float
    event_written: bool


@dataclass(frozen=True)
class ThresholdCheckResult:
    """Result of threshold check (30-day or 365-day).

    Attributes:
        threshold_exceeded: Whether the threshold was exceeded.
        count: The override count in the window.
        threshold: The threshold value.
        event_written: Whether an alert event was written.
    """

    threshold_exceeded: bool
    count: int
    threshold: int
    event_written: bool


@dataclass(frozen=True)
class TrendAnalysisReport:
    """Comprehensive trend analysis report.

    Aggregates results from all analysis methods.

    Attributes:
        trend_data: The 90-day rolling trend data (AC1).
        anti_success_50_percent: Result of 50% increase analysis (AC2).
        threshold_30_day: Result of 30-day threshold check (AC3).
        governance_365_day: Result of 365-day governance trigger (AC4, RT-3).
        analyzed_at: When the analysis was performed (UTC).
    """

    trend_data: OverrideTrendData
    anti_success_50_percent: AntiSuccessAnalysisResult
    threshold_30_day: ThresholdCheckResult
    governance_365_day: ThresholdCheckResult
    analyzed_at: datetime


class OverrideTrendAnalysisService:
    """Analyzes override trends and triggers alerts (FR27, RT-3, ADR-7).

    This service implements the Rules layer of the ADR-7 aggregate anomaly
    detection system. It detects override abuse patterns and triggers
    appropriate alerts.

    Constitutional Constraints:
    - FR27: Override trend analysis with anti-success alerts
    - RT-3: >20 overrides in 365-day window triggers governance review
    - CT-11: HALT CHECK FIRST - Check halt state before any operation
    - CT-12: All alert events MUST be witnessed
    - ADR-7: Rules layer of aggregate anomaly detection

    Developer Golden Rules:
    1. HALT FIRST - Check halt state before analysis operations
    2. SIGN COMPLETE - Alert events include signable_content()
    3. WITNESS EVERYTHING - All alerts must be witnessed via EventWriterService
    4. FAIL LOUD - Never suppress errors

    Threshold Constants:
    - PERCENTAGE_THRESHOLD: 50.0 (>50% increase triggers alert)
    - THRESHOLD_30_DAY: 5 (>5 overrides in 30 days)
    - THRESHOLD_365_DAY: 20 (>20 overrides in 365 days, RT-3)
    """

    # Threshold constants (from FR27 and RT-3)
    PERCENTAGE_THRESHOLD: float = 50.0  # >50% increase triggers alert
    THRESHOLD_30_DAY: int = 5  # >5 overrides in 30 days
    THRESHOLD_365_DAY: int = RT3_THRESHOLD  # >20 overrides in 365 days (RT-3)

    def __init__(
        self,
        trend_repository: OverrideTrendRepositoryProtocol,
        event_writer: Optional[EventWriterService],
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the trend analysis service.

        Args:
            trend_repository: Repository for querying override history.
            event_writer: Service for writing alert events (optional for query-only).
            halt_checker: Service for checking halt state.
        """
        self._trend_repository = trend_repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker
        self._log = logger.bind(service="OverrideTrendAnalysisService")

    async def get_90_day_trend(self) -> OverrideTrendData:
        """Get 90-day rolling trend data (AC1).

        Returns the override trend data for the last 90 days including
        total count, daily rate, and time boundaries.

        Returns:
            OverrideTrendData with count, rate, and time boundaries.

        Raises:
            InsufficientDataError: If unable to retrieve trend data.
        """
        log = self._log.bind(operation="get_90_day_trend", window_days=90)
        log.info("retrieving_90_day_trend")

        try:
            trend_data = await self._trend_repository.get_rolling_trend(days=90)
            log.info(
                "trend_data_retrieved",
                total_count=trend_data.total_count,
                daily_rate=trend_data.daily_rate,
            )
            return trend_data
        except Exception as e:
            log.error("trend_retrieval_failed", error=str(e))
            raise InsufficientDataError(f"FR27: Failed to retrieve 90-day trend: {e}")

    async def analyze_50_percent_increase(self) -> AntiSuccessAnalysisResult:
        """Analyze for >50% increase in override count (AC2).

        Compares current 30-day count vs previous 30-day count.
        If increase >50%, writes AntiSuccessAlert event.

        Returns:
            AntiSuccessAnalysisResult with analysis details and alert status.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            InsufficientDataError: If unable to retrieve comparison data.
        """
        log = self._log.bind(
            operation="analyze_50_percent_increase",
            threshold=self.PERCENTAGE_THRESHOLD,
        )

        # Get current 30-day count
        now = datetime.now(timezone.utc)
        current_end = now
        current_start = now - timedelta(days=30)
        previous_end = current_start
        previous_start = previous_end - timedelta(days=30)

        try:
            after_count = await self._trend_repository.get_override_count_for_period(
                start_date=current_start,
                end_date=current_end,
            )
            before_count = await self._trend_repository.get_override_count_for_period(
                start_date=previous_start,
                end_date=previous_end,
            )
        except Exception as e:
            log.error("period_count_retrieval_failed", error=str(e))
            raise InsufficientDataError(
                f"FR27: Failed to retrieve period counts: {e}"
            )

        # Calculate percentage change (handle zero division)
        if before_count == 0:
            percentage_change = 100.0 if after_count > 0 else 0.0
        else:
            percentage_change = ((after_count - before_count) / before_count) * 100.0

        alert_triggered = percentage_change > self.PERCENTAGE_THRESHOLD
        event_written = False

        log.info(
            "percentage_analysis_complete",
            before_count=before_count,
            after_count=after_count,
            percentage_change=percentage_change,
            alert_triggered=alert_triggered,
        )

        if alert_triggered and self._event_writer:
            # Write alert event (CT-12: must be witnessed)
            payload = AntiSuccessAlertPayload(
                alert_type=AlertType.PERCENTAGE_INCREASE,
                before_count=before_count,
                after_count=after_count,
                percentage_change=percentage_change,
                window_days=30,
                detected_at=now,
            )
            await self._write_anti_success_alert(payload)
            event_written = True

        return AntiSuccessAnalysisResult(
            alert_triggered=alert_triggered,
            before_count=before_count,
            after_count=after_count,
            percentage_change=percentage_change,
            event_written=event_written,
        )

    async def check_30_day_threshold(self) -> ThresholdCheckResult:
        """Check 30-day threshold (>5 overrides) (AC3).

        If more than 5 overrides in the last 30 days, writes
        AntiSuccessAlert event with THRESHOLD_30_DAY type.

        Returns:
            ThresholdCheckResult with threshold check details.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = self._log.bind(
            operation="check_30_day_threshold",
            threshold=self.THRESHOLD_30_DAY,
        )

        count = await self._trend_repository.get_override_count(days=30)
        threshold_exceeded = count > self.THRESHOLD_30_DAY
        event_written = False

        log.info(
            "30_day_threshold_check",
            count=count,
            threshold=self.THRESHOLD_30_DAY,
            exceeded=threshold_exceeded,
        )

        if threshold_exceeded and self._event_writer:
            now = datetime.now(timezone.utc)
            payload = AntiSuccessAlertPayload(
                alert_type=AlertType.THRESHOLD_30_DAY,
                before_count=self.THRESHOLD_30_DAY,  # threshold as reference
                after_count=count,
                percentage_change=((count - self.THRESHOLD_30_DAY) / self.THRESHOLD_30_DAY) * 100.0,
                window_days=30,
                detected_at=now,
            )
            await self._write_anti_success_alert(payload)
            event_written = True

        return ThresholdCheckResult(
            threshold_exceeded=threshold_exceeded,
            count=count,
            threshold=self.THRESHOLD_30_DAY,
            event_written=event_written,
        )

    async def check_365_day_governance_trigger(self) -> ThresholdCheckResult:
        """Check 365-day governance review trigger (AC4, RT-3).

        If more than 20 overrides in the last 365 days (RT-3 threshold),
        writes GovernanceReviewRequired event.

        Returns:
            ThresholdCheckResult with governance trigger details.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = self._log.bind(
            operation="check_365_day_governance_trigger",
            threshold=self.THRESHOLD_365_DAY,
            requirement="RT-3",
        )

        count = await self._trend_repository.get_override_count(days=RT3_WINDOW_DAYS)
        threshold_exceeded = count > self.THRESHOLD_365_DAY
        event_written = False

        log.info(
            "365_day_governance_check",
            count=count,
            threshold=self.THRESHOLD_365_DAY,
            exceeded=threshold_exceeded,
        )

        if threshold_exceeded and self._event_writer:
            now = datetime.now(timezone.utc)
            payload = GovernanceReviewRequiredPayload(
                override_count=count,
                window_days=RT3_WINDOW_DAYS,
                threshold=self.THRESHOLD_365_DAY,
                detected_at=now,
            )
            await self._write_governance_review_event(payload)
            event_written = True

        return ThresholdCheckResult(
            threshold_exceeded=threshold_exceeded,
            count=count,
            threshold=self.THRESHOLD_365_DAY,
            event_written=event_written,
        )

    async def run_full_analysis(self) -> TrendAnalysisReport:
        """Run complete trend analysis with all threshold checks.

        Developer Golden Rule: HALT CHECK FIRST (CT-11 pattern)

        Performs all analysis methods and aggregates results into
        a comprehensive report.

        Returns:
            TrendAnalysisReport with all analysis results.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            InsufficientDataError: If data retrieval fails.
        """
        log = self._log.bind(operation="run_full_analysis")

        # HALT CHECK FIRST (CT-11 pattern)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.warning("analysis_blocked_system_halted", reason=reason)
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        log.info("starting_full_trend_analysis")

        # Run all analyses
        trend_data = await self.get_90_day_trend()
        anti_success_result = await self.analyze_50_percent_increase()
        threshold_30_result = await self.check_30_day_threshold()
        governance_result = await self.check_365_day_governance_trigger()

        analyzed_at = datetime.now(timezone.utc)

        report = TrendAnalysisReport(
            trend_data=trend_data,
            anti_success_50_percent=anti_success_result,
            threshold_30_day=threshold_30_result,
            governance_365_day=governance_result,
            analyzed_at=analyzed_at,
        )

        log.info(
            "full_analysis_complete",
            alerts_triggered=sum([
                anti_success_result.alert_triggered,
                threshold_30_result.threshold_exceeded,
                governance_result.threshold_exceeded,
            ]),
            events_written=sum([
                anti_success_result.event_written,
                threshold_30_result.event_written,
                governance_result.event_written,
            ]),
        )

        return report

    async def _write_anti_success_alert(
        self,
        payload: AntiSuccessAlertPayload,
    ) -> None:
        """Write anti-success alert event (CT-12: must be witnessed).

        Args:
            payload: The alert payload to write.

        Raises:
            SystemHaltedError: If system is halted.
        """
        if not self._event_writer:
            return

        log = self._log.bind(
            operation="write_anti_success_alert",
            alert_type=payload.alert_type.value,
        )

        # HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.warning("alert_blocked_system_halted", reason=reason)
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        log.info(
            "writing_anti_success_alert",
            before_count=payload.before_count,
            after_count=payload.after_count,
            percentage_change=payload.percentage_change,
        )

        # Convert payload to dict for EventWriterService interface
        # Note: alert_type enum must be converted to string value
        payload_dict = asdict(payload)
        payload_dict["alert_type"] = payload.alert_type.value

        # Event will be witnessed by EventWriterService (CT-12)
        await self._event_writer.write_event(
            event_type=ANTI_SUCCESS_ALERT_EVENT_TYPE,
            payload=payload_dict,
            agent_id=TREND_ANALYSIS_SYSTEM_AGENT_ID,
            local_timestamp=payload.detected_at,
        )

        log.info("anti_success_alert_written")

    async def _write_governance_review_event(
        self,
        payload: GovernanceReviewRequiredPayload,
    ) -> None:
        """Write governance review required event (CT-12, RT-3).

        Args:
            payload: The governance review payload to write.

        Raises:
            SystemHaltedError: If system is halted.
        """
        if not self._event_writer:
            return

        log = self._log.bind(
            operation="write_governance_review_event",
            requirement="RT-3",
        )

        # HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.warning("governance_event_blocked_system_halted", reason=reason)
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        log.info(
            "writing_governance_review_event",
            override_count=payload.override_count,
            threshold=payload.threshold,
        )

        # Convert payload to dict for EventWriterService interface
        payload_dict = asdict(payload)

        # Event will be witnessed by EventWriterService (CT-12)
        await self._event_writer.write_event(
            event_type=GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE,
            payload=payload_dict,
            agent_id=TREND_ANALYSIS_SYSTEM_AGENT_ID,
            local_timestamp=payload.detected_at,
        )

        log.info("governance_review_event_written", requirement="RT-3")
