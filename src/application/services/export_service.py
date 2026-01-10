"""Export Service for regulatory reporting (Story 4.7, Task 2).

Provides export functionality for regulatory compliance (FR139, FR140).

Constitutional Constraints:
- FR139: Export SHALL support structured audit format (JSON Lines, CSV)
- FR140: Third-party attestation interface with attestation metadata
- FR44: No authentication required - exports are public
- FR48: Rate limits identical for all users
- CT-11: Silent failure destroys legitimacy - export must include all verification data
- CT-12: Witnessing creates accountability - export must include witness attribution
"""

import csv
import io
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from src.application.dtos.export import AttestationMetadataDTO, ExportFormatDTO
from src.application.ports.event_store import EventStorePort
from src.application.ports.hsm import HSMProtocol
from src.domain.events import Event


class ExportService:
    """Service for regulatory export generation (FR139, FR140).

    Provides streaming export in JSON Lines and CSV formats for
    regulatory compliance and third-party attestation.

    Per FR139: Structured audit format export (JSON Lines, CSV).
    Per FR140: Third-party attestation interface with metadata.
    Per CT-11: All verification data must be included.
    Per CT-12: Witness attribution must be included.

    Attributes:
        _event_store: Port for accessing event data.
        _hsm: Optional HSM for signing attestation metadata.
    """

    # CSV column headers matching ObserverEventResponse fields
    CSV_HEADERS = [
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

    def __init__(
        self,
        event_store: EventStorePort,
        hsm: Optional[HSMProtocol] = None,
    ) -> None:
        """Initialize export service.

        Args:
            event_store: Port for event store operations.
            hsm: Optional HSM for signing attestation metadata.
                If not provided, export_signature will be None.
        """
        self._event_store = event_store
        self._hsm = hsm

    async def export_jsonl(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        """Export events as JSON Lines format (FR139).

        Yields one JSON object per line for streaming support.
        Each line is a complete, valid JSON document with newline terminator.

        Per FR139: Structured audit format export.
        Per CT-11: All hash chain data included for verification.
        Per CT-12: Witness attribution included.

        Args:
            start_sequence: First sequence to export (optional).
            end_sequence: Last sequence to export (optional).
            start_date: Filter from date (optional).
            end_date: Filter until date (optional).
            event_types: Filter by event types (optional).

        Yields:
            JSON string for each event, newline terminated.
        """
        async for event in self._event_store.stream_events(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        ):
            yield self._event_to_jsonl(event)

    async def export_csv(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        """Export events as CSV format (FR139).

        First yield is header row, subsequent yields are data rows.
        Format follows RFC 4180 specification.

        Per FR139: Structured audit format export.
        Per CT-11: All verification fields included.
        Per CT-12: Witness attribution included.

        Args:
            start_sequence: First sequence to export (optional).
            end_sequence: Last sequence to export (optional).
            start_date: Filter from date (optional).
            end_date: Filter until date (optional).
            event_types: Filter by event types (optional).

        Yields:
            CSV rows including header.
        """
        # Yield header row first
        yield self._csv_row(self.CSV_HEADERS)

        # Yield data rows
        async for event in self._event_store.stream_events(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        ):
            yield self._event_to_csv_row(event)

    async def generate_attestation_metadata(
        self,
        sequence_start: int,
        sequence_end: int,
        event_count: int,
        filter_criteria: Optional[dict[str, Any]] = None,
    ) -> AttestationMetadataDTO:
        """Generate attestation metadata for export (FR140).

        Creates metadata for third-party attestation services.
        If HSM is available, signs the metadata for verification.

        Per FR140: Third-party attestation interface with metadata.

        Args:
            sequence_start: First sequence in export.
            sequence_end: Last sequence in export.
            event_count: Number of events exported.
            filter_criteria: Filters applied to export (optional).

        Returns:
            AttestationMetadataDTO with export context and optional signature.
        """
        # Get chain hash from the end sequence event
        end_event = await self._event_store.get_event_by_sequence(sequence_end)
        chain_hash = end_event.content_hash if end_event else "0" * 64

        export_id = uuid4()
        exported_at = datetime.now(timezone.utc)
        export_signature: str | None = None

        # Sign metadata if HSM available
        if self._hsm:
            signature_data = self._build_signature_data_dict(
                export_id=export_id,
                exported_at=exported_at,
                sequence_start=sequence_start,
                sequence_end=sequence_end,
                event_count=event_count,
                filter_criteria=filter_criteria,
                chain_hash=chain_hash,
            )
            result = await self._hsm.sign(signature_data.encode("utf-8"))
            export_signature = result.signature.hex()

        return AttestationMetadataDTO(
            export_id=export_id,
            exported_at=exported_at,
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            event_count=event_count,
            filter_criteria=filter_criteria,
            chain_hash_at_export=chain_hash,
            export_signature=export_signature,
            exporter_id="archon72-observer-api",
        )

    def _event_to_jsonl(self, event: Event) -> str:
        """Convert event to JSON Lines format.

        Args:
            event: Event to convert.

        Returns:
            JSON string with newline terminator.
        """
        data = self._event_to_dict(event)
        return json.dumps(data, default=str, ensure_ascii=False) + "\n"

    def _event_to_csv_row(self, event: Event) -> str:
        """Convert event to CSV row.

        Args:
            event: Event to convert.

        Returns:
            CSV row string.
        """
        row = [
            str(event.event_id),
            str(event.sequence),
            event.event_type,
            json.dumps(dict(event.payload), ensure_ascii=False),
            event.content_hash,
            event.prev_hash,
            event.signature,
            event.agent_id or "",
            event.witness_id,
            event.witness_signature,
            event.local_timestamp.isoformat(),
            event.authority_timestamp.isoformat() if event.authority_timestamp else "",
            str(event.hash_alg_version),
            str(event.sig_alg_version),
        ]
        return self._csv_row(row)

    def _csv_row(self, values: list[str]) -> str:
        """Format values as RFC 4180 CSV row.

        Args:
            values: List of string values.

        Returns:
            CSV formatted row string.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(values)
        return output.getvalue()

    def _event_to_dict(self, event: Event) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization.

        Args:
            event: Event to convert.

        Returns:
            Dictionary representation of event.
        """
        return {
            "event_id": str(event.event_id),
            "sequence": event.sequence,
            "event_type": event.event_type,
            "payload": dict(event.payload),
            "content_hash": event.content_hash,
            "prev_hash": event.prev_hash,
            "signature": event.signature,
            "agent_id": event.agent_id,
            "witness_id": event.witness_id,
            "witness_signature": event.witness_signature,
            "local_timestamp": event.local_timestamp.isoformat(),
            "authority_timestamp": (
                event.authority_timestamp.isoformat()
                if event.authority_timestamp
                else None
            ),
            "hash_algorithm_version": event.hash_alg_version,
            "sig_alg_version": event.sig_alg_version,
        }

    def _build_signature_data_dict(
        self,
        export_id: Any,
        exported_at: datetime,
        sequence_start: int,
        sequence_end: int,
        event_count: int,
        filter_criteria: Optional[dict[str, Any]],
        chain_hash: str,
    ) -> str:
        """Build canonical JSON for signing.

        Args:
            export_id: Export UUID.
            exported_at: Export timestamp.
            sequence_start: First sequence in export.
            sequence_end: Last sequence in export.
            event_count: Number of events.
            filter_criteria: Applied filters.
            chain_hash: Hash at export time.

        Returns:
            Canonical JSON string for signing.
        """
        data = {
            "export_id": str(export_id),
            "exported_at": exported_at.isoformat(),
            "sequence_start": sequence_start,
            "sequence_end": sequence_end,
            "event_count": event_count,
            "filter_criteria": filter_criteria,
            "chain_hash_at_export": chain_hash,
            "exporter_id": "archon72-observer-api",
        }
        return json.dumps(data, sort_keys=True, ensure_ascii=False)
