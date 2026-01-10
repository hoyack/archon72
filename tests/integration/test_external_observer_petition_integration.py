"""Integration tests for External Observer Petition (Story 7.2, FR39).

This module tests end-to-end external observer petition scenarios:
- FR39: External observers can petition with 100+ co-signers
- AC1: Submit petition with cryptographic signature
- AC2: Co-sign petition with unique signatures
- AC3: Threshold detection at 100 co-signers
- AC4: Ed25519 signature verification
- AC5: Automatic agenda placement at threshold
- AC6: Halt state behavior (reads allowed, writes blocked)
- CT-11: Silent failure destroys legitimacy (all operations logged)
- CT-12: Witnessing creates accountability (events witnessed)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.petition_service import (
    PetitionService,
)
from src.domain.errors import SystemHaltedError
from src.domain.errors.petition import (
    DuplicateCosignatureError,
    InvalidSignatureError,
    PetitionClosedError,
    PetitionNotFoundError,
)
from src.domain.events.petition import (
    PETITION_COSIGNED_EVENT_TYPE,
    PETITION_CREATED_EVENT_TYPE,
    PETITION_THRESHOLD_COSIGNERS,
    PETITION_THRESHOLD_MET_EVENT_TYPE,
    PetitionStatus,
)
from src.infrastructure.stubs.cessation_agenda_repository_stub import (
    CessationAgendaRepositoryStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.petition_repository_stub import PetitionRepositoryStub
from src.infrastructure.stubs.signature_verifier_stub import SignatureVerifierStub


@pytest.fixture
def integration_setup() -> dict:
    """Set up all components for integration testing."""
    petition_repo = PetitionRepositoryStub()
    signature_verifier = SignatureVerifierStub(accept_all=True)
    halt_checker = HaltCheckerStub()
    cessation_agenda_repo = CessationAgendaRepositoryStub()

    event_writer = AsyncMock()
    event_writer.write_event = AsyncMock(return_value=None)

    service = PetitionService(
        petition_repo=petition_repo,
        signature_verifier=signature_verifier,
        event_writer=event_writer,
        halt_checker=halt_checker,
        cessation_agenda_repo=cessation_agenda_repo,
    )

    return {
        "service": service,
        "petition_repo": petition_repo,
        "signature_verifier": signature_verifier,
        "halt_checker": halt_checker,
        "cessation_agenda_repo": cessation_agenda_repo,
        "event_writer": event_writer,
    }


class TestPetitionSubmissionFlow:
    """End-to-end tests for petition submission (AC1)."""

    @pytest.mark.asyncio
    async def test_end_to_end_petition_submission(
        self, integration_setup: dict
    ) -> None:
        """AC1: Submit petition with valid signature creates petition and event."""
        service = integration_setup["service"]
        petition_repo = integration_setup["petition_repo"]
        event_writer = integration_setup["event_writer"]

        result = await service.submit_petition(
            submitter_public_key="submitter_pubkey_hex",
            submitter_signature="valid_signature_hex",
            petition_content="Request for cessation consideration due to concern X",
        )

        # Verify submission succeeded (result has petition_id)
        assert result.petition_id is not None
        assert result.created_at is not None

        # Verify petition persisted
        petition = await petition_repo.get_petition(result.petition_id)
        assert petition is not None
        assert petition.submitter_public_key == "submitter_pubkey_hex"
        assert petition.status == PetitionStatus.OPEN

        # Verify witnessed event (CT-12)
        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == PETITION_CREATED_EVENT_TYPE
        payload = call_kwargs["payload"]
        assert payload["submitter_public_key"] == "submitter_pubkey_hex"

    @pytest.mark.asyncio
    async def test_petition_submission_with_invalid_signature(
        self, integration_setup: dict
    ) -> None:
        """AC4: Invalid signature rejected at submission."""
        service = integration_setup["service"]
        signature_verifier = integration_setup["signature_verifier"]
        event_writer = integration_setup["event_writer"]

        # Configure verifier to reject all signatures
        signature_verifier._accept_all = False

        with pytest.raises(InvalidSignatureError):
            await service.submit_petition(
                submitter_public_key="submitter_pubkey_hex",
                submitter_signature="invalid_signature",
                petition_content="Test content",
            )

        # No event should be written for failed submission
        event_writer.write_event.assert_not_called()


class TestCoSignatureFlow:
    """End-to-end tests for petition co-signature (AC2)."""

    @pytest.mark.asyncio
    async def test_end_to_end_cosignature(
        self, integration_setup: dict
    ) -> None:
        """AC2: Co-sign petition with valid signature adds co-signer."""
        service = integration_setup["service"]
        petition_repo = integration_setup["petition_repo"]
        event_writer = integration_setup["event_writer"]

        # First submit a petition
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test petition content",
        )

        # Reset mock to track co-sign event
        event_writer.reset_mock()

        # Co-sign the petition
        cosign_result = await service.cosign_petition(
            petition_id=submit_result.petition_id,
            cosigner_public_key="cosigner_pubkey",
            cosigner_signature="cosigner_sig",
        )

        # Verify co-signature succeeded
        assert cosign_result.cosigner_count == 1
        assert cosign_result.threshold_met is False

        # Verify co-signer persisted
        petition = await petition_repo.get_petition(submit_result.petition_id)
        assert petition is not None
        assert petition.cosigner_count == 1
        assert petition.has_cosigned("cosigner_pubkey") is True

        # Verify witnessed event (CT-12)
        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == PETITION_COSIGNED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_duplicate_cosignature_rejected(
        self, integration_setup: dict
    ) -> None:
        """AC2: Same public key cannot co-sign twice."""
        service = integration_setup["service"]

        # Submit petition
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test content",
        )

        # First co-signature succeeds
        await service.cosign_petition(
            petition_id=submit_result.petition_id,
            cosigner_public_key="cosigner_pubkey",
            cosigner_signature="cosigner_sig",
        )

        # Second co-signature with same key fails
        with pytest.raises(DuplicateCosignatureError):
            await service.cosign_petition(
                petition_id=submit_result.petition_id,
                cosigner_public_key="cosigner_pubkey",
                cosigner_signature="different_sig",
            )

    @pytest.mark.asyncio
    async def test_submitter_cannot_cosign_own_petition(
        self, integration_setup: dict
    ) -> None:
        """Submitter's signature already counts, cannot co-sign again."""
        service = integration_setup["service"]

        # Submit petition
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test content",
        )

        # Submitter trying to co-sign fails (already signed as submitter)
        with pytest.raises(DuplicateCosignatureError):
            await service.cosign_petition(
                petition_id=submit_result.petition_id,
                cosigner_public_key="submitter_pubkey",  # Same as submitter
                cosigner_signature="another_sig",
            )


