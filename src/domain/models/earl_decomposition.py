"""Earl Decomposition Bridge domain models.

Defines TaskDraft, DecompositionStatus, and lint helpers for the bridge
between the Executive Pipeline (winning Duke proposal) and the Governance
Layer (TaskActivationService.create_activation).

A TaskDraft is the bridge's internal representation of an activation-ready
task. It maps directly to the arguments of create_activation().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecompositionStatus(str, Enum):
    """Per-tactic decomposition outcome."""

    COMPLETED = "completed"
    AMBIGUOUS = "ambiguous"
    REVIEW_REQUIRED = "review_required"
    OVERLAP_REVIEW = "overlap_review"
    FAILED = "failed"
    FAILED_LINT = "failed_lint"


@dataclass(frozen=True)
class EarlVote:
    """Tracks one Earl's contribution during multi-Earl synthesis.

    Each Earl independently decomposes a tactic; the facilitator Earl
    then synthesizes the best elements. EarlVote records which Earls
    contributed to the final output for audit.
    """

    earl_name: str
    earl_id: str
    task_count: int = 0
    succeeded: bool = True
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "earl_name": self.earl_name,
            "earl_id": self.earl_id,
            "task_count": self.task_count,
            "succeeded": self.succeeded,
            "failure_reason": self.failure_reason,
        }


class RoutingBlockReason(str, Enum):
    """Reason a TaskDraft could not be routed."""

    BLOCKED_BY_CAPABILITY = "blocked_by_capability"
    BLOCKED_BY_CAPACITY = "blocked_by_capacity"
    ROUTED_WITH_CAPACITY_DEBT = "routed_with_capacity_debt"


SCHEMA_VERSION = "1.0"

# Placeholder / generic terms that fail legibility lint
_NON_LEGIBLE_OUTCOMES = frozenset(
    {"tbd", "???", "n/a", "todo", "finished", "done", "complete", "completed"}
)

# Pattern to detect FR/NFR requirement IDs in text
_REQUIREMENT_ID_PATTERN = re.compile(
    r"\b(?:FR|NFR)-[A-Z]{2,8}-\d{1,4}\b", re.IGNORECASE
)


@dataclass(frozen=True)
class TaskDraft:
    """Activation-ready task produced by the decomposition bridge.

    Maps directly to TaskActivationService.create_activation() arguments:
      - description  -> description
      - requirements -> requirements
      - expected_outcomes -> expected_outcomes

    Additional fields support capability matching, provenance, and audit.
    """

    task_ref: str
    parent_tactic_id: str
    rfp_id: str
    mandate_id: str
    proposal_id: str
    description: str
    requirements: list[str] = field(default_factory=list)
    expected_outcomes: list[str] = field(default_factory=list)
    capability_tags: list[str] = field(default_factory=list)
    effort_hours: float = 0.0
    deliverable_id: str = ""
    dependencies: list[str] = field(default_factory=list)
    vote_count: int = 0
    contributing_earls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "task_ref": self.task_ref,
            "parent_tactic_id": self.parent_tactic_id,
            "rfp_id": self.rfp_id,
            "mandate_id": self.mandate_id,
            "proposal_id": self.proposal_id,
            "description": self.description,
            "requirements": list(self.requirements),
            "expected_outcomes": list(self.expected_outcomes),
            "capability_tags": list(self.capability_tags),
            "effort_hours": self.effort_hours,
            "deliverable_id": self.deliverable_id,
            "dependencies": list(self.dependencies),
        }
        if self.vote_count:
            d["vote_count"] = self.vote_count
        if self.contributing_earls:
            d["contributing_earls"] = list(self.contributing_earls)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskDraft:
        return cls(
            task_ref=data["task_ref"],
            parent_tactic_id=data["parent_tactic_id"],
            rfp_id=data.get("rfp_id", ""),
            mandate_id=data.get("mandate_id", ""),
            proposal_id=data.get("proposal_id", ""),
            description=data["description"],
            requirements=data.get("requirements", []),
            expected_outcomes=data.get("expected_outcomes", []),
            capability_tags=data.get("capability_tags", []),
            effort_hours=float(data.get("effort_hours", 0.0)),
            deliverable_id=data.get("deliverable_id", ""),
            dependencies=data.get("dependencies", []),
            vote_count=int(data.get("vote_count", 0)),
            contributing_earls=data.get("contributing_earls", []),
        )


# ------------------------------------------------------------------
# Hard lint (must-pass)
# ------------------------------------------------------------------


def lint_task_draft(draft: TaskDraft) -> list[str]:
    """Validate a TaskDraft against hard lint rules.

    Returns a list of violation descriptions. Empty list means pass.

    Rules (from Lint Checklist Section A):
    1. description non-empty
    2. expected_outcomes length >= 2
    3. capability_tags length >= 1
    4. effort_hours > 0
    5. parent_tactic_id present
    6. outcomes are not placeholder/generic text
    """
    violations: list[str] = []

    # A-1: Empty description
    if not draft.description or not draft.description.strip():
        violations.append("Empty description")

    # A-2: Insufficient expected outcomes
    if len(draft.expected_outcomes) < 2:
        violations.append(
            f"Insufficient expected outcomes: {len(draft.expected_outcomes)} < 2"
        )

    # A-3: No capability tags
    if not draft.capability_tags:
        violations.append("No capability tags")

    # A-4: Zero/negative effort
    if draft.effort_hours <= 0:
        violations.append(f"Zero/negative effort: {draft.effort_hours}")

    # A-5: Missing parent tactic
    if not draft.parent_tactic_id or not draft.parent_tactic_id.strip():
        violations.append("Missing parent tactic ID")

    # A-6: Non-legible outcomes
    for outcome in draft.expected_outcomes:
        stripped = outcome.strip().lower().rstrip(".")
        if stripped in _NON_LEGIBLE_OUTCOMES:
            violations.append(f"Non-legible outcome: '{outcome}'")

    return violations


# ------------------------------------------------------------------
# Provenance lint (soft — returns events, does not block)
# ------------------------------------------------------------------


def check_provenance_mapping(draft: TaskDraft) -> list[str]:
    """Check provenance mapping quality for a TaskDraft.

    Returns list of event descriptions. Empty means strong mapping.

    From Lint Checklist Section B:
    If deliverable_id is set, at least one requirement should include
    an FR or NFR id. If not, emit bridge.provenance.weak_mapping.
    """
    events: list[str] = []

    if draft.deliverable_id:
        has_req_id = any(
            _REQUIREMENT_ID_PATTERN.search(req) for req in draft.requirements
        )
        if not has_req_id:
            events.append(
                f"Weak provenance: deliverable {draft.deliverable_id} "
                f"has no FR/NFR id in requirements"
            )

    return events


# ------------------------------------------------------------------
# Tactic-level lint
# ------------------------------------------------------------------


def detect_overlap(drafts: list[TaskDraft]) -> list[tuple[str, str]]:
    """Detect overlapping TaskDrafts within a tactic's output.

    Returns pairs of (task_ref_a, task_ref_b) that share the same
    deliverable_id and have substantially similar expected outcomes.
    """
    overlaps: list[tuple[str, str]] = []
    for i in range(len(drafts)):
        for j in range(i + 1, len(drafts)):
            a, b = drafts[i], drafts[j]
            if not a.deliverable_id or not b.deliverable_id:
                continue
            if a.deliverable_id != b.deliverable_id:
                continue
            # Check outcome similarity (exact match after normalization)
            outcomes_a = {o.strip().lower() for o in a.expected_outcomes}
            outcomes_b = {o.strip().lower() for o in b.expected_outcomes}
            if outcomes_a and outcomes_b and outcomes_a == outcomes_b:
                overlaps.append((a.task_ref, b.task_ref))
    return overlaps


# ------------------------------------------------------------------
# Manifest / summary models
# ------------------------------------------------------------------


@dataclass
class TacticDecompositionEntry:
    """One row in the decomposition manifest."""

    tactic_id: str
    tactic_title: str
    status: DecompositionStatus
    task_refs: list[str] = field(default_factory=list)
    failure_reason: str = ""
    events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tactic_id": self.tactic_id,
            "tactic_title": self.tactic_title,
            "status": self.status.value,
            "task_refs": self.task_refs,
            "failure_reason": self.failure_reason,
            "events": self.events,
        }


@dataclass
class ActivationManifestEntry:
    """One row in the activation manifest."""

    task_ref: str
    parent_tactic_id: str
    deliverable_id: str
    rfp_requirement_ids: list[str] = field(default_factory=list)
    cluster_id: str = ""
    activation_id: str = ""
    status: str = ""
    routing_block_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_ref": self.task_ref,
            "parent_tactic_id": self.parent_tactic_id,
            "deliverable_id": self.deliverable_id,
            "rfp_requirement_ids": self.rfp_requirement_ids,
            "cluster_id": self.cluster_id,
            "activation_id": self.activation_id,
            "status": self.status,
            "routing_block_reason": self.routing_block_reason,
        }


@dataclass
class BridgeSummary:
    """Summary statistics for the bridge run."""

    schema_version: str = SCHEMA_VERSION
    artifact_type: str = "earl_decomposition_summary"
    rfp_id: str = ""
    mandate_id: str = ""
    proposal_id: str = ""
    winning_duke_name: str = ""
    created_at: str = ""
    total_tactics: int = 0
    total_task_drafts: int = 0
    activations_attempted: int = 0
    activations_created: int = 0
    activations_failed: int = 0
    ambiguous_tactics: int = 0
    no_eligible_cluster: int = 0
    capacity_blocked: int = 0
    explosion_review: int = 0
    overlap_review: int = 0
    weak_provenance: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": self.artifact_type,
            "rfp_id": self.rfp_id,
            "mandate_id": self.mandate_id,
            "proposal_id": self.proposal_id,
            "winning_duke_name": self.winning_duke_name,
            "created_at": self.created_at,
            "total_tactics": self.total_tactics,
            "total_task_drafts": self.total_task_drafts,
            "activations_attempted": self.activations_attempted,
            "activations_created": self.activations_created,
            "activations_failed": self.activations_failed,
            "ambiguous_tactics": self.ambiguous_tactics,
            "no_eligible_cluster": self.no_eligible_cluster,
            "capacity_blocked": self.capacity_blocked,
            "explosion_review": self.explosion_review,
            "overlap_review": self.overlap_review,
            "weak_provenance": self.weak_provenance,
        }
