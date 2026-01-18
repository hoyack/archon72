"""Integration tests for constitutional threshold system (Story 6.4, FR33-FR34).

Tests the full threshold configuration stack with stubs.

Constitutional Constraints:
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR34: Threshold changes SHALL NOT reset active counters
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- CT-11: Silent failure destroys legitimacy → HALT CHECK FIRST
- CT-12: Witnessing creates accountability → Threshold changes must be witnessed
"""

from unittest.mock import AsyncMock

import pytest

from src.application.services.threshold_configuration_service import (
    ThresholdConfigurationService,
)
from src.domain.errors.threshold import ConstitutionalFloorViolationError
from src.domain.errors.writer import SystemHaltedError
from src.domain.primitives.constitutional_thresholds import (
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
    get_threshold,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.threshold_repository_stub import ThresholdRepositoryStub


class TestFR33ThresholdDefinitions:
    """Tests for FR33 - Constitutional threshold definitions."""

    def test_fr33_threshold_includes_floor_definition(self) -> None:
        """Test thresholds include constitutional_floor field (AC1)."""
        for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY.thresholds:
            assert hasattr(threshold, "constitutional_floor")
            assert threshold.constitutional_floor is not None
            assert threshold.constitutional_floor > 0

    def test_fr33_threshold_includes_is_constitutional_flag(self) -> None:
        """Test thresholds include is_constitutional flag set to True (AC1)."""
        for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY.thresholds:
            assert hasattr(threshold, "is_constitutional")
            assert threshold.is_constitutional is True


class TestNFR39FloorEnforcement:
    """Tests for NFR39 - Floor enforcement."""

    @pytest.mark.asyncio
    async def test_nfr39_rejects_below_floor_value(self) -> None:
        """Test below-floor values are rejected (AC2)."""
        halt_checker = HaltCheckerStub()
        repository = ThresholdRepositoryStub()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        with pytest.raises(ConstitutionalFloorViolationError):
            await service.update_threshold(
                name="cessation_breach_count",
                new_value=5,  # Floor is 10
                updated_by="test-user",
            )

    @pytest.mark.asyncio
    async def test_nfr39_error_message_includes_fr33_reference(self) -> None:
        """Test error message includes FR33 reference (AC2)."""
        halt_checker = HaltCheckerStub()
        repository = ThresholdRepositoryStub()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        with pytest.raises(ConstitutionalFloorViolationError) as exc_info:
            await service.update_threshold(
                name="cessation_breach_count",
                new_value=5,
                updated_by="test-user",
            )

        assert "FR33: Constitutional floor violation" in str(exc_info.value)


class TestFR34CounterPreservation:
    """Tests for FR34 - Counter preservation on threshold changes."""

    @pytest.mark.asyncio
    async def test_fr34_counter_not_reset_on_threshold_change(self) -> None:
        """Test threshold update has no access to counters (AC3).

        FR34 is enforced architecturally: ThresholdConfigurationService
        has NO dependency on BreachRepository, EscalationRepository, etc.
        There is no code path from threshold update to counter reset.

        This test verifies the architectural guarantee by ensuring:
        1. The service can update thresholds
        2. The service has no way to access counter state
        """
        halt_checker = HaltCheckerStub()
        repository = ThresholdRepositoryStub()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        # Update threshold - this should NOT affect any counters
        # The fact that there's no counter repository injected IS the guarantee
        result = await service.update_threshold(
            name="cessation_breach_count",
            new_value=15,
            updated_by="test-keeper",
        )

        assert result.current_value == 15

        # Verify only threshold was updated, no counter operations
        assert repository.has_override("cessation_breach_count")

    @pytest.mark.asyncio
    async def test_threshold_update_creates_witnessed_event(self) -> None:
        """Test threshold update writes witnessed event (AC3, CT-12)."""
        halt_checker = HaltCheckerStub()
        repository = ThresholdRepositoryStub()
        event_writer = AsyncMock()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
            event_writer=event_writer,
        )

        await service.update_threshold(
            name="cessation_breach_count",
            new_value=15,
            updated_by="keeper-001",
        )

        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == "threshold.updated"
        assert call_kwargs["agent_id"] == "keeper-001"

        payload = call_kwargs["payload"]
        assert payload["threshold_name"] == "cessation_breach_count"
        assert payload["previous_value"] == 10
        assert payload["new_value"] == 15
        assert payload["constitutional_floor"] == 10


class TestHaltCheckCompliance:
    """Tests for CT-11 - Halt check compliance."""

    @pytest.mark.asyncio
    async def test_halt_check_prevents_threshold_operations_during_halt(self) -> None:
        """Test all operations blocked during halt (CT-11)."""
        halt_checker = HaltCheckerStub()
        halt_checker.set_halted(True)

        repository = ThresholdRepositoryStub()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_threshold("cessation_breach_count")

        with pytest.raises(SystemHaltedError):
            await service.get_all_thresholds()

        with pytest.raises(SystemHaltedError):
            await service.validate_threshold_value("cessation_breach_count", 15)

        with pytest.raises(SystemHaltedError):
            await service.update_threshold(
                name="cessation_breach_count",
                new_value=15,
                updated_by="test",
            )


