"""Unit tests for ledger export domain models.

Story: consent-gov-9.1: Ledger Export

Tests:
- ExportMetadata validation
- LedgerExport completeness validation
- VerificationInfo structure
- Error conditions
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.governance.audit.errors import (
    ExportValidationError,
    PartialExportError,
    PIIDetectedError,
)
from src.domain.governance.audit.ledger_export import (
    EXPORT_FORMAT_VERSION,
    ExportMetadata,
    LedgerExport,
    VerificationInfo,
)


@dataclass(frozen=True)
class FakeEvent:
    """Fake event for testing."""

    event_id: UUID
    sequence: int
    event_type: str = "test.event"
    timestamp: datetime = datetime.now(timezone.utc)
    actor_id: str = "test-actor"
    prev_hash: str = ""
    hash: str = ""


@dataclass(frozen=True)
class FakePersistedEvent:
    """Fake persisted event for testing."""

    event: FakeEvent
    sequence: int

    @property
    def event_id(self) -> UUID:
        return self.event.event_id


def create_fake_event(sequence: int) -> FakePersistedEvent:
    """Create a fake persisted event for testing."""
    event = FakeEvent(
        event_id=uuid4(),
        sequence=sequence,
        hash=f"blake3:{'a' * 64}",
        prev_hash=f"blake3:{'0' * 64}" if sequence == 1 else f"blake3:{'a' * 64}",
    )
    return FakePersistedEvent(event=event, sequence=sequence)


class TestExportMetadata:
    """Tests for ExportMetadata domain model."""

    def test_valid_metadata_creation(self) -> None:
        """ExportMetadata can be created with valid fields."""
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=100,
            genesis_hash="blake3:abc123",
            latest_hash="blake3:xyz789",
            sequence_range=(1, 100),
        )

        assert metadata.total_events == 100
        assert metadata.sequence_range == (1, 100)

    def test_empty_ledger_metadata(self) -> None:
        """ExportMetadata accepts empty ledger values."""
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=0,
            genesis_hash="",
            latest_hash="",
            sequence_range=(0, 0),
        )

        assert metadata.total_events == 0
        assert metadata.sequence_range == (0, 0)

    def test_negative_total_events_rejected(self) -> None:
        """ExportMetadata rejects negative total_events."""
        with pytest.raises(ValueError, match="non-negative"):
            ExportMetadata(
                export_id=uuid4(),
                exported_at=datetime.now(timezone.utc),
                format_version=EXPORT_FORMAT_VERSION,
                total_events=-1,
                genesis_hash="",
                latest_hash="",
                sequence_range=(0, 0),
            )

    def test_invalid_sequence_range_rejected(self) -> None:
        """ExportMetadata rejects invalid sequence ranges."""
        # Empty export must have (0, 0) range
        with pytest.raises(ValueError, match="sequence_range"):
            ExportMetadata(
                export_id=uuid4(),
                exported_at=datetime.now(timezone.utc),
                format_version=EXPORT_FORMAT_VERSION,
                total_events=0,
                genesis_hash="",
                latest_hash="",
                sequence_range=(1, 10),  # Invalid for empty
            )

    def test_sequence_range_end_before_start_rejected(self) -> None:
        """ExportMetadata rejects end < start."""
        with pytest.raises(ValueError, match="sequence_range"):
            ExportMetadata(
                export_id=uuid4(),
                exported_at=datetime.now(timezone.utc),
                format_version=EXPORT_FORMAT_VERSION,
                total_events=10,
                genesis_hash="abc",
                latest_hash="xyz",
                sequence_range=(10, 5),  # Invalid: end < start
            )

    def test_sequence_range_start_less_than_one_rejected(self) -> None:
        """ExportMetadata rejects start < 1 for non-empty export."""
        with pytest.raises(ValueError, match="sequence_range"):
            ExportMetadata(
                export_id=uuid4(),
                exported_at=datetime.now(timezone.utc),
                format_version=EXPORT_FORMAT_VERSION,
                total_events=10,
                genesis_hash="abc",
                latest_hash="xyz",
                sequence_range=(0, 10),  # Invalid: start must be >= 1
            )


class TestVerificationInfo:
    """Tests for VerificationInfo domain model."""

    def test_verification_info_creation(self) -> None:
        """VerificationInfo can be created."""
        info = VerificationInfo(
            hash_algorithm="BLAKE3",
            chain_valid=True,
            genesis_to_latest=True,
        )

        assert info.hash_algorithm == "BLAKE3"
        assert info.chain_valid is True
        assert info.genesis_to_latest is True

    def test_verification_info_invalid_chain(self) -> None:
        """VerificationInfo can represent invalid chain."""
        info = VerificationInfo(
            hash_algorithm="SHA256",
            chain_valid=False,
            genesis_to_latest=True,
        )

        assert info.chain_valid is False


class TestLedgerExport:
    """Tests for LedgerExport domain model."""

    def test_empty_export_is_complete(self) -> None:
        """Empty export validates as complete."""
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=0,
            genesis_hash="",
            latest_hash="",
            sequence_range=(0, 0),
        )
        verification = VerificationInfo(
            hash_algorithm="BLAKE3",
            chain_valid=True,
            genesis_to_latest=True,
        )
        export = LedgerExport(
            metadata=metadata,
            events=tuple(),
            verification=verification,
        )

        assert export.validate_completeness() is True
        assert export.is_empty is True
        assert export.event_count == 0
        assert export.first_event is None
        assert export.last_event is None

    def test_valid_export_with_events(self) -> None:
        """Export with complete event sequence validates."""
        events = tuple(create_fake_event(i) for i in range(1, 6))
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=5,
            genesis_hash="blake3:abc",
            latest_hash="blake3:xyz",
            sequence_range=(1, 5),
        )
        verification = VerificationInfo(
            hash_algorithm="BLAKE3",
            chain_valid=True,
            genesis_to_latest=True,
        )
        export = LedgerExport(
            metadata=metadata,
            events=events,
            verification=verification,
        )

        assert export.validate_completeness() is True
        assert export.is_empty is False
        assert export.event_count == 5
        assert export.first_event is not None
        assert export.last_event is not None
        assert export.first_event.sequence == 1
        assert export.last_event.sequence == 5

    def test_sequence_gap_detected(self) -> None:
        """Export with sequence gap raises PartialExportError."""
        # Create events with a gap (missing sequence 3)
        events = [
            create_fake_event(1),
            create_fake_event(2),
            create_fake_event(4),  # Gap: missing 3
            create_fake_event(5),
        ]
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=4,
            genesis_hash="abc",
            latest_hash="xyz",
            sequence_range=(1, 5),
        )
        verification = VerificationInfo(
            hash_algorithm="BLAKE3",
            chain_valid=True,
            genesis_to_latest=True,
        )
        export = LedgerExport(
            metadata=metadata,
            events=tuple(events),
            verification=verification,
        )

        with pytest.raises(PartialExportError, match="Sequence gap"):
            export.validate_completeness()

    def test_event_count_mismatch_detected(self) -> None:
        """Export with count mismatch raises PartialExportError."""
        events = tuple(create_fake_event(i) for i in range(1, 4))  # 3 events
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=5,  # Says 5 but only 3 events
            genesis_hash="abc",
            latest_hash="xyz",
            sequence_range=(1, 3),
        )
        verification = VerificationInfo(
            hash_algorithm="BLAKE3",
            chain_valid=True,
            genesis_to_latest=True,
        )
        export = LedgerExport(
            metadata=metadata,
            events=events,
            verification=verification,
        )

        with pytest.raises(PartialExportError, match="Event count mismatch"):
            export.validate_completeness()

    def test_start_sequence_mismatch_detected(self) -> None:
        """Export with start sequence mismatch raises PartialExportError."""
        events = tuple(create_fake_event(i) for i in range(2, 5))  # Start at 2
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=3,
            genesis_hash="abc",
            latest_hash="xyz",
            sequence_range=(1, 4),  # Says start at 1
        )
        verification = VerificationInfo(
            hash_algorithm="BLAKE3",
            chain_valid=True,
            genesis_to_latest=True,
        )
        export = LedgerExport(
            metadata=metadata,
            events=events,
            verification=verification,
        )

        with pytest.raises(PartialExportError, match="Sequence gap"):
            export.validate_completeness()

    def test_end_sequence_mismatch_detected(self) -> None:
        """Export with end sequence mismatch raises PartialExportError."""
        events = tuple(create_fake_event(i) for i in range(1, 4))  # End at 3
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            format_version=EXPORT_FORMAT_VERSION,
            total_events=3,
            genesis_hash="abc",
            latest_hash="xyz",
            sequence_range=(1, 5),  # Says end at 5
        )
        verification = VerificationInfo(
            hash_algorithm="BLAKE3",
            chain_valid=True,
            genesis_to_latest=True,
        )
        export = LedgerExport(
            metadata=metadata,
            events=events,
            verification=verification,
        )

        with pytest.raises(PartialExportError, match="End sequence mismatch"):
            export.validate_completeness()


class TestErrors:
    """Tests for audit error types."""

    def test_partial_export_error(self) -> None:
        """PartialExportError can be raised with message."""
        with pytest.raises(PartialExportError, match="test message"):
            raise PartialExportError("test message")

    def test_pii_detected_error(self) -> None:
        """PIIDetectedError can be raised with message."""
        with pytest.raises(PIIDetectedError, match="email found"):
            raise PIIDetectedError("email found")

    def test_export_validation_error(self) -> None:
        """ExportValidationError can be raised with message."""
        with pytest.raises(ExportValidationError, match="validation failed"):
            raise ExportValidationError("validation failed")
