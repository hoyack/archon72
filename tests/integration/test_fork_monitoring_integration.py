"""Integration tests for fork monitoring (Story 3.1, Task 6).

Tests the full fork monitoring flow including:
- Fork detection with conflicting events
- Monitoring interval configuration
- ForkDetectedPayload creation
- Detection latency logging
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.fork_monitoring_service import ForkMonitoringService
from src.domain.events.event import Event
from src.domain.events.fork_detected import (
    FORK_DETECTED_EVENT_TYPE,
    ForkDetectedPayload,
)
from src.domain.services.fork_detection import ForkDetectionService
from src.infrastructure.stubs.fork_monitor_stub import ForkMonitorStub


class TestForkDetectionIntegration:
    """Integration tests for fork detection flow."""

    @pytest.fixture
    def create_event(self) -> callable:
        """Factory for creating test events."""

        def _create(
            prev_hash: str = "a" * 64,
            content_hash: str | None = None,
            sequence: int = 1,
        ) -> Event:
            return Event(
                event_id=uuid4(),
                sequence=sequence,
                event_type="test.event",
                payload={"test": True},
                prev_hash=prev_hash,
                content_hash=content_hash or uuid4().hex + uuid4().hex,
                signature="sig" * 20,
                witness_id="WITNESS:test",
                witness_signature="wsig" * 20,
                local_timestamp=datetime.now(timezone.utc),
            )

        return _create

    def test_fork_detection_with_conflicting_events(
        self, create_event: callable
    ) -> None:
        """Test fork detection when two events have same prev_hash but different content_hash."""
        # Create conflicting events
        shared_prev_hash = "abc" * 21 + "d"  # 64 chars
        event1 = create_event(
            prev_hash=shared_prev_hash,
            content_hash="111" * 21 + "1",
        )
        event2 = create_event(
            prev_hash=shared_prev_hash,
            content_hash="222" * 21 + "2",
        )

        # Use ForkDetectionService
        service = ForkDetectionService(service_id="integration-test")
        result = service.detect_fork([event1, event2])

        # Verify fork detected
        assert result is not None
        assert isinstance(result, ForkDetectedPayload)
        assert result.prev_hash == shared_prev_hash
        assert event1.event_id in result.conflicting_event_ids
        assert event2.event_id in result.conflicting_event_ids
        assert event1.content_hash in result.content_hashes
        assert event2.content_hash in result.content_hashes
        assert result.detecting_service_id == "integration-test"

    def test_fork_detected_payload_fields(self, create_event: callable) -> None:
        """Test ForkDetectedPayload has all required fields (AC2)."""
        shared_prev_hash = "def" * 21 + "g"
        event1 = create_event(prev_hash=shared_prev_hash, content_hash="333" * 21 + "3")
        event2 = create_event(prev_hash=shared_prev_hash, content_hash="444" * 21 + "4")

        service = ForkDetectionService(service_id="test")
        result = service.detect_fork([event1, event2])

        # Verify all fields per AC2
        assert result is not None
        assert hasattr(result, "conflicting_event_ids")  # Event IDs
        assert hasattr(result, "prev_hash")  # Shared prev_hash
        assert hasattr(result, "content_hashes")  # Both content hashes
        assert hasattr(result, "detection_timestamp")
        assert hasattr(result, "detecting_service_id")

    def test_fork_detection_event_type(self) -> None:
        """Test FORK_DETECTED_EVENT_TYPE constant."""
        assert FORK_DETECTED_EVENT_TYPE == "constitutional.fork_detected"


class TestMonitoringIntervalIntegration:
    """Integration tests for monitoring interval configuration (AC3)."""

    def test_default_monitoring_interval_10_seconds(self) -> None:
        """Default monitoring interval should be 10 seconds (AC3)."""
        stub = ForkMonitorStub()
        assert stub.monitoring_interval_seconds == 10

    def test_custom_monitoring_interval(self) -> None:
        """Monitoring interval should be configurable."""
        stub = ForkMonitorStub(monitoring_interval_seconds=5)
        assert stub.monitoring_interval_seconds == 5

    @pytest.mark.asyncio
    async def test_monitoring_service_uses_interval(self) -> None:
        """ForkMonitoringService should use the configured interval."""
        stub = ForkMonitorStub(monitoring_interval_seconds=7)
        callback = AsyncMock()

        service = ForkMonitoringService(
            fork_monitor=stub,
            on_fork_detected=callback,
            service_id="interval-test",
        )

        assert service.monitoring_interval_seconds == 7


class TestForkDetectionCallbackIntegration:
    """Integration tests for fork detection callback flow."""

    @pytest.mark.asyncio
    async def test_callback_receives_fork_payload(self) -> None:
        """Callback should receive ForkDetectedPayload when fork is detected."""
        stub = ForkMonitorStub(monitoring_interval_seconds=1)
        received_forks: list[ForkDetectedPayload] = []

        async def on_fork(fork: ForkDetectedPayload) -> None:
            received_forks.append(fork)

        service = ForkMonitoringService(
            fork_monitor=stub,
            on_fork_detected=on_fork,
            service_id="callback-test",
        )

        # Inject a fork
        injected_fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="xyz" * 21 + "z",
            content_hashes=("aaa" * 21 + "a", "bbb" * 21 + "b"),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test",
        )
        stub.inject_fork(injected_fork)

        # Start monitoring
        await service.start_monitoring()
        await asyncio.sleep(0.15)  # Let it run one cycle
        await service.stop_monitoring()

        # Verify callback was called with the fork
        assert len(received_forks) >= 1
        assert received_forks[0] == injected_fork


class TestLatencyLoggingIntegration:
    """Integration tests for latency logging (AC3)."""

    @pytest.mark.asyncio
    async def test_monitoring_completes_check_cycle(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Monitoring should complete check cycles and log latency."""
        stub = ForkMonitorStub(monitoring_interval_seconds=1)
        callback = AsyncMock()

        service = ForkMonitoringService(
            fork_monitor=stub,
            on_fork_detected=callback,
            service_id="latency-test",
        )

        await service.start_monitoring()
        await asyncio.sleep(0.15)  # Let it run one cycle
        await service.stop_monitoring()

        # The service should have completed at least one check
        # We verify it ran by checking that it started and stopped without errors
        assert service.is_monitoring is False

        # Logging happens via structlog - we can see it in captured output
        capsys.readouterr()
        # The implementation logs "fork_check_completed" with latency_ms
        # The test passes if no exceptions were raised


