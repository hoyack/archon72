"""Unit tests for AgentUnresponsiveEvent domain event (Story 2.6, FR91).

Tests the AgentUnresponsiveEvent payload for representing agent liveness
failures detected by the heartbeat monitoring system.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.agent_unresponsive import (
    AGENT_UNRESPONSIVE_EVENT_TYPE,
    AgentUnresponsivePayload,
)


class TestAgentUnresponsiveEventType:
    """Tests for event type constant."""

    def test_event_type_constant_follows_convention(self) -> None:
        """Test that event type follows lowercase.dot.notation convention."""
        assert AGENT_UNRESPONSIVE_EVENT_TYPE == "agent.unresponsive"


class TestAgentUnresponsivePayloadCreation:
    """Tests for AgentUnresponsivePayload creation."""

    def test_create_payload_with_all_fields(self) -> None:
        """Test creating payload with all required fields."""
        agent_id = "archon-1"
        session_id = uuid4()
        last_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=2)
        missed_count = 3
        detection_timestamp = datetime.now(timezone.utc)
        flagged_for_recovery = True

        payload = AgentUnresponsivePayload(
            agent_id=agent_id,
            session_id=session_id,
            last_heartbeat=last_heartbeat,
            missed_heartbeat_count=missed_count,
            detection_timestamp=detection_timestamp,
            flagged_for_recovery=flagged_for_recovery,
        )

        assert payload.agent_id == agent_id
        assert payload.session_id == session_id
        assert payload.last_heartbeat == last_heartbeat
        assert payload.missed_heartbeat_count == missed_count
        assert payload.detection_timestamp == detection_timestamp
        assert payload.flagged_for_recovery is True

    def test_create_payload_with_no_last_heartbeat(self) -> None:
        """Test creating payload when agent never sent a heartbeat."""
        payload = AgentUnresponsivePayload(
            agent_id="archon-1",
            session_id=uuid4(),
            last_heartbeat=None,  # Never received a heartbeat
            missed_heartbeat_count=0,
            detection_timestamp=datetime.now(timezone.utc),
            flagged_for_recovery=False,
        )

        assert payload.last_heartbeat is None
        assert payload.missed_heartbeat_count == 0

    def test_payload_is_frozen(self) -> None:
        """Test that payload is immutable (frozen)."""
        payload = AgentUnresponsivePayload(
            agent_id="archon-1",
            session_id=uuid4(),
            last_heartbeat=datetime.now(timezone.utc),
            missed_heartbeat_count=3,
            detection_timestamp=datetime.now(timezone.utc),
            flagged_for_recovery=True,
        )

        with pytest.raises(AttributeError):
            payload.agent_id = "archon-2"  # type: ignore[misc]


class TestAgentUnresponsivePayloadValidation:
    """Tests for AgentUnresponsivePayload validation."""

    def test_validation_rejects_empty_agent_id(self) -> None:
        """Test that empty agent_id is rejected."""
        with pytest.raises(ValueError, match="agent_id must be non-empty"):
            AgentUnresponsivePayload(
                agent_id="",
                session_id=uuid4(),
                last_heartbeat=datetime.now(timezone.utc),
                missed_heartbeat_count=3,
                detection_timestamp=datetime.now(timezone.utc),
                flagged_for_recovery=False,
            )

    def test_validation_rejects_negative_missed_count(self) -> None:
        """Test that negative missed_heartbeat_count is rejected."""
        with pytest.raises(ValueError, match="missed_heartbeat_count must be non-negative"):
            AgentUnresponsivePayload(
                agent_id="archon-1",
                session_id=uuid4(),
                last_heartbeat=datetime.now(timezone.utc),
                missed_heartbeat_count=-1,
                detection_timestamp=datetime.now(timezone.utc),
                flagged_for_recovery=False,
            )

    def test_validation_rejects_invalid_session_id_type(self) -> None:
        """Test that non-UUID session_id is rejected."""
        with pytest.raises(TypeError, match="session_id must be UUID"):
            AgentUnresponsivePayload(
                agent_id="archon-1",
                session_id="not-a-uuid",  # type: ignore[arg-type]
                last_heartbeat=datetime.now(timezone.utc),
                missed_heartbeat_count=3,
                detection_timestamp=datetime.now(timezone.utc),
                flagged_for_recovery=False,
            )


class TestAgentUnresponsivePayloadSerialization:
    """Tests for payload serialization."""

    def test_to_dict_with_all_fields(self) -> None:
        """Test serialization to dictionary with all fields."""
        session_id = uuid4()
        last_heartbeat = datetime.now(timezone.utc)
        detection_timestamp = datetime.now(timezone.utc)

        payload = AgentUnresponsivePayload(
            agent_id="archon-1",
            session_id=session_id,
            last_heartbeat=last_heartbeat,
            missed_heartbeat_count=3,
            detection_timestamp=detection_timestamp,
            flagged_for_recovery=True,
        )

        result = payload.to_dict()

        assert result["agent_id"] == "archon-1"
        assert result["session_id"] == str(session_id)
        assert result["last_heartbeat"] == last_heartbeat.isoformat()
        assert result["missed_heartbeat_count"] == 3
        assert result["detection_timestamp"] == detection_timestamp.isoformat()
        assert result["flagged_for_recovery"] is True

    def test_to_dict_with_none_last_heartbeat(self) -> None:
        """Test serialization when last_heartbeat is None."""
        payload = AgentUnresponsivePayload(
            agent_id="archon-1",
            session_id=uuid4(),
            last_heartbeat=None,
            missed_heartbeat_count=0,
            detection_timestamp=datetime.now(timezone.utc),
            flagged_for_recovery=False,
        )

        result = payload.to_dict()

        assert result["last_heartbeat"] is None
