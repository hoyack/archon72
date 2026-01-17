# Story consent-gov-9.1: Ledger Export

Status: done

---

## Story

As a **participant**,
I want **to export the complete ledger**,
So that **I can independently verify system history**.

---

## Acceptance Criteria

1. **AC1:** Any participant can export complete ledger (FR56)
2. **AC2:** Partial export is impossible (NFR-CONST-03)
3. **AC3:** Export format is JSON (machine-readable) and human-auditable (NFR-AUDIT-05)
4. **AC4:** Ledger contains no PII (NFR-INT-02)
5. **AC5:** Event `audit.ledger.exported` emitted on export
6. **AC6:** Export includes all events from genesis
7. **AC7:** Export preserves hash chain integrity
8. **AC8:** Unit tests for export completeness

---

## Tasks / Subtasks

- [x] **Task 1: Create LedgerExport domain model** (AC: 1, 3)
  - [x] Create `src/domain/governance/audit/ledger_export.py`
  - [x] Include export_id, exported_at
  - [x] Include total_events, hash_range
  - [x] Include format specification

- [x] **Task 2: Create LedgerExportService** (AC: 1, 5)
  - [x] Create `src/application/services/governance/ledger_export_service.py`
  - [x] Export complete ledger
  - [x] Emit `audit.ledger.exported` event
  - [x] No partial export option

- [x] **Task 3: Create LedgerExportPort interface** (AC: 1)
  - [x] Create port for export operations
  - [x] Define `export_complete()` method
  - [x] Define `stream_export()` for large ledgers
  - [x] NO partial export methods

- [x] **Task 4: Implement complete export guarantee** (AC: 2)
  - [x] No offset/limit parameters
  - [x] Export always starts at genesis
  - [x] Export always ends at latest
  - [x] Validate completeness on export

- [x] **Task 5: Implement JSON format** (AC: 3)
  - [x] Machine-readable JSON output
  - [x] Human-auditable structure
  - [x] Include metadata headers
  - [x] Pretty-print option for readability

- [x] **Task 6: Implement PII prevention** (AC: 4)
  - [x] Verify no personal names in events
  - [x] Verify no email addresses
  - [x] Verify no contact information
  - [x] UUIDs only for attribution

- [x] **Task 7: Implement genesis-to-latest export** (AC: 6)
  - [x] Start from event #1 (genesis)
  - [x] Include all events in sequence
  - [x] End at latest event
  - [x] Include hash chain for verification

- [x] **Task 8: Implement hash chain preservation** (AC: 7)
  - [x] Include prev_hash for each event
  - [x] Include event_hash for each event
  - [x] Allow independent verification
  - [x] Final hash for completeness check

- [x] **Task 9: Write comprehensive unit tests** (AC: 8)
  - [x] Test complete export works
  - [x] Test no partial export option
  - [x] Test JSON format valid
  - [x] Test no PII in export
  - [x] Test hash chain preserved

---

## Documentation Checklist

- [x] Architecture docs updated (export format spec) - In-code documentation
- [x] Operations runbook for large exports - Streaming export documented
- [x] Inline comments explaining completeness requirement - Extensive docstrings
- [x] N/A - README (internal component)

---

## File List

### Created Files
- `src/domain/governance/audit/__init__.py` - Module exports with comprehensive docstring
- `src/domain/governance/audit/errors.py` - PartialExportError, PIIDetectedError, ExportValidationError
- `src/domain/governance/audit/ledger_export.py` - ExportMetadata, VerificationInfo, LedgerExport domain models
- `src/application/ports/governance/ledger_export_port.py` - LedgerExportPort, PIICheckerPort protocols
- `src/application/services/governance/ledger_export_service.py` - LedgerExportService with complete export
- `tests/unit/domain/governance/audit/__init__.py` - Test package init
- `tests/unit/domain/governance/audit/test_ledger_export.py` - 17 domain model tests
- `tests/unit/application/services/governance/test_ledger_export_service.py` - 30 service tests

### Modified Files
- `src/application/ports/governance/__init__.py` - Added LedgerExportPort, PIICheckerPort exports
- `src/application/services/governance/__init__.py` - Added LedgerExportService, LEDGER_EXPORTED_EVENT exports

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-17 | Initial implementation - All 9 tasks complete | Claude |
| 2026-01-17 | 47 unit tests passing | Claude |

---

## Dev Notes

### Key Architectural Decisions

**Why Complete Export Only?**
```
NFR-CONST-03: Partial export is impossible

Why no partial export?
  - Partial data enables cherry-picking
  - Verifiers need complete history
  - Trust requires completeness
  - No "just the good parts"

Benefits:
  - Verifier sees everything
  - Cannot hide events
  - Audit is comprehensive
  - No selective disclosure

Implementation:
  - No offset parameter
  - No limit parameter
  - No date range filter
  - Export = ALL events
```

**Why JSON?**
```
NFR-AUDIT-05: Machine-readable and human-auditable

JSON because:
  - Universal format
  - Human readable
  - Machine parseable
  - Tool ecosystem

Structure:
  - metadata: export info
  - events: array of all events
  - verification: hash chain info

Pretty-print option:
  - For human auditing
  - Indented structure
  - Clear field names
```

