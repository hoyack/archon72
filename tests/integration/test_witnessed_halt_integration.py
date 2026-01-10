"""Integration tests for Witnessed Halt Event Before Stop (Story 3.9).

Tests the full integration of witnessed halt event writing:
- Fork detection -> Witnessed event -> Halt
- Failure handling with UnwitnessedHaltRecord creation

Constitutional Constraints:
- RT-2: Halt event MUST be written BEFORE halt takes effect
- CT-12: Witnessing creates accountability
- CT-13: Integrity over availability (halt proceeds even if write fails)
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.fork_monitoring_service import ForkMonitoringService
from src.application.services.halt_trigger_service import HaltTriggerService
from src.domain.events.constitutional_crisis import (
    CONSTITUTIONAL_CRISIS_EVENT_TYPE,
    CrisisType,
)
from src.domain.events.fork_detected import ForkDetectedPayload
from src.infrastructure.stubs.dual_channel_halt_stub import DualChannelHaltTransportStub
from src.infrastructure.stubs.fork_monitor_stub import ForkMonitorStub
from src.infrastructure.stubs.unwitnessed_halt_repository_stub import (
    UnwitnessedHaltRepositoryStub,
)
from src.infrastructure.stubs.witnessed_halt_writer_stub import WitnessedHaltWriterStub


class TestWitnessedHaltFullFlow:
    """Integration tests for full witnessed halt flow."""

    @pytest.fixture
    def fork_monitor_stub(self) -> ForkMonitorStub:
        """Create fork monitor stub."""
        return ForkMonitorStub(monitoring_interval_seconds=1)

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create dual channel halt transport stub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def witnessed_halt_writer(self) -> WitnessedHaltWriterStub:
        """Create witnessed halt writer stub."""
        return WitnessedHaltWriterStub()

    @pytest.fixture
    def unwitnessed_halt_repo(self) -> UnwitnessedHaltRepositoryStub:
        """Create unwitnessed halt repository stub."""
        return UnwitnessedHaltRepositoryStub()

    @pytest.fixture
    def halt_trigger_service(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        unwitnessed_halt_repo: UnwitnessedHaltRepositoryStub,
    ) -> HaltTriggerService:
        """Create halt trigger service with all components."""
        return HaltTriggerService(
            dual_channel_halt=dual_channel_stub,
            witnessed_halt_writer=witnessed_halt_writer,
            unwitnessed_halt_repository=unwitnessed_halt_repo,
            service_id="integration-halt-trigger",
        )

    @pytest.fixture
    def fork_monitoring_service(
        self,
        fork_monitor_stub: ForkMonitorStub,
        halt_trigger_service: HaltTriggerService,
    ) -> ForkMonitoringService:
        """Create fork monitoring service wired to halt trigger."""
        return ForkMonitoringService(
            fork_monitor=fork_monitor_stub,
            on_fork_detected=halt_trigger_service.on_fork_detected,
            service_id="integration-fork-monitor",
        )

    @pytest.mark.asyncio
    async def test_fork_creates_witnessed_halt_event_then_halts(
        self,
        fork_monitoring_service: ForkMonitoringService,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        dual_channel_stub: DualChannelHaltTransportStub,
    ) -> None:
        """Full flow: fork -> witnessed event -> halt (RT-2)."""
        # Create and process fork
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="integration-fork-monitor",
        )

        await halt_trigger_service.on_fork_detected(fork)

        # Verify witnessed event was written
        written_events = witnessed_halt_writer.get_written_events()
        assert len(written_events) == 1

        # Verify halt was triggered
        assert await dual_channel_stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_halt_event_contains_all_required_fields(
        self,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
    ) -> None:
        """Halt event should contain all required fields (AC2)."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test-service",
        )

        await halt_trigger_service.on_fork_detected(fork)

        written_events = witnessed_halt_writer.get_written_events()
        event = written_events[0]

        # Check event type
        assert event.event_type == CONSTITUTIONAL_CRISIS_EVENT_TYPE

        # Check payload fields
        assert event.payload["crisis_type"] == CrisisType.FORK_DETECTED.value
        assert "detection_timestamp" in event.payload
        assert "detection_details" in event.payload
        assert "triggering_event_ids" in event.payload
        assert "detecting_service_id" in event.payload

    @pytest.mark.asyncio
    async def test_halt_event_is_witnessed(
        self,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
    ) -> None:
        """Halt event should be witnessed (CT-12)."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test-service",
        )

        await halt_trigger_service.on_fork_detected(fork)

        written_events = witnessed_halt_writer.get_written_events()
        event = written_events[0]

        # CT-12: Witnessing creates accountability
        assert event.witness_id is not None
        assert len(event.witness_id) > 0
        assert event.witness_signature is not None
        assert len(event.witness_signature) > 0


class TestWitnessedHaltFailureHandling:
    """Integration tests for failure handling (CT-13)."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create dual channel halt transport stub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def witnessed_halt_writer(self) -> WitnessedHaltWriterStub:
        """Create witnessed halt writer stub."""
        return WitnessedHaltWriterStub()

    @pytest.fixture
    def unwitnessed_halt_repo(self) -> UnwitnessedHaltRepositoryStub:
        """Create unwitnessed halt repository stub."""
        return UnwitnessedHaltRepositoryStub()

    @pytest.fixture
    def halt_trigger_service(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        unwitnessed_halt_repo: UnwitnessedHaltRepositoryStub,
    ) -> HaltTriggerService:
        """Create halt trigger service with all components."""
        return HaltTriggerService(
            dual_channel_halt=dual_channel_stub,
            witnessed_halt_writer=witnessed_halt_writer,
            unwitnessed_halt_repository=unwitnessed_halt_repo,
            service_id="integration-halt-trigger",
        )

    @pytest.mark.asyncio
    async def test_halt_proceeds_when_event_store_unavailable(
        self,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        dual_channel_stub: DualChannelHaltTransportStub,
    ) -> None:
        """CT-13: Halt should proceed even when event store is unavailable."""
        # Configure writer to fail
        witnessed_halt_writer.set_fail_next()

        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test-service",
        )

        await halt_trigger_service.on_fork_detected(fork)

        # No witnessed event written
        assert len(witnessed_halt_writer.get_written_events()) == 0

        # But halt should proceed (CT-13)
        assert await dual_channel_stub.is_halted() is True

    @pytest.mark.asyncio
    async def test_unwitnessed_halt_record_created_on_failure(
        self,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        unwitnessed_halt_repo: UnwitnessedHaltRepositoryStub,
    ) -> None:
        """Should create UnwitnessedHaltRecord when write fails."""
        witnessed_halt_writer.set_fail_next()

        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test-service",
        )

        await halt_trigger_service.on_fork_detected(fork)

        # Unwitnessed halt record should exist
        records = await unwitnessed_halt_repo.get_all()
        assert len(records) == 1

        record = records[0]
        assert record.crisis_payload.crisis_type == CrisisType.FORK_DETECTED
        assert "Event store write failed" in record.failure_reason


