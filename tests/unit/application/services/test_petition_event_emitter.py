"""Unit tests for PetitionEventEmitter service (Story 1.2, FR-1.7; Story 1.7, FR-2.5).

Tests cover:
- Successful event emission (petition.received)
- Event payload structure
- Error handling (graceful degradation for petition.received)
- Time authority injection (HARDENING-1)
- Fate event emission (Story 1.7, FR-2.5, HC-1)
- Fate event MUST raise on failure (no graceful degradation)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.petition_event_emitter import PetitionEventEmitter
from src.domain.events.petition import (
    PETITION_ACKNOWLEDGED_EVENT_TYPE,
    PETITION_DEFERRED_EVENT_TYPE,
    PETITION_ESCALATED_EVENT_TYPE,
    PETITION_NO_RESPONSE_EVENT_TYPE,
    PETITION_RECEIVED_EVENT_TYPE,
    PETITION_REFERRED_EVENT_TYPE,
    PETITION_SYSTEM_AGENT_ID,
)


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._time

    def utcnow(self) -> datetime:
        return self._time

    def monotonic(self) -> float:
        return 12345.0


class TestPetitionEventEmitterEmitReceived:
    """Tests for emit_petition_received method."""

    @pytest.fixture
    def mock_ledger(self) -> AsyncMock:
        """Create a mock ledger."""
        ledger = AsyncMock()
        ledger.append_event = AsyncMock()
        return ledger

    @pytest.fixture
    def time_authority(self) -> FakeTimeAuthority:
        """Create a fake time authority."""
        return FakeTimeAuthority()

    @pytest.fixture
    def emitter(
        self, mock_ledger: AsyncMock, time_authority: FakeTimeAuthority
    ) -> PetitionEventEmitter:
        """Create an emitter with mock dependencies."""
        return PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

    @pytest.mark.asyncio
    async def test_emit_returns_true_on_success(
        self, emitter: PetitionEventEmitter
    ) -> None:
        """Test successful emission returns True."""
        result = await emitter.emit_petition_received(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash123==",
            submitter_id=None,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_emit_calls_ledger_append(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test emission calls ledger.append_event()."""
        await emitter.emit_petition_received(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash123==",
            submitter_id=None,
        )
        mock_ledger.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_creates_correct_event_type(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test emission creates event with correct type."""
        await emitter.emit_petition_received(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash123==",
            submitter_id=None,
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]  # First positional argument
        assert event.event_type == PETITION_RECEIVED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_emit_uses_petition_system_agent(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test emission uses petition-system as actor_id."""
        await emitter.emit_petition_received(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash123==",
            submitter_id=None,
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.actor_id == PETITION_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_emit_uses_petition_id_as_trace_id(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test emission uses petition_id as trace_id for correlation."""
        petition_id = uuid4()
        await emitter.emit_petition_received(
            petition_id=petition_id,
            petition_type="GENERAL",
            realm="default",
            content_hash="hash123==",
            submitter_id=None,
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.trace_id == str(petition_id)

    @pytest.mark.asyncio
    async def test_emit_includes_all_payload_fields(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test emission includes all required payload fields."""
        petition_id = uuid4()
        submitter_id = uuid4()

        await emitter.emit_petition_received(
            petition_id=petition_id,
            petition_type="CESSATION",
            realm="governance",
            content_hash="abc123hash==",
            submitter_id=submitter_id,
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        payload = dict(event.payload)

        assert payload["petition_id"] == str(petition_id)
        assert payload["petition_type"] == "CESSATION"
        assert payload["realm"] == "governance"
        assert payload["content_hash"] == "abc123hash=="
        assert payload["submitter_id"] == str(submitter_id)
        assert "received_timestamp" in payload

    @pytest.mark.asyncio
    async def test_emit_handles_null_submitter(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test emission handles null submitter_id correctly."""
        await emitter.emit_petition_received(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash==",
            submitter_id=None,
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        payload = dict(event.payload)

        assert payload["submitter_id"] is None

    @pytest.mark.asyncio
    async def test_emit_uses_time_authority(self, mock_ledger: AsyncMock) -> None:
        """Test emission uses injected time authority (HARDENING-1)."""
        fixed_time = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        time_authority = FakeTimeAuthority(fixed_time)
        emitter = PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

        await emitter.emit_petition_received(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash==",
            submitter_id=None,
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]

        assert event.timestamp == fixed_time
        assert "2026-06-15" in dict(event.payload)["received_timestamp"]


class TestPetitionEventEmitterErrorHandling:
    """Tests for error handling in PetitionEventEmitter."""

    @pytest.fixture
    def time_authority(self) -> FakeTimeAuthority:
        """Create a fake time authority."""
        return FakeTimeAuthority()

    @pytest.mark.asyncio
    async def test_emit_returns_false_on_ledger_error(
        self, time_authority: FakeTimeAuthority
    ) -> None:
        """Test emission returns False when ledger fails (graceful degradation)."""
        mock_ledger = AsyncMock()
        mock_ledger.append_event = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        emitter = PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

        result = await emitter.emit_petition_received(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash==",
            submitter_id=None,
        )

        # Should return False, not raise
        assert result is False

    @pytest.mark.asyncio
    async def test_emit_does_not_raise_on_ledger_error(
        self, time_authority: FakeTimeAuthority
    ) -> None:
        """Test emission doesn't raise exception when ledger fails."""
        mock_ledger = AsyncMock()
        mock_ledger.append_event = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        emitter = PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

        # Should not raise - errors are logged and swallowed
        try:
            await emitter.emit_petition_received(
                petition_id=uuid4(),
                petition_type="GENERAL",
                realm="default",
                content_hash="hash==",
                submitter_id=None,
            )
        except Exception:
            pytest.fail("emit_petition_received should not raise exceptions")


class TestPetitionEventEmitterFateEvents:
    """Tests for emit_fate_event method (Story 1.7, FR-2.5, HC-1)."""

    @pytest.fixture
    def mock_ledger(self) -> AsyncMock:
        """Create a mock ledger."""
        ledger = AsyncMock()
        ledger.append_event = AsyncMock()
        return ledger

    @pytest.fixture
    def time_authority(self) -> FakeTimeAuthority:
        """Create a fake time authority."""
        return FakeTimeAuthority()

    @pytest.fixture
    def emitter(
        self, mock_ledger: AsyncMock, time_authority: FakeTimeAuthority
    ) -> PetitionEventEmitter:
        """Create an emitter with mock dependencies."""
        return PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

    @pytest.mark.asyncio
    async def test_emit_fate_acknowledged_success(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test successful ACKNOWLEDGED fate event emission."""
        petition_id = uuid4()
        await emitter.emit_fate_event(
            petition_id=petition_id,
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="clotho-agent",
            reason="Routine acknowledgment",
        )

        mock_ledger.append_event.assert_called_once()
        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.event_type == PETITION_ACKNOWLEDGED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_emit_fate_referred_success(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test successful REFERRED fate event emission."""
        petition_id = uuid4()
        await emitter.emit_fate_event(
            petition_id=petition_id,
            previous_state="DELIBERATING",
            new_state="REFERRED",
            actor_id="lachesis-agent",
            reason="Requires knight intervention",
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.event_type == PETITION_REFERRED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_emit_fate_escalated_success(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test successful ESCALATED fate event emission."""
        petition_id = uuid4()
        await emitter.emit_fate_event(
            petition_id=petition_id,
            previous_state="DELIBERATING",
            new_state="ESCALATED",
            actor_id="atropos-agent",
            reason="Constitutional concern",
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.event_type == PETITION_ESCALATED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_emit_fate_uses_actor_id(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test fate event uses provided actor_id, not system agent."""
        await emitter.emit_fate_event(
            petition_id=uuid4(),
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="clotho-agent",
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.actor_id == "clotho-agent"

    @pytest.mark.asyncio
    async def test_emit_fate_includes_all_payload_fields(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test fate event includes all required payload fields."""
        petition_id = uuid4()
        await emitter.emit_fate_event(
            petition_id=petition_id,
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="clotho-agent",
            reason="Test reason",
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        payload = dict(event.payload)

        assert payload["petition_id"] == str(petition_id)
        assert payload["previous_state"] == "RECEIVED"
        assert payload["new_state"] == "ACKNOWLEDGED"
        assert payload["actor_id"] == "clotho-agent"
        assert payload["reason"] == "Test reason"
        assert "timestamp" in payload
        assert "schema_version" in payload

    @pytest.mark.asyncio
    async def test_emit_fate_reason_is_optional(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test fate event works with None reason."""
        await emitter.emit_fate_event(
            petition_id=uuid4(),
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="clotho-agent",
            reason=None,
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        payload = dict(event.payload)

        assert payload["reason"] is None

    @pytest.mark.asyncio
    async def test_emit_fate_uses_petition_id_as_trace_id(
        self, emitter: PetitionEventEmitter, mock_ledger: AsyncMock
    ) -> None:
        """Test fate event uses petition_id as trace_id for correlation."""
        petition_id = uuid4()
        await emitter.emit_fate_event(
            petition_id=petition_id,
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="clotho-agent",
        )

        call_args = mock_ledger.append_event.call_args
        event = call_args[0][0]
        assert event.trace_id == str(petition_id)


class TestPetitionEventEmitterFateErrorHandling:
    """Tests for fate event error handling - MUST raise (HC-1)."""

    @pytest.fixture
    def time_authority(self) -> FakeTimeAuthority:
        """Create a fake time authority."""
        return FakeTimeAuthority()

    @pytest.mark.asyncio
    async def test_emit_fate_raises_on_ledger_error(
        self, time_authority: FakeTimeAuthority
    ) -> None:
        """Test fate emission RAISES when ledger fails (HC-1 - no graceful degradation)."""
        mock_ledger = AsyncMock()
        mock_ledger.append_event = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        emitter = PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

        # MUST raise - caller needs to rollback state change
        with pytest.raises(Exception, match="Database connection failed"):
            await emitter.emit_fate_event(
                petition_id=uuid4(),
                previous_state="RECEIVED",
                new_state="ACKNOWLEDGED",
                actor_id="clotho-agent",
            )

    @pytest.mark.asyncio
    async def test_emit_fate_raises_for_invalid_state(
        self, time_authority: FakeTimeAuthority
    ) -> None:
        """Test fate emission raises ValueError for invalid state."""
        mock_ledger = AsyncMock()
        emitter = PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

        with pytest.raises(ValueError, match="Invalid fate state"):
            await emitter.emit_fate_event(
                petition_id=uuid4(),
                previous_state="RECEIVED",
                new_state="INVALID_STATE",
                actor_id="clotho-agent",
            )

    @pytest.mark.asyncio
    async def test_emit_fate_rejects_non_terminal_states(
        self, time_authority: FakeTimeAuthority
    ) -> None:
        """Test fate emission rejects non-terminal states."""
        mock_ledger = AsyncMock()
        emitter = PetitionEventEmitter(
            ledger=mock_ledger,
            time_authority=time_authority,
        )

        # DELIBERATING is not a terminal fate state
        with pytest.raises(ValueError, match="Invalid fate state"):
            await emitter.emit_fate_event(
                petition_id=uuid4(),
                previous_state="RECEIVED",
                new_state="DELIBERATING",
                actor_id="clotho-agent",
            )

        # RECEIVED is not a terminal fate state
        with pytest.raises(ValueError, match="Invalid fate state"):
            await emitter.emit_fate_event(
                petition_id=uuid4(),
                previous_state="RECEIVED",
                new_state="RECEIVED",
                actor_id="clotho-agent",
            )


class TestPetitionEventEmitterGetFateEventType:
    """Tests for _get_fate_event_type static method."""

    def test_acknowledged_maps_correctly(self) -> None:
        """Test ACKNOWLEDGED maps to petition.acknowledged event type."""
        result = PetitionEventEmitter._get_fate_event_type("ACKNOWLEDGED")
        assert result == PETITION_ACKNOWLEDGED_EVENT_TYPE

    def test_referred_maps_correctly(self) -> None:
        """Test REFERRED maps to petition.referred event type."""
        result = PetitionEventEmitter._get_fate_event_type("REFERRED")
        assert result == PETITION_REFERRED_EVENT_TYPE

    def test_escalated_maps_correctly(self) -> None:
        """Test ESCALATED maps to petition.escalated event type."""
        result = PetitionEventEmitter._get_fate_event_type("ESCALATED")
        assert result == PETITION_ESCALATED_EVENT_TYPE

    def test_deferred_maps_correctly(self) -> None:
        """Test DEFERRED maps to petition.deferred event type."""
        result = PetitionEventEmitter._get_fate_event_type("DEFERRED")
        assert result == PETITION_DEFERRED_EVENT_TYPE

    def test_no_response_maps_correctly(self) -> None:
        """Test NO_RESPONSE maps to petition.no_response event type."""
        result = PetitionEventEmitter._get_fate_event_type("NO_RESPONSE")
        assert result == PETITION_NO_RESPONSE_EVENT_TYPE

    def test_invalid_state_raises_value_error(self) -> None:
        """Test invalid state raises ValueError."""
        with pytest.raises(ValueError, match="Invalid fate state"):
            PetitionEventEmitter._get_fate_event_type("INVALID")

    def test_lowercase_state_raises_value_error(self) -> None:
        """Test lowercase state raises ValueError (must be uppercase)."""
        with pytest.raises(ValueError, match="Invalid fate state"):
            PetitionEventEmitter._get_fate_event_type("acknowledged")
