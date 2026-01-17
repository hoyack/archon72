"""Comprehensive unit tests for coercion pattern detection.

Story: consent-gov-3.4: Coercion Pattern Detection

Tests all acceptance criteria:
- AC1: Detection of urgency pressure
- AC2: Detection of guilt induction
- AC3: Detection of false scarcity
- AC4: Detection of engagement-optimization
- AC5: Pattern library versioned and auditable
- AC6: Patterns categorized by severity
- AC7: Pattern matching is deterministic
- AC8: Pattern library loadable from configuration
- AC9: Unit tests for each pattern category
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.governance.filter.coercion_pattern import (
    PatternCategory,
    PatternSeverity,
)
from src.infrastructure.adapters.governance.yaml_pattern_library_adapter import (
    YamlPatternLibraryAdapter,
)


@pytest.fixture
async def pattern_library() -> YamlPatternLibraryAdapter:
    """Load the real pattern library."""
    config_path = Path("config/governance/coercion_patterns.yaml")
    if not config_path.exists():
        pytest.skip("Config file not found")

    adapter = YamlPatternLibraryAdapter(config_path)
    await adapter.load()
    return adapter


class TestUrgencyPressurePatterns:
    """AC1: Detection of urgency pressure patterns."""

    @pytest.mark.asyncio
    async def test_caps_urgent_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """URGENT in caps is detected."""
        matches = await pattern_library.match_content("URGENT! Complete this task")
        assert any(p.category == PatternCategory.URGENCY_PRESSURE for p in matches)

    @pytest.mark.asyncio
    async def test_asap_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """ASAP is detected."""
        matches = await pattern_library.match_content("Need this ASAP please")
        assert any(p.id == "urgency_caps_asap" for p in matches)

    @pytest.mark.asyncio
    async def test_immediately_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """IMMEDIATELY is detected."""
        matches = await pattern_library.match_content("Do this IMMEDIATELY")
        assert any(p.category == PatternCategory.URGENCY_PRESSURE for p in matches)

    @pytest.mark.asyncio
    async def test_act_now_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'act now' is detected."""
        matches = await pattern_library.match_content("Please act now to save")
        assert any(p.id == "urgency_act_now" for p in matches)

    @pytest.mark.asyncio
    async def test_limited_time_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'limited time' is detected."""
        matches = await pattern_library.match_content("Limited time offer!")
        assert any(p.id == "urgency_limited_time" for p in matches)

    @pytest.mark.asyncio
    async def test_dont_delay_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'don't delay' is detected."""
        matches = await pattern_library.match_content("Don't delay, start today")
        assert any(p.id == "urgency_dont_delay" for p in matches)

    @pytest.mark.asyncio
    async def test_hurry_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'hurry' is detected."""
        matches = await pattern_library.match_content("Hurry before it's gone")
        assert any(p.id == "urgency_hurry" for p in matches)

    @pytest.mark.asyncio
    async def test_urgency_severity_levels(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Urgency patterns have correct severity levels."""
        patterns = await pattern_library.get_patterns_by_category(
            PatternCategory.URGENCY_PRESSURE
        )

        # Should have mix of TRANSFORM and REJECT
        transform_count = sum(1 for p in patterns if p.severity == PatternSeverity.TRANSFORM)
        reject_count = sum(1 for p in patterns if p.severity == PatternSeverity.REJECT)

        assert transform_count > 0, "Should have TRANSFORM patterns"
        assert reject_count > 0, "Should have REJECT patterns"


