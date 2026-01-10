"""Integration tests for Witness Attribution (Story 1.4, FR4-FR5).

Tests the complete witness attestation flow including:
- Atomic event writing with witness
- No-witness rejection (RT-1)
- Rollback on failure
- Witness signature verification

Constitutional Constraints Tested:
- CT-12: Witnessing creates accountability
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- FR81: Atomic operations - complete success or complete rollback

Note: These tests require:
- Database with migrations applied (001-004)
- OR use mocks for unit-level integration tests
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.hsm import HSMMode, SignatureResult
from src.application.services.atomic_event_writer import AtomicEventWriter
from src.application.services.signing_service import SigningService
from src.application.services.witness_service import WitnessService
from src.domain.errors.witness import NoWitnessAvailableError
from src.domain.models.witness import Witness
from src.infrastructure.adapters.persistence.witness_pool import InMemoryWitnessPool


@pytest.fixture
def mock_hsm() -> AsyncMock:
    """Create a mock HSM protocol."""
    hsm = AsyncMock()
    hsm.sign = AsyncMock(
        return_value=SignatureResult(
            content=b"test content",
            signature=b"A" * 64,  # 64-byte Ed25519 signature
            mode=HSMMode.DEVELOPMENT,
            key_id="dev-key-001",
        )
    )
    hsm.get_mode = AsyncMock(return_value=HSMMode.DEVELOPMENT)
    hsm.verify_with_key = AsyncMock(return_value=True)
    return hsm


@pytest.fixture
def mock_key_registry() -> AsyncMock:
    """Create a mock key registry."""
    registry = AsyncMock()
    return registry


@pytest.fixture
def witness_pool() -> InMemoryWitnessPool:
    """Create an in-memory witness pool."""
    return InMemoryWitnessPool()


@pytest.fixture
def active_witness() -> Witness:
    """Create an active witness for testing."""
    return Witness(
        witness_id=f"WITNESS:{uuid4()}",
        public_key=bytes(32),
        active_from=datetime.now(timezone.utc),
    )


@pytest.fixture
def signing_service(mock_hsm: AsyncMock, mock_key_registry: AsyncMock) -> SigningService:
    """Create a signing service with mocks."""
    return SigningService(hsm=mock_hsm, key_registry=mock_key_registry)


@pytest.fixture
def witness_service(mock_hsm: AsyncMock, witness_pool: InMemoryWitnessPool) -> WitnessService:
    """Create a witness service with mock HSM and in-memory pool."""
    return WitnessService(hsm=mock_hsm, witness_pool=witness_pool)


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create a mock event store."""
    store = AsyncMock()
    store.get_latest_event = AsyncMock(return_value=None)
    store.append_event = AsyncMock(side_effect=lambda e: e)
    store.count_events = AsyncMock(return_value=0)
    return store


@pytest.fixture
def atomic_writer(
    signing_service: SigningService,
    witness_service: WitnessService,
    mock_event_store: AsyncMock,
) -> AtomicEventWriter:
    """Create an atomic event writer."""
    return AtomicEventWriter(
        signing_service=signing_service,
        witness_service=witness_service,
        event_store=mock_event_store,
    )


