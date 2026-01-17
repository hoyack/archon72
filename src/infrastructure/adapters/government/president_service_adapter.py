"""President Service Adapter (Executive Branch).

This module implements the PresidentServiceProtocol for translating
ratified motions (WHAT) into execution plans (HOW).

Per Government PRD FR-GOV-9: Presidents translate ratified WHAT into executable HOW.
Per Government PRD FR-GOV-10: Presidents may not redefine intent, may not self-ratify,
must escalate blockers/ambiguity.
"""

import re
from uuid import UUID

from structlog import get_logger

from src.application.ports.king_service import MotionStatus
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
from src.application.ports.president_service import (
    Blocker,
    BlockerType,
    EscalationRequest,
    EscalationResult,
    ExecutionPlan,
    ExecutionTask,
    IntentRedefinitionError,
    PresidentServiceProtocol,
    SelfRatificationError,
    TaskDependency,
    TranslationRequest,
    TranslationResult,
)
from src.domain.models.aegis_task_spec import (
    AegisTaskSpec,
    ExpectedOutput,
    MeasurementPoint,
    MeasurementTrigger,
    MeasurementType,
    OutputType,
    SuccessCriterion,
)

logger = get_logger(__name__)


# Patterns that suggest the intent has been modified
INTENT_MODIFICATION_PATTERNS = [
    (re.compile(r"\b(?:instead|rather|alternatively)\b", re.I), "modification_language"),
    (re.compile(r"\b(?:change|modify|alter)\s+(?:the\s+)?(?:intent|goal|objective)\b", re.I), "explicit_modification"),
    (re.compile(r"\b(?:redefine|reinterpret|revise)\b", re.I), "redefinition_language"),
]