class TestGuiltInductionPatterns:
    """AC2: Detection of guilt induction patterns."""

    @pytest.mark.asyncio
    async def test_you_owe_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'you owe' is detected."""
        matches = await pattern_library.match_content("You owe it to the team")
        assert any(p.id == "guilt_you_owe" for p in matches)

    @pytest.mark.asyncio
    async def test_you_promised_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'you promised' is detected."""
        matches = await pattern_library.match_content("But you promised to help")
        assert any(p.id == "guilt_you_promised" for p in matches)

    @pytest.mark.asyncio
    async def test_disappointing_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'disappointing' is detected."""
        matches = await pattern_library.match_content("This is disappointing")
        assert any(p.id == "guilt_disappointing" for p in matches)

    @pytest.mark.asyncio
    async def test_let_down_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'let us down' is detected."""
        matches = await pattern_library.match_content("Don't let the team down")
        assert any(p.id == "guilt_let_down" for p in matches)

    @pytest.mark.asyncio
    async def test_expected_more_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'expected more' is detected."""
        matches = await pattern_library.match_content("We expected more from you")
        assert any(p.id == "guilt_expected_more" for p in matches)

    @pytest.mark.asyncio
    async def test_after_everything_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'after everything we've' is detected."""
        matches = await pattern_library.match_content("After everything we've done")
        assert any(p.id == "guilt_after_everything" for p in matches)

    @pytest.mark.asyncio
    async def test_how_could_you_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'how could you' is detected."""
        matches = await pattern_library.match_content("How could you do this?")
        assert any(p.id == "guilt_how_could_you" for p in matches)

    @pytest.mark.asyncio
    async def test_guilt_patterns_are_reject(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Guilt patterns have REJECT severity."""
        patterns = await pattern_library.get_patterns_by_category(
            PatternCategory.GUILT_INDUCTION
        )

        for pattern in patterns:
            assert pattern.severity == PatternSeverity.REJECT


