"""Unit tests for CeremonyEvidence (Story 3.4, AC #4, #5).

Tests the domain model for ceremony evidence validation.
ADR-6: Halt clearing is Tier 1 ceremony (2 Keepers required).
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.errors.halt_clear import (
    InsufficientApproversError,
    InvalidCeremonyError,
)
from src.domain.models.ceremony_evidence import (
    HALT_CLEAR_CEREMONY_TYPE,
    MIN_APPROVERS_TIER_1,
    ApproverSignature,
    CeremonyEvidence,
)


class TestApproverSignature:
    """Tests for ApproverSignature dataclass."""

    def test_create_approver_signature(self) -> None:
        """Test creating a valid ApproverSignature."""
        signed_at = datetime.now(timezone.utc)
        signature = ApproverSignature(
            keeper_id="keeper-001",
            signature=b"test_signature_bytes",
            signed_at=signed_at,
        )

        assert signature.keeper_id == "keeper-001"
        assert signature.signature == b"test_signature_bytes"
        assert signature.signed_at == signed_at

    def test_approver_signature_is_immutable(self) -> None:
        """Test that ApproverSignature is frozen (immutable)."""
        signature = ApproverSignature(
            keeper_id="keeper-001",
            signature=b"test",
            signed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            signature.keeper_id = "modified"  # type: ignore[misc]


class TestCeremonyEvidence:
    """Tests for CeremonyEvidence dataclass."""

    def test_create_ceremony_evidence(self) -> None:
        """Test creating valid CeremonyEvidence."""
        ceremony_id = uuid4()
        created_at = datetime.now(timezone.utc)
        approvers = (
            ApproverSignature("keeper-001", b"sig1", datetime.now(timezone.utc)),
            ApproverSignature("keeper-002", b"sig2", datetime.now(timezone.utc)),
        )

        evidence = CeremonyEvidence(
            ceremony_id=ceremony_id,
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=approvers,
            created_at=created_at,
        )

        assert evidence.ceremony_id == ceremony_id
        assert evidence.ceremony_type == HALT_CLEAR_CEREMONY_TYPE
        assert evidence.approvers == approvers
        assert evidence.created_at == created_at

    def test_ceremony_evidence_is_immutable(self) -> None:
        """Test that CeremonyEvidence is frozen (immutable)."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-001", b"sig1", datetime.now(timezone.utc)),
                ApproverSignature("keeper-002", b"sig2", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            evidence.ceremony_type = "modified"  # type: ignore[misc]

    def test_ceremony_evidence_converts_list_to_tuple(self) -> None:
        """Test that list approvers are converted to tuple for immutability."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=[  # type: ignore[arg-type]
                ApproverSignature("keeper-001", b"sig1", datetime.now(timezone.utc)),
                ApproverSignature("keeper-002", b"sig2", datetime.now(timezone.utc)),
            ],
            created_at=datetime.now(timezone.utc),
        )
        assert isinstance(evidence.approvers, tuple)


class TestCeremonyEvidenceValidation:
    """Tests for CeremonyEvidence.validate() method - AC #4, #5."""

    def test_validate_with_two_approvers_succeeds(self) -> None:
        """Test that validation succeeds with exactly 2 approvers (Tier 1 minimum)."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-001", b"sig1", datetime.now(timezone.utc)),
                ApproverSignature("keeper-002", b"sig2", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )

        # Should not raise
        assert evidence.validate() is True

    def test_validate_with_more_than_two_approvers_succeeds(self) -> None:
        """Test that validation succeeds with more than 2 approvers."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-001", b"sig1", datetime.now(timezone.utc)),
                ApproverSignature("keeper-002", b"sig2", datetime.now(timezone.utc)),
                ApproverSignature("keeper-003", b"sig3", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )

        assert evidence.validate() is True

    def test_validate_with_one_approver_raises_insufficient_error(self) -> None:
        """Test that validation fails with only 1 approver (AC #5)."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-001", b"sig1", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(InsufficientApproversError) as exc_info:
            evidence.validate()
        assert "ADR-6" in str(exc_info.value)
        assert "2 Keepers" in str(exc_info.value)

    def test_validate_with_zero_approvers_raises_insufficient_error(self) -> None:
        """Test that validation fails with 0 approvers."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(),
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(InsufficientApproversError) as exc_info:
            evidence.validate()
        assert "got 0" in str(exc_info.value)

    def test_validate_with_empty_signature_raises_invalid_ceremony(self) -> None:
        """Test that validation fails with empty signature bytes."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-001", b"valid_sig", datetime.now(timezone.utc)),
                ApproverSignature("keeper-002", b"", datetime.now(timezone.utc)),  # Empty!
            ),
            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(InvalidCeremonyError) as exc_info:
            evidence.validate()
        assert "keeper-002" in str(exc_info.value)


class TestCeremonyConstants:
    """Tests for ceremony constants."""

    def test_halt_clear_ceremony_type(self) -> None:
        """Test the halt clear ceremony type constant."""
        assert HALT_CLEAR_CEREMONY_TYPE == "halt_clear"

    def test_min_approvers_tier_1(self) -> None:
        """Test the minimum approvers for Tier 1 ceremony (ADR-6)."""
        assert MIN_APPROVERS_TIER_1 == 2


class TestApproverSignatureEquality:
    """Tests for ApproverSignature equality."""

    def test_equal_signatures(self) -> None:
        """Test that identical signatures are equal."""
        signed_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sig1 = ApproverSignature("keeper-001", b"sig", signed_at)
        sig2 = ApproverSignature("keeper-001", b"sig", signed_at)
        assert sig1 == sig2

    def test_different_signatures(self) -> None:
        """Test that different signatures are not equal."""
        signed_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sig1 = ApproverSignature("keeper-001", b"sig1", signed_at)
        sig2 = ApproverSignature("keeper-001", b"sig2", signed_at)
        assert sig1 != sig2


class TestCeremonyEvidenceKeeperIds:
    """Tests for extracting keeper IDs from ceremony evidence."""

    def test_get_keeper_ids(self) -> None:
        """Test that keeper IDs can be extracted from approvers."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-001", b"sig1", datetime.now(timezone.utc)),
                ApproverSignature("keeper-002", b"sig2", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )

        keeper_ids = evidence.get_keeper_ids()
        assert keeper_ids == ("keeper-001", "keeper-002")
