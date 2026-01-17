"""Unit tests for ViolationType enum.

Tests AC7: Violation types defined for block outcomes.
"""

import pytest

from src.domain.governance.filter.violation_type import ViolationType


class TestViolationType:
    """Unit tests for ViolationType enum."""

    def test_all_violation_types_defined(self) -> None:
        """All hard violation types are defined."""
        violations = list(ViolationType)
        assert len(violations) >= 5

        # Check expected violations exist
        assert ViolationType.EXPLICIT_THREAT in violations
        assert ViolationType.DECEPTION in violations
        assert ViolationType.MANIPULATION in violations
        assert ViolationType.COERCION in violations
        assert ViolationType.HARASSMENT in violations

    def test_each_violation_has_description(self) -> None:
        """Each violation type has a description."""
        for violation in ViolationType:
            assert hasattr(violation, "description")
            assert isinstance(violation.description, str)
            assert len(violation.description) > 0

    def test_each_violation_has_severity(self) -> None:
        """Each violation type has severity level."""
        for violation in ViolationType:
            assert hasattr(violation, "severity")
            assert isinstance(violation.severity, str)

    def test_all_violations_are_critical(self) -> None:
        """All hard violations have critical severity."""
        for violation in ViolationType:
            assert violation.severity == "critical"

    def test_each_violation_has_escalation_path(self) -> None:
        """Each violation type has escalation path."""
        for violation in ViolationType:
            assert hasattr(violation, "escalation_path")
            assert isinstance(violation.escalation_path, str)
            assert len(violation.escalation_path) > 0

    def test_violations_escalate_to_knight(self) -> None:
        """All violations escalate to Knight witness."""
        for violation in ViolationType:
            assert "knight" in violation.escalation_path.lower()

    def test_explicit_threat_description(self) -> None:
        """Explicit threat description is clear."""
        desc = ViolationType.EXPLICIT_THREAT.description
        assert "threat" in desc.lower()

    def test_deception_description(self) -> None:
        """Deception description is clear."""
        desc = ViolationType.DECEPTION.description
        assert "false" in desc.lower() or "deception" in desc.lower()

    def test_manipulation_description(self) -> None:
        """Manipulation description is clear."""
        desc = ViolationType.MANIPULATION.description
        assert "manipulation" in desc.lower()

    def test_coercion_description(self) -> None:
        """Coercion description is clear."""
        desc = ViolationType.COERCION.description
        assert "coerce" in desc.lower() or "force" in desc.lower() or "pressure" in desc.lower()

    def test_harassment_description(self) -> None:
        """Harassment description is clear."""
        desc = ViolationType.HARASSMENT.description
        assert "harassment" in desc.lower()

    def test_violations_cannot_be_transformed(self) -> None:
        """Violations are hard blocks - they cannot be transformed (by design)."""
        # This is a design principle test - violations don't have guidance
        # because they cannot be fixed by rewriting
        for violation in ViolationType:
            # Violations should not have "guidance" attribute
            assert not hasattr(violation, "guidance")
