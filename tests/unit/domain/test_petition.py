"""Unit tests for Petition domain models (Story 7.2, FR39).

Tests cover:
- Petition creation and immutability
- CoSigner creation and immutability
- Adding co-signers
- Duplicate co-signer detection
- Status transitions
- Threshold tracking
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition


class TestCoSigner:
    """Tests for CoSigner domain model."""

    @pytest.fixture
    def sample_cosigner(self) -> CoSigner:
        """Create a sample co-signer for testing."""
        return CoSigner(
            public_key="cosigner_key_abc123",
            signature="cosigner_sig_def456",
            signed_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            sequence=1,
        )

    def test_creation(self, sample_cosigner: CoSigner) -> None:
        """Test co-signer creation with all fields."""
        assert sample_cosigner.public_key == "cosigner_key_abc123"
        assert sample_cosigner.signature == "cosigner_sig_def456"
        assert sample_cosigner.sequence == 1
        assert sample_cosigner.signed_at.year == 2026

    def test_is_frozen(self, sample_cosigner: CoSigner) -> None:
        """Test co-signer is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_cosigner.sequence = 99  # type: ignore[misc]

    def test_equality(self) -> None:
        """Test co-signer equality based on all fields."""
        timestamp = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        cs1 = CoSigner(
            public_key="key1",
            signature="sig1",
            signed_at=timestamp,
            sequence=1,
        )
        cs2 = CoSigner(
            public_key="key1",
            signature="sig1",
            signed_at=timestamp,
            sequence=1,
        )
        cs3 = CoSigner(
            public_key="key2",
            signature="sig1",
            signed_at=timestamp,
            sequence=1,
        )

        assert cs1 == cs2
        assert cs1 != cs3


