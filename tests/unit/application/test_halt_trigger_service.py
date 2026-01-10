"""Unit tests for HaltTriggerService (Story 3.2/3.3/3.9).

Tests the halt trigger service with both:
- DualChannelHaltTransport (preferred, Story 3.3)
- Legacy HaltTrigger (backward compatible, Story 3.2)
- Witnessed halt event writing (Story 3.9, RT-2)

ADR-3: Partition Behavior + Halt Durability
- DualChannelHaltTransport writes to Redis Streams + DB halt flag
- If EITHER channel indicates halt -> component halts

Story 3.9: Witnessed Halt Event Before Stop
- RT-2: Halt event MUST be written BEFORE halt takes effect
- CT-13: If write fails, halt proceeds anyway (integrity over availability)
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.halt_trigger_service import HaltTriggerService
from src.domain.events.constitutional_crisis import CrisisType
from src.domain.events.fork_detected import ForkDetectedPayload
from src.infrastructure.stubs.dual_channel_halt_stub import (
    DualChannelHaltTransportStub,
)
from src.infrastructure.stubs.halt_state import HaltState
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub
from src.infrastructure.stubs.unwitnessed_halt_repository_stub import (
    UnwitnessedHaltRepositoryStub,
)
from src.infrastructure.stubs.witnessed_halt_writer_stub import WitnessedHaltWriterStub


class TestHaltTriggerServiceInitialization:
    """Test HaltTriggerService initialization."""

    def test_init_with_dual_channel_halt(self) -> None:
        """Should initialize with DualChannelHaltTransport."""
        stub = DualChannelHaltTransportStub()
        service = HaltTriggerService(
            dual_channel_halt=stub,
            service_id="test-service",
        )
        assert service.service_id == "test-service"
        assert service._dual_channel_halt is stub
        assert service._halt_trigger is None

    def test_init_with_legacy_halt_trigger(self) -> None:
        """Should initialize with legacy HaltTrigger for backward compatibility."""
        halt_state = HaltState.get_instance(f"test-{uuid4()}")
        stub = HaltTriggerStub(halt_state=halt_state)
        service = HaltTriggerService(
            halt_trigger=stub,
            service_id="test-service",
        )
        assert service.service_id == "test-service"
        assert service._halt_trigger is stub
        assert service._dual_channel_halt is None

    def test_init_with_both_prefers_dual_channel(self) -> None:
        """When both provided, dual_channel_halt should be preferred."""
        halt_state = HaltState.get_instance(f"test-{uuid4()}")
        dual_stub = DualChannelHaltTransportStub()
        legacy_stub = HaltTriggerStub(halt_state=halt_state)

        service = HaltTriggerService(
            dual_channel_halt=dual_stub,
            halt_trigger=legacy_stub,
            service_id="test-service",
        )
        assert service._dual_channel_halt is dual_stub
        assert service._halt_trigger is legacy_stub

    def test_init_without_either_raises_error(self) -> None:
        """Should raise ValueError if neither transport provided."""
        with pytest.raises(ValueError, match="Either dual_channel_halt or halt_trigger"):
            HaltTriggerService(service_id="test-service")


class TestHaltTriggerServiceWithDualChannel:
    """Test HaltTriggerService with DualChannelHaltTransport."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create DualChannelHaltTransportStub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def service(
        self, dual_channel_stub: DualChannelHaltTransportStub
    ) -> HaltTriggerService:
        """Create HaltTriggerService with dual-channel transport."""
        return HaltTriggerService(
            dual_channel_halt=dual_channel_stub,
            service_id="dual-channel-test",
        )

    @pytest.fixture
    def fork_payload(self) -> ForkDetectedPayload:
        """Create sample fork payload."""
        return ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="abc123" * 10,
            content_hashes=("hash1", "hash2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-test",
        )

    @pytest.mark.asyncio
    async def test_on_fork_detected_writes_to_dual_channel(
        self,
        service: HaltTriggerService,
        dual_channel_stub: DualChannelHaltTransportStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Fork detection should write halt to dual-channel transport."""
        assert dual_channel_stub.get_trigger_count() == 0

        await service.on_fork_detected(fork_payload)

        assert dual_channel_stub.get_trigger_count() == 1
        assert await dual_channel_stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_on_fork_detected_includes_reason(
        self,
        service: HaltTriggerService,
        dual_channel_stub: DualChannelHaltTransportStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Fork detection should include FR17 reason."""
        await service.on_fork_detected(fork_payload)

        reason = await dual_channel_stub.get_halt_reason()
        assert reason is not None
        assert "FR17" in reason

    @pytest.mark.asyncio
    async def test_on_fork_detected_includes_crisis_event_id(
        self,
        service: HaltTriggerService,
        dual_channel_stub: DualChannelHaltTransportStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Fork detection should include crisis event ID."""
        await service.on_fork_detected(fork_payload)

        crisis_id = dual_channel_stub.get_crisis_event_id()
        assert crisis_id is not None
        assert crisis_id == service.crisis_event_id

    @pytest.mark.asyncio
    async def test_trigger_halt_for_crisis_writes_to_dual_channel(
        self,
        service: HaltTriggerService,
        dual_channel_stub: DualChannelHaltTransportStub,
    ) -> None:
        """Direct crisis trigger should write to dual-channel transport."""
        crisis_id = await service.trigger_halt_for_crisis(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_details="Direct test crisis",
        )

        assert dual_channel_stub.get_trigger_count() == 1
        assert await dual_channel_stub.is_halted() is True
        assert dual_channel_stub.get_crisis_event_id() == crisis_id


class TestHaltTriggerServiceWithLegacyTrigger:
    """Test HaltTriggerService with legacy HaltTrigger (backward compatibility)."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.fixture
    def halt_state(self) -> HaltState:
        """Create shared halt state."""
        return HaltState.get_instance(f"legacy-test-{uuid4()}")

    @pytest.fixture
    def legacy_trigger(self, halt_state: HaltState) -> HaltTriggerStub:
        """Create legacy HaltTriggerStub."""
        return HaltTriggerStub(halt_state=halt_state)

    @pytest.fixture
    def service(self, legacy_trigger: HaltTriggerStub) -> HaltTriggerService:
        """Create HaltTriggerService with legacy trigger."""
        return HaltTriggerService(
            halt_trigger=legacy_trigger,
            service_id="legacy-test",
        )

    @pytest.fixture
    def fork_payload(self) -> ForkDetectedPayload:
        """Create sample fork payload."""
        return ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="abc123" * 10,
            content_hashes=("hash1", "hash2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-test",
        )

    @pytest.mark.asyncio
    async def test_on_fork_detected_uses_legacy_trigger(
        self,
        service: HaltTriggerService,
        legacy_trigger: HaltTriggerStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Fork detection should use legacy trigger when no dual-channel available."""
        assert legacy_trigger.get_trigger_count() == 0

        await service.on_fork_detected(fork_payload)

        assert legacy_trigger.get_trigger_count() == 1
        assert legacy_trigger.is_halted() is True

    @pytest.mark.asyncio
    async def test_trigger_halt_for_crisis_uses_legacy_trigger(
        self,
        service: HaltTriggerService,
        legacy_trigger: HaltTriggerStub,
    ) -> None:
        """Direct crisis trigger should use legacy trigger."""
        await service.trigger_halt_for_crisis(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_details="Direct test crisis",
        )

        assert legacy_trigger.get_trigger_count() == 1
        assert legacy_trigger.is_halted() is True


class TestDualChannelPreferredOverLegacy:
    """Test that DualChannelHaltTransport is preferred over legacy HaltTrigger."""

    @pytest.fixture(autouse=True)
    def reset_halt_state(self) -> None:
        """Reset all HaltState instances before each test."""
        HaltState.reset_all()

    @pytest.mark.asyncio
    async def test_dual_channel_used_when_both_provided(self) -> None:
        """When both transports provided, dual-channel should be used."""
        halt_state = HaltState.get_instance(f"prefer-test-{uuid4()}")
        dual_stub = DualChannelHaltTransportStub()
        legacy_stub = HaltTriggerStub(halt_state=halt_state)

        service = HaltTriggerService(
            dual_channel_halt=dual_stub,
            halt_trigger=legacy_stub,
            service_id="prefer-test",
        )

        fork_payload = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="xyz789" * 10,
            content_hashes=("h1", "h2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test",
        )

        await service.on_fork_detected(fork_payload)

        # Dual-channel should be used
        assert dual_stub.get_trigger_count() == 1
        assert await dual_stub.is_halted() is True

        # Legacy should NOT be used
        assert legacy_stub.get_trigger_count() == 0
        assert legacy_stub.is_halted() is False


class TestWitnessedHaltEventWriting:
    """Tests for Story 3.9 - Witnessed Halt Event Before Stop (RT-2)."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create DualChannelHaltTransportStub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def witnessed_halt_writer(self) -> WitnessedHaltWriterStub:
        """Create WitnessedHaltWriterStub."""
        return WitnessedHaltWriterStub()

    @pytest.fixture
    def unwitnessed_halt_repo(self) -> UnwitnessedHaltRepositoryStub:
        """Create UnwitnessedHaltRepositoryStub."""
        return UnwitnessedHaltRepositoryStub()

    @pytest.fixture
    def service_with_witnessing(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        unwitnessed_halt_repo: UnwitnessedHaltRepositoryStub,
    ) -> HaltTriggerService:
        """Create HaltTriggerService with witnessing support."""
        return HaltTriggerService(
            dual_channel_halt=dual_channel_stub,
            witnessed_halt_writer=witnessed_halt_writer,
            unwitnessed_halt_repository=unwitnessed_halt_repo,
            service_id="witnessed-test",
        )

    @pytest.fixture
    def fork_payload(self) -> ForkDetectedPayload:
        """Create sample fork payload."""
        return ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="abc123" * 10,
            content_hashes=("hash1", "hash2"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fork-monitor-test",
        )

    @pytest.mark.asyncio
    async def test_halt_writes_witnessed_event_before_triggering_halt(
        self,
        service_with_witnessing: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        dual_channel_stub: DualChannelHaltTransportStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """RT-2: Witnessed event should be written BEFORE halt is triggered."""
        await service_with_witnessing.on_fork_detected(fork_payload)

        # Event should be written
        written_events = witnessed_halt_writer.get_written_events()
        assert len(written_events) == 1

        # Halt should also be triggered
        assert await dual_channel_stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_halt_proceeds_when_event_write_fails(
        self,
        service_with_witnessing: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        dual_channel_stub: DualChannelHaltTransportStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """CT-13: Halt should proceed even if witnessed event write fails."""
        witnessed_halt_writer.set_fail_next()

        await service_with_witnessing.on_fork_detected(fork_payload)

        # Event write failed
        written_events = witnessed_halt_writer.get_written_events()
        assert len(written_events) == 0

        # But halt should still proceed (CT-13: integrity over availability)
        assert await dual_channel_stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_unwitnessed_halt_record_created_on_failure(
        self,
        service_with_witnessing: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        unwitnessed_halt_repo: UnwitnessedHaltRepositoryStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Should create UnwitnessedHaltRecord when event write fails."""
        witnessed_halt_writer.set_fail_next()

        await service_with_witnessing.on_fork_detected(fork_payload)

        # Unwitnessed halt record should be created
        records = await unwitnessed_halt_repo.get_all()
        assert len(records) == 1
        assert records[0].crisis_payload.crisis_type == CrisisType.FORK_DETECTED

    @pytest.mark.asyncio
    async def test_crisis_event_id_matches_written_event(
        self,
        service_with_witnessing: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Crisis event ID should match the written event's ID."""
        await service_with_witnessing.on_fork_detected(fork_payload)

        written_events = witnessed_halt_writer.get_written_events()
        assert len(written_events) == 1
        assert service_with_witnessing.crisis_event_id == written_events[0].event_id

    @pytest.mark.asyncio
    async def test_halt_not_triggered_twice_even_with_retry(
        self,
        service_with_witnessing: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        dual_channel_stub: DualChannelHaltTransportStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """Subsequent fork detections should not create additional events."""
        await service_with_witnessing.on_fork_detected(fork_payload)
        await service_with_witnessing.on_fork_detected(fork_payload)
        await service_with_witnessing.on_fork_detected(fork_payload)

        # Only one event should be written
        written_events = witnessed_halt_writer.get_written_events()
        assert len(written_events) == 1

        # Only one halt trigger
        assert dual_channel_stub.get_trigger_count() == 1

    @pytest.mark.asyncio
    async def test_no_unwitnessed_record_when_write_succeeds(
        self,
        service_with_witnessing: HaltTriggerService,
        unwitnessed_halt_repo: UnwitnessedHaltRepositoryStub,
        fork_payload: ForkDetectedPayload,
    ) -> None:
        """No unwitnessed halt record should be created when write succeeds."""
        await service_with_witnessing.on_fork_detected(fork_payload)

        records = await unwitnessed_halt_repo.get_all()
        assert len(records) == 0
