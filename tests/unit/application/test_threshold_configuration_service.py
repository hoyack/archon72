"""Unit tests for ThresholdConfigurationService (Story 6.4, FR33-FR34).

Tests the threshold configuration service.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.threshold_configuration_service import (
    ThresholdConfigurationService,
)
from src.domain.errors.threshold import (
    ConstitutionalFloorViolationError,
    ThresholdNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError


class TestThresholdConfigurationServiceGetThreshold:
    """Tests for get_threshold method."""

    @pytest.mark.asyncio
    async def test_get_threshold_returns_threshold_with_correct_values(self) -> None:
        """Test get_threshold returns threshold from registry."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        result = await service.get_threshold("cessation_breach_count")

        assert result.threshold_name == "cessation_breach_count"
        assert result.constitutional_floor == 10
        assert result.current_value == 10
        assert result.is_constitutional is True

    @pytest.mark.asyncio
    async def test_get_threshold_raises_for_unknown_threshold(self) -> None:
        """Test get_threshold raises ThresholdNotFoundError for unknown name."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        with pytest.raises(ThresholdNotFoundError) as exc_info:
            await service.get_threshold("nonexistent")

        assert exc_info.value.threshold_name == "nonexistent"

    @pytest.mark.asyncio
    async def test_get_threshold_checks_halt_first(self) -> None:
        """Test get_threshold checks halt state before operation (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        with pytest.raises(SystemHaltedError):
            await service.get_threshold("cessation_breach_count")

        halt_checker.is_halted.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_threshold_with_override(self) -> None:
        """Test get_threshold returns overridden value if repository has override."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        repository = AsyncMock()
        repository.get_threshold_override.return_value = 15

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        result = await service.get_threshold("cessation_breach_count")

        assert result.current_value == 15
        assert result.constitutional_floor == 10  # Floor unchanged
        repository.get_threshold_override.assert_called_once_with("cessation_breach_count")


class TestThresholdConfigurationServiceGetAllThresholds:
    """Tests for get_all_thresholds method."""

    @pytest.mark.asyncio
    async def test_get_all_thresholds_returns_all(self) -> None:
        """Test get_all_thresholds returns all 13 thresholds."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        result = await service.get_all_thresholds()

        assert len(result) == 13
        names = {t.threshold_name for t in result}
        assert "cessation_breach_count" in names
        assert "recovery_waiting_hours" in names
        assert "minimum_keeper_quorum" in names

    @pytest.mark.asyncio
    async def test_get_all_thresholds_checks_halt(self) -> None:
        """Test get_all_thresholds checks halt state (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        with pytest.raises(SystemHaltedError):
            await service.get_all_thresholds()


class TestThresholdConfigurationServiceValidate:
    """Tests for validate_threshold_value method."""

    @pytest.mark.asyncio
    async def test_validate_passes_for_valid_values(self) -> None:
        """Test validate_threshold_value passes for value >= floor."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        result = await service.validate_threshold_value("cessation_breach_count", 15)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_passes_for_exactly_at_floor(self) -> None:
        """Test validate_threshold_value passes for value == floor."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        result = await service.validate_threshold_value("cessation_breach_count", 10)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_raises_for_below_floor(self) -> None:
        """Test validate_threshold_value raises for value < floor (AC2)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        with pytest.raises(ConstitutionalFloorViolationError) as exc_info:
            await service.validate_threshold_value("cessation_breach_count", 5)

        assert "FR33: Constitutional floor violation" in str(exc_info.value)
        assert exc_info.value.attempted_value == 5
        assert exc_info.value.constitutional_floor == 10

    @pytest.mark.asyncio
    async def test_validate_raises_for_unknown_threshold(self) -> None:
        """Test validate_threshold_value raises for unknown threshold."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        with pytest.raises(ThresholdNotFoundError):
            await service.validate_threshold_value("nonexistent", 10)

    @pytest.mark.asyncio
    async def test_validate_checks_halt(self) -> None:
        """Test validate_threshold_value checks halt state (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        with pytest.raises(SystemHaltedError):
            await service.validate_threshold_value("cessation_breach_count", 10)


class TestThresholdConfigurationServiceUpdate:
    """Tests for update_threshold method."""

    @pytest.mark.asyncio
    async def test_update_succeeds_for_valid_values(self) -> None:
        """Test update_threshold succeeds for value >= floor."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        repository = AsyncMock()
        repository.get_threshold_override.return_value = None

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        result = await service.update_threshold(
            name="cessation_breach_count",
            new_value=15,
            updated_by="keeper-001",
        )

        assert result.current_value == 15
        assert result.constitutional_floor == 10
        repository.save_threshold_override.assert_called_once_with(
            "cessation_breach_count", 15
        )

    @pytest.mark.asyncio
    async def test_update_fails_for_below_floor(self) -> None:
        """Test update_threshold raises for value < floor (FR33)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        repository = AsyncMock()
        repository.get_threshold_override.return_value = None

        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        with pytest.raises(ConstitutionalFloorViolationError):
            await service.update_threshold(
                name="cessation_breach_count",
                new_value=5,
                updated_by="keeper-001",
            )

        # Should not have saved
        repository.save_threshold_override.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_writes_event_when_writer_provided(self) -> None:
        """Test update_threshold writes event when EventWriter provided (CT-12)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        repository = AsyncMock()
        repository.get_threshold_override.return_value = None

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

    @pytest.mark.asyncio
    async def test_update_checks_halt(self) -> None:
        """Test update_threshold checks halt state (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        with pytest.raises(SystemHaltedError):
            await service.update_threshold(
                name="cessation_breach_count",
                new_value=15,
                updated_by="keeper-001",
            )

    @pytest.mark.asyncio
    async def test_update_does_not_reset_counters(self) -> None:
        """Test update_threshold has no access to counter state (FR34).

        This test verifies the architectural design: the service has
        no dependency on breach/escalation repositories, so there's
        no code path to reset counters.
        """
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        repository = AsyncMock()
        repository.get_threshold_override.return_value = None

        # No breach repository, no escalation repository - by design
        service = ThresholdConfigurationService(
            halt_checker=halt_checker,
            repository=repository,
        )

        # Update should succeed without touching any counters
        # The fact that service has no counter access IS the FR34 guarantee
        await service.update_threshold(
            name="cessation_breach_count",
            new_value=15,
            updated_by="keeper-001",
        )

        # Only threshold override was saved, no counter operations
        repository.save_threshold_override.assert_called_once()


class TestThresholdConfigurationServiceHaltChecks:
    """Tests for halt check compliance (CT-11)."""

    @pytest.mark.asyncio
    async def test_all_operations_check_halt_first(self) -> None:
        """Test all operations check halt state before proceeding."""
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True

        service = ThresholdConfigurationService(halt_checker=halt_checker)

        # All operations should raise SystemHaltedError
        with pytest.raises(SystemHaltedError):
            await service.get_threshold("test")

        with pytest.raises(SystemHaltedError):
            await service.get_all_thresholds()

        with pytest.raises(SystemHaltedError):
            await service.validate_threshold_value("test", 10)

        with pytest.raises(SystemHaltedError):
            await service.update_threshold("test", 10, "user")

        # is_halted should be called for each operation
        assert halt_checker.is_halted.call_count == 4
