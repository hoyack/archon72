"""Marquis Service Port (Advisory Branch).

This module defines the abstract protocol for Marquis-rank advisory functions.
Marquis provide expert testimony and non-binding advisories across domains.

Per Government PRD FR-GOV-17: Marquis provide expert testimony and risk analysis,
issue non-binding advisories.
Per Government PRD FR-GOV-18: Advisories must be acknowledged but not obeyed;
cannot judge domains where advisory was given.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ExpertiseDomain(Enum):
    """Expertise domains for Marquis advisors.

    Per PRD §4.6: Expertise domains are Science, Ethics, Language, Knowledge.
    """

    SCIENCE = "science"  # Orias, Gamigin, Amy
    ETHICS = "ethics"  # Vine, Seere, Dantalion, Aim
    LANGUAGE = "language"  # Crocell, Alloces, Caim
    KNOWLEDGE = "knowledge"  # Foras, Barbatos, Stolas, Orobas, Ipos


class RiskLevel(Enum):
    """Risk severity levels for risk analysis."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


@dataclass(frozen=True)
class Advisory:
    """A non-binding advisory issued by a Marquis.

    Per FR-GOV-18: Advisories must be acknowledged but not obeyed.
    Immutable to ensure advisory integrity.
    """

    advisory_id: UUID
    issued_by: str  # Marquis Archon ID
    domain: ExpertiseDomain
    topic: str
    recommendation: str
    rationale: str
    binding: bool = False  # ALWAYS False per FR-GOV-18
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_by: tuple[str, ...] = field(default_factory=tuple)
    motion_ref: UUID | None = None  # Related motion if any

    @classmethod
    def create(
        cls,
        issued_by: str,
        domain: ExpertiseDomain,
        topic: str,
        recommendation: str,
        rationale: str,
        motion_ref: UUID | None = None,
    ) -> "Advisory":
        """Create a new advisory.

        Args:
            issued_by: Marquis Archon ID
            domain: Expertise domain
            topic: Subject of the advisory
            recommendation: The advisory recommendation
            rationale: Supporting reasoning
            motion_ref: Related motion if any

        Returns:
            New immutable Advisory with binding=False
        """
        return cls(
            advisory_id=uuid4(),
            issued_by=issued_by,
            domain=domain,
            topic=topic,
            recommendation=recommendation,
            rationale=rationale,
            binding=False,  # Always non-binding per FR-GOV-18
            motion_ref=motion_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "advisory_id": str(self.advisory_id),
            "issued_by": self.issued_by,
            "domain": self.domain.value,
            "topic": self.topic,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "binding": self.binding,
            "issued_at": self.issued_at.isoformat(),
            "acknowledged_by": list(self.acknowledged_by),
            "motion_ref": str(self.motion_ref) if self.motion_ref else None,
        }


@dataclass(frozen=True)
class Testimony:
    """Expert testimony provided by a Marquis.

    Testimony is formal expert opinion on a specific question.
    """

    testimony_id: UUID
    provided_by: str  # Marquis Archon ID
    domain: ExpertiseDomain
    question: str
    response: str
    supporting_evidence: tuple[str, ...] = field(default_factory=tuple)
    provided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    motion_ref: UUID | None = None

    @classmethod
    def create(
        cls,
        provided_by: str,
        domain: ExpertiseDomain,
        question: str,
        response: str,
        supporting_evidence: list[str] | None = None,
        motion_ref: UUID | None = None,
    ) -> "Testimony":
        """Create new testimony.

        Args:
            provided_by: Marquis Archon ID
            domain: Expertise domain
            question: Question being answered
            response: Expert response
            supporting_evidence: Evidence supporting the testimony
            motion_ref: Related motion if any

        Returns:
            New immutable Testimony
        """
        return cls(
            testimony_id=uuid4(),
            provided_by=provided_by,
            domain=domain,
            question=question,
            response=response,
            supporting_evidence=tuple(supporting_evidence or []),
            motion_ref=motion_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "testimony_id": str(self.testimony_id),
            "provided_by": self.provided_by,
            "domain": self.domain.value,
            "question": self.question,
            "response": self.response,
            "supporting_evidence": list(self.supporting_evidence),
            "provided_at": self.provided_at.isoformat(),
            "motion_ref": str(self.motion_ref) if self.motion_ref else None,
        }


@dataclass(frozen=True)
class RiskFactor:
    """A single risk factor identified in risk analysis."""

    risk_id: str
    description: str
    level: RiskLevel
    likelihood: float  # 0.0 to 1.0
    impact: str
    mitigation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "risk_id": self.risk_id,
            "description": self.description,
            "level": self.level.value,
            "likelihood": self.likelihood,
            "impact": self.impact,
            "mitigation": self.mitigation,
        }


