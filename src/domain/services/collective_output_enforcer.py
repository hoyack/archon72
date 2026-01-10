"""Collective output enforcer domain service (Story 2.3, FR11).

This module provides domain logic for enforcing collective output
irreducibility. FR11 requires that collective outputs are attributed
to the Conclave, not individual agents.

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability
"""

from __future__ import annotations

from src.domain.errors.collective import FR11ViolationError
from src.domain.events.collective_output import (
    AuthorType,
    CollectiveOutputPayload,
    VoteCounts,
)


def calculate_dissent_percentage(vote_counts: VoteCounts) -> float:
    """Calculate dissent percentage from vote counts.

    Dissent is the percentage of votes that are NOT in the majority.
    Formula: (minority_votes / total_votes) × 100

    Where minority_votes = total - max(yes, no, abstain)

    Args:
        vote_counts: The vote breakdown.

    Returns:
        Dissent percentage as float (0.0-100.0).
        Returns 0.0 for zero total votes (edge case).

    Examples:
        >>> calculate_dissent_percentage(VoteCounts(72, 0, 0))
        0.0
        >>> calculate_dissent_percentage(VoteCounts(36, 36, 0))
        50.0
    """
    total = vote_counts.total
    if total == 0:
        return 0.0

    majority = max(vote_counts.yes_count, vote_counts.no_count, vote_counts.abstain_count)
    minority = total - majority

    return (minority / total) * 100.0


def is_unanimous(vote_counts: VoteCounts) -> bool:
    """Check if the vote is unanimous.

    A vote is unanimous if all votes are for the same option
    (100% yes, 100% no, or 100% abstain).

    Args:
        vote_counts: The vote breakdown.

    Returns:
        True if unanimous, False otherwise.

    Examples:
        >>> is_unanimous(VoteCounts(72, 0, 0))
        True
        >>> is_unanimous(VoteCounts(71, 1, 0))
        False
    """
    total = vote_counts.total
    if total == 0:
        return True  # Edge case: no votes = unanimous by default

    majority = max(vote_counts.yes_count, vote_counts.no_count, vote_counts.abstain_count)
    return majority == total


def validate_collective_output(payload: CollectiveOutputPayload) -> None:
    """Validate a collective output payload for FR11 compliance.

    This provides defense-in-depth validation beyond the dataclass
    __post_init__ checks. It verifies:
    1. author_type is COLLECTIVE
    2. At least 2 contributing agents (FR11 requirement)
    3. dissent_percentage matches calculated value

    Args:
        payload: The collective output payload to validate.

    Raises:
        FR11ViolationError: If any FR11 constraint is violated.

    Note:
        This function is idempotent - calling it multiple times
        on the same payload produces the same result.
    """
    # Defense in depth: re-validate author_type
    if payload.author_type != AuthorType.COLLECTIVE:
        raise FR11ViolationError(
            f"FR11: Collective output requires author_type COLLECTIVE, "
            f"got {payload.author_type.value}"
        )

    # Defense in depth: re-validate contributing agents count
    if len(payload.contributing_agents) < 2:
        raise FR11ViolationError(
            f"FR11: Collective output requires multiple participants "
            f"(got {len(payload.contributing_agents)})"
        )

    # Validate dissent_percentage calculation
    expected_dissent = calculate_dissent_percentage(payload.vote_counts)

    # Allow small floating point tolerance
    if abs(payload.dissent_percentage - expected_dissent) > 0.01:
        raise FR11ViolationError(
            f"FR11: dissent_percentage mismatch - "
            f"expected {expected_dissent:.2f}, got {payload.dissent_percentage:.2f}"
        )

    # Validate unanimous flag matches calculation
    expected_unanimous = is_unanimous(payload.vote_counts)
    if payload.unanimous != expected_unanimous:
        raise FR11ViolationError(
            f"FR11: unanimous flag mismatch - "
            f"expected {expected_unanimous}, got {payload.unanimous}"
        )
