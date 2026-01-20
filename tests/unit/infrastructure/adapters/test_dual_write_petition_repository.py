"""Unit tests for DualWritePetitionRepository (Story 0.3, AC2).

Tests verify dual-write behavior during migration period:
- Writes go to BOTH repositories when enabled
- Reads come from legacy repository (source of truth)
- Co-signer operations remain legacy-only
- Config flag controls dual-write behavior

Constitutional Constraints:
- FR-9.3: System SHALL support dual-write during migration period
- FR-9.4: System SHALL preserve existing petition_id references
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from src.application.ports.petition_repository import PetitionRepositoryProtocol
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.adapters.petition_migration import (
    CESSATION_REALM,
)
from src.infrastructure.adapters.petition_migration.dual_write_repository import (
    PETITION_DUAL_WRITE_ENABLED_DEFAULT,
    DualWritePetitionRepository,
    is_dual_write_enabled,
)


# Test fixtures
@pytest.fixture
def sample_petition_id() -> UUID:
    """Sample UUID for testing."""
    return UUID("01234567-89ab-cdef-0123-456789abcdef")


@pytest.fixture
def sample_timestamp() -> datetime:
    """Sample timestamp for testing."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_petition(sample_petition_id: UUID, sample_timestamp: datetime) -> Petition:
    """Sample petition for testing."""
    return Petition(
        petition_id=sample_petition_id,
        submitter_public_key="abc123" * 10 + "ab",  # 64 char hex
        submitter_signature="def456" * 20 + "def4",  # 128 char hex
        petition_content="Test petition content for cessation",
        created_timestamp=sample_timestamp,
        status=PetitionStatus.OPEN,
        cosigners=(),
        threshold_met_at=None,
    )


@pytest.fixture
def sample_cosigner(sample_timestamp: datetime) -> CoSigner:
    """Sample co-signer for testing."""
    return CoSigner(
        public_key="cosigner1" * 8,  # 64 char hex
        signature="sig1" * 32,  # 128 char hex
        signed_at=sample_timestamp,
        sequence=1,
    )


@pytest.fixture
def mock_legacy_repo() -> AsyncMock:
    """Mock legacy petition repository."""
    mock = AsyncMock(spec=PetitionRepositoryProtocol)
    return mock


@pytest.fixture
def mock_new_repo() -> AsyncMock:
    """Mock new petition submission repository."""
    mock = AsyncMock(spec=PetitionSubmissionRepositoryProtocol)
    return mock


@pytest.fixture
def dual_write_repo(
    mock_legacy_repo: AsyncMock, mock_new_repo: AsyncMock
) -> DualWritePetitionRepository:
    """Dual-write repository with mocked dependencies."""
    return DualWritePetitionRepository(
        legacy_repo=mock_legacy_repo,
        new_repo=mock_new_repo,
    )


class TestDualWritePetitionRepositoryInit:
    """Tests for DualWritePetitionRepository initialization."""

    def test_init_accepts_both_repositories(
        self, mock_legacy_repo: AsyncMock, mock_new_repo: AsyncMock
    ) -> None:
        """Verify dual-write repo accepts both repository protocols."""
        repo = DualWritePetitionRepository(
            legacy_repo=mock_legacy_repo,
            new_repo=mock_new_repo,
        )
        assert repo is not None

    def test_dual_write_enabled_default(self) -> None:
        """Verify default dual-write enabled value."""
        # Default should be True for migration period
        assert PETITION_DUAL_WRITE_ENABLED_DEFAULT is True


