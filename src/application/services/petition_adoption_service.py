"""Petition Adoption Service (Story 6.3, FR-5.5, FR-5.6, FR-5.7).

This service handles the adoption of escalated petitions by Kings,
creating Motions with immutable provenance tracking.

Constitutional Constraints:
- FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
- FR-5.6: Adoption SHALL consume promotion budget (H1 compliance) [P0]
- FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
- NFR-6.2: Adoption provenance immutability
- NFR-8.3: Atomic budget consumption with Motion creation
- CT-11: Fail loud - never silently swallow errors
- CT-12: All events require witnessing
- CT-13: Halt check first pattern
- RULING-3: Realm-scoped data access (Kings only adopt from their realm)
- ADR-P4: Budget consumption prevents budget laundering (PRE-3 mitigation)

Key Architectural Pattern:
1. HALT CHECK FIRST (CT-13)
2. Validate petition exists and is ESCALATED
3. Validate realm authorization (RULING-3)
4. Check promotion budget (H1 compliance, FR-5.6)
5. Consume budget BEFORE creating Motion (ADR-P4, atomic with creation)
6. Create Motion via application layer (similar to PromotionService pattern)
7. Update petition with adoption back-reference (NFR-6.2)
8. Emit PetitionAdopted event (CT-12)

Budget Consumption Pattern (from PromotionService):
- Budget consumed BEFORE Motion creation
- If Motion creation fails, budget is lost (by design per ADR-P4)
- This prevents budget laundering attacks (PRE-3)
- Budget store implementations ensure durability (NFR-4.5)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import structlog

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.petition_adoption import (
    AdoptionRequest,
    AdoptionResult,
    InsufficientBudgetException,
    PetitionAdoptionProtocol,
    PetitionNotEscalatedException,
    RealmMismatchException,
)
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.ports.promotion_budget_store import PromotionBudgetStore
from src.application.services.event_writer_service import EventWriterService
from src.domain.events.petition import PetitionAdoptedEventPayload
from src.domain.models.motion_seed import RealmAssignment
from src.domain.models.petition_submission import PetitionState


@dataclass
class MotionFromAdoption:
    """A Motion created from petition adoption (parallel to MotionFromPromotion).

    This is an application-layer construct (not domain primitive) that represents
    a Motion created by adopting a petition. It contains all necessary data for
    the Motion system without modifying core Motion domain model.

    Attributes:
        motion_id: UUID of the created Motion
        title: Motion title (from adoption request)
        intent: Normative intent (from motion_body in request)
        rationale: King's adoption rationale
        sponsor_id: King UUID who adopted
        created_at: When Motion was created
        source_petition_ref: UUID of source petition (immutable provenance, FR-5.7)
        realm_assignment: Realm where Motion was created
    """

    motion_id: UUID
    title: str
    intent: str
    rationale: str
    sponsor_id: UUID
    created_at: datetime
    source_petition_ref: UUID
    realm_assignment: RealmAssignment


class PetitionAdoptionService(PetitionAdoptionProtocol):
    """Service for adopting escalated petitions and creating Motions.

    This service orchestrates the entire adoption workflow:
    1. Validation (petition state, realm authorization)
    2. Budget consumption (atomic, durable)
    3. Motion creation
    4. Petition update (adoption back-reference)
    5. Event emission (witnessed)

    Attributes:
        petition_repo: Repository for petition storage operations
        budget_store: Store for tracking King promotion budgets
        halt_checker: Checker for system halt state (CT-13)
        event_writer: Service for writing witnessed events (CT-12)
        logger: Structured logger for constitutional compliance
    """

    def __init__(
        self,
        petition_repo: PetitionSubmissionRepositoryProtocol,
        budget_store: PromotionBudgetStore,
        halt_checker: HaltChecker,
        event_writer: EventWriterService,
    ) -> None:
        """Initialize the Petition Adoption Service.

        Args:
            petition_repo: Repository for petition storage operations
            budget_store: Store for tracking King promotion budgets
            halt_checker: Checker for system halt state (CT-13)
            event_writer: Service for writing witnessed events (CT-12)
        """
        self.petition_repo = petition_repo
        self.budget_store = budget_store
        self.halt_checker = halt_checker
        self.event_writer = event_writer
        self.logger = structlog.get_logger()

    async def adopt_petition(self, request: AdoptionRequest) -> AdoptionResult:
        """Adopt an escalated petition and create a Motion.

        This is the main entry point for petition adoption. It performs all
        validation, budget consumption, Motion creation, and event emission.

        Constitutional Constraints:
        - CT-13: Halt check first (before any writes)
        - FR-5.5: King can adopt petition to create Motion
        - FR-5.6: Adoption consumes promotion budget
        - FR-5.7: Motion includes immutable source_petition_ref
        - RULING-3: Realm authorization (King's realm must match petition's realm)
        - ADR-P4: Budget consumed before Motion created (prevents laundering)

        Args:
            request: Adoption request containing petition ID, King ID, and Motion details

        Returns:
            AdoptionResult with success status, motion_id, and budget consumed

        Raises:
            SystemHaltedException: If system is in halted state (CT-13)
            PetitionNotEscalatedException: If petition is not in ESCALATED state
            RealmMismatchException: If King's realm doesn't match petition's realm
            InsufficientBudgetException: If King has insufficient promotion budget
        """
        # CT-13: HALT CHECK FIRST - no writes during halt
        if self.halt_checker.is_halted():
            self.logger.error(
                "adoption_blocked_system_halted",
                petition_id=str(request.petition_id),
                king_id=str(request.king_id),
            )
            raise SystemHaltedException("System is halted, adoption not permitted")

        # Log adoption attempt for audit trail
        self.logger.info(
            "adoption_attempt",
            petition_id=str(request.petition_id),
            king_id=str(request.king_id),
            realm_id=request.realm_id,
        )

        # Step 1: Validate petition exists and is ESCALATED
        petition = await self.petition_repo.get(request.petition_id)
        if petition is None:
            self.logger.warning(
                "adoption_failed_petition_not_found",
                petition_id=str(request.petition_id),
            )
            return AdoptionResult(
                success=False,
                errors=["PETITION_NOT_FOUND"],
                budget_consumed=0,
            )

        if petition.state != PetitionState.ESCALATED:
            self.logger.warning(
                "adoption_failed_not_escalated",
                petition_id=str(request.petition_id),
                current_state=petition.state.value,
            )
            raise PetitionNotEscalatedException(
                petition_id=request.petition_id,
                current_state=petition.state.value,
            )

        # Step 2: Validate realm authorization (RULING-3)
        if petition.escalated_to_realm != request.realm_id:
            self.logger.warning(
                "adoption_failed_realm_mismatch",
                petition_id=str(request.petition_id),
                king_realm=request.realm_id,
                petition_realm=petition.escalated_to_realm,
            )
            raise RealmMismatchException(
                king_realm=request.realm_id,
                petition_realm=petition.escalated_to_realm or "unknown",
            )

        # Step 3: Check promotion budget (H1 compliance, FR-5.6)
        # Use current cycle (for now, simplified - production would have cycle management)
        cycle_id = "2026-Q1"  # TODO: Replace with actual cycle management
        king_id_str = str(request.king_id)

        if not self.budget_store.can_promote(king_id_str, cycle_id, count=1):
            self.logger.warning(
                "adoption_failed_insufficient_budget",
                petition_id=str(request.petition_id),
                king_id=king_id_str,
                cycle_id=cycle_id,
            )
            raise InsufficientBudgetException(
                king_id=request.king_id,
                cycle_id=cycle_id,
                remaining=0,  # TODO: Get actual remaining budget
            )

        # Step 4: Consume budget ATOMICALLY (ADR-P4, NFR-8.3)
        # Budget is consumed BEFORE Motion creation
        # If Motion creation fails after this, budget is lost (by design)
        # This prevents budget laundering attacks (PRE-3)
        new_used = self.budget_store.consume(king_id_str, cycle_id, count=1)
        self.logger.info(
            "adoption_budget_consumed",
            petition_id=str(request.petition_id),
            king_id=king_id_str,
            cycle_id=cycle_id,
            new_used=new_used,
        )

        # Step 5: Create Motion from adoption
        motion = self._create_motion_from_adoption(
            petition_id=request.petition_id,
            king_id=request.king_id,
            realm_id=request.realm_id,
            motion_title=request.motion_title,
            motion_body=request.motion_body,
            adoption_rationale=request.adoption_rationale,
        )

        self.logger.info(
            "motion_created_from_adoption",
            motion_id=str(motion.motion_id),
            petition_id=str(request.petition_id),
            sponsor_id=str(motion.sponsor_id),
        )

        # Step 6: Update petition with adoption back-reference (NFR-6.2)
        updated_petition = await self.petition_repo.mark_adopted(
            submission_id=request.petition_id,
            motion_id=motion.motion_id,
            king_id=request.king_id,
        )

        self.logger.info(
            "petition_marked_adopted",
            petition_id=str(request.petition_id),
            motion_id=str(motion.motion_id),
        )

        # Step 7: Emit PetitionAdopted event (CT-12 - witnessed)
        event_payload = PetitionAdoptedEventPayload(
            petition_id=request.petition_id,
            motion_id=motion.motion_id,
            sponsor_king_id=request.king_id,
            adoption_rationale=request.adoption_rationale,
            adopted_at=motion.created_at,
            budget_consumed=1,
            realm_id=request.realm_id,
        )

        self.event_writer.write_event(
            event_type="petition.adoption.adopted",
            event_payload=event_payload.to_dict(),
            agent_id=str(request.king_id),
        )

        self.logger.info(
            "adoption_succeeded",
            petition_id=str(request.petition_id),
            motion_id=str(motion.motion_id),
            king_id=str(request.king_id),
            budget_consumed=1,
        )

        # Step 8: Return success result
        return AdoptionResult(
            success=True,
            motion_id=motion.motion_id,
            errors=[],
            budget_consumed=1,
        )

    def _create_motion_from_adoption(
        self,
        petition_id: UUID,
        king_id: UUID,
        realm_id: str,
        motion_title: str,
        motion_body: str,
        adoption_rationale: str,
    ) -> MotionFromAdoption:
        """Create Motion from petition adoption (internal helper).

        This method creates the application-layer Motion construct that
        will be passed to the Motion system for formal introduction.

        Args:
            petition_id: Source petition UUID
            king_id: King who adopted (sponsor)
            realm_id: Realm where Motion is being created
            motion_title: Title for the Motion
            motion_body: Intent/body for the Motion
            adoption_rationale: King's rationale for adoption

        Returns:
            MotionFromAdoption with all necessary Motion data
        """
        motion_id = uuid4()
        created_at = datetime.now(timezone.utc)

        # Create realm assignment for the Motion
        realm_assignment = RealmAssignment(
            primary_realm=realm_id,
            assigned_king_id=str(king_id),
            requires_collaboration=False,
            collaborating_realms=[],
        )

        return MotionFromAdoption(
            motion_id=motion_id,
            title=motion_title,
            intent=motion_body,  # motion_body becomes the normative intent
            rationale=adoption_rationale,
            sponsor_id=king_id,
            created_at=created_at,
            source_petition_ref=petition_id,
            realm_assignment=realm_assignment,
        )


class SystemHaltedException(Exception):
    """Raised when operation is attempted during system halt (CT-13)."""

    pass
