"""Unit tests for AtomicEventWriter (FR4, FR5, AC5, FR6).

Tests the atomic event writing with witness attestation and clock drift detection.

Constitutional Constraints Tested:
- CT-12: Witnessing creates accountability
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- FR6: Events must have dual timestamps (Story 1.5)
- FR81: Atomic operations - complete success or complete rollback
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.atomic_event_writer import AtomicEventWriter
from src.application.services.time_authority_service import TimeAuthorityService
from src.domain.errors.witness import NoWitnessAvailableError


@pytest.fixture
def mock_signing_service() -> AsyncMock:
    """Create a mock SigningService."""
    service = AsyncMock()
    service.sign_event = AsyncMock(
        return_value=(
            "base64_agent_signature",  # signature
            "agent-key-001",  # signing_key_id
            1,  # sig_alg_version
        )
    )
    return service


@pytest.fixture
def mock_witness_service() -> AsyncMock:
    """Create a mock WitnessService."""
    service = AsyncMock()
    service.attest_event = AsyncMock(
        return_value=(
            f"WITNESS:{uuid4()}",  # witness_id
            "base64_witness_signature",  # witness_signature_b64
        )
    )
    return service


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create a mock EventStorePort."""
    store = AsyncMock()
    store.get_latest_event = AsyncMock(return_value=None)
    store.append_event = AsyncMock(return_value=MagicMock())
    store.count_events = AsyncMock(return_value=0)
    return store


@pytest.fixture
def atomic_writer(
    mock_signing_service: AsyncMock,
    mock_witness_service: AsyncMock,
    mock_event_store: AsyncMock,
) -> AtomicEventWriter:
    """Create an AtomicEventWriter with mock dependencies."""
    return AtomicEventWriter(
        signing_service=mock_signing_service,
        witness_service=mock_witness_service,
        event_store=mock_event_store,
    )


