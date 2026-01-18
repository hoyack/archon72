"""Complexity budget models (Story 8.6, SC-3, RT-6).

Domain models for tracking complexity budget limits per CT-14.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- SC-3: Self-consistency finding - complexity budget dashboard required.
- RT-6: Red Team hardening - breach = constitutional event, not just alert.

Usage:
    from src.domain.models.complexity_budget import (
        ComplexityBudget,
        ComplexityDimension,
        ComplexityBudgetStatus,
        ComplexitySnapshot,
    )

    # Check a single budget
    budget = ComplexityBudget(
        dimension=ComplexityDimension.ADR_COUNT,
        limit=15,
        current_value=12,
    )
    print(budget.status)  # WITHIN_BUDGET or WARNING

    # Create a full snapshot
    snapshot = ComplexitySnapshot(
        adr_count=12,
        ceremony_types=5,
        cross_component_deps=18,
        timestamp=datetime.now(timezone.utc),
    )
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

# Budget limits from architecture.md and epics.md (CT-14)
ADR_LIMIT: int = 15
CEREMONY_TYPE_LIMIT: int = 10
CROSS_COMPONENT_DEP_LIMIT: int = 20

# Warning threshold (percentage of limit)
WARNING_THRESHOLD_PERCENT: float = 80.0


class ComplexityDimension(str, Enum):
    """Dimensions of complexity tracked per CT-14.

    Constitutional Constraint (CT-14):
    Each dimension represents a measurable aspect of system
    complexity that must be budgeted explicitly.

    Dimensions:
        ADR_COUNT: Number of Architecture Decision Records
        CEREMONY_TYPES: Number of governance ceremony types
        CROSS_COMPONENT_DEPS: Number of cross-component dependencies
    """

    ADR_COUNT = "adr_count"
    CEREMONY_TYPES = "ceremony_types"
    CROSS_COMPONENT_DEPS = "cross_component_deps"


class ComplexityBudgetStatus(str, Enum):
    """Status of a complexity budget dimension.

    Constitutional Constraint (RT-6):
    - WITHIN_BUDGET: Under 80% of limit, healthy
    - WARNING: 80-99% of limit, approaching breach
    - BREACHED: At or over 100% of limit, requires governance ceremony

    Red Team Hardening (RT-6):
    BREACHED status creates a constitutional event, not just an alert.
    Exceeding limits requires governance ceremony to proceed.
    """

    WITHIN_BUDGET = "within_budget"
    WARNING = "warning"
    BREACHED = "breached"


def _get_limit_for_dimension(dimension: ComplexityDimension) -> int:
    """Get the budget limit for a complexity dimension.

    Args:
        dimension: The complexity dimension.

    Returns:
        The budget limit for that dimension.
    """
    limits = {
        ComplexityDimension.ADR_COUNT: ADR_LIMIT,
        ComplexityDimension.CEREMONY_TYPES: CEREMONY_TYPE_LIMIT,
        ComplexityDimension.CROSS_COMPONENT_DEPS: CROSS_COMPONENT_DEP_LIMIT,
    }
    return limits[dimension]


@dataclass(frozen=True)
class ComplexityBudget:
    """Budget status for a single complexity dimension.

    Represents the current state of a complexity budget including
    the dimension, its limit, current value, and calculated status.

    Constitutional Constraint (CT-14):
    Complexity must be budgeted. This model tracks whether a
    dimension is within budget, at warning level, or breached.

    Red Team Hardening (RT-6):
    A breached budget creates a constitutional event requiring
    governance ceremony approval to proceed.

    Attributes:
        dimension: Which complexity dimension this budget tracks.
        limit: The maximum allowed value for this dimension.
        current_value: The current measured value.
        breach_id: Optional breach ID if this budget triggered a breach event.
    """

    dimension: ComplexityDimension
    limit: int
    current_value: int
    breach_id: UUID | None = None

    def __post_init__(self) -> None:
        """Validate budget data."""
        if self.limit <= 0:
            raise ValueError(f"limit must be positive, got {self.limit}")
        if self.current_value < 0:
            raise ValueError(
                f"current_value cannot be negative, got {self.current_value}"
            )

    @property
    def status(self) -> ComplexityBudgetStatus:
        """Calculate the budget status based on utilization.

        Constitutional Constraint (CT-14):
        - >= 100%: BREACHED (requires governance ceremony)
        - >= 80%: WARNING (approaching limit)
        - < 80%: WITHIN_BUDGET (healthy)

        Returns:
            The calculated budget status.
        """
        percentage = self.utilization_percent
        if percentage >= 100.0:
            return ComplexityBudgetStatus.BREACHED
        elif percentage >= WARNING_THRESHOLD_PERCENT:
            return ComplexityBudgetStatus.WARNING
        return ComplexityBudgetStatus.WITHIN_BUDGET

    @property
    def utilization_percent(self) -> float:
        """Calculate utilization as a percentage of limit.

        Returns:
            Percentage utilization (0-100+).
        """
        return (self.current_value / self.limit) * 100.0

    @property
    def remaining(self) -> int:
        """Calculate remaining budget capacity.

        Returns:
            Remaining capacity before limit (can be negative if breached).
        """
        return self.limit - self.current_value

    @property
    def is_breached(self) -> bool:
        """Check if this budget is breached.

        Returns:
            True if current_value >= limit.
        """
        return self.current_value >= self.limit

    @property
    def is_warning(self) -> bool:
        """Check if this budget is at warning level.

        Returns:
            True if utilization is 80-99%.
        """
        return self.status == ComplexityBudgetStatus.WARNING

    def to_summary(self) -> str:
        """Generate a human-readable summary.

        Returns:
            Summary string suitable for logging or display.
        """
        status_emoji = {
            ComplexityBudgetStatus.WITHIN_BUDGET: "✅",
            ComplexityBudgetStatus.WARNING: "⚠️",
            ComplexityBudgetStatus.BREACHED: "🚨",
        }
        emoji = status_emoji[self.status]
        return (
            f"{emoji} {self.dimension.value}: {self.current_value}/{self.limit} "
            f"({self.utilization_percent:.1f}%) - {self.status.value}"
        )


@dataclass(frozen=True)
class ComplexitySnapshot:
    """Point-in-time snapshot of all complexity dimensions.

    Captures the current state of all complexity budgets at a
    specific moment. Used for historical tracking and dashboard display.

    Constitutional Constraint (CT-14):
    Provides visibility into complexity growth across all dimensions.
    Dashboard uses snapshots to show current state and trends.

    Attributes:
        snapshot_id: Unique identifier for this snapshot.
        adr_count: Current ADR count.
        ceremony_types: Current ceremony type count.
        cross_component_deps: Current cross-component dependency count.
        timestamp: When this snapshot was taken.
        triggered_by: Optional description of what triggered this snapshot.
    """

    snapshot_id: UUID
    adr_count: int
    ceremony_types: int
    cross_component_deps: int
    timestamp: datetime
    triggered_by: str | None = None

    def __post_init__(self) -> None:
        """Validate snapshot data."""
        if self.adr_count < 0:
            raise ValueError(f"adr_count cannot be negative, got {self.adr_count}")
        if self.ceremony_types < 0:
            raise ValueError(
                f"ceremony_types cannot be negative, got {self.ceremony_types}"
            )
        if self.cross_component_deps < 0:
            raise ValueError(
                f"cross_component_deps cannot be negative, got {self.cross_component_deps}"
            )

    @classmethod
    def create(
        cls,
        adr_count: int,
        ceremony_types: int,
        cross_component_deps: int,
        triggered_by: str | None = None,
    ) -> "ComplexitySnapshot":
        """Factory method to create a snapshot with auto-generated ID and timestamp.

        Args:
            adr_count: Current ADR count.
            ceremony_types: Current ceremony type count.
            cross_component_deps: Current cross-component dependency count.
            triggered_by: Optional description of trigger.

        Returns:
            A new ComplexitySnapshot with generated ID and current timestamp.
        """
        return cls(
            snapshot_id=uuid4(),
            adr_count=adr_count,
            ceremony_types=ceremony_types,
            cross_component_deps=cross_component_deps,
            timestamp=datetime.now(timezone.utc),
            triggered_by=triggered_by,
        )

    def get_budget(self, dimension: ComplexityDimension) -> ComplexityBudget:
        """Get the ComplexityBudget for a specific dimension.

        Args:
            dimension: Which dimension to get budget for.

        Returns:
            ComplexityBudget with current value and limit for that dimension.
        """
        values = {
            ComplexityDimension.ADR_COUNT: self.adr_count,
            ComplexityDimension.CEREMONY_TYPES: self.ceremony_types,
            ComplexityDimension.CROSS_COMPONENT_DEPS: self.cross_component_deps,
        }
        return ComplexityBudget(
            dimension=dimension,
            limit=_get_limit_for_dimension(dimension),
            current_value=values[dimension],
        )

    def get_all_budgets(self) -> tuple[ComplexityBudget, ...]:
        """Get ComplexityBudget for all dimensions.

        Returns:
            Tuple of ComplexityBudget for each dimension.
        """
        return tuple(self.get_budget(dim) for dim in ComplexityDimension)

    @property
    def overall_status(self) -> ComplexityBudgetStatus:
        """Calculate the overall status across all dimensions.

        Returns the worst (most severe) status of any dimension.

        Returns:
            The worst status: BREACHED > WARNING > WITHIN_BUDGET.
        """
        statuses = [budget.status for budget in self.get_all_budgets()]
        if ComplexityBudgetStatus.BREACHED in statuses:
            return ComplexityBudgetStatus.BREACHED
        if ComplexityBudgetStatus.WARNING in statuses:
            return ComplexityBudgetStatus.WARNING
        return ComplexityBudgetStatus.WITHIN_BUDGET

    @property
    def breached_dimensions(self) -> tuple[ComplexityDimension, ...]:
        """Get dimensions that are currently breached.

        Returns:
            Tuple of dimensions where current value >= limit.
        """
        return tuple(
            budget.dimension for budget in self.get_all_budgets() if budget.is_breached
        )

    @property
    def warning_dimensions(self) -> tuple[ComplexityDimension, ...]:
        """Get dimensions that are at warning level.

        Returns:
            Tuple of dimensions at 80-99% utilization.
        """
        return tuple(
            budget.dimension for budget in self.get_all_budgets() if budget.is_warning
        )

    @property
    def has_breaches(self) -> bool:
        """Check if any dimension is breached.

        Returns:
            True if any dimension has current_value >= limit.
        """
        return len(self.breached_dimensions) > 0

    def to_summary(self) -> str:
        """Generate a human-readable summary.

        Returns:
            Summary string suitable for logging or display.
        """
        lines = [
            f"Complexity Snapshot ({self.timestamp.isoformat()})",
            f"Overall Status: {self.overall_status.value}",
            "",
        ]

        for budget in self.get_all_budgets():
            lines.append(budget.to_summary())

        if self.triggered_by:
            lines.append("")
            lines.append(f"Triggered by: {self.triggered_by}")

        return "\n".join(lines)
