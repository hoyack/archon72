"""Unit tests for IntegrityCaseService (Story 7.10, FR144).

Tests the service layer for accessing and managing the
Integrity Case Artifact.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- FR42: Public read access without authentication
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability (post-cessation access)
"""

from datetime import datetime

import pytest

from src.application.services.integrity_case_service import IntegrityCaseService
from src.domain.events.integrity_case import (
    IntegrityCaseUpdatedEventPayload,
)
from src.domain.models.integrity_case import (
    GuaranteeCategory,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)
from src.infrastructure.stubs.integrity_case_repository_stub import (
    IntegrityCaseRepositoryStub,
)


class TestIntegrityCaseServiceGetArtifact:
    """Tests for IntegrityCaseService.get_artifact method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_get_artifact_returns_artifact(
        self, service: IntegrityCaseService
    ) -> None:
        """get_artifact should return IntegrityCaseArtifact."""
        artifact = await service.get_artifact()

        assert isinstance(artifact, IntegrityCaseArtifact)
        assert artifact.version is not None
        assert len(artifact.guarantees) > 0

    @pytest.mark.asyncio
    async def test_get_artifact_contains_all_guarantees(
        self, service: IntegrityCaseService
    ) -> None:
        """get_artifact should return all 20 guarantees."""
        artifact = await service.get_artifact()

        assert len(artifact.guarantees) == 20

    @pytest.mark.asyncio
    async def test_get_artifact_version_metadata(
        self, service: IntegrityCaseService
    ) -> None:
        """get_artifact should include version metadata."""
        artifact = await service.get_artifact()

        assert artifact.version == "1.0.0"
        assert artifact.schema_version == "1.0.0"
        assert artifact.constitution_version == "1.0.0"


class TestIntegrityCaseServiceGetJsonLd:
    """Tests for IntegrityCaseService.get_artifact_jsonld method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_get_jsonld_returns_dict(self, service: IntegrityCaseService) -> None:
        """get_artifact_jsonld should return dict with JSON-LD context."""
        json_ld = await service.get_artifact_jsonld()

        assert isinstance(json_ld, dict)
        assert "@context" in json_ld
        assert "@type" in json_ld

    @pytest.mark.asyncio
    async def test_get_jsonld_type_correct(self, service: IntegrityCaseService) -> None:
        """get_artifact_jsonld should have correct @type."""
        json_ld = await service.get_artifact_jsonld()

        assert json_ld["@type"] == "integrity:IntegrityCaseArtifact"

    @pytest.mark.asyncio
    async def test_get_jsonld_guarantees_have_type(
        self, service: IntegrityCaseService
    ) -> None:
        """get_artifact_jsonld guarantees should have @type."""
        json_ld = await service.get_artifact_jsonld()

        assert "guarantees" in json_ld
        assert len(json_ld["guarantees"]) > 0
        assert json_ld["guarantees"][0]["@type"] == "integrity:Guarantee"


class TestIntegrityCaseServiceGetGuarantee:
    """Tests for IntegrityCaseService.get_guarantee method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_get_guarantee_found(self, service: IntegrityCaseService) -> None:
        """get_guarantee should return guarantee if found."""
        guarantee = await service.get_guarantee("ct-1-audit-trail")

        assert guarantee is not None
        assert guarantee.guarantee_id == "ct-1-audit-trail"
        assert guarantee.ct_reference == "CT-1"

    @pytest.mark.asyncio
    async def test_get_guarantee_not_found(self, service: IntegrityCaseService) -> None:
        """get_guarantee should return None if not found."""
        guarantee = await service.get_guarantee("nonexistent")

        assert guarantee is None

    @pytest.mark.asyncio
    async def test_get_guarantee_fr(self, service: IntegrityCaseService) -> None:
        """get_guarantee should return FR guarantee."""
        guarantee = await service.get_guarantee("fr-observer-access")

        assert guarantee is not None
        assert guarantee.category == GuaranteeCategory.FUNCTIONAL


class TestIntegrityCaseServiceGetByCategory:
    """Tests for IntegrityCaseService.get_guarantees_by_category method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_get_constitutional_guarantees(
        self, service: IntegrityCaseService
    ) -> None:
        """get_guarantees_by_category should return constitutional guarantees."""
        guarantees = await service.get_guarantees_by_category(
            GuaranteeCategory.CONSTITUTIONAL
        )

        assert len(guarantees) == 15  # All 15 CTs
        for g in guarantees:
            assert g.category == GuaranteeCategory.CONSTITUTIONAL
            assert g.ct_reference is not None

    @pytest.mark.asyncio
    async def test_get_functional_guarantees(
        self, service: IntegrityCaseService
    ) -> None:
        """get_guarantees_by_category should return functional guarantees."""
        guarantees = await service.get_guarantees_by_category(
            GuaranteeCategory.FUNCTIONAL
        )

        assert len(guarantees) >= 1
        for g in guarantees:
            assert g.category == GuaranteeCategory.FUNCTIONAL


class TestIntegrityCaseServiceValidateCompleteness:
    """Tests for IntegrityCaseService.validate_completeness method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_validate_complete_artifact(
        self, service: IntegrityCaseService
    ) -> None:
        """validate_completeness should return empty list for complete artifact."""
        missing = await service.validate_completeness()

        assert missing == []

    @pytest.mark.asyncio
    async def test_validate_all_cts_covered(
        self, service: IntegrityCaseService
    ) -> None:
        """validate_completeness verifies all 15 CTs are covered."""
        # Get artifact and check CTs manually
        artifact = await service.get_artifact()
        covered_cts = {
            g.ct_reference for g in artifact.guarantees if g.ct_reference is not None
        }

        # All 15 CTs should be covered
        for i in range(1, 16):
            assert f"CT-{i}" in covered_cts


class TestIntegrityCaseServiceVersionHistory:
    """Tests for IntegrityCaseService.get_version_history method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.mark.asyncio
    async def test_get_version_history(self, service: IntegrityCaseService) -> None:
        """get_version_history should return version list."""
        history = await service.get_version_history()

        assert isinstance(history, list)
        assert len(history) >= 1  # At least initial version

        # First entry should be version 1.0.0
        version, timestamp = history[0]
        assert version == "1.0.0"
        assert isinstance(timestamp, datetime)