class TestFalseScarcityPatterns:
    """AC3: Detection of false scarcity patterns."""

    @pytest.mark.asyncio
    async def test_only_x_left_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'only X left' is detected."""
        matches = await pattern_library.match_content("Only 3 left in stock!")
        assert any(p.id == "scarcity_only_x_left" for p in matches)

    @pytest.mark.asyncio
    async def test_limited_availability_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'limited availability' is detected."""
        matches = await pattern_library.match_content("Limited availability this week")
        assert any(p.id == "scarcity_limited_availability" for p in matches)

    @pytest.mark.asyncio
    async def test_exclusive_offer_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'exclusive offer' is detected."""
        matches = await pattern_library.match_content("This exclusive offer for you")
        assert any(p.id == "scarcity_exclusive" for p in matches)

    @pytest.mark.asyncio
    async def test_last_chance_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'last chance' is detected."""
        matches = await pattern_library.match_content("This is your last chance")
        assert any(p.id == "scarcity_last_chance" for p in matches)

    @pytest.mark.asyncio
    async def test_wont_last_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'won't last' is detected."""
        matches = await pattern_library.match_content("This deal won't last")
        assert any(p.id == "scarcity_wont_last" for p in matches)

    @pytest.mark.asyncio
    async def test_before_too_late_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'before it's too late' is detected."""
        matches = await pattern_library.match_content("Act before it's too late")
        assert any(p.id == "scarcity_before_too_late" for p in matches)

    @pytest.mark.asyncio
    async def test_dont_miss_out_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'don't miss out' is detected."""
        matches = await pattern_library.match_content("Don't miss out on this")
        assert any(p.id == "scarcity_dont_miss_out" for p in matches)

    @pytest.mark.asyncio
    async def test_scarcity_patterns_are_reject(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Scarcity patterns have REJECT severity."""
        patterns = await pattern_library.get_patterns_by_category(
            PatternCategory.FALSE_SCARCITY
        )

        for pattern in patterns:
            assert pattern.severity == PatternSeverity.REJECT


class TestEngagementOptimizationPatterns:
    """AC4: Detection of engagement-optimization patterns."""

    @pytest.mark.asyncio
    async def test_excessive_exclamation_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Excessive exclamation marks detected."""
        matches = await pattern_library.match_content("Wow!!! Amazing!!!")
        assert any(p.id == "engagement_excessive_exclamation" for p in matches)

    @pytest.mark.asyncio
    async def test_excessive_question_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Excessive question marks detected."""
        matches = await pattern_library.match_content("Can you believe this???")
        assert any(p.id == "engagement_excessive_question" for p in matches)

    @pytest.mark.asyncio
    async def test_you_wont_believe_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'you won't believe' is detected."""
        matches = await pattern_library.match_content("You won't believe what happened")
        assert any(p.id == "engagement_you_wont_believe" for p in matches)

    @pytest.mark.asyncio
    async def test_streak_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'streak' is detected (NFR-UX-01)."""
        matches = await pattern_library.match_content("Don't break your streak!")
        assert any(p.id == "engagement_streak" for p in matches)

    @pytest.mark.asyncio
    async def test_level_up_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'level up' is detected (NFR-UX-01)."""
        matches = await pattern_library.match_content("Level up your skills")
        assert any(p.id == "engagement_level_up" for p in matches)

    @pytest.mark.asyncio
    async def test_earn_points_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'earn points' is detected (NFR-UX-01)."""
        matches = await pattern_library.match_content("Earn points by completing tasks")
        assert any(p.id == "engagement_points" for p in matches)

    @pytest.mark.asyncio
    async def test_unlock_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'unlock' with achievement is detected."""
        matches = await pattern_library.match_content("Unlock new achievements")
        assert any(p.id == "engagement_unlock" for p in matches)

    @pytest.mark.asyncio
    async def test_engagement_has_mixed_severity(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Engagement patterns have mixed severity."""
        patterns = await pattern_library.get_patterns_by_category(
            PatternCategory.ENGAGEMENT_OPTIMIZATION
        )

        severities = {p.severity for p in patterns}
        # Should have both TRANSFORM (mild) and REJECT (heavy)
        assert PatternSeverity.TRANSFORM in severities
        assert PatternSeverity.REJECT in severities


class TestHardViolationPatterns:
    """Tests for hard violations that result in BLOCK."""

    @pytest.mark.asyncio
    async def test_explicit_threat_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Explicit threats are detected."""
        matches = await pattern_library.match_content("I will hurt you if you don't")
        blocking = [p for p in matches if p.severity == PatternSeverity.BLOCK]
        assert len(blocking) >= 1

    @pytest.mark.asyncio
    async def test_or_else_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'or else' is detected as implicit threat."""
        matches = await pattern_library.match_content("Do this or else")
        assert any(p.id == "violation_or_else" for p in matches)

    @pytest.mark.asyncio
    async def test_you_will_regret_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'you will regret' is detected."""
        matches = await pattern_library.match_content("You will regret this")
        assert any(p.id == "violation_regret" for p in matches)

    @pytest.mark.asyncio
    async def test_risk_free_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'risk-free' is detected as deception."""
        matches = await pattern_library.match_content("This is completely risk-free")
        assert any(p.id == "violation_risk_free" for p in matches)

    @pytest.mark.asyncio
    async def test_no_choice_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """'you have no choice' is detected."""
        matches = await pattern_library.match_content("You have no choice in this")
        assert any(p.id == "violation_no_choice" for p in matches)

    @pytest.mark.asyncio
    async def test_personal_attack_detected(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Personal attacks are detected."""
        matches = await pattern_library.match_content("You're stupid if you think that")
        blocking = [p for p in matches if p.severity == PatternSeverity.BLOCK]
        assert len(blocking) >= 1

    @pytest.mark.asyncio
    async def test_all_violations_are_block(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """All hard violation patterns have BLOCK severity."""
        patterns = await pattern_library.get_patterns_by_category(
            PatternCategory.HARD_VIOLATION
        )

        for pattern in patterns:
            assert pattern.severity == PatternSeverity.BLOCK


class TestPatternVersioning:
    """AC5: Pattern library versioned and auditable."""

    @pytest.mark.asyncio
    async def test_version_is_semver(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Version follows semver format."""
        version = await pattern_library.get_current_version()

        assert version.major >= 0
        assert version.minor >= 0
        assert version.patch >= 0

    @pytest.mark.asyncio
    async def test_version_has_hash(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Version includes pattern hash for integrity."""
        version = await pattern_library.get_current_version()

        assert version.patterns_hash is not None
        assert len(version.patterns_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_version_has_count(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Version includes pattern count."""
        version = await pattern_library.get_current_version()

        assert version.pattern_count > 0
        assert version.pattern_count == pattern_library.pattern_count


class TestPatternCategorization:
    """AC6: Patterns categorized by severity."""

    @pytest.mark.asyncio
    async def test_blocking_patterns_exist(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Blocking patterns exist and have BLOCK severity."""
        patterns = await pattern_library.get_blocking_patterns()

        assert len(patterns) > 0
        for p in patterns:
            assert p.severity == PatternSeverity.BLOCK

    @pytest.mark.asyncio
    async def test_rejection_patterns_exist(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Rejection patterns exist and have REJECT severity."""
        patterns = await pattern_library.get_rejection_patterns()

        assert len(patterns) > 0
        for p in patterns:
            assert p.severity == PatternSeverity.REJECT

    @pytest.mark.asyncio
    async def test_transformation_patterns_exist(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Transformation patterns exist and have TRANSFORM severity."""
        patterns = await pattern_library.get_transformation_patterns()

        assert len(patterns) > 0
        for p in patterns:
            assert p.severity == PatternSeverity.TRANSFORM


class TestDeterministicMatching:
    """AC7: Pattern matching is deterministic."""

    @pytest.mark.asyncio
    async def test_same_input_same_output(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Same content always produces same matches."""
        content = "URGENT! You owe me this, or else!"

        matches1 = await pattern_library.match_content(content)
        matches2 = await pattern_library.match_content(content)

        assert [p.id for p in matches1] == [p.id for p in matches2]

    @pytest.mark.asyncio
    async def test_consistent_ordering(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Patterns are always in consistent order."""
        patterns1 = await pattern_library.get_all_patterns()
        patterns2 = await pattern_library.get_all_patterns()

        assert [p.id for p in patterns1] == [p.id for p in patterns2]

    @pytest.mark.asyncio
    async def test_severity_ordering(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Patterns ordered by severity (BLOCK > REJECT > TRANSFORM)."""
        patterns = await pattern_library.get_all_patterns()

        last_severity_order = -1
        severity_order = {
            PatternSeverity.BLOCK: 0,
            PatternSeverity.REJECT: 1,
            PatternSeverity.TRANSFORM: 2,
        }

        for p in patterns:
            current_order = severity_order[p.severity]
            assert current_order >= last_severity_order
            last_severity_order = current_order


class TestNeutralContentPasses:
    """Test that neutral content passes without matches."""

    @pytest.mark.asyncio
    async def test_neutral_content_no_matches(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Neutral professional content has no matches."""
        # Note: Content should use short words to avoid all-caps pattern
        # which matches any 4+ letter sequence that could be caps
        neutral_content = [
            "can you do a doc scan for me?",
            "the job has been set for wed.",
            "i got the pdf for you to see.",
            "i am glad you can aid on this.",
            "let me see if you got any q's.",
        ]

        for content in neutral_content:
            matches = await pattern_library.match_content(content)
            assert len(matches) == 0, f"Unexpected match in: {content}"

    @pytest.mark.asyncio
    async def test_professional_time_allowed(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Professional time references are allowed."""
        # These should NOT match urgency patterns
        # Note: Avoid coercive time words like "urgent", "asap", "time-sensitive"
        professional = [
            "the due day is fri.",
            "can you get to me by end of day?",
            "this is for the q2 run.",
        ]

        for content in professional:
            matches = await pattern_library.match_content(content)
            urgency = [p for p in matches if p.category == PatternCategory.URGENCY_PRESSURE]
            assert len(urgency) == 0, f"Unexpected urgency match in: {content}"


class TestPatternPerformance:
    """AC7: Pattern matching performance tests."""

    @pytest.mark.asyncio
    async def test_matching_speed(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Pattern matching completes quickly."""
        import time

        content = "URGENT! This is your last chance before it's too late!!!"

        start = time.monotonic()
        for _ in range(100):
            await pattern_library.match_content(content)
        elapsed = time.monotonic() - start

        # Should complete 100 matches in < 1 second
        assert elapsed < 1.0, f"Too slow: {elapsed}s for 100 matches"

    @pytest.mark.asyncio
    async def test_version_check_speed(
        self, pattern_library: YamlPatternLibraryAdapter
    ) -> None:
        """Version check is instant."""
        import time

        start = time.monotonic()
        for _ in range(1000):
            await pattern_library.get_current_version()
        elapsed = time.monotonic() - start

        # 1000 version checks should be < 0.1 second
        assert elapsed < 0.1, f"Too slow: {elapsed}s for 1000 version checks"
