"""Integration tests for Integrity Case Artifact (Story 7.10, FR144).

Tests end-to-end integration of the Integrity Case Artifact:
- Observer API access without authentication
- JSON-LD response format
- Version history and amendment tracking
- Post-cessation read-only access (CT-13)

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- FR42: Public read access without authentication
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability (post-cessation access)
"""

from datetime import datetime

import pytest

from src.application.services.integrity_case_service import IntegrityCaseService
from src.domain.models.integrity_case import (
    REQUIRED_CT_REFERENCES,
    GuaranteeCategory,
    IntegrityGuarantee,
)
from src.infrastructure.stubs.integrity_case_repository_stub import (
    IntegrityCaseRepositoryStub,
)


class TestIntegrityCaseArtifactAccess:
    """Integration tests for public access to Integrity Case Artifact (FR42)."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_get_artifact_no_auth_required(
        self, service: IntegrityCaseService
    ) -> None:
        """FR42: Artifact should be accessible without authentication."""
        # No authentication provided - should work
        artifact = await service.get_artifact()

        assert artifact is not None
        assert len(artifact.guarantees) == 20

    @pytest.mark.asyncio
    async def test_artifact_contains_all_cts(
        self, service: IntegrityCaseService
    ) -> None:
        """FR144: All 15 CTs must be documented in artifact."""
        artifact = await service.get_artifact()

        covered_cts = {
            g.ct_reference for g in artifact.guarantees if g.ct_reference is not None
        }

        for ct in REQUIRED_CT_REFERENCES:
            assert ct in covered_cts, f"Missing CT: {ct}"

    @pytest.mark.asyncio
    async def test_artifact_json_ld_format(self, service: IntegrityCaseService) -> None:
        """FR144, FR50: Artifact should be available in JSON-LD format."""
        json_ld = await service.get_artifact_jsonld()

        # Verify JSON-LD structure
        assert "@context" in json_ld
        assert json_ld["@type"] == "integrity:IntegrityCaseArtifact"
        assert "guarantees" in json_ld

        # Verify guarantees have proper JSON-LD types
        for guarantee in json_ld["guarantees"]:
            assert guarantee["@type"] == "integrity:Guarantee"
            assert "guarantee_id" in guarantee
            assert "mechanism" in guarantee
            assert "invalidation_conditions" in guarantee


class TestIntegrityCaseArtifactCompleteness:
    """Integration tests for artifact completeness (FR144)."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_all_guarantees_have_mechanisms(
        self, service: IntegrityCaseService
    ) -> None:
        """FR144: All guarantees must document enforcement mechanisms."""
        artifact = await service.get_artifact()

        for guarantee in artifact.guarantees:
            assert len(guarantee.mechanism) > 0, (
                f"Guarantee {guarantee.guarantee_id} missing mechanism"
            )

    @pytest.mark.asyncio
    async def test_all_guarantees_have_invalidation_conditions(
        self, service: IntegrityCaseService
    ) -> None:
        """FR144: All guarantees must document invalidation conditions."""
        artifact = await service.get_artifact()

        for guarantee in artifact.guarantees:
            assert len(guarantee.invalidation_conditions) > 0, (
                f"Guarantee {guarantee.guarantee_id} missing invalidation conditions"
            )

    @pytest.mark.asyncio
    async def test_constitutional_guarantees_marked_correctly(
        self, service: IntegrityCaseService
    ) -> None:
        """Constitutional guarantees must have is_constitutional=True."""
        artifact = await service.get_artifact()

        constitutional = [g for g in artifact.guarantees if g.ct_reference is not None]

        for g in constitutional:
            assert g.is_constitutional is True, (
                f"Guarantee {g.guarantee_id} should be constitutional"
            )
            assert g.category == GuaranteeCategory.CONSTITUTIONAL

    @pytest.mark.asyncio
    async def test_validate_completeness_returns_empty(
        self, service: IntegrityCaseService
    ) -> None:
        """FR144: Completeness validation should pass for full artifact."""
        missing = await service.validate_completeness()

        assert missing == [], f"Missing CTs: {missing}"


