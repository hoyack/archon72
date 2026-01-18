"""Unit tests for LegitimacyRestorationService.

Tests the explicit legitimacy restoration service as specified in
consent-gov-5-3 story (FR30-FR32, AC1-AC9).

Constitutional Compliance:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- AC1-AC9: All acceptance criteria tested
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.legitimacy_restoration_service import (
    BAND_INCREASED_EVENT,
    RESTORATION_ACKNOWLEDGED_EVENT,
    UNAUTHORIZED_ATTEMPT_EVENT,
    LegitimacyRestorationService,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.restoration_acknowledgment import (
    RestorationRequest,
)
from src.domain.governance.legitimacy.transition_type import TransitionType


class FakeLegitimacyPort:
    """Fake implementation of LegitimacyStatePort for testing."""

    def __init__(self, initial_band: LegitimacyBand = LegitimacyBand.STRAINED) -> None:
        self.current_band = initial_band
        self.transitions: list[LegitimacyTransition] = []
        self.state = LegitimacyState(
            current_band=initial_band,
            entered_at=datetime.now(timezone.utc),
            violation_count=5,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

    async def get_current_band(self) -> LegitimacyBand:
        return self.current_band

    async def get_legitimacy_state(self) -> LegitimacyState:
        return self.state

    async def record_transition(self, transition: LegitimacyTransition) -> None:
        self.transitions.append(transition)
        self.current_band = transition.to_band
        self.state = LegitimacyState(
            current_band=transition.to_band,
            entered_at=transition.timestamp,
            violation_count=self.state.violation_count,
            last_triggering_event_id=None,
            last_transition_type=transition.transition_type,
        )

    async def get_transition_history(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[LegitimacyTransition]:
        return self.transitions


class FakePermissionPort:
    """Fake implementation of PermissionMatrixPort for testing."""

    def __init__(self, authorized_operators: set[UUID] | None = None) -> None:
        self.authorized_operators = authorized_operators or set()

    async def has_permission(self, actor_id: UUID, action: str) -> bool:
        return actor_id in self.authorized_operators


class FakeTimeAuthority:
    """Fake implementation of TimeAuthority for testing."""

    def __init__(self) -> None:
        self.current_time = datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self.current_time


class FakeEventEmitter:
    """Fake implementation of EventEmitter for testing."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, event_type: str, actor: str, payload: dict) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )

    def get_events_by_type(self, event_type: str) -> list[dict]:
        return [e for e in self.events if e["event_type"] == event_type]

    def get_last_event(self, event_type: str) -> dict | None:
        events = self.get_events_by_type(event_type)
        return events[-1] if events else None


@pytest.fixture
def authorized_operator() -> UUID:
    """Create an authorized operator ID."""
    return uuid4()


@pytest.fixture
def unauthorized_operator() -> UUID:
    """Create an unauthorized operator ID."""
    return uuid4()


@pytest.fixture
def legitimacy_port() -> FakeLegitimacyPort:
    """Create a fake legitimacy port starting at STRAINED."""
    return FakeLegitimacyPort(LegitimacyBand.STRAINED)


@pytest.fixture
def permission_port(authorized_operator: UUID) -> FakePermissionPort:
    """Create a fake permission port with authorized operator."""
    return FakePermissionPort({authorized_operator})


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create a fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Create a fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def restoration_service(
    legitimacy_port: FakeLegitimacyPort,
    permission_port: FakePermissionPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> LegitimacyRestorationService:
    """Create a restoration service with fakes."""
    return LegitimacyRestorationService(
        legitimacy_port=legitimacy_port,
        permission_port=permission_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


class TestAcknowledgmentRequired:
    """Test AC1: Upward transition requires explicit acknowledgment."""

    async def test_acknowledgment_required_for_upward(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
    ) -> None:
        """Upward transition requires acknowledgment."""
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Audit complete",
            )
        )

        assert result.success
        assert result.acknowledgment is not None
        assert result.new_state.current_band == LegitimacyBand.STABLE

    async def test_acknowledgment_created_with_reason_and_evidence(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
    ) -> None:
        """Acknowledgment includes reason and evidence (AC7)."""
        reason = "Coercion patterns addressed in content review"
        evidence = "Audit ID: AUD-2026-0117, all patterns resolved"

        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason=reason,
                evidence=evidence,
            )
        )

        assert result.acknowledgment.reason == reason
        assert result.acknowledgment.evidence == evidence


