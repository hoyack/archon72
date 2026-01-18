"""Load status model for load shedding decisions (Story 8.8, FR107).

Domain model for tracking system load and shedding decisions.

Constitutional Constraints:
- FR107: Constitutional events NEVER shed under load; operational
         telemetry may be deprioritized but canonical events never dropped.

Usage:
    from src.domain.models.load_status import LoadStatus, LoadLevel

    status = LoadStatus.create(
        current_load=85.0,
        capacity_threshold=80.0,
    )
    print(status.load_level)  # ELEVATED
    print(status.should_shed_telemetry)  # True
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class LoadLevel(str, Enum):
    """System load level classification.

    Constitutional Constraint (FR107):
    Load levels determine what can be shed:
    - NORMAL: No shedding needed
    - ELEVATED: Warn, prepare for shedding
    - HIGH: Shed operational telemetry
    - CRITICAL: Maximum shedding, but NEVER constitutional events
    """

    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


# Load thresholds as percentages
NORMAL_THRESHOLD: float = 60.0
ELEVATED_THRESHOLD: float = 75.0
HIGH_THRESHOLD: float = 90.0
# Above HIGH_THRESHOLD is CRITICAL

# Extreme load threshold (50× baseline per NFR43)
EXTREME_LOAD_MULTIPLIER: float = 50.0


@dataclass(frozen=True)
class LoadStatus:
    """System load status for shedding decisions (FR107).

    Tracks current system load and determines whether telemetry
    shedding is appropriate.

    Constitutional Constraint (FR107):
    System SHALL NOT shed constitutional events under load.
    Only operational telemetry may be deprioritized.

    Attributes:
        status_id: Unique identifier for this status snapshot.
        current_load: Current load as percentage of capacity.
        capacity_threshold: Threshold for shedding activation.
        shedding_active: Whether shedding is currently active.
        timestamp: When this status was captured.
        baseline_load: Optional baseline for comparison.
        telemetry_shed_count: Count of telemetry items shed.
    """

    status_id: UUID
    current_load: float
    capacity_threshold: float
    shedding_active: bool
    timestamp: datetime
    baseline_load: float | None
    telemetry_shed_count: int

    def __post_init__(self) -> None:
        """Validate load status data."""
        if self.current_load < 0:
            raise ValueError(
                f"current_load cannot be negative, got {self.current_load}"
            )
        if self.capacity_threshold <= 0:
            raise ValueError(
                f"capacity_threshold must be positive, got {self.capacity_threshold}"
            )
        if self.telemetry_shed_count < 0:
            raise ValueError(
                f"telemetry_shed_count cannot be negative, got {self.telemetry_shed_count}"
            )
        if self.baseline_load is not None and self.baseline_load < 0:
            raise ValueError(
                f"baseline_load cannot be negative, got {self.baseline_load}"
            )

    @classmethod
    def create(
        cls,
        current_load: float,
        capacity_threshold: float = 80.0,
        baseline_load: float | None = None,
    ) -> "LoadStatus":
        """Factory method to create load status.

        Args:
            current_load: Current load as percentage.
            capacity_threshold: Threshold for shedding (default 80%).
            baseline_load: Optional baseline for comparison.

        Returns:
            A new LoadStatus with generated ID and timestamp.
        """
        shedding_active = current_load >= capacity_threshold

        return cls(
            status_id=uuid4(),
            current_load=current_load,
            capacity_threshold=capacity_threshold,
            shedding_active=shedding_active,
            timestamp=datetime.now(timezone.utc),
            baseline_load=baseline_load,
            telemetry_shed_count=0,
        )

    @property
    def load_level(self) -> LoadLevel:
        """Determine load level based on current load.

        Returns:
            LoadLevel classification.
        """
        if self.current_load >= HIGH_THRESHOLD:
            return LoadLevel.CRITICAL
        elif self.current_load >= ELEVATED_THRESHOLD:
            return LoadLevel.HIGH
        elif self.current_load >= NORMAL_THRESHOLD:
            return LoadLevel.ELEVATED
        return LoadLevel.NORMAL

    @property
    def should_shed_telemetry(self) -> bool:
        """Determine if telemetry should be shed.

        Constitutional Constraint (FR107):
        Only operational telemetry can be shed.
        This property indicates when shedding is appropriate.

        Returns:
            True if telemetry shedding is advised.
        """
        return self.load_level in (LoadLevel.HIGH, LoadLevel.CRITICAL)

    @property
    def is_extreme_load(self) -> bool:
        """Check if load is extreme (>50× baseline per NFR43).

        Returns:
            True if load exceeds 50× baseline.
        """
        if self.baseline_load is None or self.baseline_load == 0:
            return self.current_load >= 95.0  # Default extreme threshold

        return self.current_load >= (self.baseline_load * EXTREME_LOAD_MULTIPLIER)

    @property
    def headroom_percent(self) -> float:
        """Calculate remaining capacity before threshold.

        Returns:
            Percentage of capacity remaining before shedding.
        """
        return max(0.0, self.capacity_threshold - self.current_load)

    @property
    def utilization_percent(self) -> float:
        """Calculate utilization as percentage of threshold.

        Returns:
            How much of the threshold capacity is used.
        """
        if self.capacity_threshold == 0:
            return 100.0
        return (self.current_load / self.capacity_threshold) * 100.0

    def with_shed(self, count: int = 1) -> "LoadStatus":
        """Create updated status with additional items shed.

        Args:
            count: Number of items shed.

        Returns:
            New LoadStatus with updated shed count.
        """
        return LoadStatus(
            status_id=self.status_id,
            current_load=self.current_load,
            capacity_threshold=self.capacity_threshold,
            shedding_active=self.shedding_active,
            timestamp=self.timestamp,
            baseline_load=self.baseline_load,
            telemetry_shed_count=self.telemetry_shed_count + count,
        )

    def to_summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Summary string suitable for logging or display.
        """
        level_emoji = {
            LoadLevel.NORMAL: "✅",
            LoadLevel.ELEVATED: "⚠️",
            LoadLevel.HIGH: "🔴",
            LoadLevel.CRITICAL: "🚨",
        }
        emoji = level_emoji[self.load_level]
        shedding_status = "🔽 Shedding active" if self.shedding_active else "▶️ Normal"

        return (
            f"{emoji} Load: {self.current_load:.1f}% ({self.load_level.value}) "
            f"| Threshold: {self.capacity_threshold:.1f}% "
            f"| {shedding_status}"
        )