class TestIntegrityCaseServiceUpdateForAmendment:
    """Tests for IntegrityCaseService.update_for_amendment method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    @pytest.fixture
    def new_guarantee(self) -> IntegrityGuarantee:
        """Create a new guarantee for testing."""
        return IntegrityGuarantee(
            guarantee_id="fr-test-new",
            category=GuaranteeCategory.FUNCTIONAL,
            name="New Test Guarantee",
            description="A new test guarantee for testing updates.",
            fr_reference="FR999",
            mechanism="Test mechanism for validation",
            invalidation_conditions=("Test condition",),
            is_constitutional=False,
        )

    @pytest.mark.asyncio
    async def test_update_adds_guarantee(
        self, service: IntegrityCaseService, new_guarantee: IntegrityGuarantee
    ) -> None:
        """update_for_amendment should add new guarantee."""
        payload = await service.update_for_amendment(
            amendment_event_id="amend-123",
            guarantees_added=(new_guarantee,),
            reason="Added FR999 guarantee",
        )

        assert payload.artifact_version == "1.0.1"  # Incremented
        assert payload.previous_version == "1.0.0"
        assert "fr-test-new" in payload.guarantees_added

        # Verify guarantee was added
        artifact = await service.get_artifact()
        assert artifact.get_guarantee("fr-test-new") is not None

    @pytest.mark.asyncio
    async def test_update_returns_event_payload(
        self, service: IntegrityCaseService, new_guarantee: IntegrityGuarantee
    ) -> None:
        """update_for_amendment should return witnessable event payload."""
        payload = await service.update_for_amendment(
            amendment_event_id="amend-456",
            guarantees_added=(new_guarantee,),
            reason="Test update",
        )

        assert isinstance(payload, IntegrityCaseUpdatedEventPayload)
        assert payload.amendment_event_id == "amend-456"
        assert payload.reason == "Test update"

        # Should be signable for witnessing
        content = payload.signable_content()
        assert isinstance(content, bytes)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_update_requires_changes(self, service: IntegrityCaseService) -> None:
        """update_for_amendment should require at least one change."""
        with pytest.raises(ValueError, match="At least one change"):
            await service.update_for_amendment(
                amendment_event_id="amend-789",
                reason="No changes",
            )

    @pytest.mark.asyncio
    async def test_update_modifies_guarantee(
        self, service: IntegrityCaseService
    ) -> None:
        """update_for_amendment should modify existing guarantee."""
        # Get current CT-1 guarantee
        original = await service.get_guarantee("ct-1-audit-trail")
        assert original is not None

        # Create modified version
        modified = IntegrityGuarantee(
            guarantee_id="ct-1-audit-trail",
            category=original.category,
            name=original.name,
            description="Updated description for CT-1.",
            fr_reference=original.fr_reference,
            ct_reference=original.ct_reference,
            mechanism="Updated mechanism",
            invalidation_conditions=original.invalidation_conditions,
            is_constitutional=original.is_constitutional,
        )

        payload = await service.update_for_amendment(
            amendment_event_id="amend-mod",
            guarantees_modified=(modified,),
            reason="Modified CT-1",
        )

        assert "ct-1-audit-trail" in payload.guarantees_modified

        # Verify modification
        updated = await service.get_guarantee("ct-1-audit-trail")
        assert updated is not None
        assert updated.description == "Updated description for CT-1."

    @pytest.mark.asyncio
    async def test_update_increments_version(
        self, service: IntegrityCaseService, new_guarantee: IntegrityGuarantee
    ) -> None:
        """update_for_amendment should increment patch version."""
        # First update
        await service.update_for_amendment(
            amendment_event_id="amend-1",
            guarantees_added=(new_guarantee,),
            reason="First update",
        )

        artifact = await service.get_artifact()
        assert artifact.version == "1.0.1"

        # Second update
        new_guarantee2 = IntegrityGuarantee(
            guarantee_id="fr-test-new-2",
            category=GuaranteeCategory.FUNCTIONAL,
            name="Another New",
            description="Another new guarantee for testing.",
            fr_reference="FR998",
            mechanism="Mechanism for testing",
            invalidation_conditions=("Condition",),
            is_constitutional=False,
        )

        await service.update_for_amendment(
            amendment_event_id="amend-2",
            guarantees_added=(new_guarantee2,),
            reason="Second update",
        )

        artifact = await service.get_artifact()
        assert artifact.version == "1.0.2"


class TestIntegrityCaseServiceJsonLdContext:
    """Tests for IntegrityCaseService.get_json_ld_context method."""

    @pytest.fixture
    def service(self) -> IntegrityCaseService:
        """Create service with stub repository."""
        repository = IntegrityCaseRepositoryStub()
        return IntegrityCaseService(repository=repository)

    def test_get_json_ld_context(self, service: IntegrityCaseService) -> None:
        """get_json_ld_context should return context dict."""
        context = service.get_json_ld_context()

        assert isinstance(context, dict)
        assert "@context" in context
        assert "integrity" in context["@context"]
