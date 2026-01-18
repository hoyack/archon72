"""Unit tests for ForkMonitorStub (Story 3.1, Task 4).

Tests the stub implementation of ForkMonitor for testing/development.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.fork_detected import ForkDetectedPayload
from src.infrastructure.stubs.fork_monitor_stub import ForkMonitorStub


class TestForkMonitorStubBasic:
    """Basic tests for ForkMonitorStub."""

    @pytest.fixture
    def stub(self) -> ForkMonitorStub:
        """Create a ForkMonitorStub."""
        return ForkMonitorStub()

    @pytest.mark.asyncio
    async def test_no_fork_by_default(self, stub: ForkMonitorStub) -> None:
        """Stub should return no fork by default."""
        result = await stub.check_for_forks()
        assert result is None

    @pytest.mark.asyncio
    async def test_start_monitoring_does_not_raise(self, stub: ForkMonitorStub) -> None:
        """start_monitoring should not raise."""
        await stub.start_monitoring()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_monitoring_does_not_raise(self, stub: ForkMonitorStub) -> None:
        """stop_monitoring should not raise."""
        await stub.stop_monitoring()  # Should not raise

    def test_default_monitoring_interval(self, stub: ForkMonitorStub) -> None:
        """Default monitoring interval should be 10 seconds."""
        assert stub.monitoring_interval_seconds == 10


class TestForkMonitorStubInjection:
    """Tests for fork injection in ForkMonitorStub."""

    @pytest.fixture
    def stub(self) -> ForkMonitorStub:
        """Create a ForkMonitorStub."""
        return ForkMonitorStub()

    @pytest.mark.asyncio
    async def test_inject_fork_returns_injected(self, stub: ForkMonitorStub) -> None:
        """After injecting a fork, check_for_forks returns it."""
        injected_fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test-service",
        )

        stub.inject_fork(injected_fork)
        result = await stub.check_for_forks()

        assert result == injected_fork

    @pytest.mark.asyncio
    async def test_injected_fork_persists(self, stub: ForkMonitorStub) -> None:
        """Injected fork should persist across multiple calls."""
        injected_fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="d" * 64,
            content_hashes=("e" * 64, "f" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test-service",
        )

        stub.inject_fork(injected_fork)

        # Multiple calls should return the same fork
        result1 = await stub.check_for_forks()
        result2 = await stub.check_for_forks()

        assert result1 == injected_fork
        assert result2 == injected_fork

    @pytest.mark.asyncio
    async def test_clear_fork(self, stub: ForkMonitorStub) -> None:
        """clear_fork should remove injected fork."""
        injected_fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="g" * 64,
            content_hashes=("h" * 64, "i" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="test-service",
        )

        stub.inject_fork(injected_fork)
        assert await stub.check_for_forks() == injected_fork

        stub.clear_fork()
        assert await stub.check_for_forks() is None


class TestForkMonitorStubConfiguration:
    """Tests for ForkMonitorStub configuration."""

    def test_custom_monitoring_interval(self) -> None:
        """Should support custom monitoring interval."""
        stub = ForkMonitorStub(monitoring_interval_seconds=5)
        assert stub.monitoring_interval_seconds == 5

    def test_custom_service_id(self) -> None:
        """Should support custom service ID."""
        stub = ForkMonitorStub(service_id="custom-detector")
        assert stub.service_id == "custom-detector"

    def test_default_service_id(self) -> None:
        """Default service ID should be set."""
        stub = ForkMonitorStub()
        assert stub.service_id == "fork-monitor-stub"


class TestForkMonitorStubMonitoringState:
    """Tests for monitoring state in ForkMonitorStub."""

    @pytest.fixture
    def stub(self) -> ForkMonitorStub:
        """Create a ForkMonitorStub."""
        return ForkMonitorStub()

    @pytest.mark.asyncio
    async def test_is_monitoring_false_by_default(self, stub: ForkMonitorStub) -> None:
        """is_monitoring should be False by default."""
        assert stub.is_monitoring is False

    @pytest.mark.asyncio
    async def test_is_monitoring_true_after_start(self, stub: ForkMonitorStub) -> None:
        """is_monitoring should be True after start_monitoring."""
        await stub.start_monitoring()
        assert stub.is_monitoring is True

    @pytest.mark.asyncio
    async def test_is_monitoring_false_after_stop(self, stub: ForkMonitorStub) -> None:
        """is_monitoring should be False after stop_monitoring."""
        await stub.start_monitoring()
        await stub.stop_monitoring()
        assert stub.is_monitoring is False
