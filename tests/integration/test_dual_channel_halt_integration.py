"""Integration tests for Dual-Channel Halt Transport (Story 3.3, Task 9).

Tests the full integration of:
- HaltTriggerService → DualChannelHaltTransport → HaltCheckerStub

Constitutional Constraints:
- AC1: write_halt() writes to BOTH channels (Redis + DB)
- AC2: is_halted() returns True if EITHER channel indicates halt
- AC3: Falls back to DB if Redis fails
- AC4: Detects and logs channel conflicts

ADR-3: Partition Behavior + Halt Durability
- Dual-channel halt: Redis Streams for speed + DB halt flag for safety
- If EITHER channel indicates halt -> component halts
- DB is canonical when channels disagree
- 5-second Redis-to-DB confirmation (RT-2)

Test Strategy:
- Use DualChannelHaltTransportStub for controlled testing
- Test full flow from trigger to halt check
- Verify conflict detection and resolution
"""

import asyncio
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.dual_channel_halt import CONFIRMATION_TIMEOUT_SECONDS
from src.application.services.halt_trigger_service import HaltTriggerService
from src.domain.events.constitutional_crisis import CrisisType
from src.domain.events.fork_detected import ForkDetectedPayload
from src.infrastructure.stubs.dual_channel_halt_stub import (
    DualChannelHaltTransportStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


class TestFullHaltFlow:
    """Test full halt flow: trigger → dual-channel write → check."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create DualChannelHaltTransportStub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def halt_trigger_service(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> HaltTriggerService:
        """Create HaltTriggerService with dual-channel transport."""
        return HaltTriggerService(
            dual_channel_halt=dual_channel_stub,
            service_id="integration-test",
        )

    @pytest.fixture
    def halt_checker(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> HaltCheckerStub:
        """Create HaltCheckerStub with dual-channel transport."""
        return HaltCheckerStub(dual_channel_halt=dual_channel_stub)

    @pytest.fixture
    def fork_payload(self) -> ForkDetectedPayload:
        """Create sample fork payload."""
        return ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="abc123" * 10,
            content_hashes=("hash1", "hash2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-integration",
        )

    @pytest.mark.asyncio
    async def test_fork_triggers_halt_via_dual_channel(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test AC1: Fork detection triggers halt via dual-channel transport."""
        # Initially not halted
        assert await halt_checker.is_halted() is False

        # Trigger halt via fork detection
        await halt_trigger_service.on_fork_detected(fork_payload)

        # Verify halt is detected
        assert await halt_checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_halt_reason_includes_fr17(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test halt reason includes FR17 constitutional constraint."""
        await halt_trigger_service.on_fork_detected(fork_payload)

        reason = await halt_checker.get_halt_reason()
        assert reason is not None
        assert "FR17" in reason

    @pytest.mark.asyncio
    async def test_halt_completes_quickly(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test halt operation completes well under timeout."""
        start_time = time.monotonic()

        await halt_trigger_service.on_fork_detected(fork_payload)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Should complete in much less than 100ms (stub is instant)
        assert elapsed_ms < 100, f"Halt took {elapsed_ms}ms"
        assert await halt_checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_direct_crisis_trigger_via_dual_channel(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test direct crisis trigger uses dual-channel transport."""
        crisis_id = await halt_trigger_service.trigger_halt_for_crisis(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_details="Direct crisis trigger test",
        )

        assert await halt_checker.is_halted() is True
        assert halt_trigger_service.crisis_event_id == crisis_id


class TestEitherChannelHalt:
    """Test AC2: is_halted() returns True if EITHER channel indicates halt."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create DualChannelHaltTransportStub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def halt_checker(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> HaltCheckerStub:
        """Create HaltCheckerStub with dual-channel transport."""
        return HaltCheckerStub(dual_channel_halt=dual_channel_stub)

    @pytest.mark.asyncio
    async def test_halted_when_only_db_halted(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test AC2: Halt detected when only DB channel halted."""
        dual_channel_stub.set_db_halted(True, "DB halt only")
        dual_channel_stub.set_redis_halted(False)

        assert await halt_checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_halted_when_only_redis_halted(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test AC2: Halt detected when only Redis channel halted."""
        dual_channel_stub.set_db_halted(False, None)
        dual_channel_stub.set_redis_halted(True)

        assert await halt_checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_halted_when_both_halted(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test AC2: Halt detected when both channels halted."""
        await dual_channel_stub.write_halt("Both channels", uuid4())

        assert await halt_checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_not_halted_when_neither_halted(
        self,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test not halted when neither channel halted."""
        assert await halt_checker.is_halted() is False


class TestRedisFallback:
    """Test AC3: Falls back to DB if Redis fails."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create DualChannelHaltTransportStub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def halt_checker(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> HaltCheckerStub:
        """Create HaltCheckerStub with dual-channel transport."""
        return HaltCheckerStub(dual_channel_halt=dual_channel_stub)

    @pytest.mark.asyncio
    async def test_uses_db_when_redis_fails(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test AC3: Uses DB (canonical) when Redis fails."""
        # Simulate Redis failure
        dual_channel_stub.set_redis_failure(True)

        # DB is halted
        dual_channel_stub.set_db_halted(True, "DB is canonical")

        # Should still detect halt via DB
        assert await halt_checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_uses_db_reason_when_redis_fails(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test AC3: Uses DB reason (canonical) when Redis fails."""
        dual_channel_stub.set_redis_failure(True)
        dual_channel_stub.set_db_halted(True, "FR17: DB canonical reason")

        reason = await halt_checker.get_halt_reason()
        assert reason == "FR17: DB canonical reason"


class TestChannelConflict:
    """Test AC4: Detects and handles channel conflicts."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create DualChannelHaltTransportStub."""
        return DualChannelHaltTransportStub()

    @pytest.mark.asyncio
    async def test_detects_redis_halted_db_not(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Test AC4: Detects conflict when Redis halted but DB not."""
        dual_channel_stub.set_redis_halted(True)
        dual_channel_stub.set_db_halted(False, None)

        # Channels are inconsistent
        assert await dual_channel_stub.check_channels_consistent() is False

    @pytest.mark.asyncio
    async def test_detects_db_halted_redis_not(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Test AC4: Detects conflict when DB halted but Redis not."""
        dual_channel_stub.set_db_halted(True, "DB halt")
        dual_channel_stub.set_redis_halted(False)

        # Channels are inconsistent
        assert await dual_channel_stub.check_channels_consistent() is False

    @pytest.mark.asyncio
    async def test_consistent_when_both_match(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Test AC4: Channels consistent when both match."""
        # Both not halted
        assert await dual_channel_stub.check_channels_consistent() is True

        # Both halted
        await dual_channel_stub.write_halt("Both", uuid4())
        assert await dual_channel_stub.check_channels_consistent() is True

    @pytest.mark.asyncio
    async def test_resolve_conflict_propagates_db_to_redis(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Test AC4: Conflict resolution propagates DB halt to Redis."""
        dual_channel_stub.set_db_halted(True, "DB halt", uuid4())
        dual_channel_stub.set_redis_halted(False)

        # Resolve conflict
        await dual_channel_stub.resolve_conflict()

        # Now consistent
        assert await dual_channel_stub.check_channels_consistent() is True

    @pytest.mark.asyncio
    async def test_phantom_halt_not_cleared(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> None:
        """Test AC4: Phantom halt (Redis but not DB) not cleared for security."""
        dual_channel_stub.set_redis_halted(True)
        dual_channel_stub.set_db_halted(False, None)

        # Resolve conflict
        await dual_channel_stub.resolve_conflict()

        # Redis still halted (security measure)
        assert dual_channel_stub._redis_halted is True


class TestConfirmationTimeout:
    """Test RT-2: 5-second Redis-to-DB confirmation timeout."""

    def test_confirmation_timeout_is_5_seconds(self) -> None:
        """Test RT-2: Confirmation timeout is 5 seconds."""
        assert CONFIRMATION_TIMEOUT_SECONDS == 5.0

    def test_dual_channel_stub_returns_correct_timeout(self) -> None:
        """Test stub returns correct timeout constant."""
        stub = DualChannelHaltTransportStub()
        assert stub.confirmation_timeout_seconds == 5.0


class TestEndToEndFlow:
    """End-to-end integration tests for complete halt flow."""

    @pytest.mark.asyncio
    async def test_complete_fork_to_halt_check_flow(self) -> None:
        """Test complete flow: Fork detected → Halt triggered → Halt checked."""
        # Setup
        dual_channel = DualChannelHaltTransportStub()
        halt_trigger_service = HaltTriggerService(
            dual_channel_halt=dual_channel,
            service_id="e2e-test-service",
        )
        halt_checker = HaltCheckerStub(dual_channel_halt=dual_channel)

        # Verify initial state
        assert await halt_checker.is_halted() is False
        assert dual_channel.get_trigger_count() == 0

        # Simulate fork detection
        fork_payload = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="e2e_test_hash" * 5,
            content_hashes=("h1", "h2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="e2e-fork-monitor",
        )

        # Trigger halt
        await halt_trigger_service.on_fork_detected(fork_payload)

        # Verify halt state
        assert await halt_checker.is_halted() is True
        assert dual_channel.get_trigger_count() == 1

        # Verify crisis event recorded
        assert halt_trigger_service.crisis_event_id is not None
        assert dual_channel.get_crisis_event_id() is not None

        # Verify halt reason
        reason = await halt_checker.get_halt_reason()
        assert reason is not None
        assert "FR17" in reason
        assert "fork" in reason.lower() or "Fork" in reason

    @pytest.mark.asyncio
    async def test_multiple_services_see_halt(self) -> None:
        """Test multiple services see the same halt state."""
        # Shared dual-channel transport
        dual_channel = DualChannelHaltTransportStub()

        # Multiple halt checkers (simulating different services)
        checker1 = HaltCheckerStub(dual_channel_halt=dual_channel)
        checker2 = HaltCheckerStub(dual_channel_halt=dual_channel)
        checker3 = HaltCheckerStub(dual_channel_halt=dual_channel)

        # Initially none halted
        assert await checker1.is_halted() is False
        assert await checker2.is_halted() is False
        assert await checker3.is_halted() is False

        # Write halt to dual-channel
        await dual_channel.write_halt("System-wide halt", uuid4())

        # All checkers see halt
        assert await checker1.is_halted() is True
        assert await checker2.is_halted() is True
        assert await checker3.is_halted() is True

        # All checkers return same reason
        reason1 = await checker1.get_halt_reason()
        reason2 = await checker2.get_halt_reason()
        reason3 = await checker3.get_halt_reason()
        assert reason1 == reason2 == reason3 == "System-wide halt"
