"""Export DTOs for regulatory reporting (Story 4.7).

Application-layer DTOs for export functionality. These are used by
the ExportService and mapped to API models by the routes.

Architecture Note:
Application layer defines its own DTOs. API layer converts these
to Pydantic response models. This maintains hexagonal architecture
boundary where application layer has no dependency on API layer.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ExportFormatDTO(str, Enum):
    """Supported export formats (FR139).

    Per FR139: Export SHALL support structured audit format.

    Values:
        JSONL: JSON Lines format (one JSON object per line).
        CSV: Comma-separated values format (RFC 4180).
    """

    JSONL = "jsonl"
    CSV = "csv"


@dataclass(frozen=True)
class AttestationMetadataDTO:
    """Attestation metadata for regulatory export (FR140).

    Provides context and verification data for exported records.
    Third-party attestation services can use this metadata to
    verify export authenticity and completeness.

    Per FR140: Third-party attestation interface with metadata.

    Attributes:
        export_id: Unique identifier for this export.
        exported_at: When export was generated (UTC).
        sequence_start: First event sequence in export.
        sequence_end: Last event sequence in export.
        event_count: Number of events exported.
        filter_criteria: Filters applied to export (optional).
        chain_hash_at_export: Content hash of latest event at export time.
        export_signature: Signature of export metadata for verification (optional).
        exporter_id: ID of service that generated export.
    """

    export_id: UUID
    exported_at: datetime
    sequence_start: int
    sequence_end: int
    event_count: int
    chain_hash_at_export: str
    exporter_id: str = "archon72-observer-api"
    filter_criteria: dict[str, Any] | None = None
    export_signature: str | None = None
