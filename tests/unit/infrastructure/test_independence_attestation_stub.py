"""Unit tests for IndependenceAttestationStub (FR98, FR133).

Tests the in-memory stub implementation for testing purposes.

Constitutional Constraints:
- FR133: Annual independence attestation requirement
- FR76: Historical attestations must be preserved (no deletion)
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.independence_attestation import (
    DuplicateIndependenceAttestationError,
)
from src.domain.models.independence_attestation import (
    ConflictDeclaration,
    DeclarationType,
    IndependenceAttestation,
    get_current_attestation_year,
)
from src.infrastructure.stubs.independence_attestation_stub import (
    IndependenceAttestationStub,
)


@pytest.fixture
def stub() -> IndependenceAttestationStub:
    """Create fresh stub for each test."""
    return IndependenceAttestationStub()


def create_attestation(
    keeper_id: str = "KEEPER:alice",
    year: int | None = None,
    conflicts: list[ConflictDeclaration] | None = None,
    organizations: list[str] | None = None,
) -> IndependenceAttestation:
    """Helper to create attestation for testing."""
    return IndependenceAttestation(
        id=uuid4(),
        keeper_id=keeper_id,
        attested_at=datetime.now(timezone.utc),
        attestation_year=year or get_current_attestation_year(),
        conflict_declarations=conflicts or [],
        affiliated_organizations=organizations or [],
        signature=b"x" * 64,
    )


class TestGetAttestation:
    """Tests for get_attestation method."""

    @pytest.mark.asyncio
    async def test_get_attestation_not_found(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns None when attestation not found."""
        result = await stub.get_attestation("KEEPER:alice", 2026)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_attestation_found(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns attestation when found."""
        attestation = create_attestation()
        await stub.record_attestation(attestation)

        result = await stub.get_attestation(
            attestation.keeper_id,
            attestation.attestation_year,
        )

        assert result is not None
        assert result.id == attestation.id

    @pytest.mark.asyncio
    async def test_get_attestation_wrong_year(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns None when year doesn't match."""
        attestation = create_attestation(year=2026)
        await stub.record_attestation(attestation)

        result = await stub.get_attestation(attestation.keeper_id, 2025)

        assert result is None


class TestRecordAttestation:
    """Tests for record_attestation method."""

    @pytest.mark.asyncio
    async def test_record_attestation_success(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test successful attestation recording."""
        attestation = create_attestation()

        await stub.record_attestation(attestation)

        result = await stub.get_attestation(
            attestation.keeper_id,
            attestation.attestation_year,
        )
        assert result is not None
        assert result.id == attestation.id

    @pytest.mark.asyncio
    async def test_record_attestation_duplicate_rejected(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test duplicate attestation for same year is rejected."""
        attestation1 = create_attestation()
        attestation2 = create_attestation(year=attestation1.attestation_year)

        await stub.record_attestation(attestation1)

        with pytest.raises(DuplicateIndependenceAttestationError):
            await stub.record_attestation(attestation2)

    @pytest.mark.asyncio
    async def test_record_different_years_allowed(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test attestations for different years are allowed."""
        attestation1 = create_attestation(year=2025)
        attestation2 = create_attestation(year=2026)

        await stub.record_attestation(attestation1)
        await stub.record_attestation(attestation2)

        result1 = await stub.get_attestation(attestation1.keeper_id, 2025)
        result2 = await stub.get_attestation(attestation2.keeper_id, 2026)

        assert result1 is not None
        assert result2 is not None

    @pytest.mark.asyncio
    async def test_record_different_keepers_allowed(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test attestations for different Keepers are allowed."""
        attestation1 = create_attestation(keeper_id="KEEPER:alice")
        attestation2 = create_attestation(keeper_id="KEEPER:bob")

        await stub.record_attestation(attestation1)
        await stub.record_attestation(attestation2)

        result1 = await stub.get_attestation("KEEPER:alice", attestation1.attestation_year)
        result2 = await stub.get_attestation("KEEPER:bob", attestation2.attestation_year)

        assert result1 is not None
        assert result2 is not None


class TestGetAttestationHistory:
    """Tests for get_attestation_history method."""

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns empty list when no attestations."""
        result = await stub.get_attestation_history("KEEPER:alice")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_ordered_by_year(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns attestations ordered by year ascending."""
        keeper_id = "KEEPER:alice"

        # Add in random order
        await stub.record_attestation(create_attestation(keeper_id=keeper_id, year=2026))
        await stub.record_attestation(create_attestation(keeper_id=keeper_id, year=2024))
        await stub.record_attestation(create_attestation(keeper_id=keeper_id, year=2025))

        result = await stub.get_attestation_history(keeper_id)

        assert len(result) == 3
        years = [a.attestation_year for a in result]
        assert years == [2024, 2025, 2026]


class TestGetLatestAttestation:
    """Tests for get_latest_attestation method."""

    @pytest.mark.asyncio
    async def test_get_latest_none(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns None when no attestations."""
        result = await stub.get_latest_attestation("KEEPER:alice")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_returns_most_recent(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns most recent attestation by year."""
        keeper_id = "KEEPER:alice"

        await stub.record_attestation(create_attestation(keeper_id=keeper_id, year=2024))
        await stub.record_attestation(create_attestation(keeper_id=keeper_id, year=2026))
        await stub.record_attestation(create_attestation(keeper_id=keeper_id, year=2025))

        result = await stub.get_latest_attestation(keeper_id)

        assert result is not None
        assert result.attestation_year == 2026


class TestKeepersOverdueAttestation:
    """Tests for get_keepers_overdue_attestation method."""

    @pytest.mark.asyncio
    async def test_get_overdue_empty_when_no_keepers(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns empty when no active Keepers."""
        result = await stub.get_keepers_overdue_attestation()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_overdue_includes_keepers_without_current_year(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns Keepers without current year attestation."""
        stub.add_keeper("KEEPER:alice")
        stub.add_keeper("KEEPER:bob")

        # Only Bob has current year attestation
        await stub.record_attestation(create_attestation(keeper_id="KEEPER:bob"))

        result = await stub.get_keepers_overdue_attestation()

        assert "KEEPER:alice" in result
        assert "KEEPER:bob" not in result


class TestSuspension:
    """Tests for suspension-related methods."""

    @pytest.mark.asyncio
    async def test_mark_keeper_suspended(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test marking Keeper as suspended."""
        keeper_id = "KEEPER:alice"

        await stub.mark_keeper_suspended(keeper_id, "Overdue")

        assert await stub.is_keeper_suspended(keeper_id)

    @pytest.mark.asyncio
    async def test_is_keeper_suspended_false(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test non-suspended Keeper returns False."""
        assert not await stub.is_keeper_suspended("KEEPER:alice")

    @pytest.mark.asyncio
    async def test_clear_suspension(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test clearing suspension."""
        keeper_id = "KEEPER:alice"

        await stub.mark_keeper_suspended(keeper_id, "Overdue")
        assert await stub.is_keeper_suspended(keeper_id)

        await stub.clear_suspension(keeper_id)
        assert not await stub.is_keeper_suspended(keeper_id)

    @pytest.mark.asyncio
    async def test_clear_non_suspended_no_error(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test clearing non-suspended Keeper doesn't raise."""
        await stub.clear_suspension("KEEPER:alice")  # Should not raise


class TestActiveKeepers:
    """Tests for active Keeper management."""

    @pytest.mark.asyncio
    async def test_get_all_active_keepers_empty(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns empty when no active Keepers."""
        result = await stub.get_all_active_keepers()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_active_keepers(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test returns all active Keepers."""
        stub.add_keeper("KEEPER:alice")
        stub.add_keeper("KEEPER:bob")

        result = await stub.get_all_active_keepers()

        assert len(result) == 2
        assert "KEEPER:alice" in result
        assert "KEEPER:bob" in result


class TestHelperMethods:
    """Tests for test helper methods."""

    def test_add_keeper(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test add_keeper helper method."""
        stub.add_keeper("KEEPER:alice")
        assert "KEEPER:alice" in stub._active_keepers

    def test_remove_keeper_preserves_attestations(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test remove_keeper preserves attestation history (FR76)."""
        keeper_id = "KEEPER:alice"
        stub.add_keeper(keeper_id)

        # Record attestation
        stub._attestations[keeper_id] = {2026: create_attestation(keeper_id=keeper_id)}

        # Remove Keeper
        stub.remove_keeper(keeper_id)

        # Keeper removed from active
        assert keeper_id not in stub._active_keepers

        # But attestation preserved (FR76)
        assert keeper_id in stub._attestations

    def test_get_suspension_reason(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test get_suspension_reason helper method."""
        keeper_id = "KEEPER:alice"

        stub._suspended_keepers[keeper_id] = "Test reason"

        assert stub.get_suspension_reason(keeper_id) == "Test reason"
        assert stub.get_suspension_reason("KEEPER:bob") is None

    def test_get_suspended_keepers(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test get_suspended_keepers helper method."""
        stub._suspended_keepers["KEEPER:alice"] = "Reason 1"
        stub._suspended_keepers["KEEPER:bob"] = "Reason 2"

        result = stub.get_suspended_keepers()

        assert len(result) == 2
        assert "KEEPER:alice" in result
        assert "KEEPER:bob" in result

    def test_reset(
        self,
        stub: IndependenceAttestationStub,
    ) -> None:
        """Test reset clears all state."""
        stub.add_keeper("KEEPER:alice")
        stub._attestations["KEEPER:alice"] = {2026: create_attestation()}
        stub._suspended_keepers["KEEPER:bob"] = "Suspended"

        stub.reset()

        assert stub._attestations == {}
        assert stub._active_keepers == set()
        assert stub._suspended_keepers == {}