class TestThresholdDetectionFlow:
    """End-to-end tests for threshold detection (AC3, AC5)."""

    @pytest.mark.asyncio
    async def test_threshold_met_at_100_cosigners(
        self, integration_setup: dict
    ) -> None:
        """AC3: Threshold detected when 100 unique co-signers reached."""
        service = integration_setup["service"]
        petition_repo = integration_setup["petition_repo"]
        event_writer = integration_setup["event_writer"]

        # Submit petition
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test petition for threshold detection",
        )

        # Add co-signers until threshold
        for i in range(PETITION_THRESHOLD_COSIGNERS):
            event_writer.reset_mock()

            result = await service.cosign_petition(
                petition_id=submit_result.petition_id,
                cosigner_public_key=f"cosigner_{i}_pubkey",
                cosigner_signature=f"cosigner_{i}_sig",
            )

            if i < PETITION_THRESHOLD_COSIGNERS - 1:
                # Before threshold
                assert result.threshold_met is False
            else:
                # At threshold (100th co-signer)
                assert result.threshold_met is True
                assert result.cosigner_count == PETITION_THRESHOLD_COSIGNERS

        # Verify petition status updated
        petition = await petition_repo.get_petition(submit_result.petition_id)
        assert petition is not None
        assert petition.status == PetitionStatus.THRESHOLD_MET
        assert petition.threshold_met_at is not None

    @pytest.mark.asyncio
    async def test_threshold_met_triggers_agenda_placement(
        self, integration_setup: dict
    ) -> None:
        """AC5: Automatic agenda placement when threshold met."""
        service = integration_setup["service"]
        cessation_agenda_repo = integration_setup["cessation_agenda_repo"]
        event_writer = integration_setup["event_writer"]

        # Submit petition
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Request cessation consideration",
        )

        # Add 100 co-signers to trigger threshold
        for i in range(PETITION_THRESHOLD_COSIGNERS):
            await service.cosign_petition(
                petition_id=submit_result.petition_id,
                cosigner_public_key=f"cosigner_{i}",
                cosigner_signature=f"sig_{i}",
            )

        # Verify threshold_met event was written
        threshold_event_found = False
        for call in event_writer.write_event.call_args_list:
            if call.kwargs.get("event_type") == PETITION_THRESHOLD_MET_EVENT_TYPE:
                threshold_event_found = True
                payload = call.kwargs["payload"]
                assert payload["final_cosigner_count"] == PETITION_THRESHOLD_COSIGNERS
                assert "petition_id" in payload
                break

        assert threshold_event_found, "Threshold met event should be written"

        # Verify cessation agenda placement
        placements = await cessation_agenda_repo.list_all_placements()
        petition_placements = [
            p for p in placements
            if "petition" in p.agenda_placement_reason.lower()
        ]
        assert len(petition_placements) >= 1


