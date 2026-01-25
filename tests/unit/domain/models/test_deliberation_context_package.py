"""Unit tests for DeliberationContextPackage domain model (Story 2A.3).

Tests cover:
- Package creation and validation
- JSON serialization/deserialization
- Content hash computation and verification
- Ruling-3 compliance (empty similar_petitions)
- Schema version presence
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.deliberation_context_package import (
    CONTEXT_PACKAGE_SCHEMA_VERSION,
    DeliberationContextPackage,
    compute_content_hash,
)


# Test fixtures
@pytest.fixture
def sample_archons() -> tuple:
    """Return 3 sample archon UUIDs."""
    return (uuid4(), uuid4(), uuid4())


@pytest.fixture
def sample_package(sample_archons) -> DeliberationContextPackage:
    """Return a sample valid context package."""
    now = datetime.now(timezone.utc)
    petition_id = uuid4()
    session_id = uuid4()

    # Build hashable dict for hash computation
    hashable_dict = {
        "petition_id": str(petition_id),
        "petition_text": "Test petition content",
        "petition_type": "GENERAL",
        "co_signer_count": 5,
        "submitter_id": None,
        "realm": "default",
        "submitted_at": now.isoformat(),
        "session_id": str(session_id),
        "assigned_archons": [str(a) for a in sample_archons],
        "similar_petitions": [],
        "ruling_3_deferred": True,
        "severity_tier": "low",
        "severity_signals": [],
        "schema_version": CONTEXT_PACKAGE_SCHEMA_VERSION,
        "built_at": now.isoformat(),
    }
    content_hash = compute_content_hash(hashable_dict)

    return DeliberationContextPackage(
        petition_id=petition_id,
        petition_text="Test petition content",
        petition_type="GENERAL",
        co_signer_count=5,
        submitter_id=None,
        realm="default",
        submitted_at=now,
        session_id=session_id,
        assigned_archons=sample_archons,
        similar_petitions=tuple(),
        ruling_3_deferred=True,
        schema_version=CONTEXT_PACKAGE_SCHEMA_VERSION,
        built_at=now,
        content_hash=content_hash,
    )


class TestDeliberationContextPackageCreation:
    """Tests for package creation and validation."""

    def test_create_valid_package(self, sample_archons):
        """Test creating a valid package."""
        now = datetime.now(timezone.utc)
        package = DeliberationContextPackage(
            petition_id=uuid4(),
            petition_text="Test petition",
            petition_type="GENERAL",
            co_signer_count=0,
            submitter_id=None,
            realm="default",
            submitted_at=now,
            session_id=uuid4(),
            assigned_archons=sample_archons,
            similar_petitions=tuple(),
            ruling_3_deferred=True,
            schema_version=CONTEXT_PACKAGE_SCHEMA_VERSION,
            built_at=now,
            content_hash="a" * 64,
        )

        assert package.petition_type == "GENERAL"
        assert package.co_signer_count == 0
        assert len(package.assigned_archons) == 3
        assert package.ruling_3_deferred is True

    def test_package_is_frozen(self, sample_package):
        """Test that package is immutable (frozen dataclass)."""
        with pytest.raises(Exception):  # FrozenInstanceError
            sample_package.petition_text = "Modified"  # type: ignore

    def test_requires_exactly_3_archons(self):
        """Test that exactly 3 archons are required."""
        now = datetime.now(timezone.utc)

        # Too few archons
        with pytest.raises(ValueError, match="Exactly 3 archons required"):
            DeliberationContextPackage(
                petition_id=uuid4(),
                petition_text="Test",
                petition_type="GENERAL",
                co_signer_count=0,
                submitter_id=None,
                realm="default",
                submitted_at=now,
                session_id=uuid4(),
                assigned_archons=(uuid4(), uuid4()),  # Only 2
                built_at=now,
                content_hash="a" * 64,
            )

    def test_rejects_duplicate_archons(self):
        """Test that duplicate archon IDs are rejected."""
        now = datetime.now(timezone.utc)
        same_id = uuid4()

        with pytest.raises(ValueError, match="Duplicate archon IDs"):
            DeliberationContextPackage(
                petition_id=uuid4(),
                petition_text="Test",
                petition_type="GENERAL",
                co_signer_count=0,
                submitter_id=None,
                realm="default",
                submitted_at=now,
                session_id=uuid4(),
                assigned_archons=(same_id, same_id, uuid4()),
                built_at=now,
                content_hash="a" * 64,
            )

    def test_rejects_invalid_schema_version(self, sample_archons):
        """Test that invalid schema version is rejected."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="Schema version must be"):
            DeliberationContextPackage(
                petition_id=uuid4(),
                petition_text="Test",
                petition_type="GENERAL",
                co_signer_count=0,
                submitter_id=None,
                realm="default",
                submitted_at=now,
                session_id=uuid4(),
                assigned_archons=sample_archons,
                schema_version="2.0.0",  # Invalid
                built_at=now,
                content_hash="a" * 64,
            )

    def test_rejects_invalid_content_hash_length(self, sample_archons):
        """Test that invalid content hash length is rejected."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="Content hash must be 64 hex chars"):
            DeliberationContextPackage(
                petition_id=uuid4(),
                petition_text="Test",
                petition_type="GENERAL",
                co_signer_count=0,
                submitter_id=None,
                realm="default",
                submitted_at=now,
                session_id=uuid4(),
                assigned_archons=sample_archons,
                built_at=now,
                content_hash="tooshort",
            )


class TestRuling3Compliance:
    """Tests for Ruling-3 compliance (similar petitions deferred to M2)."""

    def test_similar_petitions_empty_by_default(self, sample_package):
        """Test that similar_petitions is empty by default."""
        assert sample_package.similar_petitions == tuple()

    def test_ruling_3_deferred_flag_is_true(self, sample_package):
        """Test that ruling_3_deferred flag is True."""
        assert sample_package.ruling_3_deferred is True

    def test_rejects_similar_petitions_in_m1(self, sample_archons):
        """Test that non-empty similar_petitions with deferred=False is rejected."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="Cannot have similar_petitions in M1"):
            DeliberationContextPackage(
                petition_id=uuid4(),
                petition_text="Test",
                petition_type="GENERAL",
                co_signer_count=0,
                submitter_id=None,
                realm="default",
                submitted_at=now,
                session_id=uuid4(),
                assigned_archons=sample_archons,
                similar_petitions=("some_ref",),  # type: ignore
                ruling_3_deferred=False,  # Invalid combination
                built_at=now,
                content_hash="a" * 64,
            )


