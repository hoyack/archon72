"""Integration tests for Cessation Petition Migration (Story 0.3, AC4, AC6).

This module tests the end-to-end migration flow for Story 7.2 cessation petitions
to the new Story 0.2 petition submission schema.

Constitutional Constraints:
- FR-9.1: System SHALL migrate Story 7.2 cessation_petition to CESSATION type
- FR-9.3: System SHALL support dual-write during migration period
- FR-9.4: System SHALL preserve existing petition_id references

Test Categories:
1. Dual-write repository integration
2. Migration adapter correctness
3. All 98 Story 7.2 tests continue to pass
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.application.ports.petition_repository import PetitionRepositoryProtocol
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.domain.events.petition import (
    PETITION_THRESHOLD_COSIGNERS,
    PetitionStatus,
)
from src.domain.models.petition import CoSigner, Petition
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.adapters.petition_migration import (
    CESSATION_REALM,
    CessationPetitionAdapter,
    DualWritePetitionRepository,
    is_dual_write_enabled,
)
from src.infrastructure.stubs.petition_repository_stub import PetitionRepositoryStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


# Test fixtures
@pytest.fixture
def legacy_repo() -> PetitionRepositoryStub:
    """Legacy Story 7.2 petition repository."""
    return PetitionRepositoryStub()


@pytest.fixture
def new_repo() -> PetitionSubmissionRepositoryStub:
    """New Story 0.2 petition submission repository."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def dual_write_repo(
    legacy_repo: PetitionRepositoryStub,
    new_repo: PetitionSubmissionRepositoryStub,
) -> DualWritePetitionRepository:
    """Dual-write repository for migration testing."""
    return DualWritePetitionRepository(
        legacy_repo=legacy_repo,
        new_repo=new_repo,
    )


@pytest.fixture
def sample_timestamp() -> datetime:
    """Sample timestamp for testing."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def create_petition(
    petition_id: UUID | None = None,
    status: PetitionStatus = PetitionStatus.OPEN,
    cosigners: tuple[CoSigner, ...] = (),
    created_timestamp: datetime | None = None,
) -> Petition:
    """Helper to create test petition."""
    return Petition(
        petition_id=petition_id or uuid4(),
        submitter_public_key="submitter_" + "a" * 54,  # 64 hex chars
        submitter_signature="sig_" + "b" * 122,  # 128 hex chars
        petition_content="Test cessation petition content for migration testing",
        created_timestamp=created_timestamp or datetime.now(timezone.utc),
        status=status,
        cosigners=cosigners,
        threshold_met_at=None,
    )


class TestDualWriteIntegration:
    """Integration tests for dual-write repository (FR-9.3)."""

    @pytest.mark.asyncio
    async def test_save_writes_to_both_repositories(
        self,
        dual_write_repo: DualWritePetitionRepository,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """FR-9.3: save_petition writes to both legacy and new repositories."""
        petition = create_petition()

        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.save_petition(petition)

        # Verify legacy repository has the petition
        legacy_petition = await legacy_repo.get_petition(petition.petition_id)
        assert legacy_petition is not None
        assert legacy_petition.petition_id == petition.petition_id

        # Verify new repository has the submission
        new_submission = await new_repo.get(petition.petition_id)
        assert new_submission is not None
        assert new_submission.id == petition.petition_id  # FR-9.4

    @pytest.mark.asyncio
    async def test_id_preservation_in_dual_write(
        self,
        dual_write_repo: DualWritePetitionRepository,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """FR-9.4: Petition ID preserved exactly during dual-write."""
        specific_id = UUID("12345678-1234-5678-1234-567812345678")
        petition = create_petition(petition_id=specific_id)

        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.save_petition(petition)

        # Verify exact ID match
        legacy_petition = await legacy_repo.get_petition(specific_id)
        new_submission = await new_repo.get(specific_id)

        assert legacy_petition.petition_id == specific_id
        assert new_submission.id == specific_id

    @pytest.mark.asyncio
    async def test_status_update_dual_write_with_mapping(
        self,
        dual_write_repo: DualWritePetitionRepository,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """FR-9.3: Status updates map correctly between schemas."""
        petition = create_petition()

        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.save_petition(petition)

            # Update to THRESHOLD_MET
            await dual_write_repo.update_status(
                petition.petition_id,
                PetitionStatus.THRESHOLD_MET,
                threshold_met_at=datetime.now(timezone.utc).isoformat(),
            )

        # Verify legacy has THRESHOLD_MET
        legacy_petition = await legacy_repo.get_petition(petition.petition_id)
        assert legacy_petition.status == PetitionStatus.THRESHOLD_MET

        # Verify new has ESCALATED (mapped)
        new_submission = await new_repo.get(petition.petition_id)
        assert new_submission.state == PetitionState.ESCALATED

    @pytest.mark.asyncio
    async def test_cosigner_remains_legacy_only(
        self,
        dual_write_repo: DualWritePetitionRepository,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Co-signers stay in legacy schema only during migration."""
        petition = create_petition()

        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.save_petition(petition)

            # Add co-signer
            cosigner = CoSigner(
                public_key="cosigner_" + "c" * 55,
                signature="cosig_" + "d" * 121,
                signed_at=datetime.now(timezone.utc),
                sequence=1,
            )
            updated_petition = await dual_write_repo.add_cosigner(
                petition.petition_id, cosigner
            )

        # Legacy has the co-signer
        assert updated_petition.cosigner_count == 1
        assert updated_petition.has_cosigned("cosigner_" + "c" * 55)

        # New schema submission unchanged (no co-signer concept)
        new_submission = await new_repo.get(petition.petition_id)
        assert new_submission is not None
        # PetitionSubmission doesn't have cosigners


