"""Unit tests for IntegrityCaseRepositoryStub (Story 7.10, FR144).

Tests the in-memory stub implementation of the Integrity Case
Repository port.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- CT-13: Post-cessation read-only access
"""

from datetime import datetime, timezone

import pytest

from src.domain.models.integrity_case import (
    GuaranteeCategory,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)
from src.infrastructure.stubs.integrity_case_repository_stub import (
    IntegrityCaseRepositoryStub,
)


class TestIntegrityCaseRepositoryStubGetCurrent:
    """Tests for IntegrityCaseRepositoryStub.get_current method."""

    @pytest.mark.asyncio
    async def test_get_current_returns_artifact(self) -> None:
        """get_current should return pre-populated artifact."""
        repo = IntegrityCaseRepositoryStub()

        artifact = await repo.get_current()

        assert isinstance(artifact, IntegrityCaseArtifact)
        assert artifact.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_current_has_all_guarantees(self) -> None:
        """get_current should return artifact with all 20 guarantees."""
        repo = IntegrityCaseRepositoryStub()

        artifact = await repo.get_current()

        assert len(artifact.guarantees) == 20

    @pytest.mark.asyncio
    async def test_get_current_covers_all_cts(self) -> None:
        """get_current artifact should cover all 15 CTs."""
        repo = IntegrityCaseRepositoryStub()

        artifact = await repo.get_current()
        covered_cts = {
            g.ct_reference for g in artifact.guarantees if g.ct_reference
        }

        for i in range(1, 16):
            assert f"CT-{i}" in covered_cts


class TestIntegrityCaseRepositoryStubGetVersion:
    """Tests for IntegrityCaseRepositoryStub.get_version method."""

    @pytest.mark.asyncio
    async def test_get_version_initial(self) -> None:
        """get_version should return initial version."""
        repo = IntegrityCaseRepositoryStub()

        artifact = await repo.get_version("1.0.0")

        assert artifact is not None
        assert artifact.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_version_not_found(self) -> None:
        """get_version should return None for nonexistent version."""
        repo = IntegrityCaseRepositoryStub()

        artifact = await repo.get_version("99.99.99")

        assert artifact is None


class TestIntegrityCaseRepositoryStubUpdateWithAmendment:
    """Tests for IntegrityCaseRepositoryStub.update_with_amendment method."""

    @pytest.fixture
    def new_guarantee(self) -> IntegrityGuarantee:
        """Create a new guarantee for testing."""
        return IntegrityGuarantee(
            guarantee_id="test-new",
            category=GuaranteeCategory.FUNCTIONAL,
            name="Test New Guarantee",
            description="A test guarantee for testing updates.",
            fr_reference="FR999",
            mechanism="Test mechanism for testing",
            invalidation_conditions=("Test condition",),
            is_constitutional=False,
        )

    @pytest.mark.asyncio
    async def test_update_creates_new_version(
        self, new_guarantee: IntegrityGuarantee
    ) -> None:
        """update_with_amendment should create new version."""
        repo = IntegrityCaseRepositoryStub()
        current = await repo.get_current()

        # Create new artifact with additional guarantee
        now = datetime.now(timezone.utc)
        new_artifact = IntegrityCaseArtifact(
            guarantees=current.guarantees + (new_guarantee,),
            version="1.0.1",
            schema_version=current.schema_version,
            constitution_version=current.constitution_version,
            created_at=current.created_at,
            last_updated=now,
            amendment_event_id="amend-test",
        )

        await repo.update_with_amendment(new_artifact, "amend-test")

        # Current should now be new version
        updated = await repo.get_current()
        assert updated.version == "1.0.1"
        assert updated.get_guarantee("test-new") is not None

    @pytest.mark.asyncio
    async def test_update_preserves_history(
        self, new_guarantee: IntegrityGuarantee
    ) -> None:
        """update_with_amendment should preserve version history."""
        repo = IntegrityCaseRepositoryStub()
        current = await repo.get_current()

        now = datetime.now(timezone.utc)
        new_artifact = IntegrityCaseArtifact(
            guarantees=current.guarantees + (new_guarantee,),
            version="1.0.1",
            schema_version=current.schema_version,
            constitution_version=current.constitution_version,
            created_at=current.created_at,
            last_updated=now,
            amendment_event_id="amend-test",
        )

        await repo.update_with_amendment(new_artifact, "amend-test")

        # Old version should still be accessible
        old = await repo.get_version("1.0.0")
        assert old is not None
        assert old.get_guarantee("test-new") is None

        # New version should be accessible
        new = await repo.get_version("1.0.1")
        assert new is not None
        assert new.get_guarantee("test-new") is not None


