"""Unit tests for ledger export service.

Story: consent-gov-9.1: Ledger Export

Tests:
- Complete export functionality
- No partial export methods exist
- PII detection and rejection
- JSON serialization
- Hash chain validation
- Event emission
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.ledger_export_service import (
    EMAIL_PATTERN,
    LEDGER_EXPORTED_EVENT,
    LedgerExportService,
    NAME_PATTERN,
    TECHNICAL_TERMS,
    UUID_PATTERN,
)
from src.domain.governance.audit.errors import PartialExportError, PIIDetectedError
from src.domain.governance.audit.ledger_export import EXPORT_FORMAT_VERSION


@dataclass(frozen=True)
class FakeEventMetadata:
    """Fake event metadata for testing."""

    event_id: UUID
    event_type: str
    timestamp: datetime
    actor_id: str
    schema_version: str
    trace_id: str
    prev_hash: str
    hash: str


@dataclass(frozen=True)
class FakeGovernanceEvent:
    """Fake governance event for testing."""

    metadata: FakeEventMetadata
    payload: MappingProxyType[str, Any]

    @property
    def event_id(self) -> UUID:
        return self.metadata.event_id

    @property
    def event_type(self) -> str:
        return self.metadata.event_type

    @property
    def timestamp(self) -> datetime:
        return self.metadata.timestamp

    @property
    def actor_id(self) -> str:
        return self.metadata.actor_id

    @property
    def schema_version(self) -> str:
        return self.metadata.schema_version

    @property
    def trace_id(self) -> str:
        return self.metadata.trace_id

    @property
    def prev_hash(self) -> str:
        return self.metadata.prev_hash

    @property
    def hash(self) -> str:
        return self.metadata.hash


@dataclass(frozen=True)
class FakePersistedGovernanceEvent:
    """Fake persisted event for testing."""

    event: FakeGovernanceEvent
    sequence: int

    @property
    def event_id(self) -> UUID:
        return self.event.event_id

    @property
    def event_type(self) -> str:
        return self.event.event_type

    @property
    def branch(self) -> str:
        return self.event.event_type.split(".")[0]

    @property
    def timestamp(self) -> datetime:
        return self.event.timestamp

    @property
    def actor_id(self) -> str:
        return self.event.actor_id


def create_fake_event(
    sequence: int,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
    prev_hash: str | None = None,
) -> FakePersistedGovernanceEvent:
    """Create a fake persisted event for testing."""
    event_id = uuid4()
    if prev_hash is None:
        prev_hash = f"blake3:{'0' * 64}" if sequence == 1 else f"blake3:{'a' * 64}"

    metadata = FakeEventMetadata(
        event_id=event_id,
        event_type="test.event.created",
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id or str(uuid4()),
        schema_version="1.0.0",
        trace_id=str(uuid4()),
        prev_hash=prev_hash,
        hash=f"blake3:{'b' * 64}",
    )
    event = FakeGovernanceEvent(
        metadata=metadata,
        payload=MappingProxyType(payload or {}),
    )
    return FakePersistedGovernanceEvent(event=event, sequence=sequence)


class FakeLedgerPort:
    """Fake ledger port for testing."""

    def __init__(self, events: list[FakePersistedGovernanceEvent] | None = None) -> None:
        self.events = events or []

    async def count_events(self, options=None) -> int:
        return len(self.events)

    async def read_events(self, options=None) -> list[FakePersistedGovernanceEvent]:
        if options is None:
            return self.events
        offset = getattr(options, "offset", 0)
        limit = getattr(options, "limit", 100)
        return self.events[offset : offset + limit]


class FakeEventEmitter:
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self.emitted: list[dict[str, Any]] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        self.emitted.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._time


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Provide a fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Provide a fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def empty_ledger() -> FakeLedgerPort:
    """Provide an empty ledger."""
    return FakeLedgerPort([])


@pytest.fixture
def ledger_with_events() -> FakeLedgerPort:
    """Provide a ledger with some events."""
    events = [create_fake_event(i) for i in range(1, 11)]
    return FakeLedgerPort(events)


@pytest.fixture
def export_service(
    empty_ledger: FakeLedgerPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> LedgerExportService:
    """Provide an export service with empty ledger."""
    return LedgerExportService(
        ledger_port=empty_ledger,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


class TestLedgerExportService:
    """Tests for LedgerExportService."""

    async def test_export_empty_ledger(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """Exporting an empty ledger returns empty export."""
        requester_id = uuid4()
        export = await export_service.export_complete(requester_id)

        assert export.is_empty
        assert export.event_count == 0
        assert export.metadata.total_events == 0
        assert export.metadata.sequence_range == (0, 0)

    async def test_export_returns_all_events(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Export contains all events from ledger."""
        service = LedgerExportService(
            ledger_port=ledger_with_events,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        export = await service.export_complete(requester_id)

        assert export.event_count == 10
        assert export.metadata.total_events == 10
        assert export.metadata.sequence_range == (1, 10)

    async def test_export_starts_at_genesis(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Export starts at event #1."""
        service = LedgerExportService(
            ledger_port=ledger_with_events,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        export = await service.export_complete(requester_id)

        assert export.first_event is not None
        assert export.first_event.sequence == 1

    async def test_export_ends_at_latest(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Export ends at the latest event."""
        service = LedgerExportService(
            ledger_port=ledger_with_events,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        export = await service.export_complete(requester_id)

        assert export.last_event is not None
        assert export.last_event.sequence == 10

    async def test_export_emits_audit_event(
        self,
        export_service: LedgerExportService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Export emits audit event."""
        requester_id = uuid4()

        await export_service.export_complete(requester_id)

        assert len(event_emitter.emitted) == 1
        event = event_emitter.emitted[0]
        assert event["event_type"] == LEDGER_EXPORTED_EVENT
        assert event["actor"] == str(requester_id)
        assert "export_id" in event["payload"]
        assert "total_events" in event["payload"]


class TestNoPartialExport:
    """Tests ensuring no partial export methods exist."""

    def test_no_export_partial_method(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """No partial export method exists."""
        assert not hasattr(export_service, "export_partial")

    def test_no_export_range_method(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """No range export method exists."""
        assert not hasattr(export_service, "export_range")

    def test_no_export_filtered_method(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """No filtered export method exists."""
        assert not hasattr(export_service, "export_filtered")

    def test_no_export_by_type_method(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """No export by type method exists."""
        assert not hasattr(export_service, "export_by_type")


class TestJSONExport:
    """Tests for JSON export functionality."""

    async def test_export_to_json_is_valid(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """JSON export produces valid JSON."""
        service = LedgerExportService(
            ledger_port=ledger_with_events,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        json_str = await service.export_to_json(requester_id)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "metadata" in parsed
        assert "events" in parsed
        assert "verification" in parsed

    async def test_export_to_json_pretty_print(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """Pretty-printed JSON is human readable."""
        requester_id = uuid4()

        json_str = await export_service.export_to_json(requester_id, pretty_print=True)

        # Should have newlines and indentation
        assert "\n" in json_str
        assert "  " in json_str

    async def test_export_to_json_compact(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """Compact JSON has no extra whitespace."""
        requester_id = uuid4()

        json_str = await export_service.export_to_json(requester_id, pretty_print=False)

        # Should not have pretty-print indentation
        assert "  \"metadata\"" not in json_str

    async def test_json_contains_metadata(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """JSON includes all metadata fields."""
        requester_id = uuid4()

        json_str = await export_service.export_to_json(requester_id)
        parsed = json.loads(json_str)

        metadata = parsed["metadata"]
        assert "export_id" in metadata
        assert "exported_at" in metadata
        assert "format_version" in metadata
        assert metadata["format_version"] == EXPORT_FORMAT_VERSION
        assert "total_events" in metadata
        assert "genesis_hash" in metadata
        assert "latest_hash" in metadata
        assert "sequence_range" in metadata

    async def test_json_contains_verification(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """JSON includes verification information."""
        requester_id = uuid4()

        json_str = await export_service.export_to_json(requester_id)
        parsed = json.loads(json_str)

        verification = parsed["verification"]
        assert "hash_algorithm" in verification
        assert "chain_valid" in verification
        assert "genesis_to_latest" in verification


class TestPIIDetection:
    """Tests for PII detection and rejection."""

    async def test_email_in_payload_rejected(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Events with email in payload are rejected."""
        events = [
            create_fake_event(
                1,
                payload={"note": "Contact user@example.com for details"},
            ),
        ]
        ledger = FakeLedgerPort(events)
        service = LedgerExportService(
            ledger_port=ledger,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        with pytest.raises(PIIDetectedError, match="email"):
            await service.export_complete(uuid4())

    async def test_invalid_actor_id_rejected(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Events with non-UUID actor_id are rejected."""
        events = [
            create_fake_event(
                1,
                actor_id="john.doe",  # Not a UUID
            ),
        ]
        ledger = FakeLedgerPort(events)
        service = LedgerExportService(
            ledger_port=ledger,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        with pytest.raises(PIIDetectedError, match="invalid actor_id"):
            await service.export_complete(uuid4())

    async def test_system_actor_allowed(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Actor_id 'system' is allowed."""
        events = [
            create_fake_event(1, actor_id="system"),
        ]
        ledger = FakeLedgerPort(events)
        service = LedgerExportService(
            ledger_port=ledger,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        # Should not raise
        export = await service.export_complete(uuid4())
        assert export.event_count == 1

    async def test_uuid_actor_allowed(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """UUID actor_id is allowed."""
        events = [
            create_fake_event(1, actor_id=str(uuid4())),
        ]
        ledger = FakeLedgerPort(events)
        service = LedgerExportService(
            ledger_port=ledger,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        # Should not raise
        export = await service.export_complete(uuid4())
        assert export.event_count == 1


class TestPatterns:
    """Tests for PII pattern detection."""

    def test_email_pattern_matches_email(self) -> None:
        """Email pattern matches email addresses."""
        assert EMAIL_PATTERN.search("user@example.com")
        assert EMAIL_PATTERN.search("test.user+tag@sub.domain.co.uk")

    def test_email_pattern_no_false_positives(self) -> None:
        """Email pattern doesn't match non-emails."""
        assert not EMAIL_PATTERN.search("not an email")
        assert not EMAIL_PATTERN.search("user@")
        assert not EMAIL_PATTERN.search("@domain.com")

    def test_uuid_pattern_matches_uuid(self) -> None:
        """UUID pattern matches valid UUIDs."""
        assert UUID_PATTERN.match("550e8400-e29b-41d4-a716-446655440000")
        assert UUID_PATTERN.match(str(uuid4()))

    def test_uuid_pattern_no_false_positives(self) -> None:
        """UUID pattern doesn't match non-UUIDs."""
        assert not UUID_PATTERN.match("not-a-uuid")
        assert not UUID_PATTERN.match("550e8400-e29b-41d4-a716")

    def test_name_pattern_matches_names(self) -> None:
        """Name pattern matches name-like strings."""
        assert NAME_PATTERN.search("John Smith")
        assert NAME_PATTERN.search("Hello Jane Doe how are you")

    def test_name_pattern_no_false_positives(self) -> None:
        """Name pattern doesn't match non-names."""
        assert not NAME_PATTERN.search("john smith")  # Not capitalized
        assert not NAME_PATTERN.search("JOHN SMITH")  # All caps

    def test_technical_terms_not_flagged(self) -> None:
        """Technical terms that look like names are allowed."""
        assert "Event Type" in TECHNICAL_TERMS
        assert "Panel Finding" in TECHNICAL_TERMS
        assert "Time Authority" in TECHNICAL_TERMS


class TestHashChainValidation:
    """Tests for hash chain validation in export."""

    async def test_valid_hash_chain_detected(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Valid hash chain is detected."""
        # Create events with proper hash chain
        event1 = create_fake_event(1, prev_hash=f"blake3:{'0' * 64}")
        event2 = create_fake_event(
            2,
            prev_hash=event1.event.hash,  # References event1's hash
        )
        ledger = FakeLedgerPort([event1, event2])
        service = LedgerExportService(
            ledger_port=ledger,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        export = await service.export_complete(uuid4())

        assert export.verification.chain_valid is True

    async def test_broken_hash_chain_detected(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Broken hash chain is detected."""
        # Create events with broken hash chain
        event1 = create_fake_event(1, prev_hash=f"blake3:{'0' * 64}")
        event2 = create_fake_event(
            2,
            prev_hash=f"blake3:{'wrong' * 16}",  # Wrong prev_hash
        )
        ledger = FakeLedgerPort([event1, event2])
        service = LedgerExportService(
            ledger_port=ledger,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        export = await service.export_complete(uuid4())

        assert export.verification.chain_valid is False


class TestHashAlgorithmDetection:
    """Tests for hash algorithm detection."""

    async def test_blake3_algorithm_detected(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """BLAKE3 algorithm is detected from hash prefix."""
        events = [
            create_fake_event(1),  # Default uses blake3:...
        ]
        ledger = FakeLedgerPort(events)
        service = LedgerExportService(
            ledger_port=ledger,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        export = await service.export_complete(uuid4())

        assert export.verification.hash_algorithm == "BLAKE3"

    async def test_empty_ledger_defaults_to_blake3(
        self,
        export_service: LedgerExportService,
    ) -> None:
        """Empty ledger defaults to BLAKE3."""
        export = await export_service.export_complete(uuid4())

        assert export.verification.hash_algorithm == "BLAKE3"


class TestStreamExport:
    """Tests for streaming export."""

    async def test_stream_returns_complete_export(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Stream export returns complete export."""
        service = LedgerExportService(
            ledger_port=ledger_with_events,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        exports = []
        async for export in service.stream_export(requester_id):
            exports.append(export)

        assert len(exports) == 1
        assert exports[0].event_count == 10