@dataclass(frozen=True)
class RiskAnalysis:
    """Risk analysis of a proposal by a Marquis.

    Non-binding analysis of risks associated with a proposal.
    """

    analysis_id: UUID
    analyzed_by: str  # Marquis Archon ID
    domain: ExpertiseDomain
    proposal: str
    risks: tuple[RiskFactor, ...]
    overall_risk_level: RiskLevel
    recommendations: tuple[str, ...]
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    motion_ref: UUID | None = None

    @classmethod
    def create(
        cls,
        analyzed_by: str,
        domain: ExpertiseDomain,
        proposal: str,
        risks: list[RiskFactor],
        overall_risk_level: RiskLevel,
        recommendations: list[str],
        motion_ref: UUID | None = None,
    ) -> "RiskAnalysis":
        """Create new risk analysis.

        Args:
            analyzed_by: Marquis Archon ID
            domain: Expertise domain
            proposal: Proposal being analyzed
            risks: List of identified risks
            overall_risk_level: Overall risk assessment
            recommendations: Risk mitigation recommendations
            motion_ref: Related motion if any

        Returns:
            New immutable RiskAnalysis
        """
        return cls(
            analysis_id=uuid4(),
            analyzed_by=analyzed_by,
            domain=domain,
            proposal=proposal,
            risks=tuple(risks),
            overall_risk_level=overall_risk_level,
            recommendations=tuple(recommendations),
            motion_ref=motion_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "analysis_id": str(self.analysis_id),
            "analyzed_by": self.analyzed_by,
            "domain": self.domain.value,
            "proposal": self.proposal,
            "risks": [r.to_dict() for r in self.risks],
            "overall_risk_level": self.overall_risk_level.value,
            "recommendations": list(self.recommendations),
            "analyzed_at": self.analyzed_at.isoformat(),
            "motion_ref": str(self.motion_ref) if self.motion_ref else None,
        }


@dataclass
class TestimonyRequest:
    """Request for expert testimony."""

    requested_by: str  # Archon ID requesting
    domain: ExpertiseDomain
    question: str
    context: str | None = None
    motion_ref: UUID | None = None


@dataclass
class TestimonyResult:
    """Result of providing testimony."""

    success: bool
    testimony: Testimony | None = None
    error: str | None = None


@dataclass
class AdvisoryRequest:
    """Request to issue an advisory."""

    marquis_id: str  # Marquis Archon ID
    domain: ExpertiseDomain
    topic: str
    recommendation: str
    rationale: str
    motion_ref: UUID | None = None


@dataclass
class AdvisoryResult:
    """Result of issuing an advisory."""

    success: bool
    advisory: Advisory | None = None
    error: str | None = None


@dataclass
class RiskAnalysisRequest:
    """Request for risk analysis."""

    marquis_id: str  # Marquis Archon ID
    proposal: str
    context: str | None = None
    motion_ref: UUID | None = None


@dataclass
class RiskAnalysisResult:
    """Result of risk analysis."""

    success: bool
    analysis: RiskAnalysis | None = None
    error: str | None = None


# Marquis-to-Domain Mapping (15 Marquis Archons)
MARQUIS_DOMAIN_MAPPING: dict[str, ExpertiseDomain] = {
    # Science Domain
    "orias": ExpertiseDomain.SCIENCE,
    "gamigin": ExpertiseDomain.SCIENCE,
    "amy": ExpertiseDomain.SCIENCE,
    # Ethics Domain
    "vine": ExpertiseDomain.ETHICS,
    "seere": ExpertiseDomain.ETHICS,
    "dantalion": ExpertiseDomain.ETHICS,
    "aim": ExpertiseDomain.ETHICS,
    # Language Domain
    "crocell": ExpertiseDomain.LANGUAGE,
    "alloces": ExpertiseDomain.LANGUAGE,
    "caim": ExpertiseDomain.LANGUAGE,
    # Knowledge Domain
    "foras": ExpertiseDomain.KNOWLEDGE,
    "barbatos": ExpertiseDomain.KNOWLEDGE,
    "stolas": ExpertiseDomain.KNOWLEDGE,
    "orobas": ExpertiseDomain.KNOWLEDGE,
    "ipos": ExpertiseDomain.KNOWLEDGE,
}


