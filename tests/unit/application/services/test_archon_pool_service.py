"""Unit tests for ArchonPoolService (Story 0.7, HP-11).

Tests:
- Service initialization
- Archon selection (deterministic)
- Selection idempotency
- Lookup operations
- Pool size requirements
"""

from uuid import UUID, uuid4

import pytest

from src.application.services.archon_pool import (
    ArchonPoolService,
    get_archon_pool_service,
)
from src.domain.models.fate_archon import (
    FATE_ARCHON_AMON,
    FATE_ARCHON_LERAJE,
    FATE_ARCHON_RONOVE,
    THREE_FATES_POOL,
    DeliberationStyle,
    FateArchon,
)


def _create_test_archon(name: str, archon_id: UUID | None = None) -> FateArchon:
    """Create a test FateArchon."""
    return FateArchon(
        id=archon_id or uuid4(),
        name=name,
        title=f"Marquis of {name}",
        deliberation_style=DeliberationStyle.PRAGMATIC_MODERATOR,
        system_prompt_template=f"You are {name}.",
    )


class TestArchonPoolServiceInitialization:
    """Test service initialization."""

    def test_default_uses_canonical_pool(self) -> None:
        """Default initialization uses THREE_FATES_POOL."""
        service = ArchonPoolService()

        assert service.get_pool_size() == len(THREE_FATES_POOL)

    def test_custom_pool(self) -> None:
        """Custom pool can be provided."""
        custom_pool = (
            _create_test_archon("Alpha"),
            _create_test_archon("Beta"),
            _create_test_archon("Gamma"),
        )

        service = ArchonPoolService(pool=custom_pool)

        assert service.get_pool_size() == 3

    def test_pool_too_small_raises_error(self) -> None:
        """Pool with fewer than 3 Archons raises ValueError."""
        small_pool = (
            _create_test_archon("One"),
            _create_test_archon("Two"),
        )

        with pytest.raises(ValueError, match="at least 3 Archons"):
            ArchonPoolService(pool=small_pool)


class TestArchonSelection:
    """Test Archon selection for deliberation."""

    def test_selects_exactly_three(self) -> None:
        """select_archons returns exactly 3 Archons."""
        service = ArchonPoolService()
        petition_id = uuid4()

        selected = service.select_archons(petition_id)

        assert len(selected) == 3
        assert all(isinstance(a, FateArchon) for a in selected)

    def test_selection_is_deterministic(self) -> None:
        """Same inputs produce same selection."""
        service = ArchonPoolService()
        petition_id = uuid4()
        seed = 12345

        selection1 = service.select_archons(petition_id, seed=seed)
        selection2 = service.select_archons(petition_id, seed=seed)

        assert selection1 == selection2

    def test_different_petitions_different_selection(self) -> None:
        """Different petition IDs produce different selections."""
        service = ArchonPoolService()
        petition1 = uuid4()
        petition2 = uuid4()

        selection1 = service.select_archons(petition1)
        selection2 = service.select_archons(petition2)

        # Very unlikely to be identical with 7 Archons
        # (7 choose 3) * 3! = 35 * 6 = 210 permutations
        assert selection1 != selection2

    def test_different_seeds_different_selection(self) -> None:
        """Different seeds produce different selections."""
        service = ArchonPoolService()
        petition_id = uuid4()

        selection1 = service.select_archons(petition_id, seed=1)
        selection2 = service.select_archons(petition_id, seed=2)

        assert selection1 != selection2

    def test_selected_archons_are_unique(self) -> None:
        """Selected Archons are unique (no duplicates)."""
        service = ArchonPoolService()

        for _ in range(100):  # Test with many petitions
            petition_id = uuid4()
            selected = service.select_archons(petition_id)
            ids = [a.id for a in selected]
            assert len(ids) == len(set(ids)), "Duplicate Archon selected"

    def test_selection_without_seed(self) -> None:
        """Selection works without explicit seed."""
        service = ArchonPoolService()
        petition_id = uuid4()

        selected = service.select_archons(petition_id)

        assert len(selected) == 3

    def test_all_pool_members_can_be_selected(self) -> None:
        """Over many selections, all pool members appear."""
        service = ArchonPoolService()
        selected_ids: set[UUID] = set()

        # Run many selections
        for i in range(1000):
            petition_id = uuid4()
            selected = service.select_archons(petition_id)
            selected_ids.update(a.id for a in selected)

        # All 7 Archons should have been selected at least once
        pool_ids = {a.id for a in THREE_FATES_POOL}
        assert selected_ids == pool_ids


