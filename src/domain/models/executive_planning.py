"""Domain models for Executive planning pipeline.

This stage transforms ratified intent (WHAT) into execution plans (HOW)
through bounded Executive-branch deliberation and explicit attestations.

Schema Versions:
- 1.x: Original blocker model with requires_escalation flag
- 2.0: Expanded blocker model with class, disposition, and validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Schema version for v2 artifacts
SCHEMA_VERSION = "2.0"
SCHEMA_VERSION_V1 = "1.0"


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


# -----------------------------------------------------------------------------
# Blocker Model v2: Classification + Disposition
# -----------------------------------------------------------------------------


class BlockerClass(str, Enum):
    """Classification of blocker type.

    Each class has constraints on valid dispositions:
    - INTENT_AMBIGUITY: Must use ESCALATE_NOW
    - EXECUTION_UNCERTAINTY: May use MITIGATE_IN_EXECUTIVE or DEFER_DOWNSTREAM
    - CAPACITY_CONFLICT: May use MITIGATE_IN_EXECUTIVE or DEFER_DOWNSTREAM
    """

    INTENT_AMBIGUITY = "INTENT_AMBIGUITY"
    EXECUTION_UNCERTAINTY = "EXECUTION_UNCERTAINTY"
    CAPACITY_CONFLICT = "CAPACITY_CONFLICT"


class BlockerDisposition(str, Enum):
    """How a blocker should be handled.

    - ESCALATE_NOW: Requires Conclave deliberation (emits conclave_queue_item)
    - MITIGATE_IN_EXECUTIVE: Presidents resolve in E2.5 (requires mitigation_notes)
    - DEFER_DOWNSTREAM: Convert to discovery tasks (requires verification_tasks)
    """

    ESCALATE_NOW = "ESCALATE_NOW"
    MITIGATE_IN_EXECUTIVE = "MITIGATE_IN_EXECUTIVE"
    DEFER_DOWNSTREAM = "DEFER_DOWNSTREAM"


class BlockerSeverity(str, Enum):
    """Severity level for blockers."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class VerificationTask:
    """A task to verify resolution of a deferred blocker.

    Required when disposition is DEFER_DOWNSTREAM.
    """

    task_id: str
    description: str
    success_signal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "success_signal": self.success_signal,
        }


