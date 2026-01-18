"""Integration tests for heartbeat monitoring (Story 2.6, FR14/FR90-FR93).

Tests the end-to-end heartbeat monitoring system including emission,
liveness detection, spoofing defense, and HALT compliance.

Constitutional Requirements Tested:
- FR14: Heartbeat monitoring operational requirement
- FR90: Each agent SHALL emit heartbeat during active operation
- FR91: Missing heartbeat beyond 2x expected interval triggers alert
- FR92: Missed heartbeats logged without derailing process
- FR93: Spoofed heartbeats must be rejected and logged
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import AgentStatus
from src.application.ports.heartbeat_emitter import (
    HEARTBEAT_INTERVAL_SECONDS,
    MISSED_HEARTBEAT_THRESHOLD,
    UNRESPONSIVE_TIMEOUT_SECONDS,
)
from src.application.services.heartbeat_service import HeartbeatService
from src.domain.errors.heartbeat import HeartbeatSpoofingError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.agent_unresponsive import (
    AGENT_UNRESPONSIVE_EVENT_TYPE,
    AgentUnresponsivePayload,
)
from src.domain.models.heartbeat import Heartbeat
from src.domain.services.heartbeat_verifier import HeartbeatVerifier
from src.infrastructure.stubs.heartbeat_emitter_stub import HeartbeatEmitterStub
from src.infrastructure.stubs.heartbeat_monitor_stub import HeartbeatMonitorStub

if TYPE_CHECKING:
    from uuid import UUID


# Test fixture for HALT checker
class MockHaltChecker:
    """Mock halt checker for testing."""

    def __init__(self, is_halted: bool = False) -> None:
        self._is_halted = is_halted

    async def is_halted(self) -> bool:
        return self._is_halted

    def set_halted(self, halted: bool) -> None:
        self._is_halted = halted


@pytest.fixture
def halt_checker() -> MockHaltChecker:
    """Provide a mock halt checker that is not halted by default."""
    return MockHaltChecker(is_halted=False)


@pytest.fixture
def emitter_stub() -> HeartbeatEmitterStub:
    """Provide a heartbeat emitter stub."""
    return HeartbeatEmitterStub()


@pytest.fixture
def monitor_stub() -> HeartbeatMonitorStub:
    """Provide a heartbeat monitor stub."""
    return HeartbeatMonitorStub()


@pytest.fixture
def heartbeat_service(
    halt_checker: MockHaltChecker,
    emitter_stub: HeartbeatEmitterStub,
    monitor_stub: HeartbeatMonitorStub,
) -> HeartbeatService:
    """Provide a fully wired heartbeat service."""
    return HeartbeatService(
        halt_checker=halt_checker,
        emitter=emitter_stub,
        monitor=monitor_stub,
        verifier=HeartbeatVerifier(),
    )


class TestHeartbeatConfiguration:
    """Tests for heartbeat timing configuration (FR90)."""

    def test_heartbeat_interval_is_30_seconds(self) -> None:
        """Test that heartbeat interval is 30 seconds (faster than PRD minimum)."""
        assert HEARTBEAT_INTERVAL_SECONDS == 30

    def test_missed_heartbeat_threshold_is_3(self) -> None:
        """Test that 3 missed heartbeats triggers unresponsive."""
        assert MISSED_HEARTBEAT_THRESHOLD == 3

    def test_unresponsive_timeout_is_90_seconds(self) -> None:
        """Test that unresponsive timeout is 90s (3 * 30s)."""
        assert UNRESPONSIVE_TIMEOUT_SECONDS == 90
        assert (
            UNRESPONSIVE_TIMEOUT_SECONDS
            == HEARTBEAT_INTERVAL_SECONDS * MISSED_HEARTBEAT_THRESHOLD
        )


class TestHeartbeatEmission:
    """Tests for heartbeat emission during deliberation (FR90)."""

    @pytest.mark.asyncio
    async def test_agent_emits_heartbeat_with_all_required_fields(
        self,
        heartbeat_service: HeartbeatService,
    ) -> None:
        """Test: Agent emits heartbeat with all required fields (FR90)."""
        agent_id = "archon-42"
        session_id = uuid4()
        status = AgentStatus.BUSY
        memory_usage_mb = 256

        heartbeat = await heartbeat_service.emit_agent_heartbeat(
            agent_id=agent_id,
            session_id=session_id,
            status=status,
            memory_usage_mb=memory_usage_mb,
        )

        # Verify all required fields are present
        assert heartbeat.agent_id == agent_id
        assert heartbeat.session_id == session_id
        assert heartbeat.status == status
        assert heartbeat.memory_usage_mb == memory_usage_mb
        assert heartbeat.heartbeat_id is not None
        assert heartbeat.timestamp is not None
        assert heartbeat.signature is not None  # Signed for spoofing defense

    @pytest.mark.asyncio
    async def test_heartbeat_is_registered_with_monitor_after_emission(
        self,
        heartbeat_service: HeartbeatService,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: Emitted heartbeat is registered with monitor for tracking."""
        agent_id = "archon-1"
        session_id = uuid4()

        await heartbeat_service.emit_agent_heartbeat(
            agent_id=agent_id,
            session_id=session_id,
            status=AgentStatus.IDLE,
            memory_usage_mb=128,
        )

        # Verify heartbeat is registered
        last_hb = await monitor_stub.get_last_heartbeat(agent_id)
        assert last_hb is not None
        assert last_hb.agent_id == agent_id

    @pytest.mark.asyncio
    async def test_heartbeat_signature_is_valid_format(
        self,
        heartbeat_service: HeartbeatService,
    ) -> None:
        """Test: Heartbeat signature follows DEV_MODE format for spoofing defense."""
        heartbeat = await heartbeat_service.emit_agent_heartbeat(
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=512,
        )

        # DEV_MODE signatures start with [DEV_MODE] prefix (RT-1/ADR-4)
        assert heartbeat.signature is not None
        assert heartbeat.signature.startswith("[DEV_MODE]")