class TestNoAutomaticUpward:
    """Test AC2: No automatic upward transitions."""

    async def test_restoration_must_be_upward(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        legitimacy_port: FakeLegitimacyPort,
    ) -> None:
        """Restoration rejects downward target."""
        # Set current state to STABLE
        legitimacy_port.current_band = LegitimacyBand.STABLE
        legitimacy_port.state = LegitimacyState(
            current_band=LegitimacyBand.STABLE,
            entered_at=datetime.now(timezone.utc),
            violation_count=0,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.ACKNOWLEDGED,
        )

        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STRAINED,  # Downward
                reason="Trying to go down",
                evidence="Evidence",
            )
        )

        assert not result.success
        assert "upward" in result.error.lower()


class TestAcknowledgmentLogged:
    """Test AC3: Acknowledgment logged in append-only ledger."""

    async def test_acknowledgment_logged_to_ledger(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Acknowledgment is logged via event emission."""
        reason = "Issues resolved"
        evidence = "Audit ID: AUD-123"

        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason=reason,
                evidence=evidence,
            )
        )

        event = event_emitter.get_last_event(RESTORATION_ACKNOWLEDGED_EVENT)
        assert event is not None
        assert event["payload"]["reason"] == reason
        assert event["payload"]["evidence"] == evidence


class TestOneStepAtATime:
    """Test AC4: Only one band up at a time."""

    async def test_one_step_at_a_time_enforced(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        legitimacy_port: FakeLegitimacyPort,
    ) -> None:
        """Multi-step restoration is rejected."""
        # Set to COMPROMISED (severity 3)
        legitimacy_port.current_band = LegitimacyBand.COMPROMISED
        legitimacy_port.state = LegitimacyState(
            current_band=LegitimacyBand.COMPROMISED,
            entered_at=datetime.now(timezone.utc),
            violation_count=10,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        # Try to jump to STABLE (severity 0) - 3 steps
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Everything is fixed",
                evidence="Trust me",
            )
        )

        assert not result.success
        assert "one step" in result.error.lower()

    async def test_one_step_restoration_allowed(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        legitimacy_port: FakeLegitimacyPort,
    ) -> None:
        """Single step restoration succeeds."""
        # Set to ERODING (severity 2)
        legitimacy_port.current_band = LegitimacyBand.ERODING
        legitimacy_port.state = LegitimacyState(
            current_band=LegitimacyBand.ERODING,
            entered_at=datetime.now(timezone.utc),
            violation_count=5,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        # Move to STRAINED (severity 1) - exactly 1 step
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STRAINED,
                reason="Issues addressed",
                evidence="Audit complete",
            )
        )

        assert result.success
        assert result.new_state.current_band == LegitimacyBand.STRAINED


class TestAuthorizationRequired:
    """Test AC5: Operator must be authenticated and authorized."""

    async def test_unauthorized_operator_rejected(
        self,
        restoration_service: LegitimacyRestorationService,
        unauthorized_operator: UUID,
    ) -> None:
        """Unauthorized operator cannot restore."""
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=unauthorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Trying to restore",
                evidence="No authorization",
            )
        )

        assert not result.success
        assert "authorized" in result.error.lower()

    async def test_unauthorized_attempt_logged(
        self,
        restoration_service: LegitimacyRestorationService,
        unauthorized_operator: UUID,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Unauthorized attempts are logged."""
        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=unauthorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Trying",
                evidence="Evidence",
            )
        )

        event = event_emitter.get_last_event(UNAUTHORIZED_ATTEMPT_EVENT)
        assert event is not None
        assert event["actor"] == str(unauthorized_operator)


class TestBandIncreasedEvent:
    """Test AC6: Event `constitutional.legitimacy.band_increased` emitted."""

    async def test_band_increased_event_emitted(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Band increased event is emitted on restoration."""
        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Evidence",
            )
        )

        event = event_emitter.get_last_event(BAND_INCREASED_EVENT)
        assert event is not None
        assert event["payload"]["from_band"] == "strained"
        assert event["payload"]["to_band"] == "stable"
        assert event["actor"] == str(authorized_operator)

    async def test_band_increased_event_has_acknowledgment_id(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event includes acknowledgment ID for traceability."""
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Evidence",
            )
        )

        event = event_emitter.get_last_event(BAND_INCREASED_EVENT)
        assert event["payload"]["acknowledgment_id"] == str(
            result.acknowledgment.acknowledgment_id
        )