@dataclass
class BlockerV2:
    """A portfolio-scoped blocker with full classification and disposition (v2).

    This replaces the simple Blocker model with explicit classification,
    disposition, and validation to prevent "blocker spam" from halting planning.
    """

    id: str
    blocker_class: BlockerClass
    severity: BlockerSeverity
    description: str
    owner_portfolio_id: str
    disposition: BlockerDisposition
    ttl: str  # ISO8601 duration, e.g., "P7D"
    escalation_conditions: list[str]
    verification_tasks: list[VerificationTask] = field(default_factory=list)
    mitigation_notes: str | None = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "blocker_class": self.blocker_class.value,
            "severity": self.severity.value,
            "description": self.description,
            "owner_portfolio_id": self.owner_portfolio_id,
            "disposition": self.disposition.value,
            "ttl": self.ttl,
            "escalation_conditions": self.escalation_conditions,
            "verification_tasks": [vt.to_dict() for vt in self.verification_tasks],
            "mitigation_notes": self.mitigation_notes,
        }

    def validate(self) -> list[str]:
        """Validate blocker according to v2 rules.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        # Required fields
        if not self.id:
            errors.append("Blocker missing required field: id")
        if not self.description:
            errors.append("Blocker missing required field: description")
        if not self.owner_portfolio_id:
            errors.append("Blocker missing required field: owner_portfolio_id")
        if not self.ttl:
            errors.append("Blocker missing required field: ttl")
        if not self.escalation_conditions:
            errors.append("Blocker missing required field: escalation_conditions")

        # Intent ambiguity must escalate
        if (
            self.blocker_class == BlockerClass.INTENT_AMBIGUITY
            and self.disposition != BlockerDisposition.ESCALATE_NOW
        ):
            errors.append(
                f"Blocker {self.id}: INTENT_AMBIGUITY must have disposition ESCALATE_NOW"
            )

        # Defer downstream requires verification tasks
        if (
            self.disposition == BlockerDisposition.DEFER_DOWNSTREAM
            and not self.verification_tasks
        ):
            errors.append(
                f"Blocker {self.id}: DEFER_DOWNSTREAM requires non-empty verification_tasks"
            )

        # Mitigate in executive requires mitigation notes
        if (
            self.disposition == BlockerDisposition.MITIGATE_IN_EXECUTIVE
            and not self.mitigation_notes
        ):
            errors.append(
                f"Blocker {self.id}: MITIGATE_IN_EXECUTIVE requires mitigation_notes"
            )

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockerV2:
        """Create BlockerV2 from dictionary representation."""
        verification_tasks = [
            VerificationTask(
                task_id=vt["task_id"],
                description=vt["description"],
                success_signal=vt["success_signal"],
            )
            for vt in data.get("verification_tasks", [])
        ]

        return cls(
            id=data["id"],
            blocker_class=BlockerClass(data["blocker_class"]),
            severity=BlockerSeverity(data["severity"]),
            description=data["description"],
            owner_portfolio_id=data["owner_portfolio_id"],
            disposition=BlockerDisposition(data["disposition"]),
            ttl=data["ttl"],
            escalation_conditions=data.get("escalation_conditions", []),
            verification_tasks=verification_tasks,
            mitigation_notes=data.get("mitigation_notes"),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Downstream Artifacts (emitted by blockers)
# -----------------------------------------------------------------------------


@dataclass
class DiscoveryTaskStub:
    """A discovery task stub emitted for DEFER_DOWNSTREAM blockers.

    These are handed off to Administration for execution and tracking.
    """

    task_id: str
    origin_blocker_id: str
    question: str
    deliverable: str
    max_effort: str  # ISO8601 duration, e.g., "P3D"
    stop_conditions: list[str]
    ttl: str  # ISO8601 duration
    escalation_conditions: list[str]
    suggested_tools: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "origin_blocker_id": self.origin_blocker_id,
            "question": self.question,
            "deliverable": self.deliverable,
            "max_effort": self.max_effort,
            "stop_conditions": self.stop_conditions,
            "ttl": self.ttl,
            "escalation_conditions": self.escalation_conditions,
            "suggested_tools": self.suggested_tools,
        }


@dataclass
class ConclaveQueueItem:
    """An item for the Conclave deliberation queue.

    Emitted when INTENT_AMBIGUITY blockers require Conclave resolution.
    """

    queue_item_id: str
    cycle_id: str
    motion_id: str
    blocker_id: str
    blocker_class: BlockerClass
    questions: list[str]
    options: list[str]
    source_citations: list[str]
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "queue_item_id": self.queue_item_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "blocker_id": self.blocker_id,
            "blocker_class": self.blocker_class.value,
            "questions": self.questions,
            "options": self.options,
            "source_citations": self.source_citations,
            "created_at": self.created_at,
        }


# -----------------------------------------------------------------------------
# E2.5 Blocker Workup: Peer Review + Disposition
# -----------------------------------------------------------------------------


@dataclass
class BlockerPacket:
    """A packet of blockers submitted for E2.5 cross-review.

    Contains all blockers from portfolio drafting (E2) that need
    disposition validation and peer review before integration.
    """

    packet_id: str
    cycle_id: str
    motion_id: str
    blockers: list[BlockerV2]
    source_portfolios: list[str]
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "packet_id": self.packet_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "blockers": [b.to_dict() for b in self.blockers],
            "source_portfolios": self.source_portfolios,
            "created_at": self.created_at,
        }

    @classmethod
    def from_contributions(
        cls,
        cycle_id: str,
        motion_id: str,
        contributions: list[Any],  # PortfolioContribution
        created_at: str,
    ) -> BlockerPacket:
        """Create a BlockerPacket from portfolio contributions.

        Args:
            cycle_id: The executive cycle ID
            motion_id: The motion being planned
            contributions: List of PortfolioContribution objects
            created_at: ISO timestamp

        Returns:
            BlockerPacket containing all v2 blockers from contributions
        """
        blockers: list[BlockerV2] = []
        source_portfolios: list[str] = []

        for c in contributions:
            portfolio_id = c.portfolio.portfolio_id
            has_v2_blockers = False

            for b in c.blockers:
                if isinstance(b, BlockerV2):
                    blockers.append(b)
                    has_v2_blockers = True

            if has_v2_blockers and portfolio_id not in source_portfolios:
                source_portfolios.append(portfolio_id)

        import uuid

        return cls(
            packet_id=f"bp_{uuid.uuid4().hex[:12]}",
            cycle_id=cycle_id,
            motion_id=motion_id,
            blockers=blockers,
            source_portfolios=source_portfolios,
            created_at=created_at,
        )


@dataclass
class PeerReviewSummary:
    """Summary of E2.5 blocker workup peer review.

    Plan Owner emits this after cross-reviewing blockers from all portfolios.
    Identifies duplicates, conflicts, coverage gaps, and disposition rationale.
    """

    cycle_id: str
    motion_id: str
    plan_owner_portfolio_id: str
    duplicates_detected: list[list[str]]  # Groups of duplicate blocker IDs
    conflicts_detected: list[dict[str, Any]]  # Conflicting blocker pairs
    coverage_gaps: list[str]  # Identified gaps in portfolio coverage
    blocker_disposition_rationale: dict[str, str]  # blocker_id -> rationale
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "plan_owner_portfolio_id": self.plan_owner_portfolio_id,
            "duplicates_detected": self.duplicates_detected,
            "conflicts_detected": self.conflicts_detected,
            "coverage_gaps": self.coverage_gaps,
            "blocker_disposition_rationale": self.blocker_disposition_rationale,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PeerReviewSummary:
        """Create PeerReviewSummary from dictionary representation."""
        return cls(
            cycle_id=data["cycle_id"],
            motion_id=data["motion_id"],
            plan_owner_portfolio_id=data["plan_owner_portfolio_id"],
            duplicates_detected=data.get("duplicates_detected", []),
            conflicts_detected=data.get("conflicts_detected", []),
            coverage_gaps=data.get("coverage_gaps", []),
            blocker_disposition_rationale=data.get("blocker_disposition_rationale", {}),
            created_at=data["created_at"],
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


@dataclass
class BlockerWorkupResult:
    """Result of E2.5 blocker workup phase.

    Contains the peer review summary and any modifications to blocker
    dispositions that occurred during cross-review.
    """

    cycle_id: str
    motion_id: str
    peer_review_summary: PeerReviewSummary
    final_blockers: list[BlockerV2]
    conclave_queue_items: list[ConclaveQueueItem]
    discovery_task_stubs: list[DiscoveryTaskStub]
    workup_duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "peer_review_summary": self.peer_review_summary.to_dict(),
            "final_blockers": [b.to_dict() for b in self.final_blockers],
            "conclave_queue_items": [i.to_dict() for i in self.conclave_queue_items],
            "discovery_task_stubs": [s.to_dict() for s in self.discovery_task_stubs],
            "workup_duration_ms": self.workup_duration_ms,
        }


# -----------------------------------------------------------------------------
# Epic Model + Work Packages (v2)
# -----------------------------------------------------------------------------

# Forbidden fields that indicate v1 artifacts or Administrative-level detail
FORBIDDEN_EXECUTIVE_FIELDS = frozenset(
    [
        "story_points",
        "estimate",
        "hours",
        "FR",
        "NFR",
        "detailed_requirements",
        "functional_requirements",
        "non_functional_requirements",
    ]
)


@dataclass
class Epic:
    """An epic with acceptance intent for Executive planning (v2).

    Epics represent high-level work units with success signals, not detailed
    requirements. Story points, estimates, and FR/NFR belong in Administration.

    Validation Rules:
    - Must have at least one mapped_motion_clause (traceability)
    - Must have at least one success_signal (verifiability)
    """

    epic_id: str
    intent: str
    success_signals: list[str]
    constraints: list[str]
    assumptions: list[str]
    discovery_required: list[str]  # blocker_ids requiring discovery
    mapped_motion_clauses: list[str]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "epic_id": self.epic_id,
            "intent": self.intent,
            "success_signals": self.success_signals,
            "constraints": self.constraints,
            "assumptions": self.assumptions,
            "discovery_required": self.discovery_required,
            "mapped_motion_clauses": self.mapped_motion_clauses,
        }

    def validate(self) -> list[str]:
        """Validate epic according to v2 rules.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        # Required fields
        if not self.epic_id:
            errors.append("Epic missing required field: epic_id")
        if not self.intent:
            errors.append("Epic missing required field: intent")

        # Must have at least one mapped_motion_clause (traceability)
        if not self.mapped_motion_clauses:
            errors.append(
                f"Epic {self.epic_id}: requires at least one mapped_motion_clause "
                "(traceability)"
            )

        # Must have at least one success_signal (verifiability)
        if not self.success_signals:
            errors.append(
                f"Epic {self.epic_id}: requires at least one success_signal "
                "(verifiability)"
            )

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Epic:
        """Create Epic from dictionary representation."""
        return cls(
            epic_id=data["epic_id"],
            intent=data["intent"],
            success_signals=data.get("success_signals", []),
            constraints=data.get("constraints", []),
            assumptions=data.get("assumptions", []),
            discovery_required=data.get("discovery_required", []),
            mapped_motion_clauses=data.get("mapped_motion_clauses", []),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


@dataclass
class WorkPackage:
    """A thin work package for Executive planning (v2).

    Work packages describe scope without detail - no story points, estimates,
    or functional/non-functional requirements. Those belong in Administration.

    Forbidden fields: story_points, estimate, hours, FR, NFR, detailed_requirements
    """

    package_id: str
    epic_id: str
    scope_description: str
    portfolio_id: str
    dependencies: list[str] = field(default_factory=list)
    constraints_respected: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "epic_id": self.epic_id,
            "scope_description": self.scope_description,
            "portfolio_id": self.portfolio_id,
            "dependencies": self.dependencies,
            "constraints_respected": self.constraints_respected,
        }

    def validate(self) -> list[str]:
        """Validate work package according to v2 rules.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        if not self.package_id:
            errors.append("WorkPackage missing required field: package_id")
        if not self.epic_id:
            errors.append("WorkPackage missing required field: epic_id")
        if not self.scope_description:
            errors.append("WorkPackage missing required field: scope_description")
        if not self.portfolio_id:
            errors.append("WorkPackage missing required field: portfolio_id")

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkPackage:
        """Create WorkPackage from dictionary representation."""
        return cls(
            package_id=data["package_id"],
            epic_id=data["epic_id"],
            scope_description=data["scope_description"],
            portfolio_id=data["portfolio_id"],
            dependencies=data.get("dependencies", []),
            constraints_respected=data.get("constraints_respected", []),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


def validate_no_forbidden_fields(
    data: dict[str, Any],
    context: str = "artifact",
) -> list[str]:
    """Check that a dictionary does not contain forbidden Executive fields.

    Args:
        data: Dictionary to validate
        context: Description of the artifact for error messages

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []
    found = set(data.keys()) & FORBIDDEN_EXECUTIVE_FIELDS

    if found:
        errors.append(
            f"{context} contains forbidden Executive fields: {sorted(found)}. "
            "Story points, estimates, and FR/NFR belong in Administration."
        )

    # Also check nested structures
    for key, value in data.items():
        if isinstance(value, dict):
            nested_errors = validate_no_forbidden_fields(value, f"{context}.{key}")
            errors.extend(nested_errors)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    nested_errors = validate_no_forbidden_fields(
                        item, f"{context}.{key}[{i}]"
                    )
                    errors.extend(nested_errors)

    return errors


