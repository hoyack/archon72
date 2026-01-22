"""Orphan petition detection service (Story 8.3, FR-8.5).

This service identifies petitions stuck in RECEIVED state for >24 hours
and emits detection events for operator visibility and remediation.

Constitutional Constraints:
- FR-8.5: System SHALL identify petitions stuck in RECEIVED state
- NFR-7.1: 100% of orphans must be detected
- CT-12: All detection events must be witnessed
- CT-11: Silent failure destroys legitimacy -> Log all orphans

Architectural Notes:
- Queries petition repository for RECEIVED state petitions
- Computes age based on received_at timestamp
- Emits OrphanPetitionsDetected event via EventWriterService
- Designed for daily scheduled execution

Developer Golden Rules:
1. WITNESS EVERYTHING - Orphan detection events require witnessing
2. FAIL LOUD - Never silently swallow detection errors
3. READS DURING HALT - Detection queries work during halt (CT-13)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

from src.domain.events.orphan_petition import (
    ORPHAN_PETITIONS_DETECTED_EVENT_TYPE,
    OrphanPetitionsDetectedEventPayload,
)
from src.domain.models.orphan_petition_detection import (
    OrphanPetitionDetectionResult,
    OrphanPetitionInfo,
)
from src.domain.models.petition_submission import PetitionState, PetitionSubmission

logger = logging.getLogger(__name__)


class PetitionRepositoryPort(Protocol):
    """Port for petition repository operations.

    This protocol defines the interface for querying petitions
    from the persistence layer.
    """

    def find_by_state(
        self, state: PetitionState, received_before: datetime | None = None
    ) -> list[PetitionSubmission]:
        """Find petitions in a specific state.

        Args:
            state: The petition state to query
            received_before: Optional cutoff timestamp (UTC)

        Returns:
            List of petitions matching the criteria.
        """
        ...


class EventWriterPort(Protocol):
    """Port for event writing with witnessing.

    This protocol defines the interface for emitting witnessed events.
    """

    def write_event(
        self,
        event_type: str,
        payload: object,
        agent_id: str,
        entity_id: UUID,
    ) -> None:
        """Write an event to the ledger with witnessing.

        Args:
            event_type: Type of event being written
            payload: Event payload (must have get_signable_content method)
            agent_id: ID of agent emitting the event
            entity_id: ID of entity the event pertains to
        """
        ...


class OrphanPetitionDetectionService:
    """Service for detecting orphaned petitions (Story 8.3, FR-8.5).

    This service identifies petitions stuck in RECEIVED state beyond
    acceptable thresholds and emits witnessed events for visibility.

    Constitutional Requirements:
    - FR-8.5: Identify petitions stuck in RECEIVED >24 hours
    - NFR-7.1: 100% detection rate required
    - CT-12: Witnessing for all detection events

    Attributes:
        petition_repository: Repository for querying petitions
        event_writer: Service for emitting witnessed events
        threshold_hours: Hours before a petition is considered orphaned (default: 24)
    """

    def __init__(
        self,
        petition_repository: PetitionRepositoryPort,
        event_writer: EventWriterPort,
        threshold_hours: float = 24.0,
    ):
        """Initialize orphan detection service.

        Args:
            petition_repository: Repository for querying petitions
            event_writer: Service for emitting witnessed events
            threshold_hours: Hours before petition considered orphaned (default: 24)
        """
        self.petition_repository = petition_repository
        self.event_writer = event_writer
        self.threshold_hours = threshold_hours

    def detect_orphans(self) -> OrphanPetitionDetectionResult:
        """Run orphan detection scan (FR-8.5).

        Queries for petitions in RECEIVED state older than threshold
        and emits witnessed event if orphans are found.

        Constitutional Requirements:
        - FR-8.5: Identify all petitions stuck >threshold_hours
        - NFR-7.1: 100% detection rate
        - CT-12: Emit witnessed event for accountability

        Returns:
            OrphanPetitionDetectionResult with detected orphans.

        Raises:
            Exception: If detection or event emission fails (FAIL LOUD)
        """
        detection_id = uuid4()
        logger.info(
            "Starting orphan petition detection",
            extra={
                "detection_id": str(detection_id),
                "threshold_hours": self.threshold_hours,
            },
        )

        # Calculate cutoff timestamp (FR-8.5)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.threshold_hours)

        # Query for RECEIVED petitions before cutoff
        # Constitutional: CT-13 - Read operations allowed during halt
        received_petitions = self.petition_repository.find_by_state(
            state=PetitionState.RECEIVED, received_before=cutoff_time
        )

        # Build orphan info list
        orphan_infos: list[OrphanPetitionInfo] = []
        for petition in received_petitions:
            age_hours = (
                datetime.now(timezone.utc) - petition.created_at
            ).total_seconds() / 3600.0

            orphan_info = OrphanPetitionInfo(
                petition_id=petition.id,
                created_at=petition.created_at,
                age_hours=age_hours,
                petition_type=petition.type.value,
                co_signer_count=petition.co_signer_count,
            )
            orphan_infos.append(orphan_info)

        # Create detection result (FR-8.5, NFR-7.1)
        detection_result = OrphanPetitionDetectionResult.create(
            detection_id=detection_id,
            threshold_hours=self.threshold_hours,
            orphan_petitions=orphan_infos,
        )

        logger.info(
            "Orphan detection completed",
            extra={
                "detection_id": str(detection_id),
                "orphan_count": detection_result.total_orphans,
                "oldest_age_hours": detection_result.oldest_orphan_age_hours,
            },
        )

        # Emit event if orphans found (CT-12: witnessing required)
        if detection_result.has_orphans():
            self._emit_orphans_detected_event(detection_result)

        return detection_result

    def _emit_orphans_detected_event(
        self, detection_result: OrphanPetitionDetectionResult
    ) -> None:
        """Emit OrphanPetitionsDetected event (CT-12).

        Args:
            detection_result: Detection result containing orphan data

        Raises:
            Exception: If event emission fails (FAIL LOUD)
        """
        payload = OrphanPetitionsDetectedEventPayload(
            detected_at=detection_result.detected_at,
            orphan_count=detection_result.total_orphans,
            orphan_petition_ids=detection_result.get_petition_ids(),
            oldest_orphan_age_hours=detection_result.oldest_orphan_age_hours or 0.0,
            detection_threshold_hours=detection_result.threshold_hours,
        )

        # Constitutional: CT-12 - Witnessing creates accountability
        self.event_writer.write_event(
            event_type=ORPHAN_PETITIONS_DETECTED_EVENT_TYPE,
            payload=payload,
            agent_id="orphan-detection-system",
            entity_id=detection_result.detection_id,
        )

        logger.warning(
            "Orphaned petitions detected",
            extra={
                "detection_id": str(detection_result.detection_id),
                "orphan_count": detection_result.total_orphans,
                "orphan_ids": [str(pid) for pid in detection_result.get_petition_ids()],
                "oldest_age_hours": detection_result.oldest_orphan_age_hours,
            },
        )
