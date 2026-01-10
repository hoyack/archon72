"""Unit tests for HeartbeatMonitor port interface (Story 2.6, FR91).

Tests the HeartbeatMonitorPort protocol definition.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.application.ports.heartbeat_monitor import HeartbeatMonitorPort
from src.domain.models.heartbeat import Heartbeat


class TestHeartbeatMonitorProtocol:
    """Tests for HeartbeatMonitorPort protocol definition."""

    def test_protocol_defines_register_heartbeat_method(self) -> None:
        """Test that protocol defines register_heartbeat method."""
        assert hasattr(HeartbeatMonitorPort, "register_heartbeat")

    def test_protocol_defines_get_last_heartbeat_method(self) -> None:
        """Test that protocol defines get_last_heartbeat method."""
        assert hasattr(HeartbeatMonitorPort, "get_last_heartbeat")

    def test_protocol_defines_get_unresponsive_agents_method(self) -> None:
        """Test that protocol defines get_unresponsive_agents method."""
        assert hasattr(HeartbeatMonitorPort, "get_unresponsive_agents")

    def test_protocol_defines_is_agent_responsive_method(self) -> None:
        """Test that protocol defines is_agent_responsive method."""
        assert hasattr(HeartbeatMonitorPort, "is_agent_responsive")

    @pytest.mark.asyncio
    async def test_register_heartbeat_accepts_heartbeat(self) -> None:
        """Test that register_heartbeat accepts a Heartbeat object."""
        mock_monitor = AsyncMock(spec=HeartbeatMonitorPort)
        mock_monitor.register_heartbeat.return_value = None

        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
        )

        # Should not raise
        await mock_monitor.register_heartbeat(heartbeat)
        mock_monitor.register_heartbeat.assert_called_once_with(heartbeat)

    @pytest.mark.asyncio
    async def test_get_last_heartbeat_returns_heartbeat_or_none(self) -> None:
        """Test that get_last_heartbeat returns Heartbeat or None."""
        mock_monitor = AsyncMock(spec=HeartbeatMonitorPort)
        expected_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
        )
        mock_monitor.get_last_heartbeat.return_value = expected_heartbeat

        result = await mock_monitor.get_last_heartbeat("archon-1")

        assert result is not None
        assert isinstance(result, Heartbeat)
        assert result.agent_id == "archon-1"

    @pytest.mark.asyncio
    async def test_get_last_heartbeat_returns_none_for_unknown_agent(self) -> None:
        """Test that get_last_heartbeat returns None for unknown agent."""
        mock_monitor = AsyncMock(spec=HeartbeatMonitorPort)
        mock_monitor.get_last_heartbeat.return_value = None

        result = await mock_monitor.get_last_heartbeat("unknown-agent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_unresponsive_agents_returns_list(self) -> None:
        """Test that get_unresponsive_agents returns list of agent IDs."""
        mock_monitor = AsyncMock(spec=HeartbeatMonitorPort)
        mock_monitor.get_unresponsive_agents.return_value = ["archon-1", "archon-42"]

        result = await mock_monitor.get_unresponsive_agents(threshold_seconds=90)

        assert isinstance(result, list)
        assert len(result) == 2
        assert "archon-1" in result
        assert "archon-42" in result

    @pytest.mark.asyncio
    async def test_is_agent_responsive_returns_bool(self) -> None:
        """Test that is_agent_responsive returns a boolean."""
        mock_monitor = AsyncMock(spec=HeartbeatMonitorPort)
        mock_monitor.is_agent_responsive.return_value = True

        result = await mock_monitor.is_agent_responsive("archon-1")

        assert isinstance(result, bool)
        assert result is True
