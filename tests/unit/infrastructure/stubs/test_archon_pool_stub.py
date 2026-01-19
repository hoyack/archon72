"""Unit tests for ArchonPoolStub (Story 0.7, HP-11).

Tests:
- Stub initialization and pre-population
- Archon selection (deterministic)
- Fixed selection override
- Lookup operations
- Operation tracking
- Testing helper methods
"""

from uuid import uuid4

import pytest

from src.domain.models.fate_archon import (
    FATE_ARCHON_AMON,
    FATE_ARCHON_LERAJE,
    THREE_FATES_POOL,
    DeliberationStyle,
)
from src.infrastructure.stubs.archon_pool_stub import (
    ArchonPoolStub,
    create_test_archon,
)


class TestArchonPoolStubInitialization:
    """Test stub initialization and pre-population."""

    def test_default_populates_canonical_pool(self) -> None:
        """Default initialization populates with canonical pool."""
        stub = ArchonPoolStub()

        assert stub.get_archon_count() == 7

    def test_all_canonical_archons_present(self) -> None:
        """All 7 canonical Archons are present and queryable."""
        stub = ArchonPoolStub()

        for archon in THREE_FATES_POOL:
            result = stub.get_archon_by_id(archon.id)
            assert result is not None
            assert result.name == archon.name

    def test_populate_false_creates_empty_pool(self) -> None:
        """populate_canonical=False creates empty pool."""
        stub = ArchonPoolStub(populate_canonical=False)

        assert stub.get_archon_count() == 0
        assert stub.list_all_archons() == []


class TestArchonPoolStubSelection:
    """Test Archon selection operations."""

    def test_selects_exactly_three(self) -> None:
        """select_archons returns exactly 3 Archons."""
        stub = ArchonPoolStub()
        petition_id = uuid4()

        selected = stub.select_archons(petition_id)

        assert len(selected) == 3

    def test_selection_is_deterministic(self) -> None:
        """Same inputs produce same selection."""
        stub = ArchonPoolStub()
        petition_id = uuid4()
        seed = 42

        selection1 = stub.select_archons(petition_id, seed=seed)
        selection2 = stub.select_archons(petition_id, seed=seed)

        assert selection1 == selection2

    def test_selection_matches_service_algorithm(self) -> None:
        """Stub selection matches service selection algorithm."""
        from src.application.services.archon_pool import ArchonPoolService

        stub = ArchonPoolStub()
        service = ArchonPoolService()
        petition_id = uuid4()
        seed = 999

        stub_selection = stub.select_archons(petition_id, seed=seed)
        service_selection = service.select_archons(petition_id, seed=seed)

        # Both should select the same Archons
        assert [a.id for a in stub_selection] == [a.id for a in service_selection]

    def test_pool_too_small_raises_error(self) -> None:
        """Selection with fewer than 3 Archons raises error."""
        stub = ArchonPoolStub(populate_canonical=False)
        stub.add_archon(create_test_archon("One"))
        stub.add_archon(create_test_archon("Two"))

        with pytest.raises(ValueError, match="at least 3 Archons"):
            stub.select_archons(uuid4())


class TestArchonPoolStubFixedSelection:
    """Test fixed selection override."""

    def test_fixed_selection_returns_configured_archons(self) -> None:
        """Fixed selection returns configured Archons regardless of input."""
        stub = ArchonPoolStub()
        fixed = (
            FATE_ARCHON_AMON,
            FATE_ARCHON_LERAJE,
            THREE_FATES_POOL[2],
        )
        stub.set_fixed_selection(fixed)

        selection1 = stub.select_archons(uuid4())
        selection2 = stub.select_archons(uuid4())

        assert selection1 == fixed
        assert selection2 == fixed

    def test_clear_fixed_selection(self) -> None:
        """Setting fixed selection to None restores deterministic behavior."""
        stub = ArchonPoolStub()
        petition_id = uuid4()

        # Get deterministic selection
        normal_selection = stub.select_archons(petition_id, seed=1)

        # Set fixed selection
        fixed = (
            FATE_ARCHON_AMON,
            FATE_ARCHON_LERAJE,
            THREE_FATES_POOL[2],
        )
        stub.set_fixed_selection(fixed)
        fixed_selection = stub.select_archons(petition_id, seed=1)

        # Clear fixed selection
        stub.set_fixed_selection(None)
        stub.clear_operations()
        restored_selection = stub.select_archons(petition_id, seed=1)

        assert fixed_selection == fixed
        assert restored_selection == normal_selection


