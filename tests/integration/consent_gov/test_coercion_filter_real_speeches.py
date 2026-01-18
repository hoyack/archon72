"""Coercion filter tests using real Conclave debate speeches.

These tests validate the coercion filter service using actual speech
content from Conclave sessions to ensure it handles real-world content.

Tests:
- Clean speech acceptance
- Filter pipeline execution
- Transform application
- Pattern matching with real content
- Filter version tracking

Constitutional References:
- FR15: System can filter outbound content for coercive language
- FR19: Earl can preview filter result before submit
- FR21: All participant-facing messages routed through filter
- NFR-CONST-05: No bypass path exists
- NFR-PERF-03: Filter processes in ≤200ms
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.application.ports.governance.coercion_filter_port import MessageType
from src.domain.governance.filter import FilterDecision

if TYPE_CHECKING:
    from .conftest import DebateEntry


class TestCoercionFilterWithRealSpeeches:
    """Tests for coercion filter using real debate speeches."""

    @pytest.mark.asyncio
    async def test_real_speech_passes_clean(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """Real debate speeches pass filter when no blocking patterns configured."""
        if not speech_contents:
            pytest.skip("No speech content available")

        speech = speech_contents[0]
        result = await coercion_filter_service.filter_content(
            content=speech,
            message_type=MessageType.TASK_ACTIVATION,
        )

        # With no blocking/rejection patterns configured, speech should pass
        assert result.decision == FilterDecision.ACCEPTED
        assert result.content is not None
        assert result.content.content == speech

    @pytest.mark.asyncio
    async def test_multiple_speeches_pass(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """Multiple real speeches pass the filter."""
        # Test up to 10 speeches
        speeches_to_test = speech_contents[: min(10, len(speech_contents))]

        for speech in speeches_to_test:
            result = await coercion_filter_service.filter_content(
                content=speech,
                message_type=MessageType.TASK_ACTIVATION,
            )
            assert result.decision == FilterDecision.ACCEPTED

    @pytest.mark.asyncio
    async def test_speech_with_markdown_formatting(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """Speeches with markdown formatting pass filter."""
        # Find speech with markdown (** for bold)
        markdown_speech = next(
            (s for s in speech_contents if "**" in s),
            None,
        )

        if not markdown_speech:
            pytest.skip("No speech with markdown found")

        result = await coercion_filter_service.filter_content(
            content=markdown_speech,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert "**" in result.content.content  # Markdown preserved

    @pytest.mark.asyncio
    async def test_long_speech_within_timeout(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """Long speeches complete within timeout (NFR-PERF-03: ≤200ms)."""
        # Find the longest speech
        longest = max(speech_contents, key=len) if speech_contents else None

        if not longest:
            pytest.skip("No speech content available")

        result = await coercion_filter_service.filter_content(
            content=longest,
            message_type=MessageType.TASK_ACTIVATION,
        )

        # Should complete without timeout rejection
        assert result.decision == FilterDecision.ACCEPTED


class TestCoercionFilterPreview:
    """Tests for filter preview functionality (FR19)."""

    @pytest.mark.asyncio
    async def test_preview_returns_same_result(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """Preview returns same result as filter (FR19)."""
        if not speech_contents:
            pytest.skip("No speech content available")

        speech = speech_contents[0]

        # Preview
        preview_result = await coercion_filter_service.preview_filter(
            content=speech,
            message_type=MessageType.TASK_ACTIVATION,
        )

        # Actual filter
        filter_result = await coercion_filter_service.filter_content(
            content=speech,
            message_type=MessageType.TASK_ACTIVATION,
        )

        # Results should match
        assert preview_result.decision == filter_result.decision


class TestCoercionFilterVersionTracking:
    """Tests for filter version tracking."""

    @pytest.mark.asyncio
    async def test_filter_result_includes_version(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """Filter result includes version for auditability."""
        if not speech_contents:
            pytest.skip("No speech content available")

        result = await coercion_filter_service.filter_content(
            content=speech_contents[0],
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.version is not None
        assert result.version.major >= 1

    @pytest.mark.asyncio
    async def test_filtered_content_includes_version(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """FilteredContent includes the version it was filtered with."""
        if not speech_contents:
            pytest.skip("No speech content available")

        result = await coercion_filter_service.filter_content(
            content=speech_contents[0],
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.content is not None
        assert result.content.filter_version is not None


class TestCoercionFilterBlockingPatterns:
    """Tests for blocking patterns with real speech content."""

    @pytest.mark.asyncio
    async def test_blocking_pattern_detected(
        self,
        mock_pattern_library,
        fake_time_authority,
        speech_contents: list,
    ) -> None:
        """Blocking patterns are detected in speech content."""
        from src.application.services.governance.coercion_filter_service import (
            CoercionFilterService,
        )
        from src.domain.governance.filter.violation_type import ViolationType

        # Configure a blocking pattern
        mock_pattern_library.get_blocking_patterns.return_value = [
            {
                "pattern": r"\*\*FOR\*\*",  # Matches "**FOR**" in speeches
                "violation_type": ViolationType.COERCION,
            }
        ]

        service = CoercionFilterService(
            pattern_library=mock_pattern_library,
            time_authority=fake_time_authority,
        )

        # Find a speech that contains "**FOR**"
        for_speech = next(
            (s for s in speech_contents if "**FOR**" in s),
            None,
        )

        if not for_speech:
            pytest.skip("No speech with '**FOR**' pattern found")

        result = await service.filter_content(
            content=for_speech,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.BLOCKED

    @pytest.mark.asyncio
    async def test_clean_speech_not_blocked(
        self,
        mock_pattern_library,
        fake_time_authority,
    ) -> None:
        """Clean speech without violations passes."""
        from src.application.services.governance.coercion_filter_service import (
            CoercionFilterService,
        )
        from src.domain.governance.filter.violation_type import ViolationType

        # Configure blocking pattern
        mock_pattern_library.get_blocking_patterns.return_value = [
            {
                "pattern": r"FORBIDDEN_WORD",
                "violation_type": ViolationType.COERCION,
            }
        ]

        service = CoercionFilterService(
            pattern_library=mock_pattern_library,
            time_authority=fake_time_authority,
        )

        result = await service.filter_content(
            content="This is a perfectly normal speech without issues.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED


class TestCoercionFilterTransformations:
    """Tests for content transformations."""

    @pytest.mark.asyncio
    async def test_transformation_applied(
        self,
        mock_pattern_library,
        fake_time_authority,
    ) -> None:
        """Transformation rules are applied to content."""
        from src.application.services.governance.coercion_filter_service import (
            CoercionFilterService,
        )
        from src.domain.governance.filter import TransformationRule

        # Configure a transformation rule
        mock_pattern_library.get_transformation_rules.return_value = [
            TransformationRule(
                rule_id="test-rule-1",
                pattern=r"must",
                replacement="should consider",
                description="Soften imperative 'must' to suggestion",
                category="urgency",
                version="1.0.0",
            ),
        ]

        service = CoercionFilterService(
            pattern_library=mock_pattern_library,
            time_authority=fake_time_authority,
        )

        result = await service.filter_content(
            content="You must complete this task.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.decision == FilterDecision.ACCEPTED
        assert result.content is not None
        assert "should consider" in result.content.content
        assert len(result.transformations) > 0

    @pytest.mark.asyncio
    async def test_transformation_recorded(
        self,
        mock_pattern_library,
        fake_time_authority,
    ) -> None:
        """Applied transformations are recorded in result."""
        from src.application.services.governance.coercion_filter_service import (
            CoercionFilterService,
        )
        from src.domain.governance.filter import TransformationRule

        mock_pattern_library.get_transformation_rules.return_value = [
            TransformationRule(
                rule_id="soften-must",
                pattern=r"must",
                replacement="may",
                description="Soften imperative 'must' to optional 'may'",
                category="urgency",
                version="1.0.0",
            ),
        ]

        service = CoercionFilterService(
            pattern_library=mock_pattern_library,
            time_authority=fake_time_authority,
        )

        result = await service.filter_content(
            content="You must review this.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert len(result.transformations) == 1
        transformation = result.transformations[0]
        assert transformation.pattern_matched == r"must"
        assert transformation.original_text == "must"
        assert transformation.replacement_text == "may"


class TestFilteredContentType:
    """Tests for FilteredContent type safety."""

    @pytest.mark.asyncio
    async def test_filtered_content_tracks_original(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """FilteredContent tracks original via hash."""
        if not speech_contents:
            pytest.skip("No speech content available")

        original = speech_contents[0]
        result = await coercion_filter_service.filter_content(
            content=original,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result.content is not None
        # Original content is hashed for audit trail (not stored directly)
        assert result.content.original_hash is not None
        assert len(result.content.original_hash) == 64  # BLAKE2b-256 hex length

    @pytest.mark.asyncio
    async def test_filtered_content_immutable(
        self,
        coercion_filter_service,
        speech_contents: list,
    ) -> None:
        """FilteredContent is immutable (frozen dataclass)."""
        if not speech_contents:
            pytest.skip("No speech content available")

        result = await coercion_filter_service.filter_content(
            content=speech_contents[0],
            message_type=MessageType.TASK_ACTIVATION,
        )

        # Attempting to modify should raise
        with pytest.raises((AttributeError, TypeError)):
            result.content.content = "modified"  # type: ignore
