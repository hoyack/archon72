"""Integration tests for hash verification (Story 6.8, FR125).

Tests HashVerificationService with infrastructure stubs.

Constitutional Constraints:
- FR125: Witness selection algorithm SHALL be published; statistical
         deviation from expected distribution flagged (Selection Audit)
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-13: Integrity outranks availability -> Hash mismatch MUST halt
"""

from __future__ import annotations

import pytest

from src.application.services.hash_verification_service import (
    HashVerificationService,
)
from src.domain.errors.writer import SystemHaltedError
from src.infrastructure.stubs.event_store_stub import EventStoreStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def halt_trigger() -> HaltTriggerStub:
    """Create halt trigger stub."""
    return HaltTriggerStub()


@pytest.fixture
def event_store() -> EventStoreStub:
    """Create event store stub."""
    return EventStoreStub()


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub,
    halt_trigger: HaltTriggerStub,
    event_store: EventStoreStub,
) -> HashVerificationService:
    """Create hash verification service with stubs."""
    return HashVerificationService(
        halt_checker=halt_checker,
        halt_trigger=halt_trigger,
        event_store=event_store,
    )


class TestHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_verify_event_hash_halted(
        self,
        service: HashVerificationService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that verify_event_hash raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.verify_event_hash("event-123")

    @pytest.mark.asyncio
    async def test_run_full_scan_halted(
        self,
        service: HashVerificationService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that run_full_scan raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.run_full_scan()

    @pytest.mark.asyncio
    async def test_verify_chain_link_halted(
        self,
        service: HashVerificationService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that verify_hash_chain_link raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.verify_hash_chain_link(1)


class TestGetLastScanStatus:
    """Tests for scan status reporting."""

    @pytest.mark.asyncio
    async def test_initial_status(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test initial status before any scans."""
        status = await service.get_last_scan_status()

        assert status.last_scan_id is None
        assert status.last_scan_passed is None
        assert status.events_verified_total == 0
        assert status.is_healthy  # No scans yet is healthy

    @pytest.mark.asyncio
    async def test_status_after_scan(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test status is updated after scan."""
        # Run empty scan (will pass)
        await service.run_full_scan()

        status = await service.get_last_scan_status()
        assert status.last_scan_id is not None
        assert status.last_scan_passed is True
        assert status.is_healthy


class TestScheduleContinuousVerification:
    """Tests for continuous verification scheduling."""

    @pytest.mark.asyncio
    async def test_sets_interval(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test that interval can be configured."""
        await service.schedule_continuous_verification(1800)
        interval = await service.get_verification_interval()
        assert interval == 1800

    @pytest.mark.asyncio
    async def test_rejects_invalid_interval(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test that invalid interval is rejected."""
        with pytest.raises(ValueError):
            await service.schedule_continuous_verification(0)

        with pytest.raises(ValueError):
            await service.schedule_continuous_verification(-100)


class TestIntegrityHaltTrigger:
    """Tests for CT-13: Integrity outranks availability."""

    @pytest.mark.asyncio
    async def test_scan_empty_store_passes(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test that empty store passes verification."""
        result = await service.run_full_scan()
        assert result.passed
        assert result.events_scanned == 0


class TestVerificationInterval:
    """Tests for verification interval configuration."""

    @pytest.mark.asyncio
    async def test_default_interval(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test default verification interval is 1 hour."""
        interval = await service.get_verification_interval()
        assert interval == 3600  # Default 1 hour


class TestStatusHealthCheck:
    """Tests for health status determination."""

    @pytest.mark.asyncio
    async def test_healthy_before_scans(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test that system is healthy before any scans."""
        status = await service.get_last_scan_status()
        assert status.is_healthy

    @pytest.mark.asyncio
    async def test_healthy_after_passed_scan(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test that system is healthy after passed scan."""
        await service.run_full_scan()
        status = await service.get_last_scan_status()
        assert status.is_healthy


class TestRunFullScan:
    """Tests for full chain verification scans."""

    @pytest.mark.asyncio
    async def test_scan_updates_state(
        self,
        service: HashVerificationService,
    ) -> None:
        """Test that scan updates internal state."""
        result = await service.run_full_scan()

        assert result.scan_id is not None
        assert result.completed_at is not None
        assert result.duration_seconds >= 0.0

        status = await service.get_last_scan_status()
        assert status.last_scan_id == result.scan_id


class TestIntegrationWithEventStore:
    """Tests for integration with event store."""

    @pytest.mark.asyncio
    async def test_empty_store_passes(
        self,
        service: HashVerificationService,
        event_store: EventStoreStub,
    ) -> None:
        """Test that empty event store passes verification."""
        result = await service.run_full_scan()
        assert result.passed
        assert result.events_scanned == 0
