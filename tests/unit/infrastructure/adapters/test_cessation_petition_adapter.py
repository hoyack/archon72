"""Unit tests for CessationPetitionAdapter (Story 0.3, AC1, AC5, AC7).

Tests verify bidirectional model conversion between Story 7.2 Petition
and Story 0.2 PetitionSubmission models with proper state mapping
and ID preservation (FR-9.4).
"""

import uuid
from datetime import datetime, timezone

import pytest

from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.adapters.petition_migration.cessation_adapter import (
    CESSATION_REALM,
    STATUS_TO_STATE_MAP,
    STATE_TO_STATUS_MAP,
    CessationPetitionAdapter,
)


def _make_petition(
    petition_id: uuid.UUID | None = None,
    content: str = "Test cessation petition content",
    status: PetitionStatus = PetitionStatus.OPEN,
    cosigners: tuple[CoSigner, ...] = (),
    threshold_met_at: datetime | None = None,
) -> Petition:
    """Helper to create a Petition for testing."""
    return Petition(
        petition_id=petition_id or uuid.uuid4(),
        submitter_public_key="abcd1234" * 8,  # 64 hex chars
        submitter_signature="ef567890" * 16,  # 128 hex chars
        petition_content=content,
        created_timestamp=datetime.now(timezone.utc),
        status=status,
        cosigners=cosigners,
        threshold_met_at=threshold_met_at,
    )


def _make_cosigner(sequence: int = 1) -> CoSigner:
    """Helper to create a CoSigner for testing."""
    return CoSigner(
        public_key=f"cosigner{sequence:02d}" + "x" * 54,  # 64 hex chars
        signature="sig" + "y" * 125,  # 128 hex chars
        signed_at=datetime.now(timezone.utc),
        sequence=sequence,
    )


