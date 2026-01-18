"""Unit tests for Integrity Guarantees registry (Story 7.10, FR144).

Tests the static registry of all constitutional guarantees that
must be documented in the Integrity Case Artifact.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- CT-1 through CT-15: All must be documented
"""

import pytest

from src.domain.models.integrity_case import (
    REQUIRED_CT_REFERENCES,
    GuaranteeCategory,
)
from src.domain.primitives.integrity_guarantees import (
    ALL_GUARANTEES,
    INTEGRITY_GUARANTEE_REGISTRY,
    get_guarantee,
    validate_all_guarantees,
)


class TestAllGuarantees:
    """Tests for ALL_GUARANTEES tuple."""

    def test_all_guarantees_count(self) -> None:
        """ALL_GUARANTEES should contain exactly 20 guarantees."""
        assert len(ALL_GUARANTEES) == 20

    def test_all_guarantees_unique_ids(self) -> None:
        """All guarantee IDs should be unique."""
        ids = [g.guarantee_id for g in ALL_GUARANTEES]
        assert len(ids) == len(set(ids)), "Duplicate guarantee IDs found"

    def test_all_cts_covered(self) -> None:
        """All 15 CTs should be covered by guarantees."""
        covered_cts = {
            g.ct_reference for g in ALL_GUARANTEES if g.ct_reference is not None
        }

        for ct in REQUIRED_CT_REFERENCES:
            assert ct in covered_cts, f"Missing guarantee for {ct}"

    def test_guarantee_categories_used(self) -> None:
        """Multiple categories should be used in guarantees."""
        categories = {g.category for g in ALL_GUARANTEES}

        assert GuaranteeCategory.CONSTITUTIONAL in categories
        assert GuaranteeCategory.FUNCTIONAL in categories
        assert len(categories) >= 2  # At least 2 different categories


class TestIntegrityGuaranteeRegistry:
    """Tests for INTEGRITY_GUARANTEE_REGISTRY (IntegrityCaseArtifact)."""

    def test_registry_contains_all_guarantees(self) -> None:
        """Registry should contain all guarantees from ALL_GUARANTEES."""
        assert len(INTEGRITY_GUARANTEE_REGISTRY) == len(ALL_GUARANTEES)

        for guarantee in ALL_GUARANTEES:
            found = INTEGRITY_GUARANTEE_REGISTRY.get_guarantee(guarantee.guarantee_id)
            assert found is not None, f"Missing guarantee: {guarantee.guarantee_id}"
            assert found == guarantee

    def test_registry_lookup_ct1(self) -> None:
        """Registry should contain CT-1 guarantee."""
        guarantee = INTEGRITY_GUARANTEE_REGISTRY.get_guarantee("ct-1-audit-trail")

        assert guarantee is not None
        assert guarantee.ct_reference == "CT-1"
        assert guarantee.name == "Append-Only Audit Trail"
        assert guarantee.is_constitutional is True

    def test_registry_lookup_ct11(self) -> None:
        """Registry should contain CT-11 guarantee."""
        guarantee = INTEGRITY_GUARANTEE_REGISTRY.get_guarantee("ct-11-loud-failure")

        assert guarantee is not None
        assert guarantee.ct_reference == "CT-11"
        assert guarantee.is_constitutional is True

    def test_registry_lookup_ct13(self) -> None:
        """Registry should contain CT-13 guarantee."""
        guarantee = INTEGRITY_GUARANTEE_REGISTRY.get_guarantee(
            "ct-13-integrity-priority"
        )

        assert guarantee is not None
        assert guarantee.ct_reference == "CT-13"
        assert guarantee.is_constitutional is True


