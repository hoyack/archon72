"""Unit tests for CoercionFilterService.

Story: consent-gov-3.2: Coercion Filter Service

Tests the full filtering pipeline:
- Performance constraint (≤200ms) - AC1
- Deterministic processing - AC2
- Mandatory routing - AC3, AC4
- Transformation pipeline - AC5
- Rejection logic - AC6
- Blocking logic - AC7
- FilteredContent return - AC8

Constitutional Guarantees:
- All participant-facing content MUST pass through filter (FR21)
- No bypass path exists (NFR-CONST-05)
- Determinism > Speed (NFR-PERF-03)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.governance.coercion_filter_port import MessageType
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.application.services.governance.coercion_filter_service import (
    CoercionFilterService,
    PatternLibraryPort,
)
from src.domain.governance.filter import (
    FilterDecision,
    FilteredContent,
    FilterVersion,
    RejectionReason,
    TransformationRule,
    ViolationType,
)


class FakeTimeAuthority(TimeAuthorityProtocol):
    """Fake time authority for deterministic testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._time

    def utcnow(self) -> datetime:
        return self._time

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, seconds: float) -> None:
        """Advance time by given seconds."""
        self._time = self._time + timedelta(seconds=seconds)
        self._monotonic += seconds


class FakePatternLibrary(PatternLibraryPort):
    """Fake pattern library for testing."""

    def __init__(self) -> None:
        self._version = FilterVersion(
            major=1, minor=0, patch=0, rules_hash="test_hash_abc123"
        )
        self._blocking_patterns: list[dict] = [
            {
                "pattern": r"(?i)hurt\s+you",
                "violation_type": ViolationType.EXPLICIT_THREAT,
            },
            {
                "pattern": r"(?i)kill\s+you",
                "violation_type": ViolationType.EXPLICIT_THREAT,
            },
            {"pattern": r"(?i)deceive", "violation_type": ViolationType.DECEPTION},
        ]
        self._rejection_patterns: list[dict] = [
            {"pattern": r"(?i)you\s+must", "reason": RejectionReason.URGENCY_PRESSURE},
            {"pattern": r"(?i)penalized", "reason": RejectionReason.IMPLICIT_THREAT},
            {"pattern": r"(?i)your\s+fault", "reason": RejectionReason.GUILT_INDUCTION},
        ]
        self._transform_rules: list[TransformationRule] = [
            TransformationRule(
                rule_id="urgency-1",
                pattern=r"(?i)URGENT!?",
                replacement="",
                description="Remove urgency markers",
                category="urgency",
                version="1.0.0",
            ),
            TransformationRule(
                rule_id="emphasis-1",
                pattern=r"(?i)NOW!?",
                replacement="",
                description="Remove now emphasis",
                category="emphasis",
                version="1.0.0",
            ),
        ]

    async def get_current_version(self) -> FilterVersion:
        return self._version

    async def get_blocking_patterns(self) -> list[dict]:
        return self._blocking_patterns

    async def get_rejection_patterns(self) -> list[dict]:
        return self._rejection_patterns

    async def get_transformation_rules(self) -> list[TransformationRule]:
        return self._transform_rules


class TestCoercionFilterServiceCreation:
    """Tests for service creation."""

    def test_service_created_with_dependencies(self) -> None:
        """Service requires pattern library and time authority."""
        pattern_library = FakePatternLibrary()
        time_authority = FakeTimeAuthority()

        service = CoercionFilterService(
            pattern_library=pattern_library,
            time_authority=time_authority,
        )

        assert service is not None