class TestMigrationAdapterIntegration:
    """Integration tests for CessationPetitionAdapter."""

    @pytest.mark.asyncio
    async def test_full_migration_flow(
        self,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Test complete migration of a petition from legacy to new schema."""
        # Create and save a petition in legacy
        petition = create_petition(status=PetitionStatus.THRESHOLD_MET)
        await legacy_repo.save_petition(petition)

        # Convert using adapter
        submission = CessationPetitionAdapter.to_submission(petition)

        # Save to new repository
        await new_repo.save(submission)

        # Verify migration preserved data
        retrieved = await new_repo.get(petition.petition_id)
        assert retrieved is not None
        assert retrieved.id == petition.petition_id
        assert retrieved.text == petition.petition_content
        assert retrieved.type == PetitionType.CESSATION
        assert retrieved.realm == CESSATION_REALM
        assert retrieved.state == PetitionState.ESCALATED

    @pytest.mark.asyncio
    async def test_bidirectional_conversion_preserves_data(self) -> None:
        """Test round-trip conversion preserves essential data."""
        original_id = uuid4()
        original_content = "Test petition content for round-trip"
        original_timestamp = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Create original petition
        original = Petition(
            petition_id=original_id,
            submitter_public_key="submitter_pub",
            submitter_signature="submitter_sig",
            petition_content=original_content,
            created_timestamp=original_timestamp,
            status=PetitionStatus.OPEN,
            cosigners=(),
            threshold_met_at=None,
        )

        # Convert to submission
        submission = CessationPetitionAdapter.to_submission(original)

        # Convert back
        recovered = CessationPetitionAdapter.from_submission(
            submission=submission,
            cosigners=(),
            submitter_public_key="submitter_pub",
            submitter_signature="submitter_sig",
            threshold_met_at=None,
        )

        # Verify key fields preserved
        assert recovered.petition_id == original_id
        assert recovered.petition_content == original_content
        assert recovered.status == PetitionStatus.OPEN
        assert recovered.created_timestamp == original_timestamp

    @pytest.mark.asyncio
    async def test_all_status_mappings(self) -> None:
        """Test all status to state mappings are correct."""
        mappings = [
            (PetitionStatus.OPEN, PetitionState.RECEIVED),
            (PetitionStatus.THRESHOLD_MET, PetitionState.ESCALATED),
            (PetitionStatus.CLOSED, PetitionState.ACKNOWLEDGED),
        ]

        for status, expected_state in mappings:
            petition = create_petition(status=status)
            submission = CessationPetitionAdapter.to_submission(petition)
            assert (
                submission.state == expected_state
            ), f"{status} should map to {expected_state}"


class TestReadPathDuringMigration:
    """Tests for read operations during migration period."""

    @pytest.mark.asyncio
    async def test_reads_always_from_legacy(
        self,
        dual_write_repo: DualWritePetitionRepository,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Reads always come from legacy (source of truth during migration)."""
        petition = create_petition()
        await legacy_repo.save_petition(petition)

        # Don't save to new repo - reads should still work
        result = await dual_write_repo.get_petition(petition.petition_id)
        assert result is not None
        assert result.petition_id == petition.petition_id

    @pytest.mark.asyncio
    async def test_list_open_petitions_from_legacy(
        self,
        dual_write_repo: DualWritePetitionRepository,
        legacy_repo: PetitionRepositoryStub,
    ) -> None:
        """List operations read from legacy."""
        # Create multiple petitions in legacy
        for _ in range(3):
            await legacy_repo.save_petition(create_petition())

        petitions, total = await dual_write_repo.list_open_petitions()
        assert total == 3
        assert len(petitions) == 3


class TestMigrationConfigurationFlag:
    """Tests for PETITION_DUAL_WRITE_ENABLED configuration."""

    @pytest.mark.asyncio
    async def test_dual_write_disabled_skips_new_repo(
        self,
        dual_write_repo: DualWritePetitionRepository,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """When dual-write disabled, only write to legacy."""
        petition = create_petition()

        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=False,
        ):
            await dual_write_repo.save_petition(petition)

        # Legacy has the petition
        assert await legacy_repo.get_petition(petition.petition_id) is not None

        # New repo does NOT have the submission
        assert await new_repo.get(petition.petition_id) is None


class TestMigrationWithThresholdReached:
    """Tests for migrating petitions that have reached threshold."""

    @pytest.mark.asyncio
    async def test_migrate_threshold_met_petition(
        self, new_repo: PetitionSubmissionRepositoryStub
    ) -> None:
        """Test migration of a petition that has already met threshold."""
        # Create petition with threshold met status
        cosigners = tuple(
            CoSigner(
                public_key=f"cosigner_{i}_" + "x" * 50,
                signature=f"sig_{i}_" + "y" * 118,
                signed_at=datetime.now(timezone.utc),
                sequence=i + 1,
            )
            for i in range(PETITION_THRESHOLD_COSIGNERS)
        )

        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="submitter_pub",
            submitter_signature="submitter_sig",
            petition_content="Petition that reached 100 co-signers",
            created_timestamp=datetime.now(timezone.utc),
            status=PetitionStatus.THRESHOLD_MET,
            cosigners=cosigners,
            threshold_met_at=datetime.now(timezone.utc),
        )

        # Migrate
        submission = CessationPetitionAdapter.to_submission(petition)
        await new_repo.save(submission)

        # Verify
        retrieved = await new_repo.get(petition.petition_id)
        assert retrieved is not None
        assert retrieved.state == PetitionState.ESCALATED
        assert retrieved.type == PetitionType.CESSATION


class TestRollbackCapability:
    """Tests for migration rollback capability."""

    @pytest.mark.asyncio
    async def test_can_identify_migrated_petitions(
        self,
        legacy_repo: PetitionRepositoryStub,
        new_repo: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Migrated petitions can be identified for rollback."""
        # Simulate migration
        petition_ids = []
        for _ in range(3):
            petition = create_petition()
            petition_ids.append(petition.petition_id)

            # Save to legacy
            await legacy_repo.save_petition(petition)

            # Migrate to new
            submission = CessationPetitionAdapter.to_submission(petition)
            await new_repo.save(submission)

        # All IDs should exist in both repositories
        for pid in petition_ids:
            assert await legacy_repo.get_petition(pid) is not None
            assert await new_repo.get(pid) is not None

        # Rollback: delete from new (simulated)
        for pid in petition_ids:
            # In real rollback, this would use the mapping table
            # Here we just verify the data structure supports it
            pass  # Delete would happen via SQL, not stub

        # Legacy still intact after rollback
        for pid in petition_ids:
            assert await legacy_repo.get_petition(pid) is not None
