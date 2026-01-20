"""Unit tests for ThresholdRepositoryStub (Story 6.4).

Tests the in-memory threshold repository stub.
"""

import pytest

from src.infrastructure.stubs.threshold_repository_stub import ThresholdRepositoryStub


class TestThresholdRepositoryStub:
    """Tests for ThresholdRepositoryStub."""

    @pytest.fixture
    def stub(self) -> ThresholdRepositoryStub:
        """Create a fresh stub for each test."""
        return ThresholdRepositoryStub()

    @pytest.mark.asyncio
    async def test_save_and_get_override(self, stub: ThresholdRepositoryStub) -> None:
        """Test saving and retrieving an override."""
        await stub.save_threshold_override("test_threshold", 15)

        result = await stub.get_threshold_override("test_threshold")

        assert result == 15

    @pytest.mark.asyncio
    async def test_get_override_returns_none_for_unset(
        self, stub: ThresholdRepositoryStub
    ) -> None:
        """Test get_threshold_override returns None for unset threshold."""
        result = await stub.get_threshold_override("unset_threshold")

        assert result is None

    @pytest.mark.asyncio
    async def test_save_override_updates_existing(
        self, stub: ThresholdRepositoryStub
    ) -> None:
        """Test saving override updates existing value."""
        await stub.save_threshold_override("test", 10)
        await stub.save_threshold_override("test", 20)

        result = await stub.get_threshold_override("test")

        assert result == 20

    @pytest.mark.asyncio
    async def test_clear_override(self, stub: ThresholdRepositoryStub) -> None:
        """Test clearing an override."""
        await stub.save_threshold_override("test", 15)
        await stub.clear_threshold_override("test")

        result = await stub.get_threshold_override("test")

        assert result is None

    @pytest.mark.asyncio
    async def test_clear_nonexistent_override_no_error(
        self, stub: ThresholdRepositoryStub
    ) -> None:
        """Test clearing nonexistent override doesn't raise."""
        # Should not raise
        await stub.clear_threshold_override("nonexistent")

    def test_clear_all(self, stub: ThresholdRepositoryStub) -> None:
        """Test clear() method removes all overrides."""
        # Use sync pattern for clear()
        import asyncio

        async def setup():
            await stub.save_threshold_override("t1", 10)
            await stub.save_threshold_override("t2", 20)

        asyncio.run(setup())

        stub.clear()

        async def check():
            assert await stub.get_threshold_override("t1") is None
            assert await stub.get_threshold_override("t2") is None

        asyncio.run(check())

    @pytest.mark.asyncio
    async def test_override_count(self, stub: ThresholdRepositoryStub) -> None:
        """Test override_count property."""
        assert stub.override_count == 0

        await stub.save_threshold_override("t1", 10)
        assert stub.override_count == 1

        await stub.save_threshold_override("t2", 20)
        assert stub.override_count == 2

    @pytest.mark.asyncio
    async def test_has_override(self, stub: ThresholdRepositoryStub) -> None:
        """Test has_override method."""
        assert stub.has_override("test") is False

        await stub.save_threshold_override("test", 10)

        assert stub.has_override("test") is True
        assert stub.has_override("other") is False

    @pytest.mark.asyncio
    async def test_save_float_value(self, stub: ThresholdRepositoryStub) -> None:
        """Test saving and retrieving float values."""
        await stub.save_threshold_override("diversity", 0.35)

        result = await stub.get_threshold_override("diversity")

        assert result == 0.35

    @pytest.mark.asyncio
    async def test_multiple_thresholds(self, stub: ThresholdRepositoryStub) -> None:
        """Test storing multiple threshold overrides."""
        await stub.save_threshold_override("t1", 10)
        await stub.save_threshold_override("t2", 20)
        await stub.save_threshold_override("t3", 0.5)

        assert await stub.get_threshold_override("t1") == 10
        assert await stub.get_threshold_override("t2") == 20
        assert await stub.get_threshold_override("t3") == 0.5
        assert stub.override_count == 3
