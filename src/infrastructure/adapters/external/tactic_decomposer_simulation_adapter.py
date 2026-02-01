"""Simulation adapter for tactic decomposition.

Produces deterministic TaskDraft dictionaries without any LLM calls.
Each tactic generates exactly 2 tasks with fixed capability tags,
effort estimates, and expected outcomes.

Used for end-to-end pipeline testing and as the fallback in 'auto' mode
when no LLM is available.
"""

from __future__ import annotations

from src.application.ports.tactic_decomposition import (
    DecompositionContext,
    TacticDecomposerProtocol,
)

# Default capability tags for simulation
_DEFAULT_CAPABILITY_TAGS = ["dev_backend", "qa_testing"]


class TacticDecomposerSimulationAdapter(TacticDecomposerProtocol):
    """Deterministic tactic decomposer for testing."""

    async def decompose_tactic(
        self,
        context: DecompositionContext,
    ) -> list[dict[str, str | list[str] | float]]:
        """Produce 2 deterministic task drafts per tactic."""
        tactic = context.tactic
        abbrev = tactic.tactic_id.split("-")[1] if "-" in tactic.tactic_id else "XXXX"
        base_num = _extract_tactic_number(tactic.tactic_id)

        deliverable_id = tactic.deliverable_id or ""
        fr_refs = context.related_fr_ids[:2] if context.related_fr_ids else []

        requirement_lines: list[str] = []
        if fr_refs:
            requirement_lines.extend(
                f"Addresses {fr_id}" for fr_id in fr_refs
            )
        if deliverable_id:
            requirement_lines.append(f"Contributes to deliverable {deliverable_id}")
        if not requirement_lines:
            requirement_lines.append(
                f"Implements tactic {tactic.tactic_id}: {tactic.title}"
            )

        task_a_ref = f"TASK-{abbrev}-{base_num:03d}a"
        task_b_ref = f"TASK-{abbrev}-{base_num:03d}b"

        return [
            {
                "task_ref": task_a_ref,
                "parent_tactic_id": tactic.tactic_id,
                "rfp_id": context.rfp_id,
                "mandate_id": context.mandate_id,
                "proposal_id": context.proposal_id,
                "deliverable_id": deliverable_id,
                "description": (
                    f"Design and document approach for: {tactic.title}. "
                    f"Produce specification and test plan."
                ),
                "requirements": list(requirement_lines),
                "expected_outcomes": [
                    f"Written specification for {tactic.title} reviewed and accepted",
                    "Test plan with at least 3 acceptance criteria defined",
                ],
                "capability_tags": list(_DEFAULT_CAPABILITY_TAGS),
                "effort_hours": 8.0,
                "dependencies": [],
            },
            {
                "task_ref": task_b_ref,
                "parent_tactic_id": tactic.tactic_id,
                "rfp_id": context.rfp_id,
                "mandate_id": context.mandate_id,
                "proposal_id": context.proposal_id,
                "deliverable_id": deliverable_id,
                "description": (
                    f"Implement and verify: {tactic.title}. "
                    f"Produce working implementation with passing tests."
                ),
                "requirements": list(requirement_lines),
                "expected_outcomes": [
                    f"Implementation of {tactic.title} passes all acceptance tests",
                    "Code reviewed and merged to target branch",
                ],
                "capability_tags": list(_DEFAULT_CAPABILITY_TAGS),
                "effort_hours": 16.0,
                "dependencies": [task_a_ref],
            },
        ]


def _extract_tactic_number(tactic_id: str) -> int:
    """Extract the numeric suffix from a tactic ID like T-AGAR-003."""
    parts = tactic_id.rsplit("-", 1)
    if len(parts) == 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 1
