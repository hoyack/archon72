"""Domain models for Executive planning pipeline.

This stage transforms ratified intent (WHAT) into execution plans (HOW)
through bounded Executive-branch deliberation and explicit attestations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NoActionReason(str, Enum):
    """Enumerated reasons for no-action attestations."""

    OUTSIDE_PORTFOLIO_SCOPE = "OUTSIDE_PORTFOLIO_SCOPE"
    MOTION_DOES_NOT_REQUIRE_MY_DOMAIN = "MOTION_DOES_NOT_REQUIRE_MY_DOMAIN"
    NO_CAPACITY_AVAILABLE = "NO_CAPACITY_AVAILABLE"
    DELEGATED_TO_OTHER_PORTFOLIO = "DELEGATED_TO_OTHER_PORTFOLIO"


class GateStatus(str, Enum):
    """Gate pass/fail status for Executive completeness checks."""

    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class CapacityClaim:
    """Coarse capacity visibility, even when claiming none."""

    claim_type: str  # NONE | COARSE_ESTIMATE
    units: float | None = None
    unit_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_type": self.claim_type,
            "units": self.units,
            "unit_label": self.unit_label,
        }


@dataclass
class Blocker:
    """A portfolio-scoped blocker raised during Executive planning."""

    severity: str  # LOW|MEDIUM|HIGH|CRITICAL
    description: str
    requires_escalation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "description": self.description,
            "requires_escalation": self.requires_escalation,
        }


@dataclass
class PortfolioIdentity:
    """Identity binding between a portfolio and its President."""

    portfolio_id: str
    president_id: str
    president_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "president_id": self.president_id,
            "president_name": self.president_name,
        }


@dataclass
class RatifiedIntentPacket:
    """Formal handoff contract from Review pipeline to Executive."""

    packet_id: str
    created_at: str
    motion_id: str
    ratified_motion: dict[str, Any]
    ratification_record: dict[str, Any]
    review_artifacts: dict[str, Any]
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "created_at": self.created_at,
            "motion_id": self.motion_id,
            "ratified_motion": self.ratified_motion,
            "ratification_record": self.ratification_record,
            "review_artifacts": self.review_artifacts,
            "provenance": self.provenance,
        }


@dataclass
class PortfolioContribution:
    """Explicit portfolio contribution to an execution plan."""

    cycle_id: str
    motion_id: str
    portfolio: PortfolioIdentity
    tasks: list[dict[str, Any]]
    capacity_claim: CapacityClaim
    blockers: list[Blocker] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "portfolio": self.portfolio.to_dict(),
            "tasks": self.tasks,
            "capacity_claim": self.capacity_claim.to_dict(),
            "blockers": [b.to_dict() for b in self.blockers],
        }


@dataclass
class NoActionAttestation:
    """Explicit attestation that no contribution is being made."""

    cycle_id: str
    motion_id: str
    portfolio: PortfolioIdentity
    reason_code: NoActionReason
    explanation: str
    capacity_claim: CapacityClaim

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "portfolio": self.portfolio.to_dict(),
            "reason_code": self.reason_code.value,
            "explanation": self.explanation,
            "capacity_claim": self.capacity_claim.to_dict(),
        }


@dataclass
class ExecutiveGates:
    """Executive completeness/integrity/visibility gate outcomes."""

    completeness: GateStatus
    integrity: GateStatus
    visibility: GateStatus
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "completeness": self.completeness.value,
            "integrity": self.integrity.value,
            "visibility": self.visibility.value,
            "failures": self.failures,
        }


@dataclass
class ExecutiveCycleResult:
    """Result of an Executive mini-conclave planning cycle."""

    cycle_id: str
    motion_id: str
    plan_owner: PortfolioIdentity
    contributions: list[PortfolioContribution]
    attestations: list[NoActionAttestation]
    blockers_requiring_escalation: list[Blocker]
    execution_plan: dict[str, Any]
    gates: ExecutiveGates

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "plan_owner": self.plan_owner.to_dict(),
            "contributions": [c.to_dict() for c in self.contributions],
            "attestations": [a.to_dict() for a in self.attestations],
            "blockers_requiring_escalation": [
                b.to_dict() for b in self.blockers_requiring_escalation
            ],
            "execution_plan": self.execution_plan,
            "gates": self.gates.to_dict(),
        }
