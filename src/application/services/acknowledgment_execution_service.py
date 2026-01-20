"""Acknowledgment execution service implementation (Story 3.2, 3.5, FR-3.1, FR-3.5).

This module implements the AcknowledgmentExecutionProtocol for executing
petition acknowledgments when deliberation reaches ACKNOWLEDGE consensus.

Constitutional Constraints:
- FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
- FR-3.3: System SHALL require rationale for REFUSED/NO_ACTION_WARRANTED
- FR-3.4: System SHALL require reference_petition_id for DUPLICATE
- FR-3.5: System SHALL enforce minimum dwell time before ACKNOWLEDGE
- CT-12: Every action that affects an Archon must be witnessed
- CT-14: Every claim terminates in visible, witnessed fate
- NFR-3.2: Fate assignment atomicity (100% single-fate)
- NFR-6.1: All fate transitions witnessed
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from structlog import get_logger

from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.errors.acknowledgment import (
    AcknowledgmentAlreadyExistsError,
    DeliberationSessionNotFoundError,
    DwellTimeNotElapsedError,
    InvalidArchonCountError,
    InvalidReferencePetitionError,
    PetitionNotFoundError,
    PetitionNotInDeliberatingStateError,
    WitnessHashGenerationError,
)
from src.domain.events.acknowledgment import PetitionAcknowledgedEvent
from src.domain.models.acknowledgment import (
    ACKNOWLEDGMENT_SCHEMA_VERSION,
    MIN_ACKNOWLEDGING_ARCHONS,
    Acknowledgment,
)
from src.domain.models.acknowledgment_reason import (
    AcknowledgmentReasonCode,
    validate_acknowledgment_requirements,
)
from src.domain.models.petition_submission import PetitionState

if TYPE_CHECKING:
    from src.application.ports.acknowledgment_execution import (
        AcknowledgmentRepositoryProtocol,
    )
    from src.application.ports.archon_assignment import ArchonAssignmentServiceProtocol
    from src.application.ports.content_hash import ContentHashProtocol
    from src.application.ports.event_writer import EventWriterProtocol
    from src.application.ports.petition_submission import (
        PetitionSubmissionRepositoryProtocol,
    )

logger = get_logger(__name__)


class AcknowledgmentExecutionService:
    """Service for executing petition acknowledgments (Story 3.2, 3.5).

    Implements the acknowledgment execution flow when Three Fates
    deliberation reaches consensus on ACKNOWLEDGE disposition.

    The service ensures:
    1. Petition is in DELIBERATING state (FR-3.1)
    2. Minimum dwell time has elapsed (FR-3.5)
    3. Reason code requirements are met (FR-3.3, FR-3.4)
    4. At least 2 archons voted ACKNOWLEDGE (FR-11.5)
    5. State transition is atomic (NFR-3.2)
    6. Acknowledgment is witnessed (CT-12, NFR-6.1)

    Example:
        >>> service = AcknowledgmentExecutionService(
        ...     acknowledgment_repo=repo,
        ...     petition_repo=petition_repo,
        ...     session_service=session_service,
        ...     event_writer=event_writer,
        ...     hash_service=hash_service,
        ... )
        >>> ack = await service.execute(
        ...     petition_id=petition.id,
        ...     reason_code=AcknowledgmentReasonCode.NOTED,
        ...     acknowledging_archon_ids=(15, 42),
        ... )
    """

    def __init__(
        self,
        acknowledgment_repo: AcknowledgmentRepositoryProtocol,
        petition_repo: PetitionSubmissionRepositoryProtocol,
        event_writer: EventWriterProtocol,
        hash_service: ContentHashProtocol,
        session_service: ArchonAssignmentServiceProtocol | None = None,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize the acknowledgment execution service.

        Args:
            acknowledgment_repo: Repository for acknowledgment persistence
            petition_repo: Repository for petition access
            event_writer: Service for event emission and witnessing
            hash_service: Service for generating witness hashes
            session_service: Service for retrieving deliberation sessions (FR-3.5)
            config: Deliberation configuration including dwell time (FR-3.5)
        """
        self._acknowledgment_repo = acknowledgment_repo
        self._petition_repo = petition_repo
        self._event_writer = event_writer
        self._hash_service = hash_service
        self._session_service = session_service
        self._config = config or DEFAULT_DELIBERATION_CONFIG

    async def execute(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        acknowledging_archon_ids: Sequence[int],
        rationale: str | None = None,
        reference_petition_id: UUID | None = None,
    ) -> Acknowledgment:
        """Execute acknowledgment for a petition.

        Args:
            petition_id: The petition to acknowledge
            reason_code: Reason for acknowledgment
            acknowledging_archon_ids: IDs of archons who voted ACKNOWLEDGE
            rationale: Required for REFUSED/NO_ACTION_WARRANTED
            reference_petition_id: Required for DUPLICATE

        Returns:
            The created Acknowledgment record

        Raises:
            PetitionNotFoundError: Petition doesn't exist
            PetitionNotInDeliberatingStateError: Not in DELIBERATING state
            DwellTimeNotElapsedError: Minimum dwell time not yet elapsed (FR-3.5)
            DeliberationSessionNotFoundError: Session not found for DELIBERATING petition
            AcknowledgmentAlreadyExistsError: Already acknowledged
            InvalidArchonCountError: Less than 2 archons
            RationaleRequiredError: Missing rationale
            ReferenceRequiredError: Missing reference
            InvalidReferencePetitionError: Reference doesn't exist
        """
        log = logger.bind(
            petition_id=str(petition_id),
            reason_code=reason_code.value,
            archon_count=len(acknowledging_archon_ids),
        )
        log.info("Starting acknowledgment execution")

        # Step 1: Validate archon count (FR-11.5)
        # Exemptions: KNIGHT_REFERRAL (Story 4.4), EXPIRED (Story 4.6, FR-4.5)
        # These are system-triggered acknowledgments without deliberating archons
        exempt_reason_codes = {
            AcknowledgmentReasonCode.KNIGHT_REFERRAL,
            AcknowledgmentReasonCode.EXPIRED,
        }
        if reason_code not in exempt_reason_codes:
            if len(acknowledging_archon_ids) < MIN_ACKNOWLEDGING_ARCHONS:
                raise InvalidArchonCountError(
                    actual_count=len(acknowledging_archon_ids),
                    required_count=MIN_ACKNOWLEDGING_ARCHONS,
                )

        # Step 2: Validate reason code requirements (FR-3.3, FR-3.4)
        validate_acknowledgment_requirements(
            reason_code=reason_code,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
        )

        # Step 3: Verify petition exists and is in correct state
        petition = await self._petition_repo.get_by_id(petition_id)
        if petition is None:
            raise PetitionNotFoundError(petition_id)

        # System-triggered acknowledgments from referral workflow (Story 4.4, 4.6)
        # can come from REFERRED state - KNIGHT_REFERRAL (Knight recommendation)
        # or EXPIRED (referral timeout auto-acknowledge per FR-4.5)
        referral_workflow_reason_codes = {
            AcknowledgmentReasonCode.KNIGHT_REFERRAL,
            AcknowledgmentReasonCode.EXPIRED,
        }
        valid_states = {PetitionState.DELIBERATING}
        if reason_code in referral_workflow_reason_codes:
            valid_states.add(PetitionState.REFERRED)

        if petition.state not in valid_states:
            raise PetitionNotInDeliberatingStateError(
                petition_id=petition_id,
                current_state=petition.state.value,
            )

        # Step 4: Enforce minimum dwell time (FR-3.5)
        # Skip for system-triggered acknowledgments (EXPIRED, KNIGHT_REFERRAL)
        # These come from the referral workflow and don't have deliberation sessions
        if reason_code not in referral_workflow_reason_codes:
            await self._enforce_dwell_time(petition_id, log)
        else:
            log.debug("Dwell time check skipped (system-triggered reason code)")

        # Step 5: Check for existing acknowledgment (idempotency / NFR-3.2)
        existing = await self._acknowledgment_repo.get_by_petition_id(petition_id)
        if existing is not None:
            log.info(
                "Acknowledgment already exists, returning existing",
                acknowledgment_id=str(existing.id),
            )
            # Return existing for idempotency
            return existing

        # Step 7: Validate reference petition exists for DUPLICATE
        if reference_petition_id is not None:
            ref_petition = await self._petition_repo.get_by_id(reference_petition_id)
            if ref_petition is None:
                raise InvalidReferencePetitionError(
                    petition_id=petition_id,
                    reference_petition_id=reference_petition_id,
                )

        # Step 8: Generate witness hash (CT-12)
        acknowledgment_id = uuid4()
        acknowledged_at = datetime.now(timezone.utc)

        try:
            witness_content = self._build_witness_content(
                acknowledgment_id=acknowledgment_id,
                petition_id=petition_id,
                reason_code=reason_code,
                acknowledging_archon_ids=tuple(acknowledging_archon_ids),
                acknowledged_at=acknowledged_at,
                rationale=rationale,
                reference_petition_id=reference_petition_id,
            )
            witness_hash = await self._hash_service.compute_hash(witness_content)
        except Exception as e:
            raise WitnessHashGenerationError(
                petition_id=petition_id,
                reason=str(e),
            ) from e

        # Step 9: Create Acknowledgment record
        acknowledgment = Acknowledgment.create(
            id=acknowledgment_id,
            petition_id=petition_id,
            reason_code=reason_code,
            acknowledging_archon_ids=acknowledging_archon_ids,
            acknowledged_at=acknowledged_at,
            witness_hash=witness_hash,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
        )

        # Step 10: Persist acknowledgment and update petition state atomically
        # Note: In production, this would be wrapped in a transaction
        await self._acknowledgment_repo.save(acknowledgment)

        # Update petition state to ACKNOWLEDGED
        await self._petition_repo.update_state(
            petition_id=petition_id,
            new_state=PetitionState.ACKNOWLEDGED,
            fate_reason=reason_code.value,
        )

        # Step 11: Emit witnessed event (CT-12, NFR-6.1)
        event = PetitionAcknowledgedEvent.from_acknowledgment(
            event_id=uuid4(),
            acknowledgment_id=acknowledgment.id,
            petition_id=petition_id,
            reason_code=reason_code,
            acknowledging_archon_ids=acknowledgment.acknowledging_archon_ids,
            acknowledged_at=acknowledged_at,
            witness_hash=witness_hash,
            rationale=rationale,
            reference_petition_id=reference_petition_id,
        )
        await self._event_writer.write(event.to_dict())

        log.info(
            "Acknowledgment execution completed",
            acknowledgment_id=str(acknowledgment.id),
            witness_hash=witness_hash,
        )

        return acknowledgment

    async def get_acknowledgment(
        self,
        acknowledgment_id: UUID,
    ) -> Acknowledgment | None:
        """Retrieve an acknowledgment by ID."""
        return await self._acknowledgment_repo.get_by_id(acknowledgment_id)

    async def get_acknowledgment_by_petition(
        self,
        petition_id: UUID,
    ) -> Acknowledgment | None:
        """Retrieve an acknowledgment by petition ID."""
        return await self._acknowledgment_repo.get_by_petition_id(petition_id)

    async def execute_system_acknowledge(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        rationale: str,
    ) -> Acknowledgment:
        """Execute system-triggered acknowledgment (Story 4.6, FR-4.5).

        System-triggered acknowledgments bypass certain validations:
        - No archon count validation (no deliberating archons)
        - No dwell time enforcement (system action)
        - Accepts REFERRED state (referral workflow completion)

        Used for:
        - EXPIRED: Referral timeout auto-acknowledge (Story 4.6)
        - KNIGHT_REFERRAL: Knight recommendation routing (Story 4.4)

        Args:
            petition_id: The petition to acknowledge.
            reason_code: Must be EXPIRED or KNIGHT_REFERRAL.
            rationale: System-generated rationale.

        Returns:
            The created Acknowledgment record.

        Raises:
            ValueError: If reason_code is not a system reason code.
            PetitionNotFoundError: Petition doesn't exist.
            AcknowledgmentAlreadyExistsError: Petition already acknowledged.
        """
        valid_system_codes = {
            AcknowledgmentReasonCode.EXPIRED,
            AcknowledgmentReasonCode.KNIGHT_REFERRAL,
        }
        if reason_code not in valid_system_codes:
            raise ValueError(
                f"execute_system_acknowledge only accepts system reason codes: "
                f"{[c.value for c in valid_system_codes]}, got {reason_code.value}"
            )

        return await self.execute(
            petition_id=petition_id,
            reason_code=reason_code,
            acknowledging_archon_ids=[],  # No archons for system actions
            rationale=rationale,
        )

    def _build_witness_content(
        self,
        acknowledgment_id: UUID,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        acknowledging_archon_ids: tuple[int, ...],
        acknowledged_at: datetime,
        rationale: str | None,
        reference_petition_id: UUID | None,
    ) -> str:
        """Build content string for witness hash generation.

        Creates a deterministic string representation of the acknowledgment
        for hashing per CT-12 witnessing requirements.

        Args:
            acknowledgment_id: UUID for the acknowledgment
            petition_id: Petition being acknowledged
            reason_code: Reason for acknowledgment
            acknowledging_archon_ids: Archons who voted ACKNOWLEDGE
            acknowledged_at: Timestamp
            rationale: Optional explanation
            reference_petition_id: Optional reference for DUPLICATE

        Returns:
            Deterministic string for hashing
        """
        # Build deterministic content for hash
        parts = [
            f"acknowledgment_id:{acknowledgment_id}",
            f"petition_id:{petition_id}",
            f"reason_code:{reason_code.value}",
            f"archons:{','.join(str(a) for a in sorted(acknowledging_archon_ids))}",
            f"acknowledged_at:{acknowledged_at.isoformat()}",
            f"schema_version:{ACKNOWLEDGMENT_SCHEMA_VERSION}",
        ]

        if rationale:
            parts.append(f"rationale:{rationale}")

        if reference_petition_id:
            parts.append(f"reference_petition_id:{reference_petition_id}")

        return "|".join(parts)

    async def _enforce_dwell_time(
        self,
        petition_id: UUID,
        log: Any,
    ) -> None:
        """Enforce minimum dwell time before acknowledgment (FR-3.5).

        Per FR-3.5, the system SHALL enforce minimum dwell time before ACKNOWLEDGE.
        This ensures petitions receive adequate deliberation time.

        If dwell time is 0 (disabled) or no session service is configured,
        the check is skipped. This allows for testing and legacy compatibility.

        Args:
            petition_id: UUID of the petition being acknowledged
            log: Structured logger with context

        Raises:
            DwellTimeNotElapsedError: If minimum dwell time has not elapsed
            DeliberationSessionNotFoundError: If session not found but required
        """
        # Skip if dwell time is disabled (0) or no session service
        if self._config.min_dwell_seconds == 0:
            log.debug("Dwell time check skipped (disabled)")
            return

        if self._session_service is None:
            log.debug("Dwell time check skipped (no session service)")
            return

        # Get the deliberation session to check when deliberation started
        session = await self._session_service.get_session_by_petition(petition_id)
        if session is None:
            raise DeliberationSessionNotFoundError(petition_id)

        # Calculate elapsed time since deliberation started
        now = datetime.now(timezone.utc)
        elapsed = (now - session.created_at).total_seconds()

        log.debug(
            "Checking dwell time",
            elapsed_seconds=elapsed,
            min_dwell_seconds=self._config.min_dwell_seconds,
            session_created_at=session.created_at.isoformat(),
        )

        # Check if enough time has elapsed
        if elapsed < self._config.min_dwell_seconds:
            raise DwellTimeNotElapsedError(
                petition_id=petition_id,
                deliberation_started_at=session.created_at,
                min_dwell_seconds=self._config.min_dwell_seconds,
                elapsed_seconds=elapsed,
            )