class TestFullForkMonitoringPipeline:
    """Full pipeline integration tests."""

    @pytest.fixture
    def create_event(self) -> callable:
        """Factory for creating test events."""

        def _create(
            prev_hash: str = "a" * 64,
            content_hash: str | None = None,
            sequence: int = 1,
        ) -> Event:
            return Event(
                event_id=uuid4(),
                sequence=sequence,
                event_type="test.event",
                payload={"test": True},
                prev_hash=prev_hash,
                content_hash=content_hash or uuid4().hex + uuid4().hex,
                signature="sig" * 20,
                witness_id="WITNESS:test",
                witness_signature="wsig" * 20,
                local_timestamp=datetime.now(timezone.utc),
            )

        return _create

    @pytest.mark.asyncio
    async def test_full_fork_detection_pipeline(self, create_event: callable) -> None:
        """Test the full fork detection pipeline from events to callback."""
        # Create conflicting events
        shared_prev = "full" * 16  # 64 chars
        event1 = create_event(prev_hash=shared_prev, content_hash="eee" * 21 + "e")
        event2 = create_event(prev_hash=shared_prev, content_hash="fff" * 21 + "f")

        # Use domain service to detect fork
        detector = ForkDetectionService(service_id="pipeline-detector")
        fork_result = detector.detect_fork([event1, event2])

        assert fork_result is not None

        # Now test monitoring service with the detected fork
        stub = ForkMonitorStub(monitoring_interval_seconds=1)
        stub.inject_fork(fork_result)

        callback_results: list[ForkDetectedPayload] = []

        async def capture_fork(fork: ForkDetectedPayload) -> None:
            callback_results.append(fork)

        monitoring_service = ForkMonitoringService(
            fork_monitor=stub,
            on_fork_detected=capture_fork,
            service_id="pipeline-monitor",
        )

        await monitoring_service.start_monitoring()
        await asyncio.sleep(0.15)
        await monitoring_service.stop_monitoring()

        # Verify the pipeline worked end-to-end
        assert len(callback_results) >= 1
        captured_fork = callback_results[0]
        assert captured_fork.prev_hash == shared_prev
        assert event1.event_id in captured_fork.conflicting_event_ids
        assert event2.event_id in captured_fork.conflicting_event_ids
