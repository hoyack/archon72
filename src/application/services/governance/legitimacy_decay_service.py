"""Legitimacy decay service for automatic legitimacy band transitions.

This service handles automatic legitimacy decay based on violation events
as specified in consent-gov-5-2 story (FR29, AC1-AC9).

Constitutional Compliance:
- FR29: System can auto-transition legitimacy downward based on violation events
- AC2: Transition includes triggering event reference (NFR-AUDIT-04)
- AC3: All transitions logged with timestamp, actor, reason (NFR-CONST-04)
- AC4: Decay can skip bands based on violation severity
- AC5: System actor for automatic transitions
- AC6: Event `constitutional.legitimacy.band_decreased` emitted
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from src.application.ports.governance.legitimacy_decay_port import DecayResult
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.transition_type import TransitionType
from src.domain.governance.legitimacy.violation_severity import (
    calculate_target_band,
    get_severity_for_violation,
)

# Event type for band decreased events (AC6)
BAND_DECREASED_EVENT = "constitutional.legitimacy.band_decreased"


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


class LegitimacyDecayService:
    """Service for automatic legitimacy decay based on violations.

    This service:
    1. Receives violation events
    2. Determines severity from violation type
    3. Calculates target band based on severity
    4. Creates and records transitions with system actor
    5. Emits band_decreased events

    Asymmetric Design:
    - Decay is automatic, immediate, and objective
    - Restoration (upward) is handled by a separate service and requires acknowledgment
    """

    def __init__(
        self,
        legitimacy_port: LegitimacyStatePort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ) -> None:
        """Initialize the decay service.

        Args:
            legitimacy_port: Port for legitimacy state operations.
            event_emitter: Emitter for governance events.
            time_authority: Authority for timestamps.
        """
        self._legitimacy = legitimacy_port
        self._emitter = event_emitter
        self._time = time_authority

    async def process_violation(
        self,
        violation_event_id: UUID,
        violation_type: str,
    ) -> DecayResult:
        """Process a violation event and decay legitimacy if needed.

        This method:
        1. Gets current legitimacy state
        2. Skips if already in terminal FAILED state
        3. Determines severity from violation type
        4. Calculates target band based on severity
        5. Creates and records transition
        6. Emits band_decreased event

        Args:
            violation_event_id: Unique ID of the violation event.
            violation_type: Type string (e.g., "coercion.filter_blocked").

        Returns:
            DecayResult with transition details.
        """
        # 1. Get current state
        current_state = await self._legitimacy.get_legitimacy_state()
        current_band = current_state.current_band

        # 2. Determine severity (AC1)
        severity = get_severity_for_violation(violation_type)

        # 3. Skip if already FAILED (terminal state)
        if current_band == LegitimacyBand.FAILED:
            return DecayResult(
                transition_occurred=False,
                new_state=current_state,
                violation_event_id=violation_event_id,
                severity=severity,
                bands_dropped=0,
            )

        # 4. Calculate target band (AC4)
        target_band = calculate_target_band(current_band, severity)

        # 5. If no change needed, return early
        if target_band == current_band:
            return DecayResult(
                transition_occurred=False,
                new_state=current_state,
                violation_event_id=violation_event_id,
                severity=severity,
                bands_dropped=0,
            )

        # 6. Create transition record (AC2, AC3, AC5, AC7)
        now = self._time.now()
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=current_band,
            to_band=target_band,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",  # AC5: System actor for automatic transitions
            triggering_event_id=violation_event_id,  # AC2, AC7
            acknowledgment_id=None,  # Automatic transitions have no acknowledgment
            timestamp=now,  # AC3: Timestamp
            reason=f"Violation: {violation_type}",  # AC3: Reason
        )

        # 7. Record transition (updates state)
        await self._legitimacy.record_transition(transition)

        # 8. Get new state
        new_state = await self._legitimacy.get_legitimacy_state()

        # 9. Emit band_decreased event (AC6)
        await self._emitter.emit(
            event_type=BAND_DECREASED_EVENT,
            actor="system",
            payload={
                "from_band": current_band.value,
                "to_band": target_band.value,
                "severity": severity.value,
                "violation_type": violation_type,
                "violation_event_id": str(violation_event_id),
                "violation_count": new_state.violation_count,
                "transitioned_at": now.isoformat(),
            },
        )

        # 10. Calculate bands dropped
        bands_dropped = target_band.severity - current_band.severity

        return DecayResult(
            transition_occurred=True,
            new_state=new_state,
            violation_event_id=violation_event_id,
            severity=severity,
            bands_dropped=bands_dropped,
        )

    async def get_decay_history(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[LegitimacyTransition]:
        """Get history of automatic decay transitions.

        Returns only AUTOMATIC type transitions (decay events).

        Args:
            since: Only return transitions after this time.
            limit: Maximum number of transitions to return.

        Returns:
            List of LegitimacyTransition records for decay events.
        """
        all_transitions = await self._legitimacy.get_transition_history(
            since=since,
            limit=None,  # Filter after
        )

        # Filter to only automatic (decay) transitions
        decay_transitions = [
            t for t in all_transitions if t.transition_type == TransitionType.AUTOMATIC
        ]

        if limit:
            decay_transitions = decay_transitions[:limit]

        return decay_transitions

    async def get_decay_count(self) -> int:
        """Get total number of decay events that have occurred.

        Returns:
            Count of automatic decay transitions.
        """
        history = await self.get_decay_history()
        return len(history)
