"""Unit tests for Heartbeat domain model (Story 2.6, FR90).

Tests the Heartbeat frozen dataclass and its validation logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.domain.models.heartbeat import Heartbeat


class TestHeartbeatCreation:
    """Tests for Heartbeat model instantiation."""

    def test_heartbeat_creation_with_valid_data(self) -> None:
        """Test creating a heartbeat with all valid fields."""
        heartbeat_id = uuid4()
        agent_id = "archon-42"
        session_id = uuid4()
        status = AgentStatus.BUSY
        memory_usage_mb = 256
        timestamp = datetime.now(timezone.utc)

        heartbeat = Heartbeat(
            heartbeat_id=heartbeat_id,
            agent_id=agent_id,
            session_id=session_id,
            status=status,
            memory_usage_mb=memory_usage_mb,
            timestamp=timestamp,
        )

        assert heartbeat.heartbeat_id == heartbeat_id
        assert heartbeat.agent_id == agent_id
        assert heartbeat.session_id == session_id
        assert heartbeat.status == status
        assert heartbeat.memory_usage_mb == memory_usage_mb
        assert heartbeat.timestamp == timestamp
        assert heartbeat.signature is None

    def test_heartbeat_creation_with_signature(self) -> None:
        """Test creating a heartbeat with signature."""
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
            timestamp=datetime.now(timezone.utc),
            signature="abc123signature",
        )

        assert heartbeat.signature == "abc123signature"

    def test_heartbeat_is_frozen(self) -> None:
        """Test that Heartbeat is immutable (frozen dataclass)."""
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            heartbeat.agent_id = "archon-2"  # type: ignore[misc]


class TestHeartbeatValidation:
    """Tests for Heartbeat validation logic."""

    def test_invalid_agent_id_empty_string(self) -> None:
        """Test that empty agent_id raises ValueError."""
        with pytest.raises(ValueError, match="agent_id must be non-empty"):
            Heartbeat(
                heartbeat_id=uuid4(),
                agent_id="",
                session_id=uuid4(),
                status=AgentStatus.IDLE,
                memory_usage_mb=128,
                timestamp=datetime.now(timezone.utc),
            )

    def test_invalid_agent_id_whitespace_only(self) -> None:
        """Test that whitespace-only agent_id raises ValueError."""
        with pytest.raises(ValueError, match="agent_id must be non-empty"):
            Heartbeat(
                heartbeat_id=uuid4(),
                agent_id="   ",
                session_id=uuid4(),
                status=AgentStatus.IDLE,
                memory_usage_mb=128,
                timestamp=datetime.now(timezone.utc),
            )

    def test_invalid_memory_usage_negative(self) -> None:
        """Test that negative memory_usage_mb raises ValueError."""
        with pytest.raises(ValueError, match="memory_usage_mb must be >= 0"):
            Heartbeat(
                heartbeat_id=uuid4(),
                agent_id="archon-1",
                session_id=uuid4(),
                status=AgentStatus.IDLE,
                memory_usage_mb=-1,
                timestamp=datetime.now(timezone.utc),
            )

    def test_memory_usage_zero_is_valid(self) -> None:
        """Test that zero memory_usage_mb is valid."""
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=0,
            timestamp=datetime.now(timezone.utc),
        )

        assert heartbeat.memory_usage_mb == 0


class TestHeartbeatEquality:
    """Tests for Heartbeat equality and hashing."""

    def test_heartbeats_with_same_id_are_equal(self) -> None:
        """Test that heartbeats with same heartbeat_id are equal."""
        heartbeat_id = uuid4()
        session_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        heartbeat1 = Heartbeat(
            heartbeat_id=heartbeat_id,
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
            timestamp=timestamp,
        )

        heartbeat2 = Heartbeat(
            heartbeat_id=heartbeat_id,
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
            timestamp=timestamp,
        )

        assert heartbeat1 == heartbeat2

    def test_heartbeat_hashable(self) -> None:
        """Test that Heartbeat is hashable (can be used in sets)."""
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
            timestamp=datetime.now(timezone.utc),
        )

        # Should not raise - heartbeat should be hashable
        heartbeat_set = {heartbeat}
        assert heartbeat in heartbeat_set
