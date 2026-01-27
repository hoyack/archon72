"""Tests for enhanced DeliberationContext and TraceMetadata (v2)."""

from src.application.ports.president_deliberation import (
    DeliberationContext,
    DeliberationResult,
    GeneratedBy,
    TraceMetadata,
)
from src.domain.models.executive_planning import (
    CapacityClaim,
    NoActionAttestation,
    NoActionReason,
    PortfolioContribution,
    PortfolioIdentity,
)


class TestTraceMetadata:
    """Test TraceMetadata for LLM provenance tracking."""

    def test_to_dict_includes_all_fields(self):
        """TraceMetadata.to_dict should include all fields."""
        trace = TraceMetadata(
            timestamp="2026-01-27T12:00:00Z",
            model="gpt-4",
            provider="openai",
            duration_ms=1500,
            prompt_tokens=500,
            completion_tokens=200,
            temperature=0.3,
            request_id="req_abc123",
        )

        data = trace.to_dict()

        assert data["timestamp"] == "2026-01-27T12:00:00Z"
        assert data["model"] == "gpt-4"
        assert data["provider"] == "openai"
        assert data["duration_ms"] == 1500
        assert data["prompt_tokens"] == 500
        assert data["completion_tokens"] == 200
        assert data["temperature"] == 0.3
        assert data["request_id"] == "req_abc123"

    def test_to_dict_with_optional_fields_none(self):
        """TraceMetadata should handle None optional fields."""
        trace = TraceMetadata(
            timestamp="2026-01-27T12:00:00Z",
            model="claude-3-opus",
            provider="anthropic",
            duration_ms=2000,
        )

        data = trace.to_dict()

        assert data["timestamp"] == "2026-01-27T12:00:00Z"
        assert data["model"] == "claude-3-opus"
        assert data["provider"] == "anthropic"
        assert data["duration_ms"] == 2000
        assert data["prompt_tokens"] is None
        assert data["completion_tokens"] is None
        assert data["temperature"] is None
        assert data["request_id"] is None


class TestDeliberationContext:
    """Test enhanced DeliberationContext with v2 fields."""

    def test_basic_context_fields(self):
        """DeliberationContext should have all basic fields."""
        context = DeliberationContext(
            cycle_id="exec_001",
            motion_id="motion_001",
            motion_title="Test Motion",
            motion_text="Motion content here",
            constraints=["security", "compliance"],
            affected_portfolios=["portfolio_tech", "portfolio_governance"],
            plan_owner_portfolio_id="portfolio_tech",
            response_deadline="2026-01-28T12:00:00Z",
        )

        assert context.cycle_id == "exec_001"
        assert context.motion_id == "motion_001"
        assert context.motion_title == "Test Motion"
        assert len(context.constraints) == 2
        assert "portfolio_tech" in context.affected_portfolios

    def test_enhanced_context_fields(self):
        """DeliberationContext should support v2 enhanced fields."""
        context = DeliberationContext(
            cycle_id="exec_001",
            motion_id="motion_001",
            motion_title="Test Motion",
            motion_text="Motion content here",
            constraints=["security"],
            affected_portfolios=["portfolio_tech"],
            plan_owner_portfolio_id="portfolio_tech",
            response_deadline="2026-01-28T12:00:00Z",
            # v2 fields
            ratified_motion={"motion_id": "motion_001", "title": "Test Motion"},
            review_artifacts={"triage": {"score": 0.8}},
            assignment_record={"cycle_id": "exec_001", "plan_owner": {}},
            portfolio_labels={"portfolio_tech": "Technical Solutions"},
        )

        assert context.ratified_motion["motion_id"] == "motion_001"
        assert context.review_artifacts["triage"]["score"] == 0.8
        assert "cycle_id" in context.assignment_record
        assert context.portfolio_labels["portfolio_tech"] == "Technical Solutions"

    def test_to_dict_includes_all_fields(self):
        """DeliberationContext.to_dict should include all fields."""
        context = DeliberationContext(
            cycle_id="exec_001",
            motion_id="motion_001",
            motion_title="Test Motion",
            motion_text="Motion content",
            constraints=["c1"],
            affected_portfolios=["p1"],
            plan_owner_portfolio_id="p1",
            response_deadline="2026-01-28T12:00:00Z",
            ratified_motion={"key": "value"},
            review_artifacts={"key": "value"},
            assignment_record={"key": "value"},
            portfolio_labels={"p1": "Portfolio 1"},
        )

        data = context.to_dict()

        assert data["cycle_id"] == "exec_001"
        assert data["motion_id"] == "motion_001"
        assert "ratified_motion" in data
        assert "review_artifacts" in data
        assert "assignment_record" in data
        assert "portfolio_labels" in data

    def test_default_enhanced_fields_are_empty(self):
        """Enhanced fields should default to empty dicts."""
        context = DeliberationContext(
            cycle_id="exec_001",
            motion_id="motion_001",
            motion_title="Test Motion",
            motion_text="Motion content",
            constraints=[],
            affected_portfolios=[],
            plan_owner_portfolio_id="p1",
            response_deadline="",
        )

        assert context.ratified_motion == {}
        assert context.review_artifacts == {}
        assert context.assignment_record == {}
        assert context.portfolio_labels == {}


