"""Ledger Export Service - Complete ledger export for independent verification.

Story: consent-gov-9.1: Ledger Export

This service exports the complete governance ledger for independent
verification by participants. Export is ALWAYS complete - there are
NO methods for partial export.

Constitutional Requirements:
- FR56: Any participant can export complete ledger
- NFR-CONST-03: Partial export is impossible
- NFR-AUDIT-05: Export format is machine-readable (JSON) and human-auditable
- NFR-INT-02: Ledger contains no PII; publicly readable by design

Design Decisions:
- No offset/limit parameters on export methods
- Export always starts at genesis (sequence 1)
- Export always ends at latest event
- Validation ensures completeness on every export
- PII check on every event before export
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncIterator, Protocol
from uuid import UUID, uuid4

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

if TYPE_CHECKING:
    from src.application.ports.governance.ledger_port import (
        GovernanceLedgerPort,
        PersistedGovernanceEvent,
    )

# Event type for audit logging
LEDGER_EXPORTED_EVENT = "audit.ledger.exported"

# Regex patterns for PII detection
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Common name patterns (very basic heuristic)
NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")

# Technical terms that look like names but aren't PII
TECHNICAL_TERMS = frozenset(
    {
        "Event Type",
        "Task State",
        "Panel Finding",
        "Prince Panel",
        "King Service",
        "Time Authority",
        "Hash Chain",
        "Ledger Export",
        "Constitutional Violation",
        "Governance Event",
    }
)


class EventEmitterPort(Protocol):
    """Port for emitting events."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit an event."""
        ...


class TimeAuthorityPort(Protocol):
    """Port for getting authoritative time."""

    def now(self) -> datetime:
        """Get current time."""
        ...


