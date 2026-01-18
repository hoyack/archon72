"""Complexity Budget event payloads (Story 8.6, SC-3, RT-6).

This module defines the event payloads for complexity budget violations:
- ComplexityBudgetBreachedPayload: When a complexity budget limit is exceeded
- ComplexityBudgetEscalatedPayload: When a breach is escalated due to no governance approval

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event, not just alert
- CT-11: Silent failure destroys legitimacy → All breach events must be logged
- CT-12: Witnessing creates accountability → All events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating breach events (writes)
2. WITNESS EVERYTHING - All breach events require attribution
3. FAIL LOUD - Never silently swallow event creation errors
4. RT-6 ENFORCEMENT - Breach requires governance ceremony, not just alert
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.complexity_budget import ComplexityDimension

# Event type constants for complexity budget events
COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE: str = "complexity.budget.breached"
COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE: str = "complexity.budget.escalated"

# System agent ID for complexity events (automated system, not human agent)
COMPLEXITY_SYSTEM_AGENT_ID: str = "system.complexity_monitor"


@dataclass(frozen=True, eq=True)
class ComplexityBudgetBreachedPayload:
    """Payload for complexity budget breach events (RT-6, AC: 2,3).

    A ComplexityBudgetBreachedPayload is created when a complexity dimension
    exceeds its budget limit. Per RT-6, this is a constitutional event
    requiring governance ceremony approval, not just an operational alert.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - CT-14: Complexity is a failure vector. Complexity must be budgeted.
    - RT-6: Breach = constitutional event requiring governance ceremony
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        breach_id: Unique identifier for this breach event.
        dimension: Which complexity dimension was breached.
        limit: The configured limit for this dimension.
        actual_value: The actual value that triggered the breach.
        breached_at: When the breach was detected (UTC).
        requires_governance_ceremony: True if governance approval is required.
        resolution_deadline: When the breach must be resolved to avoid escalation.
        governance_approval_id: Optional ID if governance ceremony approved this.
        resolved_at: When the breach was resolved (if resolved).
    """

    breach_id: UUID
    dimension: ComplexityDimension
    limit: int
    actual_value: int
    breached_at: datetime
    requires_governance_ceremony: bool = True  # RT-6 default
    resolution_deadline: datetime | None = None
    governance_approval_id: UUID | None = None
    resolved_at: datetime | None = None

    @property
    def is_resolved(self) -> bool:
        """Check if this breach has been resolved.

        Returns:
            True if the breach has a resolution timestamp.
        """
        return self.resolved_at is not None

    @property
    def overage(self) -> int:
        """Calculate how much the limit was exceeded by.

        Returns:
            The amount over the limit (0 if under).
        """
        return max(0, self.actual_value - self.limit)

    @property
    def overage_percent(self) -> float:
        """Calculate overage as a percentage.

        Returns:
            Percentage over the limit.
        """
        return (self.overage / self.limit) * 100.0 if self.limit > 0 else 0.0

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "actual_value": self.actual_value,
            "breach_id": str(self.breach_id),
            "breached_at": self.breached_at.isoformat(),
            "dimension": self.dimension.value,
            "limit": self.limit,
            "requires_governance_ceremony": self.requires_governance_ceremony,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        result: dict[str, Any] = {
            "breach_id": str(self.breach_id),
            "dimension": self.dimension.value,
            "limit": self.limit,
            "actual_value": self.actual_value,
            "breached_at": self.breached_at.isoformat(),
            "requires_governance_ceremony": self.requires_governance_ceremony,
        }

        if self.resolution_deadline:
            result["resolution_deadline"] = self.resolution_deadline.isoformat()
        if self.governance_approval_id:
            result["governance_approval_id"] = str(self.governance_approval_id)
        if self.resolved_at:
            result["resolved_at"] = self.resolved_at.isoformat()

        return result


@dataclass(frozen=True, eq=True)
class ComplexityBudgetEscalatedPayload:
    """Payload for complexity budget escalation events (RT-6, AC: 4).

    A ComplexityBudgetEscalatedPayload is created when a breach exceeds
    its resolution deadline without governance ceremony approval.
    This represents a more severe constitutional violation.

    Per RT-6, escalation creates additional constitutional pressure
    to address the complexity budget breach.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - RT-6: Automatic escalation if limits exceeded without ceremony approval
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        escalation_id: Unique identifier for this escalation event.
        breach_id: Reference to the original breach being escalated.
        dimension: Which complexity dimension was breached.
        original_breach_at: When the original breach occurred.
        escalated_at: When this escalation was triggered.
        days_without_resolution: Days since breach without governance approval.
        escalation_level: Level of escalation (1, 2, 3, etc.).
        requires_immediate_action: True if requires immediate attention.
    """

    escalation_id: UUID
    breach_id: UUID
    dimension: ComplexityDimension
    original_breach_at: datetime
    escalated_at: datetime
    days_without_resolution: int
    escalation_level: int = 1
    requires_immediate_action: bool = False

    def __post_init__(self) -> None:
        """Validate escalation data."""
        if self.days_without_resolution < 0:
            raise ValueError(
                f"days_without_resolution cannot be negative, got {self.days_without_resolution}"
            )
        if self.escalation_level < 1:
            raise ValueError(
                f"escalation_level must be at least 1, got {self.escalation_level}"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "breach_id": str(self.breach_id),
            "days_without_resolution": self.days_without_resolution,
            "dimension": self.dimension.value,
            "escalated_at": self.escalated_at.isoformat(),
            "escalation_id": str(self.escalation_id),
            "escalation_level": self.escalation_level,
            "original_breach_at": self.original_breach_at.isoformat(),
            "requires_immediate_action": self.requires_immediate_action,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "escalation_id": str(self.escalation_id),
            "breach_id": str(self.breach_id),
            "dimension": self.dimension.value,
            "original_breach_at": self.original_breach_at.isoformat(),
            "escalated_at": self.escalated_at.isoformat(),
            "days_without_resolution": self.days_without_resolution,
            "escalation_level": self.escalation_level,
            "requires_immediate_action": self.requires_immediate_action,
        }
