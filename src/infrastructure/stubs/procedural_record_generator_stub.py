"""Procedural record generator stub implementation (Story 2.8, FR141-FR142).

In-memory stub for ProceduralRecordGeneratorPort for development and testing.
Follows DEV_MODE_WATERMARK pattern per RT-1/ADR-4.

Constitutional Constraints:
- FR141: Procedural records SHALL be generated for each deliberation
- FR142: Records SHALL include agenda, participants, votes, timeline, decisions
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern for dev stubs
- CT-12: Witnessing creates accountability -> Immutable record structure
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.procedural_record_generator import (
    ProceduralRecordData,
)

logger = structlog.get_logger()


# DEV_MODE_WATERMARK per RT-1/ADR-4
# This constant indicates this is a development stub, not production code
DEV_MODE_WATERMARK: str = "DEV_STUB:ProceduralRecordGeneratorStub:v1"


@dataclass
class MockDeliberationData:
    """Mock deliberation data for testing."""

    agenda_items: list[str]
    participant_ids: list[str]
    vote_summary: dict[str, int]
    timeline_events: list[dict[str, Any]]
    decisions: list[str]


class ProceduralRecordGeneratorStub:
    """In-memory stub for ProceduralRecordGeneratorPort (FR141-FR142).

    Development and testing implementation that stores procedural records
    in memory. Follows DEV_MODE_WATERMARK pattern.

    WARNING: This is a development stub. Not for production use.
    Production implementations should use HSM for signing.

    Attributes:
        _records: In-memory dict mapping record_id to ProceduralRecordData.
        _mock_data: In-memory dict mapping deliberation_id to mock data.
        _halt_checker: Optional halt checker for HALT FIRST enforcement.

    Example:
        >>> stub = ProceduralRecordGeneratorStub()
        >>> record = await stub.generate_record(uuid4())
        >>> is_valid = await stub.verify_record(record.record_id)
        >>> is_valid  # True
    """

    def __init__(
        self,
        halt_checker: HaltChecker | None = None,
    ) -> None:
        """Initialize empty record store.

        Args:
            halt_checker: Optional halt checker for HALT FIRST enforcement.
        """
        self._records: dict[UUID, ProceduralRecordData] = {}
        self._mock_data: dict[UUID, MockDeliberationData] = {}
        self._halt_checker = halt_checker
        logger.debug(
            "procedural_record_generator_stub_initialized",
            watermark=DEV_MODE_WATERMARK,
        )

    def register_mock_deliberation_data(
        self,
        deliberation_id: UUID,
        agenda_items: list[str],
        participant_ids: list[str],
        vote_summary: dict[str, int],
        timeline_events: list[dict[str, Any]],
        decisions: list[str],
    ) -> None:
        """Register mock deliberation data for testing.

        This is an additional method for the stub to allow setting up
        test data. Production implementations would fetch from real sources.

        Args:
            deliberation_id: UUID of the deliberation.
            agenda_items: List of agenda item descriptions.
            participant_ids: List of participant agent IDs.
            vote_summary: Summary of votes.
            timeline_events: Key timestamped events.
            decisions: List of decisions made.
        """
        self._mock_data[deliberation_id] = MockDeliberationData(
            agenda_items=agenda_items,
            participant_ids=participant_ids,
            vote_summary=vote_summary,
            timeline_events=timeline_events,
            decisions=decisions,
        )
        logger.debug(
            "mock_deliberation_data_registered",
            deliberation_id=str(deliberation_id),
            agenda_item_count=len(agenda_items),
            participant_count=len(participant_ids),
        )

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
        """
        record_id = uuid4()

        # Get mock data if available, otherwise use defaults
        mock = self._mock_data.get(deliberation_id)
        if mock:
            agenda_items = mock.agenda_items
            participant_ids = mock.participant_ids
            vote_summary = mock.vote_summary
            timeline_events = mock.timeline_events
            decisions = mock.decisions
        else:
            # Default mock data for testing
            agenda_items = ["Mock Agenda Item"]
            participant_ids = ["mock-agent-1", "mock-agent-2"]
            vote_summary = {"aye": 10, "nay": 5}
            timeline_events = []
            decisions = ["Mock Decision"]

        # Compute record hash
        record_content = {
            "deliberation_id": str(deliberation_id),
            "agenda_items": agenda_items,
            "participant_ids": participant_ids,
            "vote_summary": vote_summary,
            "timeline_events": timeline_events,
            "decisions": decisions,
        }
        canonical = json.dumps(
            record_content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        record_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        # DEV MODE signature - in production this would use HSM
        signable_content = f"[DEV MODE]{record_hash}"
        signature = hashlib.sha256(signable_content.encode("utf-8")).hexdigest()

        # Convert to immutable types per CT-12 (witnessing creates accountability)
        immutable_timeline = tuple(MappingProxyType(event) for event in timeline_events)

        record = ProceduralRecordData(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=tuple(agenda_items),
            participant_ids=tuple(participant_ids),
            vote_summary=MappingProxyType(vote_summary),
            timeline_events=immutable_timeline,
            decisions=tuple(decisions),
            record_hash=record_hash,
            signature=signature,
        )

        self._records[record_id] = record

        logger.info(
            "procedural_record_generated",
            record_id=str(record_id),
            deliberation_id=str(deliberation_id),
            record_hash_prefix=record_hash[:8],
            agenda_item_count=len(agenda_items),
            participant_count=len(participant_ids),
        )

        return record

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
        record = self._records.get(record_id)

        logger.debug(
            "procedural_record_lookup",
            record_id=str(record_id),
            found=record is not None,
        )

        return record

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
        record = self._records.get(record_id)

        if record is None:
            logger.debug(
                "record_not_found_for_verification",
                record_id=str(record_id),
            )
            return False

        # Recompute record hash (convert immutable types back to mutable for JSON)
        record_content = {
            "deliberation_id": str(record.deliberation_id),
            "agenda_items": list(record.agenda_items),
            "participant_ids": list(record.participant_ids),
            "vote_summary": dict(record.vote_summary),
            "timeline_events": [dict(event) for event in record.timeline_events],
            "decisions": list(record.decisions),
        }
        canonical = json.dumps(
            record_content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        # Verify hash matches
        if computed_hash != record.record_hash:
            logger.warning(
                "procedural_record_hash_mismatch",
                record_id=str(record_id),
                stored_hash_prefix=record.record_hash[:8],
                computed_hash_prefix=computed_hash[:8],
            )
            return False

        # Verify signature
        signable_content = f"[DEV MODE]{record.record_hash}"
        expected_signature = hashlib.sha256(
            signable_content.encode("utf-8")
        ).hexdigest()

        if expected_signature != record.signature:
            logger.warning(
                "procedural_record_signature_mismatch",
                record_id=str(record_id),
            )
            return False

        logger.debug(
            "procedural_record_verification_passed",
            record_id=str(record_id),
        )

        return True
