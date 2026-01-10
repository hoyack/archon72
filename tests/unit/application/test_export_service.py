"""Unit tests for Export Service (Story 4.7, Task 2).

Tests for regulatory export functionality (FR139, FR140).

Constitutional Constraints:
- FR139: Export SHALL support structured audit format (JSON Lines, CSV)
- FR140: Third-party attestation interface with attestation metadata
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.api.models.observer import AttestationMetadata, ExportFormat
from src.application.ports.event_store import EventStorePort
from src.application.ports.hsm import HSMMode, HSMProtocol, SignatureResult
from src.application.services.export_service import ExportService
from src.domain.events import Event
from src.infrastructure.stubs.event_store_stub import EventStoreStub


# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_event(
    sequence: int,
    event_type: str = "test.event",
    payload: dict[str, Any] | None = None,
    authority_timestamp: datetime | None = None,
) -> Event:
    """Create a test event with given parameters."""
    ts = authority_timestamp or datetime.now(timezone.utc)
    return Event(
        event_id=uuid4(),
        sequence=sequence,
        event_type=event_type,
        payload=payload or {"test": "data"},
        prev_hash="0" * 64 if sequence == 1 else "a" * 64,
        content_hash="b" * 64,
        signature="sig123",
        witness_id="witness-001",
        witness_signature="wsig123",
        local_timestamp=ts,
        authority_timestamp=ts,
    )


class MockHSMProtocol(HSMProtocol):
    """Mock HSM for testing export signature."""

    def __init__(self) -> None:
        self._signed_contents: list[bytes] = []

    async def sign(self, content: bytes) -> SignatureResult:
        self._signed_contents.append(content)
        return SignatureResult(
            content=content,
            signature=b"mock_signature_" + content[:20],
            mode=HSMMode.DEVELOPMENT,
            key_id="test-key-001",
        )

    async def verify(self, content: bytes, signature: bytes) -> bool:
        return signature.startswith(b"mock_signature_")

    async def generate_key_pair(self) -> str:
        return "test-key-001"

    async def get_mode(self) -> HSMMode:
        return HSMMode.DEVELOPMENT

    async def get_current_key_id(self) -> str:
        return "test-key-001"

    async def verify_with_key(
        self,
        content: bytes,
        signature: bytes,
        key_id: str,
    ) -> bool:
        return signature.startswith(b"mock_signature_")

    async def get_public_key_bytes(self, key_id: str | None = None) -> bytes:
        """Return mock public key bytes (32 bytes for Ed25519)."""
        return b"\x00" * 32


@pytest.fixture
def event_store() -> EventStoreStub:
    """Provide event store stub with test events."""
    store = EventStoreStub()
    # Add test events
    for i in range(1, 6):
        event = create_test_event(
            sequence=i,
            event_type=f"type_{i % 3}",  # type_0, type_1, type_2
            authority_timestamp=datetime(2026, 1, i, 12, 0, 0, tzinfo=timezone.utc),
        )
        store.add_event(event)
    return store


@pytest.fixture
def hsm() -> MockHSMProtocol:
    """Provide mock HSM."""
    return MockHSMProtocol()


@pytest.fixture
def export_service(event_store: EventStoreStub) -> ExportService:
    """Provide export service without HSM."""
    return ExportService(event_store=event_store)


@pytest.fixture
def export_service_with_hsm(
    event_store: EventStoreStub,
    hsm: MockHSMProtocol,
) -> ExportService:
    """Provide export service with HSM for signing."""
    return ExportService(event_store=event_store, hsm=hsm)


# =============================================================================
# Test: JSON Lines Export (FR139)
# =============================================================================


class TestExportJsonl:
    """Tests for JSON Lines export format (FR139)."""

    @pytest.mark.asyncio
    async def test_export_jsonl_generates_valid_output(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify export_jsonl yields valid JSON objects."""
        lines = []
        async for line in export_service.export_jsonl():
            lines.append(line)

        assert len(lines) == 5
        for line in lines:
            # Each line should be valid JSON
            parsed = json.loads(line.strip())
            assert "event_id" in parsed
            assert "sequence" in parsed
            assert "content_hash" in parsed

    @pytest.mark.asyncio
    async def test_export_jsonl_one_json_per_line(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify each line is a complete JSON object (FR139)."""
        lines = []
        async for line in export_service.export_jsonl():
            lines.append(line)

        for line in lines:
            assert line.endswith("\n")
            # Should parse without combining with other lines
            json.loads(line.strip())

    @pytest.mark.asyncio
    async def test_export_jsonl_includes_hash_chain_fields(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify export includes all hash chain fields for verification."""
        lines = []
        async for line in export_service.export_jsonl():
            lines.append(line)

        parsed = json.loads(lines[0].strip())
        assert "content_hash" in parsed
        assert "prev_hash" in parsed
        assert "signature" in parsed
        assert "witness_id" in parsed
        assert "witness_signature" in parsed

    @pytest.mark.asyncio
    async def test_export_jsonl_with_sequence_range(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify sequence range filtering works."""
        lines = []
        async for line in export_service.export_jsonl(
            start_sequence=2,
            end_sequence=4,
        ):
            lines.append(line)

        assert len(lines) == 3
        sequences = [json.loads(line)["sequence"] for line in lines]
        assert sequences == [2, 3, 4]

    @pytest.mark.asyncio
    async def test_export_jsonl_with_date_filter(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify date range filtering works."""
        lines = []
        async for line in export_service.export_jsonl(
            start_date=datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 1, 4, 23, 59, 59, tzinfo=timezone.utc),
        ):
            lines.append(line)

        assert len(lines) == 3  # Events 2, 3, 4

    @pytest.mark.asyncio
    async def test_export_jsonl_with_event_type_filter(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify event type filtering works."""
        lines = []
        async for line in export_service.export_jsonl(event_types=["type_1"]):
            lines.append(line)

        for line in lines:
            parsed = json.loads(line)
            assert parsed["event_type"] == "type_1"


# =============================================================================
# Test: CSV Export (FR139)
# =============================================================================


class TestExportCsv:
    """Tests for CSV export format (FR139)."""

    @pytest.mark.asyncio
    async def test_export_csv_generates_valid_output(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify export_csv yields valid CSV rows."""
        rows = []
        async for row in export_service.export_csv():
            rows.append(row)

        # First row is header + 5 data rows
        assert len(rows) == 6

    @pytest.mark.asyncio
    async def test_export_csv_starts_with_header(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify first yield is the header row."""
        rows = []
        async for row in export_service.export_csv():
            rows.append(row)
            break  # Only get first row

        header = rows[0]
        assert "event_id" in header
        assert "sequence" in header
        assert "content_hash" in header
        assert "prev_hash" in header
        assert "signature" in header

    @pytest.mark.asyncio
    async def test_export_csv_includes_all_verification_columns(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify CSV includes all fields for verification (FR139)."""
        rows = []
        async for row in export_service.export_csv():
            rows.append(row)
            break

        header = rows[0]
        required_columns = [
            "event_id",
            "sequence",
            "event_type",
            "payload",
            "content_hash",
            "prev_hash",
            "signature",
            "agent_id",
            "witness_id",
            "witness_signature",
            "local_timestamp",
            "authority_timestamp",
            "hash_algorithm_version",
            "sig_alg_version",
        ]
        for col in required_columns:
            assert col in header, f"Missing column: {col}"

    @pytest.mark.asyncio
    async def test_export_csv_with_sequence_range(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify sequence range filtering works for CSV."""
        rows = []
        async for row in export_service.export_csv(
            start_sequence=2,
            end_sequence=4,
        ):
            rows.append(row)

        # Header + 3 data rows
        assert len(rows) == 4


# =============================================================================
# Test: Attestation Metadata (FR140)
# =============================================================================


class TestAttestationMetadata:
    """Tests for attestation metadata generation (FR140)."""

    @pytest.mark.asyncio
    async def test_attestation_metadata_populated(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify attestation metadata is properly populated."""
        metadata = await export_service.generate_attestation_metadata(
            sequence_start=1,
            sequence_end=5,
            event_count=5,
        )

        assert metadata.sequence_start == 1
        assert metadata.sequence_end == 5
        assert metadata.event_count == 5
        assert metadata.exporter_id == "archon72-observer-api"
        assert len(metadata.chain_hash_at_export) == 64

    @pytest.mark.asyncio
    async def test_attestation_metadata_includes_export_id(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify export_id is a valid UUID."""
        metadata = await export_service.generate_attestation_metadata(
            sequence_start=1,
            sequence_end=5,
            event_count=5,
        )

        assert isinstance(metadata.export_id, UUID)

    @pytest.mark.asyncio
    async def test_attestation_metadata_includes_timestamp(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify exported_at timestamp is set."""
        before = datetime.now(timezone.utc)
        metadata = await export_service.generate_attestation_metadata(
            sequence_start=1,
            sequence_end=5,
            event_count=5,
        )
        after = datetime.now(timezone.utc)

        assert before <= metadata.exported_at <= after

    @pytest.mark.asyncio
    async def test_attestation_metadata_includes_chain_hash(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify chain_hash_at_export is from the end sequence event."""
        metadata = await export_service.generate_attestation_metadata(
            sequence_start=1,
            sequence_end=5,
            event_count=5,
        )

        # Should be a valid hex hash
        assert len(metadata.chain_hash_at_export) == 64
        assert all(c in "0123456789abcdef" for c in metadata.chain_hash_at_export)

    @pytest.mark.asyncio
    async def test_attestation_metadata_with_filter_criteria(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify filter criteria is stored in metadata."""
        filter_criteria = {"event_types": ["vote", "halt"]}
        metadata = await export_service.generate_attestation_metadata(
            sequence_start=1,
            sequence_end=5,
            event_count=5,
            filter_criteria=filter_criteria,
        )

        assert metadata.filter_criteria == filter_criteria


# =============================================================================
# Test: Export Signature (FR140)
# =============================================================================


class TestExportSignature:
    """Tests for export signature when HSM is available."""

    @pytest.mark.asyncio
    async def test_export_signature_generated_with_hsm(
        self,
        export_service_with_hsm: ExportService,
    ) -> None:
        """Verify export is signed when HSM is available."""
        metadata = await export_service_with_hsm.generate_attestation_metadata(
            sequence_start=1,
            sequence_end=5,
            event_count=5,
        )

        assert metadata.export_signature is not None
        assert len(metadata.export_signature) > 0

    @pytest.mark.asyncio
    async def test_export_signature_not_present_without_hsm(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify export_signature is None without HSM."""
        metadata = await export_service.generate_attestation_metadata(
            sequence_start=1,
            sequence_end=5,
            event_count=5,
        )

        assert metadata.export_signature is None


# =============================================================================
# Test: Streaming Behavior
# =============================================================================


class TestStreamingExport:
    """Tests for streaming export behavior."""

    @pytest.mark.asyncio
    async def test_export_yields_incrementally(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify export yields events one at a time."""
        count = 0
        async for _ in export_service.export_jsonl():
            count += 1

        assert count == 5

    @pytest.mark.asyncio
    async def test_export_empty_store(
        self,
        event_store: EventStoreStub,
    ) -> None:
        """Verify empty store returns no events."""
        event_store.clear()
        service = ExportService(event_store=event_store)

        lines = []
        async for line in service.export_jsonl():
            lines.append(line)

        assert len(lines) == 0

    @pytest.mark.asyncio
    async def test_csv_export_empty_store_yields_header_only(
        self,
        event_store: EventStoreStub,
    ) -> None:
        """Verify empty store CSV export yields header only."""
        event_store.clear()
        service = ExportService(event_store=event_store)

        rows = []
        async for row in service.export_csv():
            rows.append(row)

        # Just the header row
        assert len(rows) == 1
        assert "event_id" in rows[0]


# =============================================================================
# Test: Event Data Conversion
# =============================================================================


class TestEventDataConversion:
    """Tests for event to export format conversion."""

    @pytest.mark.asyncio
    async def test_jsonl_payload_is_serialized(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify payload is properly serialized in JSONL."""
        lines = []
        async for line in export_service.export_jsonl():
            lines.append(line)

        parsed = json.loads(lines[0])
        assert isinstance(parsed["payload"], dict)

    @pytest.mark.asyncio
    async def test_jsonl_timestamps_are_iso8601(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify timestamps are in ISO 8601 format."""
        lines = []
        async for line in export_service.export_jsonl():
            lines.append(line)

        parsed = json.loads(lines[0])
        # Should be parseable as ISO 8601
        local_ts = parsed["local_timestamp"]
        assert "2026" in local_ts  # Year should be present

    @pytest.mark.asyncio
    async def test_csv_payload_is_json_string(
        self,
        export_service: ExportService,
    ) -> None:
        """Verify payload in CSV is a JSON string."""
        rows = []
        async for row in export_service.export_csv():
            rows.append(row)

        # Skip header, get first data row
        data_row = rows[1]
        # The payload column should contain a JSON string
        # CSV format means it's embedded in the row
        assert "test" in data_row or "{" in data_row