def get_expertise_domain(archon_name: str) -> ExpertiseDomain | None:
    """Get the expertise domain for a Marquis Archon.

    Args:
        archon_name: Name of the Marquis Archon (lowercase)

    Returns:
        ExpertiseDomain if found, None if not a Marquis
    """
    return MARQUIS_DOMAIN_MAPPING.get(archon_name.lower())


def get_marquis_for_domain(domain: ExpertiseDomain) -> list[str]:
    """Get all Marquis Archons for a given expertise domain.

    Args:
        domain: The expertise domain

    Returns:
        List of Archon names in that domain
    """
    return [
        name for name, d in MARQUIS_DOMAIN_MAPPING.items() if d == domain
    ]


class MarquisServiceProtocol(ABC):
    """Abstract protocol for Marquis-rank advisory functions.

    Per Government PRD:
    - FR-GOV-17: Provide expert testimony and risk analysis, issue non-binding advisories
    - FR-GOV-18: Advisories must be acknowledged but not obeyed;
                 cannot judge domains where advisory was given

    This protocol explicitly EXCLUDES:
    - Motion introduction (King function)
    - Execution definition (President function)
    - Task execution (Duke/Earl function)
    - Compliance judgment (Prince function) - especially on advised domains
    - Witnessing (Knight function)
    """

    @abstractmethod
    async def provide_testimony(
        self,
        request: TestimonyRequest,
    ) -> TestimonyResult:
        """Provide expert testimony on a domain question.

        Per FR-GOV-17: Marquis provide expert testimony.

        Args:
            request: Testimony request with domain and question

        Returns:
            TestimonyResult with testimony or error

        Raises:
            RankViolationError: If the Archon is not Marquis-rank
        """
        ...

    @abstractmethod
    async def issue_advisory(
        self,
        request: AdvisoryRequest,
    ) -> AdvisoryResult:
        """Issue a non-binding advisory.

        Per FR-GOV-17: Marquis issue non-binding advisories.
        Per FR-GOV-18: Advisories must be acknowledged but not obeyed.

        Args:
            request: Advisory request with topic and recommendation

        Returns:
            AdvisoryResult with advisory (binding=False) or error

        Note:
            The advisory is NEVER binding. Recipients must acknowledge
            but need not follow the recommendation.
        """
        ...

    @abstractmethod
    async def analyze_risk(
        self,
        request: RiskAnalysisRequest,
    ) -> RiskAnalysisResult:
        """Analyze risks in a proposal.

        Per FR-GOV-17: Marquis provide risk analysis.

        Args:
            request: Risk analysis request with proposal

        Returns:
            RiskAnalysisResult with analysis or error
        """
        ...

    @abstractmethod
    async def get_expertise_domains(
        self,
        marquis_id: str,
    ) -> list[ExpertiseDomain]:
        """Get expertise domains for a Marquis.

        Args:
            marquis_id: Marquis Archon ID

        Returns:
            List of expertise domains (typically one per Marquis)
        """
        ...

    @abstractmethod
    async def get_advisory(self, advisory_id: UUID) -> Advisory | None:
        """Retrieve an advisory by ID.

        Args:
            advisory_id: UUID of the advisory

        Returns:
            Advisory if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_advisories_by_marquis(
        self,
        marquis_id: str,
    ) -> list[Advisory]:
        """Get all advisories issued by a specific Marquis.

        Args:
            marquis_id: The Marquis Archon ID

        Returns:
            List of advisories issued by that Marquis
        """
        ...

    @abstractmethod
    async def get_advisories_by_domain(
        self,
        domain: ExpertiseDomain,
    ) -> list[Advisory]:
        """Get all advisories in a specific domain.

        Args:
            domain: The expertise domain

        Returns:
            List of advisories in that domain
        """
        ...

    @abstractmethod
    async def get_advisories_by_motion(
        self,
        motion_ref: UUID,
    ) -> list[Advisory]:
        """Get all advisories related to a specific motion.

        Args:
            motion_ref: The motion's UUID

        Returns:
            List of advisories for that motion
        """
        ...

    # =========================================================================
    # EXPLICITLY EXCLUDED METHODS
    # These methods are NOT part of the Marquis Service per FR-GOV-18
    # =========================================================================

    # def introduce_motion(self) -> None:  # PROHIBITED (King function)
    # def define_execution(self) -> None:  # PROHIBITED (President function)
    # def execute_task(self) -> None:  # PROHIBITED (Duke/Earl function)
    # def judge_compliance(self) -> None:  # PROHIBITED (Prince function)
    # def witness(self) -> None:  # PROHIBITED (Knight function)

    # Per FR-GOV-18: Cannot judge domains where advisory was given
    # This is enforced at the permission level, not in this protocol
