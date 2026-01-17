"""Unit tests for KingServiceAdapter.

Tests the King Service legislative functions per Government PRD FR-GOV-5/FR-GOV-6.
"""

import pytest
from uuid import uuid4

from src.application.ports.king_service import (
    MotionIntroductionRequest,
    MotionStatus,
)
from src.infrastructure.adapters.government.king_service_adapter import (
    KingServiceAdapter,
    create_king_service,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def king_service() -> KingServiceAdapter:
    """Create a King Service for testing (no dependencies)."""
    return KingServiceAdapter(verbose=True)


@pytest.fixture
def valid_intent_request() -> MotionIntroductionRequest:
    """Create a valid motion request with intent-only content."""
    return MotionIntroductionRequest(
        introduced_by="archon-bael-001",  # Bael is King-rank
        title="Improve Customer Satisfaction",
        intent="Ensure customers receive timely and helpful responses to their inquiries.",
        rationale="Customer satisfaction scores have been declining, affecting retention.",
    )


@pytest.fixture
def invalid_intent_request() -> MotionIntroductionRequest:
    """Create a motion request with execution details (HOW)."""
    return MotionIntroductionRequest(
        introduced_by="archon-bael-001",
        title="Build New API",
        intent="Step 1: Design the API using Python. Step 2: Deploy to AWS within 2 weeks.",
        rationale="We need a new API for integration.",
    )


# =============================================================================
# TEST ADAPTER INITIALIZATION
# =============================================================================


class TestAdapterInit:
    """Test adapter initialization."""

    def test_create_adapter(self) -> None:
        """Test basic adapter creation."""
        adapter = KingServiceAdapter()
        assert adapter is not None

    def test_factory_function(self) -> None:
        """Test factory function."""
        adapter = create_king_service(verbose=True)
        assert isinstance(adapter, KingServiceAdapter)


# =============================================================================
# TEST MOTION INTRODUCTION - VALID INTENT
# =============================================================================


class TestMotionIntroductionValid:
    """Test successful motion introduction with valid intent."""

    @pytest.mark.asyncio
    async def test_introduce_valid_motion(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test introducing a valid intent-only motion."""
        result = await king_service.introduce_motion(valid_intent_request)

        assert result.success is True
        assert result.motion is not None
        assert result.motion.status == MotionStatus.INTRODUCED
        assert result.motion.introduced_by == valid_intent_request.introduced_by
        assert result.motion.title == valid_intent_request.title
        assert result.motion.intent == valid_intent_request.intent
        assert result.error is None

    @pytest.mark.asyncio
    async def test_motion_stored(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test that introduced motion is stored."""
        result = await king_service.introduce_motion(valid_intent_request)

        assert result.success is True
        motion = await king_service.get_motion(result.motion.motion_id)
        assert motion is not None
        assert motion.motion_id == result.motion.motion_id

    @pytest.mark.asyncio
    async def test_validation_result_included(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test that validation result is included."""
        result = await king_service.introduce_motion(valid_intent_request)

        assert result.validation_result is not None
        assert result.validation_result.is_valid is True
        assert result.validation_result.violation_count == 0


# =============================================================================
# TEST MOTION INTRODUCTION - INVALID INTENT (EXECUTION DETAILS)
# =============================================================================


class TestMotionIntroductionInvalid:
    """Test motion rejection when intent contains execution details."""

    @pytest.mark.asyncio
    async def test_reject_execution_details(
        self,
        king_service: KingServiceAdapter,
        invalid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test rejection of motion with execution details (HOW)."""
        result = await king_service.introduce_motion(invalid_intent_request)

        assert result.success is False
        assert result.motion is None
        assert result.error is not None
        assert "execution details" in result.error.lower()

    @pytest.mark.asyncio
    async def test_violations_reported(
        self,
        king_service: KingServiceAdapter,
        invalid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test that violations are reported in result."""
        result = await king_service.introduce_motion(invalid_intent_request)

        assert result.validation_result is not None
        assert result.validation_result.is_valid is False
        assert result.validation_result.violation_count > 0

    @pytest.mark.asyncio
    async def test_task_list_violation(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test detection of task list in motion."""
        request = MotionIntroductionRequest(
            introduced_by="archon-bael-001",
            title="Test Motion",
            intent="Step 1: Do A. Step 2: Do B. Step 3: Do C.",
            rationale="Testing task list detection.",
        )

        result = await king_service.introduce_motion(request)

        assert result.success is False
        assert any("task_list" in v.violation_type.value for v in result.validation_result.violations)

    @pytest.mark.asyncio
    async def test_timeline_violation(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test detection of timeline in motion."""
        request = MotionIntroductionRequest(
            introduced_by="archon-bael-001",
            title="Test Motion",
            intent="Complete this within 3 weeks with deadline: Friday.",
            rationale="Testing timeline detection.",
        )

        result = await king_service.introduce_motion(request)

        assert result.success is False
        assert any("timeline" in v.violation_type.value for v in result.validation_result.violations)

    @pytest.mark.asyncio
    async def test_tool_specification_violation(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test detection of tool specification in motion."""
        request = MotionIntroductionRequest(
            introduced_by="archon-bael-001",
            title="Test Motion",
            intent="Build this using Python and deploy to AWS.",
            rationale="Testing tool spec detection.",
        )

        result = await king_service.introduce_motion(request)

        assert result.success is False
        assert any("tool_specification" in v.violation_type.value for v in result.validation_result.violations)


# =============================================================================
# TEST VALIDATE INTENT ONLY
# =============================================================================


class TestValidateIntentOnly:
    """Test direct intent validation."""

    @pytest.mark.asyncio
    async def test_validate_clean_intent(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test validation of clean intent."""
        result = await king_service.validate_intent_only(
            "Improve system reliability and user experience."
        )

        assert result.is_valid is True
        assert result.violation_count == 0

    @pytest.mark.asyncio
    async def test_validate_dirty_intent(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test validation of intent with execution details."""
        result = await king_service.validate_intent_only(
            "Step 1: Implement using React. Timeline: 2 sprints."
        )

        assert result.is_valid is False
        assert result.violation_count > 0


# =============================================================================
# TEST MOTION RETRIEVAL
# =============================================================================


class TestMotionRetrieval:
    """Test motion retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_motion_exists(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test retrieving an existing motion."""
        intro_result = await king_service.introduce_motion(valid_intent_request)
        motion = await king_service.get_motion(intro_result.motion.motion_id)

        assert motion is not None
        assert motion.motion_id == intro_result.motion.motion_id

    @pytest.mark.asyncio
    async def test_get_motion_not_exists(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test retrieving a non-existent motion."""
        motion = await king_service.get_motion(uuid4())
        assert motion is None

    @pytest.mark.asyncio
    async def test_get_motions_by_status(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test retrieving motions by status."""
        await king_service.introduce_motion(valid_intent_request)
        motions = await king_service.get_motions_by_status(MotionStatus.INTRODUCED)

        assert len(motions) >= 1
        assert all(m.status == MotionStatus.INTRODUCED for m in motions)

    @pytest.mark.asyncio
    async def test_get_motions_by_king(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test retrieving motions by King."""
        request1 = MotionIntroductionRequest(
            introduced_by="archon-bael-001",
            title="Motion 1",
            intent="Improve quality.",
            rationale="Quality matters.",
        )
        request2 = MotionIntroductionRequest(
            introduced_by="archon-paimon-002",
            title="Motion 2",
            intent="Increase efficiency.",
            rationale="Efficiency matters.",
        )

        await king_service.introduce_motion(request1)
        await king_service.introduce_motion(request2)

        bael_motions = await king_service.get_motions_by_king("archon-bael-001")
        paimon_motions = await king_service.get_motions_by_king("archon-paimon-002")

        assert len(bael_motions) == 1
        assert len(paimon_motions) == 1
        assert bael_motions[0].introduced_by == "archon-bael-001"
        assert paimon_motions[0].introduced_by == "archon-paimon-002"


# =============================================================================
# TEST MOTION DOMAIN MODEL
# =============================================================================


class TestMotionModel:
    """Test Motion domain model."""

    @pytest.mark.asyncio
    async def test_motion_immutable(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test that Motion is immutable (frozen dataclass)."""
        result = await king_service.introduce_motion(valid_intent_request)
        motion = result.motion

        with pytest.raises(Exception):
            motion.title = "Modified"  # type: ignore

    @pytest.mark.asyncio
    async def test_motion_to_dict(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test Motion serialization."""
        result = await king_service.introduce_motion(valid_intent_request)
        d = result.motion.to_dict()

        assert "motion_id" in d
        assert d["title"] == valid_intent_request.title
        assert d["intent"] == valid_intent_request.intent
        assert d["status"] == "introduced"


# =============================================================================
# TEST RESULT SERIALIZATION
# =============================================================================


class TestResultSerialization:
    """Test result object serialization."""

    @pytest.mark.asyncio
    async def test_success_result_to_dict(
        self,
        king_service: KingServiceAdapter,
        valid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test successful result serialization."""
        result = await king_service.introduce_motion(valid_intent_request)
        d = result.to_dict()

        assert d["success"] is True
        assert d["motion"] is not None
        assert d["error"] is None

    @pytest.mark.asyncio
    async def test_failure_result_to_dict(
        self,
        king_service: KingServiceAdapter,
        invalid_intent_request: MotionIntroductionRequest,
    ) -> None:
        """Test failure result serialization."""
        result = await king_service.introduce_motion(invalid_intent_request)
        d = result.to_dict()

        assert d["success"] is False
        assert d["motion"] is None
        assert d["error"] is not None
        assert d["validation_result"] is not None


# =============================================================================
# TEST EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_intent(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test motion with empty intent."""
        request = MotionIntroductionRequest(
            introduced_by="archon-bael-001",
            title="Empty Intent",
            intent="",
            rationale="Testing empty intent.",
        )

        result = await king_service.introduce_motion(request)
        # Empty intent is technically valid (no HOW), but questionable
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multiple_motions_same_king(
        self,
        king_service: KingServiceAdapter,
    ) -> None:
        """Test multiple motions from same King."""
        for i in range(3):
            request = MotionIntroductionRequest(
                introduced_by="archon-bael-001",
                title=f"Motion {i}",
                intent=f"Intent number {i}.",
                rationale="Testing multiple motions.",
            )
            result = await king_service.introduce_motion(request)
            assert result.success is True

        motions = await king_service.get_motions_by_king("archon-bael-001")
        assert len(motions) == 3
