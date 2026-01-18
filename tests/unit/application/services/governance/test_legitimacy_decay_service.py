"""Unit tests for LegitimacyDecayService.

Tests the automatic legitimacy decay service as specified in
consent-gov-5-2 story (FR29, AC1-AC9).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.governance.legitimacy_decay_service import (
    BAND_DECREASED_EVENT,
    LegitimacyDecayService,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.transition_type import TransitionType
from src.domain.governance.legitimacy.violation_severity import ViolationSeverity


class FakeLegitimacyPort:
    """Fake LegitimacyPort for testing."""

    def __init__(self, initial_state: LegitimacyState) -> None:
        self._state = initial_state
        self._transitions: list[LegitimacyTransition] = []

    async def get_current_band(self) -> LegitimacyBand:
        return self._state.current_band

    async def get_legitimacy_state(self) -> LegitimacyState:
        return self._state

    async def record_transition(self, transition: LegitimacyTransition) -> None:
        self._transitions.append(transition)
        # Update state to reflect transition
        self._state = self._state.with_new_band(
            new_band=transition.to_band,
            entered_at=transition.timestamp,
            triggering_event_id=transition.triggering_event_id,
            transition_type=transition.transition_type,
            increment_violations=True,
        )

    async def get_transition_history(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[LegitimacyTransition]:
        result = self._transitions
        if since:
            result = [t for t in result if t.timestamp >= since]
        if limit:
            result = result[:limit]
        return result

    async def get_violation_count(self) -> int:
        return self._state.violation_count

    async def initialize_state(
        self,
        initial_band: LegitimacyBand,
        timestamp: datetime,
    ) -> LegitimacyState:
        self._state = LegitimacyState.initial(timestamp)
        return self._state

    async def get_state_at(self, timestamp: datetime) -> LegitimacyState | None:
        return self._state


class FakeTimeAuthority:
    """Fake TimeAuthority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._fixed_time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._fixed_time


class FakeEventEmitter:
    """Fake event emitter for capturing emitted events."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )

    def get_last(self, event_type: str | None = None) -> dict | None:
        if event_type:
            for event in reversed(self.events):
                if event["event_type"] == event_type:
                    return event
            return None
        return self.events[-1] if self.events else None


@pytest.fixture
def fixed_time() -> datetime:
    """Fixed timestamp for tests."""
    return datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def stable_state(fixed_time: datetime) -> LegitimacyState:
    """Initial stable state."""
    return LegitimacyState(
        current_band=LegitimacyBand.STABLE,
        entered_at=fixed_time,
        violation_count=0,
        last_triggering_event_id=None,
        last_transition_type=TransitionType.AUTOMATIC,
    )


@pytest.fixture
def strained_state(fixed_time: datetime) -> LegitimacyState:
    """Strained state with some violations."""
    return LegitimacyState(
        current_band=LegitimacyBand.STRAINED,
        entered_at=fixed_time,
        violation_count=2,
        last_triggering_event_id=uuid4(),
        last_transition_type=TransitionType.AUTOMATIC,
    )


@pytest.fixture
def compromised_state(fixed_time: datetime) -> LegitimacyState:
    """Compromised state."""
    return LegitimacyState(
        current_band=LegitimacyBand.COMPROMISED,
        entered_at=fixed_time,
        violation_count=5,
        last_triggering_event_id=uuid4(),
        last_transition_type=TransitionType.AUTOMATIC,
    )


@pytest.fixture
def failed_state(fixed_time: datetime) -> LegitimacyState:
    """Failed (terminal) state."""
    return LegitimacyState(
        current_band=LegitimacyBand.FAILED,
        entered_at=fixed_time,
        violation_count=10,
        last_triggering_event_id=uuid4(),
        last_transition_type=TransitionType.AUTOMATIC,
    )


@pytest.fixture
def time_authority(fixed_time: datetime) -> FakeTimeAuthority:
    """Time authority returning fixed time."""
    return FakeTimeAuthority(fixed_time)


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Event emitter for capturing events."""
    return FakeEventEmitter()


def create_service(
    initial_state: LegitimacyState,
    time_authority: FakeTimeAuthority,
    event_emitter: FakeEventEmitter,
) -> tuple[LegitimacyDecayService, FakeLegitimacyPort]:
    """Create service with fake dependencies."""
    legitimacy_port = FakeLegitimacyPort(initial_state)
    service = LegitimacyDecayService(
        legitimacy_port=legitimacy_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )
    return service, legitimacy_port