**No PII Guarantee:**
```
NFR-INT-02: Ledger contains no PII

Events use:
  ✓ UUIDs for participants
  ✓ UUIDs for tasks
  ✓ Timestamps
  ✓ System-generated IDs

Events never contain:
  ✗ Personal names
  ✗ Email addresses
  ✗ Phone numbers
  ✗ Any identifying info

Why?
  - Public ledger by design
  - Anyone can read export
  - No privacy concerns
  - Pseudonymous attribution
```

### Domain Models

```python
@dataclass(frozen=True)
class ExportMetadata:
    """Metadata about the ledger export."""
    export_id: UUID
    exported_at: datetime
    format_version: str
    total_events: int
    genesis_hash: str
    latest_hash: str
    sequence_range: tuple[int, int]


@dataclass(frozen=True)
class LedgerExport:
    """Complete ledger export.

    Always contains ALL events from genesis to latest.
    No partial exports allowed.
    """
    metadata: ExportMetadata
    events: list[EventEnvelope]

    def validate_completeness(self) -> bool:
        """Verify export contains complete sequence."""
        if not self.events:
            return True  # Empty ledger is complete

        # Check sequence is complete
        expected_seq = 1
        for event in self.events:
            if event.sequence_number != expected_seq:
                return False
            expected_seq += 1

        return True


class PartialExportError(ValueError):
    """Raised when partial export is attempted.

    This should never happen - partial export is structurally prevented.
    """
    pass


class PIIDetectedError(ValueError):
    """Raised when PII is detected in export.

    This indicates a bug - PII should never be stored.
    """
    pass
```

### Service Implementation Sketch

```python
class LedgerExportService:
    """Exports complete ledger for independent verification.

    Exports are ALWAYS complete (genesis to latest).
    NO partial export methods exist.
    """

    def __init__(
        self,
        ledger_port: LedgerPort,
        pii_checker: PIIChecker,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._ledger = ledger_port
        self._pii_checker = pii_checker
        self._event_emitter = event_emitter
        self._time = time_authority

    async def export_complete(
        self,
        requester_id: UUID,
        pretty_print: bool = False,
    ) -> LedgerExport:
        """Export complete ledger.

        This ALWAYS exports everything from genesis to latest.
        There are no parameters to limit or filter.

        Args:
            requester_id: Who is requesting the export
            pretty_print: Format for human readability

        Returns:
            LedgerExport containing ALL events
        """
        now = self._time.now()
        export_id = uuid4()

        # Get ALL events (no filtering)
        events = await self._ledger.get_all_events()

        # Verify no PII
        for event in events:
            if self._pii_checker.contains_pii(event):
                raise PIIDetectedError(
                    f"Event {event.event_id} contains PII - this is a bug"
                )

        # Build metadata
        metadata = ExportMetadata(
            export_id=export_id,
            exported_at=now,
            format_version="1.0.0",
            total_events=len(events),
            genesis_hash=events[0].event_hash if events else "",
            latest_hash=events[-1].event_hash if events else "",
            sequence_range=(
                (events[0].sequence_number, events[-1].sequence_number)
                if events else (0, 0)
            ),
        )

        export = LedgerExport(
            metadata=metadata,
            events=events,
        )

        # Validate completeness
        if not export.validate_completeness():
            raise PartialExportError(
                "Export validation failed - sequence incomplete"
            )

        # Emit export event
        await self._event_emitter.emit(
            event_type="audit.ledger.exported",
            actor=str(requester_id),
            payload={
                "export_id": str(export_id),
                "requester_id": str(requester_id),
                "exported_at": now.isoformat(),
                "total_events": len(events),
                "sequence_range": metadata.sequence_range,
            },
        )

        return export

    async def export_to_json(
        self,
        requester_id: UUID,
        pretty_print: bool = True,
    ) -> str:
        """Export ledger as JSON string.

        Args:
            requester_id: Who is requesting
            pretty_print: Indent for readability

        Returns:
            JSON string of complete ledger
        """
        export = await self.export_complete(
            requester_id=requester_id,
            pretty_print=pretty_print,
        )

        if pretty_print:
            return json.dumps(
                asdict(export),
                indent=2,
                default=str,
            )
        else:
            return json.dumps(
                asdict(export),
                default=str,
            )

    # These methods intentionally do not exist:
    # async def export_partial(self, ...): ...
    # async def export_range(self, ...): ...
    # async def export_filtered(self, ...): ...


class LedgerPort(Protocol):
    """Port for ledger operations.

    Export is ALWAYS complete.
    """

    async def get_all_events(self) -> list[EventEnvelope]:
        """Get ALL events from genesis to latest.

        No filtering. No pagination. All events.
        """
        ...

    # Intentionally NOT defined:
    # - get_events_range()
    # - get_events_filtered()
    # - get_events_paginated()
```

### JSON Export Format

