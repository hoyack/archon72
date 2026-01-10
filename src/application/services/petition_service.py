"""Petition service for external observer petitions (Story 7.2, FR39).

This module implements the petition capability that allows external observers
to petition for cessation consideration with 100+ co-signers.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST (for writes)
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
- CT-13: Integrity outranks availability -> Reads allowed during halt
- FR39: External observers can petition with 100+ co-signers

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every WRITE operation
2. WITNESS EVERYTHING - All petition events must be witnessed
3. FAIL LOUD - Never silently swallow signature errors
4. READS DURING HALT - Petition queries work during halt (CT-13)
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from src.application.ports.cessation_agenda_repository import (
    CessationAgendaRepositoryProtocol,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.petition_repository import PetitionRepositoryProtocol
from src.application.ports.signature_verifier import SignatureVerifierProtocol
from src.application.services.event_writer_service import EventWriterService
from src.domain.errors import SystemHaltedError
from src.domain.errors.petition import (
    DuplicateCosignatureError,
    InvalidSignatureError,
    PetitionClosedError,
    PetitionNotFoundError,
)
from src.domain.events.cessation_agenda import (
    CESSATION_AGENDA_PLACEMENT_EVENT_TYPE,
    AgendaTriggerType,
    CessationAgendaPlacementEventPayload,
)
from src.domain.events.petition import (
    PETITION_COSIGNED_EVENT_TYPE,
    PETITION_CREATED_EVENT_TYPE,
    PETITION_SYSTEM_AGENT_ID,
    PETITION_THRESHOLD_COSIGNERS,
    PETITION_THRESHOLD_MET_EVENT_TYPE,
    PetitionCoSignedEventPayload,
    PetitionCreatedEventPayload,
    PetitionStatus,
    PetitionThresholdMetEventPayload,
)
from src.domain.models.petition import CoSigner, Petition

log = structlog.get_logger()


@dataclass(frozen=True)
class SubmitPetitionResult:
    """Result of a petition submission.

    Attributes:
        petition_id: The unique identifier for the created petition.
        created_at: When the petition was created.
    """

    petition_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class CosignPetitionResult:
    """Result of co-signing a petition.

    Attributes:
        petition_id: The petition that was co-signed.
        cosigner_sequence: The sequence number of this co-signer.
        cosigner_count: Total co-signers after this signature.
        threshold_met: Whether the threshold was reached.
        agenda_placement_id: ID of agenda placement (if threshold met).
    """

    petition_id: UUID
    cosigner_sequence: int
    cosigner_count: int
    threshold_met: bool
    agenda_placement_id: Optional[UUID]


class PetitionService:
    """Service for external observer petitions (FR39).

    This service provides:
    - Petition submission with signature verification
    - Co-signing with duplicate detection
    - Automatic agenda placement at 100 co-signers
    - Public petition queries (reads allowed during halt)

    Constitutional Constraints:
    - CT-11: HALT CHECK FIRST for all write operations
    - CT-12: All events MUST be witnessed via EventWriterService
    - CT-13: Read operations allowed during halt
    - AC5: Idempotent agenda placement (no duplicates)

    Developer Golden Rules:
    1. HALT CHECK FIRST - Writes check halt, reads don't
    2. WITNESS EVERYTHING - All petition events witnessed
    3. FAIL LOUD - Invalid signatures raise errors
    4. READS DURING HALT - Queries work during halt
    """

    def __init__(
        self,
        petition_repo: PetitionRepositoryProtocol,
        signature_verifier: SignatureVerifierProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
        cessation_agenda_repo: CessationAgendaRepositoryProtocol,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            petition_repo: Repository for petition storage.
            signature_verifier: Service for Ed25519 signature verification.
            event_writer: Service for writing witnessed events.
            halt_checker: Service for checking halt state.
            cessation_agenda_repo: Repository for agenda placement.
        """
        self._petition_repo = petition_repo
        self._signature_verifier = signature_verifier
        self._event_writer = event_writer
        self._halt_checker = halt_checker
        self._cessation_agenda_repo = cessation_agenda_repo

    async def _check_halt_state(self) -> None:
        """Check halt state and raise if halted (CT-11).

        Constitutional Constraint (CT-11):
        Silent failure destroys legitimacy. We must fail loud
        if the system is halted.

        Raises:
            SystemHaltedError: If the system is in halted state.
        """
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical("petition_operation_rejected_system_halted", halt_reason=reason)
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

    async def submit_petition(
        self,
        petition_content: str,
        submitter_public_key: str,
        submitter_signature: str,
    ) -> SubmitPetitionResult:
        """Submit a new petition (FR39, AC1).

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST
        - CT-12: Event MUST be witnessed
        - AC4: Signature must be verified

        Args:
            petition_content: Reason for cessation concern.
            submitter_public_key: Hex-encoded Ed25519 public key.
            submitter_signature: Hex-encoded Ed25519 signature.

        Returns:
            SubmitPetitionResult with petition_id and created_at.

        Raises:
            SystemHaltedError: If system is halted (AC7).
            InvalidSignatureError: If signature verification fails (AC4).
        """
        # HALT CHECK FIRST (CT-11, AC7)
        await self._check_halt_state()

        log.info(
            "submitting_petition",
            public_key=submitter_public_key[:16] + "...",
            content_length=len(petition_content),
        )

        # Verify signature (AC4)
        content_bytes = petition_content.encode("utf-8")
        is_valid = await self._signature_verifier.verify_signature(
            public_key=submitter_public_key,
            signature=submitter_signature,
            content=content_bytes,
        )
        if not is_valid:
            log.warning(
                "petition_signature_invalid",
                public_key=submitter_public_key[:16] + "...",
            )
            raise InvalidSignatureError(
                submitter_public_key,
                "Submitter signature verification failed",
            )

        # Create petition
        petition_id = uuid4()
        created_timestamp = datetime.now(timezone.utc)

        petition = Petition(
            petition_id=petition_id,
            submitter_public_key=submitter_public_key,
            submitter_signature=submitter_signature,
            petition_content=petition_content,
            created_timestamp=created_timestamp,
            status=PetitionStatus.OPEN,
        )

        # Save petition
        await self._petition_repo.save_petition(petition)

        # Create and write witnessed event (CT-12)
        payload = PetitionCreatedEventPayload(
            petition_id=petition_id,
            submitter_public_key=submitter_public_key,
            submitter_signature=submitter_signature,
            petition_content=petition_content,
            created_timestamp=created_timestamp,
        )

        await self._event_writer.write_event(
            event_type=PETITION_CREATED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=PETITION_SYSTEM_AGENT_ID,
            local_timestamp=created_timestamp,
        )

        log.info(
            "petition_submitted",
            petition_id=str(petition_id),
            public_key=submitter_public_key[:16] + "...",
        )

        return SubmitPetitionResult(
            petition_id=petition_id,
            created_at=created_timestamp,
        )

    async def cosign_petition(
        self,
        petition_id: UUID,
        cosigner_public_key: str,
        cosigner_signature: str,
    ) -> CosignPetitionResult:
        """Co-sign an existing petition (FR39, AC2, AC3).

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST
        - CT-12: Event MUST be witnessed
        - AC2: Duplicate co-signatures rejected
        - AC3: Threshold triggers agenda placement
        - AC4: Signature must be verified
        - AC5: Idempotent agenda placement

        Args:
            petition_id: The petition to co-sign.
            cosigner_public_key: Hex-encoded Ed25519 public key.
            cosigner_signature: Hex-encoded Ed25519 signature.

        Returns:
            CosignPetitionResult with co-signer info and threshold status.

        Raises:
            SystemHaltedError: If system is halted (AC7).
            PetitionNotFoundError: If petition doesn't exist.
            DuplicateCosignatureError: If already co-signed (AC2).
            PetitionClosedError: If petition is not open.
            InvalidSignatureError: If signature verification fails (AC4).
        """
        # HALT CHECK FIRST (CT-11, AC7)
        await self._check_halt_state()

        log.info(
            "cosigning_petition",
            petition_id=str(petition_id),
            public_key=cosigner_public_key[:16] + "...",
        )

        # Get petition
        petition = await self._petition_repo.get_petition(petition_id)
        if petition is None:
            raise PetitionNotFoundError(str(petition_id))

        # Check petition is open (allow co-signing even after threshold_met per AC5)
        if petition.status == PetitionStatus.CLOSED:
            raise PetitionClosedError(str(petition_id), petition.status.value)

        # Check for duplicate (AC2)
        if petition.has_cosigned(cosigner_public_key):
            raise DuplicateCosignatureError(str(petition_id), cosigner_public_key)

        # Verify signature (AC4)
        content_bytes = petition.canonical_content_bytes()
        is_valid = await self._signature_verifier.verify_signature(
            public_key=cosigner_public_key,
            signature=cosigner_signature,
            content=content_bytes,
        )
        if not is_valid:
            log.warning(
                "cosigner_signature_invalid",
                petition_id=str(petition_id),
                public_key=cosigner_public_key[:16] + "...",
            )
            raise InvalidSignatureError(
                cosigner_public_key,
                "Co-signer signature verification failed",
            )

        # Add co-signer
        cosigned_timestamp = datetime.now(timezone.utc)
        cosigner_sequence = petition.cosigner_count + 1

        cosigner = CoSigner(
            public_key=cosigner_public_key,
            signature=cosigner_signature,
            signed_at=cosigned_timestamp,
            sequence=cosigner_sequence,
        )

        updated_petition = await self._petition_repo.add_cosigner(petition_id, cosigner)

        # Write co-signed event (CT-12)
        cosigned_payload = PetitionCoSignedEventPayload(
            petition_id=petition_id,
            cosigner_public_key=cosigner_public_key,
            cosigner_signature=cosigner_signature,
            cosigned_timestamp=cosigned_timestamp,
            cosigner_sequence=cosigner_sequence,
        )

        await self._event_writer.write_event(
            event_type=PETITION_COSIGNED_EVENT_TYPE,
            payload=cosigned_payload.to_dict(),
            agent_id=PETITION_SYSTEM_AGENT_ID,
            local_timestamp=cosigned_timestamp,
        )

        log.info(
            "petition_cosigned",
            petition_id=str(petition_id),
            cosigner_sequence=cosigner_sequence,
            total_cosigners=updated_petition.cosigner_count,
        )

        # Check threshold (AC3)
        threshold_met = False
        agenda_placement_id: Optional[UUID] = None

        if updated_petition.cosigner_count >= PETITION_THRESHOLD_COSIGNERS:
            # Check if threshold already triggered (AC5 idempotency)
            if updated_petition.threshold_met_at is None:
                agenda_placement_id = await self._trigger_threshold_met(updated_petition)
                threshold_met = True
            else:
                log.info(
                    "threshold_already_met",
                    petition_id=str(petition_id),
                    threshold_met_at=updated_petition.threshold_met_at.isoformat(),
                )

        return CosignPetitionResult(
            petition_id=petition_id,
            cosigner_sequence=cosigner_sequence,
            cosigner_count=updated_petition.cosigner_count,
            threshold_met=threshold_met,
            agenda_placement_id=agenda_placement_id,
        )

    async def _trigger_threshold_met(self, petition: Petition) -> UUID:
        """Trigger threshold met events and agenda placement (AC3).

        Constitutional Constraint (CT-12):
        All events MUST be witnessed via EventWriterService.

        Args:
            petition: The petition that reached threshold.

        Returns:
            The agenda placement ID.
        """
        trigger_timestamp = datetime.now(timezone.utc)
        placement_id = uuid4()

        log.info(
            "petition_threshold_met",
            petition_id=str(petition.petition_id),
            cosigner_count=petition.cosigner_count,
            threshold=PETITION_THRESHOLD_COSIGNERS,
        )

        # Get all co-signer public keys
        cosigner_keys = tuple(c.public_key for c in petition.cosigners)

        # Write threshold met event (CT-12)
        threshold_payload = PetitionThresholdMetEventPayload(
            petition_id=petition.petition_id,
            threshold=PETITION_THRESHOLD_COSIGNERS,
            final_cosigner_count=petition.cosigner_count,
            trigger_timestamp=trigger_timestamp,
            cosigner_public_keys=cosigner_keys,
            agenda_placement_reason=f"FR39: External observer petition reached {PETITION_THRESHOLD_COSIGNERS} co-signers",
        )

        await self._event_writer.write_event(
            event_type=PETITION_THRESHOLD_MET_EVENT_TYPE,
            payload=threshold_payload.to_dict(),
            agent_id=PETITION_SYSTEM_AGENT_ID,
            local_timestamp=trigger_timestamp,
        )

        # Update petition status
        await self._petition_repo.update_status(
            petition.petition_id,
            PetitionStatus.THRESHOLD_MET,
            threshold_met_at=trigger_timestamp.isoformat(),
        )

        # Create agenda placement event (integrates with Story 7.1)
        agenda_payload = CessationAgendaPlacementEventPayload(
            placement_id=placement_id,
            trigger_type=AgendaTriggerType.ROLLING_WINDOW,  # Reusing enum, conceptually "petition"
            trigger_timestamp=trigger_timestamp,
            failure_count=0,  # Not failure-based
            window_days=0,  # Not window-based
            consecutive=False,
            failure_event_ids=(),  # Not failure-based
            agenda_placement_reason=f"FR39: External observer petition {petition.petition_id} reached {PETITION_THRESHOLD_COSIGNERS} co-signers",
        )

        await self._event_writer.write_event(
            event_type=CESSATION_AGENDA_PLACEMENT_EVENT_TYPE,
            payload=agenda_payload.to_dict(),
            agent_id=PETITION_SYSTEM_AGENT_ID,
            local_timestamp=trigger_timestamp,
        )

        # Save to cessation agenda repository
        await self._cessation_agenda_repo.save_agenda_placement(agenda_payload)

        log.info(
            "cessation_placed_on_agenda_via_petition",
            placement_id=str(placement_id),
            petition_id=str(petition.petition_id),
            cosigner_count=petition.cosigner_count,
        )

        return placement_id

    async def get_petition(self, petition_id: UUID) -> Optional[Petition]:
        """Get a petition by ID (AC8, CT-13).

        Constitutional Constraint (CT-13):
        Reads are allowed during halt.

        Args:
            petition_id: The petition ID to retrieve.

        Returns:
            The petition if found, None otherwise.
        """
        # NO halt check - reads allowed during halt (CT-13, AC7)
        return await self._petition_repo.get_petition(petition_id)

    async def list_open_petitions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Petition], int]:
        """List all open petitions with pagination (AC8, FR44).

        Constitutional Constraints:
        - CT-13: Reads allowed during halt
        - FR44: Public access without authentication

        Args:
            limit: Maximum number of petitions to return.
            offset: Number of petitions to skip.

        Returns:
            Tuple of (list of petitions, total count).
        """
        # NO halt check - reads allowed during halt (CT-13, AC7)
        return await self._petition_repo.list_open_petitions(limit=limit, offset=offset)