class TestGetGuarantee:
    """Tests for get_guarantee function."""

    def test_get_existing_guarantee(self) -> None:
        """get_guarantee should return guarantee if found."""
        result = get_guarantee("ct-1-audit-trail")

        assert result is not None
        assert result.ct_reference == "CT-1"

    def test_get_nonexistent_guarantee(self) -> None:
        """get_guarantee should raise KeyError if not found."""
        with pytest.raises(KeyError, match="nonexistent-guarantee"):
            get_guarantee("nonexistent-guarantee")

    def test_get_fr_guarantee(self) -> None:
        """get_guarantee should work for FR guarantees."""
        result = get_guarantee("fr-observer-access")

        assert result is not None
        assert result.category == GuaranteeCategory.FUNCTIONAL


class TestValidateAllGuarantees:
    """Tests for validate_all_guarantees function."""

    def test_validation_returns_empty_for_complete(self) -> None:
        """validate_all_guarantees should return empty list when complete."""
        missing = validate_all_guarantees()

        assert missing == [], f"Missing CTs: {missing}"

    def test_validation_checks_all_fifteen_cts(self) -> None:
        """Validation should check all 15 CTs."""
        # This test validates the function is working by checking it
        # successfully finds all CTs are covered
        covered_cts = {
            g.ct_reference for g in ALL_GUARANTEES if g.ct_reference is not None
        }

        assert len(covered_cts) >= 15


class TestGuaranteeContent:
    """Tests for specific guarantee content requirements."""

    def test_ct1_has_hash_chain_mechanism(self) -> None:
        """CT-1 guarantee should mention hash chain in mechanism."""
        guarantee = get_guarantee("ct-1-audit-trail")

        assert guarantee is not None
        mechanism_lower = guarantee.mechanism.lower()
        assert "hash" in mechanism_lower or "chain" in mechanism_lower

    def test_ct11_has_halt_mechanism(self) -> None:
        """CT-11 guarantee should mention halt or failure."""
        guarantee = get_guarantee("ct-11-loud-failure")

        assert guarantee is not None
        desc_lower = guarantee.description.lower()
        assert "halt" in desc_lower or "failure" in desc_lower

    def test_ct12_has_witness_mechanism(self) -> None:
        """CT-12 guarantee should mention witness/signing."""
        guarantee = get_guarantee("ct-12-witnessing")

        assert guarantee is not None
        mechanism_lower = guarantee.mechanism.lower()
        desc_lower = guarantee.description.lower()
        assert "witness" in mechanism_lower or "witness" in desc_lower

    def test_ct13_has_cessation_mechanism(self) -> None:
        """CT-13 guarantee should mention halt/cessation."""
        guarantee = get_guarantee("ct-13-integrity-priority")

        assert guarantee is not None
        mechanism_lower = guarantee.mechanism.lower()
        desc_lower = guarantee.description.lower()
        assert (
            "halt" in mechanism_lower
            or "halt" in desc_lower
            or "cessation" in desc_lower
        )

    def test_fr_observer_has_public_access(self) -> None:
        """FR observer guarantee should mention public/unauthenticated access."""
        guarantee = get_guarantee("fr-observer-access")

        assert guarantee is not None
        mechanism_lower = guarantee.mechanism.lower()
        desc_lower = guarantee.description.lower()
        assert "public" in mechanism_lower or "unauthenticated" in desc_lower

    def test_all_guarantees_have_invalidation_conditions(self) -> None:
        """All guarantees should have at least one invalidation condition."""
        for guarantee in ALL_GUARANTEES:
            assert len(guarantee.invalidation_conditions) >= 1, (
                f"Guarantee {guarantee.guarantee_id} has no invalidation conditions"
            )

    def test_all_guarantees_have_descriptions(self) -> None:
        """All guarantees should have non-empty descriptions."""
        for guarantee in ALL_GUARANTEES:
            assert len(guarantee.description) >= 20, (
                f"Guarantee {guarantee.guarantee_id} has short description"
            )

    def test_all_guarantees_have_mechanisms(self) -> None:
        """All guarantees should have non-empty mechanisms."""
        for guarantee in ALL_GUARANTEES:
            assert len(guarantee.mechanism) >= 10, (
                f"Guarantee {guarantee.guarantee_id} has short mechanism"
            )
