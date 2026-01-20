"""Unit tests for HaltFlagRepository (Story 3.3, Task 2; Story 3.4 for protected clear).

Tests the halt flag repository that provides durable halt state storage.
This is the DB channel of the dual-channel halt transport.

ADR-3: DB halt flag is the canonical source of truth.
- If Redis is down, DB halt flag is authoritative
- Singleton pattern: only one halt state row exists
- Halt is **sticky** - clearing requires witnessed ceremony (Story 3.4)
"""

from uuid import uuid4

import pytest

from src.domain.errors.halt_clear import HaltClearDeniedError
from src.infrastructure.adapters.persistence.halt_flag_repository import (
    HaltFlagRepository,
    InMemoryHaltFlagRepository,
)


class TestInMemoryHaltFlagRepository:
    """Test the in-memory halt flag repository."""

    @pytest.fixture
    def repo(self) -> InMemoryHaltFlagRepository:
        """Create a fresh repository for each test."""
        return InMemoryHaltFlagRepository()

    @pytest.mark.asyncio
    async def test_initial_state_not_halted(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """Initial halt state should be not halted."""
        state = await repo.get_halt_flag()

        assert state.is_halted is False
        assert state.reason is None
        assert state.crisis_event_id is None

    @pytest.mark.asyncio
    async def test_set_halt_flag_halted(self, repo: InMemoryHaltFlagRepository) -> None:
        """Should be able to set halt flag to halted."""
        crisis_id = uuid4()

        await repo.set_halt_flag(
            halted=True,
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        state = await repo.get_halt_flag()
        assert state.is_halted is True
        assert state.reason == "FR17: Fork detected"
        assert state.crisis_event_id == crisis_id

    @pytest.mark.asyncio
    async def test_set_halt_flag_cleared_with_ceremony(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """Should be able to clear halt flag with ceremony ID (Story 3.4)."""
        # First set halt
        crisis_id = uuid4()
        await repo.set_halt_flag(
            halted=True,
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        # Then clear it with ceremony
        ceremony_id = uuid4()
        await repo.set_halt_flag(
            halted=False,
            reason=None,
            crisis_event_id=None,
            ceremony_id=ceremony_id,
        )

        state = await repo.get_halt_flag()
        assert state.is_halted is False
        assert state.reason is None
        assert state.crisis_event_id is None

    @pytest.mark.asyncio
    async def test_set_halt_flag_clear_without_ceremony_raises_error(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """Clearing halt without ceremony should raise HaltClearDeniedError (AC #1)."""
        # First set halt
        crisis_id = uuid4()
        await repo.set_halt_flag(
            halted=True,
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        # Attempt to clear without ceremony
        with pytest.raises(HaltClearDeniedError) as exc_info:
            await repo.set_halt_flag(
                halted=False,
                reason=None,
                crisis_event_id=None,
                # No ceremony_id!
            )
        assert "ceremony required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_flag_state_is_immutable(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """HaltFlagState returned should be immutable."""
        await repo.set_halt_flag(
            halted=True,
            reason="Test",
            crisis_event_id=uuid4(),
        )

        state = await repo.get_halt_flag()

        with pytest.raises(AttributeError):
            state.is_halted = False  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_multiple_sets_overwrite(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """Setting halt flag multiple times should overwrite previous state."""
        crisis_id_1 = uuid4()
        crisis_id_2 = uuid4()

        await repo.set_halt_flag(
            halted=True,
            reason="First halt",
            crisis_event_id=crisis_id_1,
        )
        await repo.set_halt_flag(
            halted=True,
            reason="Second halt",
            crisis_event_id=crisis_id_2,
        )

        state = await repo.get_halt_flag()
        assert state.reason == "Second halt"
        assert state.crisis_event_id == crisis_id_2

    @pytest.mark.asyncio
    async def test_get_halt_flag_returns_consistent_state(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """Multiple get_halt_flag calls should return consistent state."""
        crisis_id = uuid4()
        await repo.set_halt_flag(
            halted=True,
            reason="Test halt",
            crisis_event_id=crisis_id,
        )

        state1 = await repo.get_halt_flag()
        state2 = await repo.get_halt_flag()

        assert state1.is_halted == state2.is_halted
        assert state1.reason == state2.reason
        assert state1.crisis_event_id == state2.crisis_event_id


class TestHaltFlagRepositoryInterface:
    """Test that HaltFlagRepository is properly defined."""

    def test_is_abstract_class(self) -> None:
        """HaltFlagRepository should be an abstract class."""
        from abc import ABC

        assert issubclass(HaltFlagRepository, ABC)

    def test_in_memory_implements_interface(self) -> None:
        """InMemoryHaltFlagRepository should implement HaltFlagRepository."""
        assert issubclass(InMemoryHaltFlagRepository, HaltFlagRepository)


class TestClearHaltWithCeremony:
    """Tests for clear_halt_with_ceremony method (Story 3.4)."""

    @pytest.fixture
    def repo(self) -> InMemoryHaltFlagRepository:
        """Create a fresh repository for each test."""
        return InMemoryHaltFlagRepository()

    @pytest.mark.asyncio
    async def test_clear_halt_with_ceremony_succeeds(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """Should clear halt when valid ceremony ID is provided."""
        # First set halt
        crisis_id = uuid4()
        await repo.set_halt_flag(
            halted=True,
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        # Clear with ceremony
        ceremony_id = uuid4()
        await repo.clear_halt_with_ceremony(
            ceremony_id=ceremony_id,
            reason="Recovery ceremony completed",
        )

        state = await repo.get_halt_flag()
        assert state.is_halted is False
        assert state.reason == "Recovery ceremony completed"

    @pytest.mark.asyncio
    async def test_clear_halt_with_ceremony_stores_reason(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """Clearing halt should store the reason for audit trail."""
        # First set halt
        await repo.set_halt_flag(
            halted=True,
            reason="Original halt reason",
            crisis_event_id=uuid4(),
        )

        # Clear with ceremony
        await repo.clear_halt_with_ceremony(
            ceremony_id=uuid4(),
            reason="Cleared by Keeper Council - Issue resolved",
        )

        state = await repo.get_halt_flag()
        assert state.reason == "Cleared by Keeper Council - Issue resolved"


class TestClearForTesting:
    """Tests for clear_for_testing method (testing support)."""

    @pytest.fixture
    def repo(self) -> InMemoryHaltFlagRepository:
        """Create a fresh repository for each test."""
        return InMemoryHaltFlagRepository()

    def test_clear_for_testing_resets_state(
        self, repo: InMemoryHaltFlagRepository
    ) -> None:
        """clear_for_testing should reset to initial state without ceremony."""
        import asyncio

        # Set halt
        asyncio.run(
            repo.set_halt_flag(
                halted=True,
                reason="Test halt",
                crisis_event_id=uuid4(),
            )
        )

        # Bypass ceremony with test helper
        repo.clear_for_testing()

        state = asyncio.run(repo.get_halt_flag())
        assert state.is_halted is False
        assert state.reason is None
        assert state.crisis_event_id is None
