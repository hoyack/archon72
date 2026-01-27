"""Domain models for Administrative Pipeline.

The Administrative Pipeline transforms Executive execution plans (WHAT) into
concrete implementation proposals (HOW) through bottom-up resource discovery
and capacity analysis.

Principle: "Conclave is for intent. Administration is for reality."

This stage:
- Receives execution plan handoffs from Executive
- Generates implementation proposals per epic
- Discovers and aggregates resource requests
- Produces capacity commitments based on reality

Schema Versions:
- 2.0: Initial version aligned with Executive v2 artifacts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Schema version for Administrative Pipeline artifacts
ADMIN_SCHEMA_VERSION = "2.0"


class ResourceType(str, Enum):
    """Classification of resource types that can be requested."""

    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"
    NETWORK = "NETWORK"
    HUMAN_HOURS = "HUMAN_HOURS"
    TOOLING = "TOOLING"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    BUDGET = "BUDGET"
    ACCESS = "ACCESS"
    OTHER = "OTHER"


class ResourcePriority(str, Enum):
    """Priority level for resource requests."""

    CRITICAL = "CRITICAL"  # Blocks all progress
    HIGH = "HIGH"  # Significant impact if delayed
    MEDIUM = "MEDIUM"  # Impacts efficiency
    LOW = "LOW"  # Nice to have


class RiskLikelihood(str, Enum):
    """Likelihood classification for implementation risks."""

    RARE = "RARE"
    UNLIKELY = "UNLIKELY"
    POSSIBLE = "POSSIBLE"
    LIKELY = "LIKELY"
    ALMOST_CERTAIN = "ALMOST_CERTAIN"


class RiskImpact(str, Enum):
    """Impact classification for implementation risks."""

    NEGLIGIBLE = "NEGLIGIBLE"
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"
    SEVERE = "SEVERE"


class SpecType(str, Enum):
    """Types of technical specification documents."""

    ARCHITECTURE = "ARCHITECTURE"
    API = "API"
    DATA_MODEL = "DATA_MODEL"
    INTEGRATION = "INTEGRATION"
    SECURITY = "SECURITY"
    DEPLOYMENT = "DEPLOYMENT"
    TEST_PLAN = "TEST_PLAN"
    RUNBOOK = "RUNBOOK"
    OTHER = "OTHER"


class ConfidenceLevel(str, Enum):
    """Confidence level for capacity commitments."""

    HIGH = "HIGH"  # 80-100% confidence
    MEDIUM = "MEDIUM"  # 50-80% confidence
    LOW = "LOW"  # Below 50% confidence
    SPECULATIVE = "SPECULATIVE"  # Rough estimate only


# -----------------------------------------------------------------------------
# Resource Request Models
# -----------------------------------------------------------------------------


@dataclass
class ResourceRequest:
    """A bottom-up resource request from Administration.

    These requests surface real capacity needs discovered during
    implementation planning. They flow upward to inform Executive review.
    """

    request_id: str
    resource_type: ResourceType
    description: str
    justification: str
    required_by: str  # ISO8601 date
    priority: ResourcePriority
    alternatives: list[str] = field(default_factory=list)
    quantity: float | None = None
    unit: str | None = None
    estimated_cost: float | None = None
    cost_currency: str = "USD"
    owner_portfolio_id: str = ""
    epic_id: str = ""
    schema_version: str = ADMIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "resource_type": self.resource_type.value,
            "description": self.description,
            "justification": self.justification,
            "required_by": self.required_by,
            "priority": self.priority.value,
            "alternatives": self.alternatives,
            "quantity": self.quantity,
            "unit": self.unit,
            "estimated_cost": self.estimated_cost,
            "cost_currency": self.cost_currency,
            "owner_portfolio_id": self.owner_portfolio_id,
            "epic_id": self.epic_id,
        }

    def validate(self) -> list[str]:
        """Validate resource request completeness."""
        errors: list[str] = []

        if not self.request_id:
            errors.append("ResourceRequest missing required field: request_id")
        if not self.description:
            errors.append("ResourceRequest missing required field: description")
        if not self.justification:
            errors.append("ResourceRequest missing required field: justification")
        if not self.required_by:
            errors.append("ResourceRequest missing required field: required_by")

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceRequest:
        """Create ResourceRequest from dictionary representation."""
        return cls(
            request_id=data["request_id"],
            resource_type=ResourceType(data["resource_type"]),
            description=data["description"],
            justification=data["justification"],
            required_by=data["required_by"],
            priority=ResourcePriority(data.get("priority", "MEDIUM")),
            alternatives=data.get("alternatives", []),
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            estimated_cost=data.get("estimated_cost"),
            cost_currency=data.get("cost_currency", "USD"),
            owner_portfolio_id=data.get("owner_portfolio_id", ""),
            epic_id=data.get("epic_id", ""),
            schema_version=data.get("schema_version", ADMIN_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Capacity Commitment Models
# -----------------------------------------------------------------------------


@dataclass
class CapacityCommitment:
    """Reality-based capacity commitment from a portfolio.

    This represents what Administration believes can actually be delivered,
    based on real resource availability and constraints.
    """

    portfolio_id: str
    committed_units: float
    unit_label: str  # e.g., "story_points", "hours", "sprints"
    confidence: ConfidenceLevel
    assumptions: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    epic_id: str = ""
    schema_version: str = ADMIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "portfolio_id": self.portfolio_id,
            "committed_units": self.committed_units,
            "unit_label": self.unit_label,
            "confidence": self.confidence.value,
            "assumptions": self.assumptions,
            "caveats": self.caveats,
            "risk_factors": self.risk_factors,
            "epic_id": self.epic_id,
        }

    def validate(self) -> list[str]:
        """Validate capacity commitment completeness."""
        errors: list[str] = []

        if not self.portfolio_id:
            errors.append("CapacityCommitment missing required field: portfolio_id")
        if self.committed_units < 0:
            errors.append("CapacityCommitment committed_units must be >= 0")
        if not self.unit_label:
            errors.append("CapacityCommitment missing required field: unit_label")

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapacityCommitment:
        """Create CapacityCommitment from dictionary representation."""
        return cls(
            portfolio_id=data["portfolio_id"],
            committed_units=data["committed_units"],
            unit_label=data["unit_label"],
            confidence=ConfidenceLevel(data.get("confidence", "MEDIUM")),
            assumptions=data.get("assumptions", []),
            caveats=data.get("caveats", []),
            risk_factors=data.get("risk_factors", []),
            epic_id=data.get("epic_id", ""),
            schema_version=data.get("schema_version", ADMIN_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Tactic and Spec Reference Models
# -----------------------------------------------------------------------------


@dataclass
class TacticProposal:
    """A tactical approach proposed for implementing an epic.

    Tactics describe the "how" at an actionable level, including
    prerequisites and dependencies.
    """

    tactic_id: str
    description: str
    rationale: str
    prerequisites: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    estimated_duration: str = ""  # ISO8601 duration, e.g., "P7D"
    owner_portfolio_id: str = ""
    schema_version: str = ADMIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tactic_id": self.tactic_id,
            "description": self.description,
            "rationale": self.rationale,
            "prerequisites": self.prerequisites,
            "dependencies": self.dependencies,
            "estimated_duration": self.estimated_duration,
            "owner_portfolio_id": self.owner_portfolio_id,
        }

    def validate(self) -> list[str]:
        """Validate tactic proposal completeness."""
        errors: list[str] = []

        if not self.tactic_id:
            errors.append("TacticProposal missing required field: tactic_id")
        if not self.description:
            errors.append("TacticProposal missing required field: description")
        if not self.rationale:
            errors.append("TacticProposal missing required field: rationale")

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TacticProposal:
        """Create TacticProposal from dictionary representation."""
        return cls(
            tactic_id=data["tactic_id"],
            description=data["description"],
            rationale=data["rationale"],
            prerequisites=data.get("prerequisites", []),
            dependencies=data.get("dependencies", []),
            estimated_duration=data.get("estimated_duration", ""),
            owner_portfolio_id=data.get("owner_portfolio_id", ""),
            schema_version=data.get("schema_version", ADMIN_SCHEMA_VERSION),
        )


@dataclass
class TechnicalSpecReference:
    """Reference to a technical specification artifact."""

    spec_id: str
    spec_type: SpecType
    location: str  # File path or URL
    summary: str
    version: str = ""
    last_updated: str = ""  # ISO8601 timestamp
    schema_version: str = ADMIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "spec_type": self.spec_type.value,
            "location": self.location,
            "summary": self.summary,
            "version": self.version,
            "last_updated": self.last_updated,
        }

    def validate(self) -> list[str]:
        """Validate spec reference completeness."""
        errors: list[str] = []

        if not self.spec_id:
            errors.append("TechnicalSpecReference missing required field: spec_id")
        if not self.location:
            errors.append("TechnicalSpecReference missing required field: location")
        if not self.summary:
            errors.append("TechnicalSpecReference missing required field: summary")

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TechnicalSpecReference:
        """Create TechnicalSpecReference from dictionary representation."""
        return cls(
            spec_id=data["spec_id"],
            spec_type=SpecType(data["spec_type"]),
            location=data["location"],
            summary=data["summary"],
            version=data.get("version", ""),
            last_updated=data.get("last_updated", ""),
            schema_version=data.get("schema_version", ADMIN_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Implementation Risk Models
# -----------------------------------------------------------------------------


@dataclass
class ImplementationRisk:
    """An identified risk for implementation.

    Risks discovered during Administrative analysis that may affect
    delivery success or require executive attention.
    """

    risk_id: str
    description: str
    likelihood: RiskLikelihood
    impact: RiskImpact
    mitigation_strategy: str
    owner_portfolio_id: str = ""
    contingency_plan: str = ""
    trigger_conditions: list[str] = field(default_factory=list)
    affected_epics: list[str] = field(default_factory=list)
    schema_version: str = ADMIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "risk_id": self.risk_id,
            "description": self.description,
            "likelihood": self.likelihood.value,
            "impact": self.impact.value,
            "mitigation_strategy": self.mitigation_strategy,
            "owner_portfolio_id": self.owner_portfolio_id,
            "contingency_plan": self.contingency_plan,
            "trigger_conditions": self.trigger_conditions,
            "affected_epics": self.affected_epics,
        }

    def validate(self) -> list[str]:
        """Validate implementation risk completeness."""
        errors: list[str] = []

        if not self.risk_id:
            errors.append("ImplementationRisk missing required field: risk_id")
        if not self.description:
            errors.append("ImplementationRisk missing required field: description")
        if not self.mitigation_strategy:
            errors.append(
                "ImplementationRisk missing required field: mitigation_strategy"
            )

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImplementationRisk:
        """Create ImplementationRisk from dictionary representation."""
        return cls(
            risk_id=data["risk_id"],
            description=data["description"],
            likelihood=RiskLikelihood(data["likelihood"]),
            impact=RiskImpact(data["impact"]),
            mitigation_strategy=data["mitigation_strategy"],
            owner_portfolio_id=data.get("owner_portfolio_id", ""),
            contingency_plan=data.get("contingency_plan", ""),
            trigger_conditions=data.get("trigger_conditions", []),
            affected_epics=data.get("affected_epics", []),
            schema_version=data.get("schema_version", ADMIN_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Implementation Proposal Model (aggregate)
# -----------------------------------------------------------------------------


@dataclass
class ImplementationProposal:
    """Complete implementation proposal for an epic.

    This is the primary output artifact from Administrative Pipeline,
    containing all tactical, resource, and risk information needed
    for Executive Review (E4).
    """

    proposal_id: str
    cycle_id: str
    motion_id: str
    epic_id: str
    created_at: str  # ISO8601 timestamp
    proposing_portfolio_id: str
    tactics: list[TacticProposal] = field(default_factory=list)
    spec_references: list[TechnicalSpecReference] = field(default_factory=list)
    risks: list[ImplementationRisk] = field(default_factory=list)
    resource_requests: list[ResourceRequest] = field(default_factory=list)
    capacity_commitment: CapacityCommitment | None = None
    discovery_findings: list[str] = field(default_factory=list)
    assumptions_validated: list[str] = field(default_factory=list)
    assumptions_invalidated: list[str] = field(default_factory=list)
    schema_version: str = ADMIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposal_id": self.proposal_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "epic_id": self.epic_id,
            "created_at": self.created_at,
            "proposing_portfolio_id": self.proposing_portfolio_id,
            "tactics": [t.to_dict() for t in self.tactics],
            "spec_references": [s.to_dict() for s in self.spec_references],
            "risks": [r.to_dict() for r in self.risks],
            "resource_requests": [rr.to_dict() for rr in self.resource_requests],
            "capacity_commitment": (
                self.capacity_commitment.to_dict() if self.capacity_commitment else None
            ),
            "discovery_findings": self.discovery_findings,
            "assumptions_validated": self.assumptions_validated,
            "assumptions_invalidated": self.assumptions_invalidated,
        }

    def validate(self) -> list[str]:
        """Validate implementation proposal completeness."""
        errors: list[str] = []

        if not self.proposal_id:
            errors.append("ImplementationProposal missing required field: proposal_id")
        if not self.cycle_id:
            errors.append("ImplementationProposal missing required field: cycle_id")
        if not self.motion_id:
            errors.append("ImplementationProposal missing required field: motion_id")
        if not self.epic_id:
            errors.append("ImplementationProposal missing required field: epic_id")
        if not self.created_at:
            errors.append("ImplementationProposal missing required field: created_at")
        if not self.proposing_portfolio_id:
            errors.append(
                "ImplementationProposal missing required field: proposing_portfolio_id"
            )

        # Must have at least one tactic
        if not self.tactics:
            errors.append(f"Proposal {self.proposal_id}: requires at least one tactic")

        # Validate nested objects
        for t in self.tactics:
            errors.extend(t.validate())
        for s in self.spec_references:
            errors.extend(s.validate())
        for r in self.risks:
            errors.extend(r.validate())
        for rr in self.resource_requests:
            errors.extend(rr.validate())
        if self.capacity_commitment:
            errors.extend(self.capacity_commitment.validate())

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImplementationProposal:
        """Create ImplementationProposal from dictionary representation."""
        tactics = [TacticProposal.from_dict(t) for t in data.get("tactics", [])]
        spec_references = [
            TechnicalSpecReference.from_dict(s) for s in data.get("spec_references", [])
        ]
        risks = [ImplementationRisk.from_dict(r) for r in data.get("risks", [])]
        resource_requests = [
            ResourceRequest.from_dict(rr) for rr in data.get("resource_requests", [])
        ]
        capacity_commitment = None
        if data.get("capacity_commitment"):
            capacity_commitment = CapacityCommitment.from_dict(
                data["capacity_commitment"]
            )

        return cls(
            proposal_id=data["proposal_id"],
            cycle_id=data["cycle_id"],
            motion_id=data["motion_id"],
            epic_id=data["epic_id"],
            created_at=data["created_at"],
            proposing_portfolio_id=data["proposing_portfolio_id"],
            tactics=tactics,
            spec_references=spec_references,
            risks=risks,
            resource_requests=resource_requests,
            capacity_commitment=capacity_commitment,
            discovery_findings=data.get("discovery_findings", []),
            assumptions_validated=data.get("assumptions_validated", []),
            assumptions_invalidated=data.get("assumptions_invalidated", []),
            schema_version=data.get("schema_version", ADMIN_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Aggregated Resource Summary
# -----------------------------------------------------------------------------


@dataclass
class AggregatedResourceSummary:
    """Aggregated view of all resource requests across proposals.

    Used for Executive Review to understand total resource impact.
    """

    cycle_id: str
    motion_id: str
    created_at: str
    total_requests: int
    requests_by_type: dict[str, int] = field(default_factory=dict)
    requests_by_priority: dict[str, int] = field(default_factory=dict)
    requests_by_portfolio: dict[str, int] = field(default_factory=dict)
    all_requests: list[ResourceRequest] = field(default_factory=list)
    total_estimated_cost: float = 0.0
    cost_currency: str = "USD"
    schema_version: str = ADMIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "created_at": self.created_at,
            "total_requests": self.total_requests,
            "requests_by_type": self.requests_by_type,
            "requests_by_priority": self.requests_by_priority,
            "requests_by_portfolio": self.requests_by_portfolio,
            "all_requests": [r.to_dict() for r in self.all_requests],
            "total_estimated_cost": self.total_estimated_cost,
            "cost_currency": self.cost_currency,
        }

    @classmethod
    def from_proposals(
        cls,
        proposals: list[ImplementationProposal],
        cycle_id: str,
        motion_id: str,
        created_at: str,
    ) -> AggregatedResourceSummary:
        """Aggregate resource requests from multiple proposals."""
        all_requests: list[ResourceRequest] = []
        requests_by_type: dict[str, int] = {}
        requests_by_priority: dict[str, int] = {}
        requests_by_portfolio: dict[str, int] = {}
        total_cost = 0.0

        for proposal in proposals:
            for rr in proposal.resource_requests:
                all_requests.append(rr)

                # Count by type
                type_key = rr.resource_type.value
                requests_by_type[type_key] = requests_by_type.get(type_key, 0) + 1

                # Count by priority
                priority_key = rr.priority.value
                requests_by_priority[priority_key] = (
                    requests_by_priority.get(priority_key, 0) + 1
                )

                # Count by portfolio
                portfolio_key = rr.owner_portfolio_id or "unassigned"
                requests_by_portfolio[portfolio_key] = (
                    requests_by_portfolio.get(portfolio_key, 0) + 1
                )

                # Sum cost
                if rr.estimated_cost:
                    total_cost += rr.estimated_cost

        return cls(
            cycle_id=cycle_id,
            motion_id=motion_id,
            created_at=created_at,
            total_requests=len(all_requests),
            requests_by_type=requests_by_type,
            requests_by_priority=requests_by_priority,
            requests_by_portfolio=requests_by_portfolio,
            all_requests=all_requests,
            total_estimated_cost=total_cost,
        )
