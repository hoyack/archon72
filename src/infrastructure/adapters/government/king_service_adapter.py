"""King Service Adapter (Legislative Branch).

This module implements the KingServiceProtocol for motion introduction
and intent validation.

Per Government PRD FR-GOV-5: Kings may introduce motions and define WHAT (intent only).
Per Government PRD FR-GOV-6: Kings may NOT define tasks, timelines, tools, execution
methods, supervise execution, or judge outcomes.
"""

from uuid import UUID

from structlog import get_logger

from src.application.ports.king_service import (
    IntentValidationResult,
    KingServiceProtocol,
    Motion,
    MotionIntroductionRequest,
    MotionIntroductionResult,
    MotionStatus,
    RankViolationError,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatementType,
)
from src.application.ports.permission_enforcer import (
    GovernanceAction,
    PermissionContext,
    PermissionEnforcerProtocol,
)
from src.application.services.intent_validator import IntentValidator

logger = get_logger(__name__)


class KingServiceAdapter(KingServiceProtocol):
    """Implementation of King-rank legislative functions.

    This service allows King-rank Archons to introduce motions that define
    WHAT (intent), while strictly validating that they cannot define HOW
    (execution details).

    All operations are witnessed by Knight per FR-GOV-20.
    """

    def __init__(
        self,
        permission_enforcer: PermissionEnforcerProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        intent_validator: IntentValidator | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the King Service.

        Args:
            permission_enforcer: Permission enforcement (optional for testing)
            knight_witness: Knight witness for recording events (optional)
            intent_validator: Validator for intent-only content
            verbose: Enable verbose logging
        """
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness
        self._intent_validator = intent_validator or IntentValidator()
        self._verbose = verbose

        # In-memory storage for motions (would be repository in production)
        self._motions: dict[UUID, Motion] = {}

        if self._verbose:
            logger.debug("king_service_initialized")

    async def introduce_motion(
        self,
        request: MotionIntroductionRequest,
    ) -> MotionIntroductionResult:
        """Introduce a new motion defining WHAT (intent only).

        Per FR-GOV-5: Kings may introduce motions and define WHAT (intent only).

        Args:
            request: Motion introduction request with intent

        Returns:
            MotionIntroductionResult with success/failure and motion

        Raises:
            RankViolationError: If the Archon is not King-rank
        """
        if self._verbose:
            logger.debug(
                "motion_introduction_requested",
                introduced_by=request.introduced_by,
                title=request.title,
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource="motion",
                action_details={"title": request.title},
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.introduced_by,
                action=GovernanceAction.INTRODUCE_MOTION,
                context=context,
            )

            if not permission_result.allowed:
                # Witness the violation
                await self._witness_violation(
                    archon_id=request.introduced_by,
                    violation_type="rank_violation",
                    description=f"Attempted to introduce motion without King rank: {permission_result.violation_reason}",
                )

                raise RankViolationError(
                    archon_id=request.introduced_by,
                    action="introduce_motion",
                    reason=permission_result.violation_reason or "Not authorized",
                    prd_reference="FR-GOV-5",
                )

        # Validate intent-only content
        validation_result = await self.validate_intent_only(request.intent)

        if not validation_result.is_valid:
            # Witness the violation - King tried to define HOW
            await self._witness_violation(
                archon_id=request.introduced_by,
                violation_type="execution_detail_violation",
                description=(
                    f"King attempted to define execution details (HOW): "
                    f"{validation_result.violation_count} violation(s) found"
                ),
                evidence={
                    "violations": [v.to_dict() for v in validation_result.violations],
                },
            )

            if self._verbose:
                logger.warning(
                    "motion_rejected_execution_details",
                    introduced_by=request.introduced_by,
                    violation_count=validation_result.violation_count,
                )

            return MotionIntroductionResult(
                success=False,
                validation_result=validation_result,
                error="Motion contains execution details (HOW). Kings may only define WHAT (intent).",
            )

        # Create the motion
        motion = Motion.create(
            introduced_by=request.introduced_by,
            title=request.title,
            intent=request.intent,
            rationale=request.rationale,
            session_ref=request.session_ref,
        )

        # Store the motion
        self._motions[motion.motion_id] = motion

        # Witness the introduction
        await self._observe_event(
            event_type="motion_introduced",
            description=f"King {request.introduced_by} introduced motion: {request.title}",
            data={
                "motion_id": str(motion.motion_id),
                "introduced_by": request.introduced_by,
                "title": request.title,
            },
        )

        if self._verbose:
            logger.info(
                "motion_introduced",
                motion_id=str(motion.motion_id),
                introduced_by=request.introduced_by,
                title=request.title,
            )

        return MotionIntroductionResult(
            success=True,
            motion=motion,
            validation_result=validation_result,
        )

    async def validate_intent_only(
        self,
        motion_text: str,
    ) -> IntentValidationResult:
        """Validate that motion text contains only WHAT, not HOW.

        Per FR-GOV-6, this detects and rejects:
        - Task lists
        - Timelines
        - Tool specifications
        - Resource allocations
        - Execution methods
        - Supervision directions

        Args:
            motion_text: The intent text to validate

        Returns:
            IntentValidationResult with violations if any execution details found
        """
        result = self._intent_validator.validate(motion_text)

        if self._verbose:
            logger.debug(
                "intent_validated",
                is_valid=result.is_valid,
                violation_count=result.violation_count,
            )

        return result

    async def get_motion(self, motion_id: UUID) -> Motion | None:
        """Retrieve a motion by ID.

        Args:
            motion_id: UUID of the motion

        Returns:
            Motion if found, None otherwise
        """
        return self._motions.get(motion_id)

    async def get_motions_by_status(
        self,
        status: MotionStatus,
    ) -> list[Motion]:
        """Get all motions with a specific status.

        Args:
            status: The status to filter by

        Returns:
            List of motions with that status
        """
        return [m for m in self._motions.values() if m.status == status]

    async def get_motions_by_king(
        self,
        king_archon_id: str,
    ) -> list[Motion]:
        """Get all motions introduced by a specific King.

        Args:
            king_archon_id: The Archon ID of the King

        Returns:
            List of motions introduced by that King
        """
        return [m for m in self._motions.values() if m.introduced_by == king_archon_id]

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    async def _witness_violation(
        self,
        archon_id: str,
        violation_type: str,
        description: str,
        evidence: dict | None = None,
    ) -> None:
        """Record a violation via Knight Witness.

        Args:
            archon_id: The Archon who committed the violation
            violation_type: Type of violation
            description: Description of what happened
            evidence: Additional evidence
        """
        if not self._knight_witness:
            return

        # Map violation type to WitnessStatementType
        statement_type = WitnessStatementType.ROLE_VIOLATION
        if "execution" in violation_type.lower():
            statement_type = WitnessStatementType.BRANCH_VIOLATION

        record = ViolationRecord(
            statement_type=statement_type,
            description=description,
            roles_involved=(archon_id,),
            evidence=evidence or {},
            prd_reference="FR-GOV-6",
        )

        await self._knight_witness.record_violation(record)

    async def _observe_event(
        self,
        event_type: str,
        description: str,
        data: dict | None = None,
    ) -> None:
        """Record an event via Knight Witness.

        Args:
            event_type: Type of event
            description: Description of the event
            data: Additional event data
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            event_type=event_type,
            source_service="king_service",
            data=data or {},
        )

        await self._knight_witness.observe(description, context)


def create_king_service(
    permission_enforcer: PermissionEnforcerProtocol | None = None,
    knight_witness: KnightWitnessProtocol | None = None,
    verbose: bool = False,
) -> KingServiceAdapter:
    """Factory function to create a KingServiceAdapter.

    Args:
        permission_enforcer: Permission enforcement
        knight_witness: Knight witness service
        verbose: Enable verbose logging

    Returns:
        Configured KingServiceAdapter
    """
    return KingServiceAdapter(
        permission_enforcer=permission_enforcer,
        knight_witness=knight_witness,
        verbose=verbose,
    )