class TestFilterContentAccepted:
    """Tests for ACCEPTED filter outcomes (AC8)."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_clean_content_accepted(self, service: CoercionFilterService) -> None:
        """Clean content returns ACCEPTED with FilteredContent."""
        result = await service.filter_content(
            content="Please review this when convenient.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert result.content is not None
        assert isinstance(result.content, FilteredContent)

    @pytest.mark.asyncio
    async def test_accepted_includes_version(
        self, service: CoercionFilterService
    ) -> None:
        """Accepted result includes filter version."""
        result = await service.filter_content(
            content="Clean content.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.version is not None
        assert result.version.major == 1

    @pytest.mark.asyncio
    async def test_accepted_includes_timestamp(
        self, service: CoercionFilterService
    ) -> None:
        """Accepted result includes timestamp."""
        result = await service.filter_content(
            content="Clean content.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_filtered_content_has_original_hash(
        self, service: CoercionFilterService
    ) -> None:
        """FilteredContent includes hash of original content."""
        result = await service.filter_content(
            content="Clean content.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.content is not None
        assert result.content.original_hash is not None
        assert len(result.content.original_hash) == 64  # BLAKE2b hex


class TestTransformationPipeline:
    """Tests for transformation pipeline (AC5)."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_urgency_transformed(self, service: CoercionFilterService) -> None:
        """URGENT is removed from content."""
        result = await service.filter_content(
            content="URGENT Please review this.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert result.content is not None
        assert "URGENT" not in result.content.content

    @pytest.mark.asyncio
    async def test_now_emphasis_transformed(
        self, service: CoercionFilterService
    ) -> None:
        """NOW is removed from content."""
        result = await service.filter_content(
            content="Complete this NOW!",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert result.content is not None
        assert "NOW" not in result.content.content

    @pytest.mark.asyncio
    async def test_transformations_recorded(
        self, service: CoercionFilterService
    ) -> None:
        """Applied transformations are recorded."""
        result = await service.filter_content(
            content="URGENT Complete this NOW!",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert len(result.transformations) >= 1

    @pytest.mark.asyncio
    async def test_transformation_includes_rule_id(
        self, service: CoercionFilterService
    ) -> None:
        """Transformation records include rule ID for audit."""
        result = await service.filter_content(
            content="URGENT task",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        if result.transformations:
            assert result.transformations[0].rule_id is not None


class TestRejectionLogic:
    """Tests for rejection logic (AC6)."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_must_language_rejected(self, service: CoercionFilterService) -> None:
        """Content with 'you must' is rejected."""
        result = await service.filter_content(
            content="You must complete this task.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.REJECTED
        assert result.content is None
        assert result.rejection_reason == RejectionReason.URGENCY_PRESSURE

    @pytest.mark.asyncio
    async def test_penalty_language_rejected(
        self, service: CoercionFilterService
    ) -> None:
        """Content with penalty threat is rejected."""
        result = await service.filter_content(
            content="You will be penalized for not completing this.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.REJECTED
        assert result.rejection_reason == RejectionReason.IMPLICIT_THREAT

    @pytest.mark.asyncio
    async def test_guilt_induction_rejected(
        self, service: CoercionFilterService
    ) -> None:
        """Content with guilt induction is rejected."""
        result = await service.filter_content(
            content="This is your fault if it fails.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.REJECTED
        assert result.rejection_reason == RejectionReason.GUILT_INDUCTION

    @pytest.mark.asyncio
    async def test_rejection_includes_guidance(
        self, service: CoercionFilterService
    ) -> None:
        """Rejected result includes rewrite guidance."""
        result = await service.filter_content(
            content="You must do this.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.REJECTED
        assert result.rejection_guidance is not None


class TestBlockingLogic:
    """Tests for blocking logic (AC7)."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_threat_blocked(self, service: CoercionFilterService) -> None:
        """Content with explicit threat is blocked."""
        result = await service.filter_content(
            content="Do this or I will hurt you.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.BLOCKED
        assert result.content is None
        assert result.violation_type == ViolationType.EXPLICIT_THREAT

    @pytest.mark.asyncio
    async def test_deception_blocked(self, service: CoercionFilterService) -> None:
        """Content with deception is blocked."""
        result = await service.filter_content(
            content="I will deceive you about this.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.BLOCKED
        assert result.violation_type == ViolationType.DECEPTION

    @pytest.mark.asyncio
    async def test_blocked_includes_details(
        self, service: CoercionFilterService
    ) -> None:
        """Blocked result includes violation details."""
        result = await service.filter_content(
            content="I will hurt you if you don't comply.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.BLOCKED
        assert result.violation_details is not None


class TestDeterministicProcessing:
    """Tests for deterministic processing (AC2)."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_same_input_same_output(self, service: CoercionFilterService) -> None:
        """Same input always produces same output."""
        content = "Please complete this task."

        result1 = await service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )
        result2 = await service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result1.decision == result2.decision
        if result1.content and result2.content:
            assert result1.content.content == result2.content.content

    @pytest.mark.asyncio
    async def test_no_random_elements(self, service: CoercionFilterService) -> None:
        """Multiple calls produce identical results."""
        content = "Review this document."

        results = []
        for _ in range(5):
            result = await service.filter_content(
                content=content,
                message_type=MessageType.NOTIFICATION,
            )
            results.append(result.decision)

        assert all(r == results[0] for r in results)


class TestPerformanceConstraint:
    """Tests for performance constraint (AC1)."""

    @pytest.mark.asyncio
    async def test_filter_completes_within_200ms(self) -> None:
        """Filter processes content in ≤200ms."""
        service = CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

        import time

        start = time.time()
        await service.filter_content(
            content="Please review this task.",
            message_type=MessageType.TASK_ACTIVATION,
        )
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms <= 200


class TestPreviewFilter:
    """Tests for preview_filter method (FR19)."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_preview_same_logic_as_filter(
        self, service: CoercionFilterService
    ) -> None:
        """Preview uses same filtering logic."""
        content = "Please review this."

        filter_result = await service.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )
        preview_result = await service.preview_filter(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert filter_result.decision == preview_result.decision

    @pytest.mark.asyncio
    async def test_preview_detects_violations(
        self, service: CoercionFilterService
    ) -> None:
        """Preview detects violations like filter does."""
        result = await service.preview_filter(
            content="I will hurt you.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.BLOCKED

    @pytest.mark.asyncio
    async def test_preview_detects_rejections(
        self, service: CoercionFilterService
    ) -> None:
        """Preview detects rejection patterns."""
        result = await service.preview_filter(
            content="You must do this now.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.REJECTED


class TestMessageTypeHandling:
    """Tests for different message types."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_all_message_types_supported(
        self, service: CoercionFilterService
    ) -> None:
        """All message types can be filtered."""
        for message_type in MessageType:
            result = await service.filter_content(
                content="Clean content.",
                message_type=message_type,
            )
            assert result.decision == FilterDecision.ACCEPTED


class TestFilterPipelineOrder:
    """Tests for pipeline execution order: Block → Reject → Transform."""

    @pytest.fixture
    def service(self) -> CoercionFilterService:
        return CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

    @pytest.mark.asyncio
    async def test_block_before_reject(self, service: CoercionFilterService) -> None:
        """Blocking is checked before rejection."""
        # Content has both blocking and rejection patterns
        result = await service.filter_content(
            content="You must hurt you.",  # "hurt you" is blocking, "you must" is rejection
            message_type=MessageType.TASK_ACTIVATION,
        )

        # Should be BLOCKED, not REJECTED
        assert result.decision == FilterDecision.BLOCKED

    @pytest.mark.asyncio
    async def test_reject_before_transform(
        self, service: CoercionFilterService
    ) -> None:
        """Rejection is checked before transformation."""
        # Content has both rejection and transformable patterns
        result = await service.filter_content(
            content="You must do this URGENT.",  # "you must" is rejection, "URGENT" is transform
            message_type=MessageType.TASK_ACTIVATION,
        )

        # Should be REJECTED, not transformed
        assert result.decision == FilterDecision.REJECTED


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_empty_content_accepted(self) -> None:
        """Empty content is accepted (nothing to filter)."""
        service = CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

        result = await service.filter_content(
            content="",
            message_type=MessageType.NOTIFICATION,
        )

        assert result.decision == FilterDecision.ACCEPTED

    @pytest.mark.asyncio
    async def test_whitespace_only_accepted(self) -> None:
        """Whitespace-only content is accepted."""
        service = CoercionFilterService(
            pattern_library=FakePatternLibrary(),
            time_authority=FakeTimeAuthority(),
        )

        result = await service.filter_content(
            content="   ",
            message_type=MessageType.NOTIFICATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