```json
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
  "events": [
    {
      "event_id": "uuid",
      "sequence_number": 1,
      "event_type": "constitutional.system.genesis",
      "actor": "system",
      "timestamp": "2026-01-01T00:00:00Z",
      "prev_hash": "0000...",
      "event_hash": "blake3:abc123...",
      "payload": { ... }
    },
    ...
  ],
  "verification": {
    "hash_algorithm": "BLAKE3",
    "chain_valid": true,
    "genesis_to_latest": true
  }
}
```

### Event Pattern

```python
# Ledger exported
{
    "event_type": "audit.ledger.exported",
    "actor": "requester-uuid",
    "payload": {
        "export_id": "uuid",
        "requester_id": "uuid",
        "exported_at": "2026-01-16T00:00:00Z",
        "total_events": 12345,
        "sequence_range": [1, 12345]
    }
}
```

### Test Patterns

```python
class TestLedgerExportService:
    """Unit tests for ledger export service."""

    async def test_export_returns_all_events(
        self,
        export_service: LedgerExportService,
        ledger_with_events: FakeLedgerPort,
        participant: Participant,
    ):
        """Export contains all events."""
        export = await export_service.export_complete(
            requester_id=participant.id,
        )

        expected_count = await ledger_with_events.count_all()
        assert len(export.events) == expected_count

    async def test_export_starts_at_genesis(
        self,
        export_service: LedgerExportService,
        ledger_with_events: FakeLedgerPort,
        participant: Participant,
    ):
        """Export starts at event #1."""
        export = await export_service.export_complete(
            requester_id=participant.id,
        )

        assert export.events[0].sequence_number == 1

    async def test_export_ends_at_latest(
        self,
        export_service: LedgerExportService,
        ledger_with_events: FakeLedgerPort,
        participant: Participant,
    ):
        """Export ends at latest event."""
        export = await export_service.export_complete(
            requester_id=participant.id,
        )

        latest = await ledger_with_events.get_latest_sequence()
        assert export.events[-1].sequence_number == latest

    async def test_export_sequence_is_complete(
        self,
        export_service: LedgerExportService,
        ledger_with_events: FakeLedgerPort,
        participant: Participant,
    ):
        """Export contains complete sequence with no gaps."""
        export = await export_service.export_complete(
            requester_id=participant.id,
        )

        assert export.validate_completeness()

    async def test_export_event_emitted(
        self,
        export_service: LedgerExportService,
        participant: Participant,
        event_capture: EventCapture,
    ):
        """Export event is emitted."""
        await export_service.export_complete(
            requester_id=participant.id,
        )

        event = event_capture.get_last("audit.ledger.exported")
        assert event is not None


class TestNoPartialExport:
    """Tests ensuring no partial export option."""

    def test_no_partial_method(
        self,
        export_service: LedgerExportService,
    ):
        """No partial export method exists."""
        assert not hasattr(export_service, "export_partial")
        assert not hasattr(export_service, "export_range")

    def test_no_filter_method(
        self,
        export_service: LedgerExportService,
    ):
        """No filtered export method exists."""
        assert not hasattr(export_service, "export_filtered")
        assert not hasattr(export_service, "export_by_type")


class TestJSONFormat:
    """Tests for JSON export format."""

    async def test_json_is_valid(
        self,
        export_service: LedgerExportService,
        participant: Participant,
    ):
        """Export produces valid JSON."""
        json_str = await export_service.export_to_json(
            requester_id=participant.id,
        )

        parsed = json.loads(json_str)
        assert "metadata" in parsed
        assert "events" in parsed

    async def test_json_is_human_readable(
        self,
        export_service: LedgerExportService,
        participant: Participant,
    ):
        """Pretty-printed JSON is human readable."""
        json_str = await export_service.export_to_json(
            requester_id=participant.id,
            pretty_print=True,
        )

        # Should have newlines and indentation
        assert "\n" in json_str
        assert "  " in json_str


class TestNoPII:
    """Tests ensuring no PII in export."""

    async def test_no_personal_names(
        self,
        export_service: LedgerExportService,
        participant: Participant,
    ):
        """Export contains no personal names."""
        export = await export_service.export_complete(
            requester_id=participant.id,
        )

        for event in export.events:
            assert not has_personal_name(event.payload)

    async def test_no_email_addresses(
        self,
        export_service: LedgerExportService,
        participant: Participant,
    ):
        """Export contains no email addresses."""
        export = await export_service.export_complete(
            requester_id=participant.id,
        )

        for event in export.events:
            assert not has_email(event.payload)

    async def test_uses_uuids_only(
        self,
        export_service: LedgerExportService,
        participant: Participant,
    ):
        """Export uses UUIDs for attribution."""
        export = await export_service.export_complete(
            requester_id=participant.id,
        )

        for event in export.events:
            # Actor should be UUID
            assert is_valid_uuid(event.actor) or event.actor == "system"
```

### Dependencies

- **Depends on:** consent-gov-1-2 (append-only ledger)
- **Enables:** consent-gov-9-3 (independent verification)

### References

- FR56: Any participant can export complete ledger
- NFR-CONST-03: Partial export is impossible
- NFR-AUDIT-05: Export format is machine-readable (JSON) and human-auditable
- NFR-INT-02: Ledger contains no PII; publicly readable by design
