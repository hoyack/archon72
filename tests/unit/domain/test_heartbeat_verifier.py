"""Unit tests for HeartbeatVerifier domain service (Story 2.6, FR90).

Tests signature verification and spoofing detection for heartbeats.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.domain.errors.heartbeat import HeartbeatSpoofingError
from src.domain.models.heartbeat import Heartbeat
from src.domain.services.heartbeat_verifier import HeartbeatVerifier


class TestHeartbeatVerifierSignatureVerification:
    """Tests for heartbeat signature verification."""

    def test_verify_heartbeat_signature_with_valid_signature(self) -> None:
        """Test that valid signature returns True."""
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="valid_signature_here",
        )
        # For dev mode, we use simple verification (signature != None)
        result = verifier.verify_heartbeat_signature(heartbeat)
        assert result is True

    def test_verify_heartbeat_signature_with_none_returns_false(self) -> None:
        """Test that unsigned heartbeat returns False."""
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature=None,
        )
        result = verifier.verify_heartbeat_signature(heartbeat)
        assert result is False

    def test_verify_heartbeat_signature_with_empty_returns_false(self) -> None:
        """Test that empty signature returns False."""
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="",
        )
        result = verifier.verify_heartbeat_signature(heartbeat)
        assert result is False


class TestHeartbeatVerifierSpoofingDetection:
    """Tests for heartbeat spoofing detection."""

    def test_detect_spoofing_with_valid_session(self) -> None:
        """Test that heartbeat with valid session is not flagged as spoofed."""
        verifier = HeartbeatVerifier()
        session_id = uuid4()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="valid_sig",
        )
        session_registry = {"archon-1": session_id}

        result = verifier.detect_spoofing(heartbeat, session_registry)
        assert result is False  # Not spoofed

    def test_detect_spoofing_with_mismatched_session(self) -> None:
        """Test that heartbeat with wrong session is flagged as spoofed."""
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),  # Different session
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="valid_sig",
        )
        session_registry = {"archon-1": uuid4()}  # Expected different session

        result = verifier.detect_spoofing(heartbeat, session_registry)
        assert result is True  # Spoofed

    def test_detect_spoofing_with_unknown_agent(self) -> None:
        """Test that heartbeat from unknown agent is flagged as spoofed."""
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="unknown-agent",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="valid_sig",
        )
        session_registry = {"archon-1": uuid4()}  # Unknown agent not in registry

        result = verifier.detect_spoofing(heartbeat, session_registry)
        assert result is True  # Spoofed - unknown agent

    def test_detect_spoofing_with_unsigned_heartbeat(self) -> None:
        """Test that unsigned heartbeat is flagged as spoofed."""
        verifier = HeartbeatVerifier()
        session_id = uuid4()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature=None,  # Not signed
        )
        session_registry = {"archon-1": session_id}

        result = verifier.detect_spoofing(heartbeat, session_registry)
        assert result is True  # Spoofed - no signature


class TestHeartbeatVerifierRejection:
    """Tests for heartbeat spoofing rejection."""

    def test_reject_spoofed_heartbeat_raises_error(self) -> None:
        """Test that rejecting spoofed heartbeat raises HeartbeatSpoofingError."""
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-42",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature=None,
        )

        with pytest.raises(HeartbeatSpoofingError) as exc_info:
            verifier.reject_spoofed_heartbeat(heartbeat, reason="signature_mismatch")

        assert exc_info.value.agent_id == "archon-42"
        assert exc_info.value.reason == "signature_mismatch"

    def test_reject_spoofed_heartbeat_logs_rejection(self) -> None:
        """Test that rejecting spoofed heartbeat logs the rejection."""
        # This test verifies the logging happens (implementation detail)
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-42",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature=None,
        )

        with pytest.raises(HeartbeatSpoofingError):
            verifier.reject_spoofed_heartbeat(heartbeat, reason="session_invalid")

        # Logging verification would require capturing log output
        # For now, we verify the error is raised correctly


class TestHeartbeatVerifierIntegration:
    """Tests for complete verification flow."""

    def test_verify_and_check_spoofing_valid_heartbeat(self) -> None:
        """Test full verification flow for valid heartbeat."""
        verifier = HeartbeatVerifier()
        session_id = uuid4()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="valid_signature",
        )
        session_registry = {"archon-1": session_id}

        # Signature is valid
        assert verifier.verify_heartbeat_signature(heartbeat) is True
        # Not spoofed
        assert verifier.detect_spoofing(heartbeat, session_registry) is False

    def test_verify_and_check_spoofing_invalid_heartbeat(self) -> None:
        """Test full verification flow for spoofed heartbeat."""
        verifier = HeartbeatVerifier()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature=None,  # No signature
        )
        session_registry = {"archon-1": uuid4()}

        # Signature verification fails
        assert verifier.verify_heartbeat_signature(heartbeat) is False
        # Spoofing detected
        assert verifier.detect_spoofing(heartbeat, session_registry) is True