class TestConstitutionalComplianceRT2:
    """Tests verifying RT-2 constitutional compliance."""

    @pytest.fixture
    def dual_channel_stub(self) -> DualChannelHaltTransportStub:
        """Create dual channel halt transport stub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def witnessed_halt_writer(self) -> WitnessedHaltWriterStub:
        """Create witnessed halt writer stub."""
        return WitnessedHaltWriterStub()

    @pytest.fixture
    def unwitnessed_halt_repo(self) -> UnwitnessedHaltRepositoryStub:
        """Create unwitnessed halt repository stub."""
        return UnwitnessedHaltRepositoryStub()

    @pytest.fixture
    def halt_trigger_service(
        self,
        dual_channel_stub: DualChannelHaltTransportStub,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        unwitnessed_halt_repo: UnwitnessedHaltRepositoryStub,
    ) -> HaltTriggerService:
        """Create halt trigger service with all components."""
        return HaltTriggerService(
            dual_channel_halt=dual_channel_stub,
            witnessed_halt_writer=witnessed_halt_writer,
            unwitnessed_halt_repository=unwitnessed_halt_repo,
            service_id="rt2-test",
        )

    @pytest.mark.asyncio
    async def test_constitutional_compliance_rt2(
        self,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
    ) -> None:
        """RT-2: Halt signals MUST create witnessed event BEFORE system stops."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="rt2-test",
        )

        await halt_trigger_service.on_fork_detected(fork)

        # RT-2: Witnessed event MUST exist
        written_events = witnessed_halt_writer.get_written_events()
        assert len(written_events) == 1

        # RT-2: Crisis event ID should match written event
        assert halt_trigger_service.crisis_event_id == written_events[0].event_id

    @pytest.mark.asyncio
    async def test_constitutional_compliance_ct12(
        self,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
    ) -> None:
        """CT-12: Witnessing creates accountability."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="ct12-test",
        )

        await halt_trigger_service.on_fork_detected(fork)

        written_events = witnessed_halt_writer.get_written_events()
        event = written_events[0]

        # CT-12: Event MUST have witness attribution
        assert event.witness_id is not None
        assert event.witness_signature is not None

    @pytest.mark.asyncio
    async def test_sequence_gap_creates_witnessed_halt_event(
        self,
        halt_trigger_service: HaltTriggerService,
        witnessed_halt_writer: WitnessedHaltWriterStub,
        dual_channel_stub: DualChannelHaltTransportStub,
    ) -> None:
        """Sequence gap crisis should also create witnessed halt event."""
        crisis_id = await halt_trigger_service.trigger_halt_for_crisis(
            crisis_type=CrisisType.SEQUENCE_GAP_DETECTED,
            detection_details="Gap detected in sequence 100-105",
            triggering_event_ids=(),
        )

        # Witnessed event should be written
        written_events = witnessed_halt_writer.get_written_events()
        assert len(written_events) == 1

        # Halt should be triggered
        assert await dual_channel_stub.is_halted() is True

        # Crisis ID should match
        assert halt_trigger_service.crisis_event_id == crisis_id
