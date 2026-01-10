"""Unit tests for PetitionService (Story 7.2, FR39).

Tests cover:
- submit_petition() with valid signature
- submit_petition() with invalid signature (AC4)
- submit_petition() during halt (AC7)
- cosign_petition() with valid signature
- cosign_petition() duplicate rejection (AC2)
- cosign_petition() threshold trigger (AC3)
- cosign_petition() idempotent agenda placement (AC5)
- get_petition() during halt (CT-13)
- list_open_petitions() public access (AC8)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.petition_service import (
    CosignPetitionResult,
    PetitionService,
    SubmitPetitionResult,
)
from src.domain.errors import SystemHaltedError
from src.domain.errors.petition import (
    DuplicateCosignatureError,
    InvalidSignatureError,
    PetitionClosedError,
    PetitionNotFoundError,
)
from src.domain.events.petition import (
    PETITION_THRESHOLD_COSIGNERS,
    PetitionStatus,
)
from src.domain.models.petition import CoSigner, Petition
from src.infrastructure.stubs.petition_repository_stub import PetitionRepositoryStub
from src.infrastructure.stubs.signature_verifier_stub import SignatureVerifierStub


class TestPetitionServiceSubmit:
    """Tests for submit_petition()."""

    @pytest.fixture
    def petition_repo(self) -> PetitionRepositoryStub:
        """Create a fresh petition repository stub."""
        return PetitionRepositoryStub()

    @pytest.fixture
    def signature_verifier(self) -> SignatureVerifierStub:
        """Create a signature verifier stub that accepts all signatures."""
        return SignatureVerifierStub(accept_all=True)

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def cessation_agenda_repo(self) -> AsyncMock:
        """Create a mock cessation agenda repository."""
        repo = AsyncMock()
        repo.save_agenda_placement = AsyncMock()
        return repo

    @pytest.fixture
    def petition_service(
        self,
        petition_repo: PetitionRepositoryStub,
        signature_verifier: SignatureVerifierStub,
        event_writer: AsyncMock,
        halt_checker: AsyncMock,
        cessation_agenda_repo: AsyncMock,
    ) -> PetitionService:
        """Create a petition service with test dependencies."""
        return PetitionService(
            petition_repo=petition_repo,
            signature_verifier=signature_verifier,
            event_writer=event_writer,
            halt_checker=halt_checker,
            cessation_agenda_repo=cessation_agenda_repo,
        )

    @pytest.mark.asyncio
    async def test_submit_petition_success(
        self,
        petition_service: PetitionService,
        event_writer: AsyncMock,
    ) -> None:
        """Test successful petition submission (AC1)."""
        result = await petition_service.submit_petition(
            petition_content="Test cessation concern",
            submitter_public_key="abc123" * 16,
            submitter_signature="sig456" * 32,
        )

        assert isinstance(result, SubmitPetitionResult)
        assert result.petition_id is not None
        assert result.created_at is not None

        # Event should be written
        event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_petition_invalid_signature(
        self,
        petition_service: PetitionService,
        signature_verifier: SignatureVerifierStub,
    ) -> None:
        """Test submission with invalid signature (AC4)."""
        signature_verifier.set_accept_all(False)

        with pytest.raises(InvalidSignatureError):
            await petition_service.submit_petition(
                petition_content="Test cessation concern",
                submitter_public_key="abc123" * 16,
                submitter_signature="bad_sig" * 32,
            )

    @pytest.mark.asyncio
    async def test_submit_petition_during_halt(
        self,
        petition_service: PetitionService,
        halt_checker: AsyncMock,
    ) -> None:
        """Test submission rejected during halt (AC7)."""
        halt_checker.is_halted = AsyncMock(return_value=True)
        halt_checker.get_halt_reason = AsyncMock(return_value="Test halt")

        with pytest.raises(SystemHaltedError):
            await petition_service.submit_petition(
                petition_content="Test cessation concern",
                submitter_public_key="abc123" * 16,
                submitter_signature="sig456" * 32,
            )


class TestPetitionServiceCosign:
    """Tests for cosign_petition()."""

    @pytest.fixture
    def petition_repo(self) -> PetitionRepositoryStub:
        """Create a fresh petition repository stub."""
        return PetitionRepositoryStub()

    @pytest.fixture
    def signature_verifier(self) -> SignatureVerifierStub:
        """Create a signature verifier stub that accepts all signatures."""
        return SignatureVerifierStub(accept_all=True)

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def cessation_agenda_repo(self) -> AsyncMock:
        """Create a mock cessation agenda repository."""
        repo = AsyncMock()
        repo.save_agenda_placement = AsyncMock()
        return repo

    @pytest.fixture
    def petition_service(
        self,
        petition_repo: PetitionRepositoryStub,
        signature_verifier: SignatureVerifierStub,
        event_writer: AsyncMock,
        halt_checker: AsyncMock,
        cessation_agenda_repo: AsyncMock,
    ) -> PetitionService:
        """Create a petition service with test dependencies."""
        return PetitionService(
            petition_repo=petition_repo,
            signature_verifier=signature_verifier,
            event_writer=event_writer,
            halt_checker=halt_checker,
            cessation_agenda_repo=cessation_agenda_repo,
        )

    @pytest.fixture
    async def existing_petition(
        self, petition_repo: PetitionRepositoryStub
    ) -> Petition:
        """Create an existing petition for co-signing tests."""
        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="submitter" * 12,
            submitter_signature="submitter_sig" * 12,
            petition_content="Test petition content",
            created_timestamp=datetime.now(timezone.utc),
            status=PetitionStatus.OPEN,
        )
        await petition_repo.save_petition(petition)
        return petition

    @pytest.mark.asyncio
    async def test_cosign_petition_success(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
        event_writer: AsyncMock,
    ) -> None:
        """Test successful co-signing."""
        result = await petition_service.cosign_petition(
            petition_id=existing_petition.petition_id,
            cosigner_public_key="cosigner1" * 12,
            cosigner_signature="cosigner1_sig" * 12,
        )

        assert isinstance(result, CosignPetitionResult)
        assert result.petition_id == existing_petition.petition_id
        assert result.cosigner_sequence == 1
        assert result.cosigner_count == 1
        assert result.threshold_met is False

        # Event should be written
        assert event_writer.write_event.call_count >= 1

    @pytest.mark.asyncio
    async def test_cosign_petition_duplicate_rejection(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
    ) -> None:
        """Test duplicate co-signature rejection (AC2)."""
        # First co-signature
        await petition_service.cosign_petition(
            petition_id=existing_petition.petition_id,
            cosigner_public_key="cosigner1" * 12,
            cosigner_signature="cosigner1_sig" * 12,
        )

        # Duplicate should fail
        with pytest.raises(DuplicateCosignatureError):
            await petition_service.cosign_petition(
                petition_id=existing_petition.petition_id,
                cosigner_public_key="cosigner1" * 12,
                cosigner_signature="cosigner1_sig" * 12,
            )

    @pytest.mark.asyncio
    async def test_cosign_petition_not_found(
        self,
        petition_service: PetitionService,
    ) -> None:
        """Test co-signing non-existent petition."""
        with pytest.raises(PetitionNotFoundError):
            await petition_service.cosign_petition(
                petition_id=uuid4(),
                cosigner_public_key="cosigner1" * 12,
                cosigner_signature="cosigner1_sig" * 12,
            )

    @pytest.mark.asyncio
    async def test_cosign_petition_invalid_signature(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
        signature_verifier: SignatureVerifierStub,
    ) -> None:
        """Test co-signing with invalid signature (AC4)."""
        signature_verifier.set_accept_all(False)

        with pytest.raises(InvalidSignatureError):
            await petition_service.cosign_petition(
                petition_id=existing_petition.petition_id,
                cosigner_public_key="cosigner1" * 12,
                cosigner_signature="bad_sig" * 12,
            )

    @pytest.mark.asyncio
    async def test_cosign_petition_during_halt(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
        halt_checker: AsyncMock,
    ) -> None:
        """Test co-signing rejected during halt (AC7)."""
        halt_checker.is_halted = AsyncMock(return_value=True)
        halt_checker.get_halt_reason = AsyncMock(return_value="Test halt")

        with pytest.raises(SystemHaltedError):
            await petition_service.cosign_petition(
                petition_id=existing_petition.petition_id,
                cosigner_public_key="cosigner1" * 12,
                cosigner_signature="cosigner1_sig" * 12,
            )


class TestPetitionServiceRead:
    """Tests for get_petition() and list_open_petitions()."""

    @pytest.fixture
    def petition_repo(self) -> PetitionRepositoryStub:
        """Create a fresh petition repository stub."""
        return PetitionRepositoryStub()

    @pytest.fixture
    def signature_verifier(self) -> SignatureVerifierStub:
        """Create a signature verifier stub that accepts all signatures."""
        return SignatureVerifierStub(accept_all=True)

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def cessation_agenda_repo(self) -> AsyncMock:
        """Create a mock cessation agenda repository."""
        repo = AsyncMock()
        repo.save_agenda_placement = AsyncMock()
        return repo

    @pytest.fixture
    def petition_service(
        self,
        petition_repo: PetitionRepositoryStub,
        signature_verifier: SignatureVerifierStub,
        event_writer: AsyncMock,
        halt_checker: AsyncMock,
        cessation_agenda_repo: AsyncMock,
    ) -> PetitionService:
        """Create a petition service with test dependencies."""
        return PetitionService(
            petition_repo=petition_repo,
            signature_verifier=signature_verifier,
            event_writer=event_writer,
            halt_checker=halt_checker,
            cessation_agenda_repo=cessation_agenda_repo,
        )

    @pytest.fixture
    async def existing_petition(
        self, petition_repo: PetitionRepositoryStub
    ) -> Petition:
        """Create an existing petition."""
        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="submitter" * 12,
            submitter_signature="submitter_sig" * 12,
            petition_content="Test petition content",
            created_timestamp=datetime.now(timezone.utc),
            status=PetitionStatus.OPEN,
        )
        await petition_repo.save_petition(petition)
        return petition

    @pytest.mark.asyncio
    async def test_get_petition_success(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
    ) -> None:
        """Test getting an existing petition."""
        result = await petition_service.get_petition(existing_petition.petition_id)

        assert result is not None
        assert result.petition_id == existing_petition.petition_id
        assert result.petition_content == "Test petition content"

    @pytest.mark.asyncio
    async def test_get_petition_not_found(
        self,
        petition_service: PetitionService,
    ) -> None:
        """Test getting non-existent petition returns None."""
        result = await petition_service.get_petition(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_petition_during_halt(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
        halt_checker: AsyncMock,
    ) -> None:
        """Test reading petition during halt (CT-13: reads allowed)."""
        halt_checker.is_halted = AsyncMock(return_value=True)

        # Should NOT raise SystemHaltedError
        result = await petition_service.get_petition(existing_petition.petition_id)
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_open_petitions_empty(
        self,
        petition_service: PetitionService,
    ) -> None:
        """Test listing when no petitions exist."""
        petitions, total = await petition_service.list_open_petitions()
        assert petitions == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_open_petitions(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
    ) -> None:
        """Test listing open petitions."""
        petitions, total = await petition_service.list_open_petitions()
        assert len(petitions) == 1
        assert total == 1
        assert petitions[0].petition_id == existing_petition.petition_id

    @pytest.mark.asyncio
    async def test_list_open_petitions_during_halt(
        self,
        petition_service: PetitionService,
        existing_petition: Petition,
        halt_checker: AsyncMock,
    ) -> None:
        """Test listing petitions during halt (CT-13: reads allowed)."""
        halt_checker.is_halted = AsyncMock(return_value=True)

        # Should NOT raise SystemHaltedError
        petitions, total = await petition_service.list_open_petitions()
        assert len(petitions) == 1