class TestAtomicWriteWithWitness:
    """Integration tests for AC1: Atomic write with witness."""

    @pytest.mark.asyncio
    async def test_write_event_succeeds_with_witness(
        self,
        atomic_writer: AtomicEventWriter,
        witness_pool: InMemoryWitnessPool,
        active_witness: Witness,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write_event succeeds when witness is available."""
        # Register the witness
        await witness_pool.register_witness(active_witness)

        # Write event
        event = await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Verify event has witness attribution
        assert event.witness_id.startswith("WITNESS:")
        assert event.witness_signature is not None
        assert len(event.witness_signature) > 0

        # Verify event was persisted
        mock_event_store.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_event_has_agent_signature(
        self,
        atomic_writer: AtomicEventWriter,
        witness_pool: InMemoryWitnessPool,
        active_witness: Witness,
    ) -> None:
        """Test that write_event includes agent signature."""
        await witness_pool.register_witness(active_witness)

        event = await atomic_writer.write_event(
            event_type="test.event",
            payload={"key": "value"},
            agent_id="SYSTEM:TEST",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event.signature is not None
        assert event.signing_key_id is not None


class TestNoWitnessRejection:
    """Integration tests for AC2: No-witness rejection (RT-1)."""

    @pytest.mark.asyncio
    async def test_write_rejected_when_no_witnesses(
        self,
        atomic_writer: AtomicEventWriter,
        witness_pool: InMemoryWitnessPool,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write is rejected when no witnesses available."""
        # Don't register any witnesses

        with pytest.raises(NoWitnessAvailableError) as exc_info:
            await atomic_writer.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "RT-1" in str(exc_info.value)
        assert "No witnesses available" in str(exc_info.value)

        # Verify nothing was persisted
        mock_event_store.append_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_rejected_when_only_inactive_witnesses(
        self,
        atomic_writer: AtomicEventWriter,
        witness_pool: InMemoryWitnessPool,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that write is rejected when only inactive witnesses exist."""
        from datetime import timedelta

        # Register an inactive witness
        inactive = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=datetime.now(timezone.utc) - timedelta(hours=2),
            active_until=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await witness_pool.register_witness(inactive)

        with pytest.raises(NoWitnessAvailableError):
            await atomic_writer.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )

        mock_event_store.append_event.assert_not_called()


class TestRollbackOnFailure:
    """Integration tests for AC3/AC5: Rollback on failure."""

    @pytest.mark.asyncio
    async def test_rollback_when_event_store_fails(
        self,
        signing_service: SigningService,
        witness_service: WitnessService,
        witness_pool: InMemoryWitnessPool,
        active_witness: Witness,
    ) -> None:
        """Test that failure during persistence causes rollback."""
        await witness_pool.register_witness(active_witness)

        # Create event store that fails
        failing_store = AsyncMock()
        failing_store.get_latest_event = AsyncMock(return_value=None)
        failing_store.append_event = AsyncMock(side_effect=Exception("DB connection lost"))

        writer = AtomicEventWriter(
            signing_service=signing_service,
            witness_service=witness_service,
            event_store=failing_store,
        )

        with pytest.raises(Exception, match="DB connection lost"):
            await writer.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="SYSTEM:TEST",
                local_timestamp=datetime.now(timezone.utc),
            )


class TestWitnessSignatureVerification:
    """Integration tests for AC4: Witness signature verification."""

    @pytest.mark.asyncio
    async def test_verify_attestation_returns_true_for_valid(
        self,
        witness_service: WitnessService,
        witness_pool: InMemoryWitnessPool,
        active_witness: Witness,
    ) -> None:
        """Test that valid attestation can be verified."""
        await witness_pool.register_witness(active_witness)

        # First attest an event
        witness_id, witness_signature = await witness_service.attest_event(
            event_content_hash="abcd" * 16,
        )

        # Then verify the attestation
        result = await witness_service.verify_attestation(
            event_content_hash="abcd" * 16,
            witness_id=witness_id,
            witness_signature_b64=witness_signature,
        )

        assert result is True


class TestWitnessPoolIntegration:
    """Integration tests for witness pool operations."""

    @pytest.mark.asyncio
    async def test_pool_round_robin_selection(
        self, witness_pool: InMemoryWitnessPool
    ) -> None:
        """Test that witnesses are selected in round-robin order."""
        witnesses = [
            Witness(
                witness_id=f"WITNESS:test-{i}",
                public_key=bytes(32),
                active_from=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]

        for w in witnesses:
            await witness_pool.register_witness(w)

        # Get witnesses multiple times
        selected_ids = []
        for _ in range(6):
            w = await witness_pool.get_available_witness()
            selected_ids.append(w.witness_id)

        # Should cycle through all witnesses
        assert "WITNESS:test-0" in selected_ids
        assert "WITNESS:test-1" in selected_ids
        assert "WITNESS:test-2" in selected_ids

    @pytest.mark.asyncio
    async def test_pool_deactivation_prevents_selection(
        self, witness_pool: InMemoryWitnessPool, active_witness: Witness
    ) -> None:
        """Test that deactivated witnesses are not selected."""
        await witness_pool.register_witness(active_witness)

        # Verify can get witness
        w = await witness_pool.get_available_witness()
        assert w == active_witness

        # Deactivate
        await witness_pool.deactivate_witness(active_witness.witness_id)

        # Should now fail
        with pytest.raises(NoWitnessAvailableError):
            await witness_pool.get_available_witness()


class TestEndToEndFlow:
    """End-to-end integration tests for complete witness flow."""

    @pytest.mark.asyncio
    async def test_complete_atomic_write_flow(
        self,
        mock_hsm: AsyncMock,
        mock_key_registry: AsyncMock,
    ) -> None:
        """Test complete atomic write flow with all components."""
        # Setup
        witness_pool = InMemoryWitnessPool()
        witness = Witness(
            witness_id=f"WITNESS:{uuid4()}",
            public_key=bytes(32),
            active_from=datetime.now(timezone.utc),
        )
        await witness_pool.register_witness(witness)

        signing_service = SigningService(hsm=mock_hsm, key_registry=mock_key_registry)
        witness_service = WitnessService(hsm=mock_hsm, witness_pool=witness_pool)

        # Mock event store with in-memory storage
        events: list = []

        async def mock_append(event):
            events.append(event)
            return event

        event_store = AsyncMock()
        event_store.get_latest_event = AsyncMock(return_value=None)
        event_store.append_event = AsyncMock(side_effect=mock_append)

        writer = AtomicEventWriter(
            signing_service=signing_service,
            witness_service=witness_service,
            event_store=event_store,
        )

        # Execute
        event = await writer.write_event(
            event_type="conclave.vote.cast",
            payload={"archon_id": "archon-001", "vote": "yes"},
            agent_id="SYSTEM:CONCLAVE",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Verify
        assert len(events) == 1
        persisted = events[0]

        # Event has required fields
        assert persisted.event_type == "conclave.vote.cast"
        assert persisted.sequence == 1
        assert persisted.agent_id == "SYSTEM:CONCLAVE"

        # Event has agent signature
        assert persisted.signature is not None
        assert persisted.signing_key_id == "dev-key-001"

        # Event has witness attribution
        assert persisted.witness_id == witness.witness_id
        assert persisted.witness_signature is not None

        # Event has hash chain fields
        assert persisted.prev_hash is not None
        assert persisted.content_hash is not None
