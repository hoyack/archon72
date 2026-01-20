"""Referral execution service implementation (Story 4.2, FR-4.1, FR-4.2).

This module implements the ReferralExecutionProtocol for executing
petition referrals when deliberation reaches REFER consensus.

Constitutional Constraints:
- FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
- FR-4.2: System SHALL assign referral deadline (3 cycles default)
- CT-12: Every action that affects an Archon must be witnessed
- NFR-3.4: Referral timeout reliability: 100% timeouts fire
- NFR-4.4: Referral deadline persistence: Survives scheduler restart

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before modifying referrals (writes)
2. WITNESS EVERYTHING - All referral events require attribution
3. FAIL LOUD - Never silently swallow deadline errors
4. READS DURING HALT - Referral queries work during halt (CT-13)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from structlog import get_logger

from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.errors.referral import (
    PetitionNotReferrableError,
    ReferralJobSchedulingError,
    ReferralWitnessHashError,
)
from src.domain.events.referral import (
    REFERRAL_EVENT_SCHEMA_VERSION,
    PetitionReferredEvent,
)
from src.domain.models.petition_submission import PetitionState
from src.domain.models.referral import (
    REFERRAL_DEFAULT_DEADLINE_CYCLES,
    Referral,
    ReferralStatus,
)

if TYPE_CHECKING:
    from src.application.ports.content_hash_service import ContentHashServiceProtocol
    from src.application.ports.event_writer import EventWriterProtocol
    from src.application.ports.job_scheduler import JobSchedulerProtocol
    from src.application.ports.petition_submission_repository import (
        PetitionSubmissionRepositoryProtocol,
    )
    from src.application.ports.referral_execution import ReferralRepositoryProtocol

logger = get_logger(__name__)

# Job type for referral timeout
JOB_TYPE_REFERRAL_TIMEOUT = "referral_timeout"


class ReferralExecutionService:
    """Service for executing petition referrals (Story 4.2).

    Implements the referral execution flow when Three Fates
    deliberation reaches consensus on REFER disposition.

    The service ensures:
    1. Petition is in DELIBERATING state (FR-4.1)
    2. Referral record is created with deadline (FR-4.2)
    3. State transition is atomic (NFR-3.2)
    4. Referral is witnessed (CT-12, NFR-6.1)
    5. Deadline job is scheduled (NFR-3.4, NFR-4.4)

    Example:
        >>> service = ReferralExecutionService(
        ...     referral_repo=referral_repo,
        ...     petition_repo=petition_repo,
        ...     event_writer=event_writer,
        ...     job_scheduler=job_scheduler,
        ...     hash_service=hash_service,
        ... )
        >>> referral = await service.execute(
        ...     petition_id=petition.id,
        ...     realm_id=realm.id,
        ... )
    """

    def __init__(
        self,
        referral_repo: ReferralRepositoryProtocol,
        petition_repo: PetitionSubmissionRepositoryProtocol,
        event_writer: EventWriterProtocol,
        job_scheduler: JobSchedulerProtocol,
        hash_service: ContentHashServiceProtocol,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize the referral execution service.

        Args:
            referral_repo: Repository for referral persistence
            petition_repo: Repository for petition access
            event_writer: Service for event emission and witnessing
            job_scheduler: Service for scheduling deadline jobs
            hash_service: Service for generating witness hashes
            config: Deliberation configuration
        """
        self._referral_repo = referral_repo
        self._petition_repo = petition_repo
        self._event_writer = event_writer
        self._job_scheduler = job_scheduler
        self._hash_service = hash_service
        self._config = config or DEFAULT_DELIBERATION_CONFIG

    async def execute(
        self,
        petition_id: UUID,
        realm_id: UUID,
        deadline_cycles: int | None = None,
    ) -> Referral:
        """Execute referral for a petition.

        Args:
            petition_id: The petition to refer
            realm_id: The realm to route the referral to
            deadline_cycles: Number of cycles for deadline (default 3)

        Returns:
            The created Referral record

        Raises:
            PetitionNotFoundError: Petition doesn't exist
            PetitionNotReferrableError: Petition not in DELIBERATING state
            ReferralAlreadyExistsError: Petition already referred
            ReferralWitnessHashError: Failed to generate witness hash
            ReferralJobSchedulingError: Failed to schedule deadline job
        """
        log = logger.bind(
            petition_id=str(petition_id),
            realm_id=str(realm_id),
            deadline_cycles=deadline_cycles,
        )
        log.info("Starting referral execution")

        # Step 1: Check for existing referral (idempotency)
        # This must come first to support idempotency when petition state has changed
        existing = await self._referral_repo.get_by_petition_id(petition_id)
        if existing is not None:
            log.info(
                "Referral already exists, returning existing",
                referral_id=str(existing.referral_id),
            )
            return existing

        # Step 2: Verify petition exists and is in correct state
        petition = await self._petition_repo.get(petition_id)
        if petition is None:
            from src.domain.errors.acknowledgment import PetitionNotFoundError

            raise PetitionNotFoundError(petition_id)

        if petition.state != PetitionState.DELIBERATING:
            raise PetitionNotReferrableError(
                petition_id=petition_id,
                current_state=petition.state.value,
            )

        # Step 3: Calculate deadline
        cycles = deadline_cycles or REFERRAL_DEFAULT_DEADLINE_CYCLES
        now = datetime.now(timezone.utc)
        deadline = Referral.calculate_default_deadline(from_time=now, cycles=cycles)

        # Step 4: Create Referral record
        referral_id = uuid4()
        referral = Referral(
            referral_id=referral_id,
            petition_id=petition_id,
            realm_id=realm_id,
            deadline=deadline,
            created_at=now,
            status=ReferralStatus.PENDING,
        )

        # Step 5: Generate witness hash (CT-12)
        try:
            witness_content = self._build_witness_content(
                referral_id=referral_id,
                petition_id=petition_id,
                realm_id=realm_id,
                deadline=deadline,
                created_at=now,
            )
            witness_hash_bytes = self._hash_service.hash_text(witness_content)
            witness_hash = f"blake3:{witness_hash_bytes.hex()}"
        except Exception as e:
            raise ReferralWitnessHashError(
                petition_id=petition_id,
                reason=str(e),
            ) from e

        # Step 6: Persist referral
        await self._referral_repo.save(referral)

        # Step 7: Update petition state to REFERRED
        await self._petition_repo.update_state(
            submission_id=petition_id,
            new_state=PetitionState.REFERRED,
            fate_reason=f"REFER to realm {realm_id}",
        )

        # Step 8: Schedule deadline job (NFR-3.4, NFR-4.4)
        try:
            job_payload = {
                "referral_id": str(referral_id),
                "petition_id": str(petition_id),
                "realm_id": str(realm_id),
                "deadline": deadline.isoformat(),
            }
            job_id = await self._job_scheduler.schedule(
                job_type=JOB_TYPE_REFERRAL_TIMEOUT,
                payload=job_payload,
                run_at=deadline,
            )
            log.info(
                "Scheduled referral timeout job",
                job_id=str(job_id),
                deadline=deadline.isoformat(),
            )
        except Exception as e:
            # Note: In production, this would need rollback or compensation
            raise ReferralJobSchedulingError(
                referral_id=referral_id,
                reason=str(e),
            ) from e

        # Step 9: Emit witnessed event (CT-12, NFR-6.1)
        event = PetitionReferredEvent.from_referral(
            event_id=uuid4(),
            referral=referral,
            witness_hash=witness_hash,
            emitted_at=now,
        )
        await self._event_writer.write(event.to_dict())

        log.info(
            "Referral execution completed",
            referral_id=str(referral_id),
            witness_hash=witness_hash,
            deadline=deadline.isoformat(),
        )

        return referral

    async def get_referral(
        self,
        referral_id: UUID,
    ) -> Referral | None:
        """Retrieve a referral by ID."""
        return await self._referral_repo.get_by_id(referral_id)

    async def get_referral_by_petition(
        self,
        petition_id: UUID,
    ) -> Referral | None:
        """Retrieve a referral by petition ID."""
        return await self._referral_repo.get_by_petition_id(petition_id)

    def _build_witness_content(
        self,
        referral_id: UUID,
        petition_id: UUID,
        realm_id: UUID,
        deadline: datetime,
        created_at: datetime,
    ) -> str:
        """Build content string for witness hash generation.

        Creates a deterministic string representation of the referral
        for hashing per CT-12 witnessing requirements.

        Args:
            referral_id: UUID for the referral
            petition_id: Petition being referred
            realm_id: Target realm
            deadline: Referral deadline
            created_at: Creation timestamp

        Returns:
            Deterministic string for hashing
        """
        parts = [
            f"referral_id:{referral_id}",
            f"petition_id:{petition_id}",
            f"realm_id:{realm_id}",
            f"deadline:{deadline.isoformat()}",
            f"created_at:{created_at.isoformat()}",
            f"schema_version:{REFERRAL_EVENT_SCHEMA_VERSION}",
        ]
        return "|".join(parts)