def _make_submission(
    submission_id: uuid.UUID | None = None,
    text: str = "Test petition content",
    state: PetitionState = PetitionState.RECEIVED,
) -> PetitionSubmission:
    """Helper to create a PetitionSubmission for testing."""
    return PetitionSubmission(
        id=submission_id or uuid.uuid4(),
        type=PetitionType.CESSATION,
        text=text,
        state=state,
        realm=CESSATION_REALM,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestStatusMapping:
    """Tests for state mapping constants (AC1)."""

    def test_open_maps_to_received(self) -> None:
        """Verify OPEN status maps to RECEIVED state."""
        assert STATUS_TO_STATE_MAP[PetitionStatus.OPEN] == PetitionState.RECEIVED

    def test_threshold_met_maps_to_escalated(self) -> None:
        """Verify THRESHOLD_MET status maps to ESCALATED state."""
        assert STATUS_TO_STATE_MAP[PetitionStatus.THRESHOLD_MET] == PetitionState.ESCALATED

    def test_closed_maps_to_acknowledged(self) -> None:
        """Verify CLOSED status maps to ACKNOWLEDGED state."""
        assert STATUS_TO_STATE_MAP[PetitionStatus.CLOSED] == PetitionState.ACKNOWLEDGED

    def test_reverse_mapping_received_to_open(self) -> None:
        """Verify RECEIVED state maps back to OPEN status."""
        assert STATE_TO_STATUS_MAP[PetitionState.RECEIVED] == PetitionStatus.OPEN

    def test_reverse_mapping_escalated_to_threshold_met(self) -> None:
        """Verify ESCALATED state maps back to THRESHOLD_MET status."""
        assert STATE_TO_STATUS_MAP[PetitionState.ESCALATED] == PetitionStatus.THRESHOLD_MET

    def test_reverse_mapping_acknowledged_to_closed(self) -> None:
        """Verify ACKNOWLEDGED state maps back to CLOSED status."""
        assert STATE_TO_STATUS_MAP[PetitionState.ACKNOWLEDGED] == PetitionStatus.CLOSED


class TestToSubmission:
    """Tests for to_submission conversion (AC1)."""

    def test_converts_petition_content_to_text(self) -> None:
        """Verify petition_content maps to text."""
        petition = _make_petition(content="Cessation concern: System breach")
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.text == "Cessation concern: System breach"

    def test_preserves_petition_id_exactly_fr94(self) -> None:
        """Verify petition_id is preserved exactly (FR-9.4)."""
        specific_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        petition = _make_petition(petition_id=specific_id)
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.id == specific_id
        assert str(submission.id) == "12345678-1234-5678-1234-567812345678"

    def test_preserves_created_timestamp(self) -> None:
        """Verify created_timestamp maps to created_at."""
        petition = _make_petition()
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.created_at == petition.created_timestamp

    def test_sets_type_to_cessation(self) -> None:
        """Verify type is hardcoded to CESSATION."""
        petition = _make_petition()
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.type == PetitionType.CESSATION

    def test_sets_realm_to_cessation_realm(self) -> None:
        """Verify realm is hardcoded to cessation-realm."""
        petition = _make_petition()
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.realm == CESSATION_REALM

    def test_maps_open_status_to_received_state(self) -> None:
        """Verify OPEN status maps to RECEIVED state."""
        petition = _make_petition(status=PetitionStatus.OPEN)
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.state == PetitionState.RECEIVED

    def test_maps_threshold_met_status_to_escalated_state(self) -> None:
        """Verify THRESHOLD_MET status maps to ESCALATED state."""
        petition = _make_petition(
            status=PetitionStatus.THRESHOLD_MET,
            threshold_met_at=datetime.now(timezone.utc),
        )
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.state == PetitionState.ESCALATED

    def test_maps_closed_status_to_acknowledged_state(self) -> None:
        """Verify CLOSED status maps to ACKNOWLEDGED state."""
        petition = _make_petition(status=PetitionStatus.CLOSED)
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.state == PetitionState.ACKNOWLEDGED


class TestFromSubmission:
    """Tests for from_submission conversion (AC1)."""

    def test_converts_text_to_petition_content(self) -> None:
        """Verify text maps to petition_content."""
        submission = _make_submission(text="Restored petition content")
        cosigners = ()
        petition = CessationPetitionAdapter.from_submission(
            submission, cosigners, submitter_public_key="a" * 64, submitter_signature="b" * 128
        )
        assert petition.petition_content == "Restored petition content"

    def test_preserves_submission_id_as_petition_id_fr94(self) -> None:
        """Verify submission.id is preserved as petition_id (FR-9.4)."""
        specific_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        submission = _make_submission(submission_id=specific_id)
        petition = CessationPetitionAdapter.from_submission(
            submission, (), submitter_public_key="a" * 64, submitter_signature="b" * 128
        )
        assert petition.petition_id == specific_id

    def test_preserves_cosigners(self) -> None:
        """Verify co-signers are preserved in reverse conversion."""
        submission = _make_submission()
        cosigners = (_make_cosigner(1), _make_cosigner(2))
        petition = CessationPetitionAdapter.from_submission(
            submission, cosigners, submitter_public_key="a" * 64, submitter_signature="b" * 128
        )
        assert petition.cosigners == cosigners
        assert petition.cosigner_count == 2

    def test_maps_received_state_to_open_status(self) -> None:
        """Verify RECEIVED state maps to OPEN status."""
        submission = _make_submission(state=PetitionState.RECEIVED)
        petition = CessationPetitionAdapter.from_submission(
            submission, (), submitter_public_key="a" * 64, submitter_signature="b" * 128
        )
        assert petition.status == PetitionStatus.OPEN

    def test_maps_escalated_state_to_threshold_met_status(self) -> None:
        """Verify ESCALATED state maps to THRESHOLD_MET status."""
        submission = _make_submission(state=PetitionState.ESCALATED)
        petition = CessationPetitionAdapter.from_submission(
            submission, (), submitter_public_key="a" * 64, submitter_signature="b" * 128
        )
        assert petition.status == PetitionStatus.THRESHOLD_MET

    def test_maps_acknowledged_state_to_closed_status(self) -> None:
        """Verify ACKNOWLEDGED state maps to CLOSED status."""
        submission = _make_submission(state=PetitionState.ACKNOWLEDGED)
        petition = CessationPetitionAdapter.from_submission(
            submission, (), submitter_public_key="a" * 64, submitter_signature="b" * 128
        )
        assert petition.status == PetitionStatus.CLOSED


class TestRoundTrip:
    """Tests for round-trip conversion (AC7)."""

    def test_petition_roundtrip_preserves_id(self) -> None:
        """Verify petition ID survives round-trip conversion (FR-9.4)."""
        original_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        original = _make_petition(petition_id=original_id)
        submission = CessationPetitionAdapter.to_submission(original)
        restored = CessationPetitionAdapter.from_submission(
            submission,
            original.cosigners,
            submitter_public_key=original.submitter_public_key,
            submitter_signature=original.submitter_signature,
        )
        assert restored.petition_id == original_id

    def test_petition_roundtrip_preserves_content(self) -> None:
        """Verify petition content survives round-trip conversion."""
        original = _make_petition(content="Important cessation concern")
        submission = CessationPetitionAdapter.to_submission(original)
        restored = CessationPetitionAdapter.from_submission(
            submission,
            original.cosigners,
            submitter_public_key=original.submitter_public_key,
            submitter_signature=original.submitter_signature,
        )
        assert restored.petition_content == original.petition_content

    def test_petition_roundtrip_preserves_status(self) -> None:
        """Verify petition status survives round-trip conversion."""
        for status in [PetitionStatus.OPEN, PetitionStatus.THRESHOLD_MET, PetitionStatus.CLOSED]:
            original = _make_petition(status=status)
            if status == PetitionStatus.THRESHOLD_MET:
                original = _make_petition(
                    status=status, threshold_met_at=datetime.now(timezone.utc)
                )
            submission = CessationPetitionAdapter.to_submission(original)
            restored = CessationPetitionAdapter.from_submission(
                submission,
                original.cosigners,
                submitter_public_key=original.submitter_public_key,
                submitter_signature=original.submitter_signature,
            )
            assert restored.status == status, f"Status {status} not preserved"


class TestEdgeCases:
    """Tests for edge cases (AC7)."""

    def test_empty_content(self) -> None:
        """Verify empty content is handled."""
        petition = _make_petition(content="")
        submission = CessationPetitionAdapter.to_submission(petition)
        assert submission.text == ""

    def test_max_length_content(self) -> None:
        """Verify content at max length (10000 chars) is handled."""
        max_content = "x" * 10000
        petition = _make_petition(content=max_content)
        submission = CessationPetitionAdapter.to_submission(petition)
        assert len(submission.text) == 10000

    def test_no_cosigners(self) -> None:
        """Verify petition with no co-signers is handled."""
        petition = _make_petition(cosigners=())
        submission = CessationPetitionAdapter.to_submission(petition)
        restored = CessationPetitionAdapter.from_submission(
            submission,
            (),
            submitter_public_key=petition.submitter_public_key,
            submitter_signature=petition.submitter_signature,
        )
        assert restored.cosigner_count == 0

    def test_many_cosigners(self) -> None:
        """Verify petition with 100+ co-signers is handled."""
        cosigners = tuple(_make_cosigner(i) for i in range(1, 101))
        petition = _make_petition(cosigners=cosigners)
        submission = CessationPetitionAdapter.to_submission(petition)
        restored = CessationPetitionAdapter.from_submission(
            submission,
            cosigners,
            submitter_public_key=petition.submitter_public_key,
            submitter_signature=petition.submitter_signature,
        )
        assert restored.cosigner_count == 100
