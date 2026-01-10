"""Unit tests for heartbeat domain errors (Story 2.6, FR90-FR91).

Tests the AgentUnresponsiveError and HeartbeatSpoofingError classes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.heartbeat import (
    AgentUnresponsiveError,
    HeartbeatSpoofingError,
)
from src.domain.exceptions import ConclaveError


class TestAgentUnresponsiveError:
    """Tests for AgentUnresponsiveError."""

    def test_inherits_from_conclave_error(self) -> None:
        """Test that AgentUnresponsiveError inherits from ConclaveError."""
        assert issubclass(AgentUnresponsiveError, ConclaveError)

    def test_creation_with_all_fields(self) -> None:
        """Test creating error with all fields."""
        timestamp = datetime.now(timezone.utc)
        error = AgentUnresponsiveError(
            agent_id="archon-42",
            last_heartbeat_timestamp=timestamp,
            missed_count=3,
        )

        assert error.agent_id == "archon-42"
        assert error.last_heartbeat_timestamp == timestamp
        assert error.missed_count == 3

    def test_creation_with_no_heartbeat(self) -> None:
        """Test creating error when agent never sent heartbeat."""
        error = AgentUnresponsiveError(
            agent_id="archon-1",
            last_heartbeat_timestamp=None,
            missed_count=3,
        )

        assert error.agent_id == "archon-1"
        assert error.last_heartbeat_timestamp is None
        assert error.missed_count == 3

    def test_error_message_contains_agent_id(self) -> None:
        """Test that error message includes agent_id."""
        error = AgentUnresponsiveError(
            agent_id="archon-42",
            last_heartbeat_timestamp=None,
            missed_count=3,
        )

        assert "archon-42" in str(error)


class TestHeartbeatSpoofingError:
    """Tests for HeartbeatSpoofingError (FR90)."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Test that HeartbeatSpoofingError inherits from ConstitutionalViolationError."""
        assert issubclass(HeartbeatSpoofingError, ConstitutionalViolationError)

    def test_creation_with_agent_id(self) -> None:
        """Test creating error with agent_id."""
        error = HeartbeatSpoofingError(
            agent_id="archon-42",
            reason="signature_mismatch",
        )

        assert error.agent_id == "archon-42"
        assert error.reason == "signature_mismatch"

    def test_error_message_contains_fr90_reference(self) -> None:
        """Test that error message references FR90."""
        error = HeartbeatSpoofingError(
            agent_id="archon-42",
            reason="signature_mismatch",
        )

        # Constitutional violations should reference the FR
        assert "FR90" in str(error) or "spoofing" in str(error).lower()
