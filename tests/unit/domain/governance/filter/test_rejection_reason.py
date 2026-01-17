"""Unit tests for RejectionReason enum.

Tests AC6: Rejection reasons defined for reject outcomes.
"""

import pytest

from src.domain.governance.filter.rejection_reason import RejectionReason


class TestRejectionReason:
    """Unit tests for RejectionReason enum."""

    def test_all_rejection_reasons_defined(self) -> None:
        """All rejection reason categories are defined."""
        reasons = list(RejectionReason)
        assert len(reasons) >= 6

        # Check expected reasons exist
        assert RejectionReason.URGENCY_PRESSURE in reasons
        assert RejectionReason.GUILT_INDUCTION in reasons
        assert RejectionReason.FALSE_SCARCITY in reasons
        assert RejectionReason.ENGAGEMENT_OPTIMIZATION in reasons
        assert RejectionReason.EXCESSIVE_EMPHASIS in reasons
        assert RejectionReason.IMPLICIT_THREAT in reasons

    def test_each_reason_has_description(self) -> None:
        """Each rejection reason has a description."""
        for reason in RejectionReason:
            assert hasattr(reason, "description")
            assert isinstance(reason.description, str)
            assert len(reason.description) > 0

    def test_each_reason_has_guidance(self) -> None:
        """Each rejection reason has rewrite guidance."""
        for reason in RejectionReason:
            assert hasattr(reason, "guidance")
            assert isinstance(reason.guidance, str)
            assert len(reason.guidance) > 0

    def test_urgency_pressure_guidance(self) -> None:
        """Urgency pressure guidance is actionable."""
        guidance = RejectionReason.URGENCY_PRESSURE.guidance
        assert "time pressure" in guidance.lower() or "pressure" in guidance.lower()

    def test_guilt_induction_guidance(self) -> None:
        """Guilt induction guidance is actionable."""
        guidance = RejectionReason.GUILT_INDUCTION.guidance
        assert "guilt" in guidance.lower()

    def test_false_scarcity_guidance(self) -> None:
        """False scarcity guidance is actionable."""
        guidance = RejectionReason.FALSE_SCARCITY.guidance
        assert "scarcity" in guidance.lower()

    def test_engagement_optimization_guidance(self) -> None:
        """Engagement optimization guidance is actionable."""
        guidance = RejectionReason.ENGAGEMENT_OPTIMIZATION.guidance
        assert "neutral" in guidance.lower() or "engagement" in guidance.lower()

    def test_excessive_emphasis_guidance(self) -> None:
        """Excessive emphasis guidance is actionable."""
        guidance = RejectionReason.EXCESSIVE_EMPHASIS.guidance
        assert "caps" in guidance.lower() or "emphasis" in guidance.lower()

    def test_implicit_threat_guidance(self) -> None:
        """Implicit threat guidance is actionable."""
        guidance = RejectionReason.IMPLICIT_THREAT.guidance
        assert "consequences" in guidance.lower() or "threat" in guidance.lower()

    def test_rejection_reasons_are_correctable(self) -> None:
        """All rejection reasons represent correctable issues (not violations)."""
        # Rejection reasons should have guidance for fixing the issue
        for reason in RejectionReason:
            # Guidance should be positive/constructive
            assert reason.guidance
            # Should not mention "violation" as rejections are correctable
            assert "violation" not in reason.description.lower()