class TestFailedIsTerminal:
    """Test AC8: FAILED state cannot be restored."""

    async def test_failed_cannot_be_restored(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        legitimacy_port: FakeLegitimacyPort,
    ) -> None:
        """FAILED state is terminal and cannot be restored."""
        # Set to FAILED
        legitimacy_port.current_band = LegitimacyBand.FAILED
        legitimacy_port.state = LegitimacyState(
            current_band=LegitimacyBand.FAILED,
            entered_at=datetime.now(timezone.utc),
            violation_count=100,
            last_triggering_event_id=uuid4(),
            last_transition_type=TransitionType.AUTOMATIC,
        )

        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.COMPROMISED,
                reason="Attempting restore",
                evidence="Evidence",
            )
        )

        assert not result.success
        assert (
            "terminal" in result.error.lower()
            or "reconstitution" in result.error.lower()
        )


class TestRestorationHistory:
    """Tests for restoration history tracking."""

    async def test_restoration_history_empty_initially(
        self,
        restoration_service: LegitimacyRestorationService,
    ) -> None:
        """History is empty before any restorations."""
        history = await restoration_service.get_restoration_history()
        assert len(history) == 0

    async def test_restoration_history_tracks_acknowledgments(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
    ) -> None:
        """History contains acknowledgments after restoration."""
        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Evidence",
            )
        )

        history = await restoration_service.get_restoration_history()
        assert len(history) == 1
        assert history[0].reason == "Issues resolved"

    async def test_get_acknowledgment_by_id(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
    ) -> None:
        """Can retrieve acknowledgment by ID."""
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Evidence",
            )
        )

        ack = await restoration_service.get_acknowledgment(
            result.acknowledgment.acknowledgment_id
        )
        assert ack is not None
        assert ack.acknowledgment_id == result.acknowledgment.acknowledgment_id

    async def test_get_acknowledgment_not_found(
        self,
        restoration_service: LegitimacyRestorationService,
    ) -> None:
        """Returns None for non-existent acknowledgment."""
        ack = await restoration_service.get_acknowledgment(uuid4())
        assert ack is None

    async def test_restoration_count(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
    ) -> None:
        """Count tracks successful restorations."""
        assert await restoration_service.get_restoration_count() == 0

        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Evidence",
            )
        )

        assert await restoration_service.get_restoration_count() == 1


class TestGradualRestorationWorkflow:
    """Integration test for gradual restoration from COMPROMISED to STABLE."""

    async def test_gradual_restoration_from_compromised(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        legitimacy_port: FakeLegitimacyPort,
    ) -> None:
        """Restoration from COMPROMISED requires multiple steps."""
        # Set to COMPROMISED
        legitimacy_port.current_band = LegitimacyBand.COMPROMISED
        legitimacy_port.state = LegitimacyState(
            current_band=LegitimacyBand.COMPROMISED,
            entered_at=datetime.now(timezone.utc),
            violation_count=10,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        # Step 1: COMPROMISED → ERODING
        result1 = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.ERODING,
                reason="Critical issues addressed",
                evidence="Audit 1",
            )
        )
        assert result1.success
        assert result1.new_state.current_band == LegitimacyBand.ERODING

        # Step 2: ERODING → STRAINED
        result2 = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STRAINED,
                reason="Significant issues addressed",
                evidence="Audit 2",
            )
        )
        assert result2.success
        assert result2.new_state.current_band == LegitimacyBand.STRAINED

        # Step 3: STRAINED → STABLE
        result3 = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="All issues resolved",
                evidence="Audit 3",
            )
        )
        assert result3.success
        assert result3.new_state.current_band == LegitimacyBand.STABLE

        # Verify 3 acknowledgments recorded
        assert await restoration_service.get_restoration_count() == 3


class TestTransitionRecording:
    """Test that transitions are properly recorded."""

    async def test_transition_recorded_with_acknowledged_type(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: UUID,
        legitimacy_port: FakeLegitimacyPort,
    ) -> None:
        """Transition is recorded with ACKNOWLEDGED type."""
        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Evidence",
            )
        )

        assert len(legitimacy_port.transitions) == 1
        transition = legitimacy_port.transitions[0]
        assert transition.transition_type == TransitionType.ACKNOWLEDGED
        assert transition.actor == str(authorized_operator)
        assert transition.acknowledgment_id is not None
