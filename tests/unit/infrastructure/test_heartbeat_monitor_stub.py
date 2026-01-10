"""Unit tests for HeartbeatMonitorStub infrastructure (Story 2.6, FR91).

Tests the stub implementation of HeartbeatMonitorPort.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.application.ports.heartbeat_monitor import HeartbeatMonitorPort
from src.domain.models.heartbeat import Heartbeat
from src.infrastructure.stubs.heartbeat_monitor_stub import HeartbeatMonitorStub


class TestHeartbeatMonitorStubProtocol:
    """Tests that stub implements protocol correctly."""

    def test_implements_heartbeat_monitor_port(self) -> None:
        """Test that stub implements HeartbeatMonitorPort protocol."""
        stub = HeartbeatMonitorStub()
        assert isinstance(stub, HeartbeatMonitorPort)


class TestHeartbeatMonitorStubRegistration:
    """Tests for heartbeat registration."""

    @pytest.mark.asyncio
    async def test_register_heartbeat_stores_heartbeat(self) -> None:
        """Test that register_heartbeat stores the heartbeat."""
        stub = HeartbeatMonitorStub()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="test_sig",
        )

        await stub.register_heartbeat(heartbeat)

        stored = await stub.get_last_heartbeat("archon-1")
        assert stored is not None
        assert stored.heartbeat_id == heartbeat.heartbeat_id

    @pytest.mark.asyncio
    async def test_register_heartbeat_overwrites_previous(self) -> None:
        """Test that newer heartbeat overwrites previous."""
        stub = HeartbeatMonitorStub()
        old_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=1),
            signature="old_sig",
        )
        new_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="new_sig",
        )

        await stub.register_heartbeat(old_heartbeat)
        await stub.register_heartbeat(new_heartbeat)

        stored = await stub.get_last_heartbeat("archon-1")
        assert stored is not None
        assert stored.heartbeat_id == new_heartbeat.heartbeat_id


class TestHeartbeatMonitorStubQuery:
    """Tests for heartbeat queries."""

    @pytest.mark.asyncio
    async def test_get_last_heartbeat_returns_none_for_unknown(self) -> None:
        """Test that get_last_heartbeat returns None for unknown agent."""
        stub = HeartbeatMonitorStub()

        result = await stub.get_last_heartbeat("unknown-agent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_unresponsive_agents_returns_empty_initially(self) -> None:
        """Test that get_unresponsive_agents returns empty list initially."""
        stub = HeartbeatMonitorStub()

        result = await stub.get_unresponsive_agents()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_unresponsive_agents_with_old_heartbeat(self) -> None:
        """Test that agents with old heartbeats are flagged as unresponsive."""
        stub = HeartbeatMonitorStub()
        old_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=100),  # > 90s
            signature="old_sig",
        )

        await stub.register_heartbeat(old_heartbeat)

        result = await stub.get_unresponsive_agents(threshold_seconds=90)
        assert "archon-1" in result

    @pytest.mark.asyncio
    async def test_get_unresponsive_agents_with_recent_heartbeat(self) -> None:
        """Test that agents with recent heartbeats are NOT flagged."""
        stub = HeartbeatMonitorStub()
        recent_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),  # Now
            signature="recent_sig",
        )

        await stub.register_heartbeat(recent_heartbeat)

        result = await stub.get_unresponsive_agents(threshold_seconds=90)
        assert "archon-1" not in result


class TestHeartbeatMonitorStubResponsiveness:
    """Tests for agent responsiveness checks."""

    @pytest.mark.asyncio
    async def test_is_agent_responsive_returns_false_for_unknown(self) -> None:
        """Test that unknown agents are not responsive."""
        stub = HeartbeatMonitorStub()

        result = await stub.is_agent_responsive("unknown-agent")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_agent_responsive_returns_true_for_recent(self) -> None:
        """Test that agents with recent heartbeats are responsive."""
        stub = HeartbeatMonitorStub()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="sig",
        )

        await stub.register_heartbeat(heartbeat)

        result = await stub.is_agent_responsive("archon-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_agent_responsive_returns_false_for_old(self) -> None:
        """Test that agents with old heartbeats are not responsive."""
        stub = HeartbeatMonitorStub()
        old_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=100),
            signature="sig",
        )

        await stub.register_heartbeat(old_heartbeat)

        result = await stub.is_agent_responsive("archon-1")
        assert result is False


class TestHeartbeatMonitorStubTestHelpers:
    """Tests for test helper methods."""

    def test_clear_heartbeats(self) -> None:
        """Test that clear_heartbeats resets tracking."""
        stub = HeartbeatMonitorStub()
        # Pre-populate
        stub._heartbeats["archon-1"] = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=0,
            timestamp=datetime.now(timezone.utc),
        )

        stub.clear_heartbeats()

        assert len(stub._heartbeats) == 0

    def test_get_all_heartbeats(self) -> None:
        """Test that get_all_heartbeats returns copy of stored heartbeats."""
        stub = HeartbeatMonitorStub()
        hb1 = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=0,
            timestamp=datetime.now(timezone.utc),
        )
        stub._heartbeats["archon-1"] = hb1

        result = stub.get_all_heartbeats()

        assert len(result) == 1
        assert "archon-1" in result
        # Should be a copy
        result["archon-2"] = hb1
        assert "archon-2" not in stub._heartbeats