class TestGeneratedBy:
    """Test GeneratedBy origin constants."""

    def test_llm_constant(self):
        """GeneratedBy.LLM should be 'llm'."""
        assert GeneratedBy.LLM == "llm"

    def test_manual_constant(self):
        """GeneratedBy.MANUAL should be 'manual'."""
        assert GeneratedBy.MANUAL == "manual"

    def test_hybrid_constant(self):
        """GeneratedBy.HYBRID should be 'hybrid'."""
        assert GeneratedBy.HYBRID == "hybrid"


class TestDeliberationResult:
    """Test enhanced DeliberationResult with v2 fields."""

    def _make_portfolio(self) -> PortfolioIdentity:
        return PortfolioIdentity(
            portfolio_id="portfolio_tech",
            president_id="president_001",
            president_name="Tech President",
        )

    def _make_contribution(self) -> PortfolioContribution:
        return PortfolioContribution(
            cycle_id="exec_001",
            motion_id="motion_001",
            portfolio=self._make_portfolio(),
            tasks=[{"task_id": "t1"}],
            capacity_claim=CapacityClaim("COARSE_ESTIMATE", 5.0, "points"),
        )

    def _make_attestation(self) -> NoActionAttestation:
        return NoActionAttestation(
            cycle_id="exec_001",
            motion_id="motion_001",
            portfolio=self._make_portfolio(),
            reason_code=NoActionReason.OUTSIDE_PORTFOLIO_SCOPE,
            explanation="Not our domain",
            capacity_claim=CapacityClaim("NONE", None, None),
        )

    def test_result_with_llm_origin(self):
        """DeliberationResult should track LLM origin."""
        result = DeliberationResult(
            portfolio_id="portfolio_tech",
            president_name="Tech President",
            contributed=True,
            contribution=self._make_contribution(),
            generated_by=GeneratedBy.LLM,
        )

        assert result.generated_by == "llm"

    def test_result_with_manual_origin(self):
        """DeliberationResult should track manual origin."""
        result = DeliberationResult(
            portfolio_id="portfolio_tech",
            president_name="Tech President",
            contributed=False,
            attestation=self._make_attestation(),
            generated_by=GeneratedBy.MANUAL,
        )

        assert result.generated_by == "manual"

    def test_result_with_trace_metadata(self):
        """DeliberationResult should include trace metadata."""
        trace = TraceMetadata(
            timestamp="2026-01-27T12:00:00Z",
            model="gpt-4",
            provider="openai",
            duration_ms=1500,
        )

        result = DeliberationResult(
            portfolio_id="portfolio_tech",
            president_name="Tech President",
            contributed=True,
            contribution=self._make_contribution(),
            generated_by=GeneratedBy.LLM,
            trace_metadata=trace,
        )

        assert result.trace_metadata is not None
        assert result.trace_metadata.model == "gpt-4"
        assert result.trace_metadata.duration_ms == 1500

    def test_to_dict_includes_generated_by(self):
        """DeliberationResult.to_dict should include generated_by."""
        result = DeliberationResult(
            portfolio_id="portfolio_tech",
            president_name="Tech President",
            contributed=True,
            contribution=self._make_contribution(),
            generated_by=GeneratedBy.LLM,
        )

        data = result.to_dict()

        assert data["generated_by"] == "llm"
        assert "contribution" in data

    def test_to_dict_includes_trace_metadata(self):
        """DeliberationResult.to_dict should include trace metadata when present."""
        trace = TraceMetadata(
            timestamp="2026-01-27T12:00:00Z",
            model="claude-3",
            provider="anthropic",
            duration_ms=2000,
        )

        result = DeliberationResult(
            portfolio_id="portfolio_tech",
            president_name="Tech President",
            contributed=False,
            attestation=self._make_attestation(),
            generated_by=GeneratedBy.LLM,
            trace_metadata=trace,
        )

        data = result.to_dict()

        assert "trace_metadata" in data
        assert data["trace_metadata"]["model"] == "claude-3"
        assert data["trace_metadata"]["provider"] == "anthropic"

    def test_to_dict_without_trace_metadata(self):
        """DeliberationResult.to_dict should handle missing trace metadata."""
        result = DeliberationResult(
            portfolio_id="portfolio_tech",
            president_name="Tech President",
            contributed=False,
            attestation=self._make_attestation(),
            generated_by=GeneratedBy.MANUAL,
            trace_metadata=None,
        )

        data = result.to_dict()

        assert data["generated_by"] == "manual"
        assert "trace_metadata" not in data

    def test_default_generated_by_is_llm(self):
        """DeliberationResult should default to LLM origin."""
        result = DeliberationResult(
            portfolio_id="portfolio_tech",
            president_name="Tech President",
            contributed=False,
        )

        assert result.generated_by == GeneratedBy.LLM
