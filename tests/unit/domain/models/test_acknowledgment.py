"""Unit tests for Acknowledgment domain model.

Story: 3.2 - Acknowledgment Execution Service
FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.acknowledgment import (
    ACKNOWLEDGMENT_SCHEMA_VERSION,
    MIN_ACKNOWLEDGING_ARCHONS,
    Acknowledgment,
    AlreadyAcknowledgedError,
    InsufficientArchonsError,
)
from src.domain.models.acknowledgment_reason import (
    AcknowledgmentReasonCode,
    RationaleRequiredError,
    ReferenceRequiredError,
)


class TestAcknowledgmentCreation:
    """Tests for Acknowledgment domain model creation."""

    def test_create_valid_acknowledgment_noted(self) -> None:
        """Valid NOTED acknowledgment creates successfully."""
        petition_id = uuid4()
        archon_ids = (15, 42)

        ack = Acknowledgment.create(
            petition_id=petition_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=archon_ids,
            witness_hash="blake3:abc123",
        )

        assert ack.petition_id == petition_id
        assert ack.reason_code == AcknowledgmentReasonCode.NOTED
        assert ack.acknowledging_archon_ids == archon_ids
        assert ack.rationale is None
        assert ack.reference_petition_id is None
        assert ack.witness_hash == "blake3:abc123"
        assert ack.id is not None

    def test_create_valid_acknowledgment_addressed(self) -> None:
        """Valid ADDRESSED acknowledgment creates successfully."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.ADDRESSED,
            acknowledging_archon_ids=(1, 2, 3),
            witness_hash="blake3:def456",
        )

        assert ack.reason_code == AcknowledgmentReasonCode.ADDRESSED
        assert ack.archon_count == 3

    def test_create_valid_acknowledgment_with_rationale(self) -> None:
        """Acknowledgment with optional rationale creates successfully."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.OUT_OF_SCOPE,
            acknowledging_archon_ids=(10, 20),
            witness_hash="blake3:ghi789",
            rationale="This matter falls outside our jurisdiction",
        )

        assert ack.has_rationale is True
        assert ack.rationale == "This matter falls outside our jurisdiction"

    def test_create_refused_requires_rationale(self) -> None:
        """REFUSED without rationale raises RationaleRequiredError."""
        with pytest.raises(RationaleRequiredError) as exc_info:
            Acknowledgment.create(
                petition_id=uuid4(),
                reason_code=AcknowledgmentReasonCode.REFUSED,
                acknowledging_archon_ids=(15, 42),
                witness_hash="blake3:xxx",
                rationale=None,
            )
        assert exc_info.value.reason_code == AcknowledgmentReasonCode.REFUSED

    def test_create_refused_with_rationale_succeeds(self) -> None:
        """REFUSED with rationale creates successfully per FR-3.3."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.REFUSED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
            rationale="Petition violates community guidelines",
        )

        assert ack.reason_code == AcknowledgmentReasonCode.REFUSED
        assert ack.rationale == "Petition violates community guidelines"

    def test_create_no_action_warranted_requires_rationale(self) -> None:
        """NO_ACTION_WARRANTED without rationale raises RationaleRequiredError."""
        with pytest.raises(RationaleRequiredError):
            Acknowledgment.create(
                petition_id=uuid4(),
                reason_code=AcknowledgmentReasonCode.NO_ACTION_WARRANTED,
                acknowledging_archon_ids=(15, 42),
                witness_hash="blake3:xxx",
            )

    def test_create_no_action_warranted_with_rationale_succeeds(self) -> None:
        """NO_ACTION_WARRANTED with rationale creates successfully."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NO_ACTION_WARRANTED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
            rationale="After careful review, existing policies address this concern",
        )

        assert ack.reason_code == AcknowledgmentReasonCode.NO_ACTION_WARRANTED
        assert ack.has_rationale is True

    def test_create_duplicate_requires_reference(self) -> None:
        """DUPLICATE without reference raises ReferenceRequiredError."""
        with pytest.raises(ReferenceRequiredError):
            Acknowledgment.create(
                petition_id=uuid4(),
                reason_code=AcknowledgmentReasonCode.DUPLICATE,
                acknowledging_archon_ids=(15, 42),
                witness_hash="blake3:xxx",
            )

    def test_create_duplicate_with_reference_succeeds(self) -> None:
        """DUPLICATE with reference creates successfully per FR-3.4."""
        reference_id = uuid4()
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.DUPLICATE,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
            reference_petition_id=reference_id,
        )

        assert ack.reason_code == AcknowledgmentReasonCode.DUPLICATE
        assert ack.reference_petition_id == reference_id
        assert ack.is_duplicate_reference is True


class TestArchonCountValidation:
    """Tests for minimum archon count validation."""

    def test_minimum_two_archons_required(self) -> None:
        """At least 2 archons required per FR-11.5."""
        with pytest.raises(InsufficientArchonsError) as exc_info:
            Acknowledgment.create(
                petition_id=uuid4(),
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15,),  # Only 1
                witness_hash="blake3:xxx",
            )
        assert exc_info.value.actual_count == 1

    def test_zero_archons_fails(self) -> None:
        """Zero archons fails validation."""
        with pytest.raises(InsufficientArchonsError) as exc_info:
            Acknowledgment.create(
                petition_id=uuid4(),
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(),
                witness_hash="blake3:xxx",
            )
        assert exc_info.value.actual_count == 0

    def test_two_archons_succeeds(self) -> None:
        """Exactly 2 archons succeeds (2-of-3 supermajority)."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
        )
        assert ack.archon_count == 2
        assert ack.is_unanimous is False

    def test_three_archons_unanimous(self) -> None:
        """All 3 archons is unanimous."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42, 67),
            witness_hash="blake3:xxx",
        )
        assert ack.archon_count == 3
        assert ack.is_unanimous is True


class TestWitnessHashValidation:
    """Tests for witness hash validation (CT-12)."""

    def test_witness_hash_required(self) -> None:
        """Witness hash is required for CT-12 compliance."""
        with pytest.raises(ValueError, match="witness_hash is required"):
            Acknowledgment.create(
                petition_id=uuid4(),
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
                witness_hash="",
            )

    def test_witness_hash_cannot_be_whitespace(self) -> None:
        """Witness hash cannot be whitespace only."""
        with pytest.raises(ValueError, match="witness_hash is required"):
            Acknowledgment.create(
                petition_id=uuid4(),
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
                witness_hash="   ",
            )


class TestAcknowledgmentSerialization:
    """Tests for Acknowledgment serialization."""

    def test_to_dict_basic(self) -> None:
        """to_dict produces correct dictionary."""
        ack_id = uuid4()
        petition_id = uuid4()
        acknowledged_at = datetime.now(timezone.utc)

        ack = Acknowledgment(
            id=ack_id,
            petition_id=petition_id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            rationale=None,
            reference_petition_id=None,
            acknowledging_archon_ids=(15, 42),
            acknowledged_by_king_id=None,
            acknowledged_at=acknowledged_at,
            witness_hash="blake3:abc",
        )

        result = ack.to_dict()

        assert result["id"] == str(ack_id)
        assert result["petition_id"] == str(petition_id)
        assert result["reason_code"] == "NOTED"
        assert result["rationale"] is None
        assert result["reference_petition_id"] is None
        assert result["acknowledging_archon_ids"] == [15, 42]
        assert result["acknowledged_by_king_id"] is None
        assert result["acknowledged_at"] == acknowledged_at.isoformat()
        assert result["witness_hash"] == "blake3:abc"
        assert result["schema_version"] == ACKNOWLEDGMENT_SCHEMA_VERSION

    def test_to_dict_with_rationale_and_reference(self) -> None:
        """to_dict includes rationale and reference when present."""
        # Note: DUPLICATE requires reference, not rationale
        # Use REFUSED for rationale test
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.REFUSED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:abc",
            rationale="Policy violation",
        )

        result = ack.to_dict()
        assert result["rationale"] == "Policy violation"


class TestAcknowledgmentProperties:
    """Tests for Acknowledgment computed properties."""

    def test_archon_count(self) -> None:
        """archon_count returns correct count."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42, 67),
            witness_hash="blake3:xxx",
        )
        assert ack.archon_count == 3

    def test_is_unanimous_true(self) -> None:
        """is_unanimous is True when all 3 archons vote."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42, 67),
            witness_hash="blake3:xxx",
        )
        assert ack.is_unanimous is True

    def test_is_unanimous_false(self) -> None:
        """is_unanimous is False when only 2 archons vote."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
        )
        assert ack.is_unanimous is False

    def test_has_rationale_true(self) -> None:
        """has_rationale is True when rationale provided."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.REFUSED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
            rationale="Policy violation",
        )
        assert ack.has_rationale is True

    def test_has_rationale_false(self) -> None:
        """has_rationale is False when no rationale."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
        )
        assert ack.has_rationale is False

    def test_is_duplicate_reference_true(self) -> None:
        """is_duplicate_reference is True for DUPLICATE code."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.DUPLICATE,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
            reference_petition_id=uuid4(),
        )
        assert ack.is_duplicate_reference is True

    def test_is_duplicate_reference_false(self) -> None:
        """is_duplicate_reference is False for non-DUPLICATE codes."""
        ack = Acknowledgment.create(
            petition_id=uuid4(),
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
            witness_hash="blake3:xxx",
        )
        assert ack.is_duplicate_reference is False


class TestExceptionClasses:
    """Tests for acknowledgment exception classes."""

    def test_insufficient_archons_error_message(self) -> None:
        """InsufficientArchonsError has informative message."""
        error = InsufficientArchonsError(actual_count=1)
        assert "2" in str(error)  # Minimum required
        assert "1" in str(error)  # Actual provided
        assert "FR-11.5" in str(error)  # Requirement reference

    def test_already_acknowledged_error_message(self) -> None:
        """AlreadyAcknowledgedError has informative message."""
        petition_id = uuid4()
        ack_id = uuid4()
        error = AlreadyAcknowledgedError(petition_id, ack_id)
        assert str(petition_id) in str(error)
        assert str(ack_id) in str(error)
        assert "NFR-3.2" in str(error)


class TestMinimumArchonConstant:
    """Tests for MIN_ACKNOWLEDGING_ARCHONS constant."""

    def test_constant_value(self) -> None:
        """MIN_ACKNOWLEDGING_ARCHONS is 2."""
        assert MIN_ACKNOWLEDGING_ARCHONS == 2

    def test_constant_matches_supermajority(self) -> None:
        """Constant matches 2-of-3 supermajority requirement."""
        # 2 out of 3 is supermajority (>50%)
        assert MIN_ACKNOWLEDGING_ARCHONS >= 2
        assert MIN_ACKNOWLEDGING_ARCHONS <= 3