class TestAtomicEventWriterWriteEvent:
    """Tests for write_event() method."""

    @pytest.mark.asyncio
    async def test_write_event_coordinates_signing_and_witness(
        self,
        atomic_writer: AtomicEventWriter,
        mock_signing_service: AsyncMock,
        mock_witness_service: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write_event coordinates agent signing and witness attestation."""
        await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        mock_signing_service.sign_event.assert_called_once()
        mock_witness_service.attest_event.assert_called_once()
        mock_event_store.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_event_returns_event_with_witness(
        self,
        atomic_writer: AtomicEventWriter,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write_event returns event with witness attribution."""
        from src.domain.events.event import Event

        # Create a mock event to return
        mock_event = MagicMock(spec=Event)
        mock_event_store.append_event = AsyncMock(return_value=mock_event)

        result = await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert result is mock_event

    @pytest.mark.asyncio
    async def test_write_event_uses_agent_signature(
        self,
        atomic_writer: AtomicEventWriter,
        mock_signing_service: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that the event includes the agent signature."""
        await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Check that append_event was called with an event containing the agent signature
        call_args = mock_event_store.append_event.call_args
        event = call_args[0][0]
        assert event.signature == "base64_agent_signature"
        assert event.signing_key_id == "agent-key-001"

    @pytest.mark.asyncio
    async def test_write_event_uses_witness_attestation(
        self,
        atomic_writer: AtomicEventWriter,
        mock_witness_service: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that the event includes the witness attestation."""
        await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Check that append_event was called with an event containing witness
        call_args = mock_event_store.append_event.call_args
        event = call_args[0][0]
        assert event.witness_id.startswith("WITNESS:")
        assert event.witness_signature == "base64_witness_signature"


class TestAtomicEventWriterNoWitness:
    """Tests for no-witness-available scenarios (AC2)."""

    @pytest.mark.asyncio
    async def test_write_event_fails_when_no_witness_available(
        self,
        mock_signing_service: AsyncMock,
        mock_witness_service: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write_event raises NoWitnessAvailableError when pool is empty."""
        mock_witness_service.attest_event = AsyncMock(
            side_effect=NoWitnessAvailableError()
        )
        writer = AtomicEventWriter(
            signing_service=mock_signing_service,
            witness_service=mock_witness_service,
            event_store=mock_event_store,
        )

        with pytest.raises(NoWitnessAvailableError) as exc_info:
            await writer.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "RT-1" in str(exc_info.value)
        assert "No witnesses available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_event_persisted_when_no_witness(
        self,
        mock_signing_service: AsyncMock,
        mock_witness_service: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that no event is persisted when witness is unavailable."""
        mock_witness_service.attest_event = AsyncMock(
            side_effect=NoWitnessAvailableError()
        )
        writer = AtomicEventWriter(
            signing_service=mock_signing_service,
            witness_service=mock_witness_service,
            event_store=mock_event_store,
        )

        with pytest.raises(NoWitnessAvailableError):
            await writer.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        # Event store should NOT have been called
        mock_event_store.append_event.assert_not_called()


class TestAtomicEventWriterRollback:
    """Tests for rollback scenarios (AC3, AC5)."""

    @pytest.mark.asyncio
    async def test_rollback_when_event_store_fails(
        self,
        mock_signing_service: AsyncMock,
        mock_witness_service: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that failure during event store append causes rollback."""
        mock_event_store.append_event = AsyncMock(
            side_effect=Exception("Database error")
        )
        writer = AtomicEventWriter(
            signing_service=mock_signing_service,
            witness_service=mock_witness_service,
            event_store=mock_event_store,
        )

        with pytest.raises(Exception, match="Database error"):
            await writer.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_rollback_when_signing_fails(
        self,
        mock_signing_service: AsyncMock,
        mock_witness_service: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that failure during agent signing causes rollback."""
        mock_signing_service.sign_event = AsyncMock(
            side_effect=Exception("Signing error")
        )
        writer = AtomicEventWriter(
            signing_service=mock_signing_service,
            witness_service=mock_witness_service,
            event_store=mock_event_store,
        )

        with pytest.raises(Exception, match="Signing error"):
            await writer.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        # Neither witness nor event store should have been called
        mock_witness_service.attest_event.assert_not_called()
        mock_event_store.append_event.assert_not_called()


class TestAtomicEventWriterHashChain:
    """Tests for hash chain continuity."""

    @pytest.mark.asyncio
    async def test_first_event_uses_genesis_hash(
        self,
        atomic_writer: AtomicEventWriter,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that first event uses genesis hash for prev_hash."""
        mock_event_store.get_latest_event = AsyncMock(return_value=None)

        await atomic_writer.write_event(
            event_type="genesis.event",
            payload={},
            agent_id="SYSTEM:GENESIS",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Check that event has sequence 1 (genesis)
        call_args = mock_event_store.append_event.call_args
        event = call_args[0][0]
        assert event.sequence == 1

    @pytest.mark.asyncio
    async def test_subsequent_event_chains_to_previous(
        self,
        atomic_writer: AtomicEventWriter,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that subsequent events chain to previous event hash."""
        # Mock a previous event
        mock_prev_event = MagicMock()
        mock_prev_event.sequence = 1
        mock_prev_event.content_hash = "prev_content_hash_12345"
        mock_event_store.get_latest_event = AsyncMock(return_value=mock_prev_event)

        await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Check that event has sequence 2 and correct prev_hash
        call_args = mock_event_store.append_event.call_args
        event = call_args[0][0]
        assert event.sequence == 2
        assert event.prev_hash == "prev_content_hash_12345"


class TestAtomicEventWriterTimeAuthority:
    """Tests for TimeAuthorityService integration (Story 1.5, AC1, AC4)."""

    @pytest.fixture
    def mock_time_authority(self) -> MagicMock:
        """Create a mock TimeAuthorityService."""
        service = MagicMock(spec=TimeAuthorityService)
        service.check_drift = MagicMock(return_value=timedelta(seconds=0))
        return service

    @pytest.fixture
    def writer_with_time_authority(
        self,
        mock_signing_service: AsyncMock,
        mock_witness_service: AsyncMock,
        mock_event_store: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> AtomicEventWriter:
        """Create an AtomicEventWriter with TimeAuthorityService."""
        return AtomicEventWriter(
            signing_service=mock_signing_service,
            witness_service=mock_witness_service,
            event_store=mock_event_store,
            time_authority=mock_time_authority,
        )

    @pytest.mark.asyncio
    async def test_write_event_checks_drift_after_successful_write(
        self,
        writer_with_time_authority: AtomicEventWriter,
        mock_event_store: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Test that clock drift is checked after successful event write (AC4)."""
        # Set up mock event with authority_timestamp
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.authority_timestamp = datetime.now(timezone.utc)
        mock_event.local_timestamp = datetime.now(timezone.utc)
        mock_event_store.append_event = AsyncMock(return_value=mock_event)

        await writer_with_time_authority.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        # TimeAuthorityService.check_drift should have been called
        mock_time_authority.check_drift.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_event_passes_correct_timestamps_to_drift_check(
        self,
        writer_with_time_authority: AtomicEventWriter,
        mock_event_store: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Test that correct timestamps are passed to drift check."""
        local_ts = datetime.now(timezone.utc)
        authority_ts = datetime.now(timezone.utc) + timedelta(seconds=2)

        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.authority_timestamp = authority_ts
        mock_event.local_timestamp = local_ts
        mock_event_store.append_event = AsyncMock(return_value=mock_event)

        await writer_with_time_authority.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=local_ts,
        )

        call_kwargs = mock_time_authority.check_drift.call_args.kwargs
        assert call_kwargs["local_timestamp"] == local_ts
        assert call_kwargs["authority_timestamp"] == authority_ts

    @pytest.mark.asyncio
    async def test_write_event_continues_even_with_drift(
        self,
        writer_with_time_authority: AtomicEventWriter,
        mock_event_store: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Test that event is still returned even when drift is detected (AC4)."""
        # Simulate drift detection returning large drift
        mock_time_authority.check_drift = MagicMock(
            return_value=timedelta(seconds=10)
        )

        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.authority_timestamp = datetime.now(timezone.utc)
        mock_event.local_timestamp = datetime.now(timezone.utc)
        mock_event_store.append_event = AsyncMock(return_value=mock_event)

        result = await writer_with_time_authority.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Event should still be returned (drift doesn't reject events)
        assert result is mock_event

    @pytest.mark.asyncio
    async def test_write_event_without_time_authority_skips_drift_check(
        self,
        atomic_writer: AtomicEventWriter,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that drift check is skipped when no TimeAuthorityService configured."""
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.authority_timestamp = datetime.now(timezone.utc)
        mock_event.local_timestamp = datetime.now(timezone.utc)
        mock_event_store.append_event = AsyncMock(return_value=mock_event)

        # Should not raise any exceptions
        result = await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert result is mock_event

    @pytest.mark.asyncio
    async def test_write_event_skips_drift_check_when_no_authority_timestamp(
        self,
        writer_with_time_authority: AtomicEventWriter,
        mock_event_store: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Test that drift check is skipped when authority_timestamp is None."""
        mock_event = MagicMock()
        mock_event.event_id = uuid4()
        mock_event.authority_timestamp = None  # No authority timestamp
        mock_event.local_timestamp = datetime.now(timezone.utc)
        mock_event_store.append_event = AsyncMock(return_value=mock_event)

        await writer_with_time_authority.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        # TimeAuthorityService.check_drift should NOT have been called
        mock_time_authority.check_drift.assert_not_called()
