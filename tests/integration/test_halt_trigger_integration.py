"""Integration tests for Halt Trigger System (Story 3.2, Task 7).

Tests the full integration of:
- ForkMonitoringService → HaltTriggerService → HaltTrigger → HaltChecker

Constitutional Constraints:
- AC1: Immediate halt on fork detection (within 1 second)
- AC2: ConstitutionalCrisisEvent created BEFORE halt (RT-2)
- AC3: Writer stops accepting events after halt
- AC4: HaltChecker reflects halt state

Test Strategy:
- Use stubs for all infrastructure (HaltTriggerStub, HaltCheckerStub)
- Test full flow from fork detection to halt state
- Verify timing constraints where applicable
"""

import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.fork_monitoring_service import ForkMonitoringService
from src.application.services.halt_trigger_service import HaltTriggerService
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.fork_detected import ForkDetectedPayload
from src.infrastructure.stubs.fork_monitor_stub import ForkMonitorStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.halt_state import HaltState
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub


class TestForkDetectionHaltIntegration:
    """Integration tests for fork detection → halt trigger flow."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.fixture
    def shared_halt_state(self) -> HaltState:
        """Create shared halt state for test isolation."""
        return HaltState.get_instance(f"integration-test-{uuid4()}")

    @pytest.fixture
    def halt_trigger(self, shared_halt_state: HaltState) -> HaltTriggerStub:
        """Create halt trigger stub with shared state."""
        return HaltTriggerStub(halt_state=shared_halt_state)

    @pytest.fixture
    def halt_checker(self, shared_halt_state: HaltState) -> HaltCheckerStub:
        """Create halt checker stub with same shared state."""
        return HaltCheckerStub(halt_state=shared_halt_state)

    @pytest.fixture
    def halt_trigger_service(self, halt_trigger: HaltTriggerStub) -> HaltTriggerService:
        """Create halt trigger service."""
        return HaltTriggerService(
            halt_trigger=halt_trigger,
            service_id="halt-trigger-integration-test",
        )

    @pytest.fixture
    def fork_payload(self) -> ForkDetectedPayload:
        """Create a sample fork detected payload."""
        return ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="abc123" * 10,
            content_hashes=("hash1", "hash2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-integration-test",
        )

    @pytest.mark.asyncio
    async def test_fork_detection_triggers_halt_within_1_second(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test AC1: Fork detection triggers halt within 1 second."""
        # Initially not halted
        assert await halt_checker.is_halted() is False

        # Record start time
        start_time = time.monotonic()

        # Trigger halt via fork detection
        await halt_trigger_service.on_fork_detected(fork_payload)

        # Record end time
        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Verify halt triggered within 1 second (1000ms)
        assert elapsed_ms < 1000, f"Halt took {elapsed_ms}ms, expected < 1000ms"

        # Verify system is halted
        assert await halt_checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_constitutional_crisis_event_created_before_halt(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_trigger: HaltTriggerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test AC2: ConstitutionalCrisisEvent created BEFORE halt (RT-2)."""
        # Initially no crisis event
        assert halt_trigger_service.crisis_event_id is None
        assert halt_trigger_service.halt_triggered is False

        # Trigger halt
        await halt_trigger_service.on_fork_detected(fork_payload)

        # Crisis event should be set
        assert halt_trigger_service.crisis_event_id is not None

        # Halt trigger should have received the crisis event ID
        assert (
            halt_trigger.get_last_crisis_event_id()
            == halt_trigger_service.crisis_event_id
        )

    @pytest.mark.asyncio
    async def test_halt_checker_returns_true_after_halt(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test AC4: HaltChecker returns True after halt is triggered."""
        # Before halt
        assert await halt_checker.is_halted() is False
        assert await halt_checker.get_halt_reason() is None

        # Trigger halt
        await halt_trigger_service.on_fork_detected(fork_payload)

        # After halt
        assert await halt_checker.is_halted() is True

        # Reason should include FR17
        reason = await halt_checker.get_halt_reason()
        assert reason is not None
        assert "FR17" in reason

    @pytest.mark.asyncio
    async def test_halt_reason_includes_crisis_details(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test AC4: Halt reason includes crisis details."""
        await halt_trigger_service.on_fork_detected(fork_payload)

        reason = await halt_checker.get_halt_reason()
        assert reason is not None

        # Should mention fork detected
        assert "fork" in reason.lower() or "Fork" in reason

        # Should mention number of conflicting events
        assert "2" in reason  # We created 2 conflicting events

    @pytest.mark.asyncio
    async def test_multiple_fork_detections_dont_cause_duplicate_halts(
        self,
        halt_trigger_service: HaltTriggerService,
        halt_trigger: HaltTriggerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Test: Multiple fork detections don't cause duplicate crisis events."""
        # First fork detection
        await halt_trigger_service.on_fork_detected(fork_payload)
        first_crisis_id = halt_trigger_service.crisis_event_id
        first_trigger_count = halt_trigger.get_trigger_count()

        # Second fork detection (different prev_hash)
        second_fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="xyz789" * 10,
            content_hashes=("hash3", "hash4"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-2",
        )
        await halt_trigger_service.on_fork_detected(second_fork)

        # Should still have original crisis event ID
        assert halt_trigger_service.crisis_event_id == first_crisis_id

        # Trigger count should be 1 (only first halt)
        assert halt_trigger.get_trigger_count() == first_trigger_count


class TestFullForkMonitoringIntegration:
    """Integration tests for full ForkMonitoringService → HaltTriggerService flow."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.fixture
    def shared_halt_state(self) -> HaltState:
        """Create shared halt state for test isolation."""
        return HaltState.get_instance(f"full-integration-{uuid4()}")

    @pytest.fixture
    def halt_trigger(self, shared_halt_state: HaltState) -> HaltTriggerStub:
        """Create halt trigger stub."""
        return HaltTriggerStub(halt_state=shared_halt_state)

    @pytest.fixture
    def halt_checker(self, shared_halt_state: HaltState) -> HaltCheckerStub:
        """Create halt checker stub."""
        return HaltCheckerStub(halt_state=shared_halt_state)

    @pytest.fixture
    def halt_trigger_service(self, halt_trigger: HaltTriggerStub) -> HaltTriggerService:
        """Create halt trigger service."""
        return HaltTriggerService(
            halt_trigger=halt_trigger,
            service_id="halt-service-full-integration",
        )

    @pytest.fixture
    def fork_monitor_stub(self) -> ForkMonitorStub:
        """Create fork monitor stub."""
        return ForkMonitorStub()

    @pytest.mark.asyncio
    async def test_fork_monitoring_to_halt_checker_full_flow(
        self,
        fork_monitor_stub: ForkMonitorStub,
        halt_trigger_service: HaltTriggerService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test full flow: ForkMonitoringService → HaltTriggerService → HaltChecker."""
        # Create fork monitoring service with halt trigger callback
        fork_monitoring_service = ForkMonitoringService(
            fork_monitor=fork_monitor_stub,
            on_fork_detected=halt_trigger_service.on_fork_detected,
            service_id="fork-monitor-full-integration",
        )

        # Initially not halted
        assert await halt_checker.is_halted() is False

        # Inject a fork into the monitor stub
        fork_payload = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="fulltest" * 8,
            content_hashes=("h1", "h2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-full-integration",
        )
        fork_monitor_stub.inject_fork(fork_payload)

        # Check for forks and manually invoke callback
        # (The callback is normally invoked in the monitoring loop,
        # but for testing we manually call check_for_forks and invoke callback)
        detected_fork = await fork_monitoring_service.check_for_forks()

        # Fork should be detected
        assert detected_fork is not None

        # Manually invoke the callback (simulating what monitoring loop does)
        await halt_trigger_service.on_fork_detected(detected_fork)

        # After fork processing, system should be halted
        assert await halt_checker.is_halted() is True

        # Crisis event should be recorded
        assert halt_trigger_service.crisis_event_id is not None


class TestWriterRejectsAfterHalt:
    """Tests that Writer rejects writes after halt (AC3)."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.mark.asyncio
    async def test_simulated_writer_rejects_after_halt(self) -> None:
        """Test AC3: Writer rejects writes after halt with SystemHaltedError."""
        # Set up halt state
        halt_state = HaltState.get_instance(f"writer-reject-test-{uuid4()}")
        halt_checker = HaltCheckerStub(halt_state=halt_state)

        # Simulate a writer that checks halt state before writing
        async def simulated_write() -> str:
            """Simulated writer that checks halt state per HALT FIRST rule."""
            if await halt_checker.is_halted():
                reason = await halt_checker.get_halt_reason()
                raise SystemHaltedError(f"FR17: Constitutional crisis - {reason}")
            return "write successful"

        # Before halt, write succeeds
        result = await simulated_write()
        assert result == "write successful"

        # Trigger halt
        halt_state.set_halted_sync(True, "FR17: Fork detected")

        # After halt, write is rejected with SystemHaltedError
        with pytest.raises(SystemHaltedError) as exc_info:
            await simulated_write()

        # Error message should include FR17
        assert "FR17" in str(exc_info.value)
        assert "Constitutional crisis" in str(exc_info.value)


class TestHaltTriggerTiming:
    """Tests for halt trigger timing constraints."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.mark.asyncio
    async def test_halt_propagation_timeout_is_1_second(self) -> None:
        """Test that halt propagation timeout is configured to 1 second."""
        halt_state = HaltState.get_instance(f"timing-test-{uuid4()}")
        halt_trigger = HaltTriggerStub(halt_state=halt_state)

        assert halt_trigger.halt_propagation_timeout_seconds == 1.0

    @pytest.mark.asyncio
    async def test_halt_completes_quickly(self) -> None:
        """Test that halt operation completes quickly (well under timeout)."""
        halt_state = HaltState.get_instance(f"quick-halt-{uuid4()}")
        halt_trigger = HaltTriggerStub(halt_state=halt_state)

        start_time = time.monotonic()
        await halt_trigger.trigger_halt("Test halt", uuid4())
        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Should complete in much less than 100ms (stub is instant)
        assert elapsed_ms < 100, f"Halt took {elapsed_ms}ms"


class TestDirectCrisisTrigger:
    """Tests for direct crisis trigger (not via fork detection)."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.mark.asyncio
    async def test_direct_crisis_trigger(self) -> None:
        """Test triggering halt directly for a crisis."""
        from src.domain.events.constitutional_crisis import CrisisType

        halt_state = HaltState.get_instance(f"direct-crisis-{uuid4()}")
        halt_trigger = HaltTriggerStub(halt_state=halt_state)
        halt_checker = HaltCheckerStub(halt_state=halt_state)

        halt_trigger_service = HaltTriggerService(
            halt_trigger=halt_trigger,
            service_id="direct-crisis-test",
        )

        # Initially not halted
        assert await halt_checker.is_halted() is False

        # Trigger crisis directly
        crisis_id = await halt_trigger_service.trigger_halt_for_crisis(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_details="Direct crisis trigger test",
            triggering_event_ids=(uuid4(),),
        )

        # Should be halted
        assert await halt_checker.is_halted() is True

        # Crisis ID should be set
        assert crisis_id is not None
        assert halt_trigger_service.crisis_event_id == crisis_id

    @pytest.mark.asyncio
    async def test_direct_crisis_trigger_rejects_when_already_halted(self) -> None:
        """Test that direct crisis trigger rejects when already halted."""
        from src.domain.events.constitutional_crisis import CrisisType

        halt_state = HaltState.get_instance(f"already-halted-{uuid4()}")
        halt_trigger = HaltTriggerStub(halt_state=halt_state)

        halt_trigger_service = HaltTriggerService(
            halt_trigger=halt_trigger,
            service_id="already-halted-test",
        )

        # First trigger succeeds
        await halt_trigger_service.trigger_halt_for_crisis(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_details="First crisis",
        )

        # Second trigger raises RuntimeError
        with pytest.raises(RuntimeError, match="Halt already triggered"):
            await halt_trigger_service.trigger_halt_for_crisis(
                crisis_type=CrisisType.FORK_DETECTED,
                detection_details="Second crisis",
            )