class TestMinorViolationDecay:
    """Tests for MINOR violation decay (AC1, AC4)."""

    @pytest.mark.asyncio
    async def test_minor_from_stable_drops_one_band(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Minor violation from STABLE drops to STRAINED."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        result = await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        assert result.transition_occurred is True
        assert result.new_state is not None
        assert result.new_state.current_band == LegitimacyBand.STRAINED
        assert result.severity == ViolationSeverity.MINOR
        assert result.bands_dropped == 1


class TestMajorViolationDecay:
    """Tests for MAJOR violation decay (AC1, AC4)."""

    @pytest.mark.asyncio
    async def test_major_from_stable_drops_two_bands(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Major violation from STABLE drops to ERODING (skips STRAINED)."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        result = await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        assert result.transition_occurred is True
        assert result.new_state is not None
        assert result.new_state.current_band == LegitimacyBand.ERODING
        assert result.severity == ViolationSeverity.MAJOR
        assert result.bands_dropped == 2


class TestCriticalViolationDecay:
    """Tests for CRITICAL violation decay (AC1, AC4)."""

    @pytest.mark.asyncio
    async def test_critical_jumps_to_compromised(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Critical violation jumps directly to COMPROMISED."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        result = await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.unauthorized_creation",
        )

        assert result.transition_occurred is True
        assert result.new_state is not None
        assert result.new_state.current_band == LegitimacyBand.COMPROMISED
        assert result.severity == ViolationSeverity.CRITICAL


class TestIntegrityViolationDecay:
    """Tests for INTEGRITY violation decay (AC1, AC4)."""

    @pytest.mark.asyncio
    async def test_integrity_goes_to_failed(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Integrity violation goes immediately to FAILED."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        result = await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="chain.discontinuity",
        )

        assert result.transition_occurred is True
        assert result.new_state is not None
        assert result.new_state.current_band == LegitimacyBand.FAILED
        assert result.severity == ViolationSeverity.INTEGRITY


class TestTerminalState:
    """Tests for FAILED (terminal) state behavior."""

    @pytest.mark.asyncio
    async def test_failed_state_no_transition(
        self,
        failed_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """FAILED state does not change on further violations."""
        service, _ = create_service(failed_state, time_authority, event_emitter)

        result = await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="chain.discontinuity",
        )

        assert result.transition_occurred is False
        assert result.bands_dropped == 0


class TestTransitionRecording:
    """Tests for transition recording (AC2, AC3, AC7)."""

    @pytest.mark.asyncio
    async def test_transition_includes_triggering_event(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Transition record includes triggering event ID (AC2, AC7)."""
        service, port = create_service(stable_state, time_authority, event_emitter)
        violation_id = uuid4()

        await service.process_violation(
            violation_event_id=violation_id,
            violation_type="coercion.filter_blocked",
        )

        transitions = await port.get_transition_history()
        assert len(transitions) == 1
        assert transitions[0].triggering_event_id == violation_id

    @pytest.mark.asyncio
    async def test_transition_has_system_actor(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Automatic transitions have 'system' actor (AC5)."""
        service, port = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        transitions = await port.get_transition_history()
        assert transitions[0].actor == "system"

    @pytest.mark.asyncio
    async def test_transition_has_timestamp(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
        fixed_time: datetime,
    ) -> None:
        """Transition includes timestamp (AC3)."""
        service, port = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        transitions = await port.get_transition_history()
        assert transitions[0].timestamp == fixed_time

    @pytest.mark.asyncio
    async def test_transition_has_reason(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Transition includes reason describing violation (AC3)."""
        service, port = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        transitions = await port.get_transition_history()
        assert "coercion.filter_blocked" in transitions[0].reason


class TestViolationAccumulation:
    """Tests for violation count accumulation (AC8)."""

    @pytest.mark.asyncio
    async def test_violation_count_increments(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Violation count increments with each violation."""
        service, port = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        state = await port.get_legitimacy_state()
        assert state.violation_count == 1

    @pytest.mark.asyncio
    async def test_violation_count_accumulates_across_transitions(
        self,
        strained_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Violation count persists and accumulates across transitions."""
        service, port = create_service(strained_state, time_authority, event_emitter)
        initial_count = strained_state.violation_count

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        state = await port.get_legitimacy_state()
        assert state.violation_count == initial_count + 1


class TestEventEmission:
    """Tests for band_decreased event emission (AC6)."""

    @pytest.mark.asyncio
    async def test_band_decreased_event_emitted(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Band decreased event is emitted on decay (AC6)."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        event = event_emitter.get_last(BAND_DECREASED_EVENT)
        assert event is not None
        assert event["event_type"] == BAND_DECREASED_EVENT
        assert event["actor"] == "system"

    @pytest.mark.asyncio
    async def test_event_includes_band_transition_details(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event payload includes from_band, to_band, severity."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        event = event_emitter.get_last(BAND_DECREASED_EVENT)
        assert event["payload"]["from_band"] == "stable"
        assert event["payload"]["to_band"] == "eroding"
        assert event["payload"]["severity"] == "major"

    @pytest.mark.asyncio
    async def test_event_includes_violation_event_id(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event payload includes violation_event_id."""
        service, _ = create_service(stable_state, time_authority, event_emitter)
        violation_id = uuid4()

        await service.process_violation(
            violation_event_id=violation_id,
            violation_type="coercion.filter_blocked",
        )

        event = event_emitter.get_last(BAND_DECREASED_EVENT)
        assert event["payload"]["violation_event_id"] == str(violation_id)

    @pytest.mark.asyncio
    async def test_no_event_when_no_transition(
        self,
        failed_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """No event emitted when already in terminal state."""
        service, _ = create_service(failed_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="chain.discontinuity",
        )

        # No events emitted because no transition occurred
        assert event_emitter.get_last(BAND_DECREASED_EVENT) is None


class TestDecayHistory:
    """Tests for decay history queries."""

    @pytest.mark.asyncio
    async def test_get_decay_history(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Get decay history returns only automatic transitions."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        history = await service.get_decay_history()
        assert len(history) == 1
        assert history[0].transition_type == TransitionType.AUTOMATIC

    @pytest.mark.asyncio
    async def test_get_decay_count(
        self,
        stable_state: LegitimacyState,
        time_authority: FakeTimeAuthority,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Get decay count returns number of decay events."""
        service, _ = create_service(stable_state, time_authority, event_emitter)

        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )
        await service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        count = await service.get_decay_count()
        assert count == 2
