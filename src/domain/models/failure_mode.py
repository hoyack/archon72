"""Failure mode domain models (Story 8.8, FR106-FR107).

Domain models for pre-mortem operational failure prevention tracking.
These models represent the failure modes identified during architecture
validation (VAL-*) and pattern violation risk matrix (PV-*).

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events
- FR107: Constitutional events NEVER shed under load

Usage:
    from src.domain.models.failure_mode import (
        FailureMode,
        FailureModeId,
        FailureModeStatus,
        FailureModeThreshold,
        FailureModeSeverity,
    )

    # Create a failure mode
    mode = FailureMode(
        id=FailureModeId.VAL_1,
        description="Silent signature corruption",
        severity=FailureModeSeverity.CRITICAL,
        mitigation="Verify before DB write",
    )

    # Check threshold
    threshold = FailureModeThreshold(
        metric_name="signature_verification_failures",
        warning_value=1.0,
        critical_value=5.0,
        current_value=3.0,
    )
    print(threshold.status)  # WARNING
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class FailureModeId(str, Enum):
    """Identifiers for pre-mortem failure modes.

    Constitutional Constraint (FR106-FR107):
    These failure modes were identified during architecture validation
    and FMEA analysis to prevent constitutional integrity failures.

    VAL-* modes: From pre-mortem validation analysis
    PV-* modes: From pattern violation risk matrix
    """

    # Pre-mortem Validation Analysis (VAL-*)
    VAL_1 = "VAL-1"  # Silent signature corruption
    VAL_2 = "VAL-2"  # Ceremony timeout limbo
    VAL_3 = "VAL-3"  # Import boundary bypass
    VAL_4 = "VAL-4"  # Halt storm via restarts
    VAL_5 = "VAL-5"  # Observer verification staleness

    # Pattern Violation Risk Matrix (PV-*)
    PV_001 = "PV-001"  # Raw string event type
    PV_002 = "PV-002"  # Plain string hash
    PV_003 = "PV-003"  # Missing HaltGuard


class FailureModeStatus(str, Enum):
    """Health status of a failure mode's indicators.

    Constitutional Constraint (FR106-FR107):
    - HEALTHY: All indicators within normal range
    - WARNING: Approaching failure threshold, preventive action advised
    - CRITICAL: At or beyond threshold, immediate action required

    The status determines whether early warning alerts are raised
    and whether the system approaches a failure condition.
    """

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class FailureModeSeverity(str, Enum):
    """Severity classification of failure modes.

    Constitutional Constraint:
    Severity determines the impact if the failure mode is not mitigated:
    - CRITICAL: Could cause constitutional integrity failure
    - HIGH: Could cause service degradation affecting constitutional operations
    - MEDIUM: Could cause operational issues
    - LOW: Minor operational concern
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class FailureModeThreshold:
    """Threshold configuration for failure mode monitoring.

    Defines the metric and threshold values that determine
    when a failure mode transitions between health states.

    Constitutional Constraint (FR106-FR107):
    Thresholds enable early warning before failure occurs,
    allowing preventive action to be taken.

    Attributes:
        threshold_id: Unique identifier for this threshold configuration.
        mode_id: The failure mode this threshold monitors.
        metric_name: Name of the metric being monitored.
        warning_value: Value at which WARNING status is triggered.
        critical_value: Value at which CRITICAL status is triggered.
        current_value: Current measured value of the metric.
        last_updated: When the current_value was last updated.
        comparison: How to compare values ("greater" or "less").
    """

    threshold_id: UUID
    mode_id: FailureModeId
    metric_name: str
    warning_value: float
    critical_value: float
    current_value: float
    last_updated: datetime
    comparison: str = "greater"  # "greater" or "less"

    def __post_init__(self) -> None:
        """Validate threshold configuration."""
        if self.comparison not in ("greater", "less"):
            raise ValueError(f"comparison must be 'greater' or 'less', got {self.comparison}")
        if self.comparison == "greater":
            if self.warning_value > self.critical_value:
                raise ValueError(
                    f"For 'greater' comparison, warning_value ({self.warning_value}) "
                    f"must be <= critical_value ({self.critical_value})"
                )
        else:
            if self.warning_value < self.critical_value:
                raise ValueError(
                    f"For 'less' comparison, warning_value ({self.warning_value}) "
                    f"must be >= critical_value ({self.critical_value})"
                )

    @classmethod
    def create(
        cls,
        mode_id: FailureModeId,
        metric_name: str,
        warning_value: float,
        critical_value: float,
        current_value: float = 0.0,
        comparison: str = "greater",
    ) -> "FailureModeThreshold":
        """Factory method to create a threshold with auto-generated ID.

        Args:
            mode_id: The failure mode this threshold monitors.
            metric_name: Name of the metric being monitored.
            warning_value: Value at which WARNING status is triggered.
            critical_value: Value at which CRITICAL status is triggered.
            current_value: Current measured value (default 0.0).
            comparison: How to compare values (default "greater").

        Returns:
            A new FailureModeThreshold with generated ID and timestamp.
        """
        return cls(
            threshold_id=uuid4(),
            mode_id=mode_id,
            metric_name=metric_name,
            warning_value=warning_value,
            critical_value=critical_value,
            current_value=current_value,
            last_updated=datetime.now(timezone.utc),
            comparison=comparison,
        )

    @property
    def status(self) -> FailureModeStatus:
        """Calculate health status based on current value vs thresholds.

        Returns:
            HEALTHY, WARNING, or CRITICAL based on threshold comparison.
        """
        if self.comparison == "greater":
            if self.current_value >= self.critical_value:
                return FailureModeStatus.CRITICAL
            elif self.current_value >= self.warning_value:
                return FailureModeStatus.WARNING
            return FailureModeStatus.HEALTHY
        else:
            # "less" comparison - lower values are worse
            if self.current_value <= self.critical_value:
                return FailureModeStatus.CRITICAL
            elif self.current_value <= self.warning_value:
                return FailureModeStatus.WARNING
            return FailureModeStatus.HEALTHY

    @property
    def is_critical(self) -> bool:
        """Check if status is CRITICAL."""
        return self.status == FailureModeStatus.CRITICAL

    @property
    def is_warning(self) -> bool:
        """Check if status is WARNING."""
        return self.status == FailureModeStatus.WARNING

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        status_emoji = {
            FailureModeStatus.HEALTHY: "✅",
            FailureModeStatus.WARNING: "⚠️",
            FailureModeStatus.CRITICAL: "🚨",
        }
        emoji = status_emoji[self.status]
        return (
            f"{emoji} {self.metric_name}: {self.current_value} "
            f"(warn: {self.warning_value}, crit: {self.critical_value}) - {self.status.value}"
        )


