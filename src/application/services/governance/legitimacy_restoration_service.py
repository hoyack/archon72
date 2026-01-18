"""Legitimacy restoration service for explicit upward legitimacy transitions.

This service handles human-acknowledged legitimacy restoration as specified
in consent-gov-5-3 story (FR30-FR32, AC1-AC9).

Key Principles:
- Restoration requires explicit human acknowledgment (FR30)
- No automatic upward transitions allowed (FR32)
- Only one band up at a time (AC4)
- FAILED state is terminal (AC8)
- All restorations logged with full context (FR31, NFR-CONST-04)

Constitutional Compliance:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- AC1-AC9: All acceptance criteria implemented
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.restoration_acknowledgment import (
    RestorationAcknowledgment,
    RestorationRequest,
    RestorationResult,
)
from src.domain.governance.legitimacy.transition_type import TransitionType

# Event types for restoration operations (AC6)
BAND_INCREASED_EVENT = "constitutional.legitimacy.band_increased"
RESTORATION_ACKNOWLEDGED_EVENT = "constitutional.legitimacy.restoration_acknowledged"
UNAUTHORIZED_ATTEMPT_EVENT = "security.unauthorized_restoration_attempt"


class LegitimacyStatePort(Protocol):
    """Port for legitimacy state operations."""

    async def get_current_band(self) -> LegitimacyBand:
        """Get the current legitimacy band."""
        ...

    async def get_legitimacy_state(self) -> LegitimacyState:
        """Get the full legitimacy state."""
        ...

    async def record_transition(
        self,
        transition: LegitimacyTransition,
    ) -> None:
        """Record a transition and update state."""
        ...

    async def get_transition_history(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[LegitimacyTransition]:
        """Get transition history."""
        ...


class PermissionMatrixPort(Protocol):
    """Port for permission matrix operations."""

    async def has_permission(
        self,
        actor_id: UUID,
        action: str,
    ) -> bool:
        """Check if actor has permission to perform action."""
        ...


class TimeAuthority(Protocol):
    """Protocol for time authority."""

    def now(self) -> datetime:
        """Get current time."""
        ...


class EventEmitter(Protocol):
    """Protocol for event emission."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Emit an event."""
        ...


