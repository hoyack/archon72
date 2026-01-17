"""Unit tests for Transformation and TransformationRule models.

Tests AC5: Content transformation rules defined for accept outcomes.
"""

import pytest

from src.domain.governance.filter.transformation import Transformation, TransformationRule


class TestTransformationRule:
    """Unit tests for TransformationRule model."""

    def test_create_transformation_rule(self) -> None:
        """TransformationRule can be created with required fields."""
        rule = TransformationRule(
            rule_id="remove_urgency",
            pattern=r"URGENT\!?",
            replacement="",
            description="Removes urgency language",
            category="urgency",
            version="1.0.0",
        )

        assert rule.rule_id == "remove_urgency"
        assert rule.pattern == r"URGENT\!?"
        assert rule.replacement == ""
        assert rule.category == "urgency"

    def test_transformation_rule_immutable(self) -> None:
        """TransformationRule is immutable."""
        from dataclasses import FrozenInstanceError

        rule = TransformationRule(
            rule_id="test",
            pattern=r"test",
            replacement="",
            description="Test rule",
            category="test",
            version="1.0.0",
        )

        with pytest.raises(FrozenInstanceError):
            rule.pattern = r"new_pattern"  # type: ignore

    def test_transformation_rule_requires_rule_id(self) -> None:
        """TransformationRule requires rule_id."""
        with pytest.raises(ValueError, match="Rule ID is required"):
            TransformationRule(
                rule_id="",
                pattern=r"test",
                replacement="",
                description="Test",
                category="test",
                version="1.0.0",
            )

    def test_transformation_rule_requires_pattern(self) -> None:
        """TransformationRule requires pattern."""
        with pytest.raises(ValueError, match="Pattern is required"):
            TransformationRule(
                rule_id="test",
                pattern="",
                replacement="",
                description="Test",
                category="test",
                version="1.0.0",
            )

    def test_transformation_rule_requires_category(self) -> None:
        """TransformationRule requires category."""
        with pytest.raises(ValueError, match="Category is required"):
            TransformationRule(
                rule_id="test",
                pattern=r"test",
                replacement="",
                description="Test",
                category="",
                version="1.0.0",
            )

    def test_transformation_rule_requires_version(self) -> None:
        """TransformationRule requires version."""
        with pytest.raises(ValueError, match="Version is required"):
            TransformationRule(
                rule_id="test",
                pattern=r"test",
                replacement="",
                description="Test",
                category="test",
                version="",
            )

    def test_transformation_rule_version_must_be_semver(self) -> None:
        """TransformationRule version must be in semver format."""
        with pytest.raises(ValueError, match="semver format"):
            TransformationRule(
                rule_id="test",
                pattern=r"test",
                replacement="",
                description="Test",
                category="test",
                version="v1.0",  # Invalid format
            )

    def test_transformation_rule_version_valid_semver(self) -> None:
        """TransformationRule accepts valid semver versions."""
        rule = TransformationRule(
            rule_id="test",
            pattern=r"test",
            replacement="",
            description="Test",
            category="test",
            version="2.1.0",
        )
        assert rule.version == "2.1.0"


class TestTransformation:
    """Unit tests for Transformation model."""

    def test_create_transformation(self) -> None:
        """Transformation can be created with required fields."""
        transform = Transformation(
            pattern_matched=r"URGENT\!",
            original_text="URGENT!",
            replacement_text="",
            rule_id="remove_urgency",
        )

        assert transform.pattern_matched == r"URGENT\!"
        assert transform.original_text == "URGENT!"
        assert transform.replacement_text == ""
        assert transform.rule_id == "remove_urgency"

    def test_transformation_immutable(self) -> None:
        """Transformation is immutable."""
        from dataclasses import FrozenInstanceError

        transform = Transformation(
            pattern_matched=r"test",
            original_text="test",
            replacement_text="",
            rule_id="test_rule",
        )

        with pytest.raises(FrozenInstanceError):
            transform.replacement_text = "new"  # type: ignore

    def test_transformation_was_removed_true(self) -> None:
        """was_removed returns True when replacement is empty."""
        transform = Transformation(
            pattern_matched=r"URGENT",
            original_text="URGENT",
            replacement_text="",
            rule_id="remove_urgency",
        )

        assert transform.was_removed is True

    def test_transformation_was_removed_false(self) -> None:
        """was_removed returns False when replacement is not empty."""
        transform = Transformation(
            pattern_matched=r"HELLO!",
            original_text="HELLO!",
            replacement_text="Hello,",
            rule_id="soften_greeting",
        )

        assert transform.was_removed is False

    def test_transformation_change_description_removed(self) -> None:
        """change_description describes removal correctly."""
        transform = Transformation(
            pattern_matched=r"URGENT",
            original_text="URGENT",
            replacement_text="",
            rule_id="remove_urgency",
        )

        desc = transform.change_description
        assert "Removed" in desc
        assert "URGENT" in desc
        assert "remove_urgency" in desc

    def test_transformation_change_description_replaced(self) -> None:
        """change_description describes replacement correctly."""
        transform = Transformation(
            pattern_matched=r"HELLO!",
            original_text="HELLO!",
            replacement_text="Hello,",
            rule_id="soften_greeting",
        )

        desc = transform.change_description
        assert "Changed" in desc
        assert "HELLO!" in desc
        assert "Hello," in desc
        assert "soften_greeting" in desc

    def test_transformation_with_position(self) -> None:
        """Transformation can include position information."""
        transform = Transformation(
            pattern_matched=r"URGENT",
            original_text="URGENT",
            replacement_text="",
            rule_id="remove_urgency",
            position=42,
        )

        assert transform.position == 42

    def test_transformation_position_optional(self) -> None:
        """Transformation position is optional."""
        transform = Transformation(
            pattern_matched=r"URGENT",
            original_text="URGENT",
            replacement_text="",
            rule_id="remove_urgency",
        )

        assert transform.position is None

    def test_transformation_requires_rule_id(self) -> None:
        """Transformation requires rule_id for audit trail."""
        with pytest.raises(ValueError, match="Rule ID is required"):
            Transformation(
                pattern_matched=r"URGENT",
                original_text="URGENT",
                replacement_text="",
                rule_id="",
            )
