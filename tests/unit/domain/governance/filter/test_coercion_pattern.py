"""Unit tests for CoercionPattern domain model.

Story: consent-gov-3.4: Coercion Pattern Detection

Tests for:
- PatternSeverity enum
- PatternCategory enum
- CoercionPattern value object
- PatternLibraryVersion value object
- Pattern matching (deterministic per AC7)
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.domain.governance.filter.coercion_pattern import (
    CoercionPattern,
    PatternCategory,
    PatternLibraryVersion,
    PatternSeverity,
)


class TestPatternSeverity:
    """Tests for PatternSeverity enum."""

    def test_transform_is_sendable(self) -> None:
        """TRANSFORM severity allows content to be sent after action."""
        assert PatternSeverity.TRANSFORM.is_sendable_after_action is True

    def test_reject_not_sendable(self) -> None:
        """REJECT severity does not allow content to be sent."""
        assert PatternSeverity.REJECT.is_sendable_after_action is False

    def test_block_not_sendable(self) -> None:
        """BLOCK severity does not allow content to be sent."""
        assert PatternSeverity.BLOCK.is_sendable_after_action is False

    def test_transform_no_human_action(self) -> None:
        """TRANSFORM does not require human action."""
        assert PatternSeverity.TRANSFORM.requires_human_action is False

    def test_reject_requires_human_action(self) -> None:
        """REJECT requires human action."""
        assert PatternSeverity.REJECT.requires_human_action is True

    def test_block_requires_human_action(self) -> None:
        """BLOCK requires human action."""
        assert PatternSeverity.BLOCK.requires_human_action is True


class TestPatternCategory:
    """Tests for PatternCategory enum."""

    def test_urgency_pressure_description(self) -> None:
        """Urgency pressure has correct description."""
        assert "time pressure" in PatternCategory.URGENCY_PRESSURE.description.lower()

    def test_guilt_induction_description(self) -> None:
        """Guilt induction has correct description."""
        assert "guilt" in PatternCategory.GUILT_INDUCTION.description.lower()

    def test_false_scarcity_description(self) -> None:
        """False scarcity has correct description."""
        assert "scarcity" in PatternCategory.FALSE_SCARCITY.description.lower()

    def test_engagement_optimization_description(self) -> None:
        """Engagement optimization has correct description."""
        assert (
            "engagement" in PatternCategory.ENGAGEMENT_OPTIMIZATION.description.lower()
        )

    def test_hard_violation_description(self) -> None:
        """Hard violation has correct description."""
        assert "cannot" in PatternCategory.HARD_VIOLATION.description.lower()

    def test_urgency_default_transform(self) -> None:
        """Urgency pressure defaults to TRANSFORM."""
        assert (
            PatternCategory.URGENCY_PRESSURE.default_severity
            == PatternSeverity.TRANSFORM
        )

    def test_guilt_default_reject(self) -> None:
        """Guilt induction defaults to REJECT."""
        assert (
            PatternCategory.GUILT_INDUCTION.default_severity == PatternSeverity.REJECT
        )

    def test_scarcity_default_reject(self) -> None:
        """False scarcity defaults to REJECT."""
        assert PatternCategory.FALSE_SCARCITY.default_severity == PatternSeverity.REJECT

    def test_engagement_default_transform(self) -> None:
        """Engagement optimization defaults to TRANSFORM."""
        assert (
            PatternCategory.ENGAGEMENT_OPTIMIZATION.default_severity
            == PatternSeverity.TRANSFORM
        )

    def test_violation_default_block(self) -> None:
        """Hard violation defaults to BLOCK."""
        assert PatternCategory.HARD_VIOLATION.default_severity == PatternSeverity.BLOCK


class TestCoercionPattern:
    """Tests for CoercionPattern value object."""

    @pytest.fixture
    def transform_pattern(self) -> CoercionPattern:
        """Create a TRANSFORM severity pattern."""
        return CoercionPattern(
            id="urgency_caps_urgent",
            category=PatternCategory.URGENCY_PRESSURE,
            severity=PatternSeverity.TRANSFORM,
            pattern=r"\bURGENT\b",
            description="Caps-lock URGENT creates artificial pressure",
            replacement="",
        )

    @pytest.fixture
    def reject_pattern(self) -> CoercionPattern:
        """Create a REJECT severity pattern."""
        return CoercionPattern(
            id="guilt_you_owe",
            category=PatternCategory.GUILT_INDUCTION,
            severity=PatternSeverity.REJECT,
            pattern=r"\byou\s+owe\b",
            description="Creates obligation through guilt",
            rejection_reason="guilt_induction",
        )

    @pytest.fixture
    def block_pattern(self) -> CoercionPattern:
        """Create a BLOCK severity pattern."""
        return CoercionPattern(
            id="violation_explicit_threat",
            category=PatternCategory.HARD_VIOLATION,
            severity=PatternSeverity.BLOCK,
            pattern=r"\b(hurt|harm|punish)\s+(you|your)\b",
            description="Explicit threat of harm",
            violation_type="explicit_threat",
        )

    def test_pattern_requires_id(self) -> None:
        """Pattern ID is required."""
        with pytest.raises(ValueError, match="Pattern ID is required"):
            CoercionPattern(
                id="",
                category=PatternCategory.URGENCY_PRESSURE,
                severity=PatternSeverity.TRANSFORM,
                pattern=r"\bURGENT\b",
                description="Test",
            )

    def test_pattern_requires_pattern(self) -> None:
        """Pattern regex is required."""
        with pytest.raises(ValueError, match="Pattern regex is required"):
            CoercionPattern(
                id="test",
                category=PatternCategory.URGENCY_PRESSURE,
                severity=PatternSeverity.TRANSFORM,
                pattern="",
                description="Test",
            )

    def test_pattern_requires_description(self) -> None:
        """Pattern description is required."""
        with pytest.raises(ValueError, match="Pattern description is required"):
            CoercionPattern(
                id="test",
                category=PatternCategory.URGENCY_PRESSURE,
                severity=PatternSeverity.TRANSFORM,
                pattern=r"\btest\b",
                description="",
            )

    def test_invalid_regex_rejected(self) -> None:
        """Invalid regex patterns are rejected."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            CoercionPattern(
                id="test",
                category=PatternCategory.URGENCY_PRESSURE,
                severity=PatternSeverity.TRANSFORM,
                pattern=r"[invalid",  # Unclosed bracket
                description="Test",
            )

    def test_transform_default_replacement(self) -> None:
        """TRANSFORM patterns get empty string replacement by default."""
        pattern = CoercionPattern(
            id="test",
            category=PatternCategory.URGENCY_PRESSURE,
            severity=PatternSeverity.TRANSFORM,
            pattern=r"\btest\b",
            description="Test",
            replacement=None,  # Explicitly None
        )
        assert pattern.replacement == ""

    def test_matches_case_insensitive(self, transform_pattern: CoercionPattern) -> None:
        """Pattern matching is case-insensitive."""
        assert transform_pattern.matches("URGENT task") is True
        assert transform_pattern.matches("urgent task") is True
        assert transform_pattern.matches("Urgent task") is True

    def test_matches_returns_false_no_match(
        self, transform_pattern: CoercionPattern
    ) -> None:
        """Pattern returns False when no match."""
        assert transform_pattern.matches("Please review this") is False

    def test_extract_match(self, transform_pattern: CoercionPattern) -> None:
        """Extract matched text from content."""
        assert transform_pattern.extract_match("This is URGENT!") == "URGENT"

    def test_extract_match_none(self, transform_pattern: CoercionPattern) -> None:
        """Extract returns None when no match."""
        assert transform_pattern.extract_match("This is normal") is None

    def test_find_all_matches(self) -> None:
        """Find all matches in content."""
        pattern = CoercionPattern(
            id="test_multi",
            category=PatternCategory.URGENCY_PRESSURE,
            severity=PatternSeverity.TRANSFORM,
            pattern=r"[!]{2,}",
            description="Multiple exclamation marks",
            replacement="!",
        )
        matches = pattern.find_all_matches("Wow!! Amazing!!! Great!!!!")
        assert len(matches) == 3

    def test_find_match_positions(self) -> None:
        """Find positions of all matches."""
        pattern = CoercionPattern(
            id="test_pos",
            category=PatternCategory.URGENCY_PRESSURE,
            severity=PatternSeverity.TRANSFORM,
            pattern=r"\bURGENT\b",
            description="URGENT",
            replacement="",
        )
        positions = pattern.find_match_positions("URGENT: This is URGENT!")
        assert len(positions) == 2
        assert positions[0] == (0, 6)  # First URGENT

    def test_apply_transformation(self, transform_pattern: CoercionPattern) -> None:
        """Apply transformation to content."""
        result = transform_pattern.apply("URGENT: Complete this task")
        assert result == ": Complete this task"

    def test_apply_with_replacement(self) -> None:
        """Apply transformation with non-empty replacement."""
        pattern = CoercionPattern(
            id="urgency_act_now",
            category=PatternCategory.URGENCY_PRESSURE,
            severity=PatternSeverity.TRANSFORM,
            pattern=r"\bact\s+now\b",
            description="Act now creates time pressure",
            replacement="when convenient",
        )
        result = pattern.apply("Please act now to complete")
        assert result == "Please when convenient to complete"

    def test_apply_fails_for_reject(self, reject_pattern: CoercionPattern) -> None:
        """Cannot apply transformation to REJECT patterns."""
        with pytest.raises(ValueError, match="Can only apply TRANSFORM patterns"):
            reject_pattern.apply("You owe me this")

    def test_apply_fails_for_block(self, block_pattern: CoercionPattern) -> None:
        """Cannot apply transformation to BLOCK patterns."""
        with pytest.raises(ValueError, match="Can only apply TRANSFORM patterns"):
            block_pattern.apply("I will hurt you")

    def test_count_matches(self) -> None:
        """Count number of matches."""
        pattern = CoercionPattern(
            id="test_count",
            category=PatternCategory.URGENCY_PRESSURE,
            severity=PatternSeverity.TRANSFORM,
            pattern=r"\bURGENT\b",
            description="URGENT",
            replacement="",
        )
        assert pattern.count_matches("URGENT URGENT URGENT") == 3
        assert pattern.count_matches("No urgency here") == 0

    def test_pattern_is_frozen(self, transform_pattern: CoercionPattern) -> None:
        """Pattern is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            transform_pattern.id = "new_id"  # type: ignore


class TestPatternLibraryVersion:
    """Tests for PatternLibraryVersion value object."""

    @pytest.fixture
    def test_time(self) -> datetime:
        """Fixed test time for deterministic tests."""
        from datetime import timezone

        return datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_valid_version(self, test_time: datetime) -> None:
        """Valid version string accepted."""
        version = PatternLibraryVersion(
            version="1.2.3",
            patterns_hash="abc123",
            pattern_count=10,
            loaded_at=test_time,
        )
        assert version.version == "1.2.3"
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.loaded_at == test_time

    def test_version_required(self, test_time: datetime) -> None:
        """Version string is required."""
        with pytest.raises(ValueError, match="Version is required"):
            PatternLibraryVersion(
                version="",
                patterns_hash="abc123",
                pattern_count=10,
                loaded_at=test_time,
            )

    def test_patterns_hash_required(self, test_time: datetime) -> None:
        """Patterns hash is required."""
        with pytest.raises(ValueError, match="Patterns hash is required"):
            PatternLibraryVersion(
                version="1.0.0",
                patterns_hash="",
                pattern_count=10,
                loaded_at=test_time,
            )

    def test_invalid_version_format(self, test_time: datetime) -> None:
        """Invalid version format rejected."""
        with pytest.raises(ValueError, match="semver format"):
            PatternLibraryVersion(
                version="1.0",  # Missing patch version
                patterns_hash="abc123",
                pattern_count=10,
                loaded_at=test_time,
            )

    def test_version_properties(self, test_time: datetime) -> None:
        """Version properties extract correctly."""
        version = PatternLibraryVersion(
            version="10.20.30",
            patterns_hash="abc123",
            pattern_count=100,
            loaded_at=test_time,
        )
        assert version.major == 10
        assert version.minor == 20
        assert version.patch == 30


class TestDeterministicMatching:
    """Tests for deterministic pattern matching (AC7)."""

    @pytest.fixture
    def patterns(self) -> list[CoercionPattern]:
        """Create a set of test patterns."""
        return [
            CoercionPattern(
                id="urgency_1",
                category=PatternCategory.URGENCY_PRESSURE,
                severity=PatternSeverity.TRANSFORM,
                pattern=r"\bURGENT\b",
                description="URGENT",
                replacement="",
            ),
            CoercionPattern(
                id="guilt_1",
                category=PatternCategory.GUILT_INDUCTION,
                severity=PatternSeverity.REJECT,
                pattern=r"\byou\s+owe\b",
                description="You owe",
            ),
            CoercionPattern(
                id="block_1",
                category=PatternCategory.HARD_VIOLATION,
                severity=PatternSeverity.BLOCK,
                pattern=r"\bor\s+else\b",
                description="Or else",
            ),
        ]

    def test_same_content_same_matches(self, patterns: list[CoercionPattern]) -> None:
        """Same content always matches same patterns (AC7)."""
        content = "URGENT! You owe me, or else!"

        # Run matching twice
        matches1 = [p for p in patterns if p.matches(content)]
        matches2 = [p for p in patterns if p.matches(content)]

        assert matches1 == matches2
        assert len(matches1) == 3

    def test_consistent_extraction(self, patterns: list[CoercionPattern]) -> None:
        """Same content always extracts same text."""
        content = "This is URGENT!"

        pattern = patterns[0]
        extract1 = pattern.extract_match(content)
        extract2 = pattern.extract_match(content)

        assert extract1 == extract2 == "URGENT"

    def test_consistent_transformation(self, patterns: list[CoercionPattern]) -> None:
        """Same content always transforms the same way."""
        content = "URGENT! Please review"

        pattern = patterns[0]
        result1 = pattern.apply(content)
        result2 = pattern.apply(content)

        assert result1 == result2 == "! Please review"

    def test_order_independent_matching(self, patterns: list[CoercionPattern]) -> None:
        """Pattern matching is independent of iteration order."""
        content = "URGENT!"

        # Match with patterns in original order
        matches_forward = [p.id for p in patterns if p.matches(content)]

        # Match with patterns in reverse order
        matches_reverse = [p.id for p in reversed(patterns) if p.matches(content)]

        # Same patterns match (order may differ)
        assert set(matches_forward) == set(matches_reverse)