class TestIsDualWriteEnabled:
    """Tests for is_dual_write_enabled config function."""

    def test_returns_true_when_env_true(self) -> None:
        """Verify returns True when env var is 'true'."""
        with patch.dict("os.environ", {"PETITION_DUAL_WRITE_ENABLED": "true"}):
            assert is_dual_write_enabled() is True

    def test_returns_true_when_env_1(self) -> None:
        """Verify returns True when env var is '1'."""
        with patch.dict("os.environ", {"PETITION_DUAL_WRITE_ENABLED": "1"}):
            assert is_dual_write_enabled() is True

    def test_returns_false_when_env_false(self) -> None:
        """Verify returns False when env var is 'false'."""
        with patch.dict("os.environ", {"PETITION_DUAL_WRITE_ENABLED": "false"}):
            assert is_dual_write_enabled() is False

    def test_returns_false_when_env_0(self) -> None:
        """Verify returns False when env var is '0'."""
        with patch.dict("os.environ", {"PETITION_DUAL_WRITE_ENABLED": "0"}):
            assert is_dual_write_enabled() is False

    def test_returns_default_when_env_not_set(self) -> None:
        """Verify returns default when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove the key if present
            import os

            if "PETITION_DUAL_WRITE_ENABLED" in os.environ:
                del os.environ["PETITION_DUAL_WRITE_ENABLED"]
            result = is_dual_write_enabled()
            assert result is PETITION_DUAL_WRITE_ENABLED_DEFAULT


class TestDualWriteSavePetition:
    """Tests for dual-write save_petition behavior."""

    @pytest.mark.asyncio
    async def test_save_writes_to_legacy_first(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition: Petition,
    ) -> None:
        """Verify save_petition writes to legacy repository first."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.save_petition(sample_petition)

        mock_legacy_repo.save_petition.assert_called_once_with(sample_petition)

    @pytest.mark.asyncio
    async def test_save_writes_to_new_when_enabled(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition: Petition,
    ) -> None:
        """Verify save_petition writes to new repository when dual-write enabled."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.save_petition(sample_petition)

        # Verify new repo was called with converted submission
        mock_new_repo.save.assert_called_once()
        saved_submission = mock_new_repo.save.call_args[0][0]
        assert isinstance(saved_submission, PetitionSubmission)
        assert saved_submission.id == sample_petition.petition_id  # FR-9.4

    @pytest.mark.asyncio
    async def test_save_skips_new_when_disabled(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition: Petition,
    ) -> None:
        """Verify save_petition skips new repository when dual-write disabled."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=False,
        ):
            await dual_write_repo.save_petition(sample_petition)

        mock_legacy_repo.save_petition.assert_called_once()
        mock_new_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_uses_cessation_adapter(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_new_repo: AsyncMock,
        sample_petition: Petition,
    ) -> None:
        """Verify save uses CessationPetitionAdapter for conversion."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.save_petition(sample_petition)

        saved_submission = mock_new_repo.save.call_args[0][0]
        assert saved_submission.type == PetitionType.CESSATION
        assert saved_submission.realm == CESSATION_REALM


class TestDualWriteUpdateStatus:
    """Tests for dual-write update_status behavior."""

    @pytest.mark.asyncio
    async def test_update_status_writes_to_legacy(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        sample_petition_id: UUID,
    ) -> None:
        """Verify update_status writes to legacy repository."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.update_status(
                sample_petition_id, PetitionStatus.THRESHOLD_MET
            )

        mock_legacy_repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_writes_to_new_when_enabled(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
    ) -> None:
        """Verify update_status writes to new repository with mapped state."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.update_status(
                sample_petition_id, PetitionStatus.THRESHOLD_MET
            )

        mock_new_repo.update_state.assert_called_once_with(
            sample_petition_id, PetitionState.ESCALATED
        )

    @pytest.mark.asyncio
    async def test_update_status_maps_open_to_received(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
    ) -> None:
        """Verify OPEN status maps to RECEIVED state."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.update_status(sample_petition_id, PetitionStatus.OPEN)

        mock_new_repo.update_state.assert_called_once_with(
            sample_petition_id, PetitionState.RECEIVED
        )

    @pytest.mark.asyncio
    async def test_update_status_maps_closed_to_acknowledged(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
    ) -> None:
        """Verify CLOSED status maps to ACKNOWLEDGED state."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            await dual_write_repo.update_status(
                sample_petition_id, PetitionStatus.CLOSED
            )

        mock_new_repo.update_state.assert_called_once_with(
            sample_petition_id, PetitionState.ACKNOWLEDGED
        )

    @pytest.mark.asyncio
    async def test_update_status_skips_new_when_disabled(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
    ) -> None:
        """Verify update_status skips new repository when disabled."""
        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=False,
        ):
            await dual_write_repo.update_status(
                sample_petition_id, PetitionStatus.THRESHOLD_MET
            )

        mock_legacy_repo.update_status.assert_called_once()
        mock_new_repo.update_state.assert_not_called()


class TestAddCosignerLegacyOnly:
    """Tests for add_cosigner (legacy-only operation)."""

    @pytest.mark.asyncio
    async def test_add_cosigner_writes_to_legacy_only(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
        sample_cosigner: CoSigner,
        sample_petition: Petition,
    ) -> None:
        """Verify add_cosigner only writes to legacy repository."""
        mock_legacy_repo.add_cosigner.return_value = sample_petition

        with patch(
            "src.infrastructure.adapters.petition_migration.dual_write_repository.is_dual_write_enabled",
            return_value=True,
        ):
            result = await dual_write_repo.add_cosigner(
                sample_petition_id, sample_cosigner
            )

        mock_legacy_repo.add_cosigner.assert_called_once_with(
            sample_petition_id, sample_cosigner
        )
        # New repo should NOT be called for co-signer operations
        mock_new_repo.save.assert_not_called()
        mock_new_repo.update_state.assert_not_called()
        assert result == sample_petition


class TestReadsFromLegacy:
    """Tests for read operations (always from legacy repository)."""

    @pytest.mark.asyncio
    async def test_get_petition_reads_from_legacy(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
        sample_petition: Petition,
    ) -> None:
        """Verify get_petition reads from legacy repository."""
        mock_legacy_repo.get_petition.return_value = sample_petition

        result = await dual_write_repo.get_petition(sample_petition_id)

        mock_legacy_repo.get_petition.assert_called_once_with(sample_petition_id)
        mock_new_repo.get.assert_not_called()
        assert result == sample_petition

    @pytest.mark.asyncio
    async def test_list_open_petitions_reads_from_legacy(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition: Petition,
    ) -> None:
        """Verify list_open_petitions reads from legacy repository."""
        mock_legacy_repo.list_open_petitions.return_value = ([sample_petition], 1)

        result = await dual_write_repo.list_open_petitions(limit=10, offset=0)

        mock_legacy_repo.list_open_petitions.assert_called_once_with(limit=10, offset=0)
        mock_new_repo.list_by_state.assert_not_called()
        assert result == ([sample_petition], 1)

    @pytest.mark.asyncio
    async def test_has_cosigned_reads_from_legacy(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
    ) -> None:
        """Verify has_cosigned reads from legacy repository."""
        mock_legacy_repo.has_cosigned.return_value = True

        result = await dual_write_repo.has_cosigned(
            sample_petition_id, "some_public_key"
        )

        mock_legacy_repo.has_cosigned.assert_called_once_with(
            sample_petition_id, "some_public_key"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_get_cosigner_count_reads_from_legacy(
        self,
        dual_write_repo: DualWritePetitionRepository,
        mock_legacy_repo: AsyncMock,
        mock_new_repo: AsyncMock,
        sample_petition_id: UUID,
    ) -> None:
        """Verify get_cosigner_count reads from legacy repository."""
        mock_legacy_repo.get_cosigner_count.return_value = 42

        result = await dual_write_repo.get_cosigner_count(sample_petition_id)

        mock_legacy_repo.get_cosigner_count.assert_called_once_with(sample_petition_id)
        assert result == 42


class TestProtocolCompliance:
    """Tests for PetitionRepositoryProtocol compliance."""

    def test_implements_petition_repository_protocol(
        self, dual_write_repo: DualWritePetitionRepository
    ) -> None:
        """Verify DualWritePetitionRepository has all protocol methods."""
        assert hasattr(dual_write_repo, "save_petition")
        assert hasattr(dual_write_repo, "get_petition")
        assert hasattr(dual_write_repo, "list_open_petitions")
        assert hasattr(dual_write_repo, "add_cosigner")
        assert hasattr(dual_write_repo, "has_cosigned")
        assert hasattr(dual_write_repo, "update_status")
        assert hasattr(dual_write_repo, "get_cosigner_count")

    def test_can_be_used_as_petition_repository(
        self, dual_write_repo: DualWritePetitionRepository
    ) -> None:
        """Verify DualWritePetitionRepository can substitute PetitionRepositoryProtocol."""

        def some_function(repo: PetitionRepositoryProtocol) -> None:
            """Function expecting PetitionRepositoryProtocol."""
            pass

        # Should not raise
        some_function(dual_write_repo)
