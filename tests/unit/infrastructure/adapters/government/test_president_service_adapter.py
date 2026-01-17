"""Unit tests for PresidentServiceAdapter.

Tests the President Service executive functions per Government PRD FR-GOV-9/FR-GOV-10.
"""

import pytest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from src.application.ports.king_service import Motion, MotionStatus
from src.application.ports.president_service import (
    Blocker,
    BlockerType,
    EscalationRequest,
    ExecutionPlanStatus,
    SelfRatificationError,
    TranslationRequest,
)
from src.infrastructure.adapters.government.president_service_adapter import (
    PresidentServiceAdapter,
    create_president_service,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def president_service() -> PresidentServiceAdapter:
    """Create a President Service for testing."""
    return PresidentServiceAdapter(verbose=True)


@pytest.fixture
def ratified_motion() -> Motion:
    """Create a ratified motion for translation."""
    return Motion(
        motion_id=uuid4(),
        introduced_by="archon-bael-001",
        title="Improve System Reliability",
        intent="Ensure the system maintains 99.9% uptime by addressing infrastructure weaknesses and implementing redundancy measures.",
        rationale="Current uptime is below target, affecting customer satisfaction.",
        status=MotionStatus.RATIFIED,
        introduced_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def unratified_motion() -> Motion:
    """Create an unratified motion (INTRODUCED status)."""
    return Motion(
        motion_id=uuid4(),
        introduced_by="archon-bael-001",
        title="Pending Motion",
        intent="This motion has not been ratified yet.",
        rationale="Testing status check.",
        status=MotionStatus.INTRODUCED,
        introduced_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def ambiguous_motion() -> Motion:
    """Create a motion with ambiguous intent."""
    return Motion(
        motion_id=uuid4(),
        introduced_by="archon-bael-001",
        title="Vague Motion",
        intent="Improve various aspects of the system as needed, possibly including some enhancements, etc.",
        rationale="Testing ambiguity detection.",
        status=MotionStatus.RATIFIED,
        introduced_at=datetime.now(timezone.utc),
    )


# =============================================================================
# TEST ADAPTER INITIALIZATION
# =============================================================================


class TestAdapterInit:
    """Test adapter initialization."""

    def test_create_adapter(self) -> None:
        """Test basic adapter creation."""
        adapter = PresidentServiceAdapter()
        assert adapter is not None

    def test_factory_function(self) -> None:
        """Test factory function."""
        adapter = create_president_service(verbose=True)
        assert isinstance(adapter, PresidentServiceAdapter)


# =============================================================================
# TEST TRANSLATION - SUCCESS
# =============================================================================


class TestTranslationSuccess:
    """Test successful translation of ratified motions."""

    @pytest.mark.asyncio
    async def test_translate_ratified_motion(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test translating a ratified motion to execution plan."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",  # President rank
        )

        result = await president_service.translate_to_execution(request)

        assert result.success is True
        assert result.plan is not None
        assert result.plan.motion_ref == ratified_motion.motion_id
        assert result.plan.original_intent == ratified_motion.intent
        assert result.blocker is None

    @pytest.mark.asyncio
    async def test_plan_has_tasks(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test that execution plan contains decomposed tasks."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )

        result = await president_service.translate_to_execution(request)

        assert result.plan.task_count > 0
        # Should have at least intent tasks + completion verification
        assert result.plan.task_count >= 2

    @pytest.mark.asyncio
    async def test_plan_has_dependencies(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test that execution plan contains dependency graph."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )

        result = await president_service.translate_to_execution(request)

        assert len(result.plan.dependency_graph) > 0

    @pytest.mark.asyncio
    async def test_plan_status_pending_ratification(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test that new plans are PENDING_RATIFICATION (per FR-GOV-10)."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )

        result = await president_service.translate_to_execution(request)

        assert result.plan.status == ExecutionPlanStatus.PENDING_RATIFICATION
        assert result.plan.is_pending_ratification is True


# =============================================================================
# TEST TRANSLATION - FAILURES
# =============================================================================


class TestTranslationFailures:
    """Test translation failures."""

    @pytest.mark.asyncio
    async def test_reject_unratified_motion(
        self,
        president_service: PresidentServiceAdapter,
        unratified_motion: Motion,
    ) -> None:
        """Test rejection of unratified motion."""
        request = TranslationRequest(
            motion=unratified_motion,
            president_id="archon-agares-001",
        )

        result = await president_service.translate_to_execution(request)

        assert result.success is False
        assert result.plan is None
        assert "not ratified" in result.error.lower()

    @pytest.mark.asyncio
    async def test_detect_ambiguity(
        self,
        president_service: PresidentServiceAdapter,
        ambiguous_motion: Motion,
    ) -> None:
        """Test detection of ambiguous intent requiring escalation."""
        request = TranslationRequest(
            motion=ambiguous_motion,
            president_id="archon-agares-001",
        )

        result = await president_service.translate_to_execution(request)

        assert result.success is False
        assert result.blocker is not None
        assert result.blocker.blocker_type == BlockerType.AMBIGUITY
        assert len(result.blocker.questions) > 0


# =============================================================================
# TEST TASK DECOMPOSITION
# =============================================================================


class TestTaskDecomposition:
    """Test task decomposition logic."""

    @pytest.mark.asyncio
    async def test_decompose_tasks(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test decomposing intent into tasks."""
        intent = "Improve customer response times. Reduce ticket resolution time."
        motion_ref = uuid4()

        tasks = await president_service.decompose_tasks(intent, motion_ref)

        assert len(tasks) >= 2  # At least 2 sentences + completion task
        assert all(len(t.success_criteria) > 0 for t in tasks)

    @pytest.mark.asyncio
    async def test_tasks_have_success_criteria(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test that each task has success criteria."""
        intent = "Achieve goal A. Accomplish objective B."
        motion_ref = uuid4()

        tasks = await president_service.decompose_tasks(intent, motion_ref)

        for task in tasks:
            assert len(task.success_criteria) > 0, f"Task {task.name} has no success criteria"

    @pytest.mark.asyncio
    async def test_completion_verification_task(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test that decomposition includes completion verification task."""
        intent = "Do something important."
        motion_ref = uuid4()

        tasks = await president_service.decompose_tasks(intent, motion_ref)

        completion_tasks = [t for t in tasks if "completion" in t.name.lower()]
        assert len(completion_tasks) == 1


# =============================================================================
# TEST DEPENDENCY IDENTIFICATION
# =============================================================================


class TestDependencyIdentification:
    """Test dependency identification logic."""

    @pytest.mark.asyncio
    async def test_identify_sequential_dependencies(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test identifying sequential dependencies."""
        intent = "First objective. Second objective. Third objective."
        motion_ref = uuid4()

        tasks = await president_service.decompose_tasks(intent, motion_ref)
        dependencies = await president_service.identify_dependencies(tasks)

        assert len(dependencies) > 0
        assert all(d.dependency_type == "blocks" for d in dependencies)


# =============================================================================
# TEST BLOCKER ESCALATION (Story 3.3)
# =============================================================================


class TestBlockerEscalation:
    """Test blocker escalation to Conclave."""

    @pytest.mark.asyncio
    async def test_escalate_blocker(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test escalating a blocker."""
        blocker = Blocker.create(
            blocker_type=BlockerType.AMBIGUITY,
            description="Intent is unclear about scope",
            questions=[
                "Should the scope include legacy systems?",
                "What is the priority order?",
            ],
            motion_ref=uuid4(),
            raised_by="archon-agares-001",
        )

        request = EscalationRequest(
            blocker=blocker,
            president_id="archon-agares-001",
        )

        result = await president_service.escalate_blocker(request)

        assert result.success is True
        assert result.escalation_id == blocker.blocker_id

    @pytest.mark.asyncio
    async def test_escalation_recorded(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test that escalation is recorded."""
        blocker = Blocker.create(
            blocker_type=BlockerType.CONTRADICTION,
            description="Intent contradicts existing policy",
            questions=["Which policy takes precedence?"],
            motion_ref=uuid4(),
            raised_by="archon-agares-001",
        )

        request = EscalationRequest(
            blocker=blocker,
            president_id="archon-agares-001",
        )

        await president_service.escalate_blocker(request)

        # Verify recorded in escalations
        assert blocker.blocker_id in president_service._escalations


# =============================================================================
# TEST SELF-RATIFICATION PREVENTION (Story 3.4)
# =============================================================================


class TestSelfRatificationPrevention:
    """Test prevention of self-ratification."""

    @pytest.mark.asyncio
    async def test_prevent_self_ratification(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test that President cannot ratify their own plan."""
        # Create a plan
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )
        result = await president_service.translate_to_execution(request)
        plan = result.plan

        # Attempt self-ratification
        with pytest.raises(SelfRatificationError) as exc_info:
            await president_service.prevent_self_ratification(
                plan_id=plan.plan_id,
                ratifier_id="archon-agares-001",  # Same as creator
            )

        assert exc_info.value.president_id == "archon-agares-001"
        assert exc_info.value.plan_id == plan.plan_id

    @pytest.mark.asyncio
    async def test_different_ratifier_allowed(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test that different President can ratify."""
        # Create a plan
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )
        result = await president_service.translate_to_execution(request)
        plan = result.plan

        # Different ratifier should not raise
        await president_service.prevent_self_ratification(
            plan_id=plan.plan_id,
            ratifier_id="archon-vassago-002",  # Different from creator
        )
        # No exception raised = success


# =============================================================================
# TEST INTENT PRESERVATION
# =============================================================================


class TestIntentPreservation:
    """Test intent preservation checking."""

    @pytest.mark.asyncio
    async def test_preserved_intent(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test that valid tasks preserve intent."""
        from src.application.ports.president_service import ExecutionTask

        intent = "Improve system reliability through monitoring and alerting."
        tasks = [
            ExecutionTask.create(
                name="Task 1",
                description="Implement monitoring for system reliability",
                success_criteria=["Monitoring operational"],
            ),
            ExecutionTask.create(
                name="Task 2",
                description="Set up alerting for reliability issues",
                success_criteria=["Alerts configured"],
            ),
        ]

        result = await president_service.check_intent_preservation(intent, tasks)
        assert result is True

    @pytest.mark.asyncio
    async def test_modified_intent_detected(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test detection of intent modification."""
        from src.application.ports.president_service import ExecutionTask

        intent = "Improve system reliability."
        tasks = [
            ExecutionTask.create(
                name="Task 1",
                description="Instead of reliability, let's redefine the goal to focus on performance",
                success_criteria=["Performance improved"],
            ),
        ]

        result = await president_service.check_intent_preservation(intent, tasks)
        assert result is False


# =============================================================================
# TEST PLAN RETRIEVAL
# =============================================================================


class TestPlanRetrieval:
    """Test plan retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_plan_exists(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test retrieving an existing plan."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )
        result = await president_service.translate_to_execution(request)

        plan = await president_service.get_plan(result.plan.plan_id)
        assert plan is not None
        assert plan.plan_id == result.plan.plan_id

    @pytest.mark.asyncio
    async def test_get_plan_not_exists(
        self,
        president_service: PresidentServiceAdapter,
    ) -> None:
        """Test retrieving a non-existent plan."""
        plan = await president_service.get_plan(uuid4())
        assert plan is None

    @pytest.mark.asyncio
    async def test_get_plans_by_motion(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test retrieving plans by motion."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )
        await president_service.translate_to_execution(request)

        plans = await president_service.get_plans_by_motion(ratified_motion.motion_id)
        assert len(plans) == 1
        assert plans[0].motion_ref == ratified_motion.motion_id


# =============================================================================
# TEST AEGIS TASK SPEC CREATION
# =============================================================================


class TestAegisTaskSpecCreation:
    """Test AegisTaskSpec creation from execution tasks."""

    @pytest.mark.asyncio
    async def test_create_aegis_task_spec(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test creating AegisTaskSpec from ExecutionTask."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )
        result = await president_service.translate_to_execution(request)
        plan = result.plan
        task = plan.tasks[0]

        spec = await president_service.create_aegis_task_spec(plan, task)

        assert spec.motion_ref == plan.motion_ref
        assert spec.created_by == plan.created_by
        assert len(spec.success_criteria) == len(task.success_criteria)
        assert len(spec.expected_outputs) > 0


# =============================================================================
# TEST SERIALIZATION
# =============================================================================


class TestSerialization:
    """Test object serialization."""

    @pytest.mark.asyncio
    async def test_plan_to_dict(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test ExecutionPlan serialization."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )
        result = await president_service.translate_to_execution(request)
        d = result.plan.to_dict()

        assert "plan_id" in d
        assert "motion_ref" in d
        assert "original_intent" in d
        assert "tasks" in d
        assert "dependency_graph" in d
        assert d["status"] == "pending_ratification"

    @pytest.mark.asyncio
    async def test_result_to_dict(
        self,
        president_service: PresidentServiceAdapter,
        ratified_motion: Motion,
    ) -> None:
        """Test TranslationResult serialization."""
        request = TranslationRequest(
            motion=ratified_motion,
            president_id="archon-agares-001",
        )
        result = await president_service.translate_to_execution(request)
        d = result.to_dict()

        assert d["success"] is True
        assert d["plan"] is not None
        assert d["blocker"] is None
