"""Unit tests for Marquis Service port (Epic 6, Story 6.1).

Tests:
- Advisory model creation (always non-binding per FR-GOV-18)
- Testimony model creation
- RiskAnalysis model creation
- ExpertiseDomain enum values
- Marquis-to-domain mapping
- Immutability of frozen dataclasses

Constitutional Constraints:
- FR-GOV-17: Marquis provide expert testimony and risk analysis, issue non-binding advisories
- FR-GOV-18: Advisories must be acknowledged but not obeyed; cannot judge domains where advisory was given
"""

from __future__ import annotations

from uuid import uuid4

import pytest


class TestExpertiseDomainEnum:
    """Test ExpertiseDomain enum."""

    def test_all_expertise_domains_defined(self) -> None:
        """All expertise domains are defined per PRD §4.6."""
        from src.application.ports.marquis_service import ExpertiseDomain

        expected = {"science", "ethics", "language", "knowledge"}
        actual = {d.value for d in ExpertiseDomain}
        assert actual == expected


class TestRiskLevelEnum:
    """Test RiskLevel enum."""

    def test_all_risk_levels_defined(self) -> None:
        """All risk levels are defined."""
        from src.application.ports.marquis_service import RiskLevel

        expected = {"critical", "high", "medium", "low", "negligible"}
        actual = {r.value for r in RiskLevel}
        assert actual == expected


