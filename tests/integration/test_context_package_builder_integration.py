"""Integration tests for context package builder (Story 2A.3).

Tests cover:
- End-to-end package building workflow
- Hash verification across serialization
- Stub equivalence with real service
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.context_package_builder_service import (
    ContextPackageBuilderService,
)
from src.domain.models.deliberation_context_package import (
    DeliberationContextPackage,
)
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.context_package_builder_stub import (
    ContextPackageBuilderStub,
)


class TestEndToEndPackageBuilding:
    """Integration tests for complete package building workflow."""

    @pytest.fixture
    def full_petition(self) -> PetitionSubmission:
        """Create a petition with all fields populated."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.CESSATION,
            text="This is a comprehensive petition requesting review of cessation protocols.",
            state=PetitionState.DELIBERATING,
            submitter_id=uuid4(),
            realm="safety",
            co_signer_count=42,
        )

    @pytest.fixture
    def full_session(self, full_petition) -> DeliberationSession:
        """Create a session for the petition."""
        return DeliberationSession.create(
            session_id=uuid4(),
            petition_id=full_petition.id,
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

    def test_build_serialize_deserialize_verify(self, full_petition, full_session):
        """Test complete workflow: build -> serialize -> deserialize -> verify."""
        builder = ContextPackageBuilderService()

        # Build package
        package = builder.build_package(full_petition, full_session)

        # Serialize to JSON
        json_str = package.to_canonical_json()

        # Deserialize
        restored = DeliberationContextPackage.from_json(json_str)

        # Verify hash is still valid
        assert restored.verify_hash() is True
        assert restored.content_hash == package.content_hash

    def test_hash_survives_json_roundtrip(self, full_petition, full_session):
        """Test that hash remains valid after JSON roundtrip."""
        builder = ContextPackageBuilderService()
        package = builder.build_package(full_petition, full_session)

        # Multiple roundtrips
        json1 = package.to_canonical_json()
        restored1 = DeliberationContextPackage.from_json(json1)

        json2 = restored1.to_canonical_json()
        restored2 = DeliberationContextPackage.from_json(json2)

        # All should have same hash and verify correctly
        assert package.content_hash == restored1.content_hash == restored2.content_hash
        assert restored2.verify_hash() is True

    def test_package_contains_all_petition_data(self, full_petition, full_session):
        """Test that package contains all petition information."""
        builder = ContextPackageBuilderService()
        package = builder.build_package(full_petition, full_session)

        # Verify all petition data preserved
        assert package.petition_id == full_petition.id
        assert package.petition_text == full_petition.text
        assert package.petition_type == full_petition.type.value
        assert package.co_signer_count == full_petition.co_signer_count
        assert package.submitter_id == full_petition.submitter_id
        assert package.realm == full_petition.realm
        assert package.submitted_at == full_petition.created_at

    def test_package_contains_all_session_data(self, full_petition, full_session):
        """Test that package contains all session information."""
        builder = ContextPackageBuilderService()
        package = builder.build_package(full_petition, full_session)

        # Verify all session data preserved
        assert package.session_id == full_session.session_id
        assert package.assigned_archons == full_session.assigned_archons


class TestStubEquivalence:
    """Tests verifying stub produces equivalent results to real service."""

    @pytest.fixture
    def petition(self) -> PetitionSubmission:
        """Create a test petition."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition for stub equivalence.",
            state=PetitionState.DELIBERATING,
        )

    @pytest.fixture
    def session(self, petition) -> DeliberationSession:
        """Create a session for the petition."""
        return DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

    def test_stub_produces_valid_package(self, petition, session):
        """Test that stub produces valid, verifiable packages."""
        stub = ContextPackageBuilderStub()
        package = stub.build_package(petition, session)

        assert package.verify_hash() is True
        assert package.petition_id == petition.id
        assert package.session_id == session.session_id

    def test_stub_tracks_built_packages(self, petition, session):
        """Test that stub tracks packages for test assertions."""
        stub = ContextPackageBuilderStub()

        package1 = stub.build_package(petition, session)

        assert stub.get_package_count() == 1
        assert stub.get_built_packages() == [package1]

    def test_stub_with_fixed_time_is_deterministic(self, petition, session):
        """Test that stub with fixed time produces identical packages."""
        fixed_time = datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)
        stub = ContextPackageBuilderStub(fixed_build_time=fixed_time)

        package1 = stub.build_package(petition, session)
        stub.clear()  # Reset tracking
        package2 = stub.build_package(petition, session)

        # With fixed time, hashes should be identical
        assert package1.content_hash == package2.content_hash
        assert package1.built_at == package2.built_at == fixed_time

    def test_stub_clear_resets_tracking(self, petition, session):
        """Test that stub.clear() resets package tracking."""
        stub = ContextPackageBuilderStub()

        stub.build_package(petition, session)
        assert stub.get_package_count() == 1

        stub.clear()
        assert stub.get_package_count() == 0
        assert stub.get_built_packages() == []


class TestCanonicalJsonDeterminism:
    """Tests for canonical JSON determinism."""

    def test_canonical_json_is_sorted(self):
        """Test that canonical JSON has sorted keys."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test",
            state=PetitionState.DELIBERATING,
        )
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        builder = ContextPackageBuilderService()
        package = builder.build_package(petition, session)
        json_str = package.to_canonical_json()

        # Parse and verify keys are sorted
        parsed = json.loads(json_str)
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_canonical_json_is_compact(self):
        """Test that canonical JSON has no unnecessary whitespace."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test",
            state=PetitionState.DELIBERATING,
        )
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        builder = ContextPackageBuilderService()
        package = builder.build_package(petition, session)
        json_str = package.to_canonical_json()

        # No pretty-print whitespace
        assert "\n" not in json_str
        assert "  " not in json_str  # No indentation
        assert ": " not in json_str  # No space after colon


class TestHashIntegrity:
    """Tests for content hash integrity verification."""

    def test_tampered_content_fails_verification(self):
        """Test that modifying content after hash fails verification."""
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Original text",
            state=PetitionState.DELIBERATING,
        )
        session = DeliberationSession.create(
            session_id=uuid4(),
            petition_id=petition.id,
            assigned_archons=(uuid4(), uuid4(), uuid4()),
        )

        builder = ContextPackageBuilderService()
        package = builder.build_package(petition, session)

        # Serialize
        data = package.to_dict()

        # Tamper with content
        data["petition_text"] = "Tampered text"

        # Recreate package with original hash but tampered content
        tampered = DeliberationContextPackage.from_dict(data)

        # Should fail verification
        assert tampered.verify_hash() is False

    def test_hash_changes_with_different_co_signer_count(self):
        """Test that hash changes when co-signer count differs."""
        archons = (uuid4(), uuid4(), uuid4())
        petition_id = uuid4()

        petition1 = PetitionSubmission(
            id=petition_id,
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.DELIBERATING,
            co_signer_count=5,
        )
        petition2 = PetitionSubmission(
            id=petition_id,
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.DELIBERATING,
            co_signer_count=10,  # Different count
        )

        session_id = uuid4()
        session1 = DeliberationSession.create(
            session_id=session_id,
            petition_id=petition_id,
            assigned_archons=archons,
        )
        session2 = DeliberationSession.create(
            session_id=session_id,
            petition_id=petition_id,
            assigned_archons=archons,
        )

        # Use fixed time for determinism
        fixed_time = datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)
        stub = ContextPackageBuilderStub(fixed_build_time=fixed_time)

        package1 = stub.build_package(petition1, session1)
        stub.clear()
        package2 = stub.build_package(petition2, session2)

        # Hashes should differ due to different co_signer_count
        assert package1.content_hash != package2.content_hash