class TestHaltStateBehavior:
    """End-to-end tests for halt state handling (AC6)."""

    @pytest.mark.asyncio
    async def test_reads_allowed_during_halt(
        self, integration_setup: dict
    ) -> None:
        """AC6: Read operations succeed during system halt."""
        service = integration_setup["service"]
        halt_checker = integration_setup["halt_checker"]

        # Submit petition while not halted
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test content",
        )

        # Enter halt state
        halt_checker.set_halted(True)

        # Read operations should succeed
        petition = await service.get_petition(submit_result.petition_id)
        assert petition is not None
        assert petition.petition_id == submit_result.petition_id

        petitions, total = await service.list_open_petitions()
        assert total >= 0  # List should work

    @pytest.mark.asyncio
    async def test_writes_blocked_during_halt(
        self, integration_setup: dict
    ) -> None:
        """AC6: Write operations blocked during system halt."""
        service = integration_setup["service"]
        halt_checker = integration_setup["halt_checker"]

        # Submit petition while not halted
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test content",
        )

        # Enter halt state
        halt_checker.set_halted(True)

        # New submission should fail
        with pytest.raises(SystemHaltedError):
            await service.submit_petition(
                submitter_public_key="another_submitter",
                submitter_signature="another_sig",
                petition_content="Should fail during halt",
            )

        # Co-signing should fail
        with pytest.raises(SystemHaltedError):
            await service.cosign_petition(
                petition_id=submit_result.petition_id,
                cosigner_public_key="cosigner_pubkey",
                cosigner_signature="cosigner_sig",
            )


