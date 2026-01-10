"""Unit tests for HeartbeatEmitterStub infrastructure (Story 2.6, FR90).

Tests the stub implementation of HeartbeatEmitterPort.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.application.ports.heartbeat_emitter import HeartbeatEmitterPort
from src.domain.models.heartbeat import Heartbeat
from src.infrastructure.stubs.heartbeat_emitter_stub import (
    DEV_MODE_SIGNATURE_PREFIX,
    HeartbeatEmitterStub,
)


class TestHeartbeatEmitterStubProtocol:
    """Tests that stub implements protocol correctly."""

    def test_implements_heartbeat_emitter_port(self) -> None:
        """Test that stub implements HeartbeatEmitterPort protocol."""
        stub = HeartbeatEmitterStub()
        assert isinstance(stub, HeartbeatEmitterPort)


class TestHeartbeatEmitterStubEmission:
    """Tests for heartbeat emission."""

    @pytest.mark.asyncio
    async def test_emit_heartbeat_returns_heartbeat(self) -> None:
        """Test that emit_heartbeat returns a Heartbeat object."""
        stub = HeartbeatEmitterStub()
        session_id = uuid4()

        heartbeat = await stub.emit_heartbeat(
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
        )

        assert isinstance(heartbeat, Heartbeat)
        assert heartbeat.agent_id == "archon-1"
        assert heartbeat.session_id == session_id
        assert heartbeat.status == AgentStatus.BUSY
        assert heartbeat.memory_usage_mb == 256

    @pytest.mark.asyncio
    async def test_emit_heartbeat_has_uuid(self) -> None:
        """Test that emitted heartbeat has unique UUID."""
        stub = HeartbeatEmitterStub()

        heartbeat = await stub.emit_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
        )

        assert heartbeat.heartbeat_id is not None

    @pytest.mark.asyncio
    async def test_emit_heartbeat_has_timestamp(self) -> None:
        """Test that emitted heartbeat has timestamp."""
        stub = HeartbeatEmitterStub()
        before = datetime.now(timezone.utc)

        heartbeat = await stub.emit_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
        )

        after = datetime.now(timezone.utc)
        assert heartbeat.timestamp >= before
        assert heartbeat.timestamp <= after

    @pytest.mark.asyncio
    async def test_emit_heartbeat_unsigned(self) -> None:
        """Test that emitted heartbeat has no signature."""
        stub = HeartbeatEmitterStub()

        heartbeat = await stub.emit_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
        )

        assert heartbeat.signature is None

    @pytest.mark.asyncio
    async def test_emit_heartbeat_tracks_emission(self) -> None:
        """Test that stub tracks emitted heartbeats."""
        stub = HeartbeatEmitterStub()

        await stub.emit_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
        )

        emissions = stub.get_emissions()
        assert len(emissions) == 1


class TestHeartbeatEmitterStubSigning:
    """Tests for heartbeat signing."""

    @pytest.mark.asyncio
    async def test_sign_heartbeat_adds_signature(self) -> None:
        """Test that sign_heartbeat adds a signature."""
        stub = HeartbeatEmitterStub()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
        )

        # Mock agent key (stub doesn't use real crypto)
        mock_agent_key = None

        signed = await stub.sign_heartbeat(heartbeat, mock_agent_key)

        assert signed.signature is not None
        assert len(signed.signature) > 0

    @pytest.mark.asyncio
    async def test_sign_heartbeat_includes_dev_mode_prefix(self) -> None:
        """Test that signature includes DEV MODE prefix (RT-1/ADR-4)."""
        stub = HeartbeatEmitterStub()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
        )

        signed = await stub.sign_heartbeat(heartbeat, None)

        assert signed.signature is not None
        assert signed.signature.startswith(DEV_MODE_SIGNATURE_PREFIX)

    @pytest.mark.asyncio
    async def test_sign_heartbeat_preserves_other_fields(self) -> None:
        """Test that signing preserves all other heartbeat fields."""
        stub = HeartbeatEmitterStub()
        original = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-42",
            session_id=uuid4(),
            status=AgentStatus.FAILED,
            memory_usage_mb=512,
            timestamp=datetime.now(timezone.utc),
        )

        signed = await stub.sign_heartbeat(original, None)

        assert signed.heartbeat_id == original.heartbeat_id
        assert signed.agent_id == original.agent_id
        assert signed.session_id == original.session_id
        assert signed.status == original.status
        assert signed.memory_usage_mb == original.memory_usage_mb
        assert signed.timestamp == original.timestamp


class TestHeartbeatEmitterStubTestHelpers:
    """Tests for test helper methods."""

    @pytest.mark.asyncio
    async def test_get_emissions_returns_list(self) -> None:
        """Test that get_emissions returns list of heartbeats."""
        stub = HeartbeatEmitterStub()

        await stub.emit_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
        )
        await stub.emit_heartbeat(
            agent_id="archon-2",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
        )

        emissions = stub.get_emissions()
        assert len(emissions) == 2
        assert emissions[0].agent_id == "archon-1"
        assert emissions[1].agent_id == "archon-2"

    def test_clear_emissions(self) -> None:
        """Test that clear_emissions resets tracking."""
        stub = HeartbeatEmitterStub()
        # Pre-populate (sync method for test)
        stub._emissions.append(
            Heartbeat(
                heartbeat_id=uuid4(),
                agent_id="test",
                session_id=uuid4(),
                status=AgentStatus.IDLE,
                memory_usage_mb=0,
                timestamp=datetime.now(timezone.utc),
            )
        )

        stub.clear_emissions()

        assert len(stub.get_emissions()) == 0
