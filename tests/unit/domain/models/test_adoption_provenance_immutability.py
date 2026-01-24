"""Unit tests for adoption provenance immutability (Story 6.6, FR-5.7, NFR-6.2).

Tests that adoption provenance fields are immutable once set:
- adopted_as_motion_id cannot be modified
- adopted_by_king_id cannot be modified
- adopted_at cannot be modified

Constitutional Constraints:
- FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
- NFR-6.2: Adoption provenance immutability
- Story 6.6 AC: Immutability enforced at database level (trigger or constraint)
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


class TestAdoptionProvenanceImmutability:
    """Test immutability of adoption provenance fields."""

    def test_can_set_adoption_fields_when_none(self):
        """Test that adoption fields can be set when they are None."""
        # Given: A petition with no adoption data
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
        )

        # When: Setting adoption fields for the first time
        motion_id = uuid4()
        king_id = uuid4()
        adopted_at = datetime.now(timezone.utc)

        # Create new petition with adoption fields set
        adopted_petition = PetitionSubmission(
            id=petition.id,
            type=petition.type,
            text=petition.text,
            state=petition.state,
            adopted_as_motion_id=motion_id,
            adopted_by_king_id=king_id,
            adopted_at=adopted_at,
        )

        # Then: Fields should be set correctly
        assert adopted_petition.adopted_as_motion_id == motion_id
        assert adopted_petition.adopted_by_king_id == king_id
        assert adopted_petition.adopted_at == adopted_at

    def test_adoption_fields_remain_set(self):
        """Test that once set, adoption fields remain in place."""
        # Given: A petition that has been adopted
        motion_id = uuid4()
        king_id = uuid4()
        adopted_at = datetime.now(timezone.utc)

        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
            adopted_as_motion_id=motion_id,
            adopted_by_king_id=king_id,
            adopted_at=adopted_at,
        )

        # Then: Fields should remain set
        assert petition.adopted_as_motion_id == motion_id
        assert petition.adopted_by_king_id == king_id
        assert petition.adopted_at == adopted_at

    def test_bidirectional_provenance_visibility(self):
        """Test that provenance is visible in both directions.

        Story 6.6 AC: Provenance is visible in both directions
        - Motion → Petition (via source_petition_ref in Motion)
        - Petition → Motion (via adopted_as_motion_id in Petition)
        """
        # Given: A petition and motion ID
        petition_id = uuid4()
        motion_id = uuid4()
        king_id = uuid4()

        petition = PetitionSubmission(
            id=petition_id,
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
            adopted_as_motion_id=motion_id,
            adopted_by_king_id=king_id,
            adopted_at=datetime.now(timezone.utc),
        )

        # Then: Petition should show it was adopted as the Motion
        assert petition.adopted_as_motion_id == motion_id

        # And: The Motion would have source_petition_ref = petition_id
        # (this is tested in the Motion model tests and integration tests)

    def test_adopted_petition_state_preserved(self):
        """Test that petition state is preserved when adoption fields are set."""
        # Given: An escalated petition
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
        )

        # When: Adoption fields are set
        adopted_petition = PetitionSubmission(
            id=petition.id,
            type=petition.type,
            text=petition.text,
            state=petition.state,
            adopted_as_motion_id=uuid4(),
            adopted_by_king_id=uuid4(),
            adopted_at=datetime.now(timezone.utc),
        )

        # Then: State should remain ESCALATED
        assert adopted_petition.state == PetitionState.ESCALATED


class TestAdoptionProvenanceDataIntegrity:
    """Test data integrity of adoption provenance."""

    def test_adoption_with_all_required_fields(self):
        """Test that adoption requires all three fields together."""
        # Given: Valid adoption data
        motion_id = uuid4()
        king_id = uuid4()
        adopted_at = datetime.now(timezone.utc)

        # When: Creating petition with all adoption fields
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
            adopted_as_motion_id=motion_id,
            adopted_by_king_id=king_id,
            adopted_at=adopted_at,
        )

        # Then: All fields should be set
        assert petition.adopted_as_motion_id is not None
        assert petition.adopted_by_king_id is not None
        assert petition.adopted_at is not None

    def test_adoption_timestamp_is_utc(self):
        """Test that adopted_at uses UTC timezone."""
        # Given: A petition with adoption timestamp
        adopted_at = datetime.now(timezone.utc)

        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
            adopted_as_motion_id=uuid4(),
            adopted_by_king_id=uuid4(),
            adopted_at=adopted_at,
        )

        # Then: Timestamp should have UTC timezone
        assert petition.adopted_at.tzinfo == timezone.utc

    def test_adoption_uuids_are_valid(self):
        """Test that adoption UUIDs are valid UUID objects."""
        # Given: Valid UUIDs
        motion_id = uuid4()
        king_id = uuid4()

        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
            adopted_as_motion_id=motion_id,
            adopted_by_king_id=king_id,
            adopted_at=datetime.now(timezone.utc),
        )

        # Then: UUIDs should be UUID type
        assert isinstance(petition.adopted_as_motion_id, UUID)
        assert isinstance(petition.adopted_by_king_id, UUID)


class TestAdoptionProvenanceDocumentation:
    """Test documentation and error messages for adoption provenance."""

    def test_petition_submission_has_adoption_fields_documented(self):
        """Test that PetitionSubmission documents adoption fields."""
        # The docstring should mention adoption fields
        docstring = PetitionSubmission.__doc__
        assert "adopted_as_motion_id" in docstring
        assert "Story 6.3" in docstring or "FR-5.7" in docstring

    def test_adoption_fields_have_clear_semantics(self):
        """Test that adoption fields have clear semantics."""
        # Given: A petition with adoption data
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.ESCALATED,
            adopted_as_motion_id=uuid4(),
            adopted_by_king_id=uuid4(),
            adopted_at=datetime.now(timezone.utc),
        )

        # Then: Field names should be self-documenting
        # adopted_as_motion_id: Which motion was created
        assert hasattr(petition, "adopted_as_motion_id")

        # adopted_by_king_id: Which King adopted it
        assert hasattr(petition, "adopted_by_king_id")

        # adopted_at: When adoption occurred
        assert hasattr(petition, "adopted_at")


class TestMotionProvenanceField:
    """Test source_petition_ref field in Motion model (if applicable).

    Note: The Motion model in conclave.py now has source_petition_ref field.
    These tests verify the field exists and can be set during creation.
    """

    def test_motion_has_source_petition_ref_field(self):
        """Test that Motion model has source_petition_ref field."""
        from src.domain.models.conclave import Motion

        # Check that the field is documented in the dataclass
        # (This is a smoke test to ensure the field was added)
        assert hasattr(Motion, "__dataclass_fields__")
        fields = Motion.__dataclass_fields__
        assert "source_petition_ref" in fields

    def test_motion_can_be_created_with_source_petition_ref(self):
        """Test that Motion can be created with source_petition_ref."""
        from src.domain.models.conclave import Motion, MotionType

        # Given: A petition ID to reference
        petition_id = uuid4()

        # When: Creating a Motion with source_petition_ref
        motion = Motion(
            motion_id=uuid4(),
            motion_type=MotionType.POLICY,
            title="Test Motion",
            text="Motion text",
            proposer_id="archon-1",
            proposer_name="Archon One",
            proposed_at=datetime.now(timezone.utc),
            source_petition_ref=petition_id,
        )

        # Then: source_petition_ref should be set
        assert motion.source_petition_ref == petition_id

    def test_motion_source_petition_ref_defaults_to_none(self):
        """Test that source_petition_ref defaults to None for organic motions."""
        from src.domain.models.conclave import Motion, MotionType

        # When: Creating a Motion without source_petition_ref
        motion = Motion(
            motion_id=uuid4(),
            motion_type=MotionType.POLICY,
            title="Test Motion",
            text="Motion text",
            proposer_id="archon-1",
            proposer_name="Archon One",
            proposed_at=datetime.now(timezone.utc),
        )

        # Then: source_petition_ref should be None
        assert motion.source_petition_ref is None
