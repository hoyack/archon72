"""Unit tests for PetitionRepositoryStub (Story 7.2, FR39).

Tests cover:
- save_petition() with duplicate detection
- get_petition() retrieval
- list_open_petitions() with pagination
- add_cosigner() with duplicate and status checks
- has_cosigned() detection
- update_status() transitions
- get_cosigner_count() counting
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.petition import (
    DuplicateCosignatureError,
    PetitionAlreadyExistsError,
    PetitionClosedError,
    PetitionNotFoundError,
)
from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition
from src.infrastructure.stubs.petition_repository_stub import PetitionRepositoryStub


class TestPetitionRepositoryStubSave:
    """Tests for save_petition()."""

    @pytest.fixture
    def repo(self) -> PetitionRepositoryStub:
        """Create a fresh repository stub."""
        return PetitionRepositoryStub()

    @pytest.fixture
    def sample_petition(self) -> Petition:
        """Create a sample petition."""
        return Petition(
            petition_id=uuid4(),
            submitter_public_key="key123",
            submitter_signature="sig456",
            petition_content="Test content",
            created_timestamp=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_save_petition_success(
        self,
        repo: PetitionRepositoryStub,
        sample_petition: Petition,
    ) -> None:
        """Test saving a new petition."""
        await repo.save_petition(sample_petition)
        result = await repo.get_petition(sample_petition.petition_id)
        assert result is not None
        assert result.petition_id == sample_petition.petition_id

    @pytest.mark.asyncio
    async def test_save_petition_duplicate(
        self,
        repo: PetitionRepositoryStub,
        sample_petition: Petition,
    ) -> None:
        """Test saving duplicate petition raises error."""
        await repo.save_petition(sample_petition)
        with pytest.raises(PetitionAlreadyExistsError):
            await repo.save_petition(sample_petition)


class TestPetitionRepositoryStubGet:
    """Tests for get_petition()."""

    @pytest.fixture
    def repo(self) -> PetitionRepositoryStub:
        """Create a fresh repository stub."""
        return PetitionRepositoryStub()

    @pytest.mark.asyncio
    async def test_get_petition_not_found(
        self,
        repo: PetitionRepositoryStub,
    ) -> None:
        """Test getting non-existent petition returns None."""
        result = await repo.get_petition(uuid4())
        assert result is None


class TestPetitionRepositoryStubList:
    """Tests for list_open_petitions()."""

    @pytest.fixture
    def repo(self) -> PetitionRepositoryStub:
        """Create a fresh repository stub."""
        return PetitionRepositoryStub()

    @pytest.mark.asyncio
    async def test_list_empty(
        self,
        repo: PetitionRepositoryStub,
    ) -> None:
        """Test listing empty repository."""
        petitions, total = await repo.list_open_petitions()
        assert petitions == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_with_petitions(
        self,
        repo: PetitionRepositoryStub,
    ) -> None:
        """Test listing petitions."""
        for i in range(3):
            petition = Petition(
                petition_id=uuid4(),
                submitter_public_key=f"key{i}",
                submitter_signature=f"sig{i}",
                petition_content=f"Content {i}",
                created_timestamp=datetime.now(timezone.utc),
            )
            await repo.save_petition(petition)

        petitions, total = await repo.list_open_petitions()
        assert len(petitions) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_list_pagination(
        self,
        repo: PetitionRepositoryStub,
    ) -> None:
        """Test pagination in listing."""
        for i in range(5):
            petition = Petition(
                petition_id=uuid4(),
                submitter_public_key=f"key{i}",
                submitter_signature=f"sig{i}",
                petition_content=f"Content {i}",
                created_timestamp=datetime.now(timezone.utc),
            )
            await repo.save_petition(petition)

        petitions, total = await repo.list_open_petitions(limit=2, offset=0)
        assert len(petitions) == 2
        assert total == 5

        petitions, total = await repo.list_open_petitions(limit=2, offset=2)
        assert len(petitions) == 2
        assert total == 5


class TestPetitionRepositoryStubCosigner:
    """Tests for add_cosigner() and has_cosigned()."""

    @pytest.fixture
    def repo(self) -> PetitionRepositoryStub:
        """Create a fresh repository stub."""
        return PetitionRepositoryStub()

    @pytest.fixture
    async def existing_petition(
        self,
        repo: PetitionRepositoryStub,
    ) -> Petition:
        """Create an existing petition."""
        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="submitter_key",
            submitter_signature="submitter_sig",
            petition_content="Test content",
            created_timestamp=datetime.now(timezone.utc),
        )
        await repo.save_petition(petition)
        return petition

    @pytest.mark.asyncio
    async def test_add_cosigner_success(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test adding a co-signer."""
        cosigner = CoSigner(
            public_key="cosigner_key",
            signature="cosigner_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        updated = await repo.add_cosigner(existing_petition.petition_id, cosigner)
        assert updated.cosigner_count == 1

    @pytest.mark.asyncio
    async def test_add_cosigner_duplicate(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test adding duplicate co-signer raises error."""
        cosigner = CoSigner(
            public_key="cosigner_key",
            signature="cosigner_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        await repo.add_cosigner(existing_petition.petition_id, cosigner)

        cosigner2 = CoSigner(
            public_key="cosigner_key",
            signature="cosigner_sig2",
            signed_at=datetime.now(timezone.utc),
            sequence=2,
        )
        with pytest.raises(DuplicateCosignatureError):
            await repo.add_cosigner(existing_petition.petition_id, cosigner2)

    @pytest.mark.asyncio
    async def test_add_cosigner_not_found(
        self,
        repo: PetitionRepositoryStub,
    ) -> None:
        """Test adding co-signer to non-existent petition."""
        cosigner = CoSigner(
            public_key="cosigner_key",
            signature="cosigner_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        with pytest.raises(PetitionNotFoundError):
            await repo.add_cosigner(uuid4(), cosigner)

    @pytest.mark.asyncio
    async def test_add_cosigner_closed_petition(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test adding co-signer to closed petition raises error."""
        await repo.update_status(existing_petition.petition_id, PetitionStatus.CLOSED)

        cosigner = CoSigner(
            public_key="cosigner_key",
            signature="cosigner_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        with pytest.raises(PetitionClosedError):
            await repo.add_cosigner(existing_petition.petition_id, cosigner)

    @pytest.mark.asyncio
    async def test_has_cosigned_submitter(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test has_cosigned returns True for submitter."""
        result = await repo.has_cosigned(
            existing_petition.petition_id,
            existing_petition.submitter_public_key,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_has_cosigned_cosigner(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test has_cosigned returns True for co-signer."""
        cosigner = CoSigner(
            public_key="cosigner_key",
            signature="cosigner_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        await repo.add_cosigner(existing_petition.petition_id, cosigner)

        result = await repo.has_cosigned(existing_petition.petition_id, "cosigner_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_cosigned_unknown(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test has_cosigned returns False for unknown key."""
        result = await repo.has_cosigned(existing_petition.petition_id, "unknown_key")
        assert result is False


class TestPetitionRepositoryStubStatus:
    """Tests for update_status() and get_cosigner_count()."""

    @pytest.fixture
    def repo(self) -> PetitionRepositoryStub:
        """Create a fresh repository stub."""
        return PetitionRepositoryStub()

    @pytest.fixture
    async def existing_petition(
        self,
        repo: PetitionRepositoryStub,
    ) -> Petition:
        """Create an existing petition."""
        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="submitter_key",
            submitter_signature="submitter_sig",
            petition_content="Test content",
            created_timestamp=datetime.now(timezone.utc),
        )
        await repo.save_petition(petition)
        return petition

    @pytest.mark.asyncio
    async def test_update_status_closed(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test updating status to closed."""
        await repo.update_status(existing_petition.petition_id, PetitionStatus.CLOSED)
        result = await repo.get_petition(existing_petition.petition_id)
        assert result is not None
        assert result.status == PetitionStatus.CLOSED

    @pytest.mark.asyncio
    async def test_update_status_threshold_met(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test updating status to threshold_met with timestamp."""
        timestamp = "2026-01-08T12:00:00+00:00"
        await repo.update_status(
            existing_petition.petition_id,
            PetitionStatus.THRESHOLD_MET,
            threshold_met_at=timestamp,
        )
        result = await repo.get_petition(existing_petition.petition_id)
        assert result is not None
        assert result.status == PetitionStatus.THRESHOLD_MET
        assert result.threshold_met_at is not None

    @pytest.mark.asyncio
    async def test_update_status_not_found(
        self,
        repo: PetitionRepositoryStub,
    ) -> None:
        """Test updating status of non-existent petition."""
        with pytest.raises(PetitionNotFoundError):
            await repo.update_status(uuid4(), PetitionStatus.CLOSED)

    @pytest.mark.asyncio
    async def test_get_cosigner_count(
        self,
        repo: PetitionRepositoryStub,
        existing_petition: Petition,
    ) -> None:
        """Test getting co-signer count."""
        count = await repo.get_cosigner_count(existing_petition.petition_id)
        assert count == 0

        # Add co-signers
        for i in range(3):
            cosigner = CoSigner(
                public_key=f"cosigner_key_{i}",
                signature=f"cosigner_sig_{i}",
                signed_at=datetime.now(timezone.utc),
                sequence=i + 1,
            )
            await repo.add_cosigner(existing_petition.petition_id, cosigner)

        count = await repo.get_cosigner_count(existing_petition.petition_id)
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_cosigner_count_not_found(
        self,
        repo: PetitionRepositoryStub,
    ) -> None:
        """Test getting co-signer count of non-existent petition."""
        with pytest.raises(PetitionNotFoundError):
            await repo.get_cosigner_count(uuid4())
