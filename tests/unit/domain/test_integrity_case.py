"""Unit tests for Integrity Case Artifact domain models (Story 7.10, FR144).

Tests domain models for the Integrity Case Artifact which documents
all constitutional guarantees, their enforcement mechanisms, and
invalidation conditions.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability (post-cessation access)
"""

from datetime import datetime, timezone

import pytest

from src.domain.models.integrity_case import (
    INTEGRITY_CASE_JSON_LD_CONTEXT,
    REQUIRED_CT_REFERENCES,
    GuaranteeCategory,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)


class TestIntegrityGuarantee:
    """Tests for IntegrityGuarantee domain model."""

    def test_create_constitutional_guarantee(self) -> None:
        """IntegrityGuarantee should create a constitutional constraint guarantee."""
        guarantee = IntegrityGuarantee(
            guarantee_id="ct-1-audit-trail",
            category=GuaranteeCategory.CONSTITUTIONAL,
            name="Append-Only Audit Trail",
            description="All system state changes are recorded in an immutable log.",
            fr_reference="FR5",
            ct_reference="CT-1",
            mechanism="Hash-chained event store with cryptographic witness signatures",
            invalidation_conditions=(
                "Hash chain discontinuity detected",
                "Witness signature verification fails",
            ),
            is_constitutional=True,
        )

        assert guarantee.guarantee_id == "ct-1-audit-trail"
        assert guarantee.category == GuaranteeCategory.CONSTITUTIONAL
        assert guarantee.ct_reference == "CT-1"
        assert guarantee.is_constitutional is True
        assert len(guarantee.invalidation_conditions) == 2

    def test_create_functional_guarantee(self) -> None:
        """IntegrityGuarantee should create a functional requirement guarantee."""
        guarantee = IntegrityGuarantee(
            guarantee_id="fr-44-public-access",
            category=GuaranteeCategory.FUNCTIONAL,
            name="Public Read Access",
            description="Observer API provides unauthenticated read access.",
            fr_reference="FR44",
            ct_reference=None,
            mechanism="Observer API with no authentication middleware",
            invalidation_conditions=("Authentication added to Observer API",),
            is_constitutional=False,
        )

        assert guarantee.guarantee_id == "fr-44-public-access"
        assert guarantee.category == GuaranteeCategory.FUNCTIONAL
        assert guarantee.ct_reference is None
        assert guarantee.is_constitutional is False

    def test_is_constitutional_explicit_field(self) -> None:
        """is_constitutional should be explicitly set on the model."""
        constitutional = IntegrityGuarantee(
            guarantee_id="test-ct",
            category=GuaranteeCategory.CONSTITUTIONAL,
            name="Test",
            description="Test description",
            fr_reference="FR1",
            ct_reference="CT-1",
            mechanism="Test mechanism",
            invalidation_conditions=("Test",),
            is_constitutional=True,
        )

        functional = IntegrityGuarantee(
            guarantee_id="test-func",
            category=GuaranteeCategory.FUNCTIONAL,
            name="Test",
            description="Test description",
            fr_reference="FR1",
            mechanism="Test mechanism",
            invalidation_conditions=("Test",),
            is_constitutional=False,
        )

        assert constitutional.is_constitutional is True
        assert functional.is_constitutional is False

    def test_to_dict_serialization(self) -> None:
        """to_dict should serialize all fields correctly."""
        guarantee = IntegrityGuarantee(
            guarantee_id="ct-test",
            category=GuaranteeCategory.CONSTITUTIONAL,
            name="Test",
            description="Description",
            fr_reference="FR1",
            ct_reference="CT-1",
            adr_reference="ADR-1",
            mechanism="Mechanism",
            invalidation_conditions=("Condition",),
            is_constitutional=True,
        )

        data = guarantee.to_dict()

        assert data["guarantee_id"] == "ct-test"
        assert data["category"] == "constitutional"
        assert data["ct_reference"] == "CT-1"
        assert data["adr_reference"] == "ADR-1"
        assert data["invalidation_conditions"] == ["Condition"]
        assert data["is_constitutional"] is True

    def test_constitutional_category_requires_ct_reference(self) -> None:
        """Constitutional category should require ct_reference."""
        with pytest.raises(
            ValueError, match="Constitutional guarantees require ct_reference"
        ):
            IntegrityGuarantee(
                guarantee_id="bad-ct",
                category=GuaranteeCategory.CONSTITUTIONAL,
                name="Bad CT",
                description="Missing ct_reference",
                fr_reference="FR1",
                ct_reference=None,  # Missing!
                mechanism="Mechanism",
                invalidation_conditions=("Condition",),
                is_constitutional=True,
            )


