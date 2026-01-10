"""Procedural Record Generator Port interface (Story 2.8, FR141-FR142).

This module defines the application port for procedural record generation,
enabling deliberation records to be created with full audit trails
including agenda, participants, votes, timeline, and decisions.

Constitutional Constraints:
- FR141: Procedural records SHALL be generated for each deliberation
- FR142: Records SHALL include agenda, participants, votes, timeline, decisions
- CT-12: Witnessing creates accountability -> Immutable record structure
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, eq=True)
class ProceduralRecordData:
    """Data structure for a procedural record (FR141-FR142).

    This dataclass captures all the information in a procedural record,
    including the full audit trail of a deliberation.

    All collection fields use immutable types (tuple, MappingProxyType) to ensure
    record integrity per CT-12 (witnessing creates accountability).

    Attributes:
        record_id: Unique identifier for this procedural record (UUID).
        deliberation_id: ID of the deliberation this record documents (UUID).
        agenda_items: Tuple of agenda item descriptions (immutable).
        participant_ids: Tuple of participant agent IDs (immutable).
        vote_summary: Immutable mapping of votes (e.g., {"aye": 45, "nay": 20}).
        timeline_events: Tuple of immutable timeline event mappings (immutable).
        decisions: Tuple of decisions made (immutable).
        record_hash: SHA-256 hash of record content (64 hex chars).
        signature: Cryptographic signature of the record.

    Example:
        >>> from uuid import uuid4
        >>> from types import MappingProxyType
        >>> data = ProceduralRecordData(
        ...     record_id=uuid4(),
        ...     deliberation_id=uuid4(),
        ...     agenda_items=("Motion A",),
        ...     participant_ids=("agent-1",),
        ...     vote_summary=MappingProxyType({"aye": 45}),
        ...     timeline_events=(MappingProxyType({"event": "start"}),),
        ...     decisions=("Approved",),
        ...     record_hash="a" * 64,
        ...     signature="sig123",
        ... )
    """

    record_id: UUID
    deliberation_id: UUID
    agenda_items: tuple[str, ...]
    participant_ids: tuple[str, ...]
    vote_summary: MappingProxyType[str, int]
    timeline_events: tuple[MappingProxyType[str, Any], ...]
    decisions: tuple[str, ...]
    record_hash: str
    signature: str


class ProceduralRecordGeneratorPort(Protocol):
    """Port interface for procedural record generation (FR141-FR142).

    This protocol defines the contract for procedural record generation
    adapters. Implementations must provide record generation, retrieval,
    and verification capabilities.

    Constitutional Constraints:
        - FR141: Complete record of deliberation
        - FR142: All required fields captured

    Example implementation:
        class ProceduralRecordGeneratorAdapter:
            async def generate_record(
                self, deliberation_id: UUID
            ) -> ProceduralRecordData:
                delib_data = await self.get_deliberation_data(deliberation_id)
                record_id = uuid4()
                record_hash = await self.compute_hash(delib_data)
                signature = await self.hsm.sign(record_hash.encode())
                return ProceduralRecordData(
                    record_id=record_id,
                    deliberation_id=deliberation_id,
                    agenda_items=delib_data.agenda,
                    participant_ids=delib_data.participants,
                    vote_summary=delib_data.votes,
                    timeline_events=delib_data.timeline,
                    decisions=delib_data.decisions,
                    record_hash=record_hash,
                    signature=signature,
                )
    """

    async def generate_record(
        self,
        deliberation_id: UUID,
    ) -> ProceduralRecordData:
        """Generate a procedural record for a deliberation (FR141-FR142).

        Collects all deliberation data and creates a signed procedural
        record containing agenda, participants, votes, timeline, and decisions.

        Args:
            deliberation_id: The UUID of the deliberation to document.

        Returns:
            ProceduralRecordData with complete record.

        Raises:
            CertificationError: If record generation fails.
        """
        ...

    async def get_record(
        self,
        record_id: UUID,
    ) -> ProceduralRecordData | None:
        """Get a stored procedural record.

        Args:
            record_id: The UUID of the record.

        Returns:
            The ProceduralRecordData if found, None otherwise.
        """
        ...

    async def verify_record(
        self,
        record_id: UUID,
    ) -> bool:
        """Verify a procedural record's integrity.

        Recomputes the hash and verifies the signature.

        Args:
            record_id: The UUID of the record to verify.

        Returns:
            True if record is valid, False otherwise.
        """
        ...