class TestMarquisDomainMapping:
    """Test Marquis-to-domain mapping."""

    def test_mapping_contains_15_marquis(self) -> None:
        """Mapping contains all 15 Marquis Archons."""
        from src.application.ports.marquis_service import MARQUIS_DOMAIN_MAPPING

        assert len(MARQUIS_DOMAIN_MAPPING) == 15

    def test_science_domain_marquis(self) -> None:
        """Science domain has correct Marquis."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            get_marquis_for_domain,
        )

        science_marquis = get_marquis_for_domain(ExpertiseDomain.SCIENCE)
        assert set(science_marquis) == {"orias", "gamigin", "amy"}

    def test_ethics_domain_marquis(self) -> None:
        """Ethics domain has correct Marquis."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            get_marquis_for_domain,
        )

        ethics_marquis = get_marquis_for_domain(ExpertiseDomain.ETHICS)
        assert set(ethics_marquis) == {"vine", "seere", "dantalion", "aim"}

    def test_language_domain_marquis(self) -> None:
        """Language domain has correct Marquis."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            get_marquis_for_domain,
        )

        language_marquis = get_marquis_for_domain(ExpertiseDomain.LANGUAGE)
        assert set(language_marquis) == {"crocell", "alloces", "caim"}

    def test_knowledge_domain_marquis(self) -> None:
        """Knowledge domain has correct Marquis."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            get_marquis_for_domain,
        )

        knowledge_marquis = get_marquis_for_domain(ExpertiseDomain.KNOWLEDGE)
        assert set(knowledge_marquis) == {
            "foras",
            "barbatos",
            "stolas",
            "orobas",
            "ipos",
        }

    def test_get_expertise_domain_case_insensitive(self) -> None:
        """get_expertise_domain works case-insensitively."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            get_expertise_domain,
        )

        assert get_expertise_domain("ORIAS") == ExpertiseDomain.SCIENCE
        assert get_expertise_domain("Orias") == ExpertiseDomain.SCIENCE
        assert get_expertise_domain("orias") == ExpertiseDomain.SCIENCE

    def test_get_expertise_domain_returns_none_for_non_marquis(self) -> None:
        """get_expertise_domain returns None for non-Marquis Archons."""
        from src.application.ports.marquis_service import get_expertise_domain

        assert get_expertise_domain("lucifer") is None  # King, not Marquis
        assert get_expertise_domain("nonexistent") is None


class TestAdvisory:
    """Test Advisory dataclass."""

    def test_create_advisory(self) -> None:
        """Advisory.create() produces valid advisory."""
        from src.application.ports.marquis_service import (
            Advisory,
            ExpertiseDomain,
        )

        motion_ref = uuid4()
        advisory = Advisory.create(
            issued_by="orias",
            domain=ExpertiseDomain.SCIENCE,
            topic="Data validation approach",
            recommendation="Use schema validation with strict typing",
            rationale="Strict typing prevents type coercion bugs at runtime",
            motion_ref=motion_ref,
        )

        assert advisory.issued_by == "orias"
        assert advisory.domain == ExpertiseDomain.SCIENCE
        assert advisory.topic == "Data validation approach"
        assert advisory.motion_ref == motion_ref
        assert advisory.advisory_id is not None

    def test_advisory_always_non_binding(self) -> None:
        """Per FR-GOV-18: Advisories are ALWAYS non-binding."""
        from src.application.ports.marquis_service import (
            Advisory,
            ExpertiseDomain,
        )

        advisory = Advisory.create(
            issued_by="vine",
            domain=ExpertiseDomain.ETHICS,
            topic="Privacy considerations",
            recommendation="Implement data anonymization",
            rationale="User privacy is paramount",
        )

        # Per FR-GOV-18: binding must ALWAYS be False
        assert advisory.binding is False

    def test_advisory_is_frozen(self) -> None:
        """Advisory is immutable."""
        from src.application.ports.marquis_service import (
            Advisory,
            ExpertiseDomain,
        )

        advisory = Advisory.create(
            issued_by="foras",
            domain=ExpertiseDomain.KNOWLEDGE,
            topic="Topic",
            recommendation="Rec",
            rationale="Reason",
        )

        with pytest.raises(AttributeError):
            advisory.binding = True  # type: ignore

    def test_advisory_to_dict(self) -> None:
        """Advisory serializes to dictionary."""
        from src.application.ports.marquis_service import (
            Advisory,
            ExpertiseDomain,
        )

        advisory = Advisory.create(
            issued_by="caim",
            domain=ExpertiseDomain.LANGUAGE,
            topic="Naming conventions",
            recommendation="Use snake_case",
            rationale="Consistency with Python style",
        )

        d = advisory.to_dict()

        assert d["issued_by"] == "caim"
        assert d["domain"] == "language"
        assert d["binding"] is False  # Always non-binding


class TestTestimony:
    """Test Testimony dataclass."""

    def test_create_testimony(self) -> None:
        """Testimony.create() produces valid testimony."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            Testimony,
        )

        testimony = Testimony.create(
            provided_by="gamigin",
            domain=ExpertiseDomain.SCIENCE,
            question="What algorithm is most appropriate for sorting this data?",
            response="Quicksort with median-of-three pivot selection is optimal here",
            supporting_evidence=["O(n log n) average case", "In-place sorting"],
            motion_ref=uuid4(),
        )

        assert testimony.provided_by == "gamigin"
        assert testimony.domain == ExpertiseDomain.SCIENCE
        assert "Quicksort" in testimony.response
        assert len(testimony.supporting_evidence) == 2

    def test_testimony_is_frozen(self) -> None:
        """Testimony is immutable."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            Testimony,
        )

        testimony = Testimony.create(
            provided_by="barbatos",
            domain=ExpertiseDomain.KNOWLEDGE,
            question="Question?",
            response="Answer",
        )

        with pytest.raises(AttributeError):
            testimony.response = "Modified"  # type: ignore

    def test_testimony_to_dict(self) -> None:
        """Testimony serializes to dictionary."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            Testimony,
        )

        testimony = Testimony.create(
            provided_by="stolas",
            domain=ExpertiseDomain.KNOWLEDGE,
            question="What is the best practice?",
            response="Follow established patterns",
        )

        d = testimony.to_dict()

        assert d["provided_by"] == "stolas"
        assert d["domain"] == "knowledge"


