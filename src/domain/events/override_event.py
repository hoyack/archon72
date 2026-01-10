"""Override event payload for Keeper override actions (Story 5.1, FR23; Story 5.2, FR24).

This module defines the OverrideEventPayload for override events.
Override actions MUST be logged BEFORE they take effect (FR23).
Override duration MUST be bounded (FR24).

Constitutional Constraints:
- FR23: Override actions must be logged before they take effect
- FR24: Override duration must be bounded (max 7 days)
- CT-11: Silent failure destroys legitimacy -> Log failure = NO override execution
- CT-12: Witnessing creates accountability -> OverrideEvent MUST be witnessed

Developer Golden Rules:
1. LOG FIRST - Override event must be written BEFORE override executes
2. WITNESS EVERYTHING - All overrides must be witnessed
3. FAIL LOUD - Failed log = override rejection
4. NO INDEFINITE OVERRIDES - Duration is bounded (FR24)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.override import DurationValidationError

if TYPE_CHECKING:
    pass

# Event type constant for override initiated
OVERRIDE_EVENT_TYPE: str = "override.initiated"

# Event type constant for override expired (AC2)
OVERRIDE_EXPIRED_EVENT_TYPE: str = "override.expired"

# Maximum duration for an override (7 days) - FR24
MAX_DURATION_SECONDS: int = 604800  # 7 * 24 * 60 * 60


class ActionType(Enum):
    """Types of override actions (from Architecture ADR-4).

    Each action type represents a category of Keeper intervention.
    """

    CONFIG_CHANGE = "CONFIG_CHANGE"
    """Modify operational configuration parameters."""

    CEREMONY_OVERRIDE = "CEREMONY_OVERRIDE"
    """Override ceremony health check requirement."""

    SYSTEM_RESTART = "SYSTEM_RESTART"
    """Restart system component (e.g., watchdog)."""

    HALT_CLEAR = "HALT_CLEAR"
    """Clear halt state (reference existing Story 3.4 implementation)."""


@dataclass(frozen=True, eq=True)
class OverrideEventPayload:
    """Payload for override events - immutable.

    An OverrideEvent is created when a Keeper initiates an override action.
    This event MUST be written to the event store BEFORE the override
    action executes (FR23 requirement).

    Constitutional Constraints:
    - FR23: Override must be logged before taking effect
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        keeper_id: ID of the Keeper initiating the override.
        scope: What is being overridden (component, policy, etc.).
        duration: Duration of the override in seconds (must be > 0).
        reason: Human-readable reason for the override.
        action_type: Type of override action.
        initiated_at: When the override was initiated (UTC).

    Note:
        This event creates the audit trail for override actions.
        The override action MUST NOT execute if this event fails to write.
    """

    # ID of Keeper initiating the override
    keeper_id: str

    # What is being overridden
    scope: str

    # Duration in seconds (must be > 0)
    duration: int

    # Human-readable reason
    reason: str

    # Type of override action
    action_type: ActionType

    # When the override was initiated (should be UTC)
    initiated_at: datetime

    def __post_init__(self) -> None:
        """Validate fields on creation.

        Raises:
            ConstitutionalViolationError: If validation fails.
        """
        self._validate_keeper_id()
        self._validate_scope()
        self._validate_duration()
        self._validate_reason()

    def _validate_keeper_id(self) -> None:
        """Validate keeper_id is non-empty."""
        if not self.keeper_id or not self.keeper_id.strip():
            raise ConstitutionalViolationError(
                "FR23: Override validation failed - keeper_id must be non-empty"
            )

    def _validate_scope(self) -> None:
        """Validate scope is non-empty."""
        if not self.scope or not self.scope.strip():
            raise ConstitutionalViolationError(
                "FR23: Override validation failed - scope must be non-empty"
            )

    def _validate_duration(self) -> None:
        """Validate duration is positive and within bounds (FR24).

        Raises:
            ConstitutionalViolationError: If duration is <= 0.
            DurationValidationError: If duration exceeds max (7 days).
        """
        if self.duration <= 0:
            raise ConstitutionalViolationError(
                f"FR23: Override validation failed - duration must be > 0, got {self.duration}"
            )
        if self.duration > MAX_DURATION_SECONDS:
            raise DurationValidationError(
                f"FR24: Duration exceeds maximum of 7 days ({MAX_DURATION_SECONDS} seconds) - "
                f"got {self.duration} seconds"
            )

    def _validate_reason(self) -> None:
        """Validate reason is non-empty."""
        if not self.reason or not self.reason.strip():
            raise ConstitutionalViolationError(
                "FR23: Override validation failed - reason must be non-empty"
            )

    @property
    def expires_at(self) -> datetime:
        """Calculate when this override expires.

        Returns:
            datetime: The expiration timestamp (initiated_at + duration).
        """
        return self.initiated_at + timedelta(seconds=self.duration)

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing.

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": "OverrideEvent",
                "keeper_id": self.keeper_id,
                "scope": self.scope,
                "duration": self.duration,
                "reason": self.reason,
                "action_type": self.action_type.value,
                "initiated_at": self.initiated_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")


@dataclass(frozen=True, eq=True)
class OverrideExpiredEventPayload:
    """Payload for override expiration events - immutable (AC2, Story 5.2).

    An OverrideExpiredEvent is created when an override's duration elapses
    and it automatically reverts. This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy -> Expiration must be logged
    - CT-12: Witnessing creates accountability -> Event MUST be witnessed
    - FR24: Override duration must be bounded -> Triggers automatic expiration

    Attributes:
        original_override_id: Reference to the original override event.
        keeper_id: ID of the Keeper who initiated the original override.
        scope: What was overridden (component, policy, etc.).
        expired_at: When the override expired (UTC).
        reversion_status: "success" or "failed" indicating reversion outcome.
    """

    # Reference to the original override event
    original_override_id: UUID

    # ID of Keeper who initiated the override
    keeper_id: str

    # What was overridden
    scope: str

    # When the override expired (should be UTC)
    expired_at: datetime

    # Reversion outcome: "success" or "failed"
    reversion_status: str

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": "OverrideExpiredEvent",
                "original_override_id": str(self.original_override_id),
                "keeper_id": self.keeper_id,
                "scope": self.scope,
                "expired_at": self.expired_at.isoformat(),
                "reversion_status": self.reversion_status,
            },
            sort_keys=True,
        ).encode("utf-8")