class TestArchonPoolLookups:
    """Test Archon lookup operations."""

    def test_get_archon_by_id_found(self) -> None:
        """get_archon_by_id returns Archon when found."""
        service = ArchonPoolService()

        result = service.get_archon_by_id(FATE_ARCHON_AMON.id)

        assert result is not None
        assert result.name == "Amon"

    def test_get_archon_by_id_not_found(self) -> None:
        """get_archon_by_id returns None when not found."""
        service = ArchonPoolService()

        result = service.get_archon_by_id(uuid4())

        assert result is None

    def test_get_archon_by_name_found(self) -> None:
        """get_archon_by_name returns Archon when found."""
        service = ArchonPoolService()

        result = service.get_archon_by_name("Leraje")

        assert result is not None
        assert result == FATE_ARCHON_LERAJE

    def test_get_archon_by_name_not_found(self) -> None:
        """get_archon_by_name returns None when not found."""
        service = ArchonPoolService()

        result = service.get_archon_by_name("FakeArchon")

        assert result is None

    def test_list_all_archons(self) -> None:
        """list_all_archons returns all pool Archons."""
        service = ArchonPoolService()

        result = service.list_all_archons()

        assert len(result) == 7
        assert set(result) == set(THREE_FATES_POOL)

    def test_is_valid_archon_id_true(self) -> None:
        """is_valid_archon_id returns True for valid ID."""
        service = ArchonPoolService()

        assert service.is_valid_archon_id(FATE_ARCHON_RONOVE.id) is True

    def test_is_valid_archon_id_false(self) -> None:
        """is_valid_archon_id returns False for invalid ID."""
        service = ArchonPoolService()

        assert service.is_valid_archon_id(uuid4()) is False


class TestDefaultSingleton:
    """Test default singleton accessor."""

    def test_get_archon_pool_service_returns_service(self) -> None:
        """get_archon_pool_service returns a valid service."""
        service = get_archon_pool_service()

        assert isinstance(service, ArchonPoolService)
        assert service.get_pool_size() == 7

    def test_singleton_returns_same_instance(self) -> None:
        """Singleton returns same instance on multiple calls."""
        service1 = get_archon_pool_service()
        service2 = get_archon_pool_service()

        assert service1 is service2


class TestCustomPoolSelection:
    """Test selection with custom pools."""

    def test_selection_from_custom_pool(self) -> None:
        """Selection works correctly with custom pool."""
        archon_a = _create_test_archon("Alpha")
        archon_b = _create_test_archon("Beta")
        archon_c = _create_test_archon("Gamma")
        custom_pool = (archon_a, archon_b, archon_c)

        service = ArchonPoolService(pool=custom_pool)
        petition_id = uuid4()

        selected = service.select_archons(petition_id)

        # With exactly 3 Archons, all 3 must be selected
        assert len(selected) == 3
        selected_ids = {a.id for a in selected}
        expected_ids = {archon_a.id, archon_b.id, archon_c.id}
        assert selected_ids == expected_ids

    def test_larger_custom_pool(self) -> None:
        """Selection from larger custom pool works."""
        custom_pool = tuple(_create_test_archon(f"Archon{i}") for i in range(10))

        service = ArchonPoolService(pool=custom_pool)
        petition_id = uuid4()

        selected = service.select_archons(petition_id)

        assert len(selected) == 3
        # Verify selected are from pool
        pool_ids = {a.id for a in custom_pool}
        for archon in selected:
            assert archon.id in pool_ids