class TestIntegrityCaseArtifactVersioning:
    """Integration tests for artifact versioning (FR144)."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.fixture
    def new_guarantee(self) -> IntegrityGuarantee:
        """Create a new guarantee for testing."""
        return IntegrityGuarantee(
            guarantee_id="fr-integration-test",
            category=GuaranteeCategory.FUNCTIONAL,
            name="Integration Test Guarantee",
            description="A test guarantee for integration testing.",
            fr_reference="FR999",
            mechanism="Test mechanism for integration testing",
            invalidation_conditions=("Test condition",),
            is_constitutional=False,
        )

    @pytest.mark.asyncio
    async def test_version_history_preserved(
        self, service: IntegrityCaseService
    ) -> None:
        """FR144: Version history should be maintained."""
        history = await service.get_version_history()

        assert len(history) >= 1
        version, timestamp = history[0]
        assert version == "1.0.0"
        assert isinstance(timestamp, datetime)

    @pytest.mark.asyncio
    async def test_amendment_creates_new_version(
        self,
        service: IntegrityCaseService,
        new_guarantee: IntegrityGuarantee,
    ) -> None:
        """FR144: Amendment should create new version."""
        # Get initial version
        artifact = await service.get_artifact()
        initial_version = artifact.version

        # Apply amendment
        await service.update_for_amendment(
            amendment_event_id="amend-integration-test",
            guarantees_added=(new_guarantee,),
            reason="Integration test amendment",
        )

        # Verify new version created
        updated = await service.get_artifact()
        assert updated.version != initial_version
        assert updated.get_guarantee("fr-integration-test") is not None

    @pytest.mark.asyncio
    async def test_version_history_grows_with_amendments(
        self,
        service: IntegrityCaseService,
        new_guarantee: IntegrityGuarantee,
    ) -> None:
        """FR144: Version history should grow with amendments."""
        initial_history = await service.get_version_history()

        # Apply amendment
        await service.update_for_amendment(
            amendment_event_id="amend-history-test",
            guarantees_added=(new_guarantee,),
            reason="Test amendment for history",
        )

        # Verify history grew
        updated_history = await service.get_version_history()
        assert len(updated_history) == len(initial_history) + 1


class TestIntegrityCasePostCessation:
    """Integration tests for post-cessation access (CT-13)."""

    @pytest.mark.asyncio
    async def test_read_access_after_cessation(self) -> None:
        """CT-13: Read access must be preserved after cessation."""
        repository = IntegrityCaseRepositoryStub()
        service = IntegrityCaseService(repository=repository)

        # Simulate cessation
        repository.set_ceased(True)

        # Read access should still work
        artifact = await service.get_artifact()
        assert artifact is not None
        assert len(artifact.guarantees) == 20

    @pytest.mark.asyncio
    async def test_jsonld_access_after_cessation(self) -> None:
        """CT-13: JSON-LD access must be preserved after cessation."""
        repository = IntegrityCaseRepositoryStub()
        service = IntegrityCaseService(repository=repository)

        # Simulate cessation
        repository.set_ceased(True)

        # JSON-LD access should still work
        json_ld = await service.get_artifact_jsonld()
        assert json_ld is not None
        assert "@context" in json_ld

    @pytest.mark.asyncio
    async def test_history_access_after_cessation(self) -> None:
        """CT-13: Version history access must be preserved after cessation."""
        repository = IntegrityCaseRepositoryStub()
        service = IntegrityCaseService(repository=repository)

        # Simulate cessation
        repository.set_ceased(True)

        # History access should still work
        history = await service.get_version_history()
        assert len(history) >= 1

    @pytest.mark.asyncio
    async def test_write_blocked_after_cessation(self) -> None:
        """CT-13: Write access must be blocked after cessation."""
        repository = IntegrityCaseRepositoryStub()
        service = IntegrityCaseService(repository=repository)

        # Simulate cessation
        repository.set_ceased(True)

        # Create a guarantee for testing
        new_guarantee = IntegrityGuarantee(
            guarantee_id="fr-post-cessation",
            category=GuaranteeCategory.FUNCTIONAL,
            name="Post Cessation Test",
            description="Should not be added after cessation.",
            fr_reference="FR998",
            mechanism="Test mechanism",
            invalidation_conditions=("Test",),
            is_constitutional=False,
        )

        # Write should be blocked
        from src.domain.errors.ceased import SystemCeasedError

        with pytest.raises(SystemCeasedError):
            await service.update_for_amendment(
                amendment_event_id="amend-post-cessation",
                guarantees_added=(new_guarantee,),
                reason="Should fail",
            )


class TestIntegrityCaseGuaranteeContent:
    """Integration tests for guarantee content requirements (FR144)."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_ct1_has_hash_chain_mechanism(
        self, service: IntegrityCaseService
    ) -> None:
        """CT-1 guarantee should document hash chain mechanism."""
        guarantee = await service.get_guarantee("ct-1-audit-trail")

        assert guarantee is not None
        mechanism_lower = guarantee.mechanism.lower()
        assert "hash" in mechanism_lower, "CT-1 should mention hash chain"

    @pytest.mark.asyncio
    async def test_ct11_has_halt_mechanism(self, service: IntegrityCaseService) -> None:
        """CT-11 guarantee should document halt over degrade."""
        guarantee = await service.get_guarantee("ct-11-loud-failure")

        assert guarantee is not None
        desc_lower = guarantee.description.lower()
        assert "halt" in desc_lower or "failure" in desc_lower

    @pytest.mark.asyncio
    async def test_ct12_has_witness_mechanism(
        self, service: IntegrityCaseService
    ) -> None:
        """CT-12 guarantee should document witness accountability."""
        guarantee = await service.get_guarantee("ct-12-witnessing")

        assert guarantee is not None
        mechanism_lower = guarantee.mechanism.lower()
        assert "witness" in mechanism_lower

    @pytest.mark.asyncio
    async def test_ct13_has_integrity_priority(
        self, service: IntegrityCaseService
    ) -> None:
        """CT-13 guarantee should document integrity over availability."""
        guarantee = await service.get_guarantee("ct-13-integrity-priority")

        assert guarantee is not None
        desc_lower = guarantee.description.lower()
        assert "integrity" in desc_lower

    @pytest.mark.asyncio
    async def test_fr_observer_has_public_access(
        self, service: IntegrityCaseService
    ) -> None:
        """FR observer guarantee should document public access."""
        guarantee = await service.get_guarantee("fr-observer-access")

        assert guarantee is not None
        desc_lower = guarantee.description.lower()
        assert "public" in desc_lower or "unauthenticated" in desc_lower
