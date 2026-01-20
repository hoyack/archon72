"""Unit tests for QueueCapacityStub (Story 1.3, FR-1.4).

Tests for the stub implementation of queue capacity checking.
"""

from __future__ import annotations

from src.infrastructure.stubs.queue_capacity_stub import QueueCapacityStub


class TestQueueCapacityStub:
    """Tests for QueueCapacityStub."""

    class TestFactoryMethods:
        """Tests for factory methods."""

        def test_accepting_factory(self) -> None:
            """accepting() should create stub that accepts submissions."""
            stub = QueueCapacityStub.accepting()
            assert stub._accepting is True
            assert stub._depth == 0
            assert stub._threshold == 10_000

        def test_accepting_factory_with_custom_depth(self) -> None:
            """accepting() should allow custom depth."""
            stub = QueueCapacityStub.accepting(depth=500)
            assert stub._accepting is True
            assert stub._depth == 500

        def test_rejecting_factory(self) -> None:
            """rejecting() should create stub that rejects submissions."""
            stub = QueueCapacityStub.rejecting()
            assert stub._accepting is False
            assert stub._depth == 10_000
            assert stub._retry_after == 60

        def test_rejecting_factory_with_custom_values(self) -> None:
            """rejecting() should allow custom configuration."""
            stub = QueueCapacityStub.rejecting(
                depth=5000,
                threshold=4000,
                retry_after=120,
            )
            assert stub._accepting is False
            assert stub._depth == 5000
            assert stub._threshold == 4000
            assert stub._retry_after == 120

    class TestIsAcceptingSubmissions:
        """Tests for is_accepting_submissions method."""

        async def test_returns_true_when_accepting(self) -> None:
            """Should return True when configured to accept."""
            stub = QueueCapacityStub.accepting()
            assert await stub.is_accepting_submissions() is True

        async def test_returns_false_when_rejecting(self) -> None:
            """Should return False when configured to reject."""
            stub = QueueCapacityStub.rejecting()
            assert await stub.is_accepting_submissions() is False

        async def test_set_accepting_changes_state(self) -> None:
            """set_accepting should change the accepting state."""
            stub = QueueCapacityStub.accepting()
            stub.set_accepting(False)
            assert await stub.is_accepting_submissions() is False

            stub.set_accepting(True)
            assert await stub.is_accepting_submissions() is True

    class TestGetQueueDepth:
        """Tests for get_queue_depth method."""

        async def test_returns_configured_depth(self) -> None:
            """Should return the configured depth."""
            stub = QueueCapacityStub.accepting(depth=123)
            assert await stub.get_queue_depth() == 123

        async def test_set_depth_changes_value(self) -> None:
            """set_depth should update the returned depth."""
            stub = QueueCapacityStub.accepting()
            stub.set_depth(999)
            assert await stub.get_queue_depth() == 999

    class TestGetThreshold:
        """Tests for get_threshold method."""

        def test_returns_configured_threshold(self) -> None:
            """Should return the configured threshold."""
            stub = QueueCapacityStub(threshold=5000)
            assert stub.get_threshold() == 5000

        def test_default_threshold(self) -> None:
            """Default threshold should be 10,000."""
            stub = QueueCapacityStub()
            assert stub.get_threshold() == 10_000

    class TestGetRetryAfterSeconds:
        """Tests for get_retry_after_seconds method."""

        def test_returns_configured_retry_after(self) -> None:
            """Should return the configured Retry-After value."""
            stub = QueueCapacityStub(retry_after=90)
            assert stub.get_retry_after_seconds() == 90

        def test_default_retry_after(self) -> None:
            """Default Retry-After should be 60."""
            stub = QueueCapacityStub()
            assert stub.get_retry_after_seconds() == 60

    class TestProtocolCompliance:
        """Tests for QueueCapacityPort protocol compliance."""

        def test_implements_protocol(self) -> None:
            """Stub should implement QueueCapacityPort protocol."""
            from src.application.ports.queue_capacity import QueueCapacityPort

            stub = QueueCapacityStub()
            assert isinstance(stub, QueueCapacityPort)

        async def test_all_protocol_methods_work(self) -> None:
            """All protocol methods should work correctly."""
            stub = QueueCapacityStub.accepting(depth=50)

            # All methods should work
            accepting = await stub.is_accepting_submissions()
            depth = await stub.get_queue_depth()
            threshold = stub.get_threshold()
            retry_after = stub.get_retry_after_seconds()

            assert accepting is True
            assert depth == 50
            assert threshold == 10_000
            assert retry_after == 60


class TestDirectInitialization:
    """Tests for direct initialization."""

    def test_direct_init_defaults(self) -> None:
        """Direct initialization should use sensible defaults."""
        stub = QueueCapacityStub()
        assert stub._accepting is True
        assert stub._depth == 0
        assert stub._threshold == 10_000
        assert stub._retry_after == 60

    def test_direct_init_with_all_params(self) -> None:
        """Direct initialization should accept all parameters."""
        stub = QueueCapacityStub(
            accepting=False,
            depth=500,
            threshold=1000,
            retry_after=30,
        )
        assert stub._accepting is False
        assert stub._depth == 500
        assert stub._threshold == 1000
        assert stub._retry_after == 30