# -----------------------------------------------------------------------------
# Blocker Model v1: Legacy (kept for backward compatibility)
# -----------------------------------------------------------------------------


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
    """A portfolio-scoped blocker raised during Executive planning (v1 legacy).

    DEPRECATED: Use BlockerV2 for new code. This class is retained for
    backward compatibility with v1 artifacts.

    Note: The requires_escalation field is deprecated. In v2, use
    BlockerClass + BlockerDisposition instead.
    """

    severity: str  # LOW|MEDIUM|HIGH|CRITICAL
    description: str
    requires_escalation: bool = False  # DEPRECATED: use BlockerV2.disposition
    schema_version: str = SCHEMA_VERSION_V1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "severity": self.severity,
            "description": self.description,
            "requires_escalation": self.requires_escalation,
        }

    def to_v2(self, blocker_id: str, owner_portfolio_id: str) -> BlockerV2:
        """Convert v1 blocker to v2 format.

        Args:
            blocker_id: Unique identifier for the blocker
            owner_portfolio_id: Portfolio responsible for this blocker

        Returns:
            BlockerV2 with inferred class and disposition
        """
        # Infer v2 fields from v1 data
        if self.requires_escalation:
            blocker_class = BlockerClass.INTENT_AMBIGUITY
            disposition = BlockerDisposition.ESCALATE_NOW
        else:
            blocker_class = BlockerClass.EXECUTION_UNCERTAINTY
            disposition = BlockerDisposition.DEFER_DOWNSTREAM

        severity = (
            BlockerSeverity(self.severity)
            if self.severity in [s.value for s in BlockerSeverity]
            else BlockerSeverity.MEDIUM
        )

        return BlockerV2(
            id=blocker_id,
            blocker_class=blocker_class,
            severity=severity,
            description=self.description,
            owner_portfolio_id=owner_portfolio_id,
            disposition=disposition,
            ttl="P7D",  # Default TTL
            escalation_conditions=["Converted from v1 blocker - review required"],
            verification_tasks=[],
            mitigation_notes=None,
        )


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
    """Explicit portfolio contribution to an execution plan.

    Schema Evolution:
    - v1: Uses `tasks` field with dict format (may include story_points)
    - v2: Uses `work_packages` field with WorkPackage format (no story_points)

    Both fields are supported for backward compatibility. New code should
    use work_packages. The tasks field is deprecated but retained for v1 loading.
    """

    cycle_id: str
    motion_id: str
    portfolio: PortfolioIdentity
    tasks: list[dict[str, Any]]  # v1: deprecated, use work_packages
    capacity_claim: CapacityClaim
    blockers: list[Blocker] = field(default_factory=list)
    work_packages: list[WorkPackage] = field(default_factory=list)  # v2
    schema_version: str = SCHEMA_VERSION_V1  # Default to v1 for backward compat

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "portfolio": self.portfolio.to_dict(),
            "capacity_claim": self.capacity_claim.to_dict(),
            "blockers": [b.to_dict() for b in self.blockers],
        }

        # Include appropriate field based on schema version
        if self.schema_version == SCHEMA_VERSION:
            result["work_packages"] = [wp.to_dict() for wp in self.work_packages]
        else:
            result["tasks"] = self.tasks

        return result

    def validate(self) -> list[str]:
        """Validate contribution according to schema version rules.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        if self.schema_version == SCHEMA_VERSION:
            # v2 validation: check work_packages, no forbidden fields
            if not self.work_packages and not self.tasks:
                errors.append(
                    f"Contribution from {self.portfolio.portfolio_id}: "
                    "requires work_packages (v2) or tasks (v1)"
                )

            for wp in self.work_packages:
                errors.extend(wp.validate())

            # Check for forbidden fields in any task dicts
            for i, task in enumerate(self.tasks):
                task_errors = validate_no_forbidden_fields(
                    task, f"contribution.tasks[{i}]"
                )
                errors.extend(task_errors)
        else:
            # v1 validation: just check tasks exist
            if not self.tasks:
                errors.append(
                    f"Contribution from {self.portfolio.portfolio_id}: "
                    "requires non-empty tasks"
                )

        return errors


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
    """Result of an Executive mini-conclave planning cycle.

    Schema Evolution:
    - v1: Uses blockers_requiring_escalation (list of v1 Blocker)
    - v2: Uses epics, work_packages_summary, and v2 blockers with dispositions
    """

    cycle_id: str
    motion_id: str
    plan_owner: PortfolioIdentity
    contributions: list[PortfolioContribution]
    attestations: list[NoActionAttestation]
    blockers_requiring_escalation: list[Blocker]  # v1 legacy
    execution_plan: dict[str, Any]
    gates: ExecutiveGates
    epics: list[Epic] = field(default_factory=list)  # v2
    discovery_task_stubs: list[DiscoveryTaskStub] = field(default_factory=list)  # v2
    conclave_queue_items: list[ConclaveQueueItem] = field(default_factory=list)  # v2
    schema_version: str = SCHEMA_VERSION_V1

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": self.schema_version,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "plan_owner": self.plan_owner.to_dict(),
            "contributions": [c.to_dict() for c in self.contributions],
            "attestations": [a.to_dict() for a in self.attestations],
            "execution_plan": self.execution_plan,
            "gates": self.gates.to_dict(),
        }

        if self.schema_version == SCHEMA_VERSION:
            # v2 output
            result["epics"] = [e.to_dict() for e in self.epics]
            result["discovery_task_stubs"] = [
                s.to_dict() for s in self.discovery_task_stubs
            ]
            result["conclave_queue_items"] = [
                i.to_dict() for i in self.conclave_queue_items
            ]
        else:
            # v1 output (legacy)
            result["blockers_requiring_escalation"] = [
                b.to_dict() for b in self.blockers_requiring_escalation
            ]

        return result

    def validate(self) -> list[str]:
        """Validate cycle result according to schema version rules.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        if self.schema_version == SCHEMA_VERSION:
            # v2 validation: check epics
            for epic in self.epics:
                errors.extend(epic.validate())

            # Check for forbidden fields in execution plan
            if self.execution_plan:
                plan_errors = validate_no_forbidden_fields(
                    self.execution_plan, "execution_plan"
                )
                errors.extend(plan_errors)

        return errors
