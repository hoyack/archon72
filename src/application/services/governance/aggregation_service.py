"""Aggregation service — multi-task result aggregation without judgment.

Sprint: Aggregation Without Judgment + Evidence-Backed Coverage

This service performs mechanical aggregation of task results that share
a deliverable. It answers four questions:

1. Coverage: Are all rfp_requirement_ids covered by at least one
   REPORTED/COMPLETED task?
2. Evidence: Does each covered requirement have verifiable proof?
3. Conflict: Do multiple clusters report on the same requirement?
4. Disposition: COMPLETE, UNVERIFIED, INCOMPLETE, or CONFLICTED?

Design principles:
- The service NEVER picks between conflicting results
- Conflicts produce a Duke-readable artifact and escalate
- Coverage is measured against rfp_requirement_ids, not semantic judgment
- COMPLETE requires evidence (artifact_refs or acceptance_test_results)
- Claiming coverage without proof produces UNVERIFIED
- Single-cluster deliverables skip aggregation (direct COMPLETED)

Constitutional Constraints:
- Aggregation is procedural, not qualitative
- No "best answer" selection
- Conflicts are escalated, not resolved
- COMPLETE is mandatory-evidence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.application.ports.governance.evidence_verifier_port import EvidenceVerifierPort
from src.domain.models.aggregation import (
    AcceptanceTestResult,
    AggregationResult,
    RequirementConflict,
    RequirementCoverage,
    RequirementEvidence,
    VerificationStatus,
)


@dataclass(frozen=True)
class TaskEntry:
    """Minimal task representation for aggregation.

    Extracted from activation manifest entries. Only the fields
    needed for coverage and evidence analysis.

    Evidence fields are extracted from the task result artifact:
    - artifact_refs: pointers to deliverable artifacts (file paths, URLs)
    - acceptance_results: structured test results (test + passed + notes)
    """

    task_ref: str
    deliverable_id: str
    cluster_id: str
    rfp_requirement_ids: tuple[str, ...]
    status: str
    result_output: dict[str, Any] | None = None
    artifact_refs: tuple[str, ...] = ()
    acceptance_results: tuple[AcceptanceTestResult, ...] = ()


def verify_requirement_evidence(
    evidence: RequirementEvidence,
    verifier: EvidenceVerifierPort,
) -> RequirementEvidence:
    """Verify evidence integrity and return evidence with status set.

    Pure function: takes evidence and verifier, returns new evidence
    with verification_status reflecting the structural check result.

    Verification logic:
    - If no evidence items exist → NOT_ATTEMPTED (nothing to verify)
    - Verify each artifact_ref and acceptance_result via the port
    - Aggregate per-item results into a single evidence-level status:
      - Any VERIFIED_FAILED → VERIFIED_FAILED (one bad item taints all)
      - All VERIFIED_OK → VERIFIED_OK
      - Mix of OK and UNVERIFIABLE → UNVERIFIABLE
      - All UNVERIFIABLE → UNVERIFIABLE

    Args:
        evidence: The evidence item to verify.
        verifier: Port implementation for structural checks.

    Returns:
        New RequirementEvidence with verification_status set.
    """
    if not evidence.artifact_refs and not evidence.acceptance_results:
        return evidence  # NOT_ATTEMPTED: nothing to verify

    statuses: list[VerificationStatus] = []

    # Verify artifact refs
    for ref in evidence.artifact_refs:
        result = verifier.verify_artifact_ref(ref)
        statuses.append(result.status)

    # Verify acceptance test results
    for atr in evidence.acceptance_results:
        result = verifier.verify_acceptance_test(atr.test, atr.passed, atr.notes)
        statuses.append(result.status)

    # Aggregate: FAILED taints everything, then OK > UNVERIFIABLE
    if VerificationStatus.VERIFIED_FAILED in statuses:
        final_status = VerificationStatus.VERIFIED_FAILED
    elif all(s == VerificationStatus.VERIFIED_OK for s in statuses):
        final_status = VerificationStatus.VERIFIED_OK
    else:
        final_status = VerificationStatus.UNVERIFIABLE

    return RequirementEvidence(
        req_id=evidence.req_id,
        task_ref=evidence.task_ref,
        artifact_refs=evidence.artifact_refs,
        acceptance_results=evidence.acceptance_results,
        verification_status=final_status,
    )


def aggregate_deliverable(
    deliverable_id: str,
    all_requirement_ids: list[str],
    tasks: list[TaskEntry],
    verifier: EvidenceVerifierPort | None = None,
) -> AggregationResult:
    """Aggregate results for a single deliverable.

    This is a pure function. No side effects, no state mutations.
    Takes the expected requirements and the contributing tasks,
    returns a mechanical coverage analysis.

    Args:
        deliverable_id: The deliverable being aggregated.
        all_requirement_ids: All FR/NFR IDs expected for this deliverable
            (union of rfp_requirement_ids across all tasks for this deliverable).
        tasks: Task entries that share this deliverable_id and have
            reached REPORTED or COMPLETED status.
        verifier: Optional evidence verifier. If provided, each evidence
            item is verified before disposition is computed.

    Returns:
        AggregationResult with coverage map, conflicts, and disposition.
    """
    # --- Build coverage map with evidence ---
    req_to_tasks: dict[str, list[str]] = {}
    req_to_clusters: dict[str, list[str]] = {}
    req_to_evidence: dict[str, list[RequirementEvidence]] = {}

    for task in tasks:
        for req_id in task.rfp_requirement_ids:
            req_to_tasks.setdefault(req_id, []).append(task.task_ref)
            req_to_clusters.setdefault(req_id, []).append(task.cluster_id)

            # Build evidence for this task × requirement pair
            evidence = RequirementEvidence(
                req_id=req_id,
                task_ref=task.task_ref,
                artifact_refs=task.artifact_refs,
                acceptance_results=task.acceptance_results,
            )

            # Verify if verifier is provided
            if verifier is not None:
                evidence = verify_requirement_evidence(evidence, verifier)

            req_to_evidence.setdefault(req_id, []).append(evidence)

    coverage_map: list[RequirementCoverage] = []
    for req_id in all_requirement_ids:
        refs = req_to_tasks.get(req_id, [])
        clusters = req_to_clusters.get(req_id, [])
        evidence = req_to_evidence.get(req_id, [])
        coverage_map.append(
            RequirementCoverage(
                req_id=req_id,
                task_refs=tuple(refs),
                cluster_ids=tuple(clusters),
                evidence=tuple(evidence),
            )
        )

    # --- Detect conflicts ---
    # A conflict exists when the SAME requirement is covered by tasks
    # from DIFFERENT clusters. This is a structural fact, not a judgment.
    conflicts: list[RequirementConflict] = []
    for cov in coverage_map:
        if cov.is_multi_cluster:
            conflicts.append(
                RequirementConflict(
                    req_id=cov.req_id,
                    task_refs=cov.task_refs,
                    cluster_ids=tuple(sorted(set(cov.cluster_ids))),
                    reason=(
                        f"Requirement {cov.req_id} covered by "
                        f"{len(set(cov.cluster_ids))} different clusters — "
                        "cannot mechanically determine which is authoritative"
                    ),
                )
            )

    # --- Contributing entities ---
    contributing_tasks = [t.task_ref for t in tasks]
    contributing_clusters = sorted({t.cluster_id for t in tasks})

    return AggregationResult.create(
        deliverable_id=deliverable_id,
        all_requirement_ids=all_requirement_ids,
        coverage_map=coverage_map,
        conflicts=conflicts,
        contributing_tasks=contributing_tasks,
        contributing_clusters=contributing_clusters,
    )


def group_tasks_by_deliverable(
    tasks: list[TaskEntry],
) -> dict[str, list[TaskEntry]]:
    """Group tasks by deliverable_id.

    Args:
        tasks: All task entries to group.

    Returns:
        Dict mapping deliverable_id to list of tasks for that deliverable.
    """
    groups: dict[str, list[TaskEntry]] = {}
    for task in tasks:
        groups.setdefault(task.deliverable_id, []).append(task)
    return groups


def collect_requirement_ids(tasks: list[TaskEntry]) -> list[str]:
    """Collect the union of all rfp_requirement_ids across tasks.

    This is the "expected" requirement set for a deliverable — the
    union of what all contributing tasks claim to cover.

    Args:
        tasks: Tasks sharing a deliverable.

    Returns:
        Deduplicated, sorted list of requirement IDs.
    """
    seen: set[str] = set()
    result: list[str] = []
    for task in tasks:
        for req_id in task.rfp_requirement_ids:
            if req_id not in seen:
                seen.add(req_id)
                result.append(req_id)
    return sorted(result)


def needs_aggregation(tasks: list[TaskEntry]) -> bool:
    """Determine if a set of tasks requires aggregation.

    Single-cluster deliverables skip aggregation and go directly
    to COMPLETED. Multi-cluster deliverables require aggregation
    to check for conflicts.

    Args:
        tasks: Tasks sharing a deliverable.

    Returns:
        True if tasks come from more than one cluster.
    """
    clusters = {t.cluster_id for t in tasks}
    return len(clusters) > 1
