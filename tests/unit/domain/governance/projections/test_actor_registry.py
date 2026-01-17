"""Unit tests for ActorRegistryRecord projection model.

Tests cover acceptance criteria for story consent-gov-1.5:
- AC4: Domain models for each projection record type
- Validation of actor types and branches
"""

from datetime import datetime, timezone

import pytest

from src.domain.governance.projections.actor_registry import ActorRegistryRecord


class TestActorRegistryRecordCreation:
    """Tests for ActorRegistryRecord creation and validation."""

    def test_valid_actor_registry_creation(self) -> None:
        """ActorRegistryRecord with valid data creates successfully."""
        now = datetime.now(timezone.utc)
        record = ActorRegistryRecord(
            actor_id="archon-42",
            actor_type="archon",
            branch="legislative",
            rank="tier-1",
            display_name="The Archon 42",
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        assert record.actor_id == "archon-42"
        assert record.actor_type == "archon"
        assert record.branch == "legislative"
        assert record.rank == "tier-1"
        assert record.display_name == "The Archon 42"
        assert record.active is True
        assert record.deactivated_at is None

    def test_actor_registry_record_is_immutable(self) -> None:
        """ActorRegistryRecord fields cannot be modified after creation."""
        now = datetime.now(timezone.utc)
        record = ActorRegistryRecord(
            actor_id="archon-42",
            actor_type="archon",
            branch="legislative",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )

        with pytest.raises(AttributeError):
            record.active = False  # type: ignore[misc]

    def test_invalid_actor_type_raises_error(self) -> None:
        """Invalid actor_type raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            ActorRegistryRecord(
                actor_id="invalid-1",
                actor_type="invalid_type",
                branch="legislative",
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
        assert "Invalid actor type" in str(exc_info.value)

    def test_invalid_branch_raises_error(self) -> None:
        """Invalid branch raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            ActorRegistryRecord(
                actor_id="archon-42",
                actor_type="archon",
                branch="invalid_branch",
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
        assert "Invalid branch" in str(exc_info.value)

    def test_inactive_without_deactivated_at_raises_error(self) -> None:
        """Inactive actor without deactivated_at raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            ActorRegistryRecord(
                actor_id="archon-42",
                actor_type="archon",
                branch="legislative",
                rank=None,
                display_name=None,
                active=False,
                created_at=now,
                deactivated_at=None,  # Missing deactivated_at
                last_event_sequence=1,
                updated_at=now,
            )
        assert "deactivated_at must be set when active is False" in str(exc_info.value)

    def test_active_with_deactivated_at_raises_error(self) -> None:
        """Active actor with deactivated_at raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            ActorRegistryRecord(
                actor_id="archon-42",
                actor_type="archon",
                branch="legislative",
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=now,  # Should be None when active
                last_event_sequence=1,
                updated_at=now,
            )
        assert "deactivated_at must be None when active is True" in str(exc_info.value)

    def test_negative_sequence_raises_error(self) -> None:
        """Negative last_event_sequence raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError) as exc_info:
            ActorRegistryRecord(
                actor_id="archon-42",
                actor_type="archon",
                branch="legislative",
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=None,
                last_event_sequence=-1,
                updated_at=now,
            )
        assert "non-negative" in str(exc_info.value)


class TestActorRegistryRecordValidTypes:
    """Tests for valid types enumeration."""

    def test_all_valid_actor_types_can_be_created(self) -> None:
        """All VALID_TYPES can be used to create records."""
        now = datetime.now(timezone.utc)
        for actor_type in ActorRegistryRecord.VALID_TYPES:
            # Get the default branch for this actor type
            branch = ActorRegistryRecord.TYPE_TO_BRANCH.get(actor_type, "legislative")
            record = ActorRegistryRecord(
                actor_id=f"{actor_type}-1",
                actor_type=actor_type,
                branch=branch,
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
            assert record.actor_type == actor_type

    def test_valid_types_contains_expected_values(self) -> None:
        """VALID_TYPES contains all expected actor types."""
        expected = {
            "archon", "king", "president", "duke", "earl",
            "prince", "marquis", "knight", "system"
        }
        assert ActorRegistryRecord.VALID_TYPES == frozenset(expected)

    def test_all_valid_branches_can_be_created(self) -> None:
        """All VALID_BRANCHES can be used to create records."""
        now = datetime.now(timezone.utc)
        for branch in ActorRegistryRecord.VALID_BRANCHES:
            record = ActorRegistryRecord(
                actor_id="archon-42",
                actor_type="archon",
                branch=branch,
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
            assert record.branch == branch

    def test_valid_branches_contains_expected_values(self) -> None:
        """VALID_BRANCHES contains all expected branches."""
        expected = {
            "legislative", "executive", "judicial",
            "advisory", "witness", "system"
        }
        assert ActorRegistryRecord.VALID_BRANCHES == frozenset(expected)


class TestActorRegistryRecordHelpers:
    """Tests for helper methods."""

    def test_is_active_returns_true_for_active_actor(self) -> None:
        """is_active returns True for active actor."""
        now = datetime.now(timezone.utc)
        record = ActorRegistryRecord(
            actor_id="archon-42",
            actor_type="archon",
            branch="legislative",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert record.is_active()

    def test_is_active_returns_false_for_inactive_actor(self) -> None:
        """is_active returns False for inactive actor."""
        now = datetime.now(timezone.utc)
        record = ActorRegistryRecord(
            actor_id="archon-42",
            actor_type="archon",
            branch="legislative",
            rank=None,
            display_name=None,
            active=False,
            created_at=now,
            deactivated_at=now,
            last_event_sequence=1,
            updated_at=now,
        )
        assert not record.is_active()

    def test_is_in_branch(self) -> None:
        """is_in_branch returns correct value."""
        now = datetime.now(timezone.utc)
        record = ActorRegistryRecord(
            actor_id="earl-1",
            actor_type="earl",
            branch="executive",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert record.is_in_branch("executive")
        assert not record.is_in_branch("legislative")

    def test_is_officer_for_officer_types(self) -> None:
        """is_officer returns True for officer types."""
        now = datetime.now(timezone.utc)
        officer_types = ["king", "president", "duke", "earl", "prince", "marquis", "knight"]

        for actor_type in officer_types:
            branch = ActorRegistryRecord.TYPE_TO_BRANCH.get(actor_type, "legislative")
            record = ActorRegistryRecord(
                actor_id=f"{actor_type}-1",
                actor_type=actor_type,
                branch=branch,
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
            assert record.is_officer()

    def test_is_officer_for_archon(self) -> None:
        """is_officer returns False for archon."""
        now = datetime.now(timezone.utc)
        record = ActorRegistryRecord(
            actor_id="archon-42",
            actor_type="archon",
            branch="legislative",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert not record.is_officer()

    def test_is_archon(self) -> None:
        """is_archon returns True only for archon type."""
        now = datetime.now(timezone.utc)
        archon_record = ActorRegistryRecord(
            actor_id="archon-42",
            actor_type="archon",
            branch="legislative",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert archon_record.is_archon()

        earl_record = ActorRegistryRecord(
            actor_id="earl-1",
            actor_type="earl",
            branch="executive",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert not earl_record.is_archon()

    def test_is_executive(self) -> None:
        """is_executive returns True for executive branch actors."""
        now = datetime.now(timezone.utc)
        executive_types = ["president", "duke", "earl"]

        for actor_type in executive_types:
            record = ActorRegistryRecord(
                actor_id=f"{actor_type}-1",
                actor_type=actor_type,
                branch="executive",
                rank=None,
                display_name=None,
                active=True,
                created_at=now,
                deactivated_at=None,
                last_event_sequence=1,
                updated_at=now,
            )
            assert record.is_executive()

    def test_is_judicial(self) -> None:
        """is_judicial returns True only for prince."""
        now = datetime.now(timezone.utc)
        prince_record = ActorRegistryRecord(
            actor_id="prince-1",
            actor_type="prince",
            branch="judicial",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert prince_record.is_judicial()

        earl_record = ActorRegistryRecord(
            actor_id="earl-1",
            actor_type="earl",
            branch="executive",
            rank=None,
            display_name=None,
            active=True,
            created_at=now,
            deactivated_at=None,
            last_event_sequence=1,
            updated_at=now,
        )
        assert not earl_record.is_judicial()

    def test_get_default_branch(self) -> None:
        """get_default_branch returns correct branch for actor types."""
        assert ActorRegistryRecord.get_default_branch("archon") == "legislative"
        assert ActorRegistryRecord.get_default_branch("king") == "legislative"
        assert ActorRegistryRecord.get_default_branch("president") == "executive"
        assert ActorRegistryRecord.get_default_branch("duke") == "executive"
        assert ActorRegistryRecord.get_default_branch("earl") == "executive"
        assert ActorRegistryRecord.get_default_branch("prince") == "judicial"
        assert ActorRegistryRecord.get_default_branch("marquis") == "advisory"
        assert ActorRegistryRecord.get_default_branch("knight") == "witness"
        assert ActorRegistryRecord.get_default_branch("system") == "system"

    def test_get_default_branch_unknown_type_raises(self) -> None:
        """get_default_branch raises ValueError for unknown type."""
        with pytest.raises(ValueError) as exc_info:
            ActorRegistryRecord.get_default_branch("unknown_type")
        assert "Unknown actor type" in str(exc_info.value)
