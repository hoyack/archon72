"""Unit tests for FateArchon domain model (Story 0.7, HP-11).

Tests:
- FateArchon creation and validation
- Immutability (frozen dataclass)
- Deliberation styles
- System prompt building
- Canonical Fate Archon pool
- Lookup functions
"""

from uuid import uuid4

import pytest

from src.domain.models.fate_archon import (
    FATE_ARCHON_AMON,
    FATE_ARCHON_BY_ID,
    FATE_ARCHON_BY_NAME,
    FATE_ARCHON_IDS,
    FATE_ARCHON_LERAJE,
    THREE_FATES_POOL,
    DeliberationStyle,
    FateArchon,
    get_fate_archon_by_id,
    get_fate_archon_by_name,
    is_valid_fate_archon_id,
    list_fate_archons,
)


class TestFateArchonCreation:
    """Test FateArchon instance creation."""

    def test_valid_creation(self) -> None:
        """Valid FateArchon is created with all fields."""
        archon_id = uuid4()
        archon = FateArchon(
            id=archon_id,
            name="TestArchon",
            title="Marquis of Testing",
            deliberation_style=DeliberationStyle.PRAGMATIC_MODERATOR,
            system_prompt_template="You are a test Archon.",
            backstory="A test backstory.",
        )

        assert archon.id == archon_id
        assert archon.name == "TestArchon"
        assert archon.title == "Marquis of Testing"
        assert archon.deliberation_style == DeliberationStyle.PRAGMATIC_MODERATOR
        assert archon.system_prompt_template == "You are a test Archon."
        assert archon.backstory == "A test backstory."

    def test_creation_without_backstory(self) -> None:
        """FateArchon can be created without backstory."""
        archon = FateArchon(
            id=uuid4(),
            name="NoBackstory",
            title="Marquis of Nothing",
            deliberation_style=DeliberationStyle.WISDOM_SEEKER,
            system_prompt_template="You are a test Archon.",
        )

        assert archon.backstory is None

    def test_empty_name_raises_error(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            FateArchon(
                id=uuid4(),
                name="",
                title="Marquis",
                deliberation_style=DeliberationStyle.RECONCILER,
                system_prompt_template="Test prompt",
            )

    def test_empty_title_raises_error(self) -> None:
        """Empty title raises ValueError."""
        with pytest.raises(ValueError, match="title cannot be empty"):
            FateArchon(
                id=uuid4(),
                name="Test",
                title="",
                deliberation_style=DeliberationStyle.RECONCILER,
                system_prompt_template="Test prompt",
            )

    def test_empty_system_prompt_raises_error(self) -> None:
        """Empty system prompt raises ValueError."""
        with pytest.raises(ValueError, match="system_prompt_template cannot be empty"):
            FateArchon(
                id=uuid4(),
                name="Test",
                title="Marquis",
                deliberation_style=DeliberationStyle.RECONCILER,
                system_prompt_template="",
            )

    def test_name_too_long_raises_error(self) -> None:
        """Name exceeding max length raises ValueError."""
        with pytest.raises(ValueError, match="name exceeds maximum length"):
            FateArchon(
                id=uuid4(),
                name="A" * 51,  # MAX_NAME_LENGTH = 50
                title="Marquis",
                deliberation_style=DeliberationStyle.RECONCILER,
                system_prompt_template="Test prompt",
            )

    def test_title_too_long_raises_error(self) -> None:
        """Title exceeding max length raises ValueError."""
        with pytest.raises(ValueError, match="title exceeds maximum length"):
            FateArchon(
                id=uuid4(),
                name="Test",
                title="A" * 201,  # MAX_TITLE_LENGTH = 200
                deliberation_style=DeliberationStyle.RECONCILER,
                system_prompt_template="Test prompt",
            )

    def test_backstory_too_long_raises_error(self) -> None:
        """Backstory exceeding max length raises ValueError."""
        with pytest.raises(ValueError, match="Backstory exceeds maximum length"):
            FateArchon(
                id=uuid4(),
                name="Test",
                title="Marquis",
                deliberation_style=DeliberationStyle.RECONCILER,
                system_prompt_template="Test prompt",
                backstory="A" * 2001,  # MAX_BACKSTORY_LENGTH = 2000
            )


class TestFateArchonImmutability:
    """Test FateArchon is immutable (frozen)."""

    def test_cannot_modify_name(self) -> None:
        """Cannot modify name after creation."""
        archon = FateArchon(
            id=uuid4(),
            name="Original",
            title="Marquis",
            deliberation_style=DeliberationStyle.RECONCILER,
            system_prompt_template="Test prompt",
        )

        with pytest.raises(AttributeError):
            archon.name = "Modified"  # type: ignore[misc]

    def test_cannot_modify_style(self) -> None:
        """Cannot modify deliberation_style after creation."""
        archon = FateArchon(
            id=uuid4(),
            name="Test",
            title="Marquis",
            deliberation_style=DeliberationStyle.RECONCILER,
            system_prompt_template="Test prompt",
        )

        with pytest.raises(AttributeError):
            archon.deliberation_style = DeliberationStyle.WISDOM_SEEKER  # type: ignore[misc]


class TestDeliberationStyles:
    """Test deliberation style enum."""

    def test_all_styles_exist(self) -> None:
        """All expected deliberation styles exist."""
        assert DeliberationStyle.CONSTITUTIONAL_PURIST.value == "constitutional_purist"
        assert DeliberationStyle.PRAGMATIC_MODERATOR.value == "pragmatic_moderator"
        assert (
            DeliberationStyle.ADVERSARIAL_CHALLENGER.value == "adversarial_challenger"
        )
        assert DeliberationStyle.WISDOM_SEEKER.value == "wisdom_seeker"
        assert DeliberationStyle.RECONCILER.value == "reconciler"

    def test_five_styles_available(self) -> None:
        """There are exactly 5 deliberation styles."""
        assert len(DeliberationStyle) == 5


class TestFateArchonProperties:
    """Test FateArchon property methods."""

    def test_display_name(self) -> None:
        """display_name returns formatted name with Marquis title."""
        archon = FateArchon(
            id=uuid4(),
            name="Amon",
            title="Marquis of Reconciliation",
            deliberation_style=DeliberationStyle.RECONCILER,
            system_prompt_template="Test prompt",
        )

        assert archon.display_name == "Marquis Amon"

    def test_full_designation(self) -> None:
        """full_designation returns name with full title."""
        archon = FateArchon(
            id=uuid4(),
            name="Leraje",
            title="Marquis of Conflict Resolution",
            deliberation_style=DeliberationStyle.ADVERSARIAL_CHALLENGER,
            system_prompt_template="Test prompt",
        )

        assert (
            archon.full_designation == "Marquis Leraje, Marquis of Conflict Resolution"
        )


class TestSystemPromptBuilding:
    """Test system prompt template building."""

    def test_build_prompt_no_context(self) -> None:
        """build_system_prompt returns template unchanged without context."""
        archon = FateArchon(
            id=uuid4(),
            name="Test",
            title="Marquis",
            deliberation_style=DeliberationStyle.RECONCILER,
            system_prompt_template="You are {archon_name}. Your role is to deliberate.",
        )

        result = archon.build_system_prompt()

        assert result == "You are {archon_name}. Your role is to deliberate."

    def test_build_prompt_with_context(self) -> None:
        """build_system_prompt substitutes context placeholders."""
        archon = FateArchon(
            id=uuid4(),
            name="Test",
            title="Marquis",
            deliberation_style=DeliberationStyle.RECONCILER,
            system_prompt_template="You are {archon_name}. Petition: {petition_text}",
        )

        result = archon.build_system_prompt(
            {
                "archon_name": "Amon",
                "petition_text": "Test petition content",
            }
        )

        assert result == "You are Amon. Petition: Test petition content"


class TestCanonicalFateArchons:
    """Test canonical Three Fates pool."""

    def test_pool_has_at_least_5_archons(self) -> None:
        """THREE_FATES_POOL has at least 5 Archons per requirements."""
        assert len(THREE_FATES_POOL) >= 5

    def test_pool_has_7_canonical_archons(self) -> None:
        """THREE_FATES_POOL has exactly 7 canonical Archons."""
        assert len(THREE_FATES_POOL) == 7

    def test_all_archons_have_unique_ids(self) -> None:
        """All Archons in pool have unique IDs."""
        ids = [a.id for a in THREE_FATES_POOL]
        assert len(ids) == len(set(ids))

    def test_all_archons_have_unique_names(self) -> None:
        """All Archons in pool have unique names."""
        names = [a.name for a in THREE_FATES_POOL]
        assert len(names) == len(set(names))

    def test_amon_is_reconciler(self) -> None:
        """Amon has RECONCILER style."""
        assert FATE_ARCHON_AMON.name == "Amon"
        assert FATE_ARCHON_AMON.deliberation_style == DeliberationStyle.RECONCILER

    def test_leraje_is_adversarial_challenger(self) -> None:
        """Leraje has ADVERSARIAL_CHALLENGER style."""
        assert FATE_ARCHON_LERAJE.name == "Leraje"
        assert (
            FATE_ARCHON_LERAJE.deliberation_style
            == DeliberationStyle.ADVERSARIAL_CHALLENGER
        )

    def test_lookup_by_id_works(self) -> None:
        """FATE_ARCHON_BY_ID lookup works for all Archons."""
        for archon in THREE_FATES_POOL:
            assert FATE_ARCHON_BY_ID[archon.id] == archon

    def test_lookup_by_name_works(self) -> None:
        """FATE_ARCHON_BY_NAME lookup works for all Archons."""
        for archon in THREE_FATES_POOL:
            assert FATE_ARCHON_BY_NAME[archon.name] == archon

    def test_fate_archon_ids_tuple(self) -> None:
        """FATE_ARCHON_IDS contains all pool IDs."""
        assert len(FATE_ARCHON_IDS) == len(THREE_FATES_POOL)
        for archon in THREE_FATES_POOL:
            assert archon.id in FATE_ARCHON_IDS


class TestLookupFunctions:
    """Test lookup helper functions."""

    def test_get_fate_archon_by_id_found(self) -> None:
        """get_fate_archon_by_id returns Archon when found."""
        result = get_fate_archon_by_id(FATE_ARCHON_AMON.id)

        assert result is not None
        assert result == FATE_ARCHON_AMON

    def test_get_fate_archon_by_id_not_found(self) -> None:
        """get_fate_archon_by_id returns None when not found."""
        result = get_fate_archon_by_id(uuid4())

        assert result is None

    def test_get_fate_archon_by_name_found(self) -> None:
        """get_fate_archon_by_name returns Archon when found."""
        result = get_fate_archon_by_name("Leraje")

        assert result is not None
        assert result == FATE_ARCHON_LERAJE

    def test_get_fate_archon_by_name_not_found(self) -> None:
        """get_fate_archon_by_name returns None when not found."""
        result = get_fate_archon_by_name("NonexistentArchon")

        assert result is None

    def test_list_fate_archons(self) -> None:
        """list_fate_archons returns list of all Archons."""
        result = list_fate_archons()

        assert len(result) == 7
        assert set(result) == set(THREE_FATES_POOL)

    def test_is_valid_fate_archon_id_true(self) -> None:
        """is_valid_fate_archon_id returns True for valid ID."""
        assert is_valid_fate_archon_id(FATE_ARCHON_AMON.id) is True

    def test_is_valid_fate_archon_id_false(self) -> None:
        """is_valid_fate_archon_id returns False for invalid ID."""
        assert is_valid_fate_archon_id(uuid4()) is False


class TestArchonSystemPrompts:
    """Test canonical Archon system prompts."""

    def test_all_archons_have_deliberation_header(self) -> None:
        """All canonical Archons have deliberation prompt header."""
        for archon in THREE_FATES_POOL:
            assert "Three Fates deliberation" in archon.system_prompt_template
            assert "CONSTITUTIONAL CONTEXT" in archon.system_prompt_template
            assert "{archon_name}" in archon.system_prompt_template
            assert "{petition_context}" in archon.system_prompt_template

    def test_all_archons_have_backstory(self) -> None:
        """All canonical Archons have backstory."""
        for archon in THREE_FATES_POOL:
            assert archon.backstory is not None
            assert len(archon.backstory) > 0
