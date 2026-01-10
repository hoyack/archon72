"""Complexity budget errors (Story 8.6, SC-3, RT-6).

Domain errors for complexity budget violations.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event, not just alert.
- SC-3: Self-consistency finding - complexity budget dashboard required.

Usage:
    from src.domain.errors.complexity_budget import (
        ComplexityBudgetBreachedError,
        ComplexityBudgetApprovalRequiredError,
        ComplexityBudgetEscalationError,
    )

    # Raise on budget breach
    if budget.is_breached:
        raise ComplexityBudgetBreachedError(
            dimension=budget.dimension,
            limit=budget.limit,
            actual_value=budget.current_value,
        )
"""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.complexity_budget import ComplexityDimension


class ComplexityBudgetBreachedError(Exception):
    """Raised when a complexity budget limit is exceeded.

    Constitutional Constraint (CT-14):
    Complexity is a failure vector. This error is raised when any
    complexity dimension exceeds its budgeted limit.

    Red Team Hardening (RT-6):
    This error represents a constitutional event, not just an operational
    alert. A governance ceremony is required to proceed.

    Attributes:
        dimension: Which complexity dimension was breached.
        limit: The configured limit for this dimension.
        actual_value: The actual value that triggered the breach.
        breach_id: Optional breach event ID if already recorded.
        message: Human-readable error message.
    """

    def __init__(
        self,
        dimension: "ComplexityDimension",
        limit: int,
        actual_value: int,
        breach_id: Optional[UUID] = None,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            dimension: Which dimension was breached.
            limit: The configured limit.
            actual_value: The actual value triggering breach.
            breach_id: Optional breach event ID.
            message: Optional custom message.
        """
        self.dimension = dimension
        self.limit = limit
        self.actual_value = actual_value
        self.breach_id = breach_id
        self.overage = actual_value - limit

        if message is None:
            message = (
                f"Complexity budget breached: {dimension.value} is {actual_value} "
                f"(limit: {limit}, overage: {self.overage}). "
                f"CT-14: Complexity must be budgeted. "
                f"RT-6: Governance ceremony required to proceed."
            )

        self.message = message
        super().__init__(self.message)

    def get_remediation_hints(self) -> list[str]:
        """Get remediation hints for this breach.

        Returns:
            List of human-readable remediation suggestions.
        """
        hints = []

        dimension_name = self.dimension.value

        if dimension_name == "adr_count":
            hints.append(
                f"ADR count ({self.actual_value}) exceeds limit ({self.limit}). "
                "Consider consolidating or retiring outdated ADRs. "
                "Review architectural decisions for redundancy."
            )
        elif dimension_name == "ceremony_types":
            hints.append(
                f"Ceremony type count ({self.actual_value}) exceeds limit ({self.limit}). "
                "Consider merging similar ceremony types or retiring unused ones. "
                "Each ceremony type adds governance complexity."
            )
        elif dimension_name == "cross_component_deps":
            hints.append(
                f"Cross-component dependency count ({self.actual_value}) exceeds limit ({self.limit}). "
                "Consider reducing coupling between components. "
                "Review for circular dependencies or unnecessary integrations."
            )
        else:
            hints.append(
                f"Dimension '{dimension_name}' ({self.actual_value}) exceeds limit ({self.limit}). "
                "Review and reduce complexity in this dimension."
            )

        hints.append(
            "RT-6: A governance ceremony is required to approve exceeding this limit. "
            "Contact the governance team to schedule a complexity review ceremony."
        )

        return hints


class ComplexityBudgetApprovalRequiredError(Exception):
    """Raised when governance ceremony approval is required for a breach.

    Red Team Hardening (RT-6):
    Exceeding complexity limits requires governance ceremony approval,
    not just an operational alert. This error is raised when an operation
    would proceed without required approval.

    Attributes:
        dimension: Which complexity dimension requires approval.
        breach_id: The breach event ID requiring approval.
        message: Human-readable error message.
    """

    def __init__(
        self,
        dimension: "ComplexityDimension",
        breach_id: UUID,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            dimension: Which dimension requires approval.
            breach_id: The breach event requiring approval.
            message: Optional custom message.
        """
        self.dimension = dimension
        self.breach_id = breach_id

        if message is None:
            message = (
                f"Governance ceremony approval required for complexity breach: "
                f"{dimension.value} (breach_id: {breach_id}). "
                f"RT-6: Cannot proceed without governance approval. "
                f"Schedule a complexity budget review ceremony."
            )

        self.message = message
        super().__init__(self.message)


class ComplexityBudgetEscalationError(Exception):
    """Raised when a breach has been escalated due to lack of resolution.

    Red Team Hardening (RT-6):
    If a complexity breach is not addressed within the escalation period
    (default 7 days), it is automatically escalated. This represents a
    more severe constitutional violation.

    Attributes:
        breach_id: The original breach event ID.
        escalation_id: The escalation event ID.
        days_without_resolution: Days since the breach without approval.
        escalation_level: Current escalation level (1, 2, 3, etc.).
        message: Human-readable error message.
    """

    def __init__(
        self,
        breach_id: UUID,
        escalation_id: UUID,
        days_without_resolution: int,
        escalation_level: int = 1,
        message: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            breach_id: The original breach ID.
            escalation_id: The escalation event ID.
            days_without_resolution: Days since breach.
            escalation_level: Escalation level (1, 2, 3...).
            message: Optional custom message.
        """
        self.breach_id = breach_id
        self.escalation_id = escalation_id
        self.days_without_resolution = days_without_resolution
        self.escalation_level = escalation_level

        if message is None:
            severity = "CRITICAL" if escalation_level >= 2 else "ELEVATED"
            message = (
                f"[{severity}] Complexity budget breach escalated: "
                f"breach_id={breach_id}, escalation_level={escalation_level}. "
                f"Unresolved for {days_without_resolution} days. "
                f"RT-6: Immediate governance action required."
            )

        self.message = message
        super().__init__(self.message)

    @property
    def is_critical(self) -> bool:
        """Check if this escalation is at critical level.

        Returns:
            True if escalation_level >= 2.
        """
        return self.escalation_level >= 2

    @property
    def requires_immediate_action(self) -> bool:
        """Check if this escalation requires immediate action.

        Returns:
            True if days_without_resolution > 14 or escalation_level >= 2.
        """
        return self.days_without_resolution > 14 or self.escalation_level >= 2
