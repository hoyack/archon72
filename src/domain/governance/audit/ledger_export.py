"""Ledger export domain models.

Story: consent-gov-9.1: Ledger Export

Domain models for complete ledger export functionality. These models
enforce constitutional constraints around export completeness and
audit requirements.

Constitutional Requirements:
- FR56: Any participant can export complete ledger
- NFR-CONST-03: Partial export is impossible
- NFR-AUDIT-05: Export format is machine-readable (JSON) and human-auditable
- NFR-INT-02: Ledger contains no PII; publicly readable by design

Export Structure (JSON):
{
    "metadata": {
        "export_id": "uuid",
        "exported_at": "2026-01-16T00:00:00Z",
        "format_version": "1.0.0",
        "total_events": 12345,
        "genesis_hash": "blake3:abc123...",
        "latest_hash": "blake3:xyz789...",
        "sequence_range": [1, 12345]
    },
    "events": [ ... ],
    "verification": {
        "hash_algorithm": "BLAKE3",
        "chain_valid": true,
        "genesis_to_latest": true
    }
}
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.governance.audit.errors import PartialExportError


class LedgerExportEvent(Protocol):
    """Protocol for ledger events used in export validation."""

    sequence: int


# Current export format version
EXPORT_FORMAT_VERSION = "1.0.0"


@dataclass(frozen=True)
class ExportMetadata:
    """Metadata about the ledger export.

    Contains information about when the export was created and
    the range of events included. This enables verification
    that the export is complete.

    Attributes:
        export_id: Unique identifier for this export.
        exported_at: When the export was created (UTC).
        format_version: Version of the export format.
        total_events: Number of events in the export.
        genesis_hash: Hash of the first event (or empty if no events).
        latest_hash: Hash of the last event (or empty if no events).
        sequence_range: Tuple of (first_sequence, last_sequence) or (0, 0) if empty.
    """

    export_id: UUID
    exported_at: datetime
    format_version: str
    total_events: int
    genesis_hash: str
    latest_hash: str
    sequence_range: tuple[int, int]

    def __post_init__(self) -> None:
        """Validate metadata fields."""
        if self.total_events < 0:
            raise ValueError(
                f"total_events must be non-negative, got {self.total_events}"
            )

        start, end = self.sequence_range
        if self.total_events == 0:
            if start != 0 or end != 0:
                raise ValueError(
                    f"sequence_range must be (0, 0) for empty export, got {self.sequence_range}"
                )
        elif start < 1 or end < start:
            raise ValueError(
                f"sequence_range must have start >= 1 and end >= start, got {self.sequence_range}"
            )


@dataclass(frozen=True)
class VerificationInfo:
    """Verification information for the export.

    Contains details needed to verify the integrity of the
    exported ledger, including hash chain validation status.

    Attributes:
        hash_algorithm: Algorithm used for hashing (e.g., "BLAKE3", "SHA256").
        chain_valid: Whether the hash chain validates correctly.
        genesis_to_latest: Whether export includes all events from genesis to latest.
    """

    hash_algorithm: str
    chain_valid: bool
    genesis_to_latest: bool


@dataclass(frozen=True)
class LedgerExport:
    """Complete ledger export.

    Always contains ALL events from genesis to latest.
    No partial exports allowed per NFR-CONST-03.

    This is an immutable snapshot of the complete governance
    ledger at a point in time.

    Attributes:
        metadata: Export metadata (id, timestamp, counts, hashes).
        events: Complete list of all events in sequence order.
        verification: Verification information for integrity checking.
    """

    metadata: ExportMetadata
    events: tuple[LedgerExportEvent, ...]
    verification: VerificationInfo

    def validate_completeness(self) -> bool:
        """Verify export contains complete sequence with no gaps.

        Returns:
            True if the export is complete (no sequence gaps).

        Raises:
            PartialExportError: If sequence is incomplete.
        """
        if not self.events:
            return True  # Empty ledger is complete

        # Check sequence is complete
        expected_seq = 1
        for event in self.events:
            if event.sequence != expected_seq:
                raise PartialExportError(
                    f"Sequence gap detected: expected {expected_seq}, got {event.sequence}"
                )
            expected_seq += 1

        # Check metadata matches
        if len(self.events) != self.metadata.total_events:
            raise PartialExportError(
                f"Event count mismatch: metadata says {self.metadata.total_events}, "
                f"found {len(self.events)}"
            )

        start, end = self.metadata.sequence_range
        if self.events[0].sequence != start:
            raise PartialExportError(
                f"Start sequence mismatch: metadata says {start}, "
                f"first event is {self.events[0].sequence}"
            )
        if self.events[-1].sequence != end:
            raise PartialExportError(
                f"End sequence mismatch: metadata says {end}, "
                f"last event is {self.events[-1].sequence}"
            )

        return True

    @property
    def is_empty(self) -> bool:
        """Check if this is an export of an empty ledger."""
        return len(self.events) == 0

    @property
    def event_count(self) -> int:
        """Number of events in the export."""
        return len(self.events)

    @property
    def first_event(self) -> LedgerExportEvent | None:
        """Get the first (genesis) event, or None if empty."""
        return self.events[0] if self.events else None

    @property
    def last_event(self) -> LedgerExportEvent | None:
        """Get the last (most recent) event, or None if empty."""
        return self.events[-1] if self.events else None