class TestSignatureVerificationFlow:
    """End-to-end tests for Ed25519 signature verification (AC4)."""

    @pytest.mark.asyncio
    async def test_invalid_submission_signature_rejected(
        self, integration_setup: dict
    ) -> None:
        """AC4: Invalid submitter signature rejected."""
        service = integration_setup["service"]
        signature_verifier = integration_setup["signature_verifier"]

        # Configure verifier to reject
        signature_verifier._accept_all = False

        with pytest.raises(InvalidSignatureError):
            await service.submit_petition(
                submitter_public_key="pubkey",
                submitter_signature="bad_sig",
                petition_content="Test",
            )

    @pytest.mark.asyncio
    async def test_invalid_cosigner_signature_rejected(
        self, integration_setup: dict
    ) -> None:
        """AC4: Invalid co-signer signature rejected."""
        service = integration_setup["service"]
        signature_verifier = integration_setup["signature_verifier"]

        # Submit petition with valid signature
        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="valid_sig",
            petition_content="Test",
        )

        # Now reject signatures
        signature_verifier._accept_all = False

        with pytest.raises(InvalidSignatureError):
            await service.cosign_petition(
                petition_id=submit_result.petition_id,
                cosigner_public_key="cosigner_pubkey",
                cosigner_signature="invalid_sig",
            )


class TestEventPayloadIntegrity:
    """Tests for event payload completeness (CT-12)."""

    @pytest.mark.asyncio
    async def test_petition_created_event_complete(
        self, integration_setup: dict
    ) -> None:
        """Petition created event contains all required fields."""
        service = integration_setup["service"]
        event_writer = integration_setup["event_writer"]

        await service.submit_petition(
            submitter_public_key="pubkey_hex",
            submitter_signature="sig_hex",
            petition_content="Detailed petition content here",
        )

        call_kwargs = event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify all required fields
        assert "petition_id" in payload
        assert "submitter_public_key" in payload
        assert payload["submitter_public_key"] == "pubkey_hex"
        assert "created_timestamp" in payload
        assert "petition_content" in payload
        assert payload["petition_content"] == "Detailed petition content here"
        assert "submitter_signature" in payload

    @pytest.mark.asyncio
    async def test_cosigned_event_complete(
        self, integration_setup: dict
    ) -> None:
        """Petition co-signed event contains all required fields."""
        service = integration_setup["service"]
        event_writer = integration_setup["event_writer"]

        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test",
        )

        event_writer.reset_mock()

        await service.cosign_petition(
            petition_id=submit_result.petition_id,
            cosigner_public_key="cosigner_pubkey_hex",
            cosigner_signature="cosigner_sig_hex",
        )

        call_kwargs = event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify all required fields
        assert "petition_id" in payload
        assert str(submit_result.petition_id) == payload["petition_id"]
        assert "cosigner_public_key" in payload
        assert payload["cosigner_public_key"] == "cosigner_pubkey_hex"
        assert "cosigned_timestamp" in payload
        assert "cosigner_sequence" in payload

    @pytest.mark.asyncio
    async def test_threshold_met_event_complete(
        self, integration_setup: dict
    ) -> None:
        """Threshold met event contains all required fields."""
        service = integration_setup["service"]
        event_writer = integration_setup["event_writer"]

        submit_result = await service.submit_petition(
            submitter_public_key="submitter_pubkey",
            submitter_signature="submitter_sig",
            petition_content="Test",
        )

        # Add 100 co-signers
        for i in range(PETITION_THRESHOLD_COSIGNERS):
            await service.cosign_petition(
                petition_id=submit_result.petition_id,
                cosigner_public_key=f"cosigner_{i}",
                cosigner_signature=f"sig_{i}",
            )

        # Find threshold met event
        for call in event_writer.write_event.call_args_list:
            if call.kwargs.get("event_type") == PETITION_THRESHOLD_MET_EVENT_TYPE:
                payload = call.kwargs["payload"]
                assert "petition_id" in payload
                assert "trigger_timestamp" in payload
                assert "final_cosigner_count" in payload
                assert payload["final_cosigner_count"] == PETITION_THRESHOLD_COSIGNERS
                assert "threshold" in payload
                assert payload["threshold"] == PETITION_THRESHOLD_COSIGNERS
                assert "cosigner_public_keys" in payload
                assert len(payload["cosigner_public_keys"]) == PETITION_THRESHOLD_COSIGNERS
                break
        else:
            pytest.fail("Threshold met event not found")


