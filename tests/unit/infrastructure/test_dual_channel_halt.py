"""Unit tests for DualChannelHaltTransportImpl (Story 3.3, Task 5).

Tests the combined dual-channel halt transport adapter.
This implements ADR-3: Redis Streams + DB halt flag.

Key behaviors tested:
- AC1: Write to BOTH channels atomically
- AC2: Return True if EITHER channel indicates halt
- AC3: DB as source of truth during Redis failure
- AC4: Conflict detection and resolution
- AC5: 5-second Redis-to-DB confirmation (RT-2)
"""

import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.ports.dual_channel_halt import (
    CONFIRMATION_TIMEOUT_SECONDS,
    DualChannelHaltTransport,
    HaltFlagState,
)
from src.infrastructure.adapters.messaging.dual_channel_halt_impl import (
    DualChannelHaltTransportImpl,
)
from src.infrastructure.adapters.persistence.halt_flag_repository import (
    HaltFlagRepository,
    InMemoryHaltFlagRepository,
)


class TestDualChannelHaltTransportImpl:
    """Test the dual-channel halt transport implementation."""

    @pytest.fixture
    def mock_halt_repo(self) -> AsyncMock:
        """Create mock halt flag repository."""
        repo = AsyncMock(spec=HaltFlagRepository)
        repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=False,
            reason=None,
            crisis_event_id=None,
        )
        return repo

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        """Create mock halt stream publisher."""
        publisher = AsyncMock()
        publisher.publish_halt.return_value = "1704067200000-0"
        return publisher

    @pytest.fixture
    def mock_consumer(self) -> MagicMock:
        """Create mock halt stream consumer."""
        consumer = MagicMock()
        consumer.check_redis_halt = AsyncMock(return_value=False)
        consumer.has_halt_received = False
        consumer.get_halt_info.return_value = None
        return consumer

    @pytest.fixture
    def transport(
        self,
        mock_halt_repo: AsyncMock,
        mock_publisher: AsyncMock,
        mock_consumer: MagicMock,
    ) -> DualChannelHaltTransportImpl:
        """Create the transport under test."""
        return DualChannelHaltTransportImpl(
            halt_flag_repo=mock_halt_repo,
            halt_publisher=mock_publisher,
            halt_consumer=mock_consumer,
        )

    @pytest.mark.asyncio
    async def test_implements_dual_channel_halt_transport(
        self, transport: DualChannelHaltTransportImpl
    ) -> None:
        """Transport should implement DualChannelHaltTransport interface."""
        assert isinstance(transport, DualChannelHaltTransport)

    @pytest.mark.asyncio
    async def test_confirmation_timeout_seconds(
        self, transport: DualChannelHaltTransportImpl
    ) -> None:
        """confirmation_timeout_seconds should return RT-2 value (5 seconds)."""
        assert transport.confirmation_timeout_seconds == CONFIRMATION_TIMEOUT_SECONDS
        assert transport.confirmation_timeout_seconds == 5.0


class TestWriteHalt:
    """Test write_halt method (AC1)."""

    @pytest.fixture
    def mock_halt_repo(self) -> AsyncMock:
        """Create mock halt flag repository."""
        return AsyncMock(spec=HaltFlagRepository)

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        """Create mock halt stream publisher."""
        publisher = AsyncMock()
        publisher.publish_halt.return_value = "1704067200000-0"
        return publisher

    @pytest.fixture
    def mock_consumer(self) -> MagicMock:
        """Create mock halt stream consumer."""
        consumer = MagicMock()
        consumer.check_redis_halt = AsyncMock(return_value=False)
        return consumer

    @pytest.fixture
    def transport(
        self,
        mock_halt_repo: AsyncMock,
        mock_publisher: AsyncMock,
        mock_consumer: MagicMock,
    ) -> DualChannelHaltTransportImpl:
        return DualChannelHaltTransportImpl(
            halt_flag_repo=mock_halt_repo,
            halt_publisher=mock_publisher,
            halt_consumer=mock_consumer,
        )

    @pytest.mark.asyncio
    async def test_write_halt_writes_to_db(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_halt_repo: AsyncMock,
    ) -> None:
        """write_halt should write to DB halt flag."""
        crisis_id = uuid4()

        await transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        mock_halt_repo.set_halt_flag.assert_called_once_with(
            halted=True,
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

    @pytest.mark.asyncio
    async def test_write_halt_writes_to_redis(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_publisher: AsyncMock,
    ) -> None:
        """write_halt should write to Redis stream."""
        crisis_id = uuid4()

        await transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        mock_publisher.publish_halt.assert_called_once_with(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

    @pytest.mark.asyncio
    async def test_write_halt_writes_both_atomically(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_halt_repo: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> None:
        """write_halt should write to both channels."""
        crisis_id = uuid4()

        await transport.write_halt(
            reason="Test halt",
            crisis_event_id=crisis_id,
        )

        # Both should be called
        mock_halt_repo.set_halt_flag.assert_called_once()
        mock_publisher.publish_halt.assert_called_once()


class TestIsHalted:
    """Test is_halted method (AC2, AC3)."""

    @pytest.fixture
    def mock_halt_repo(self) -> AsyncMock:
        """Create mock halt flag repository."""
        repo = AsyncMock(spec=HaltFlagRepository)
        repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=False,
            reason=None,
            crisis_event_id=None,
        )
        return repo

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_consumer(self) -> MagicMock:
        consumer = MagicMock()
        consumer.check_redis_halt = AsyncMock(return_value=False)
        consumer.has_halt_received = False
        return consumer

    @pytest.fixture
    def transport(
        self,
        mock_halt_repo: AsyncMock,
        mock_publisher: AsyncMock,
        mock_consumer: MagicMock,
    ) -> DualChannelHaltTransportImpl:
        return DualChannelHaltTransportImpl(
            halt_flag_repo=mock_halt_repo,
            halt_publisher=mock_publisher,
            halt_consumer=mock_consumer,
        )

    @pytest.mark.asyncio
    async def test_is_halted_false_when_neither_halted(
        self, transport: DualChannelHaltTransportImpl
    ) -> None:
        """is_halted should return False when neither channel indicates halt."""
        halted = await transport.is_halted()
        assert halted is False

    @pytest.mark.asyncio
    async def test_is_halted_true_when_db_halted(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_halt_repo: AsyncMock,
    ) -> None:
        """is_halted should return True when DB indicates halt."""
        mock_halt_repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=True,
            reason="DB halt",
            crisis_event_id=uuid4(),
        )

        halted = await transport.is_halted()
        assert halted is True

    @pytest.mark.asyncio
    async def test_is_halted_true_when_redis_halted(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_consumer: MagicMock,
    ) -> None:
        """is_halted should return True when Redis indicates halt."""
        mock_consumer.check_redis_halt.return_value = True

        halted = await transport.is_halted()
        assert halted is True

    @pytest.mark.asyncio
    async def test_is_halted_true_when_either_halted(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_halt_repo: AsyncMock,
        mock_consumer: MagicMock,
    ) -> None:
        """is_halted should return True if EITHER channel indicates halt."""
        # Only Redis halted
        mock_consumer.check_redis_halt.return_value = True

        halted = await transport.is_halted()
        assert halted is True

    @pytest.mark.asyncio
    async def test_is_halted_uses_db_when_redis_fails(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_halt_repo: AsyncMock,
        mock_consumer: MagicMock,
    ) -> None:
        """is_halted should use DB when Redis fails (AC3)."""
        mock_consumer.check_redis_halt.side_effect = Exception("Redis down")
        mock_halt_repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=True,
            reason="DB halt",
            crisis_event_id=uuid4(),
        )

        halted = await transport.is_halted()
        assert halted is True


