"""Unit tests for witness pool monitoring service (Story 6.6, FR117)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.witness_pool_monitor import (
    MINIMUM_WITNESSES_HIGH_STAKES,
    MINIMUM_WITNESSES_STANDARD,
    WitnessPoolStatus,
)
from src.application.services.witness_pool_monitoring_service import (
    WitnessPoolMonitoringService,
)
from src.domain.errors.witness_anomaly import WitnessPoolDegradedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.witness_anomaly import WitnessPoolDegradedEventPayload


class TestWitnessPoolMonitoringServiceInit:
    """Tests for WitnessPoolMonitoringService initialization."""

    def test_init_without_anomaly_detector(self) -> None:
        """Test initialization without anomaly detector."""
        halt_checker = MagicMock()
        witness_pool = MagicMock()

        service = WitnessPoolMonitoringService(
            halt_checker=halt_checker,
            witness_pool=witness_pool,
        )

        assert service._halt_checker == halt_checker
        assert service._witness_pool == witness_pool
        assert service._anomaly_detector is None
        assert service._degraded_since is None

    def test_init_with_anomaly_detector(self) -> None:
        """Test initialization with anomaly detector."""
        halt_checker = MagicMock()
        witness_pool = MagicMock()
        anomaly_detector = MagicMock()

        service = WitnessPoolMonitoringService(
            halt_checker=halt_checker,
            witness_pool=witness_pool,
            anomaly_detector=anomaly_detector,
        )

        assert service._anomaly_detector == anomaly_detector


class TestCheckPoolHealth:
    """Tests for check_pool_health method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_witness_pool(self) -> AsyncMock:
        """Create mock witness pool."""
        pool = AsyncMock()
        pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(15)
        ]
        return pool

    @pytest.fixture
    def mock_anomaly_detector(self) -> AsyncMock:
        """Create mock anomaly detector."""
        detector = AsyncMock()
        detector.get_excluded_pairs.return_value = set()
        return detector

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.check_pool_health()

        assert "System halted" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_healthy_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test health check with healthy pool."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        status = await service.check_pool_health()

        assert status.available_count == 15
        assert status.is_degraded is False
        assert status.degraded_since is None

    @pytest.mark.asyncio
    async def test_degraded_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test health check with degraded pool (< 12 witnesses)."""
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(8)
        ]

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        status = await service.check_pool_health()

        assert status.available_count == 8
        assert status.is_degraded is True
        assert status.degraded_since is not None

    @pytest.mark.asyncio
    async def test_pool_with_exclusions(
        self,
        mock_halt_checker: AsyncMock,
        mock_witness_pool: AsyncMock,
        mock_anomaly_detector: AsyncMock,
    ) -> None:
        """Test health check accounts for excluded witnesses."""
        # Use simple pair format: "w1:w2" instead of complex IDs with colons
        mock_anomaly_detector.get_excluded_pairs.return_value = {
            "w1:w2",
            "w3:w4",
        }

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
            anomaly_detector=mock_anomaly_detector,
        )

        status = await service.check_pool_health()

        assert status.available_count == 15
        # Exclusion extracts unique witnesses from pairs
        assert len(status.excluded_witnesses) == 4
        assert set(status.excluded_witnesses) == {"w1", "w2", "w3", "w4"}

    @pytest.mark.asyncio
    async def test_tracks_degraded_since(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test tracks when degraded mode started."""
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(8)
        ]

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        status1 = await service.check_pool_health()

        # Second check should have same degraded_since
        status2 = await service.check_pool_health()

        assert status1.degraded_since == status2.degraded_since

    @pytest.mark.asyncio
    async def test_clears_degraded_when_restored(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test clears degraded_since when pool is restored."""
        # Start degraded
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(8)
        ]

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        status1 = await service.check_pool_health()
        assert status1.is_degraded is True

        # Restore pool
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(15)
        ]

        status2 = await service.check_pool_health()

        assert status2.is_degraded is False
        assert status2.degraded_since is None


class TestHandlePoolDegraded:
    """Tests for handle_pool_degraded method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_witness_pool(self) -> AsyncMock:
        """Create mock witness pool."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        status = WitnessPoolStatus(available_count=8, is_degraded=True)

        with pytest.raises(SystemHaltedError):
            await service.handle_pool_degraded(status)

    @pytest.mark.asyncio
    async def test_creates_blocking_payload_for_high_stakes(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test creates blocking payload for high-stakes operations."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        now = datetime.now(timezone.utc)
        status = WitnessPoolStatus(
            available_count=8,
            is_degraded=True,
            degraded_since=now,
        )

        payload = await service.handle_pool_degraded(
            status, operation_type="high_stakes"
        )

        assert isinstance(payload, WitnessPoolDegradedEventPayload)
        assert payload.is_blocking is True
        assert payload.operation_type == "high_stakes"
        assert payload.minimum_required == MINIMUM_WITNESSES_HIGH_STAKES

    @pytest.mark.asyncio
    async def test_creates_non_blocking_payload_for_standard(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test creates non-blocking payload for standard operations."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        now = datetime.now(timezone.utc)
        status = WitnessPoolStatus(
            available_count=8,
            is_degraded=True,
            degraded_since=now,
        )

        payload = await service.handle_pool_degraded(status, operation_type="standard")

        assert payload.is_blocking is False
        assert payload.operation_type == "standard"
        assert payload.minimum_required == MINIMUM_WITNESSES_STANDARD

    @pytest.mark.asyncio
    async def test_includes_exclusion_info_in_reason(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test includes exclusion count in reason when excluded witnesses exist."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        status = WitnessPoolStatus(
            available_count=10,
            excluded_witnesses=("WITNESS:001", "WITNESS:002"),
            is_degraded=True,
        )

        payload = await service.handle_pool_degraded(status)

        assert "excluded" in payload.reason
        assert "2" in payload.reason


class TestCanProceedWithOperation:
    """Tests for can_proceed_with_operation method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_witness_pool(self) -> AsyncMock:
        """Create mock witness pool."""
        pool = AsyncMock()
        pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(15)
        ]
        return pool

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        with pytest.raises(SystemHaltedError):
            await service.can_proceed_with_operation(high_stakes=True)

    @pytest.mark.asyncio
    async def test_allows_high_stakes_with_healthy_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test allows high-stakes with healthy pool."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        can_proceed, reason = await service.can_proceed_with_operation(high_stakes=True)

        assert can_proceed is True
        assert "adequate" in reason.lower()

    @pytest.mark.asyncio
    async def test_blocks_high_stakes_with_degraded_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test blocks high-stakes with degraded pool."""
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(8)
        ]

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        can_proceed, reason = await service.can_proceed_with_operation(high_stakes=True)

        assert can_proceed is False
        assert "FR117" in reason

    @pytest.mark.asyncio
    async def test_allows_standard_with_adequate_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test allows standard operations with adequate pool."""
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(8)
        ]

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        can_proceed, reason = await service.can_proceed_with_operation(
            high_stakes=False
        )

        assert can_proceed is True


