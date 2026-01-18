"""Unit tests for EpochManager service.

Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion

Tests cover:
- Epoch boundary detection
- Epoch ID computation
- Epoch sequence range calculation
- Config management
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.governance.merkle_tree_port import EpochConfig, EpochInfo
from src.application.services.governance.epoch_manager import EpochManagerService

if TYPE_CHECKING:
    pass


@pytest.fixture
def mock_time_authority() -> MagicMock:
    """Create a mock TimeAuthority."""
    time_authority = MagicMock()
    time_authority.now.return_value = datetime(
        2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc
    )
    return time_authority


@pytest.fixture
def mock_ledger_port() -> AsyncMock:
    """Create a mock GovernanceLedgerPort."""
    return AsyncMock()


@pytest.fixture
def epoch_manager(
    mock_ledger_port: AsyncMock,
    mock_time_authority: MagicMock,
) -> EpochManagerService:
    """Create an EpochManagerService for testing."""
    return EpochManagerService(
        ledger_port=mock_ledger_port,
        time_authority=mock_time_authority,
        config=EpochConfig(events_per_epoch=100),
    )


class TestEpochIdComputation:
    """Tests for epoch ID computation."""

    def test_sequence_1_is_epoch_0(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 1 belongs to epoch 0."""
        assert epoch_manager._compute_epoch_id(1) == 0

    def test_sequence_100_is_epoch_0(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 100 (last of first epoch) belongs to epoch 0."""
        assert epoch_manager._compute_epoch_id(100) == 0

    def test_sequence_101_is_epoch_1(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 101 (first of second epoch) belongs to epoch 1."""
        assert epoch_manager._compute_epoch_id(101) == 1

    def test_sequence_200_is_epoch_1(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 200 belongs to epoch 1."""
        assert epoch_manager._compute_epoch_id(200) == 1

    def test_sequence_201_is_epoch_2(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 201 belongs to epoch 2."""
        assert epoch_manager._compute_epoch_id(201) == 2


class TestEpochSequenceRange:
    """Tests for epoch sequence range calculation."""

    def test_epoch_0_range(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Epoch 0 covers sequences 1-100."""
        start, end = epoch_manager._get_epoch_sequence_range(0)
        assert start == 1
        assert end == 100

    def test_epoch_1_range(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Epoch 1 covers sequences 101-200."""
        start, end = epoch_manager._get_epoch_sequence_range(1)
        assert start == 101
        assert end == 200

    def test_epoch_5_range(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Epoch 5 covers sequences 501-600."""
        start, end = epoch_manager._get_epoch_sequence_range(5)
        assert start == 501
        assert end == 600


class TestEpochBoundaryDetection:
    """Tests for check_epoch_boundary."""

    @pytest.mark.asyncio
    async def test_sequence_100_triggers_boundary(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 100 triggers epoch 0 boundary."""
        assert await epoch_manager.check_epoch_boundary(100)

    @pytest.mark.asyncio
    async def test_sequence_99_no_boundary(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 99 does not trigger boundary."""
        assert not await epoch_manager.check_epoch_boundary(99)

    @pytest.mark.asyncio
    async def test_sequence_101_no_boundary(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 101 does not trigger boundary."""
        assert not await epoch_manager.check_epoch_boundary(101)

    @pytest.mark.asyncio
    async def test_sequence_200_triggers_boundary(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Sequence 200 triggers epoch 1 boundary."""
        assert await epoch_manager.check_epoch_boundary(200)

    @pytest.mark.asyncio
    async def test_already_built_epoch_no_boundary(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """Already-built epoch does not trigger boundary again."""
        # Mark epoch 0 as built
        epoch_manager._built_epochs[0] = EpochInfo(
            epoch_id=0,
            root_hash="blake3:test",
            algorithm="blake3",
            start_sequence=1,
            end_sequence=100,
            event_count=100,
            created_at=datetime.now(timezone.utc),
        )

        # Should not trigger again
        assert not await epoch_manager.check_epoch_boundary(100)

    @pytest.mark.asyncio
    async def test_zero_events_per_epoch_no_boundary(
        self,
        mock_ledger_port: AsyncMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Zero events_per_epoch means no boundaries."""
        manager = EpochManagerService(
            ledger_port=mock_ledger_port,
            time_authority=mock_time_authority,
            config=EpochConfig(events_per_epoch=0),
        )
        assert not await manager.check_epoch_boundary(100)


class TestConfigManagement:
    """Tests for config get/update."""

    def test_get_config(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """get_config returns current config."""
        config = epoch_manager.get_config()
        assert config.events_per_epoch == 100
        assert config.time_based is False

    def test_update_config(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """update_config updates the config."""
        new_config = EpochConfig(events_per_epoch=500, time_based=True)
        epoch_manager.update_config(new_config)

        config = epoch_manager.get_config()
        assert config.events_per_epoch == 500
        assert config.time_based is True


class TestEpochInfo:
    """Tests for epoch info retrieval."""

    def test_get_epoch_info_not_built(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """get_epoch_info returns None for unbuilt epoch."""
        assert epoch_manager.get_epoch_info(0) is None

    def test_get_epoch_info_built(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """get_epoch_info returns info for built epoch."""
        info = EpochInfo(
            epoch_id=0,
            root_hash="blake3:test",
            algorithm="blake3",
            start_sequence=1,
            end_sequence=100,
            event_count=100,
            created_at=datetime.now(timezone.utc),
        )
        epoch_manager._built_epochs[0] = info

        result = epoch_manager.get_epoch_info(0)
        assert result == info

    def test_list_epochs_empty(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """list_epochs returns empty for no epochs."""
        assert epoch_manager.list_epochs() == []

    def test_list_epochs_ordered(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """list_epochs returns epochs in order."""
        epoch_manager._built_epochs[2] = EpochInfo(
            epoch_id=2,
            root_hash="blake3:test2",
            algorithm="blake3",
            start_sequence=201,
            end_sequence=300,
            event_count=100,
            created_at=datetime.now(timezone.utc),
        )
        epoch_manager._built_epochs[0] = EpochInfo(
            epoch_id=0,
            root_hash="blake3:test0",
            algorithm="blake3",
            start_sequence=1,
            end_sequence=100,
            event_count=100,
            created_at=datetime.now(timezone.utc),
        )

        epochs = epoch_manager.list_epochs()
        assert len(epochs) == 2
        assert epochs[0].epoch_id == 0
        assert epochs[1].epoch_id == 2

    def test_get_latest_epoch_none(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """get_latest_epoch returns None for no epochs."""
        assert epoch_manager.get_latest_epoch() is None

    def test_get_latest_epoch(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """get_latest_epoch returns highest epoch."""
        epoch_manager._built_epochs[0] = EpochInfo(
            epoch_id=0,
            root_hash="blake3:test0",
            algorithm="blake3",
            start_sequence=1,
            end_sequence=100,
            event_count=100,
            created_at=datetime.now(timezone.utc),
        )
        epoch_manager._built_epochs[3] = EpochInfo(
            epoch_id=3,
            root_hash="blake3:test3",
            algorithm="blake3",
            start_sequence=301,
            end_sequence=400,
            event_count=100,
            created_at=datetime.now(timezone.utc),
        )

        latest = epoch_manager.get_latest_epoch()
        assert latest is not None
        assert latest.epoch_id == 3

    def test_get_epoch_for_sequence(
        self,
        epoch_manager: EpochManagerService,
    ) -> None:
        """get_epoch_for_sequence returns correct epoch."""
        assert epoch_manager.get_epoch_for_sequence(1) == 0
        assert epoch_manager.get_epoch_for_sequence(50) == 0
        assert epoch_manager.get_epoch_for_sequence(100) == 0
        assert epoch_manager.get_epoch_for_sequence(101) == 1
        assert epoch_manager.get_epoch_for_sequence(150) == 1


class TestEpochConfigDataclass:
    """Tests for EpochConfig dataclass."""

    def test_default_values(self) -> None:
        """EpochConfig has correct defaults."""
        config = EpochConfig()
        assert config.events_per_epoch == 1000
        assert config.time_based is False
        assert config.epoch_duration_seconds == 3600

    def test_custom_values(self) -> None:
        """EpochConfig accepts custom values."""
        config = EpochConfig(
            events_per_epoch=500,
            time_based=True,
            epoch_duration_seconds=7200,
        )
        assert config.events_per_epoch == 500
        assert config.time_based is True
        assert config.epoch_duration_seconds == 7200


class TestEpochInfoDataclass:
    """Tests for EpochInfo dataclass."""

    def test_epoch_info_creation(self) -> None:
        """EpochInfo is created correctly."""
        now = datetime.now(timezone.utc)
        event_id = uuid4()

        info = EpochInfo(
            epoch_id=5,
            root_hash="blake3:abc123",
            algorithm="blake3",
            start_sequence=501,
            end_sequence=600,
            event_count=100,
            created_at=now,
            root_event_id=event_id,
        )

        assert info.epoch_id == 5
        assert info.root_hash == "blake3:abc123"
        assert info.algorithm == "blake3"
        assert info.start_sequence == 501
        assert info.end_sequence == 600
        assert info.event_count == 100
        assert info.created_at == now
        assert info.root_event_id == event_id

    def test_epoch_info_frozen(self) -> None:
        """EpochInfo is immutable (frozen)."""
        info = EpochInfo(
            epoch_id=0,
            root_hash="blake3:test",
            algorithm="blake3",
            start_sequence=1,
            end_sequence=100,
            event_count=100,
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            info.epoch_id = 1  # type: ignore[misc]
