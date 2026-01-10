"""Unit tests for HeartbeatService application service (Story 2.6, FR14/FR90-FR93).

Tests the application service that orchestrates heartbeat operations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.application.services.heartbeat_service import HeartbeatService
from src.domain.errors.heartbeat import HeartbeatSpoofingError
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.heartbeat import Heartbeat
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.heartbeat_emitter_stub import HeartbeatEmitterStub
from src.infrastructure.stubs.heartbeat_monitor_stub import HeartbeatMonitorStub


class TestHeartbeatServiceEmission:
    """Tests for heartbeat emission."""

    @pytest.mark.asyncio
    async def test_emit_agent_heartbeat_success(self) -> None:
        """Test successful heartbeat emission."""
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=HeartbeatMonitorStub(),
        )
        session_id = uuid4()

        result = await service.emit_agent_heartbeat(
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
        )

        assert result is not None
        assert result.agent_id == "archon-1"
        assert result.signature is not None  # Should be signed

    @pytest.mark.asyncio
    async def test_emit_agent_heartbeat_halted(self) -> None:
        """Test that emit_agent_heartbeat raises when halted."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = HeartbeatService(
            halt_checker=halt_checker,
            emitter=HeartbeatEmitterStub(),
            monitor=HeartbeatMonitorStub(),
        )

        with pytest.raises(SystemHaltedError):
            await service.emit_agent_heartbeat(
                agent_id="archon-1",
                session_id=uuid4(),
                status=AgentStatus.BUSY,
                memory_usage_mb=256,
            )

    @pytest.mark.asyncio
    async def test_emit_agent_heartbeat_registers_heartbeat(self) -> None:
        """Test that emitted heartbeat is registered with monitor."""
        monitor = HeartbeatMonitorStub()
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=monitor,
        )

        await service.emit_agent_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
        )

        last_hb = await monitor.get_last_heartbeat("archon-1")
        assert last_hb is not None
        assert last_hb.agent_id == "archon-1"


class TestHeartbeatServiceLivenessCheck:
    """Tests for agent liveness checking."""

    @pytest.mark.asyncio
    async def test_check_agent_liveness_responsive(self) -> None:
        """Test that responsive agent returns True."""
        monitor = HeartbeatMonitorStub()
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=monitor,
        )

        # Register a recent heartbeat
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="sig",
        )
        await monitor.register_heartbeat(heartbeat)

        result = await service.check_agent_liveness("archon-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_agent_liveness_unresponsive(self) -> None:
        """Test that unresponsive agent returns False."""
        monitor = HeartbeatMonitorStub()
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=monitor,
        )

        # Register an old heartbeat
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=100),
            signature="sig",
        )
        await monitor.register_heartbeat(heartbeat)

        result = await service.check_agent_liveness("archon-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_agent_liveness_unknown(self) -> None:
        """Test that unknown agent returns False."""
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=HeartbeatMonitorStub(),
        )

        result = await service.check_agent_liveness("unknown-agent")
        assert result is False


class TestHeartbeatServiceUnresponsiveDetection:
    """Tests for unresponsive agent detection."""

    @pytest.mark.asyncio
    async def test_detect_unresponsive_agents_none(self) -> None:
        """Test that no agents are unresponsive when all are recent."""
        monitor = HeartbeatMonitorStub()
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=monitor,
        )

        # Register recent heartbeats
        for i in range(3):
            heartbeat = Heartbeat(
                heartbeat_id=uuid4(),
                agent_id=f"archon-{i}",
                session_id=uuid4(),
                status=AgentStatus.BUSY,
                memory_usage_mb=256,
                timestamp=datetime.now(timezone.utc),
                signature="sig",
            )
            await monitor.register_heartbeat(heartbeat)

        result = await service.detect_unresponsive_agents()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_detect_unresponsive_agents_some(self) -> None:
        """Test that unresponsive agents are detected."""
        monitor = HeartbeatMonitorStub()
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=monitor,
        )

        # Register one recent and one old heartbeat
        recent = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="sig",
        )
        old = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-2",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=100),
            signature="sig",
        )
        await monitor.register_heartbeat(recent)
        await monitor.register_heartbeat(old)

        result = await service.detect_unresponsive_agents()
        assert len(result) == 1
        assert "archon-2" in result


class TestHeartbeatServiceVerification:
    """Tests for heartbeat verification and spoofing detection."""

    @pytest.mark.asyncio
    async def test_verify_and_register_heartbeat_valid(self) -> None:
        """Test that valid heartbeat is registered."""
        monitor = HeartbeatMonitorStub()
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=monitor,
        )
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

        await service.verify_and_register_heartbeat(heartbeat, session_registry)

        last_hb = await monitor.get_last_heartbeat("archon-1")
        assert last_hb is not None

    @pytest.mark.asyncio
    async def test_verify_and_register_heartbeat_spoofed_rejects(self) -> None:
        """Test that spoofed heartbeat is rejected."""
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=HeartbeatMonitorStub(),
        )
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),  # Wrong session
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="sig",
        )
        session_registry = {"archon-1": uuid4()}  # Different expected session

        with pytest.raises(HeartbeatSpoofingError):
            await service.verify_and_register_heartbeat(heartbeat, session_registry)

    @pytest.mark.asyncio
    async def test_verify_and_register_heartbeat_unsigned_rejects(self) -> None:
        """Test that unsigned heartbeat is rejected."""
        service = HeartbeatService(
            halt_checker=HaltCheckerStub(),
            emitter=HeartbeatEmitterStub(),
            monitor=HeartbeatMonitorStub(),
        )
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

        with pytest.raises(HeartbeatSpoofingError):
            await service.verify_and_register_heartbeat(heartbeat, session_registry)


class TestHeartbeatServiceHaltBehavior:
    """Tests for HALT FIRST rule compliance."""

    @pytest.mark.asyncio
    async def test_verify_and_register_halted(self) -> None:
        """Test that verification respects HALT state."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = HeartbeatService(
            halt_checker=halt_checker,
            emitter=HeartbeatEmitterStub(),
            monitor=HeartbeatMonitorStub(),
        )
        session_id = uuid4()
        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="sig",
        )
        session_registry = {"archon-1": session_id}

        with pytest.raises(SystemHaltedError):
            await service.verify_and_register_heartbeat(heartbeat, session_registry)