class TestIsDegraded:
    """Tests for is_degraded method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_witness_pool(self) -> AsyncMock:
        """Create mock witness pool."""
        pool = AsyncMock()
        pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(15)
        ]
        return pool

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        with pytest.raises(SystemHaltedError):
            await service.is_degraded()

    @pytest.mark.asyncio
    async def test_returns_false_for_healthy_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test returns False for healthy pool."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        result = await service.is_degraded()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_degraded_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test returns True for degraded pool."""
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(8)
        ]

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        result = await service.is_degraded()

        assert result is True


class TestGetDegradedSince:
    """Tests for get_degraded_since method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_witness_pool(self) -> AsyncMock:
        """Create mock witness pool."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_degraded_since()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_degraded(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test returns None when not degraded."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        result = await service.get_degraded_since()

        assert result is None


class TestRequireHealthyPoolForHighStakes:
    """Tests for require_healthy_pool_for_high_stakes method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_witness_pool(self) -> AsyncMock:
        """Create mock witness pool."""
        pool = AsyncMock()
        pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(15)
        ]
        return pool

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        with pytest.raises(SystemHaltedError):
            await service.require_healthy_pool_for_high_stakes()

    @pytest.mark.asyncio
    async def test_succeeds_with_healthy_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test succeeds with healthy pool."""
        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        # Should not raise
        await service.require_healthy_pool_for_high_stakes()

    @pytest.mark.asyncio
    async def test_raises_with_degraded_pool(
        self, mock_halt_checker: AsyncMock, mock_witness_pool: AsyncMock
    ) -> None:
        """Test raises WitnessPoolDegradedError with degraded pool."""
        mock_witness_pool.get_ordered_active_witnesses.return_value = [
            f"WITNESS:{i:03d}" for i in range(8)
        ]

        service = WitnessPoolMonitoringService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
        )

        with pytest.raises(WitnessPoolDegradedError) as exc_info:
            await service.require_healthy_pool_for_high_stakes()

        assert exc_info.value.available == 8
        assert exc_info.value.minimum_required == MINIMUM_WITNESSES_HIGH_STAKES
        assert exc_info.value.operation_type == "high_stakes"


class TestWitnessPoolStatusDataclass:
    """Tests for WitnessPoolStatus dataclass."""

    def test_effective_count_without_exclusions(self) -> None:
        """Test effective count equals available when no exclusions."""
        status = WitnessPoolStatus(available_count=15)

        assert status.effective_count == 15

    def test_effective_count_with_exclusions(self) -> None:
        """Test effective count subtracts exclusions."""
        status = WitnessPoolStatus(
            available_count=15,
            excluded_witnesses=("WITNESS:001", "WITNESS:002", "WITNESS:003"),
        )

        assert status.effective_count == 12

    def test_effective_count_non_negative(self) -> None:
        """Test effective count never goes negative."""
        status = WitnessPoolStatus(
            available_count=5,
            excluded_witnesses=("W1", "W2", "W3", "W4", "W5", "W6", "W7"),
        )

        assert status.effective_count == 0

    def test_can_perform_high_stakes_success(self) -> None:
        """Test can_perform returns True for high-stakes with adequate pool."""
        status = WitnessPoolStatus(available_count=15)

        can_proceed, reason = status.can_perform(high_stakes=True)

        assert can_proceed is True
        assert "adequate" in reason.lower()

    def test_can_perform_high_stakes_failure(self) -> None:
        """Test can_perform returns False for high-stakes with degraded pool."""
        status = WitnessPoolStatus(available_count=8)

        can_proceed, reason = status.can_perform(high_stakes=True)

        assert can_proceed is False
        assert "FR117" in reason

    def test_can_perform_standard_success(self) -> None:
        """Test can_perform returns True for standard with adequate pool."""
        status = WitnessPoolStatus(available_count=8)

        can_proceed, reason = status.can_perform(high_stakes=False)

        assert can_proceed is True

    def test_can_perform_standard_failure(self) -> None:
        """Test can_perform returns False for standard with insufficient pool."""
        status = WitnessPoolStatus(available_count=4)

        can_proceed, reason = status.can_perform(high_stakes=False)

        assert can_proceed is False
        assert "insufficient" in reason.lower()
