"""Unit tests for DissentRecord domain model (Story 2B.1, FR-11.8).

Tests the dissent record model and its invariants.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import blake3
import pytest
from uuid6 import uuid7

from src.domain.models.deliberation_session import DeliberationOutcome
from src.domain.models.dissent_record import (
    BLAKE3_HASH_LENGTH,
    DissentRecord,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _compute_rationale_hash(rationale: str) -> bytes:
    """Compute Blake3 hash of rationale text."""
    return blake3.blake3(rationale.encode("utf-8")).digest()


class TestDissentRecordCreation:
    """Tests for DissentRecord creation."""

    def test_create_valid_dissent_record(self) -> None:
        """Should create a valid dissent record with all required fields."""
        dissent_id = uuid7()
        session_id = uuid7()
        petition_id = uuid7()
        archon_id = uuid4()
        rationale = "I believe this petition should be referred to Knight review."
        rationale_hash = _compute_rationale_hash(rationale)

        record = DissentRecord(
            dissent_id=dissent_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition=DeliberationOutcome.REFER,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )

        assert record.dissent_id == dissent_id
        assert record.session_id == session_id
        assert record.petition_id == petition_id
        assert record.dissent_archon_id == archon_id
        assert record.dissent_disposition == DeliberationOutcome.REFER
        assert record.dissent_rationale == rationale
        assert record.rationale_hash == rationale_hash
        assert record.majority_disposition == DeliberationOutcome.ACKNOWLEDGE
        assert record.recorded_at is not None

    def test_dissent_escalate_vs_acknowledge(self) -> None:
        """Should allow ESCALATE dissent against ACKNOWLEDGE majority."""
        rationale = "This needs escalation."
        rationale_hash = _compute_rationale_hash(rationale)

        record = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )

        assert record.dissent_disposition == DeliberationOutcome.ESCALATE
        assert record.majority_disposition == DeliberationOutcome.ACKNOWLEDGE

    def test_dissent_acknowledge_vs_refer(self) -> None:
        """Should allow ACKNOWLEDGE dissent against REFER majority."""
        rationale = "Acknowledgment is sufficient."
        rationale_hash = _compute_rationale_hash(rationale)

        record = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.ACKNOWLEDGE,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.REFER,
        )

        assert record.dissent_disposition == DeliberationOutcome.ACKNOWLEDGE
        assert record.majority_disposition == DeliberationOutcome.REFER


class TestDissentRecordValidation:
    """Tests for DissentRecord validation."""

    def test_invalid_same_dispositions(self) -> None:
        """Should raise ValueError if dissent matches majority."""
        rationale = "Some rationale."
        rationale_hash = _compute_rationale_hash(rationale)

        with pytest.raises(ValueError) as exc_info:
            DissentRecord(
                dissent_id=uuid7(),
                session_id=uuid7(),
                petition_id=uuid7(),
                dissent_archon_id=uuid4(),
                dissent_disposition=DeliberationOutcome.ACKNOWLEDGE,
                dissent_rationale=rationale,
                rationale_hash=rationale_hash,
                majority_disposition=DeliberationOutcome.ACKNOWLEDGE,  # Same!
            )

        assert "cannot match majority disposition" in str(exc_info.value)

    def test_invalid_rationale_hash_too_short(self) -> None:
        """Should raise ValueError if rationale_hash is too short."""
        with pytest.raises(ValueError) as exc_info:
            DissentRecord(
                dissent_id=uuid7(),
                session_id=uuid7(),
                petition_id=uuid7(),
                dissent_archon_id=uuid4(),
                dissent_disposition=DeliberationOutcome.REFER,
                dissent_rationale="Some rationale.",
                rationale_hash=b"too_short",  # Not 32 bytes
                majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
            )

        assert f"must be {BLAKE3_HASH_LENGTH} bytes" in str(exc_info.value)

    def test_invalid_rationale_hash_too_long(self) -> None:
        """Should raise ValueError if rationale_hash is too long."""
        with pytest.raises(ValueError) as exc_info:
            DissentRecord(
                dissent_id=uuid7(),
                session_id=uuid7(),
                petition_id=uuid7(),
                dissent_archon_id=uuid4(),
                dissent_disposition=DeliberationOutcome.REFER,
                dissent_rationale="Some rationale.",
                rationale_hash=b"x" * 64,  # 64 bytes, not 32
                majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
            )

        assert f"must be {BLAKE3_HASH_LENGTH} bytes" in str(exc_info.value)


class TestDissentRecordProperties:
    """Tests for DissentRecord properties."""

    def test_rationale_hash_hex_property(self) -> None:
        """Should return hex-encoded rationale hash."""
        rationale = "Test rationale."
        rationale_hash = _compute_rationale_hash(rationale)

        record = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.REFER,
        )

        assert record.rationale_hash_hex == rationale_hash.hex()
        assert len(record.rationale_hash_hex) == 64  # 32 bytes = 64 hex chars

    def test_verify_rationale_integrity_valid(self) -> None:
        """Should verify rationale integrity correctly."""
        rationale = "Original rationale text."
        rationale_hash = _compute_rationale_hash(rationale)

        record = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.REFER,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )

        assert record.verify_rationale_integrity(rationale) is True

    def test_verify_rationale_integrity_invalid(self) -> None:
        """Should detect tampered rationale."""
        original_rationale = "Original rationale text."
        rationale_hash = _compute_rationale_hash(original_rationale)

        record = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.REFER,
            dissent_rationale=original_rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )

        # Verify with different rationale
        assert record.verify_rationale_integrity("Tampered rationale!") is False


class TestDissentRecordSerialization:
    """Tests for DissentRecord serialization."""

    def test_to_dict_serialization(self) -> None:
        """Should serialize to dictionary correctly."""
        dissent_id = uuid7()
        session_id = uuid7()
        petition_id = uuid7()
        archon_id = uuid4()
        rationale = "Test rationale for serialization."
        rationale_hash = _compute_rationale_hash(rationale)
        recorded_at = _utc_now()

        record = DissentRecord(
            dissent_id=dissent_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.REFER,
            recorded_at=recorded_at,
        )

        result = record.to_dict()

        assert result["dissent_id"] == str(dissent_id)
        assert result["session_id"] == str(session_id)
        assert result["petition_id"] == str(petition_id)
        assert result["dissent_archon_id"] == str(archon_id)
        assert result["dissent_disposition"] == "ESCALATE"
        assert result["dissent_rationale"] == rationale
        assert result["rationale_hash"] == rationale_hash.hex()
        assert result["majority_disposition"] == "REFER"
        assert result["recorded_at"] == recorded_at.isoformat()
        assert result["schema_version"] == 1


class TestDissentRecordImmutability:
    """Tests for DissentRecord immutability."""

    def test_record_is_frozen(self) -> None:
        """Record should be immutable (frozen dataclass)."""
        rationale = "Test rationale."
        rationale_hash = _compute_rationale_hash(rationale)

        record = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.REFER,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )

        with pytest.raises(AttributeError):
            record.dissent_rationale = "Modified!"  # type: ignore[misc]

    def test_record_equality(self) -> None:
        """Records with same values should be equal."""
        dissent_id = uuid7()
        session_id = uuid7()
        petition_id = uuid7()
        archon_id = uuid4()
        rationale = "Same rationale."
        rationale_hash = _compute_rationale_hash(rationale)
        recorded_at = _utc_now()

        record1 = DissentRecord(
            dissent_id=dissent_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
            recorded_at=recorded_at,
        )

        record2 = DissentRecord(
            dissent_id=dissent_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
            recorded_at=recorded_at,
        )

        assert record1 == record2


class TestBlake3HashLengthConstant:
    """Tests for BLAKE3_HASH_LENGTH constant."""

    def test_blake3_hash_length_is_32(self) -> None:
        """BLAKE3_HASH_LENGTH should be 32 bytes."""
        assert BLAKE3_HASH_LENGTH == 32

    def test_blake3_produces_correct_length(self) -> None:
        """Actual Blake3 hash should be 32 bytes."""
        test_hash = _compute_rationale_hash("test")
        assert len(test_hash) == BLAKE3_HASH_LENGTH