class TestIdempotencyFlow:
    """End-to-end tests for idempotent behavior."""

    @pytest.mark.asyncio
    async def test_duplicate_submission_creates_new_petition(
        self, integration_setup: dict
    ) -> None:
        """Same petition content can be submitted multiple times as new petitions."""
        service = integration_setup["service"]

        # First submission
        result1 = await service.submit_petition(
            submitter_public_key="pubkey",
            submitter_signature="sig",
            petition_content="Test content",
        )
        assert result1.petition_id is not None

        # Second submission with same details creates new petition
        # (different petition_id generated)
        result2 = await service.submit_petition(
            submitter_public_key="pubkey",
            submitter_signature="sig",
            petition_content="Test content",
        )
        assert result2.petition_id is not None
        assert result2.petition_id != result1.petition_id


class TestListingFlow:
    """End-to-end tests for petition listing."""

    @pytest.mark.asyncio
    async def test_list_open_petitions_pagination(
        self, integration_setup: dict
    ) -> None:
        """List open petitions with pagination."""
        service = integration_setup["service"]

        # Create 5 petitions
        for i in range(5):
            await service.submit_petition(
                submitter_public_key=f"pubkey_{i}",
                submitter_signature=f"sig_{i}",
                petition_content=f"Petition {i} content",
            )

        # List all
        petitions, total = await service.list_open_petitions()
        assert total == 5
        assert len(petitions) == 5

        # List with pagination
        petitions, total = await service.list_open_petitions(limit=2, offset=0)
        assert len(petitions) == 2
        assert total == 5

        petitions, total = await service.list_open_petitions(limit=2, offset=2)
        assert len(petitions) == 2
        assert total == 5

        petitions, total = await service.list_open_petitions(limit=2, offset=4)
        assert len(petitions) == 1
        assert total == 5

    @pytest.mark.asyncio
    async def test_closed_petitions_not_in_open_list(
        self, integration_setup: dict
    ) -> None:
        """Closed petitions not returned in open petition list."""
        service = integration_setup["service"]
        petition_repo = integration_setup["petition_repo"]

        # Create petition
        result = await service.submit_petition(
            submitter_public_key="pubkey",
            submitter_signature="sig",
            petition_content="Test",
        )

        # Verify it appears in list
        petitions, total = await service.list_open_petitions()
        assert total == 1

        # Close the petition directly in repo
        await petition_repo.update_status(result.petition_id, PetitionStatus.CLOSED)

        # Verify it no longer appears in open list
        petitions, total = await service.list_open_petitions()
        assert total == 0


class TestClosedPetitionBehavior:
    """Tests for behavior with closed petitions."""

    @pytest.mark.asyncio
    async def test_cannot_cosign_closed_petition(
        self, integration_setup: dict
    ) -> None:
        """Cannot co-sign a petition that has been closed."""
        service = integration_setup["service"]
        petition_repo = integration_setup["petition_repo"]

        # Create and close petition
        result = await service.submit_petition(
            submitter_public_key="pubkey",
            submitter_signature="sig",
            petition_content="Test",
        )
        await petition_repo.update_status(result.petition_id, PetitionStatus.CLOSED)

        # Attempt to co-sign closed petition
        with pytest.raises(PetitionClosedError):
            await service.cosign_petition(
                petition_id=result.petition_id,
                cosigner_public_key="cosigner",
                cosigner_signature="sig",
            )


class TestNonExistentPetition:
    """Tests for operations on non-existent petitions."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_petition(
        self, integration_setup: dict
    ) -> None:
        """Getting non-existent petition returns None."""
        service = integration_setup["service"]

        result = await service.get_petition(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_cosign_nonexistent_petition(
        self, integration_setup: dict
    ) -> None:
        """Co-signing non-existent petition raises error."""
        service = integration_setup["service"]

        with pytest.raises(PetitionNotFoundError):
            await service.cosign_petition(
                petition_id=uuid4(),
                cosigner_public_key="cosigner",
                cosigner_signature="sig",
            )
