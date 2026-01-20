"""Recommendation submission service implementation (Story 4.4, FR-4.6).

This module implements the RecommendationSubmissionProtocol for submitting
Knight recommendations on referred petitions.

Constitutional Constraints:
- FR-4.6: Knight SHALL submit recommendation with mandatory rationale [P0]
- NFR-5.2: Authorization: Only assigned Knight can submit recommendation
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
- CT-12: Every action that affects an Archon must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before writes
2. AUTHORIZATION FIRST - Verify Knight assignment before submission
3. WITNESS EVERYTHING - All submissions require witness hash
4. FAIL LOUD - Raise appropriate errors for invalid submissions
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.domain.errors.recommendation import (
    RationaleRequiredError,
    RecommendationAlreadySubmittedError,
    ReferralNotInReviewError,
    UnauthorizedRecommendationError,
)
from src.domain.errors.referral import ReferralNotFoundError
from src.domain.events.referral import (
    REFERRAL_EVENT_SCHEMA_VERSION,
    ReferralCompletedEvent,
)
from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode
from src.domain.models.referral import Referral, ReferralRecommendation, ReferralStatus

if TYPE_CHECKING:
    from src.application.ports.content_hash import ContentHashProtocol
    from src.application.ports.event_writer import EventWriterProtocol
    from src.application.ports.job_scheduler import JobSchedulerProtocol
    from src.application.ports.referral_execution import ReferralRepositoryProtocol
    from src.application.services.acknowledgment_execution_service import (
        AcknowledgmentExecutionService,
    )

logger = get_logger(__name__)

# Minimum rationale length per FR-4.6
MIN_RATIONALE_LENGTH: int = 10


class RecommendationSubmissionService:
    """Service for submitting Knight recommendations (Story 4.4).

    Implements the recommendation submission flow when a Knight completes
    their review of a referred petition and submits their recommendation.

    The service ensures:
    1. Requester is the assigned Knight (NFR-5.2)
    2. Referral is in IN_REVIEW state
    3. Rationale meets minimum requirements (FR-4.6)
    4. Recommendation is witnessed (CT-12)
    5. Deadline job is cancelled
    6. Petition is routed based on recommendation

    Example:
        >>> service = RecommendationSubmissionService(
        ...     referral_repo=repo,
        ...     event_writer=event_writer,
        ...     hash_service=hash_service,
        ...     job_scheduler=job_scheduler,
        ...     acknowledgment_service=ack_service,
        ... )
        >>> referral = await service.submit(
        ...     referral_id=referral.referral_id,
        ...     requester_id=knight_id,
        ...     recommendation=ReferralRecommendation.ACKNOWLEDGE,
        ...     rationale="This petition addresses a valid concern...",
        ... )
    """

    def __init__(
        self,
        referral_repo: ReferralRepositoryProtocol,
        event_writer: EventWriterProtocol,
        hash_service: ContentHashProtocol,
        job_scheduler: JobSchedulerProtocol,
        acknowledgment_service: AcknowledgmentExecutionService | None = None,
    ) -> None:
        """Initialize the recommendation submission service.

        Args:
            referral_repo: Repository for referral access and persistence.
            event_writer: Service for event emission and witnessing.
            hash_service: Service for generating witness hashes.
            job_scheduler: Service for cancelling deadline jobs.
            acknowledgment_service: Service for ACKNOWLEDGE routing (Epic 3).
        """
        self._referral_repo = referral_repo
        self._event_writer = event_writer
        self._hash_service = hash_service
        self._job_scheduler = job_scheduler
        self._acknowledgment_service = acknowledgment_service

    async def submit(
        self,
        referral_id: UUID,
        requester_id: UUID,
        recommendation: ReferralRecommendation,
        rationale: str,
    ) -> Referral:
        """Submit a Knight's recommendation for a referral.

        Performs authorization checks, validates the rationale,
        records the recommendation with witness hash, cancels the deadline job,
        and routes the petition based on the recommendation.

        Authorization Requirements (NFR-5.2):
        - requester_id MUST match the assigned_knight_id on the referral
        - Referral MUST be in IN_REVIEW state

        Rationale Requirements (FR-4.6):
        - rationale MUST NOT be empty
        - rationale MUST be at least 10 characters

        Args:
            referral_id: The referral to submit recommendation for.
            requester_id: The UUID of the requester (must be assigned Knight).
            recommendation: The Knight's recommendation (ACKNOWLEDGE or ESCALATE).
            rationale: The Knight's rationale explaining the decision.

        Returns:
            The updated Referral with recommendation recorded and status COMPLETED.

        Raises:
            ReferralNotFoundError: Referral doesn't exist.
            UnauthorizedRecommendationError: Requester is not the assigned Knight.
            ReferralNotInReviewError: Referral is not in IN_REVIEW state.
            RationaleRequiredError: Rationale is empty or too short.
            RecommendationAlreadySubmittedError: Referral already has recommendation.
        """
        log = logger.bind(
            referral_id=str(referral_id),
            requester_id=str(requester_id),
            recommendation=recommendation.value,
        )
        log.info("Starting recommendation submission")

        # Step 1: Validate rationale (FR-4.6)
        trimmed_rationale = rationale.strip() if rationale else ""
        if len(trimmed_rationale) < MIN_RATIONALE_LENGTH:
            log.warning(
                "Rationale validation failed",
                provided_length=len(trimmed_rationale),
                min_length=MIN_RATIONALE_LENGTH,
            )
            raise RationaleRequiredError(
                provided_length=len(trimmed_rationale),
                min_length=MIN_RATIONALE_LENGTH,
            )

        # Step 2: Retrieve the referral
        referral = await self._referral_repo.get_by_id(referral_id)
        if referral is None:
            log.warning("Referral not found")
            raise ReferralNotFoundError(referral_id=referral_id)

        # Step 3: Check for already submitted recommendation
        if referral.status == ReferralStatus.COMPLETED:
            log.warning(
                "Recommendation already submitted",
                existing_recommendation=referral.recommendation.value if referral.recommendation else None,
            )
            raise RecommendationAlreadySubmittedError(
                referral_id=referral_id,
                existing_recommendation=referral.recommendation.value if referral.recommendation else None,
            )

        # Step 4: Validate referral state
        if referral.status != ReferralStatus.IN_REVIEW:
            log.warning(
                "Referral not in IN_REVIEW state",
                current_status=referral.status.value,
            )
            raise ReferralNotInReviewError(
                referral_id=referral_id,
                current_status=referral.status.value,
            )

        # Step 5: Authorization check (NFR-5.2)
        if referral.assigned_knight_id is None:
            log.warning("Referral has no assigned Knight")
            raise UnauthorizedRecommendationError(
                referral_id=referral_id,
                requester_id=requester_id,
            )

        if requester_id != referral.assigned_knight_id:
            log.warning(
                "Unauthorized recommendation attempt",
                assigned_knight_id=str(referral.assigned_knight_id),
            )
            raise UnauthorizedRecommendationError(
                referral_id=referral_id,
                requester_id=requester_id,
                assigned_knight_id=referral.assigned_knight_id,
            )

        # Step 6: Update referral with recommendation
        completed_at = datetime.now(timezone.utc)
        updated_referral = referral.with_recommendation(
            recommendation=recommendation,
            rationale=trimmed_rationale,
            completed_at=completed_at,
        )

        # Step 7: Generate witness hash (CT-12)
        witness_content = self._build_witness_content(
            referral_id=referral_id,
            petition_id=referral.petition_id,
            knight_id=requester_id,
            recommendation=recommendation,
            rationale=trimmed_rationale,
            completed_at=completed_at,
        )
        witness_hash = await self._hash_service.compute_hash(witness_content)

        log.debug(
            "Witness hash generated",
            witness_hash=witness_hash,
        )

        # Step 8: Update the referral with recommendation
        await self._referral_repo.update(updated_referral)
        log.info("Referral updated with recommendation")

        # Step 9: Emit ReferralCompletedEvent (CT-12)
        event = ReferralCompletedEvent(
            event_id=uuid4(),
            referral_id=referral_id,
            petition_id=referral.petition_id,
            knight_id=requester_id,
            recommendation=recommendation.value,
            rationale=trimmed_rationale,
            completed_at=completed_at,
            witness_hash=witness_hash,
        )
        await self._event_writer.write(event.to_dict())
        log.info("ReferralCompletedEvent emitted")

        # Step 10: Cancel deadline job (NFR-3.4 idempotent)
        await self._cancel_deadline_job(referral_id, log)

        # Step 11: Route petition based on recommendation
        await self._route_petition(
            referral=updated_referral,
            recommendation=recommendation,
            rationale=trimmed_rationale,
            log=log,
        )

        log.info(
            "Recommendation submission completed",
            recommendation=recommendation.value,
            witness_hash=witness_hash,
        )

        return updated_referral

    def _build_witness_content(
        self,
        referral_id: UUID,
        petition_id: UUID,
        knight_id: UUID,
        recommendation: ReferralRecommendation,
        rationale: str,
        completed_at: datetime,
    ) -> str:
        """Build content string for witness hash generation.

        Creates a deterministic string representation of the recommendation
        for hashing per CT-12 witnessing requirements.

        Args:
            referral_id: UUID of the referral.
            petition_id: UUID of the petition.
            knight_id: UUID of the Knight submitting.
            recommendation: The Knight's recommendation.
            rationale: The Knight's rationale.
            completed_at: When the recommendation was submitted.

        Returns:
            Deterministic string for hashing.
        """
        parts = [
            f"referral_id:{referral_id}",
            f"petition_id:{petition_id}",
            f"knight_id:{knight_id}",
            f"recommendation:{recommendation.value}",
            f"rationale:{rationale}",
            f"completed_at:{completed_at.isoformat()}",
            f"schema_version:{REFERRAL_EVENT_SCHEMA_VERSION}",
        ]
        return "|".join(parts)

    async def _cancel_deadline_job(
        self,
        referral_id: UUID,
        log: "structlog.BoundLogger",  # type: ignore[name-defined]
    ) -> None:
        """Cancel the deadline timeout job (NFR-3.4).

        Per NFR-3.4, we need to ensure deadline jobs are cancelled when
        a recommendation is submitted. This is idempotent - if the job
        has already executed or been cancelled, this is a no-op.

        Args:
            referral_id: UUID of the referral.
            log: Structured logger with context.
        """
        job_id = f"referral-deadline-{referral_id}"
        try:
            await self._job_scheduler.cancel(job_id)
            log.info("Deadline job cancelled", job_id=job_id)
        except Exception as e:
            # Job may have already executed or been cancelled - this is OK
            log.debug(
                "Deadline job cancellation skipped (may not exist)",
                job_id=job_id,
                reason=str(e),
            )

    async def _route_petition(
        self,
        referral: Referral,
        recommendation: ReferralRecommendation,
        rationale: str,
        log: "structlog.BoundLogger",  # type: ignore[name-defined]
    ) -> None:
        """Route petition based on Knight's recommendation.

        ACKNOWLEDGE: Routes to Epic 3 acknowledgment execution.
        ESCALATE: Routes to Epic 6 King escalation queue (stub).

        Args:
            referral: The completed referral.
            recommendation: The Knight's recommendation.
            rationale: The Knight's rationale.
            log: Structured logger with context.
        """
        if recommendation == ReferralRecommendation.ACKNOWLEDGE:
            await self._route_to_acknowledgment(referral, rationale, log)
        elif recommendation == ReferralRecommendation.ESCALATE:
            await self._route_to_escalation(referral, rationale, log)
        else:
            log.error(
                "Unknown recommendation type",
                recommendation=recommendation.value,
            )

    async def _route_to_acknowledgment(
        self,
        referral: Referral,
        rationale: str,
        log: "structlog.BoundLogger",  # type: ignore[name-defined]
    ) -> None:
        """Route petition to acknowledgment execution (Epic 3).

        Per Story 4.4 AC-4, when recommendation is ACKNOWLEDGE,
        we call AcknowledgmentExecutionService with reason code KNIGHT_REFERRAL.

        Args:
            referral: The completed referral.
            rationale: The Knight's rationale.
            log: Structured logger with context.
        """
        log.info(
            "Routing petition to acknowledgment",
            petition_id=str(referral.petition_id),
            reason_code=AcknowledgmentReasonCode.KNIGHT_REFERRAL.value,
        )

        if self._acknowledgment_service is None:
            log.warning(
                "Acknowledgment service not configured - routing deferred",
                petition_id=str(referral.petition_id),
            )
            return

        # Call acknowledgment execution with KNIGHT_REFERRAL reason
        # Note: acknowledging_archon_ids is empty since this is Knight decision
        # The Knight's rationale is passed through
        try:
            await self._acknowledgment_service.execute(
                petition_id=referral.petition_id,
                reason_code=AcknowledgmentReasonCode.KNIGHT_REFERRAL,
                acknowledging_archon_ids=[],  # No archons - Knight decision
                rationale=rationale,
            )
            log.info(
                "Petition acknowledged via KNIGHT_REFERRAL",
                petition_id=str(referral.petition_id),
            )
        except Exception as e:
            log.error(
                "Failed to execute acknowledgment routing",
                petition_id=str(referral.petition_id),
                error=str(e),
            )
            # Re-raise to propagate error - this is a constitutional operation
            raise

    async def _route_to_escalation(
        self,
        referral: Referral,
        rationale: str,
        log: "structlog.BoundLogger",  # type: ignore[name-defined]
    ) -> None:
        """Route petition to King escalation queue (Epic 6 stub).

        Per Story 4.4 AC-4, when recommendation is ESCALATE,
        we queue the petition for King review. This is a stub until Epic 6.

        Args:
            referral: The completed referral.
            rationale: The Knight's rationale for escalation.
            log: Structured logger with context.
        """
        log.info(
            "Routing petition to escalation (Epic 6 stub)",
            petition_id=str(referral.petition_id),
            knight_rationale=rationale[:50] + "..." if len(rationale) > 50 else rationale,
        )

        # TODO (Epic 6): Implement actual King escalation queue
        # For now, log the escalation intent
        log.warning(
            "King escalation not yet implemented - petition queued for later processing",
            petition_id=str(referral.petition_id),
            referral_id=str(referral.referral_id),
            knight_id=str(referral.assigned_knight_id),
        )
