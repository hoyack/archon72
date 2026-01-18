"""Unit tests for FilterDecision enum.

Tests AC1: Filter outcomes defined: accept, reject, block.
"""


class TestFilterDecision:
    """Unit tests for FilterDecision enum."""

    def test_filter_decision_accepted_value(self) -> None:
        """ACCEPTED outcome is defined with correct value."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        assert FilterDecision.ACCEPTED.value == "accepted"

    def test_filter_decision_rejected_value(self) -> None:
        """REJECTED outcome is defined with correct value."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        assert FilterDecision.REJECTED.value == "rejected"

    def test_filter_decision_blocked_value(self) -> None:
        """BLOCKED outcome is defined with correct value."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        assert FilterDecision.BLOCKED.value == "blocked"

    def test_filter_decision_has_description(self) -> None:
        """Each FilterDecision has a description property."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        for decision in FilterDecision:
            assert hasattr(decision, "description")
            assert isinstance(decision.description, str)
            assert len(decision.description) > 0

    def test_filter_decision_accepted_description(self) -> None:
        """ACCEPTED description indicates content can be sent."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        assert "sent" in FilterDecision.ACCEPTED.description.lower()

    def test_filter_decision_rejected_description(self) -> None:
        """REJECTED description indicates rewrite required."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        assert "rewrite" in FilterDecision.REJECTED.description.lower()

    def test_filter_decision_blocked_description(self) -> None:
        """BLOCKED description indicates violation."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        assert "violation" in FilterDecision.BLOCKED.description.lower()

    def test_all_filter_decisions_defined(self) -> None:
        """All three filter decisions are defined."""
        from src.domain.governance.filter.filter_decision import FilterDecision

        decisions = list(FilterDecision)
        assert len(decisions) == 3
        assert FilterDecision.ACCEPTED in decisions
        assert FilterDecision.REJECTED in decisions
        assert FilterDecision.BLOCKED in decisions