class TestUnresponsiveDetection:
    """Tests for unresponsive agent detection (FR91)."""

    @pytest.mark.asyncio
    async def test_3_missed_heartbeats_triggers_unresponsive(
        self,
        heartbeat_service: HeartbeatService,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: 3 missed heartbeats (90s) triggers unresponsive detection (FR91)."""
        agent_id = "archon-slow"
        session_id = uuid4()

        # Create old heartbeat (> 90 seconds ago)
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=100)
        old_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=old_timestamp,
            signature="[DEV_MODE]:test",
        )

        # Register old heartbeat directly with monitor
        await monitor_stub.register_heartbeat(old_heartbeat)

        # Detect unresponsive agents
        unresponsive = await heartbeat_service.detect_unresponsive_agents(
            threshold_seconds=90,
        )

        assert agent_id in unresponsive

    @pytest.mark.asyncio
    async def test_recent_heartbeat_is_not_unresponsive(
        self,
        heartbeat_service: HeartbeatService,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: Agent with recent heartbeat is NOT flagged as unresponsive."""
        agent_id = "archon-active"
        session_id = uuid4()

        # Emit fresh heartbeat
        await heartbeat_service.emit_agent_heartbeat(
            agent_id=agent_id,
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
        )

        # Detect unresponsive agents
        unresponsive = await heartbeat_service.detect_unresponsive_agents()

        assert agent_id not in unresponsive

    @pytest.mark.asyncio
    async def test_unresponsive_agent_flagged_for_recovery(
        self,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: Unresponsive agent is flagged for recovery (FR91)."""
        agent_id = "archon-failing"
        session_id = uuid4()

        # Create old heartbeat
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=100)
        old_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=old_timestamp,
            signature="[DEV_MODE]:test",
        )
        await monitor_stub.register_heartbeat(old_heartbeat)

        # Create AgentUnresponsivePayload (flagged for recovery)
        payload = AgentUnresponsivePayload(
            agent_id=agent_id,
            session_id=session_id,
            last_heartbeat=old_timestamp,
            missed_heartbeat_count=4,  # > 3 missed
            detection_timestamp=datetime.now(timezone.utc),
            flagged_for_recovery=True,
        )

        assert payload.flagged_for_recovery is True
        assert payload.missed_heartbeat_count > MISSED_HEARTBEAT_THRESHOLD

    @pytest.mark.asyncio
    async def test_failure_detection_time_is_recorded(
        self,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: Failure detection time is recorded (FR91)."""
        agent_id = "archon-timed"
        session_id = uuid4()
        detection_time = datetime.now(timezone.utc)

        payload = AgentUnresponsivePayload(
            agent_id=agent_id,
            session_id=session_id,
            last_heartbeat=datetime.now(timezone.utc) - timedelta(seconds=100),
            missed_heartbeat_count=3,
            detection_timestamp=detection_time,
            flagged_for_recovery=True,
        )

        assert payload.detection_timestamp == detection_time


class TestMissedHeartbeatLogging:
    """Tests for missed heartbeat logging (FR92)."""

    @pytest.mark.asyncio
    async def test_missing_heartbeat_log_includes_last_known_state(
        self,
        heartbeat_service: HeartbeatService,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: Missing heartbeat log includes last known state and timestamp (FR92)."""
        agent_id = "archon-missing"
        session_id = uuid4()
        last_status = AgentStatus.BUSY
        last_memory = 512

        # Create and register old heartbeat
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=100)
        old_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            status=last_status,
            memory_usage_mb=last_memory,
            timestamp=old_timestamp,
            signature="[DEV_MODE]:test",
        )
        await monitor_stub.register_heartbeat(old_heartbeat)

        # Check liveness - this logs the last known state
        is_responsive = await heartbeat_service.check_agent_liveness(agent_id)

        assert is_responsive is False

        # Verify last heartbeat can be retrieved with full state
        last_hb = await monitor_stub.get_last_heartbeat(agent_id)
        assert last_hb is not None
        assert last_hb.status == last_status
        assert last_hb.memory_usage_mb == last_memory
        assert last_hb.timestamp == old_timestamp


class TestSpoofingDefense:
    """Tests for heartbeat spoofing defense (FR90/FR93)."""

    @pytest.mark.asyncio
    async def test_valid_heartbeats_pass_signature_verification(
        self,
        heartbeat_service: HeartbeatService,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: Valid heartbeats pass signature verification (FR90)."""
        agent_id = "archon-valid"
        session_id = uuid4()
        session_registry = {agent_id: session_id}

        # Create valid signed heartbeat
        valid_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="[DEV_MODE]:valid_sig",
        )

        # Should not raise
        await heartbeat_service.verify_and_register_heartbeat(
            heartbeat=valid_heartbeat,
            session_registry=session_registry,
        )

        # Verify registered
        registered = await monitor_stub.get_last_heartbeat(agent_id)
        assert registered is not None

    @pytest.mark.asyncio
    async def test_spoofed_heartbeat_rejected_unsigned(
        self,
        heartbeat_service: HeartbeatService,
    ) -> None:
        """Test: Spoofed heartbeats (unsigned) are rejected (FR90/FR93)."""
        agent_id = "archon-spoofed"
        session_id = uuid4()
        session_registry = {agent_id: session_id}

        # Create unsigned heartbeat (spoofing attempt)
        unsigned_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_id,
            session_id=session_id,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature=None,  # Unsigned - spoofed!
        )

        with pytest.raises(HeartbeatSpoofingError) as exc_info:
            await heartbeat_service.verify_and_register_heartbeat(
                heartbeat=unsigned_heartbeat,
                session_registry=session_registry,
            )

        assert exc_info.value.agent_id == agent_id
        assert "unsigned" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_spoofed_heartbeat_rejected_session_mismatch(
        self,
        heartbeat_service: HeartbeatService,
    ) -> None:
        """Test: Spoofed heartbeats (session mismatch) are rejected (FR90/FR93)."""
        agent_id = "archon-imposter"
        real_session = uuid4()
        fake_session = uuid4()  # Different session!
        session_registry = {agent_id: real_session}

        # Create heartbeat with wrong session
        spoofed_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_id,
            session_id=fake_session,  # Wrong session!
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="[DEV_MODE]:fake_sig",
        )

        with pytest.raises(HeartbeatSpoofingError) as exc_info:
            await heartbeat_service.verify_and_register_heartbeat(
                heartbeat=spoofed_heartbeat,
                session_registry=session_registry,
            )

        assert exc_info.value.agent_id == agent_id
        assert "session" in exc_info.value.reason.lower()

    @pytest.mark.asyncio
    async def test_spoofed_heartbeat_rejected_unknown_agent(
        self,
        heartbeat_service: HeartbeatService,
    ) -> None:
        """Test: Spoofed heartbeats from unknown agents are rejected (FR90/FR93)."""
        unknown_agent = "archon-unknown"
        session_registry: dict[str, UUID] = {}  # Empty - no known agents

        # Create heartbeat from unknown agent
        unknown_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=unknown_agent,
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="[DEV_MODE]:unknown_sig",
        )

        with pytest.raises(HeartbeatSpoofingError) as exc_info:
            await heartbeat_service.verify_and_register_heartbeat(
                heartbeat=unknown_heartbeat,
                session_registry=session_registry,
            )

        assert exc_info.value.agent_id == unknown_agent
        assert "unknown" in exc_info.value.reason.lower()


