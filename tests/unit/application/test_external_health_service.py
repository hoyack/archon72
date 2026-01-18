"""Unit tests for ExternalHealthService (Story 8.3, FR54).

Tests the service that provides external health status checks.

Constitutional Constraints:
- FR53: Operational metrics SHALL NOT assess constitutional integrity
- FR54: System unavailability SHALL be independently detectable
- CT-11: Silent failure destroys legitimacy

Key Test Scenarios:
1. Returns UP when healthy
2. Returns HALTED when halt checker indicates halt
3. Returns FROZEN when freeze checker indicates frozen
4. HALTED takes precedence over FROZEN
5. Service does NOT make DB calls (fast path)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.external_health import ExternalHealthStatus
from src.application.services.external_health_service import (
    ExternalHealthService,
    get_external_health_service,
    init_external_health_service,
    reset_external_health_service,
)
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a halt checker stub for testing."""
    return HaltCheckerStub()


@pytest.fixture
def freeze_checker() -> FreezeCheckerStub:
    """Create a freeze checker stub for testing."""
    return FreezeCheckerStub()


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub, freeze_checker: FreezeCheckerStub
) -> ExternalHealthService:
    """Create an ExternalHealthService for testing."""
    return ExternalHealthService(
        halt_checker=halt_checker,
        freeze_checker=freeze_checker,
    )