class TestCheckChannelsConsistent:
    """Test check_channels_consistent method (AC4)."""

    @pytest.fixture
    def mock_halt_repo(self) -> AsyncMock:
        repo = AsyncMock(spec=HaltFlagRepository)
        repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=False,
            reason=None,
            crisis_event_id=None,
        )
        return repo

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_consumer(self) -> MagicMock:
        consumer = MagicMock()
        consumer.check_redis_halt = AsyncMock(return_value=False)
        return consumer

    @pytest.fixture
    def transport(
        self,
        mock_halt_repo: AsyncMock,
        mock_publisher: AsyncMock,
        mock_consumer: MagicMock,
    ) -> DualChannelHaltTransportImpl:
        return DualChannelHaltTransportImpl(
            halt_flag_repo=mock_halt_repo,
            halt_publisher=mock_publisher,
            halt_consumer=mock_consumer,
        )

    @pytest.mark.asyncio
    async def test_consistent_when_both_not_halted(
        self, transport: DualChannelHaltTransportImpl
    ) -> None:
        """Channels are consistent when both show not halted."""
        consistent = await transport.check_channels_consistent()
        assert consistent is True

    @pytest.mark.asyncio
    async def test_consistent_when_both_halted(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_halt_repo: AsyncMock,
        mock_consumer: MagicMock,
    ) -> None:
        """Channels are consistent when both show halted."""
        mock_halt_repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=True,
            reason="Test",
            crisis_event_id=uuid4(),
        )
        mock_consumer.check_redis_halt.return_value = True

        consistent = await transport.check_channels_consistent()
        assert consistent is True

    @pytest.mark.asyncio
    async def test_inconsistent_when_redis_halted_db_not(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_consumer: MagicMock,
    ) -> None:
        """Channels are inconsistent when Redis says halt but DB doesn't."""
        mock_consumer.check_redis_halt.return_value = True

        consistent = await transport.check_channels_consistent()
        assert consistent is False


class TestGetHaltReason:
    """Test get_halt_reason method."""

    @pytest.fixture
    def mock_halt_repo(self) -> AsyncMock:
        repo = AsyncMock(spec=HaltFlagRepository)
        repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=False,
            reason=None,
            crisis_event_id=None,
        )
        return repo

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_consumer(self) -> MagicMock:
        consumer = MagicMock()
        consumer.check_redis_halt = AsyncMock(return_value=False)
        consumer.get_halt_info.return_value = None
        return consumer

    @pytest.fixture
    def transport(
        self,
        mock_halt_repo: AsyncMock,
        mock_publisher: AsyncMock,
        mock_consumer: MagicMock,
    ) -> DualChannelHaltTransportImpl:
        return DualChannelHaltTransportImpl(
            halt_flag_repo=mock_halt_repo,
            halt_publisher=mock_publisher,
            halt_consumer=mock_consumer,
        )

    @pytest.mark.asyncio
    async def test_get_halt_reason_none_when_not_halted(
        self, transport: DualChannelHaltTransportImpl
    ) -> None:
        """get_halt_reason should return None when not halted."""
        reason = await transport.get_halt_reason()
        assert reason is None

    @pytest.mark.asyncio
    async def test_get_halt_reason_from_db_when_halted(
        self,
        transport: DualChannelHaltTransportImpl,
        mock_halt_repo: AsyncMock,
    ) -> None:
        """get_halt_reason should return DB reason when halted."""
        mock_halt_repo.get_halt_flag.return_value = HaltFlagState(
            is_halted=True,
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        reason = await transport.get_halt_reason()
        assert reason == "FR17: Fork detected"