class TestJsonSerialization:
    """Tests for JSON serialization and deserialization."""

    def test_to_dict(self, sample_package):
        """Test conversion to dictionary."""
        data = sample_package.to_dict()

        assert "petition_id" in data
        assert "petition_text" in data
        assert "content_hash" in data
        assert "schema_version" in data
        assert data["ruling_3_deferred"] is True
        assert data["similar_petitions"] == []

    def test_to_canonical_json(self, sample_package):
        """Test canonical JSON serialization."""
        json_str = sample_package.to_canonical_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["petition_type"] == "GENERAL"

        # Should be deterministic (sorted keys, no whitespace)
        assert '"assigned_archons":' in json_str
        assert "  " not in json_str  # No whitespace

    def test_from_dict_roundtrip(self, sample_package):
        """Test dictionary roundtrip."""
        data = sample_package.to_dict()
        restored = DeliberationContextPackage.from_dict(data)

        assert restored.petition_id == sample_package.petition_id
        assert restored.content_hash == sample_package.content_hash

    def test_from_json_roundtrip(self, sample_package):
        """Test JSON roundtrip."""
        json_str = sample_package.to_canonical_json()
        restored = DeliberationContextPackage.from_json(json_str)

        assert restored.petition_id == sample_package.petition_id
        assert restored.content_hash == sample_package.content_hash
        assert restored.assigned_archons == sample_package.assigned_archons


class TestContentHash:
    """Tests for content hash computation and verification."""

    def test_verify_hash_returns_true_for_valid_hash(self, sample_package):
        """Test that verify_hash returns True for valid package."""
        assert sample_package.verify_hash() is True

    def test_verify_hash_returns_false_for_empty_hash(self, sample_archons):
        """Test that verify_hash returns False for empty hash."""
        now = datetime.now(timezone.utc)
        package = DeliberationContextPackage(
            petition_id=uuid4(),
            petition_text="Test",
            petition_type="GENERAL",
            co_signer_count=0,
            submitter_id=None,
            realm="default",
            submitted_at=now,
            session_id=uuid4(),
            assigned_archons=sample_archons,
            built_at=now,
            content_hash="",  # Empty
        )

        assert package.verify_hash() is False

    def test_compute_content_hash_is_deterministic(self):
        """Test that same input produces same hash."""
        data = {
            "petition_id": "123",
            "text": "test",
            "count": 5,
        }

        hash1 = compute_content_hash(data)
        hash2 = compute_content_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256

    def test_different_input_produces_different_hash(self):
        """Test that different input produces different hash."""
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}

        hash1 = compute_content_hash(data1)
        hash2 = compute_content_hash(data2)

        assert hash1 != hash2


class TestSchemaVersion:
    """Tests for schema version field."""

    def test_schema_version_is_1_1_0(self, sample_package):
        """Test that schema version is 1.1.0."""
        assert sample_package.schema_version == "1.1.0"
        assert sample_package.schema_version == CONTEXT_PACKAGE_SCHEMA_VERSION

    def test_schema_version_in_json(self, sample_package):
        """Test that schema version is included in JSON."""
        json_str = sample_package.to_canonical_json()
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "1.1.0"


class TestPetitionTypes:
    """Tests for different petition types."""

    @pytest.mark.parametrize(
        "petition_type",
        ["GENERAL", "CESSATION", "GRIEVANCE", "COLLABORATION"],
    )
    def test_accepts_valid_petition_types(self, petition_type, sample_archons):
        """Test that valid petition types are accepted."""
        now = datetime.now(timezone.utc)
        package = DeliberationContextPackage(
            petition_id=uuid4(),
            petition_text="Test",
            petition_type=petition_type,
            co_signer_count=0,
            submitter_id=None,
            realm="default",
            submitted_at=now,
            session_id=uuid4(),
            assigned_archons=sample_archons,
            built_at=now,
            content_hash="a" * 64,
        )

        assert package.petition_type == petition_type
