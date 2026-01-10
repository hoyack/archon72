"""Unit tests for EventReplicatorStub (Story 1.10).

Tests for:
- Stub returns success receipts in dev mode
- Stub verify_replicas returns positive result
- Stub failure mode for testing
- Stub replica ID configuration for testing
"""

from uuid import uuid4

import pytest

from src.application.ports.event_replicator import (
    ReplicationStatus,
)
from src.infrastructure.stubs.event_replicator_stub import EventReplicatorStub


@pytest.fixture
def stub() -> EventReplicatorStub:
    """Create a fresh EventReplicatorStub for each test."""
    return EventReplicatorStub()


class TestEventReplicatorStubInit:
    """Tests for EventReplicatorStub initialization."""

    def test_default_init(self) -> None:
        """Stub should initialize with defaults (no replicas, no failure)."""
        stub = EventReplicatorStub()

        assert stub._force_failure is False
        assert stub._replica_ids == ()

    def test_init_with_force_failure(self) -> None:
        """Stub should accept force_failure parameter."""
        stub = EventReplicatorStub(force_failure=True)

        assert stub._force_failure is True

    def test_init_with_replica_ids(self) -> None:
        """Stub should accept replica_ids parameter."""
        stub = EventReplicatorStub(replica_ids=["replica-1", "replica-2"])

        assert stub._replica_ids == ("replica-1", "replica-2")


class TestPropagateEvent:
    """Tests for EventReplicatorStub.propagate_event()."""

    @pytest.mark.asyncio
    async def test_propagate_no_replicas(self, stub: EventReplicatorStub) -> None:
        """Should return NOT_CONFIGURED when no replicas configured."""
        event_id = uuid4()

        receipt = await stub.propagate_event(event_id)

        assert receipt.event_id == event_id
        assert receipt.replica_ids == ()
        assert receipt.status == ReplicationStatus.NOT_CONFIGURED
        assert receipt.timestamp is not None

    @pytest.mark.asyncio
    async def test_propagate_with_replicas(self) -> None:
        """Should return CONFIRMED when replicas are configured."""
        stub = EventReplicatorStub(replica_ids=["replica-1", "replica-2"])
        event_id = uuid4()

        receipt = await stub.propagate_event(event_id)

        assert receipt.event_id == event_id
        assert receipt.replica_ids == ("replica-1", "replica-2")
        assert receipt.status == ReplicationStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_propagate_forced_failure(self) -> None:
        """Should return FAILED when force_failure is True."""
        stub = EventReplicatorStub(force_failure=True)
        event_id = uuid4()

        receipt = await stub.propagate_event(event_id)

        assert receipt.event_id == event_id
        assert receipt.status == ReplicationStatus.FAILED

    @pytest.mark.asyncio
    async def test_propagate_forced_failure_with_replicas(self) -> None:
        """Should return FAILED even with replicas when force_failure is True."""
        stub = EventReplicatorStub(
            force_failure=True,
            replica_ids=["replica-1"],
        )
        event_id = uuid4()

        receipt = await stub.propagate_event(event_id)

        assert receipt.status == ReplicationStatus.FAILED
        assert receipt.replica_ids == ("replica-1",)


class TestVerifyReplicas:
    """Tests for EventReplicatorStub.verify_replicas()."""

    @pytest.mark.asyncio
    async def test_verify_no_replicas(self, stub: EventReplicatorStub) -> None:
        """Should return positive verification when no replicas configured."""
        result = await stub.verify_replicas()

        assert result.head_hash_match is True
        assert result.signature_valid is True
        assert result.schema_version_match is True
        assert result.errors == ()
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_verify_with_replicas(self) -> None:
        """Should return positive verification with configured replicas."""
        stub = EventReplicatorStub(replica_ids=["replica-1"])

        result = await stub.verify_replicas()

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_verify_forced_failure(self) -> None:
        """Should return negative verification when force_failure is True."""
        stub = EventReplicatorStub(force_failure=True)

        result = await stub.verify_replicas()

        assert result.head_hash_match is False
        assert result.signature_valid is False
        assert result.schema_version_match is False
        assert len(result.errors) > 0
        assert result.is_valid is False


class TestStubHelpers:
    """Tests for EventReplicatorStub test helper methods."""

    @pytest.mark.asyncio
    async def test_set_failure_mode(self, stub: EventReplicatorStub) -> None:
        """set_failure_mode should change failure behavior."""
        # Initially no failure
        result = await stub.verify_replicas()
        assert result.is_valid is True

        # Enable failure mode
        stub.set_failure_mode(True)
        result = await stub.verify_replicas()
        assert result.is_valid is False

        # Disable failure mode
        stub.set_failure_mode(False)
        result = await stub.verify_replicas()
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_set_replica_ids(self, stub: EventReplicatorStub) -> None:
        """set_replica_ids should change replica list."""
        event_id = uuid4()

        # Initially no replicas
        receipt = await stub.propagate_event(event_id)
        assert receipt.status == ReplicationStatus.NOT_CONFIGURED

        # Add replicas
        stub.set_replica_ids(["replica-1", "replica-2"])
        receipt = await stub.propagate_event(event_id)
        assert receipt.status == ReplicationStatus.CONFIRMED
        assert receipt.replica_ids == ("replica-1", "replica-2")

        # Clear replicas
        stub.set_replica_ids([])
        receipt = await stub.propagate_event(event_id)
        assert receipt.status == ReplicationStatus.NOT_CONFIGURED


class TestDevModeWatermark:
    """Tests for dev mode watermark."""

    def test_watermark_constant_exists(self) -> None:
        """DEV_MODE_WATERMARK constant should exist."""
        assert EventReplicatorStub.DEV_MODE_WATERMARK is not None
        assert "DEV" in EventReplicatorStub.DEV_MODE_WATERMARK
