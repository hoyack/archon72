"""Override Abuse Detection Service - Constitutional constraint validation (Story 5.9, FR86-FR87, FP-3).

This service orchestrates override abuse detection, combining constitutional
constraint validation with statistical anomaly detection.

Constitutional Constraints:
- FR86: System SHALL validate override commands against constitutional constraints
- FR87: Override commands violating constraints SHALL be rejected and logged
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All abuse events MUST be witnessed
- FP-3: Patient attacker detection needs ADR-7 (Aggregate Anomaly Detection)

ADR-7 Implementation:
This service implements the Statistics layer of the three-layer detection system:
| Layer | Method | Response |
|-------|--------|----------|
| Rules | Predefined thresholds (Story 5.5) | Auto-alert, auto-halt if critical |
| Statistics (THIS SERVICE) | Baseline deviation detection | Queue for review |
| Human | Weekly anomaly review ceremony | Classify, escalate, or dismiss |

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All abuse events MUST be witnessed
3. FAIL LOUD - Never silently ignore abuse
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from structlog import get_logger

from src.application.ports.anomaly_detector import (
    AnomalyDetectorProtocol,
    AnomalyResult,
    FrequencyData,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.override_abuse_validator import (
    OverrideAbuseValidatorProtocol,
    ValidationResult,
)
from src.domain.errors.override_abuse import (
    ConstitutionalConstraintViolationError,
    EvidenceDestructionAttemptError,
    HistoryEditAttemptError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.override_abuse import (
    ANOMALY_DETECTED_EVENT_TYPE,
    OVERRIDE_ABUSE_REJECTED_EVENT_TYPE,
    AnomalyDetectedPayload,
    AnomalyType,
    OverrideAbuseRejectedPayload,
    ViolationType,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()

# System agent ID for abuse detection service events
ABUSE_DETECTION_SYSTEM_AGENT_ID: str = "abuse_detection_system"

# Detection window constants (FP-3, ADR-7)
ANOMALY_DETECTION_WINDOW_DAYS: int = 90  # Statistical analysis window
SLOW_BURN_WINDOW_DAYS: int = 365  # Long-term pattern detection (CT-9)
ANOMALY_CONFIDENCE_THRESHOLD: float = 0.7  # Minimum confidence for alerts


@dataclass(frozen=True)
class KeeperBehaviorReport:
    """Report on Keeper override behavior analysis.

    Attributes:
        keeper_id: ID of the analyzed Keeper.
        frequency_data: Override frequency statistics.
        is_outlier: True if behavior is statistically anomalous.
        outlier_reason: Reason for outlier classification if applicable.
    """

    keeper_id: str
    frequency_data: FrequencyData
    is_outlier: bool
    outlier_reason: Optional[str] = None


@dataclass(frozen=True)
class AnomalyReviewReport:
    """Report for weekly anomaly review ceremony (ADR-7).

    Attributes:
        review_timestamp: When the review was generated.
        anomalies_detected: List of all detected anomalies.
        anomaly_count: Total count of anomalies.
        high_confidence_count: Count of anomalies with confidence >= 0.9.
        medium_confidence_count: Count of anomalies with 0.7 <= confidence < 0.9.
    """

    review_timestamp: datetime
    anomalies_detected: tuple[AnomalyResult, ...]
    anomaly_count: int
    high_confidence_count: int
    medium_confidence_count: int

    @classmethod
    def from_anomalies(
        cls,
        anomalies: list[AnomalyResult],
        timestamp: datetime,
    ) -> "AnomalyReviewReport":
        """Create report from list of anomalies."""
        high_count = sum(1 for a in anomalies if a.confidence_score >= 0.9)
        medium_count = sum(1 for a in anomalies if 0.7 <= a.confidence_score < 0.9)
        return cls(
            review_timestamp=timestamp,
            anomalies_detected=tuple(anomalies),
            anomaly_count=len(anomalies),
            high_confidence_count=high_count,
            medium_confidence_count=medium_count,
        )


class OverrideAbuseDetectionService:
    """Detects override abuse and statistical anomalies (FR86, FR87, FP-3, ADR-7).

    This service provides:
    1. Constitutional constraint validation (FR86, FR87)
    2. Statistical anomaly detection (FP-3, ADR-7)
    3. Weekly anomaly review support (ADR-7)

    Constitutional Constraints:
    - FR86: Validate override commands against constitutional constraints
    - FR87: Reject and log history edit and evidence destruction attempts
    - CT-9: Detect slow-burn attacks (patient attacker detection)
    - CT-11: HALT CHECK FIRST - Check halt state before every operation
    - CT-12: All abuse events MUST be witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - All events are witnessed via EventWriterService
    3. FAIL LOUD - Raise specific errors for violations
    """

    def __init__(
        self,
        abuse_validator: OverrideAbuseValidatorProtocol,
        anomaly_detector: AnomalyDetectorProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Override Abuse Detection Service.

        Args:
            abuse_validator: Validator for constitutional constraint checks.
            anomaly_detector: Detector for statistical anomaly detection.
            event_writer: Service for writing witnessed events.
            halt_checker: Interface to check system halt state.
        """
        self._abuse_validator = abuse_validator
        self._anomaly_detector = anomaly_detector
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def validate_override_command(
        self,
        scope: str,
        action_type: str,
        keeper_id: str,
    ) -> ValidationResult:
        """Validate override command against constitutional constraints.

        Constitutional Constraints:
        - FR86: System SHALL validate override commands before execution
        - FR87: History edit and evidence destruction attempts SHALL be rejected
        - CT-11: HALT CHECK FIRST

        Args:
            scope: Override scope to validate (e.g., "voting.extension").
            action_type: Type of override action being attempted.
            keeper_id: ID of the Keeper requesting the override.

        Returns:
            ValidationResult indicating whether the override is valid.
            If invalid, result includes violation type and details.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            HistoryEditAttemptError: If scope attempts history edit (FR87).
            EvidenceDestructionAttemptError: If scope destroys evidence (FR87).
            ConstitutionalConstraintViolationError: For other violations (FR86).
        """
        log = logger.bind(
            operation="validate_override_command",
            keeper_id=keeper_id,
            scope=scope,
            action_type=action_type,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "override_validation_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Check for history edit attempt (FR87)
        # =====================================================================
        if await self._abuse_validator.is_history_edit_attempt(scope):
            log.warning(
                "override_abuse_detected_history_edit",
                violation_type=ViolationType.HISTORY_EDIT.value,
            )

            # Write abuse rejection event (witnessed per CT-12)
            await self._write_abuse_rejection_event(
                keeper_id=keeper_id,
                scope=scope,
                violation_type=ViolationType.HISTORY_EDIT,
                violation_details=f"FR87: Override scope '{scope}' attempts to edit event history",
            )

            raise HistoryEditAttemptError(scope)

        # =====================================================================
        # Check for evidence destruction attempt (FR87)
        # =====================================================================
        if await self._abuse_validator.is_evidence_destruction_attempt(scope):
            log.warning(
                "override_abuse_detected_evidence_destruction",
                violation_type=ViolationType.EVIDENCE_DESTRUCTION.value,
            )

            # Write abuse rejection event (witnessed per CT-12)
            await self._write_abuse_rejection_event(
                keeper_id=keeper_id,
                scope=scope,
                violation_type=ViolationType.EVIDENCE_DESTRUCTION,
                violation_details=f"FR87: Override scope '{scope}' attempts to destroy evidence",
            )

            raise EvidenceDestructionAttemptError(scope)

        # =====================================================================
        # Validate all constitutional constraints (FR86)
        # =====================================================================
        result = await self._abuse_validator.validate_constitutional_constraints(
            override_scope=scope,
            action_type=action_type,
        )

        if not result.is_valid:
            log.warning(
                "override_abuse_detected_constitutional_constraint",
                violation_type=result.violation_type.value if result.violation_type else "unknown",
                violation_details=result.violation_details,
            )

            # Write abuse rejection event (witnessed per CT-12)
            await self._write_abuse_rejection_event(
                keeper_id=keeper_id,
                scope=scope,
                violation_type=result.violation_type or ViolationType.CONSTITUTIONAL_CONSTRAINT,
                violation_details=result.violation_details or f"FR86: Constitutional constraint violation for scope '{scope}'",
            )

            raise ConstitutionalConstraintViolationError(
                scope=scope,
                constraint=result.violation_details or "Unknown constraint",
            )

        log.info(
            "override_validation_passed",
            message="Override scope passes all constitutional checks",
        )

        return ValidationResult.success()

    async def detect_anomalies(self) -> list[AnomalyResult]:
        """Detect statistical anomalies in override patterns.

        Constitutional Constraints:
        - CT-9: Attackers are patient - detect aggregate erosion
        - CT-11: HALT CHECK FIRST
        - FP-3: Patient attacker detection using ADR-7

        Returns:
            List of detected anomalies. Each anomaly has confidence score.
            Only anomalies with confidence >= ANOMALY_CONFIDENCE_THRESHOLD
            are included.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="detect_anomalies")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "anomaly_detection_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        all_anomalies: list[AnomalyResult] = []

        # =====================================================================
        # Run frequency spike detection (FP-3)
        # =====================================================================
        log.info("running_frequency_spike_detection", window_days=ANOMALY_DETECTION_WINDOW_DAYS)
        keeper_anomalies = await self._anomaly_detector.detect_keeper_anomalies(
            time_window_days=ANOMALY_DETECTION_WINDOW_DAYS
        )
        all_anomalies.extend(keeper_anomalies)

        # =====================================================================
        # Run slow-burn erosion detection (CT-9, ADR-7)
        # =====================================================================
        log.info("running_slow_burn_detection", window_days=SLOW_BURN_WINDOW_DAYS)
        slow_burn_anomalies = await self._anomaly_detector.detect_slow_burn_erosion(
            time_window_days=SLOW_BURN_WINDOW_DAYS,
            threshold=0.1,  # 10% annual growth threshold
        )
        all_anomalies.extend(slow_burn_anomalies)

        # =====================================================================
        # Filter by confidence threshold
        # =====================================================================
        high_confidence_anomalies = [
            a for a in all_anomalies
            if a.confidence_score >= ANOMALY_CONFIDENCE_THRESHOLD
        ]

        # =====================================================================
        # Write anomaly events for each detection (witnessed per CT-12)
        # =====================================================================
        for anomaly in high_confidence_anomalies:
            await self._write_anomaly_detected_event(anomaly)

        log.info(
            "anomaly_detection_complete",
            total_anomalies=len(all_anomalies),
            high_confidence_anomalies=len(high_confidence_anomalies),
        )

        return high_confidence_anomalies

    async def analyze_keeper_behavior(
        self,
        keeper_id: str,
    ) -> KeeperBehaviorReport:
        """Analyze override behavior for a specific Keeper.

        Constitutional Constraint:
        - CT-11: HALT CHECK FIRST

        Args:
            keeper_id: ID of the Keeper to analyze.

        Returns:
            KeeperBehaviorReport with frequency data and outlier status.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(
            operation="analyze_keeper_behavior",
            keeper_id=keeper_id,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "keeper_analysis_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # Get frequency data
        frequency = await self._anomaly_detector.get_keeper_override_frequency(
            keeper_id=keeper_id,
            time_window_days=ANOMALY_DETECTION_WINDOW_DAYS,
        )

        # Determine if outlier (> 2 standard deviations from baseline)
        is_outlier = abs(frequency.deviation_from_baseline) > 2.0
        outlier_reason = None
        if is_outlier:
            if frequency.deviation_from_baseline > 0:
                outlier_reason = f"Override frequency {frequency.deviation_from_baseline:.2f} std above baseline"
            else:
                outlier_reason = f"Override frequency {abs(frequency.deviation_from_baseline):.2f} std below baseline"

        log.info(
            "keeper_behavior_analyzed",
            override_count=frequency.override_count,
            daily_rate=frequency.daily_rate,
            deviation=frequency.deviation_from_baseline,
            is_outlier=is_outlier,
        )

        return KeeperBehaviorReport(
            keeper_id=keeper_id,
            frequency_data=frequency,
            is_outlier=is_outlier,
            outlier_reason=outlier_reason,
        )

    async def run_weekly_anomaly_review(self) -> AnomalyReviewReport:
        """Run weekly anomaly review ceremony (ADR-7).

        Constitutional Constraints:
        - CT-9: Detect slow-burn attacks over long time windows
        - CT-11: HALT CHECK FIRST
        - ADR-7: Weekly anomaly review ceremony

        ADR-7 Acceptance Criteria:
        - Weekly anomaly review ceremony is scheduled and attended
        - Anomaly backlog does not exceed 50 items
        - Each anomaly is classified: true positive, false positive, needs investigation
        - True positives trigger documented response

        Returns:
            AnomalyReviewReport containing all detected anomalies for human review.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        log = logger.bind(operation="run_weekly_anomaly_review")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "weekly_review_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        all_anomalies: list[AnomalyResult] = []

        # =====================================================================
        # Run all anomaly detectors
        # =====================================================================

        # 1. Keeper frequency anomalies
        log.info("weekly_review_running_frequency_detection")
        keeper_anomalies = await self._anomaly_detector.detect_keeper_anomalies(
            time_window_days=ANOMALY_DETECTION_WINDOW_DAYS
        )
        all_anomalies.extend(keeper_anomalies)

        # 2. Slow-burn erosion (CT-9)
        log.info("weekly_review_running_slow_burn_detection")
        slow_burn_anomalies = await self._anomaly_detector.detect_slow_burn_erosion(
            time_window_days=SLOW_BURN_WINDOW_DAYS,
            threshold=0.1,
        )
        all_anomalies.extend(slow_burn_anomalies)

        # Filter by confidence threshold
        high_confidence_anomalies = [
            a for a in all_anomalies
            if a.confidence_score >= ANOMALY_CONFIDENCE_THRESHOLD
        ]

        # Create review report
        review_timestamp = datetime.now(timezone.utc)
        report = AnomalyReviewReport.from_anomalies(
            anomalies=high_confidence_anomalies,
            timestamp=review_timestamp,
        )

        log.info(
            "weekly_review_complete",
            total_anomalies=report.anomaly_count,
            high_confidence_count=report.high_confidence_count,
            medium_confidence_count=report.medium_confidence_count,
        )

        return report

    async def _write_abuse_rejection_event(
        self,
        keeper_id: str,
        scope: str,
        violation_type: ViolationType,
        violation_details: str,
    ) -> None:
        """Write an OverrideAbuseRejected event (witnessed per CT-12).

        Args:
            keeper_id: ID of the Keeper whose override was rejected.
            scope: The override scope that was rejected.
            violation_type: Type of constitutional violation detected.
            violation_details: Human-readable description of the violation.
        """
        rejected_at = datetime.now(timezone.utc)
        payload = OverrideAbuseRejectedPayload(
            keeper_id=keeper_id,
            scope=scope,
            violation_type=violation_type,
            violation_details=violation_details,
            rejected_at=rejected_at,
        )

        await self._event_writer.write_event(
            event_type=OVERRIDE_ABUSE_REJECTED_EVENT_TYPE,
            payload={
                "keeper_id": payload.keeper_id,
                "scope": payload.scope,
                "violation_type": payload.violation_type.value,
                "violation_details": payload.violation_details,
                "rejected_at": payload.rejected_at.isoformat(),
            },
            agent_id=ABUSE_DETECTION_SYSTEM_AGENT_ID,
            local_timestamp=rejected_at,
        )

    async def _write_anomaly_detected_event(
        self,
        anomaly: AnomalyResult,
    ) -> None:
        """Write an AnomalyDetected event (witnessed per CT-12).

        Args:
            anomaly: The detected anomaly to record.
        """
        detected_at = datetime.now(timezone.utc)
        payload = AnomalyDetectedPayload(
            anomaly_type=anomaly.anomaly_type,
            keeper_ids=anomaly.affected_keepers,
            detection_method="statistical_baseline_deviation",
            confidence_score=anomaly.confidence_score,
            time_window_days=ANOMALY_DETECTION_WINDOW_DAYS,
            details=anomaly.details,
            detected_at=detected_at,
        )

        await self._event_writer.write_event(
            event_type=ANOMALY_DETECTED_EVENT_TYPE,
            payload={
                "anomaly_type": payload.anomaly_type.value,
                "keeper_ids": list(payload.keeper_ids),
                "detection_method": payload.detection_method,
                "confidence_score": payload.confidence_score,
                "time_window_days": payload.time_window_days,
                "details": payload.details,
                "detected_at": payload.detected_at.isoformat(),
            },
            agent_id=ABUSE_DETECTION_SYSTEM_AGENT_ID,
            local_timestamp=detected_at,
        )