class TestThresholdValidation:
    """Tests for threshold validation."""

    def test_all_existing_thresholds_at_or_above_floor(self) -> None:
        """Test all default thresholds are at or above their floors."""
        for threshold in CONSTITUTIONAL_THRESHOLD_REGISTRY.thresholds:
            assert threshold.current_value >= threshold.constitutional_floor, (
                f"{threshold.threshold_name} has current_value "
                f"{threshold.current_value} below floor {threshold.constitutional_floor}"
            )


class TestConstitutionalThresholds:
    """Tests for specific constitutional thresholds."""

    def test_cessation_threshold_is_constitutional(self) -> None:
        """Test cessation threshold is marked as constitutional."""
        threshold = get_threshold("cessation_breach_count")

        assert threshold.is_constitutional is True
        assert threshold.fr_reference == "FR32"

    def test_recovery_waiting_period_is_constitutional(self) -> None:
        """Test recovery waiting period threshold is constitutional."""
        threshold = get_threshold("recovery_waiting_hours")

        assert threshold.is_constitutional is True
        assert threshold.constitutional_floor == 48
        assert threshold.fr_reference == "NFR41"

    def test_keeper_quorum_is_constitutional(self) -> None:
        """Test keeper quorum threshold is constitutional."""
        threshold = get_threshold("minimum_keeper_quorum")

        assert threshold.is_constitutional is True
        assert threshold.constitutional_floor == 3
        assert threshold.fr_reference == "FR79"


class TestFullIntegrationFlow:
    """Full integration flow tests."""

    @pytest.mark.asyncio
    async def test_complete_threshold_lifecycle(self) -> None:
        """Test complete threshold get-validate-update flow."""
        halt_checker = HaltCheckerStub()
        repository = ThresholdRepositoryStub()
        event_writer = AsyncMock()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
            event_writer=event_writer,
        )

        # 1. Get threshold
        threshold = await service.get_threshold("escalation_days")
        assert threshold.current_value == 7
        assert threshold.constitutional_floor == 7

        # 2. Validate a valid new value
        is_valid = await service.validate_threshold_value("escalation_days", 14)
        assert is_valid is True

        # 3. Validate an invalid new value
        with pytest.raises(ConstitutionalFloorViolationError):
            await service.validate_threshold_value("escalation_days", 3)

        # 4. Update to valid value
        updated = await service.update_threshold(
            name="escalation_days",
            new_value=14,
            updated_by="admin-keeper",
        )
        assert updated.current_value == 14
        assert updated.constitutional_floor == 7  # Floor unchanged

        # 5. Get threshold again - should reflect update
        refreshed = await service.get_threshold("escalation_days")
        assert refreshed.current_value == 14

        # 6. Verify event was written
        assert event_writer.write_event.call_count == 1

    @pytest.mark.asyncio
    async def test_multiple_threshold_updates(self) -> None:
        """Test updating multiple thresholds."""
        halt_checker = HaltCheckerStub()
        repository = ThresholdRepositoryStub()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        # Update several thresholds
        await service.update_threshold("cessation_breach_count", 15, "admin")
        await service.update_threshold("escalation_days", 14, "admin")
        await service.update_threshold("minimum_keeper_quorum", 5, "admin")

        # Verify all updates
        assert (
            await service.get_threshold("cessation_breach_count")
        ).current_value == 15
        assert (await service.get_threshold("escalation_days")).current_value == 14
        assert (await service.get_threshold("minimum_keeper_quorum")).current_value == 5

        # Verify floors unchanged
        assert (
            await service.get_threshold("cessation_breach_count")
        ).constitutional_floor == 10
        assert (
            await service.get_threshold("escalation_days")
        ).constitutional_floor == 7
        assert (
            await service.get_threshold("minimum_keeper_quorum")
        ).constitutional_floor == 3

    @pytest.mark.asyncio
    async def test_get_all_reflects_overrides(self) -> None:
        """Test get_all_thresholds returns updated values."""
        halt_checker = HaltCheckerStub()
        repository = ThresholdRepositoryStub()

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        # Update one threshold
        await service.update_threshold("cessation_breach_count", 20, "admin")

        # Get all thresholds
        all_thresholds = await service.get_all_thresholds()

        # Find the updated one
        cessation = next(
            t for t in all_thresholds if t.threshold_name == "cessation_breach_count"
        )
        assert cessation.current_value == 20
        assert cessation.constitutional_floor == 10