class TestRiskFactor:
    """Test RiskFactor dataclass."""

    def test_risk_factor_creation(self) -> None:
        """RiskFactor can be created with all fields."""
        from src.application.ports.marquis_service import RiskFactor, RiskLevel

        risk = RiskFactor(
            risk_id="RISK-001",
            description="Memory exhaustion under high load",
            level=RiskLevel.HIGH,
            likelihood=0.75,
            impact="Service degradation or crash",
            mitigation="Implement rate limiting and memory caps",
        )

        assert risk.risk_id == "RISK-001"
        assert risk.level == RiskLevel.HIGH
        assert risk.likelihood == 0.75
        assert risk.mitigation is not None

    def test_risk_factor_to_dict(self) -> None:
        """RiskFactor serializes to dictionary."""
        from src.application.ports.marquis_service import RiskFactor, RiskLevel

        risk = RiskFactor(
            risk_id="RISK-002",
            description="Data corruption risk",
            level=RiskLevel.CRITICAL,
            likelihood=0.1,
            impact="Data loss",
        )

        d = risk.to_dict()

        assert d["risk_id"] == "RISK-002"
        assert d["level"] == "critical"
        assert d["likelihood"] == 0.1


class TestRiskAnalysis:
    """Test RiskAnalysis dataclass."""

    def test_create_risk_analysis(self) -> None:
        """RiskAnalysis.create() produces valid analysis."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            RiskAnalysis,
            RiskFactor,
            RiskLevel,
        )

        risk1 = RiskFactor(
            risk_id="R1",
            description="Memory issue",
            level=RiskLevel.HIGH,
            likelihood=0.5,
            impact="Crash",
        )
        risk2 = RiskFactor(
            risk_id="R2",
            description="Security issue",
            level=RiskLevel.CRITICAL,
            likelihood=0.2,
            impact="Data breach",
        )

        analysis = RiskAnalysis.create(
            analyzed_by="orobas",
            domain=ExpertiseDomain.KNOWLEDGE,
            proposal="Implement new caching layer",
            risks=[risk1, risk2],
            overall_risk_level=RiskLevel.HIGH,
            recommendations=["Add memory monitoring", "Implement auth checks"],
            motion_ref=uuid4(),
        )

        assert analysis.analyzed_by == "orobas"
        assert len(analysis.risks) == 2
        assert analysis.overall_risk_level == RiskLevel.HIGH
        assert len(analysis.recommendations) == 2

    def test_risk_analysis_is_frozen(self) -> None:
        """RiskAnalysis is immutable."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            RiskAnalysis,
            RiskLevel,
        )

        analysis = RiskAnalysis.create(
            analyzed_by="ipos",
            domain=ExpertiseDomain.KNOWLEDGE,
            proposal="Test proposal",
            risks=[],
            overall_risk_level=RiskLevel.LOW,
            recommendations=[],
        )

        with pytest.raises(AttributeError):
            analysis.overall_risk_level = RiskLevel.CRITICAL  # type: ignore


class TestRequestAndResultDataclasses:
    """Test request and result dataclasses."""

    def test_testimony_request(self) -> None:
        """TestimonyRequest holds request data."""
        from src.application.ports.marquis_service import (
            ExpertiseDomain,
            TestimonyRequest,
        )

        request = TestimonyRequest(
            requested_by="president-archon-001",
            domain=ExpertiseDomain.SCIENCE,
            question="What is the best approach for distributed consensus?",
            context="Building a multi-node system",
            motion_ref=uuid4(),
        )

        assert request.requested_by == "president-archon-001"
        assert request.domain == ExpertiseDomain.SCIENCE

    def test_advisory_request(self) -> None:
        """AdvisoryRequest holds advisory request data."""
        from src.application.ports.marquis_service import (
            AdvisoryRequest,
            ExpertiseDomain,
        )

        request = AdvisoryRequest(
            marquis_id="seere",
            domain=ExpertiseDomain.ETHICS,
            topic="User consent handling",
            recommendation="Require explicit opt-in",
            rationale="GDPR compliance",
        )

        assert request.marquis_id == "seere"
        assert request.domain == ExpertiseDomain.ETHICS

    def test_risk_analysis_request(self) -> None:
        """RiskAnalysisRequest holds risk analysis request data."""
        from src.application.ports.marquis_service import RiskAnalysisRequest

        request = RiskAnalysisRequest(
            marquis_id="amy",
            proposal="Add external API integration",
            context="Third-party service dependency",
            motion_ref=uuid4(),
        )

        assert request.marquis_id == "amy"
        assert "API integration" in request.proposal