class TestIntegrityCaseRepositoryStubGetVersionHistory:
    """Tests for IntegrityCaseRepositoryStub.get_version_history method."""

    @pytest.mark.asyncio
    async def test_get_history_initial(self) -> None:
        """get_version_history should include initial version."""
        repo = IntegrityCaseRepositoryStub()

        history = await repo.get_version_history()

        assert len(history) >= 1
        versions = [v for v, _ in history]
        assert "1.0.0" in versions

    @pytest.mark.asyncio
    async def test_get_history_after_updates(self) -> None:
        """get_version_history should include all versions after updates."""
        repo = IntegrityCaseRepositoryStub()
        current = await repo.get_current()

        # Add two updates
        for i in range(2):
            now = datetime.now(timezone.utc)
            new_artifact = IntegrityCaseArtifact(
                guarantees=current.guarantees,
                version=f"1.0.{i + 1}",
                schema_version=current.schema_version,
                constitution_version=current.constitution_version,
                created_at=current.created_at,
                last_updated=now,
                amendment_event_id=f"amend-{i}",
            )
            await repo.update_with_amendment(new_artifact, f"amend-{i}")

        history = await repo.get_version_history()

        assert len(history) == 3  # 1.0.0, 1.0.1, 1.0.2
        versions = [v for v, _ in history]
        assert "1.0.0" in versions
        assert "1.0.1" in versions
        assert "1.0.2" in versions


class TestIntegrityCaseRepositoryStubValidateCompleteness:
    """Tests for IntegrityCaseRepositoryStub.validate_completeness method."""

    @pytest.mark.asyncio
    async def test_validate_returns_empty_when_complete(self) -> None:
        """validate_completeness should return empty list for complete artifact."""
        repo = IntegrityCaseRepositoryStub()

        missing = await repo.validate_completeness()

        assert missing == []


class TestIntegrityCaseRepositoryStubCeaseMode:
    """Tests for IntegrityCaseRepositoryStub in ceased mode (CT-13)."""

    @pytest.mark.asyncio
    async def test_read_works_after_cease(self) -> None:
        """get_current should work after cease (CT-13)."""
        repo = IntegrityCaseRepositoryStub()
        repo.set_ceased(True)

        artifact = await repo.get_current()

        assert artifact is not None
        assert len(artifact.guarantees) == 20

    @pytest.mark.asyncio
    async def test_write_blocked_after_cease(self) -> None:
        """update_with_amendment should fail after cease (CT-13)."""
        repo = IntegrityCaseRepositoryStub()
        repo.set_ceased(True)

        current = await repo.get_current()
        now = datetime.now(timezone.utc)
        new_artifact = IntegrityCaseArtifact(
            guarantees=current.guarantees,
            version="1.0.1",
            schema_version=current.schema_version,
            constitution_version=current.constitution_version,
            created_at=current.created_at,
            last_updated=now,
            amendment_event_id="amend-blocked",
        )

        from src.domain.errors.ceased import SystemCeasedError

        with pytest.raises(SystemCeasedError):
            await repo.update_with_amendment(new_artifact, "amend-blocked")

    @pytest.mark.asyncio
    async def test_history_accessible_after_cease(self) -> None:
        """get_version_history should work after cease (CT-13)."""
        repo = IntegrityCaseRepositoryStub()
        repo.set_ceased(True)

        history = await repo.get_version_history()

        assert len(history) >= 1


class TestIntegrityCaseRepositoryStubPrePopulation:
    """Tests for pre-population of guarantees."""

    @pytest.mark.asyncio
    async def test_ct1_guarantee_populated(self) -> None:
        """CT-1 guarantee should be pre-populated."""
        repo = IntegrityCaseRepositoryStub()
        artifact = await repo.get_current()

        ct1 = artifact.get_guarantee("ct-1-audit-trail")

        assert ct1 is not None
        assert ct1.ct_reference == "CT-1"
        assert ct1.is_constitutional is True

    @pytest.mark.asyncio
    async def test_ct11_guarantee_populated(self) -> None:
        """CT-11 guarantee should be pre-populated."""
        repo = IntegrityCaseRepositoryStub()
        artifact = await repo.get_current()

        ct11 = artifact.get_guarantee("ct-11-loud-failure")

        assert ct11 is not None
        assert ct11.ct_reference == "CT-11"

    @pytest.mark.asyncio
    async def test_fr_guarantee_populated(self) -> None:
        """FR guarantee should be pre-populated."""
        repo = IntegrityCaseRepositoryStub()
        artifact = await repo.get_current()

        fr = artifact.get_guarantee("fr-observer-access")

        assert fr is not None
        assert fr.category == GuaranteeCategory.FUNCTIONAL
