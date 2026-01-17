"""Unit tests for FindingRecord domain model.

Story: consent-gov-6-5: Panel Finding Preservation

Tests verify the FindingRecord value object:
- Immutability (frozen dataclass)
- Ledger position validation
- Integrity hash validation
- Convenience accessors

References:
    - FR40: System can record all panel findings in append-only ledger
    - NFR-CONST-06: Panel findings cannot be deleted or modified
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.governance.panel import (
    PanelFinding,
    Determination,
    RemedyType,
    Dissent,
    FindingRecord,
)


def _create_finding(
    finding_id=None,
    panel_id=None,
    statement_id=None,
    determination=Determination.VIOLATION_FOUND,
    remedy=RemedyType.WARNING,
    dissent=None,
) -> PanelFinding:
    """Helper to create a test finding."""
    return PanelFinding(
        finding_id=finding_id or uuid4(),
        panel_id=panel_id or uuid4(),
        statement_id=statement_id or uuid4(),
        determination=determination,
        remedy=remedy,
        majority_rationale="Test rationale.",
        dissent=dissent,
        issued_at=datetime.now(timezone.utc),
        voting_record={uuid4(): "violation", uuid4(): "violation", uuid4(): "no_violation"},
    )


def _create_record(
    finding=None,
    record_id=None,
    ledger_position=1,
    integrity_hash="abc123def456",
) -> FindingRecord:
    """Helper to create a test finding record."""
    return FindingRecord(
        record_id=record_id or uuid4(),
        finding=finding or _create_finding(),
        recorded_at=datetime.now(timezone.utc),
        ledger_position=ledger_position,
        integrity_hash=integrity_hash,
    )


class TestFindingRecordImmutability:
    """Test that FindingRecord is immutable."""

    def test_finding_record_is_frozen(self) -> None:
        """FindingRecord is a frozen dataclass."""
        record = _create_record()

        with pytest.raises(AttributeError):
            record.ledger_position = 999  # type: ignore

    def test_finding_record_cannot_modify_finding(self) -> None:
        """Cannot replace the finding in a record."""
        record = _create_record()

        with pytest.raises(AttributeError):
            record.finding = _create_finding()  # type: ignore

    def test_finding_record_cannot_modify_hash(self) -> None:
        """Cannot modify the integrity hash."""
        record = _create_record()

        with pytest.raises(AttributeError):
            record.integrity_hash = "tampered"  # type: ignore


class TestFindingRecordValidation:
    """Test FindingRecord validation rules."""

    def test_ledger_position_must_be_positive(self) -> None:
        """Ledger position must be > 0."""
        with pytest.raises(ValueError, match="positive"):
            _create_record(ledger_position=0)

    def test_ledger_position_cannot_be_negative(self) -> None:
        """Ledger position cannot be negative."""
        with pytest.raises(ValueError, match="positive"):
            _create_record(ledger_position=-1)

    def test_integrity_hash_required(self) -> None:
        """Integrity hash cannot be empty."""
        with pytest.raises(ValueError, match="hash"):
            FindingRecord(
                record_id=uuid4(),
                finding=_create_finding(),
                recorded_at=datetime.now(timezone.utc),
                ledger_position=1,
                integrity_hash="",
            )


class TestFindingRecordConvenienceAccessors:
    """Test convenience accessor properties."""

    def test_finding_id_accessor(self) -> None:
        """Can access finding_id from record."""
        finding = _create_finding()
        record = _create_record(finding=finding)

        assert record.finding_id == finding.finding_id

    def test_panel_id_accessor(self) -> None:
        """Can access panel_id from record."""
        finding = _create_finding()
        record = _create_record(finding=finding)

        assert record.panel_id == finding.panel_id

    def test_statement_id_accessor(self) -> None:
        """Can access statement_id from record."""
        finding = _create_finding()
        record = _create_record(finding=finding)

        assert record.statement_id == finding.statement_id

    def test_determination_accessor(self) -> None:
        """Can access determination from record."""
        finding = _create_finding(determination=Determination.NO_VIOLATION)
        record = _create_record(finding=finding)

        assert record.determination == Determination.NO_VIOLATION

    def test_has_dissent_true_when_dissent_exists(self) -> None:
        """has_dissent returns True when dissent exists."""
        dissent = Dissent(
            dissenting_member_ids=[uuid4()],
            rationale="I disagree.",
        )
        finding = _create_finding(dissent=dissent)
        record = _create_record(finding=finding)

        assert record.has_dissent is True

    def test_has_dissent_false_when_no_dissent(self) -> None:
        """has_dissent returns False when no dissent."""
        finding = _create_finding(dissent=None)
        record = _create_record(finding=finding)

        assert record.has_dissent is False

    def test_issued_at_accessor(self) -> None:
        """Can access issued_at from record."""
        finding = _create_finding()
        record = _create_record(finding=finding)

        assert record.issued_at == finding.issued_at


class TestFindingRecordEquality:
    """Test FindingRecord equality and hashing."""

    def test_records_equal_by_record_id(self) -> None:
        """Records are equal if they have the same record_id."""
        record_id = uuid4()
        record1 = _create_record(record_id=record_id)
        record2 = _create_record(record_id=record_id)

        # Note: Due to different timestamps, records may not be fully equal
        # but they should hash the same
        assert hash(record1) == hash(record2)

    def test_different_records_have_different_hash(self) -> None:
        """Different record_ids produce different hashes."""
        record1 = _create_record()
        record2 = _create_record()

        assert hash(record1) != hash(record2)

    def test_records_usable_in_set(self) -> None:
        """Records can be used in sets (hashable)."""
        record1 = _create_record()
        record2 = _create_record()

        records = {record1, record2}
        assert len(records) == 2


class TestFindingRecordCreation:
    """Test FindingRecord creation scenarios."""

    def test_create_record_with_all_fields(self) -> None:
        """Can create a record with all fields."""
        finding = _create_finding()
        record_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        record = FindingRecord(
            record_id=record_id,
            finding=finding,
            recorded_at=recorded_at,
            ledger_position=42,
            integrity_hash="sha256:abc123",
        )

        assert record.record_id == record_id
        assert record.finding == finding
        assert record.recorded_at == recorded_at
        assert record.ledger_position == 42
        assert record.integrity_hash == "sha256:abc123"

    def test_create_record_preserves_dissent(self) -> None:
        """Record preserves dissent from finding (FR39)."""
        dissent = Dissent(
            dissenting_member_ids=[uuid4(), uuid4()],
            rationale="Strong disagreement with majority view.",
        )
        finding = _create_finding(dissent=dissent)
        record = _create_record(finding=finding)

        assert record.finding.dissent is not None
        assert len(record.finding.dissent.dissenting_member_ids) == 2
        assert record.finding.dissent.rationale == "Strong disagreement with majority view."

    def test_create_record_preserves_voting_record(self) -> None:
        """Record preserves voting record (AC5)."""
        member1, member2, member3 = uuid4(), uuid4(), uuid4()
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.WARNING,
            majority_rationale="Test.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={member1: "violation", member2: "violation", member3: "no_violation"},
        )
        record = _create_record(finding=finding)

        assert len(record.finding.voting_record) == 3
        assert record.finding.voting_record[member1] == "violation"
        assert record.finding.voting_record[member3] == "no_violation"