class LegitimacyRestorationService:
    """Service for explicit legitimacy restoration with human acknowledgment.

    This service:
    1. Verifies operator authorization (AC5)
    2. Validates restoration constraints (AC4, AC8)
    3. Creates acknowledgment records (AC1, AC7)
    4. Executes one-step transitions (AC4)
    5. Emits band_increased events (AC6)

    Asymmetric Design:
    - Decay is automatic (handled by LegitimacyDecayService)
    - Restoration requires explicit human acknowledgment
    - This creates accountability and prevents premature restoration
    """

    # Permission required for restoration
    RESTORE_PERMISSION = "restore_legitimacy"

    def __init__(
        self,
        legitimacy_port: LegitimacyStatePort,
        permission_port: PermissionMatrixPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ) -> None:
        """Initialize the restoration service.

        Args:
            legitimacy_port: Port for legitimacy state operations.
            permission_port: Port for permission checks.
            event_emitter: Emitter for governance events.
            time_authority: Authority for timestamps.
        """
        self._legitimacy = legitimacy_port
        self._permissions = permission_port
        self._emitter = event_emitter
        self._time = time_authority
        self._acknowledgments: dict[UUID, RestorationAcknowledgment] = {}

    async def request_restoration(
        self,
        request: RestorationRequest,
    ) -> RestorationResult:
        """Request legitimacy restoration with acknowledgment.

        Implements AC1-AC8:
        1. Verifies operator authorization (AC5)
        2. Gets current state and validates FAILED constraint (AC8)
        3. Validates one-step-at-a-time constraint (AC4)
        4. Validates restoration is upward (AC2)
        5. Creates and records acknowledgment (AC1, AC3, AC7)
        6. Executes the transition
        7. Emits band_increased event (AC6)

        Args:
            request: The restoration request with operator, target, reason, evidence.

        Returns:
            RestorationResult indicating success or failure.
        """
        # 1. Verify authorization (AC5)
        is_authorized = await self._verify_restoration_permission(request.operator_id)
        if not is_authorized:
            return RestorationResult.failed(
                "Operator not authorized to restore legitimacy"
            )

        # 2. Get current state
        current_state = await self._legitimacy.get_legitimacy_state()
        current_band = current_state.current_band

        # 3. Validate FAILED constraint (AC8)
        if current_band == LegitimacyBand.FAILED:
            return RestorationResult.failed(
                "FAILED is terminal - reconstitution required"
            )

        # 4. Validate restoration is upward (AC2)
        target_band = request.target_band
        if target_band.severity >= current_band.severity:
            return RestorationResult.failed(
                f"Restoration must be upward: {current_band.value} → {target_band.value} "
                f"(severity {current_band.severity} → {target_band.severity})"
            )

        # 5. Validate one-step constraint (AC4)
        severity_change = current_band.severity - target_band.severity
        if severity_change != 1:
            return RestorationResult.failed(
                f"Restoration must be one step at a time. "
                f"Current: {current_band.value} (severity {current_band.severity}), "
                f"Target: {target_band.value} (severity {target_band.severity}). "
                f"Allowed target: {LegitimacyBand.from_severity(current_band.severity - 1).value}"
            )

        # 6. Create acknowledgment (AC1, AC7)
        now = self._time.now()
        acknowledgment = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=request.operator_id,
            from_band=current_band,
            to_band=target_band,
            reason=request.reason,
            evidence=request.evidence,
            acknowledged_at=now,
        )

        # 7. Record acknowledgment to ledger (AC3)
        await self._record_acknowledgment(acknowledgment)

        # 8. Create and record transition
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=current_band,
            to_band=target_band,
            transition_type=TransitionType.ACKNOWLEDGED,
            actor=str(request.operator_id),  # Human operator, not "system"
            triggering_event_id=None,  # Acknowledged transitions have no trigger
            acknowledgment_id=acknowledgment.acknowledgment_id,
            timestamp=now,
            reason=request.reason,
        )

        await self._legitimacy.record_transition(transition)

        # 9. Get new state
        new_state = await self._legitimacy.get_legitimacy_state()

        # 10. Emit band_increased event (AC6)
        await self._emitter.emit(
            event_type=BAND_INCREASED_EVENT,
            actor=str(request.operator_id),
            payload={
                "from_band": current_band.value,
                "to_band": target_band.value,
                "operator_id": str(request.operator_id),
                "acknowledgment_id": str(acknowledgment.acknowledgment_id),
                "reason": request.reason,
                "restored_at": now.isoformat(),
            },
        )

        return RestorationResult.succeeded(new_state, acknowledgment)

    async def _verify_restoration_permission(self, operator_id: UUID) -> bool:
        """Verify operator has restoration permission.

        Args:
            operator_id: UUID of the operator to check.

        Returns:
            True if operator has restore_legitimacy permission.
        """
        has_permission = await self._permissions.has_permission(
            operator_id,
            self.RESTORE_PERMISSION,
        )

        if not has_permission:
            # Log unauthorized attempt
            await self._emitter.emit(
                event_type=UNAUTHORIZED_ATTEMPT_EVENT,
                actor=str(operator_id),
                payload={
                    "attempted_action": self.RESTORE_PERMISSION,
                    "attempted_at": self._time.now().isoformat(),
                },
            )

        return has_permission

    async def _record_acknowledgment(
        self,
        acknowledgment: RestorationAcknowledgment,
    ) -> None:
        """Record acknowledgment to append-only ledger.

        Args:
            acknowledgment: The acknowledgment to record.
        """
        # Store in-memory (adapter would persist)
        self._acknowledgments[acknowledgment.acknowledgment_id] = acknowledgment

        # Emit acknowledgment event for ledger (AC3)
        await self._emitter.emit(
            event_type=RESTORATION_ACKNOWLEDGED_EVENT,
            actor=str(acknowledgment.operator_id),
            payload={
                "acknowledgment_id": str(acknowledgment.acknowledgment_id),
                "from_band": acknowledgment.from_band.value,
                "to_band": acknowledgment.to_band.value,
                "reason": acknowledgment.reason,
                "evidence": acknowledgment.evidence,
                "acknowledged_at": acknowledgment.acknowledged_at.isoformat(),
            },
        )

    async def get_restoration_history(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RestorationAcknowledgment]:
        """Get history of restoration acknowledgments.

        Args:
            since: Only return acknowledgments after this time.
            limit: Maximum number of acknowledgments to return.

        Returns:
            List of RestorationAcknowledgment records, oldest first.
        """
        # Get all acknowledgments
        acknowledgments = list(self._acknowledgments.values())

        # Filter by time if specified
        if since:
            acknowledgments = [a for a in acknowledgments if a.acknowledged_at > since]

        # Sort by time (oldest first)
        acknowledgments.sort(key=lambda a: a.acknowledged_at)

        # Apply limit if specified
        if limit:
            acknowledgments = acknowledgments[:limit]

        return acknowledgments

    async def get_acknowledgment(
        self,
        acknowledgment_id: UUID,
    ) -> RestorationAcknowledgment | None:
        """Get a specific acknowledgment by ID.

        Args:
            acknowledgment_id: The unique ID of the acknowledgment.

        Returns:
            The acknowledgment record, or None if not found.
        """
        return self._acknowledgments.get(acknowledgment_id)

    async def get_restoration_count(self) -> int:
        """Get total number of successful restorations.

        Returns:
            Count of successful restoration operations.
        """
        return len(self._acknowledgments)
