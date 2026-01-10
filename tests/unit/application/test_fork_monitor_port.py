"""Unit tests for ForkMonitor port interface (Story 3.1, Task 2).

Tests the ForkMonitor abstract base class definition.
This is the port interface for fork detection monitoring.
"""

from abc import ABC

import pytest

from src.application.ports.fork_monitor import ForkMonitor
from src.domain.events.fork_detected import ForkDetectedPayload


class TestForkMonitorInterface:
    """Tests for ForkMonitor ABC interface."""

    def test_fork_monitor_is_abstract(self) -> None:
        """ForkMonitor should be an abstract class."""
        assert issubclass(ForkMonitor, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Should not be able to instantiate ForkMonitor directly."""
        with pytest.raises(TypeError):
            ForkMonitor()  # type: ignore[abstract]

    def test_has_check_for_forks_method(self) -> None:
        """ForkMonitor should define check_for_forks abstract method."""
        assert hasattr(ForkMonitor, "check_for_forks")
        # Check it's abstract
        assert getattr(ForkMonitor.check_for_forks, "__isabstractmethod__", False)

    def test_has_start_monitoring_method(self) -> None:
        """ForkMonitor should define start_monitoring abstract method."""
        assert hasattr(ForkMonitor, "start_monitoring")
        assert getattr(ForkMonitor.start_monitoring, "__isabstractmethod__", False)

    def test_has_stop_monitoring_method(self) -> None:
        """ForkMonitor should define stop_monitoring abstract method."""
        assert hasattr(ForkMonitor, "stop_monitoring")
        assert getattr(ForkMonitor.stop_monitoring, "__isabstractmethod__", False)

    def test_has_monitoring_interval_property(self) -> None:
        """ForkMonitor should define monitoring_interval_seconds property."""
        assert hasattr(ForkMonitor, "monitoring_interval_seconds")

    def test_default_monitoring_interval(self) -> None:
        """Default monitoring interval should be 10 seconds."""
        # Create a concrete implementation to test the default
        class ConcreteForkMonitor(ForkMonitor):
            async def check_for_forks(self) -> ForkDetectedPayload | None:
                return None

            async def start_monitoring(self) -> None:
                pass

            async def stop_monitoring(self) -> None:
                pass

        monitor = ConcreteForkMonitor()
        assert monitor.monitoring_interval_seconds == 10


class TestConcreteForkMonitorImplementation:
    """Tests for concrete implementations of ForkMonitor."""

    def test_concrete_implementation_satisfies_interface(self) -> None:
        """A concrete implementation should satisfy the interface."""

        class TestForkMonitor(ForkMonitor):
            async def check_for_forks(self) -> ForkDetectedPayload | None:
                return None

            async def start_monitoring(self) -> None:
                pass

            async def stop_monitoring(self) -> None:
                pass

        # Should not raise
        monitor = TestForkMonitor()
        assert isinstance(monitor, ForkMonitor)

    def test_can_override_monitoring_interval(self) -> None:
        """Concrete implementation can override monitoring interval."""

        class FastForkMonitor(ForkMonitor):
            @property
            def monitoring_interval_seconds(self) -> int:
                return 5  # Override default

            async def check_for_forks(self) -> ForkDetectedPayload | None:
                return None

            async def start_monitoring(self) -> None:
                pass

            async def stop_monitoring(self) -> None:
                pass

        monitor = FastForkMonitor()
        assert monitor.monitoring_interval_seconds == 5