@dataclass(frozen=True)
class LoadSheddingDecision:
    """Record of a load shedding decision (FR107).

    Constitutional Constraint (FR107):
    All load shedding decisions must be logged.

    Attributes:
        decision_id: Unique identifier for this decision.
        load_status: The load status that triggered the decision.
        item_type: Type of item considered for shedding.
        was_shed: Whether the item was actually shed.
        reason: Reason for the shedding decision.
        is_constitutional: Whether the item is constitutional (NEVER shed).
        timestamp: When the decision was made.
    """

    decision_id: UUID
    load_status: LoadStatus
    item_type: str
    was_shed: bool
    reason: str
    is_constitutional: bool
    timestamp: datetime

    @classmethod
    def create(
        cls,
        load_status: LoadStatus,
        item_type: str,
        is_constitutional: bool,
        reason: str = "",
    ) -> "LoadSheddingDecision":
        """Factory method to create shedding decision.

        Constitutional Constraint (FR107):
        Constitutional items are NEVER shed, regardless of load.

        Args:
            load_status: Current load status.
            item_type: Type of item considered.
            is_constitutional: Whether item is constitutional.
            reason: Reason for decision.

        Returns:
            A new LoadSheddingDecision.
        """
        # Constitutional events are NEVER shed (FR107)
        if is_constitutional:
            was_shed = False
            if not reason:
                reason = "FR107: Constitutional events NEVER shed"
        else:
            was_shed = load_status.should_shed_telemetry
            if not reason:
                reason = (
                    f"Load at {load_status.current_load:.1f}%, "
                    f"shedding {'enabled' if was_shed else 'disabled'}"
                )

        return cls(
            decision_id=uuid4(),
            load_status=load_status,
            item_type=item_type,
            was_shed=was_shed,
            reason=reason,
            is_constitutional=is_constitutional,
            timestamp=datetime.now(timezone.utc),
        )
