"""Unit tests for KeeperAvailabilityStub (Story 5.8).

Tests the in-memory stub implementation of KeeperAvailabilityProtocol.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.keeper_availability import DuplicateAttestationError
from src.domain.models.keeper_attestation import KeeperAttestation
from src.infrastructure.stubs.keeper_availability_stub import KeeperAvailabilityStub


@pytest.fixture
def stub() -> KeeperAvailabilityStub:
    """Create fresh stub for each test."""
    return KeeperAvailabilityStub()


class TestRecordAttestation:
    """Test record_attestation method."""

    @pytest.mark.asyncio
    async def test_record_attestation_success(self, stub: KeeperAvailabilityStub) -> None:
        """Test successfully recording an attestation."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=b"x" * 64,
        )

        await stub.record_attestation(attestation)

        # Should be retrievable
        retrieved = await stub.get_attestation("KEEPER:alice", period_start)
        assert retrieved is not None
        assert retrieved.keeper_id == "KEEPER:alice"

    @pytest.mark.asyncio
    async def test_record_duplicate_attestation_raises_error(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test that recording duplicate attestation raises error."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        attestation1 = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=b"x" * 64,
        )

        attestation2 = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now + timedelta(hours=1),
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=b"y" * 64,
        )

        await stub.record_attestation(attestation1)

        with pytest.raises(DuplicateAttestationError):
            await stub.record_attestation(attestation2)


class TestMissedAttestations:
    """Test missed attestation tracking methods."""

    @pytest.mark.asyncio
    async def test_get_missed_count_default_zero(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test that missed count defaults to 0."""
        count = await stub.get_missed_attestations_count("KEEPER:alice")
        assert count == 0

    @pytest.mark.asyncio
    async def test_increment_missed_attestations(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test incrementing missed attestations count."""
        new_count = await stub.increment_missed_attestations("KEEPER:alice")
        assert new_count == 1

        new_count = await stub.increment_missed_attestations("KEEPER:alice")
        assert new_count == 2

    @pytest.mark.asyncio
    async def test_reset_missed_attestations(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test resetting missed attestations count."""
        await stub.increment_missed_attestations("KEEPER:alice")
        await stub.increment_missed_attestations("KEEPER:alice")

        await stub.reset_missed_attestations("KEEPER:alice")

        count = await stub.get_missed_attestations_count("KEEPER:alice")
        assert count == 0


class TestKeeperManagement:
    """Test Keeper add/remove methods."""

    @pytest.mark.asyncio
    async def test_add_keeper(self, stub: KeeperAvailabilityStub) -> None:
        """Test adding a Keeper."""
        await stub.add_keeper("KEEPER:alice")

        active = await stub.get_all_active_keepers()
        assert "KEEPER:alice" in active

    @pytest.mark.asyncio
    async def test_remove_keeper(self, stub: KeeperAvailabilityStub) -> None:
        """Test removing a Keeper."""
        await stub.add_keeper("KEEPER:alice")
        await stub.remove_keeper("KEEPER:alice")

        active = await stub.get_all_active_keepers()
        assert "KEEPER:alice" not in active

    @pytest.mark.asyncio
    async def test_get_current_keeper_count(self, stub: KeeperAvailabilityStub) -> None:
        """Test getting current Keeper count."""
        await stub.add_keeper("KEEPER:alice")
        await stub.add_keeper("KEEPER:bob")

        count = await stub.get_current_keeper_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_keeper_count_excludes_pending_replacement(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test that Keeper count excludes those pending replacement."""
        await stub.add_keeper("KEEPER:alice")
        await stub.add_keeper("KEEPER:bob")
        await stub.mark_keeper_for_replacement("KEEPER:bob", "test reason")

        count = await stub.get_current_keeper_count()
        assert count == 1  # Only alice


class TestReplacementTracking:
    """Test replacement tracking methods."""

    @pytest.mark.asyncio
    async def test_mark_keeper_for_replacement(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test marking Keeper for replacement."""
        await stub.add_keeper("KEEPER:alice")
        await stub.mark_keeper_for_replacement("KEEPER:alice", "FR78: Missed 2")

        pending = await stub.get_keepers_pending_replacement()
        assert "KEEPER:alice" in pending

    @pytest.mark.asyncio
    async def test_get_replacement_reason(self, stub: KeeperAvailabilityStub) -> None:
        """Test getting replacement reason."""
        await stub.add_keeper("KEEPER:alice")
        await stub.mark_keeper_for_replacement("KEEPER:alice", "FR78: Missed 2")

        reason = stub.get_replacement_reason("KEEPER:alice")
        assert reason == "FR78: Missed 2"


class TestLastAttestation:
    """Test get_last_attestation method."""

    @pytest.mark.asyncio
    async def test_get_last_attestation_none_when_empty(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test returns None when no attestations."""
        result = await stub.get_last_attestation("KEEPER:alice")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_last_attestation_returns_most_recent(
        self, stub: KeeperAvailabilityStub
    ) -> None:
        """Test returns most recent attestation."""
        now = datetime.now(timezone.utc)
        period1_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period2_start = period1_start + timedelta(days=7)

        att1 = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period1_start,
            period_end=period1_start + timedelta(days=7),
            signature=b"x" * 64,
        )

        att2 = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now + timedelta(days=7),
            period_start=period2_start,
            period_end=period2_start + timedelta(days=7),
            signature=b"y" * 64,
        )

        await stub.record_attestation(att1)
        await stub.record_attestation(att2)

        last = await stub.get_last_attestation("KEEPER:alice")
        assert last is not None
        assert last.period_start == period2_start


class TestReset:
    """Test reset method."""

    @pytest.mark.asyncio
    async def test_reset_clears_all_state(self, stub: KeeperAvailabilityStub) -> None:
        """Test that reset clears all state."""
        now = datetime.now(timezone.utc)
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Add various state
        await stub.add_keeper("KEEPER:alice")
        await stub.increment_missed_attestations("KEEPER:alice")
        await stub.mark_keeper_for_replacement("KEEPER:bob", "test")

        attestation = KeeperAttestation(
            id=uuid4(),
            keeper_id="KEEPER:alice",
            attested_at=now,
            period_start=period_start,
            period_end=period_start + timedelta(days=7),
            signature=b"x" * 64,
        )
        await stub.record_attestation(attestation)

        # Reset
        stub.reset()

        # All state should be cleared
        assert await stub.get_all_active_keepers() == []
        assert await stub.get_keepers_pending_replacement() == []
        assert await stub.get_missed_attestations_count("KEEPER:alice") == 0
        assert await stub.get_last_attestation("KEEPER:alice") is None