class TestArchonPoolStubLookups:
    """Test lookup operations."""

    def test_get_archon_by_id_found(self) -> None:
        """get_archon_by_id returns Archon when found."""
        stub = ArchonPoolStub()

        result = stub.get_archon_by_id(FATE_ARCHON_AMON.id)

        assert result is not None
        assert result.name == "Amon"

    def test_get_archon_by_id_not_found(self) -> None:
        """get_archon_by_id returns None when not found."""
        stub = ArchonPoolStub()

        result = stub.get_archon_by_id(uuid4())

        assert result is None

    def test_get_archon_by_name_found(self) -> None:
        """get_archon_by_name returns Archon when found."""
        stub = ArchonPoolStub()

        result = stub.get_archon_by_name("Leraje")

        assert result is not None
        assert result == FATE_ARCHON_LERAJE

    def test_get_archon_by_name_not_found(self) -> None:
        """get_archon_by_name returns None when not found."""
        stub = ArchonPoolStub()

        result = stub.get_archon_by_name("FakeArchon")

        assert result is None

    def test_list_all_archons(self) -> None:
        """list_all_archons returns all Archons."""
        stub = ArchonPoolStub()

        result = stub.list_all_archons()

        assert len(result) == 7

    def test_is_valid_archon_id_true(self) -> None:
        """is_valid_archon_id returns True for valid ID."""
        stub = ArchonPoolStub()

        assert stub.is_valid_archon_id(FATE_ARCHON_AMON.id) is True

    def test_is_valid_archon_id_false(self) -> None:
        """is_valid_archon_id returns False for invalid ID."""
        stub = ArchonPoolStub()

        assert stub.is_valid_archon_id(uuid4()) is False


class TestArchonPoolStubHelpers:
    """Test stub helper methods."""

    def test_add_archon(self) -> None:
        """add_archon adds an Archon to the pool."""
        stub = ArchonPoolStub(populate_canonical=False)
        archon = create_test_archon("NewArchon")

        stub.add_archon(archon)

        assert stub.get_archon_count() == 1
        assert stub.get_archon_by_name("NewArchon") == archon

    def test_remove_archon(self) -> None:
        """remove_archon removes an Archon from the pool."""
        stub = ArchonPoolStub()
        initial_count = stub.get_archon_count()

        result = stub.remove_archon(FATE_ARCHON_AMON.id)

        assert result is True
        assert stub.get_archon_count() == initial_count - 1
        assert stub.get_archon_by_id(FATE_ARCHON_AMON.id) is None

    def test_remove_archon_not_found(self) -> None:
        """remove_archon returns False when Archon not found."""
        stub = ArchonPoolStub()

        result = stub.remove_archon(uuid4())

        assert result is False

    def test_clear(self) -> None:
        """clear removes all Archons and operations."""
        stub = ArchonPoolStub()
        stub.select_archons(uuid4())

        stub.clear()

        assert stub.get_archon_count() == 0
        assert stub.get_operation_count() == 0

    def test_clear_operations(self) -> None:
        """clear_operations clears only operations, preserves Archons."""
        stub = ArchonPoolStub()
        stub.select_archons(uuid4())

        stub.clear_operations()

        assert stub.get_archon_count() == 7  # Archons preserved
        assert stub.get_operation_count() == 0


class TestArchonPoolStubOperationTracking:
    """Test operation tracking for test assertions."""

    def test_operations_tracked(self) -> None:
        """All operations are tracked."""
        stub = ArchonPoolStub()
        stub.clear_operations()

        stub.get_archon_by_name("Amon")
        stub.get_archon_by_id(FATE_ARCHON_AMON.id)
        stub.list_all_archons()
        stub.select_archons(uuid4())

        assert stub.get_operation_count() == 4

    def test_get_operations_by_type(self) -> None:
        """get_operations_by_type filters operations."""
        stub = ArchonPoolStub()
        stub.clear_operations()

        stub.get_archon_by_name("Amon")
        stub.get_archon_by_name("Leraje")
        stub.list_all_archons()

        name_ops = stub.get_operations_by_type("get_archon_by_name")
        assert len(name_ops) == 2

    def test_was_petition_selected(self) -> None:
        """was_petition_selected checks if selection was made."""
        stub = ArchonPoolStub()
        stub.clear_operations()
        petition_id = uuid4()

        assert stub.was_petition_selected(petition_id) is False

        stub.select_archons(petition_id)

        assert stub.was_petition_selected(petition_id) is True

    def test_get_selection_for_petition(self) -> None:
        """get_selection_for_petition returns selected Archon names."""
        stub = ArchonPoolStub()
        stub.clear_operations()
        petition_id = uuid4()

        assert stub.get_selection_for_petition(petition_id) is None

        selected = stub.select_archons(petition_id)
        result = stub.get_selection_for_petition(petition_id)

        assert result is not None
        assert result == [a.name for a in selected]


class TestCreateTestArchon:
    """Test create_test_archon helper function."""

    def test_creates_valid_archon(self) -> None:
        """create_test_archon creates a valid FateArchon."""
        archon = create_test_archon("TestName")

        assert archon.name == "TestName"
        assert archon.title == "Test Marquis of TestName"
        assert archon.deliberation_style == DeliberationStyle.PRAGMATIC_MODERATOR

    def test_custom_style(self) -> None:
        """create_test_archon accepts custom style."""
        archon = create_test_archon(
            "Custom",
            style=DeliberationStyle.ADVERSARIAL_CHALLENGER,
        )

        assert archon.deliberation_style == DeliberationStyle.ADVERSARIAL_CHALLENGER

    def test_custom_id(self) -> None:
        """create_test_archon accepts custom ID."""
        custom_id = uuid4()
        archon = create_test_archon("WithId", archon_id=custom_id)

        assert archon.id == custom_id