@dataclass(frozen=True)
class FailureMode:
    """A pre-mortem identified failure mode with its mitigation.

    Represents a failure scenario identified during architecture
    validation or FMEA analysis, along with its prevention measure.

    Constitutional Constraint (FR106-FR107):
    Each failure mode has documented mitigation that prevents
    constitutional integrity failures.

    Attributes:
        id: Unique identifier for this failure mode.
        description: Human-readable description of the failure.
        severity: How severe the failure would be if not mitigated.
        mitigation: The prevention measure in place.
        adr_reference: Optional ADR that documents this mitigation.
        owner: Team or role responsible for this mitigation.
    """

    id: FailureModeId
    description: str
    severity: FailureModeSeverity
    mitigation: str
    adr_reference: Optional[str] = None
    owner: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate failure mode data."""
        if not self.description:
            raise ValueError("description cannot be empty")
        if not self.mitigation:
            raise ValueError("mitigation cannot be empty")

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        severity_emoji = {
            FailureModeSeverity.CRITICAL: "🚨",
            FailureModeSeverity.HIGH: "🔴",
            FailureModeSeverity.MEDIUM: "🟡",
            FailureModeSeverity.LOW: "🟢",
        }
        emoji = severity_emoji[self.severity]
        lines = [
            f"{emoji} [{self.id.value}] {self.description}",
            f"   Severity: {self.severity.value}",
            f"   Mitigation: {self.mitigation}",
        ]
        if self.adr_reference:
            lines.append(f"   ADR: {self.adr_reference}")
        if self.owner:
            lines.append(f"   Owner: {self.owner}")
        return "\n".join(lines)


@dataclass(frozen=True)
class EarlyWarning:
    """An early warning alert for a failure mode.

    Generated when a failure mode's health indicators approach
    or exceed threshold values, providing time for preventive action.

    Constitutional Constraint (FR106-FR107):
    Early warnings enable operators to prevent failures before
    they impact constitutional operations.

    Attributes:
        warning_id: Unique identifier for this warning.
        mode_id: The failure mode that triggered this warning.
        current_value: The metric value that triggered the warning.
        threshold: The threshold value that was breached.
        threshold_type: Whether this is a "warning" or "critical" threshold.
        recommended_action: What action should be taken.
        timestamp: When this warning was generated.
        metric_name: Name of the metric that triggered the warning.
    """

    warning_id: UUID
    mode_id: FailureModeId
    current_value: float
    threshold: float
    threshold_type: str  # "warning" or "critical"
    recommended_action: str
    timestamp: datetime
    metric_name: str

    def __post_init__(self) -> None:
        """Validate warning data."""
        if self.threshold_type not in ("warning", "critical"):
            raise ValueError(f"threshold_type must be 'warning' or 'critical', got {self.threshold_type}")
        if not self.recommended_action:
            raise ValueError("recommended_action cannot be empty")
        if not self.metric_name:
            raise ValueError("metric_name cannot be empty")

    @classmethod
    def create(
        cls,
        mode_id: FailureModeId,
        current_value: float,
        threshold: float,
        threshold_type: str,
        recommended_action: str,
        metric_name: str,
    ) -> "EarlyWarning":
        """Factory method to create a warning with auto-generated ID and timestamp.

        Args:
            mode_id: The failure mode that triggered this warning.
            current_value: The metric value that triggered the warning.
            threshold: The threshold value that was breached.
            threshold_type: Whether this is a "warning" or "critical" threshold.
            recommended_action: What action should be taken.
            metric_name: Name of the metric that triggered the warning.

        Returns:
            A new EarlyWarning with generated ID and current timestamp.
        """
        return cls(
            warning_id=uuid4(),
            mode_id=mode_id,
            current_value=current_value,
            threshold=threshold,
            threshold_type=threshold_type,
            recommended_action=recommended_action,
            timestamp=datetime.now(timezone.utc),
            metric_name=metric_name,
        )

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        emoji = "⚠️" if self.threshold_type == "warning" else "🚨"
        return (
            f"{emoji} [{self.mode_id.value}] {self.threshold_type.upper()}: "
            f"{self.metric_name}={self.current_value} (threshold: {self.threshold})\n"
            f"   Action: {self.recommended_action}"
        )


# Default failure mode definitions from architecture.md
DEFAULT_FAILURE_MODES: dict[FailureModeId, FailureMode] = {
    FailureModeId.VAL_1: FailureMode(
        id=FailureModeId.VAL_1,
        description="Silent signature corruption",
        severity=FailureModeSeverity.CRITICAL,
        mitigation="Verify before DB write",
        adr_reference="ADR-1, ADR-4",
        owner="Dev",
    ),
    FailureModeId.VAL_2: FailureMode(
        id=FailureModeId.VAL_2,
        description="Ceremony timeout limbo",
        severity=FailureModeSeverity.HIGH,
        mitigation="Timeout enforcement + auto-abort",
        adr_reference="ADR-6",
        owner="Ceremony Team",
    ),
    FailureModeId.VAL_3: FailureMode(
        id=FailureModeId.VAL_3,
        description="Import boundary bypass",
        severity=FailureModeSeverity.HIGH,
        mitigation="Pre-commit hook + bypass detection",
        adr_reference=None,
        owner="Ops",
    ),
    FailureModeId.VAL_4: FailureMode(
        id=FailureModeId.VAL_4,
        description="Halt storm via restarts",
        severity=FailureModeSeverity.HIGH,
        mitigation="Aggregate rate limiting",
        adr_reference="ADR-3",
        owner="Platform",
    ),
    FailureModeId.VAL_5: FailureMode(
        id=FailureModeId.VAL_5,
        description="Observer verification staleness",
        severity=FailureModeSeverity.MEDIUM,
        mitigation="Freshness health dimension",
        adr_reference="ADR-8",
        owner="Ops",
    ),
    FailureModeId.PV_001: FailureMode(
        id=FailureModeId.PV_001,
        description="Raw string event type (orphan events)",
        severity=FailureModeSeverity.HIGH,
        mitigation="EventType enum + mypy",
        adr_reference=None,
        owner="Dev",
    ),
    FailureModeId.PV_002: FailureMode(
        id=FailureModeId.PV_002,
        description="Plain string hash (invalid refs)",
        severity=FailureModeSeverity.CRITICAL,
        mitigation="ContentRef validation",
        adr_reference=None,
        owner="Dev",
    ),
    FailureModeId.PV_003: FailureMode(
        id=FailureModeId.PV_003,
        description="Missing HaltGuard (operations during halt)",
        severity=FailureModeSeverity.CRITICAL,
        mitigation="Base class requirement",
        adr_reference=None,
        owner="Dev",
    ),
}
