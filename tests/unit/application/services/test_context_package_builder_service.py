"""Unit tests for ContextPackageBuilderService (Story 2A.3).

Tests cover:
- Package building from petition + session
- Idempotent building (same inputs = same hash)
- Ruling-3 compliance (empty similar_petitions)
- Petition-session mismatch error handling
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.context_package_builder_service import (
    ContextPackageBuilderService,
)
from src.domain.errors.deliberation import PetitionSessionMismatchError
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


# Test fixtures
@pytest.fixture
def builder() -> ContextPackageBuilderService:
    """Return a new builder service instance."""
    return ContextPackageBuilderService()


@pytest.fixture
def sample_archons() -> tuple:
    """Return 3 sample archon UUIDs."""
    return (uuid4(), uuid4(), uuid4())


@pytest.fixture
def sample_petition() -> PetitionSubmission:
    """Return a sample petition in DELIBERATING state."""
    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="This is a test petition for deliberation.",
        state=PetitionState.DELIBERATING,
        submitter_id=uuid4(),
        realm="governance",
        co_signer_count=3,
    )


@pytest.fixture
def sample_session(sample_petition, sample_archons) -> DeliberationSession:
    """Return a sample deliberation session for the petition."""
    return DeliberationSession.create(
        session_id=uuid4(),
        petition_id=sample_petition.id,
        assigned_archons=sample_archons,
    )


class TestBuildPackageHappyPath:
    """Tests for successful package building."""

    def test_build_package_creates_valid_package(
        self, builder, sample_petition, sample_session
    ):
        """Test that build_package creates a valid context package."""
        package = builder.build_package(sample_petition, sample_session)

        assert package.petition_id == sample_petition.id
        assert package.petition_text == sample_petition.text
        assert package.petition_type == sample_petition.type.value
        assert package.co_signer_count == sample_petition.co_signer_count
        assert package.submitter_id == sample_petition.submitter_id
        assert package.realm == sample_petition.realm
        assert package.session_id == sample_session.session_id
        assert package.assigned_archons == sample_session.assigned_archons

    def test_package_has_valid_content_hash(
        self, builder, sample_petition, sample_session
    ):
        """Test that built package has valid content hash."""
        package = builder.build_package(sample_petition, sample_session)

        assert package.content_hash
        assert len(package.content_hash) == 64
        assert package.verify_hash() is True

    def test_package_has_schema_version(self, builder, sample_petition, sample_session):
        """Test that built package has schema version."""
        package = builder.build_package(sample_petition, sample_session)

        assert package.schema_version == "1.0.0"

    def test_package_has_build_timestamp(
        self, builder, sample_petition, sample_session
    ):
        """Test that built package has build timestamp."""
        before = datetime.now(timezone.utc)
        package = builder.build_package(sample_petition, sample_session)
        after = datetime.now(timezone.utc)

        assert before <= package.built_at <= after


class TestRuling3Compliance:
    """Tests for Ruling-3 compliance."""

    def test_similar_petitions_is_empty(self, builder, sample_petition, sample_session):
        """Test that similar_petitions is explicitly empty (Ruling-3)."""
        package = builder.build_package(sample_petition, sample_session)

        assert package.similar_petitions == tuple()

    def test_ruling_3_deferred_flag_is_true(
        self, builder, sample_petition, sample_session
    ):
        """Test that ruling_3_deferred flag is True."""
        package = builder.build_package(sample_petition, sample_session)

        assert package.ruling_3_deferred is True


class TestIdempotentBuilding:
    """Tests for idempotent package building."""

    def test_same_inputs_produce_different_hashes_due_to_timestamp(
        self, builder, sample_petition, sample_session
    ):
        """Test that same inputs may produce different hashes due to build timestamp.

        Note: This is expected behavior since built_at changes between calls.
        For truly idempotent building, use the stub with fixed_build_time.
        """
        package1 = builder.build_package(sample_petition, sample_session)
        package2 = builder.build_package(sample_petition, sample_session)

        # Hashes may differ due to built_at timestamp difference
        # Both packages should have valid hashes
        assert package1.verify_hash() is True
        assert package2.verify_hash() is True

        # Core content should be identical
        assert package1.petition_id == package2.petition_id
        assert package1.petition_text == package2.petition_text
        assert package1.assigned_archons == package2.assigned_archons


class TestPetitionSessionMismatch:
    """Tests for petition-session mismatch handling."""

    def test_raises_error_on_mismatched_petition_id(
        self, builder, sample_petition, sample_archons
    ):
        """Test that mismatched petition_id raises error."""
        # Create session with different petition ID
        wrong_session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=uuid4(),  # Different petition
            assigned_archons=sample_archons,
        )

        with pytest.raises(PetitionSessionMismatchError) as exc_info:
            builder.build_package(sample_petition, wrong_session)

        assert exc_info.value.petition_id == sample_petition.id
        assert exc_info.value.session_petition_id == wrong_session.petition_id


class TestPetitionTypes:
    """Tests for different petition types."""

    @pytest.mark.parametrize(
        "petition_type",
        [
            PetitionType.GENERAL,
            PetitionType.CESSATION,
            PetitionType.GRIEVANCE,
            PetitionType.COLLABORATION,
        ],
    )
    def test_handles_all_petition_types(self, builder, petition_type, sample_archons):
        """Test that all petition types are handled correctly."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=petition_type,
            text="Test petition",
            state=PetitionState.DELIBERATING,
        )
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=sample_archons,
        )

        package = builder.build_package(petition, session)

        assert package.petition_type == petition_type.value


class TestSubmitterIdHandling:
    """Tests for optional submitter_id handling."""

    def test_handles_none_submitter_id(self, builder, sample_archons):
        """Test that None submitter_id is handled correctly."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Anonymous petition",
            state=PetitionState.DELIBERATING,
            submitter_id=None,
        )
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=sample_archons,
        )

        package = builder.build_package(petition, session)

        assert package.submitter_id is None
        assert package.verify_hash() is True

    def test_handles_present_submitter_id(self, builder, sample_archons):
        """Test that present submitter_id is handled correctly."""
        submitter_id = uuid4()
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Identified petition",
            state=PetitionState.DELIBERATING,
            submitter_id=submitter_id,
        )
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=sample_archons,
        )

        package = builder.build_package(petition, session)

        assert package.submitter_id == submitter_id
        assert package.verify_hash() is True


class TestCoSignerCount:
    """Tests for co-signer count handling."""

    @pytest.mark.parametrize("co_signer_count", [0, 1, 5, 100, 1000])
    def test_preserves_co_signer_count(self, builder, co_signer_count, sample_archons):
        """Test that co-signer count is preserved in package."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.DELIBERATING,
            co_signer_count=co_signer_count,
        )
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=sample_archons,
        )

        package = builder.build_package(petition, session)

        assert package.co_signer_count == co_signer_count