class TestPetition:
    """Tests for Petition domain model."""

    @pytest.fixture
    def sample_petition(self) -> Petition:
        """Create a sample petition for testing."""
        return Petition(
            petition_id=uuid4(),
            submitter_public_key="submitter_key_abc",
            submitter_signature="submitter_sig_def",
            petition_content="Concern about integrity failures",
            created_timestamp=datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
        )

    def test_creation_default_status(self, sample_petition: Petition) -> None:
        """Test petition creation with default status (open)."""
        assert sample_petition.status == PetitionStatus.OPEN
        assert sample_petition.cosigners == ()
        assert sample_petition.threshold_met_at is None

    def test_creation_with_all_fields(self) -> None:
        """Test petition creation with all fields."""
        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="key123",
            submitter_signature="sig456",
            petition_content="Test content",
            created_timestamp=datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
            status=PetitionStatus.THRESHOLD_MET,
            cosigners=(
                CoSigner(
                    public_key="cs_key",
                    signature="cs_sig",
                    signed_at=datetime.now(timezone.utc),
                    sequence=1,
                ),
            ),
            threshold_met_at=datetime(2026, 1, 8, 11, 0, 0, tzinfo=timezone.utc),
        )
        assert petition.status == PetitionStatus.THRESHOLD_MET
        assert len(petition.cosigners) == 1
        assert petition.threshold_met_at is not None

    def test_is_frozen(self, sample_petition: Petition) -> None:
        """Test petition is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_petition.status = PetitionStatus.CLOSED  # type: ignore[misc]

    def test_cosigner_count_empty(self, sample_petition: Petition) -> None:
        """Test cosigner_count with no co-signers."""
        assert sample_petition.cosigner_count == 0

    def test_cosigner_count_with_cosigners(self, sample_petition: Petition) -> None:
        """Test cosigner_count with co-signers added."""
        cs = CoSigner(
            public_key="cs_key",
            signature="cs_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        updated = sample_petition.add_cosigner(cs)
        assert updated.cosigner_count == 1

    def test_all_public_keys_submitter_only(self, sample_petition: Petition) -> None:
        """Test all_public_keys with only submitter."""
        keys = sample_petition.all_public_keys
        assert len(keys) == 1
        assert keys[0] == sample_petition.submitter_public_key

    def test_all_public_keys_with_cosigners(self, sample_petition: Petition) -> None:
        """Test all_public_keys includes co-signers."""
        cs1 = CoSigner(
            public_key="cs_key_1",
            signature="cs_sig_1",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        cs2 = CoSigner(
            public_key="cs_key_2",
            signature="cs_sig_2",
            signed_at=datetime.now(timezone.utc),
            sequence=2,
        )
        updated = sample_petition.add_cosigner(cs1).add_cosigner(cs2)

        keys = updated.all_public_keys
        assert len(keys) == 3
        assert updated.submitter_public_key in keys
        assert "cs_key_1" in keys
        assert "cs_key_2" in keys

    def test_has_cosigned_submitter(self, sample_petition: Petition) -> None:
        """Test has_cosigned returns True for submitter."""
        assert sample_petition.has_cosigned(sample_petition.submitter_public_key)

    def test_has_cosigned_cosigner(self, sample_petition: Petition) -> None:
        """Test has_cosigned returns True for existing co-signer."""
        cs = CoSigner(
            public_key="cs_key",
            signature="cs_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        updated = sample_petition.add_cosigner(cs)
        assert updated.has_cosigned("cs_key")

    def test_has_cosigned_not_found(self, sample_petition: Petition) -> None:
        """Test has_cosigned returns False for unknown key."""
        assert not sample_petition.has_cosigned("unknown_key")

    def test_add_cosigner_returns_new_petition(self, sample_petition: Petition) -> None:
        """Test add_cosigner returns new Petition instance."""
        cs = CoSigner(
            public_key="cs_key",
            signature="cs_sig",
            signed_at=datetime.now(timezone.utc),
            sequence=1,
        )
        updated = sample_petition.add_cosigner(cs)

        # Original unchanged
        assert sample_petition.cosigner_count == 0
        # New has co-signer
        assert updated.cosigner_count == 1
        # Different instances
        assert updated is not sample_petition

    def test_add_multiple_cosigners(self, sample_petition: Petition) -> None:
        """Test adding multiple co-signers."""
        updated = sample_petition
        for i in range(5):
            cs = CoSigner(
                public_key=f"cs_key_{i}",
                signature=f"cs_sig_{i}",
                signed_at=datetime.now(timezone.utc),
                sequence=i + 1,
            )
            updated = updated.add_cosigner(cs)

        assert updated.cosigner_count == 5
        for i in range(5):
            assert updated.has_cosigned(f"cs_key_{i}")

    def test_with_status_returns_new_petition(self, sample_petition: Petition) -> None:
        """Test with_status returns new Petition instance."""
        updated = sample_petition.with_status(PetitionStatus.CLOSED)

        # Original unchanged
        assert sample_petition.status == PetitionStatus.OPEN
        # New has updated status
        assert updated.status == PetitionStatus.CLOSED
        # Different instances
        assert updated is not sample_petition

    def test_with_threshold_met(self, sample_petition: Petition) -> None:
        """Test with_threshold_met updates status and timestamp."""
        met_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        updated = sample_petition.with_threshold_met(met_at)

        # Original unchanged
        assert sample_petition.status == PetitionStatus.OPEN
        assert sample_petition.threshold_met_at is None

        # New has threshold met
        assert updated.status == PetitionStatus.THRESHOLD_MET
        assert updated.threshold_met_at == met_at

    def test_canonical_content_bytes(self, sample_petition: Petition) -> None:
        """Test canonical_content_bytes returns petition content as UTF-8."""
        content_bytes = sample_petition.canonical_content_bytes()
        assert isinstance(content_bytes, bytes)
        assert content_bytes == sample_petition.petition_content.encode("utf-8")

    def test_canonical_content_bytes_determinism(self) -> None:
        """Test canonical_content_bytes is deterministic."""
        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="key",
            submitter_signature="sig",
            petition_content="Test content for signature",
            created_timestamp=datetime.now(timezone.utc),
        )

        bytes1 = petition.canonical_content_bytes()
        bytes2 = petition.canonical_content_bytes()
        assert bytes1 == bytes2

    def test_add_100_cosigners_for_threshold(self) -> None:
        """Test adding exactly 100 co-signers (FR39 threshold boundary)."""
        petition = Petition(
            petition_id=uuid4(),
            submitter_public_key="submitter_key",
            submitter_signature="submitter_sig",
            petition_content="Test petition",
            created_timestamp=datetime.now(timezone.utc),
        )

        for i in range(100):
            cs = CoSigner(
                public_key=f"cosigner_key_{i}",
                signature=f"cosigner_sig_{i}",
                signed_at=datetime.now(timezone.utc),
                sequence=i + 1,
            )
            petition = petition.add_cosigner(cs)

        assert petition.cosigner_count == 100
        assert len(petition.all_public_keys) == 101  # submitter + 100 co-signers

    def test_cosigners_tuple_is_immutable(self, sample_petition: Petition) -> None:
        """Test cosigners tuple cannot be modified."""
        assert isinstance(sample_petition.cosigners, tuple)