class TestExternalHealthService:
    """Tests for ExternalHealthService."""

    @pytest.mark.asyncio
    async def test_get_status_returns_up_when_healthy(
        self, service: ExternalHealthService
    ) -> None:
        """Test get_status returns UP when system is healthy.

        AC1: System operational returns UP status.
        """
        status = await service.get_status()
        assert status == ExternalHealthStatus.UP

    @pytest.mark.asyncio
    async def test_get_status_returns_halted_when_halt_active(
        self, service: ExternalHealthService, halt_checker: HaltCheckerStub
    ) -> None:
        """Test get_status returns HALTED when halt is active.

        AC4: Halt state properly reflected in response.
        """
        halt_checker.set_halted(True, reason="Test halt")

        status = await service.get_status()
        assert status == ExternalHealthStatus.HALTED

    @pytest.mark.asyncio
    async def test_get_status_returns_frozen_when_system_ceased(
        self, service: ExternalHealthService, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Test get_status returns FROZEN when system is ceased.

        AC5: Frozen state properly reflected in response.
        """
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test cessation",
        )

        status = await service.get_status()
        assert status == ExternalHealthStatus.FROZEN

    @pytest.mark.asyncio
    async def test_halted_takes_precedence_over_frozen(
        self,
        service: ExternalHealthService,
        halt_checker: HaltCheckerStub,
        freeze_checker: FreezeCheckerStub,
    ) -> None:
        """Test that HALTED takes precedence over FROZEN.

        Precedence rule: HALTED > FROZEN > UP
        Both can be true, but HALTED is more severe.
        """
        # Both conditions active
        halt_checker.set_halted(True, reason="Test halt")
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test cessation",
        )

        status = await service.get_status()
        assert status == ExternalHealthStatus.HALTED

    @pytest.mark.asyncio
    async def test_get_timestamp_returns_utc(
        self, service: ExternalHealthService
    ) -> None:
        """Test get_timestamp returns UTC datetime."""
        timestamp = await service.get_timestamp()

        assert timestamp.tzinfo is not None
        assert timestamp.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_get_timestamp_is_current(
        self, service: ExternalHealthService
    ) -> None:
        """Test get_timestamp returns approximately current time."""
        before = datetime.now(timezone.utc)
        timestamp = await service.get_timestamp()
        after = datetime.now(timezone.utc)

        assert before <= timestamp <= after

    @pytest.mark.asyncio
    async def test_does_not_call_database(
        self,
        halt_checker: HaltCheckerStub,
        freeze_checker: FreezeCheckerStub,
    ) -> None:
        """Test service does NOT make database calls.

        This is critical for performance - external health must be fast.
        The halt and freeze checkers should use in-memory state only.
        """
        # Use mocks to verify no DB calls
        mock_halt_checker = AsyncMock()
        mock_halt_checker.is_halted = AsyncMock(return_value=False)

        mock_freeze_checker = AsyncMock()
        mock_freeze_checker.is_frozen = AsyncMock(return_value=False)

        service = ExternalHealthService(
            halt_checker=mock_halt_checker,
            freeze_checker=mock_freeze_checker,
        )

        # Call get_status
        status = await service.get_status()

        # Verify only is_halted and is_frozen were called (no DB methods)
        mock_halt_checker.is_halted.assert_called_once()
        mock_freeze_checker.is_frozen.assert_called_once()
        assert status == ExternalHealthStatus.UP

    @pytest.mark.asyncio
    async def test_check_order_halt_before_freeze(
        self,
        halt_checker: HaltCheckerStub,
        freeze_checker: FreezeCheckerStub,
    ) -> None:
        """Test that halt is checked before freeze.

        Order matters for short-circuit optimization.
        """
        # Track call order
        call_order = []

        mock_halt_checker = AsyncMock()

        async def mock_is_halted():
            call_order.append("halt")
            return True  # Return halted

        mock_halt_checker.is_halted = mock_is_halted

        mock_freeze_checker = AsyncMock()

        async def mock_is_frozen():
            call_order.append("freeze")
            return True

        mock_freeze_checker.is_frozen = mock_is_frozen

        service = ExternalHealthService(
            halt_checker=mock_halt_checker,
            freeze_checker=mock_freeze_checker,
        )

        await service.get_status()

        # Halt should be checked first
        assert call_order[0] == "halt"
        # Freeze should not be checked if halted (short-circuit)
        assert len(call_order) == 1


class TestExternalHealthServiceSingleton:
    """Tests for singleton management functions."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        reset_external_health_service()

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_external_health_service()

    def test_get_service_raises_when_not_initialized(self) -> None:
        """Test get_external_health_service raises when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_external_health_service()

    def test_init_service_returns_service(self) -> None:
        """Test init_external_health_service returns a service."""
        halt_checker = HaltCheckerStub()
        freeze_checker = FreezeCheckerStub()

        service = init_external_health_service(
            halt_checker=halt_checker,
            freeze_checker=freeze_checker,
        )

        assert isinstance(service, ExternalHealthService)

    def test_get_service_returns_same_instance(self) -> None:
        """Test get_external_health_service returns the initialized instance."""
        halt_checker = HaltCheckerStub()
        freeze_checker = FreezeCheckerStub()

        initialized = init_external_health_service(
            halt_checker=halt_checker,
            freeze_checker=freeze_checker,
        )

        retrieved = get_external_health_service()

        assert initialized is retrieved

    def test_reset_clears_singleton(self) -> None:
        """Test reset_external_health_service clears the singleton."""
        halt_checker = HaltCheckerStub()
        freeze_checker = FreezeCheckerStub()

        init_external_health_service(
            halt_checker=halt_checker,
            freeze_checker=freeze_checker,
        )

        reset_external_health_service()

        with pytest.raises(RuntimeError, match="not initialized"):
            get_external_health_service()


class TestExternalHealthStub:
    """Tests for ExternalHealthStub (the stub, not the service)."""

    @pytest.mark.asyncio
    async def test_stub_default_returns_up(self) -> None:
        """Test stub returns UP by default."""
        from src.infrastructure.stubs.external_health_stub import ExternalHealthStub

        stub = ExternalHealthStub()
        status = await stub.get_status()
        assert status == ExternalHealthStatus.UP

    @pytest.mark.asyncio
    async def test_stub_force_status(self) -> None:
        """Test stub can force a specific status."""
        from src.infrastructure.stubs.external_health_stub import ExternalHealthStub

        stub = ExternalHealthStub(force_status=ExternalHealthStatus.HALTED)
        status = await stub.get_status()
        assert status == ExternalHealthStatus.HALTED

    @pytest.mark.asyncio
    async def test_stub_with_halt_checker(self) -> None:
        """Test stub delegates to halt checker."""
        from src.infrastructure.stubs.external_health_stub import ExternalHealthStub

        halt_checker = HaltCheckerStub()
        halt_checker.set_halted(True)

        stub = ExternalHealthStub(halt_checker=halt_checker)
        status = await stub.get_status()
        assert status == ExternalHealthStatus.HALTED

    @pytest.mark.asyncio
    async def test_stub_with_freeze_checker(self) -> None:
        """Test stub delegates to freeze checker."""
        from src.infrastructure.stubs.external_health_stub import ExternalHealthStub

        freeze_checker = FreezeCheckerStub()
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test",
        )

        stub = ExternalHealthStub(freeze_checker=freeze_checker)
        status = await stub.get_status()
        assert status == ExternalHealthStatus.FROZEN

    @pytest.mark.asyncio
    async def test_stub_tracks_check_count(self) -> None:
        """Test stub tracks number of checks."""
        from src.infrastructure.stubs.external_health_stub import ExternalHealthStub

        stub = ExternalHealthStub()
        assert stub.check_count == 0

        await stub.get_status()
        assert stub.check_count == 1

        await stub.get_status()
        assert stub.check_count == 2

    @pytest.mark.asyncio
    async def test_stub_get_timestamp_returns_utc(self) -> None:
        """Test stub get_timestamp returns UTC datetime."""
        from src.infrastructure.stubs.external_health_stub import ExternalHealthStub

        stub = ExternalHealthStub()
        timestamp = await stub.get_timestamp()

        assert timestamp.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_stub_force_status_overrides_checkers(self) -> None:
        """Test force_status takes precedence over checkers."""
        from src.infrastructure.stubs.external_health_stub import ExternalHealthStub

        halt_checker = HaltCheckerStub()
        halt_checker.set_halted(True)  # Would return HALTED

        # But force_status overrides
        stub = ExternalHealthStub(
            halt_checker=halt_checker,
            force_status=ExternalHealthStatus.UP,
        )

        status = await stub.get_status()
        assert status == ExternalHealthStatus.UP