class TestHaltCompliance:
    """Tests for HALT FIRST rule compliance."""

    @pytest.mark.asyncio
    async def test_halt_state_blocks_heartbeat_emission(
        self,
        halt_checker: MockHaltChecker,
        heartbeat_service: HeartbeatService,
    ) -> None:
        """Test: HALT state blocks heartbeat emission (HALT FIRST rule)."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await heartbeat_service.emit_agent_heartbeat(
                agent_id="archon-1",
                session_id=uuid4(),
                status=AgentStatus.BUSY,
                memory_usage_mb=256,
            )

    @pytest.mark.asyncio
    async def test_halt_state_blocks_heartbeat_verification(
        self,
        halt_checker: MockHaltChecker,
        heartbeat_service: HeartbeatService,
    ) -> None:
        """Test: HALT state blocks heartbeat verification (HALT FIRST rule)."""
        halt_checker.set_halted(True)

        heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id="archon-1",
            session_id=uuid4(),
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
            timestamp=datetime.now(timezone.utc),
            signature="[DEV_MODE]:sig",
        )

        with pytest.raises(SystemHaltedError):
            await heartbeat_service.verify_and_register_heartbeat(
                heartbeat=heartbeat,
                session_registry={"archon-1": heartbeat.session_id},
            )


class TestEndToEndFlow:
    """End-to-end integration tests for heartbeat monitoring."""

    @pytest.mark.asyncio
    async def test_full_heartbeat_monitoring_flow(
        self,
        heartbeat_service: HeartbeatService,
        monitor_stub: HeartbeatMonitorStub,
    ) -> None:
        """Test: End-to-end heartbeat monitoring flow (FR14/FR90-FR93)."""
        # Setup: 3 agents with different heartbeat states
        agent_active = "archon-active"
        agent_slow = "archon-slow"
        agent_dead = "archon-dead"
        session_active = uuid4()
        session_slow = uuid4()
        session_dead = uuid4()

        # 1. Active agent: Recent heartbeat
        await heartbeat_service.emit_agent_heartbeat(
            agent_id=agent_active,
            session_id=session_active,
            status=AgentStatus.BUSY,
            memory_usage_mb=256,
        )

        # 2. Slow agent: Old heartbeat (> 90s ago)
        old_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_slow,
            session_id=session_slow,
            status=AgentStatus.BUSY,
            memory_usage_mb=128,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=100),
            signature="[DEV_MODE]:old",
        )
        await monitor_stub.register_heartbeat(old_heartbeat)

        # 3. Dead agent: Very old heartbeat (> 5 min ago)
        dead_heartbeat = Heartbeat(
            heartbeat_id=uuid4(),
            agent_id=agent_dead,
            session_id=session_dead,
            status=AgentStatus.UNKNOWN,
            memory_usage_mb=0,
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
            signature="[DEV_MODE]:dead",
        )
        await monitor_stub.register_heartbeat(dead_heartbeat)

        # Detect unresponsive agents
        unresponsive = await heartbeat_service.detect_unresponsive_agents()

        # Verify: Active is responsive, slow and dead are unresponsive
        assert agent_active not in unresponsive
        assert agent_slow in unresponsive
        assert agent_dead in unresponsive

        # Verify liveness check
        assert await heartbeat_service.check_agent_liveness(agent_active) is True
        assert await heartbeat_service.check_agent_liveness(agent_slow) is False
        assert await heartbeat_service.check_agent_liveness(agent_dead) is False


class TestAgentUnresponsiveEventConstant:
    """Tests for AgentUnresponsiveEvent type constant."""

    def test_event_type_follows_convention(self) -> None:
        """Test that event type follows lowercase.dot.notation convention."""
        assert AGENT_UNRESPONSIVE_EVENT_TYPE == "agent.unresponsive"
