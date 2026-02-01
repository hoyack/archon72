"""Aggregation models — multi-task result aggregation without judgment.

Sprint: Aggregation Without Judgment + Evidence-Backed Coverage

These models represent the mechanical outcome of aggregating results
from multiple tasks that share a deliverable. The system checks:

1. Requirement coverage — are all rfp_requirement_ids covered?
2. Evidence verification — does each covered requirement have proof?
3. Conflict detection — same requirement, different clusters?
4. Disposition — COMPLETE, UNVERIFIED, INCOMPLETE, or CONFLICTED

The system NEVER picks between conflicting results. It produces a
conflict artifact that is Duke-readable and escalates when conflicts
affect mandate viability.

COMPLETE requires evidence. Claiming coverage without proof produces
UNVERIFIED — structurally distinct from INCOMPLETE (no task at all)
and CONFLICTED (multiple clusters disagree).

Constitutional Constraints:
- Aggregation is procedural, not qualitative (no "best answer" selection)
- COMPLETE is mandatory-evidence: artifact_refs or acceptance_test_results
- Conflicts are escalated, not resolved silently
- Coverage is measured against acceptance criteria, not human judgment
- Every aggregation produces an auditable artifact
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AggregationDisposition(str, Enum):
    """Disposition of aggregation — what the coverage analysis found."""

    COMPLETE = "COMPLETE"
    """All requirements covered with evidence, no conflicts."""

    UNVERIFIED = "UNVERIFIED"
    """All requirements covered by task metadata but evidence is missing."""

    INCOMPLETE = "INCOMPLETE"
    """One or more requirements have no covering task."""

    CONFLICTED = "CONFLICTED"
    """At least one requirement is covered by tasks from different clusters."""


class VerificationStatus(str, Enum):
    """Per-evidence-item verification status.

    Verification is a structural check, not a quality judgment.
    "Can't verify" is uncertainty. "Failed verification" is a fact.
    """

    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    """Verification has not been run on this evidence item."""

    UNVERIFIABLE = "UNVERIFIABLE"
    """Verification attempted but prerequisites missing.

    Examples: no checksum provided, location unreachable, no CI linkage.
    In best-effort mode, this evidence still counts.
    """

    VERIFIED_OK = "VERIFIED_OK"
    """Verification succeeded: checksum matches, file exists, signature valid."""

    VERIFIED_FAILED = "VERIFIED_FAILED"
    """Verification attempted and failed: structural fact.

    Examples: checksum mismatch, confirmed missing file, invalid signature.
    This evidence item is invalidated and does NOT count for coverage.
    """


@dataclass(frozen=True)
class AcceptanceTestResult:
    """One acceptance test result for a requirement.

    Matches the schema in task_result_artifact.schema.json:
    acceptance_test_results[].{test, passed, notes}

    Attributes:
        test: Description of the acceptance test.
        passed: Whether the test passed.
        notes: Optional notes about the result.
    """

    test: str
    passed: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"test": self.test, "passed": self.passed}
        if self.notes:
            d["notes"] = self.notes
        return d


@dataclass(frozen=True)
class RequirementEvidence:
    """Evidence that a task addressed a specific requirement.

    This is NOT a quality judgment. It is a structural check:
    "did the task provide any verifiable pointer to work done?"

    Evidence can be:
    - artifact_refs: pointers to deliverable artifacts (file paths, URLs, checksums)
    - acceptance_results: structured test results (test description + pass/fail)

    At least one of these must be non-empty for evidence to count.
    Evidence with verification_status=VERIFIED_FAILED is invalidated
    and does NOT count for coverage purposes.

    Attributes:
        req_id: The requirement this evidence supports.
        task_ref: The task that provided this evidence.
        artifact_refs: Pointers to deliverable artifacts.
        acceptance_results: Structured acceptance test results.
        verification_status: Result of integrity verification.
    """

    req_id: str
    task_ref: str
    artifact_refs: tuple[str, ...] = ()
    acceptance_results: tuple[AcceptanceTestResult, ...] = ()
    verification_status: VerificationStatus = VerificationStatus.NOT_ATTEMPTED

    @property
    def has_evidence(self) -> bool:
        """True if evidence exists AND has not been invalidated by verification.

        VERIFIED_FAILED nullifies this evidence item entirely.
        All other statuses (NOT_ATTEMPTED, UNVERIFIABLE, VERIFIED_OK)
        allow evidence to count in best-effort mode.
        """
        if self.verification_status == VerificationStatus.VERIFIED_FAILED:
            return False
        return bool(self.artifact_refs) or bool(self.acceptance_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "task_ref": self.task_ref,
            "artifact_refs": list(self.artifact_refs),
            "acceptance_results": [r.to_dict() for r in self.acceptance_results],
            "verification_status": self.verification_status.value,
            "has_evidence": self.has_evidence,
        }


@dataclass(frozen=True)
class RequirementCoverage:
    """Tracks which tasks cover a single requirement ID.

    Attributes:
        req_id: The FR/NFR requirement identifier.
        task_refs: Task references that claim to cover this requirement.
        cluster_ids: Clusters that produced results for this requirement.
        evidence: Evidence items from each covering task.
        is_multi_cluster: True if >1 distinct cluster covers this requirement.
        has_evidence: True if at least one task provided evidence.
    """

    req_id: str
    task_refs: tuple[str, ...] = ()
    cluster_ids: tuple[str, ...] = ()
    evidence: tuple[RequirementEvidence, ...] = ()

    @property
    def is_multi_cluster(self) -> bool:
        """Flag when multiple clusters report on the same requirement."""
        return len(set(self.cluster_ids)) > 1

    @property
    def has_evidence(self) -> bool:
        """True if at least one covering task provided evidence."""
        return any(e.has_evidence for e in self.evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "task_refs": list(self.task_refs),
            "cluster_ids": list(self.cluster_ids),
            "evidence": [e.to_dict() for e in self.evidence],
            "is_multi_cluster": self.is_multi_cluster,
            "has_evidence": self.has_evidence,
        }


@dataclass(frozen=True)
class RequirementConflict:
    """A requirement covered by results from different clusters.

    This is NOT a judgment that one result is "wrong." It is a structural
    fact: two independent sources produced results for the same requirement,
    and the system cannot mechanically determine which is authoritative.

    Resolution requires Duke review or Conclave escalation — never silent
    selection by the aggregation service.

    Attributes:
        req_id: The disputed requirement identifier.
        task_refs: Tasks involved in the conflict.
        cluster_ids: Clusters involved in the conflict.
        reason: Mechanical description of why this is flagged.
    """

    req_id: str
    task_refs: tuple[str, ...] = ()
    cluster_ids: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "task_refs": list(self.task_refs),
            "cluster_ids": list(self.cluster_ids),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AggregationResult:
    """The mechanical outcome of aggregating multi-task results.

    This artifact is Duke-readable. It tells the truth about what
    the system found — coverage, gaps, conflicts — without interpretation.

    The disposition is determined by:
    - COMPLETE: all requirements covered, no conflicts → AGGREGATED → COMPLETED
    - INCOMPLETE: coverage gaps exist → escalate with gap list
    - CONFLICTED: multi-cluster conflicts → escalate with conflict artifact

    Attributes:
        deliverable_id: The deliverable being aggregated.
        total_requirements: How many requirement IDs were expected.
        covered_count: How many have at least one covering task.
        missing_requirements: Requirement IDs with no covering task.
        conflicts: Structural conflicts detected.
        coverage_map: Full coverage analysis per requirement.
        contributing_tasks: All task refs included in the aggregation.
        contributing_clusters: All cluster IDs that produced results.
        disposition: Mechanical outcome of the coverage analysis.
        created_at: When the aggregation was performed.
    """

    deliverable_id: str
    total_requirements: int
    covered_count: int
    missing_requirements: tuple[str, ...] = ()
    conflicts: tuple[RequirementConflict, ...] = ()
    coverage_map: tuple[RequirementCoverage, ...] = ()
    contributing_tasks: tuple[str, ...] = ()
    contributing_clusters: tuple[str, ...] = ()
    disposition: AggregationDisposition = AggregationDisposition.COMPLETE
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "artifact_type": "aggregation_result",
            "deliverable_id": self.deliverable_id,
            "disposition": self.disposition.value,
            "total_requirements": self.total_requirements,
            "covered_count": self.covered_count,
            "missing_requirements": list(self.missing_requirements),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "coverage_map": [c.to_dict() for c in self.coverage_map],
            "contributing_tasks": list(self.contributing_tasks),
            "contributing_clusters": list(self.contributing_clusters),
            "created_at": self.created_at,
        }

    @classmethod
    def create(
        cls,
        deliverable_id: str,
        all_requirement_ids: list[str],
        coverage_map: list[RequirementCoverage],
        conflicts: list[RequirementConflict],
        contributing_tasks: list[str],
        contributing_clusters: list[str],
    ) -> AggregationResult:
        """Factory: compute disposition from coverage and conflicts.

        Disposition rules (precedence order):
        1. If conflicts exist → CONFLICTED (regardless of coverage)
        2. If missing requirements → INCOMPLETE
        3. If all covered but any requirement lacks evidence → UNVERIFIED
        4. All covered with evidence → COMPLETE

        Evidence = at least one of: artifact_refs, acceptance_results.
        COMPLETE is mandatory-evidence: claiming coverage without proof
        produces UNVERIFIED — structurally distinct from INCOMPLETE.
        """
        covered_ids = {c.req_id for c in coverage_map if c.task_refs}
        missing = [r for r in all_requirement_ids if r not in covered_ids]

        # Check evidence: every covered requirement must have evidence
        unverified = [
            c.req_id for c in coverage_map if c.task_refs and not c.has_evidence
        ]

        if conflicts:
            disposition = AggregationDisposition.CONFLICTED
        elif missing:
            disposition = AggregationDisposition.INCOMPLETE
        elif unverified:
            disposition = AggregationDisposition.UNVERIFIED
        else:
            disposition = AggregationDisposition.COMPLETE

        return cls(
            deliverable_id=deliverable_id,
            total_requirements=len(all_requirement_ids),
            covered_count=len(covered_ids),
            missing_requirements=tuple(missing),
            conflicts=tuple(conflicts),
            coverage_map=tuple(coverage_map),
            contributing_tasks=tuple(contributing_tasks),
            contributing_clusters=tuple(contributing_clusters),
            disposition=disposition,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