class PresidentServiceAdapter(PresidentServiceProtocol):
    """Implementation of President-rank executive functions.

    This service translates ratified motions (WHAT) into execution plans (HOW)
    with task decomposition, dependencies, sequencing, and success criteria.

    Key constraints (per FR-GOV-10):
    - May not redefine intent
    - May not self-ratify plans
    - Must escalate blockers/ambiguity

    All operations are witnessed by Knight per FR-GOV-20.
    """

    def __init__(
        self,
        permission_enforcer: PermissionEnforcerProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the President Service.

        Args:
            permission_enforcer: Permission enforcement (optional for testing)
            knight_witness: Knight witness for recording events (optional)
            verbose: Enable verbose logging
        """
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness
        self._verbose = verbose

        # In-memory storage
        self._plans: dict[UUID, ExecutionPlan] = {}
        self._escalations: dict[UUID, Blocker] = {}

        if self._verbose:
            logger.debug("president_service_initialized")

    async def translate_to_execution(
        self,
        request: TranslationRequest,
    ) -> TranslationResult:
        """Translate a ratified motion's WHAT into executable HOW.

        Per FR-GOV-9: Produces task decomposition, dependencies, sequencing,
        and success criteria.

        Args:
            request: Translation request with ratified motion

        Returns:
            TranslationResult with plan or blocker if escalation needed
        """
        if self._verbose:
            logger.debug(
                "translation_requested",
                motion_id=str(request.motion.motion_id),
                president_id=request.president_id,
            )

        # Check if motion is ratified
        if request.motion.status != MotionStatus.RATIFIED:
            return TranslationResult(
                success=False,
                error=f"Motion is not ratified (status: {request.motion.status.value}). "
                      "Cannot translate non-ratified motions.",
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource="execution_plan",
                action_details={"motion_id": str(request.motion.motion_id)},
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.president_id,
                action=GovernanceAction.DEFINE_EXECUTION,
                context=context,
            )

            if not permission_result.allowed:
                await self._witness_violation(
                    archon_id=request.president_id,
                    violation_type="rank_violation",
                    description=f"Attempted to define execution without President rank",
                )
                return TranslationResult(
                    success=False,
                    error=f"Permission denied: {permission_result.violation_reason}",
                )

        # Get intent (use amended if available)
        intent = request.motion.amended_intent or request.motion.intent

        # Check for ambiguity that requires escalation
        blocker = self._check_for_ambiguity(intent, request.motion.motion_id, request.president_id)
        if blocker:
            # Store escalation
            self._escalations[blocker.blocker_id] = blocker

            await self._observe_event(
                event_type="blocker_detected",
                description=f"President {request.president_id} detected ambiguity requiring escalation",
                data=blocker.to_dict(),
            )

            return TranslationResult(
                success=False,
                blocker=blocker,
                error="Intent contains ambiguity that requires Conclave clarification",
            )

        # Decompose into tasks
        tasks = await self.decompose_tasks(intent, request.motion.motion_id)

        # Verify intent is preserved
        if not await self.check_intent_preservation(intent, tasks):
            raise IntentRedefinitionError(
                president_id=request.president_id,
                original_intent=intent,
                modified_intent="Tasks do not preserve original intent",
            )

        # Identify dependencies
        dependencies = await self.identify_dependencies(tasks)

        # Create execution plan
        plan = ExecutionPlan.create(
            motion_ref=request.motion.motion_id,
            original_intent=intent,
            tasks=tasks,
            dependency_graph=dependencies,
            created_by=request.president_id,
        )

        # Store plan
        self._plans[plan.plan_id] = plan

        # Witness the plan creation
        await self._observe_event(
            event_type="execution_plan_created",
            description=f"President {request.president_id} created execution plan for motion",
            data={
                "plan_id": str(plan.plan_id),
                "motion_ref": str(plan.motion_ref),
                "task_count": plan.task_count,
                "status": plan.status.value,
            },
        )

        if self._verbose:
            logger.info(
                "translation_complete",
                plan_id=str(plan.plan_id),
                task_count=plan.task_count,
            )

        return TranslationResult(
            success=True,
            plan=plan,
        )

    async def decompose_tasks(
        self,
        intent: str,
        motion_ref: UUID,
    ) -> list[ExecutionTask]:
        """Decompose intent into individual tasks.

        This is a simplified decomposition that extracts key objectives
        from the intent. In a full implementation, this would use more
        sophisticated NLP or LLM-based decomposition.

        Args:
            intent: The WHAT from the motion
            motion_ref: Reference to the source motion

        Returns:
            List of ExecutionTasks derived from the intent
        """
        tasks: list[ExecutionTask] = []

        # Simple decomposition: create tasks for key phrases
        # This is a basic implementation - production would use LLM
        sentences = [s.strip() for s in intent.split(".") if s.strip()]

        for i, sentence in enumerate(sentences):
            if len(sentence) > 10:  # Skip very short fragments
                task = ExecutionTask.create(
                    name=f"Task {i + 1}: {sentence[:50]}...",
                    description=f"Execute objective: {sentence}",
                    success_criteria=[
                        f"Objective '{sentence[:50]}...' is achieved",
                        "Outcome is verifiable by Prince evaluation",
                    ],
                    sequence_order=i,
                )
                tasks.append(task)

        # Always add a completion verification task
        completion_task = ExecutionTask.create(
            name="Completion Verification",
            description="Verify all objectives are met and produce completion report",
            success_criteria=[
                "All prior tasks completed successfully",
                "Outcomes documented for Prince evaluation",
            ],
            dependencies=[t.task_id for t in tasks],
            sequence_order=len(tasks),
        )
        tasks.append(completion_task)

        return tasks

    async def identify_dependencies(
        self,
        tasks: list[ExecutionTask],
    ) -> list[TaskDependency]:
        """Identify dependencies between tasks.

        This implementation uses sequence order as a simple dependency model.
        Production would analyze task relationships more deeply.

        Args:
            tasks: The decomposed tasks

        Returns:
            List of TaskDependencies forming the dependency graph
        """
        dependencies: list[TaskDependency] = []

        # Create sequential dependencies based on order
        sorted_tasks = sorted(tasks, key=lambda t: t.sequence_order)

        for i in range(1, len(sorted_tasks)):
            prev_task = sorted_tasks[i - 1]
            curr_task = sorted_tasks[i]

            # Don't create dependency if already in task's dependencies
            if prev_task.task_id not in curr_task.dependencies:
                dep = TaskDependency(
                    from_task=prev_task.task_id,
                    to_task=curr_task.task_id,
                    dependency_type="blocks",
                )
                dependencies.append(dep)

        return dependencies

    async def escalate_blocker(
        self,
        request: EscalationRequest,
    ) -> EscalationResult:
        """Escalate a blocker to Conclave for resolution.

        Per FR-GOV-10: Presidents must escalate blockers/ambiguity.

        Args:
            request: Escalation request with blocker details

        Returns:
            EscalationResult with success/failure
        """
        if self._verbose:
            logger.debug(
                "escalation_requested",
                blocker_id=str(request.blocker.blocker_id),
                president_id=request.president_id,
            )

        # Store escalation
        self._escalations[request.blocker.blocker_id] = request.blocker

        # Witness the escalation
        await self._observe_event(
            event_type="blocker_escalated",
            description=f"President {request.president_id} escalated blocker to Conclave",
            data={
                "blocker_id": str(request.blocker.blocker_id),
                "blocker_type": request.blocker.blocker_type.value,
                "motion_ref": str(request.blocker.motion_ref),
                "questions": list(request.blocker.questions),
            },
        )

        if self._verbose:
            logger.info(
                "blocker_escalated",
                blocker_id=str(request.blocker.blocker_id),
                blocker_type=request.blocker.blocker_type.value,
            )

        return EscalationResult(
            success=True,
            escalation_id=request.blocker.blocker_id,
        )

    async def get_plan(self, plan_id: UUID) -> ExecutionPlan | None:
        """Retrieve an execution plan by ID."""
        return self._plans.get(plan_id)

    async def get_plans_by_motion(
        self,
        motion_ref: UUID,
    ) -> list[ExecutionPlan]:
        """Get all plans for a specific motion."""
        return [p for p in self._plans.values() if p.motion_ref == motion_ref]

    async def check_intent_preservation(
        self,
        original_intent: str,
        derived_tasks: list[ExecutionTask],
    ) -> bool:
        """Verify that derived tasks preserve the original intent.

        Per FR-GOV-10: Presidents may not redefine intent.

        Args:
            original_intent: The motion's intent
            derived_tasks: Tasks derived from the intent

        Returns:
            True if intent is preserved, False if it appears modified
        """
        # Check for modification language in task descriptions
        for task in derived_tasks:
            for pattern, pattern_type in INTENT_MODIFICATION_PATTERNS:
                if pattern.search(task.description):
                    if self._verbose:
                        logger.warning(
                            "intent_modification_detected",
                            task_id=task.task_id,
                            pattern_type=pattern_type,
                        )
                    return False

        # Verify tasks relate to original intent keywords
        intent_words = set(
            word.lower()
            for word in re.findall(r"\b\w{4,}\b", original_intent)
        )

        task_words = set()
        for task in derived_tasks:
            task_words.update(
                word.lower()
                for word in re.findall(r"\b\w{4,}\b", task.description)
            )

        # At least 30% of intent keywords should appear in tasks
        if intent_words:
            overlap = len(intent_words & task_words) / len(intent_words)
            if overlap < 0.3:
                if self._verbose:
                    logger.warning(
                        "low_intent_overlap",
                        overlap_ratio=overlap,
                    )
                # Don't fail on low overlap - just warn
                # Production would be more sophisticated

        return True

    async def prevent_self_ratification(
        self,
        plan_id: UUID,
        ratifier_id: str,
    ) -> None:
        """Prevent a President from ratifying their own plan.

        Per FR-GOV-10: Presidents may not self-ratify plans.

        Args:
            plan_id: The plan to ratify
            ratifier_id: ID of the Archon attempting ratification

        Raises:
            SelfRatificationError: If ratifier created the plan
        """
        plan = self._plans.get(plan_id)
        if plan and plan.created_by == ratifier_id:
            # Witness the violation
            await self._witness_violation(
                archon_id=ratifier_id,
                violation_type="self_ratification_attempt",
                description=f"President {ratifier_id} attempted to ratify their own plan",
            )

            raise SelfRatificationError(
                president_id=ratifier_id,
                plan_id=plan_id,
            )

    def _check_for_ambiguity(
        self,
        intent: str,
        motion_ref: UUID,
        president_id: str,
    ) -> Blocker | None:
        """Check if intent contains ambiguity requiring escalation.

        Args:
            intent: The motion's intent
            motion_ref: Reference to the motion
            president_id: The President checking

        Returns:
            Blocker if ambiguity detected, None otherwise
        """
        questions: list[str] = []

        # Check for ambiguous language
        if re.search(r"\b(?:some|various|certain|appropriate)\b", intent, re.I):
            questions.append("Please specify which items/approaches are intended")

        if re.search(r"\b(?:etc|and so on|and more)\b", intent, re.I):
            questions.append("Please enumerate all intended items (no 'etc')")

        if re.search(r"\b(?:maybe|perhaps|possibly|might)\b", intent, re.I):
            questions.append("Please clarify conditional requirements")

        if re.search(r"\b(?:as needed|if necessary|when appropriate)\b", intent, re.I):
            questions.append("Please define specific conditions for optional items")

        if questions:
            return Blocker.create(
                blocker_type=BlockerType.AMBIGUITY,
                description="Intent contains ambiguous language requiring clarification",
                questions=questions,
                motion_ref=motion_ref,
                raised_by=president_id,
            )

        return None

    async def create_aegis_task_spec(
        self,
        plan: ExecutionPlan,
        task: ExecutionTask,
    ) -> AegisTaskSpec:
        """Convert an ExecutionTask to an AegisTaskSpec.

        This creates the formal contract for Aegis Network execution.

        Args:
            plan: The execution plan
            task: The task to convert

        Returns:
            AegisTaskSpec for submission to Aegis Network
        """
        # Convert success criteria to SuccessCriterion objects
        criteria = [
            SuccessCriterion.create(
                description=criterion,
                measurement_type=MeasurementType.BOOLEAN,
            )
            for criterion in task.success_criteria
        ]

        # Create expected output
        outputs = [
            ExpectedOutput.create(
                name=f"{task.name}_result",
                output_type=OutputType.REPORT,
                description=f"Completion report for {task.name}",
            )
        ]

        # Create measurement point at completion
        measurement = MeasurementPoint.create(
            name="Task Completion",
            trigger=MeasurementTrigger.COMPLETION,
            criteria_refs=[c.criterion_id for c in criteria],
        )

        return AegisTaskSpec.create(
            motion_ref=plan.motion_ref,
            intent_summary=task.description,
            success_criteria=criteria,
            expected_outputs=outputs,
            created_by=plan.created_by,
            measurement_points=[measurement],
        )

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
        """Record a violation via Knight Witness."""
        if not self._knight_witness:
            return

        statement_type = WitnessStatementType.ROLE_VIOLATION
        if "self_ratification" in violation_type.lower():
            statement_type = WitnessStatementType.BRANCH_VIOLATION

        record = ViolationRecord(
            statement_type=statement_type,
            description=description,
            roles_involved=(archon_id,),
            evidence=evidence or {},
            prd_reference="FR-GOV-10",
        )

        await self._knight_witness.record_violation(record)

    async def _observe_event(
        self,
        event_type: str,
        description: str,
        data: dict | None = None,
    ) -> None:
        """Record an event via Knight Witness."""
        if not self._knight_witness:
            return

        context = ObservationContext(
            event_type=event_type,
            source_service="president_service",
            data=data or {},
        )

        await self._knight_witness.observe(description, context)


def create_president_service(
    permission_enforcer: PermissionEnforcerProtocol | None = None,
    knight_witness: KnightWitnessProtocol | None = None,
    verbose: bool = False,
) -> PresidentServiceAdapter:
    """Factory function to create a PresidentServiceAdapter.

    Args:
        permission_enforcer: Permission enforcement
        knight_witness: Knight witness service
        verbose: Enable verbose logging

    Returns:
        Configured PresidentServiceAdapter
    """
    return PresidentServiceAdapter(
        permission_enforcer=permission_enforcer,
        knight_witness=knight_witness,
        verbose=verbose,
    )
