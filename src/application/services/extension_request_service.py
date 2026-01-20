"""Extension request service implementation (Story 4.5, FR-4.4).

This module implements the ExtensionRequestProtocol for processing
Knight deadline extension requests.

Constitutional Constraints:
- FR-4.4: Knight SHALL be able to request extension (max 2) [P1]
- NFR-4.4: Referral deadline persistence: Survives scheduler restart
- NFR-5.2: Authorization: Only assigned Knight can request extension
- CT-12: Every action that affects an Archon must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before writes
2. AUTHORIZATION FIRST - Verify Knight assignment before extension
3. WITNESS EVERYTHING - All extensions require witness hash
4. FAIL LOUD - Raise appropriate errors for invalid requests
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.extension_request import (
    ExtensionRequest,
    ExtensionResult,
)
from src.domain.errors.referral import (
    ExtensionReasonRequiredError,
    InvalidReferralStateError,
    MaxExtensionsReachedError,
    NotAssignedKnightError,
    ReferralNotFoundError,
)
from src.domain.events.referral import (
    REFERRAL_EVENT_SCHEMA_VERSION,
    ReferralExtendedEvent,
)
from src.domain.models.referral import (
    REFERRAL_DEFAULT_CYCLE_DURATION,
    REFERRAL_MAX_EXTENSIONS,
    Referral,
    ReferralStatus,
)

if TYPE_CHECKING:
    from src.application.ports.content_hash import ContentHashProtocol
    from src.application.ports.event_writer import EventWriterProtocol
    from src.application.ports.job_scheduler import JobSchedulerProtocol
    from src.application.ports.referral_execution import ReferralRepositoryProtocol

logger = get_logger(__name__)

# Minimum reason length for extension requests
MIN_REASON_LENGTH: int = 10

# Extension duration in cycles (FR-4.4 - 1 cycle per extension)
EXTENSION_DURATION_CYCLES: int = 1


class ExtensionRequestService:
    """Service for processing Knight deadline extension requests (Story 4.5).

    Implements the extension request flow when a Knight needs additional
    time to review a referred petition.

    The service ensures:
    1. Requester is the assigned Knight (NFR-5.2)
    2. Referral is in ASSIGNED or IN_REVIEW state
    3. Maximum extensions (2) haven't been reached (FR-4.4)
    4. Reason meets minimum requirements
    5. Extension is witnessed (CT-12)
    6. Deadline job is rescheduled (NFR-4.4)

    Example:
        >>> service = ExtensionRequestService(
        ...     referral_repo=repo,
        ...     event_writer=event_writer,
        ...     hash_service=hash_service,
        ...     job_scheduler=job_scheduler,
        ... )
        >>> result = await service.request_extension(
        ...     ExtensionRequest(
        ...         referral_id=referral_id,
        ...         knight_id=knight_id,
        ...         reason="Complex petition requires additional research",
        ...     )
        ... )
    """

    def __init__(
        self,
        referral_repo: ReferralRepositoryProtocol,
        event_writer: EventWriterProtocol,
        hash_service: ContentHashProtocol,
        job_scheduler: JobSchedulerProtocol,
        extension_duration: timedelta | None = None,
        max_extensions: int = REFERRAL_MAX_EXTENSIONS,
        min_reason_length: int = MIN_REASON_LENGTH,
    ) -> None:
        """Initialize the extension request service.

        Args:
            referral_repo: Repository for referral access and persistence.
            event_writer: Service for event emission and witnessing.
            hash_service: Service for generating witness hashes.
            job_scheduler: Service for rescheduling deadline jobs.
            extension_duration: Duration to extend per request (default: 1 week).
            max_extensions: Maximum number of extensions allowed (default: 2).
            min_reason_length: Minimum length for extension reason (default: 10).
        """
        self._referral_repo = referral_repo
        self._event_writer = event_writer
        self._hash_service = hash_service
        self._job_scheduler = job_scheduler
        self._extension_duration = extension_duration or (
            EXTENSION_DURATION_CYCLES * REFERRAL_DEFAULT_CYCLE_DURATION
        )
        self._max_extensions = max_extensions
        self._min_reason_length = min_reason_length

    async def request_extension(
        self,
        request: ExtensionRequest,
    ) -> ExtensionResult:
        """Process a deadline extension request.

        Performs authorization checks, validates the extension is allowed,
        extends the deadline, reschedules the job, and emits the event.

        Authorization Requirements (NFR-5.2):
        - request.knight_id MUST match the assigned_knight_id on the referral
        - Referral MUST be in ASSIGNED or IN_REVIEW state

        Extension Requirements (FR-4.4):
        - extensions_granted MUST be < 2
        - reason MUST be at least 10 characters

        Args:
            request: The extension request details.

        Returns:
            ExtensionResult with new deadline and witness hash.

        Raises:
            ReferralNotFoundError: Referral doesn't exist.
            NotAssignedKnightError: Requester is not the assigned Knight.
            InvalidReferralStateError: Referral is not in valid state.
            MaxExtensionsReachedError: Maximum extensions already granted.
            ExtensionReasonRequiredError: Reason is missing or too short.
        """
        log = logger.bind(
            referral_id=str(request.referral_id),
            knight_id=str(request.knight_id),
        )
        log.info("Processing extension request")

        # Step 1: Validate reason
        trimmed_reason = request.reason.strip() if request.reason else ""
        if len(trimmed_reason) < self._min_reason_length:
            log.warning(
                "Reason validation failed",
                provided_length=len(trimmed_reason),
                min_length=self._min_reason_length,
            )
            raise ExtensionReasonRequiredError(
                referral_id=request.referral_id,
                provided_length=len(trimmed_reason),
                min_length=self._min_reason_length,
            )

        # Step 2: Retrieve the referral
        referral = await self._referral_repo.get_by_id(request.referral_id)
        if referral is None:
            log.warning("Referral not found")
            raise ReferralNotFoundError(referral_id=request.referral_id)

        # Step 3: Check for maximum extensions
        if referral.extensions_granted >= self._max_extensions:
            log.warning(
                "Maximum extensions reached",
                extensions_granted=referral.extensions_granted,
                max_extensions=self._max_extensions,
            )
            raise MaxExtensionsReachedError(
                referral_id=request.referral_id,
                extensions_granted=referral.extensions_granted,
            )

        # Step 4: Validate referral state
        valid_states = [ReferralStatus.ASSIGNED, ReferralStatus.IN_REVIEW]
        if referral.status not in valid_states:
            log.warning(
                "Referral not in valid state for extension",
                current_status=referral.status.value,
                valid_states=[s.value for s in valid_states],
            )
            raise InvalidReferralStateError(
                referral_id=request.referral_id,
                current_status=referral.status.value,
                required_statuses=[s.value for s in valid_states],
                operation="extension request",
            )

        # Step 5: Authorization check (NFR-5.2)
        if referral.assigned_knight_id is None:
            log.warning("Referral has no assigned Knight")
            raise NotAssignedKnightError(
                referral_id=request.referral_id,
                requester_id=request.knight_id,
            )

        if request.knight_id != referral.assigned_knight_id:
            log.warning(
                "Unauthorized extension attempt",
                assigned_knight_id=str(referral.assigned_knight_id),
            )
            raise NotAssignedKnightError(
                referral_id=request.referral_id,
                requester_id=request.knight_id,
                assigned_knight_id=referral.assigned_knight_id,
            )

        # Step 6: Calculate new deadline
        previous_deadline = referral.deadline
        new_deadline = previous_deadline + self._extension_duration
        extended_at = datetime.now(timezone.utc)

        # Step 7: Update referral with extension
        updated_referral = referral.with_extension(new_deadline)
        extensions_granted = updated_referral.extensions_granted

        # Step 8: Generate witness hash (CT-12)
        witness_content = self._build_witness_content(
            referral_id=request.referral_id,
            petition_id=referral.petition_id,
            knight_id=request.knight_id,
            previous_deadline=previous_deadline,
            new_deadline=new_deadline,
            extensions_granted=extensions_granted,
            reason=trimmed_reason,
            extended_at=extended_at,
        )
        witness_hash = await self._hash_service.compute_hash(witness_content)

        log.debug(
            "Witness hash generated",
            witness_hash=witness_hash,
        )

        # Step 9: Persist the updated referral
        await self._referral_repo.update(updated_referral)
        log.info("Referral updated with extension")

        # Step 10: Emit ReferralExtendedEvent (CT-12)
        event = ReferralExtendedEvent(
            event_id=uuid4(),
            referral_id=request.referral_id,
            petition_id=referral.petition_id,
            knight_id=request.knight_id,
            previous_deadline=previous_deadline,
            new_deadline=new_deadline,
            extensions_granted=extensions_granted,
            reason=trimmed_reason,
            witness_hash=witness_hash,
            emitted_at=extended_at,
        )
        await self._event_writer.write(event.to_dict())
        log.info("ReferralExtendedEvent emitted")

        # Step 11: Reschedule deadline job (NFR-4.4)
        await self._reschedule_deadline_job(
            referral_id=request.referral_id,
            new_deadline=new_deadline,
            log=log,
        )

        log.info(
            "Extension request completed",
            previous_deadline=previous_deadline.isoformat(),
            new_deadline=new_deadline.isoformat(),
            extensions_granted=extensions_granted,
            witness_hash=witness_hash,
        )

        return ExtensionResult(
            referral_id=request.referral_id,
            petition_id=referral.petition_id,
            knight_id=request.knight_id,
            previous_deadline=previous_deadline,
            new_deadline=new_deadline,
            extensions_granted=extensions_granted,
            reason=trimmed_reason,
            witness_hash=witness_hash,
            extended_at=extended_at,
        )

    async def get_extension_count(self, referral_id: UUID) -> int:
        """Get the number of extensions granted for a referral.

        Args:
            referral_id: The referral to check.

        Returns:
            Number of extensions granted (0, 1, or 2).

        Raises:
            ReferralNotFoundError: If referral doesn't exist.
        """
        referral = await self._referral_repo.get_by_id(referral_id)
        if referral is None:
            raise ReferralNotFoundError(referral_id=referral_id)
        return referral.extensions_granted

    async def can_extend(self, referral_id: UUID) -> bool:
        """Check if a referral can be extended.

        A referral can be extended if:
        - It exists
        - Status is ASSIGNED or IN_REVIEW
        - extensions_granted < MAX_EXTENSIONS (2)

        Args:
            referral_id: The referral to check.

        Returns:
            True if extension is possible, False otherwise.

        Raises:
            ReferralNotFoundError: If referral doesn't exist.
        """
        referral = await self._referral_repo.get_by_id(referral_id)
        if referral is None:
            raise ReferralNotFoundError(referral_id=referral_id)
        return referral.can_extend()

    def _build_witness_content(
        self,
        referral_id: UUID,
        petition_id: UUID,
        knight_id: UUID,
        previous_deadline: datetime,
        new_deadline: datetime,
        extensions_granted: int,
        reason: str,
        extended_at: datetime,
    ) -> str:
        """Build content string for witness hash generation.

        Creates a deterministic string representation of the extension
        for hashing per CT-12 witnessing requirements.

        Args:
            referral_id: UUID of the referral.
            petition_id: UUID of the petition.
            knight_id: UUID of the Knight requesting.
            previous_deadline: Deadline before extension.
            new_deadline: Deadline after extension.
            extensions_granted: Total extensions granted.
            reason: Reason for extension.
            extended_at: When the extension was processed.

        Returns:
            Deterministic string for hashing.
        """
        parts = [
            f"referral_id:{referral_id}",
            f"petition_id:{petition_id}",
            f"knight_id:{knight_id}",
            f"previous_deadline:{previous_deadline.isoformat()}",
            f"new_deadline:{new_deadline.isoformat()}",
            f"extensions_granted:{extensions_granted}",
            f"reason:{reason}",
            f"extended_at:{extended_at.isoformat()}",
            f"schema_version:{REFERRAL_EVENT_SCHEMA_VERSION}",
        ]
        return "|".join(parts)

    async def _reschedule_deadline_job(
        self,
        referral_id: UUID,
        new_deadline: datetime,
        log: "structlog.BoundLogger",  # type: ignore[name-defined]
    ) -> None:
        """Reschedule the deadline timeout job (NFR-4.4).

        Per NFR-4.4, referral deadline persistence must survive scheduler restart.
        We cancel the existing job and schedule a new one with the updated deadline.

        Args:
            referral_id: UUID of the referral.
            new_deadline: The new deadline to schedule.
            log: Structured logger with context.
        """
        job_id = f"referral-deadline-{referral_id}"

        # Cancel existing job (idempotent)
        try:
            await self._job_scheduler.cancel(job_id)
            log.debug("Existing deadline job cancelled", job_id=job_id)
        except Exception as e:
            log.debug(
                "Existing deadline job cancellation skipped (may not exist)",
                job_id=job_id,
                reason=str(e),
            )

        # Schedule new job with updated deadline
        try:
            await self._job_scheduler.schedule(
                job_id=job_id,
                run_at=new_deadline,
                handler="referral_timeout_handler",
                payload={"referral_id": str(referral_id)},
            )
            log.info(
                "Deadline job rescheduled",
                job_id=job_id,
                new_deadline=new_deadline.isoformat(),
            )
        except Exception as e:
            log.error(
                "Failed to reschedule deadline job",
                job_id=job_id,
                error=str(e),
            )
            # Don't raise - the extension itself succeeded
            # The job will be re-scheduled on next system startup per NFR-4.4