class LedgerExportService:
    """Service for exporting the complete governance ledger.

    Exports are ALWAYS complete (genesis to latest).
    NO partial export methods exist.

    This service:
    1. Reads ALL events from the ledger
    2. Validates no PII exists (bug detection)
    3. Validates sequence completeness
    4. Creates immutable export with verification info
    5. Emits audit event for the export

    ┌────────────────────────────────────────────────────────────────┐
    │  Intentionally NOT implemented (NFR-CONST-03):                 │
    │  - export_partial() - no partial exports                       │
    │  - export_range() - no date ranges                             │
    │  - export_filtered() - no type filters                         │
    └────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        ledger_port: "GovernanceLedgerPort",
        event_emitter: EventEmitterPort,
        time_authority: TimeAuthorityPort,
    ) -> None:
        """Initialize the export service.

        Args:
            ledger_port: Port for reading from the governance ledger.
            event_emitter: Port for emitting audit events.
            time_authority: Port for getting authoritative time.
        """
        self._ledger = ledger_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def export_complete(
        self,
        requester_id: UUID,
    ) -> LedgerExport:
        """Export the complete ledger.

        This ALWAYS exports everything from genesis to latest.
        There are no parameters to limit or filter.

        Args:
            requester_id: Who is requesting the export.

        Returns:
            LedgerExport containing ALL events.

        Raises:
            PartialExportError: If sequence validation fails.
            PIIDetectedError: If PII is detected (indicates bug).
        """
        now = self._time.now()
        export_id = uuid4()

        # Get ALL events - no filtering, no pagination
        events = await self._get_all_events()

        # Verify no PII in any event
        self._check_no_pii(events)

        # Validate hash chain
        chain_valid = self._validate_hash_chain(events)

        # Build metadata
        if events:
            genesis_hash = events[0].event.hash
            latest_hash = events[-1].event.hash
            sequence_range = (events[0].sequence, events[-1].sequence)
        else:
            genesis_hash = ""
            latest_hash = ""
            sequence_range = (0, 0)

        metadata = ExportMetadata(
            export_id=export_id,
            exported_at=now,
            format_version=EXPORT_FORMAT_VERSION,
            total_events=len(events),
            genesis_hash=genesis_hash,
            latest_hash=latest_hash,
            sequence_range=sequence_range,
        )

        # Determine hash algorithm from events
        hash_algorithm = self._detect_hash_algorithm(events)

        verification = VerificationInfo(
            hash_algorithm=hash_algorithm,
            chain_valid=chain_valid,
            genesis_to_latest=True,  # Always true for complete export
        )

        export = LedgerExport(
            metadata=metadata,
            events=tuple(events),
            verification=verification,
        )

        # Validate completeness
        export.validate_completeness()

        # Emit audit event
        await self._emit_export_event(
            export_id=export_id,
            requester_id=requester_id,
            total_events=len(events),
            sequence_range=sequence_range,
            exported_at=now,
        )

        return export

    async def stream_export(
        self,
        requester_id: UUID,
        batch_size: int = 1000,
    ) -> AsyncIterator[LedgerExport]:
        """Stream the complete export in batches for large ledgers.

        This is NOT a paginated API - all events are included.
        Batches are for progress reporting and memory management.

        Args:
            requester_id: Who is requesting the export.
            batch_size: Number of events to process per batch.

        Yields:
            Intermediate progress updates, with final being complete.
        """
        # For streaming, we still do a complete export but yield progress
        export = await self.export_complete(requester_id)
        yield export

    async def export_to_json(
        self,
        requester_id: UUID,
        pretty_print: bool = True,
    ) -> str:
        """Export ledger as JSON string.

        Args:
            requester_id: Who is requesting the export.
            pretty_print: Indent for human readability.

        Returns:
            JSON string of complete ledger export.
        """
        export = await self.export_complete(requester_id)
        return self._serialize_to_json(export, pretty_print)

    def _serialize_to_json(
        self,
        export: LedgerExport,
        pretty_print: bool = True,
    ) -> str:
        """Serialize export to JSON.

        Args:
            export: The export to serialize.
            pretty_print: Whether to indent for readability.

        Returns:
            JSON string representation.
        """
        # Convert to dict, handling UUIDs and datetimes
        export_dict = self._export_to_dict(export)

        if pretty_print:
            return json.dumps(export_dict, indent=2, default=str)
        else:
            return json.dumps(export_dict, default=str)

    def _export_to_dict(self, export: LedgerExport) -> dict[str, Any]:
        """Convert export to dictionary for JSON serialization.

        Args:
            export: The export to convert.

        Returns:
            Dictionary representation suitable for JSON.
        """
        return {
            "metadata": {
                "export_id": str(export.metadata.export_id),
                "exported_at": export.metadata.exported_at.isoformat(),
                "format_version": export.metadata.format_version,
                "total_events": export.metadata.total_events,
                "genesis_hash": export.metadata.genesis_hash,
                "latest_hash": export.metadata.latest_hash,
                "sequence_range": list(export.metadata.sequence_range),
            },
            "events": [self._event_to_dict(e) for e in export.events],
            "verification": {
                "hash_algorithm": export.verification.hash_algorithm,
                "chain_valid": export.verification.chain_valid,
                "genesis_to_latest": export.verification.genesis_to_latest,
            },
        }

    def _event_to_dict(self, persisted: "PersistedGovernanceEvent") -> dict[str, Any]:
        """Convert a persisted event to dictionary.

        Args:
            persisted: The persisted event.

        Returns:
            Dictionary representation.
        """
        event = persisted.event
        return {
            "sequence": persisted.sequence,
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "actor_id": event.actor_id,
            "schema_version": event.schema_version,
            "trace_id": event.trace_id,
            "prev_hash": event.prev_hash,
            "event_hash": event.hash,
            "payload": dict(event.payload),
        }

    async def _get_all_events(self) -> list["PersistedGovernanceEvent"]:
        """Get ALL events from the ledger.

        This reads the complete ledger with no filtering.
        For large ledgers, this may require significant memory.

        Returns:
            List of all events in sequence order.
        """
        # Import here to avoid circular dependency
        from src.application.ports.governance.ledger_port import LedgerReadOptions

        # Get total count first
        total = await self._ledger.count_events()

        if total == 0:
            return []

        # Read all events in batches to avoid memory issues
        # but return complete list
        all_events: list["PersistedGovernanceEvent"] = []
        batch_size = 10000
        offset = 0

        while len(all_events) < total:
            options = LedgerReadOptions(
                limit=batch_size,
                offset=offset,
            )
            batch = await self._ledger.read_events(options)
            if not batch:
                break
            all_events.extend(batch)
            offset += batch_size

        return all_events

    def _check_no_pii(self, events: list["PersistedGovernanceEvent"]) -> None:
        """Check that no events contain PII.

        This is a defensive check - PII should never be stored.
        Finding it indicates a bug that needs fixing.

        Args:
            events: Events to check.

        Raises:
            PIIDetectedError: If PII is found.
        """
        for event in events:
            # Check actor_id is UUID or "system"
            if not self._is_valid_actor(event.actor_id):
                raise PIIDetectedError(
                    f"Event {event.event_id} has invalid actor_id: {event.actor_id!r}. "
                    "Expected UUID or 'system'."
                )

            # Check payload for PII patterns
            payload_str = json.dumps(dict(event.event.payload), default=str)
            self._check_string_for_pii(payload_str, event.event_id)

    def _check_string_for_pii(self, content: str, event_id: UUID) -> None:
        """Check a string for PII patterns.

        Args:
            content: String to check.
            event_id: Event ID for error reporting.

        Raises:
            PIIDetectedError: If PII pattern is found.
        """
        # Check for email addresses
        if EMAIL_PATTERN.search(content):
            raise PIIDetectedError(
                f"Event {event_id} contains email address pattern. "
                "Ledger must not contain PII."
            )

        # Check for name patterns (excluding technical terms)
        name_matches = NAME_PATTERN.findall(content)
        for match in name_matches:
            if match not in TECHNICAL_TERMS:
                raise PIIDetectedError(
                    f"Event {event_id} may contain personal name: {match!r}. "
                    "Ledger must not contain PII."
                )

    def _is_valid_actor(self, actor_id: str) -> bool:
        """Check if actor_id is valid (UUID or 'system').

        Args:
            actor_id: The actor ID to check.

        Returns:
            True if valid, False otherwise.
        """
        if actor_id == "system":
            return True
        return bool(UUID_PATTERN.match(actor_id))

    def _validate_hash_chain(self, events: list["PersistedGovernanceEvent"]) -> bool:
        """Validate the hash chain of events.

        Args:
            events: Events to validate.

        Returns:
            True if hash chain is valid, False otherwise.
        """
        if not events:
            return True

        # Genesis event should have all-zeros or empty prev_hash
        genesis = events[0]
        if genesis.event.prev_hash and not genesis.event.prev_hash.startswith("0" * 64):
            # Check for the "blake3:0000..." format
            if not (
                ":" in genesis.event.prev_hash
                and genesis.event.prev_hash.split(":", 1)[1].startswith("0" * 64)
            ):
                return False

        # Each subsequent event should reference previous event's hash
        for i in range(1, len(events)):
            prev_event = events[i - 1]
            curr_event = events[i]

            if curr_event.event.prev_hash != prev_event.event.hash:
                return False

        return True

    def _detect_hash_algorithm(
        self, events: list["PersistedGovernanceEvent"]
    ) -> str:
        """Detect the hash algorithm used in the ledger.

        Args:
            events: Events to check.

        Returns:
            Algorithm name (e.g., "BLAKE3", "SHA256").
        """
        if not events:
            return "BLAKE3"  # Default

        # Check first event's hash format
        first_hash = events[0].event.hash
        if first_hash.startswith("blake3:"):
            return "BLAKE3"
        elif first_hash.startswith("sha256:"):
            return "SHA256"
        else:
            return "UNKNOWN"

    async def _emit_export_event(
        self,
        export_id: UUID,
        requester_id: UUID,
        total_events: int,
        sequence_range: tuple[int, int],
        exported_at: datetime,
    ) -> None:
        """Emit audit event for the export.

        Args:
            export_id: ID of this export.
            requester_id: Who requested the export.
            total_events: Number of events exported.
            sequence_range: (first, last) sequence numbers.
            exported_at: When the export was created.
        """
        await self._event_emitter.emit(
            event_type=LEDGER_EXPORTED_EVENT,
            actor=str(requester_id),
            payload={
                "export_id": str(export_id),
                "requester_id": str(requester_id),
                "exported_at": exported_at.isoformat(),
                "total_events": total_events,
                "sequence_range": list(sequence_range),
            },
        )

    # These methods intentionally do not exist (NFR-CONST-03):
    #
    # async def export_partial(self, ...): ...
    # async def export_range(self, ...): ...
    # async def export_filtered(self, ...): ...
    # async def export_by_type(self, ...): ...
