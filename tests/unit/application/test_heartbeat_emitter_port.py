"""Unit tests for HeartbeatEmitter port interface (Story 2.6, FR90).

Tests the HeartbeatEmitterPort protocol definition and constants.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.application.ports.heartbeat_emitter import (
    HEARTBEAT_INTERVAL_SECONDS,
    MISSED_HEARTBEAT_THRESHOLD,
    UNRESPONSIVE_TIMEOUT_SECONDS,
    HeartbeatEmitterPort,
)
from src.domain.models.heartbeat import Heartbeat

if TYPE_CHECKING:
    pass


class TestHeartbeatEmitterConstants:
    """Tests for HeartbeatEmitter constants."""

    def test_heartbeat_interval_is_30_seconds(self) -> None:
        """Test that heartbeat interval is 30 seconds per story spec."""
        assert HEARTBEAT_INTERVAL_SECONDS == 30

    def test_missed_heartbeat_threshold_is_3(self) -> None:
        """Test that missed heartbeat threshold is 3 per story spec."""
        assert MISSED_HEARTBEAT_THRESHOLD == 3

    def test_unresponsive_timeout_is_90_seconds(self) -> None:
        """Test that unresponsive timeout is 90 seconds (3 * 30s)."""
        assert UNRESPONSIVE_TIMEOUT_SECONDS == 90


class TestHeartbeatEmitterProtocol:
    """Tests for HeartbeatEmitterPort protocol definition."""

    def test_protocol_defines_emit_heartbeat_method(self) -> None:
        """Test that protocol defines emit_heartbeat method."""
        assert hasattr(HeartbeatEmitterPort, "emit_heartbeat")

    def test_protocol_defines_sign_heartbeat_method(self) -> None:
        """Test that protocol defines sign_heartbeat method."""
        assert hasattr(HeartbeatEmitterPort, "sign_heartbeat")

    @pytest.mark.asyncio
    async def test_emit_heartbeat_returns_heartbeat(self) -> None:
        """Test that emit_heartbeat returns a Heartbeat object."""
        # Create a mock emitter
        mock_emitter = AsyncMock(spec=HeartbeatEmitterPort)
        expected_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
        )
        mock_emitter.emit_heartbeat.return_value = expected_heartbeat

        result = await mock_emitter.emit_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
        )

        assert isinstance(result, Heartbeat)
        assert result.agent_id == "archon-1"

    @pytest.mark.asyncio
    async def test_sign_heartbeat_returns_heartbeat_with_signature(self) -> None:
        """Test that sign_heartbeat returns a Heartbeat with signature."""
        mock_emitter = AsyncMock(spec=HeartbeatEmitterPort)
        unsigned_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
        )
        signed_heartbeat = Heartbeat(
            heartbeat_id=unsigned_heartbeat.heartbeat_id,
            agent_id=unsigned_heartbeat.agent_id,
            session_id=unsigned_heartbeat.session_id,
            status=unsigned_heartbeat.status,
            memory_usage_mb=unsigned_heartbeat.memory_usage_mb,
            timestamp=unsigned_heartbeat.timestamp,
            signature="test_signature_123",
        )
        mock_emitter.sign_heartbeat.return_value = signed_heartbeat

        # Mock agent key (using None since we just test the interface)
        mock_agent_key = AsyncMock()

        result = await mock_emitter.sign_heartbeat(
            heartbeat=unsigned_heartbeat,
            agent_key=mock_agent_key,
        )

        assert isinstance(result, Heartbeat)
        assert result.signature is not None
        assert result.signature == "test_signature_123"