class TestIntegrityCaseArtifact:
    """Tests for IntegrityCaseArtifact domain model."""

    @pytest.fixture
    def sample_guarantees(self) -> tuple[IntegrityGuarantee, ...]:
        """Create sample guarantees for testing."""
        return (
            IntegrityGuarantee(
                guarantee_id="ct-1-audit-trail",
                category=GuaranteeCategory.CONSTITUTIONAL,
                name="Audit Trail",
                description="Append-only audit trail",
                fr_reference="FR5",
                ct_reference="CT-1",
                mechanism="Hash-chained event store",
                invalidation_conditions=("Hash discontinuity",),
                is_constitutional=True,
            ),
            IntegrityGuarantee(
                guarantee_id="fr-44-public-access",
                category=GuaranteeCategory.FUNCTIONAL,
                name="Public Access",
                description="Observer API access",
                fr_reference="FR44",
                mechanism="No auth middleware",
                invalidation_conditions=("Auth added",),
                is_constitutional=False,
            ),
        )

    def test_create_artifact(
        self, sample_guarantees: tuple[IntegrityGuarantee, ...]
    ) -> None:
        """IntegrityCaseArtifact should create with valid guarantees."""
        now = datetime.now(timezone.utc)
        artifact = IntegrityCaseArtifact(
            guarantees=sample_guarantees,
            version="1.0.0",
            schema_version="1.0.0",
            constitution_version="1.0.0",
            created_at=now,
            last_updated=now,
        )

        assert len(artifact.guarantees) == 2
        assert artifact.version == "1.0.0"

    def test_get_guarantee_found(
        self, sample_guarantees: tuple[IntegrityGuarantee, ...]
    ) -> None:
        """get_guarantee should return guarantee if found."""
        artifact = IntegrityCaseArtifact(
            guarantees=sample_guarantees,
            version="1.0.0",
            schema_version="1.0.0",
            constitution_version="1.0.0",
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        result = artifact.get_guarantee("ct-1-audit-trail")

        assert result is not None
        assert result.guarantee_id == "ct-1-audit-trail"
        assert result.ct_reference == "CT-1"

    def test_get_guarantee_not_found(
        self, sample_guarantees: tuple[IntegrityGuarantee, ...]
    ) -> None:
        """get_guarantee should return None if not found."""
        artifact = IntegrityCaseArtifact(
            guarantees=sample_guarantees,
            version="1.0.0",
            schema_version="1.0.0",
            constitution_version="1.0.0",
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        result = artifact.get_guarantee("nonexistent")

        assert result is None

    def test_get_by_category(
        self, sample_guarantees: tuple[IntegrityGuarantee, ...]
    ) -> None:
        """get_by_category should return only matching guarantees."""
        artifact = IntegrityCaseArtifact(
            guarantees=sample_guarantees,
            version="1.0.0",
            schema_version="1.0.0",
            constitution_version="1.0.0",
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        constitutional = artifact.get_by_category(GuaranteeCategory.CONSTITUTIONAL)
        functional = artifact.get_by_category(GuaranteeCategory.FUNCTIONAL)

        assert len(constitutional) == 1
        assert constitutional[0].ct_reference == "CT-1"
        assert len(functional) == 1
        assert functional[0].guarantee_id == "fr-44-public-access"

    def test_len_returns_guarantee_count(
        self, sample_guarantees: tuple[IntegrityGuarantee, ...]
    ) -> None:
        """__len__ should return correct count."""
        artifact = IntegrityCaseArtifact(
            guarantees=sample_guarantees,
            version="1.0.0",
            schema_version="1.0.0",
            constitution_version="1.0.0",
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
        )

        assert len(artifact) == 2

    def test_to_json_ld(
        self, sample_guarantees: tuple[IntegrityGuarantee, ...]
    ) -> None:
        """to_json_ld should return JSON-LD formatted dict."""
        now = datetime.now(timezone.utc)
        artifact = IntegrityCaseArtifact(
            guarantees=sample_guarantees,
            version="1.0.0",
            schema_version="1.0.0",
            constitution_version="1.0.0",
            created_at=now,
            last_updated=now,
        )

        json_ld = artifact.to_json_ld()

        assert "@context" in json_ld
        assert json_ld["@type"] == "integrity:IntegrityCaseArtifact"
        assert json_ld["version"] == "1.0.0"
        assert len(json_ld["guarantees"]) == 2
        assert json_ld["guarantees"][0]["@type"] == "integrity:Guarantee"


class TestIntegrityCaseConstants:
    """Tests for module-level constants."""

    def test_required_ct_references_all_fifteen(self) -> None:
        """REQUIRED_CT_REFERENCES should contain all 15 CTs."""
        assert len(REQUIRED_CT_REFERENCES) == 15
        assert "CT-1" in REQUIRED_CT_REFERENCES
        assert "CT-15" in REQUIRED_CT_REFERENCES

    def test_json_ld_context_structure(self) -> None:
        """JSON-LD context should have proper structure."""
        context = INTEGRITY_CASE_JSON_LD_CONTEXT["@context"]

        assert "integrity" in context
        assert "archon72.org" in context["integrity"]
        assert "guarantee_id" in context
        assert "invalidation_conditions" in context


class TestGuaranteeCategory:
    """Tests for GuaranteeCategory enum."""

    def test_all_categories_defined(self) -> None:
        """All required guarantee categories should be defined."""
        assert GuaranteeCategory.CONSTITUTIONAL.value == "constitutional"
        assert GuaranteeCategory.FUNCTIONAL.value == "functional"
        assert GuaranteeCategory.OPERATIONAL.value == "operational"

    def test_category_count(self) -> None:
        """Exactly 3 categories should be defined."""
        assert len(GuaranteeCategory) == 3
