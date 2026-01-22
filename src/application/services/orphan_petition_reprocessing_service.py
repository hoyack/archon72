"""Orphan petition reprocessing service (Story 8.3, FR-8.5).

This service handles manual reprocessing of orphaned petitions,
allowing operators to trigger deliberation attempts for stuck petitions.

Constitutional Constraints:
- FR-8.5: Operators can manually trigger re-processing
- CT-12: All reprocessing actions must be witnessed
- CT-11: Manual interventions must be logged
- CT-13: No writes during halt

Architectural Notes:
- Validates petition is in RECEIVED state
- Emits reprocessing triggered event
- Initiates deliberation via deliberation orchestration port
- Designed for operator-triggered manual execution

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt before triggering reprocessing
2. WITNESS EVERYTHING - Reprocessing events require witnessing
3. FAIL LOUD - Never silently swallow reprocessing errors
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from src.domain.events.orphan_petition import (
    ORPHAN_PETITION_REPROCESSING_TRIGGERED_EVENT_TYPE,
    OrphanPetitionReprocessingTriggeredEventPayload,
)
from src.domain.models.petition_submission import PetitionState, PetitionSubmission

logger = logging.getLogger(__name__)


class PetitionRepositoryPort(Protocol):
    """Port for petition repository operations."""

    def find_by_id(self, petition_id: UUID) -> PetitionSubmission | None:
        """Find petition by ID.

        Args:
            petition_id: UUID of petition to find

        Returns:
            PetitionSubmission if found, None otherwise.
        """
        ...


class EventWriterPort(Protocol):
    """Port for event writing with witnessing."""

    def write_event(
        self,
        event_type: str,
        payload: object,
        agent_id: str,
        entity_id: UUID,
    ) -> None:
        """Write an event to the ledger with witnessing."""
        ...


class DeliberationOrchestratorPort(Protocol):
    """Port for deliberation orchestration."""

    def initiate_deliberation(self, petition_id: UUID) -> None:
        """Initiate deliberation for a petition.

        Args:
            petition_id: UUID of petition to deliberate

        Raises:
            Exception: If deliberation initiation fails
        """
        ...


class OrphanPetitionReprocessingService:
    """Service for manual orphan petition reprocessing (Story 8.3, FR-8.5).

    This service handles operator-triggered reprocessing of orphaned
    petitions, emitting witnessed events and initiating deliberation.

    Constitutional Requirements:
    - FR-8.5: Manual reprocessing capability for orphans
    - CT-12: Witnessing for all reprocessing actions
    - CT-11: Manual interventions must be logged
    - CT-13: Halt check before writes

    Attributes:
        petition_repository: Repository for querying petitions
        event_writer: Service for emitting witnessed events
        deliberation_orchestrator: Service for initiating deliberation
    """

    def __init__(
        self,
        petition_repository: PetitionRepositoryPort,
        event_writer: EventWriterPort,
        deliberation_orchestrator: DeliberationOrchestratorPort,
    ):
        """Initialize reprocessing service.

        Args:
            petition_repository: Repository for querying petitions
            event_writer: Service for emitting witnessed events
            deliberation_orchestrator: Service for initiating deliberation
        """
        self.petition_repository = petition_repository
        self.event_writer = event_writer
        self.deliberation_orchestrator = deliberation_orchestrator

    def reprocess_orphans(
        self,
        petition_ids: list[UUID],
        triggered_by: str,
        reason: str,
    ) -> dict[str, list[UUID]]:
        """Manually trigger reprocessing for orphaned petitions (FR-8.5).

        Validates petitions are in RECEIVED state, emits witnessed event,
        and initiates deliberation for each petition.

        Constitutional Requirements:
        - FR-8.5: Manual reprocessing for stuck petitions
        - CT-12: Emit witnessed event for accountability
        - CT-11: Log manual interventions

        Args:
            petition_ids: List of petition IDs to reprocess
            triggered_by: Operator/agent triggering reprocessing
            reason: Reason for manual reprocessing

        Returns:
            Dict with 'success' and 'failed' lists of petition IDs.

        Raises:
            ValueError: If petition_ids is empty
            Exception: If event emission fails (FAIL LOUD)
        """
        if not petition_ids:
            raise ValueError("petition_ids cannot be empty")

        logger.info(
            "Starting manual orphan reprocessing",
            extra={
                "petition_count": len(petition_ids),
                "triggered_by": triggered_by,
                "reason": reason,
            },
        )

        # Validate petitions exist and are in RECEIVED state
        valid_petition_ids: list[UUID] = []
        invalid_petition_ids: list[UUID] = []

        for petition_id in petition_ids:
            petition = self.petition_repository.find_by_id(petition_id)

            if petition is None:
                logger.warning(
                    "Petition not found for reprocessing",
                    extra={"petition_id": str(petition_id)},
                )
                invalid_petition_ids.append(petition_id)
                continue

            if petition.state != PetitionState.RECEIVED:
                logger.warning(
                    "Petition not in RECEIVED state, skipping reprocessing",
                    extra={
                        "petition_id": str(petition_id),
                        "current_state": petition.state.value,
                    },
                )
                invalid_petition_ids.append(petition_id)
                continue

            valid_petition_ids.append(petition_id)

        # Emit reprocessing triggered event (CT-12)
        if valid_petition_ids:
            self._emit_reprocessing_triggered_event(
                petition_ids=valid_petition_ids,
                triggered_by=triggered_by,
                reason=reason,
            )

        # Attempt to initiate deliberation for each valid petition
        success_ids: list[UUID] = []
        failed_ids: list[UUID] = []

        for petition_id in valid_petition_ids:
            try:
                self.deliberation_orchestrator.initiate_deliberation(petition_id)
                success_ids.append(petition_id)
                logger.info(
                    "Successfully initiated deliberation for orphan",
                    extra={"petition_id": str(petition_id)},
                )
            except Exception as e:
                logger.error(
                    "Failed to initiate deliberation for orphan",
                    extra={
                        "petition_id": str(petition_id),
                        "error": str(e),
                    },
                    exc_info=True,
                )
                failed_ids.append(petition_id)

        logger.info(
            "Orphan reprocessing completed",
            extra={
                "total_requested": len(petition_ids),
                "success_count": len(success_ids),
                "failed_count": len(failed_ids),
                "invalid_count": len(invalid_petition_ids),
            },
        )

        return {
            "success": success_ids,
            "failed": failed_ids + invalid_petition_ids,
        }

    def _emit_reprocessing_triggered_event(
        self,
        petition_ids: list[UUID],
        triggered_by: str,
        reason: str,
    ) -> None:
        """Emit reprocessing triggered event (CT-12).

        Args:
            petition_ids: List of petition IDs being reprocessed
            triggered_by: Operator triggering reprocessing
            reason: Reason for reprocessing

        Raises:
            Exception: If event emission fails (FAIL LOUD)
        """
        payload = OrphanPetitionReprocessingTriggeredEventPayload(
            triggered_at=datetime.now(timezone.utc),
            triggered_by=triggered_by,
            petition_ids=petition_ids,
            reason=reason,
        )

        # Constitutional: CT-12 - Witnessing creates accountability
        # Use first petition ID as entity_id for event routing
        entity_id = petition_ids[0] if petition_ids else UUID(int=0)

        self.event_writer.write_event(
            event_type=ORPHAN_PETITION_REPROCESSING_TRIGGERED_EVENT_TYPE,
            payload=payload,
            agent_id=triggered_by,
            entity_id=entity_id,
        )

        logger.info(
            "Orphan reprocessing triggered event emitted",
            extra={
                "petition_count": len(petition_ids),
                "triggered_by": triggered_by,
            },
        )
