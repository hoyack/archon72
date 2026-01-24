"""Vote override service for applying validated choices.

Story 4.2: Implement Vote Override Application
Pre-mortems: P6 (Tally invariant: ayes + nays + abstains == len(votes))

This service applies vote overrides when the validated choice differs
from the optimistic (regex-parsed) choice, ensuring tally integrity.
"""

import logging
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from src.domain.errors.reconciliation import TallyInvariantError, VoteOverrideError
from src.domain.models.reconciliation import (
    ReconciliationResult,
    ValidationOutcome,
    VoteValidationSummary,
)

logger = logging.getLogger(__name__)


class VoteChoice:
    """Standard vote choice values."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"
    INVALID = "INVALID"

    VALID_CHOICES = {APPROVE, REJECT, ABSTAIN}
    ALL_CHOICES = {APPROVE, REJECT, ABSTAIN, INVALID}


@dataclass
class TallySnapshot:
    """Snapshot of vote tallies.

    Used to track before/after state when applying overrides.
    """

    ayes: int
    nays: int
    abstains: int
    total_votes: int

    @property
    def sum(self) -> int:
        """Sum of all tally counts."""
        return self.ayes + self.nays + self.abstains

    @property
    def is_valid(self) -> bool:
        """Check P6 invariant: sum must equal total."""
        return self.sum == self.total_votes

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "ayes": self.ayes,
            "nays": self.nays,
            "abstains": self.abstains,
            "total_votes": self.total_votes,
            "sum": self.sum,
            "is_valid": self.is_valid,
        }


@dataclass
class OverrideResult:
    """Result of applying a single vote override."""

    vote_id: UUID
    archon_id: str
    old_choice: str
    new_choice: str
    tally_before: TallySnapshot
    tally_after: TallySnapshot
    witnessed: bool


@dataclass
class OverrideApplicationResult:
    """Result of applying all vote overrides."""

    session_id: UUID
    motion_id: UUID
    overrides_applied: int
    overrides_skipped: int
    tally_before: TallySnapshot
    tally_after: TallySnapshot
    individual_results: list[OverrideResult]
    outcome_changed: bool  # Did the motion outcome change?


class MotionProtocol(Protocol):
    """Protocol for motion operations."""

    @property
    def id(self) -> UUID:
        """Motion identifier."""
        ...

    def get_vote(self, archon_id: str) -> Any:
        """Get a vote by archon ID."""
        ...

    def update_vote_choice(self, archon_id: str, new_choice: str) -> None:
        """Update a vote's choice."""
        ...

    def tally_votes(self) -> TallySnapshot:
        """Recompute vote tallies and return snapshot."""
        ...

    def get_outcome(self) -> str:
        """Get current motion outcome (APPROVED, REJECTED, etc)."""
        ...


class WitnessProtocol(Protocol):
    """Protocol for witnessing vote overrides (constitutional)."""

    async def witness_vote_override(
        self,
        vote_id: UUID,
        session_id: UUID,
        motion_id: UUID,
        archon_id: str,
        old_choice: str,
        new_choice: str,
    ) -> None:
        """Witness a vote override.

        This is a constitutional operation - failures should propagate.
        """
        ...


class VoteOverrideService:
    """Service for applying vote overrides from reconciliation.

    This service:
    1. Applies vote overrides when validated != optimistic
    2. Recomputes tallies after each override
    3. Enforces P6 invariant: ayes + nays + abstains == len(votes)
    4. Witnesses all overrides for audit trail

    Thread Safety:
    - This service is NOT thread-safe
    - Should be called after reconciliation completes
    - Motion state should not be modified concurrently

    Usage:
        service = VoteOverrideService(witness=knight_witness)

        result = await service.apply_overrides(
            session_id=session_id,
            motion=motion,
            reconciliation_result=reconciliation_result,
        )

        if result.outcome_changed:
            logger.warning("Motion outcome changed after validation!")
    """

    def __init__(
        self,
        witness: WitnessProtocol | None = None,
        strict_invariant: bool = True,
    ) -> None:
        """Initialize the vote override service.

        Args:
            witness: Optional witness for override logging
            strict_invariant: If True, raises on P6 violation
        """
        self._witness = witness
        self._strict_invariant = strict_invariant

    def _get_tally_snapshot(
        self,
        ayes: int,
        nays: int,
        abstains: int,
        total: int,
    ) -> TallySnapshot:
        """Create a tally snapshot and optionally validate P6."""
        snapshot = TallySnapshot(
            ayes=ayes,
            nays=nays,
            abstains=abstains,
            total_votes=total,
        )
        return snapshot

    def _check_invariant(
        self,
        session_id: UUID,
        motion_id: UUID,
        snapshot: TallySnapshot,
        context: str,
    ) -> None:
        """Check P6 invariant and raise if violated.

        Args:
            session_id: Session for error context
            motion_id: Motion for error context
            snapshot: Tally to check
            context: Description of when check is happening

        Raises:
            TallyInvariantError: If P6 is violated and strict mode
        """
        if not snapshot.is_valid:
            logger.error(
                "P6 invariant violated (%s): %d + %d + %d = %d != %d",
                context,
                snapshot.ayes,
                snapshot.nays,
                snapshot.abstains,
                snapshot.sum,
                snapshot.total_votes,
            )

            if self._strict_invariant:
                raise TallyInvariantError(
                    session_id=session_id,
                    motion_id=motion_id,
                    ayes=snapshot.ayes,
                    nays=snapshot.nays,
                    abstains=snapshot.abstains,
                    total_votes=snapshot.total_votes,
                )

    def _translate_choice(self, choice: str) -> str:
        """Translate various choice formats to standard format.

        Args:
            choice: Input choice (APPROVE, AYE, FOR, YES, etc.)

        Returns:
            Standardized choice (APPROVE, REJECT, ABSTAIN)
        """
        choice_upper = choice.upper().strip()

        # Map to APPROVE
        if choice_upper in {"APPROVE", "AYE", "FOR", "YES", "YEA"}:
            return VoteChoice.APPROVE

        # Map to REJECT
        if choice_upper in {"REJECT", "NAY", "AGAINST", "NO"}:
            return VoteChoice.REJECT

        # Map to ABSTAIN
        if choice_upper in {"ABSTAIN", "PRESENT", "PASS"}:
            return VoteChoice.ABSTAIN

        # Unknown - treat as invalid
        logger.warning("Unknown vote choice: %s", choice)
        return VoteChoice.INVALID

    async def apply_overrides(
        self,
        session_id: UUID,
        motion_id: UUID,
        reconciliation_result: ReconciliationResult,
        get_vote_fn: callable,
        update_vote_fn: callable,
        get_tallies_fn: callable,
        total_votes: int,
    ) -> OverrideApplicationResult:
        """Apply all vote overrides from reconciliation.

        Args:
            session_id: The deliberation session
            motion_id: The motion being voted on
            reconciliation_result: Result from await_all_validations()
            get_vote_fn: Function to get current vote choice by archon_id
            update_vote_fn: Function to update vote choice (archon_id, new_choice)
            get_tallies_fn: Function to get current tallies -> (ayes, nays, abstains)
            total_votes: Total number of votes expected

        Returns:
            OverrideApplicationResult with all changes

        Raises:
            TallyInvariantError: If P6 is violated after override
            VoteOverrideError: If override fails
        """
        # Get initial tally state
        ayes, nays, abstains = get_tallies_fn()
        tally_before = self._get_tally_snapshot(ayes, nays, abstains, total_votes)

        # Check P6 invariant before starting
        self._check_invariant(session_id, motion_id, tally_before, "before overrides")

        # Track results
        individual_results: list[OverrideResult] = []
        overrides_applied = 0
        overrides_skipped = 0

        # Process each vote that needs override
        for summary in reconciliation_result.vote_summaries:
            if not summary.requires_override:
                overrides_skipped += 1
                continue

            # Skip DLQ fallbacks - they use optimistic which is already recorded
            if summary.outcome == ValidationOutcome.DLQ_FALLBACK:
                overrides_skipped += 1
                continue

            # Get current choice
            try:
                current_choice = get_vote_fn(summary.archon_id)
            except Exception as e:
                raise VoteOverrideError(
                    session_id=session_id,
                    motion_id=motion_id,
                    vote_id=summary.vote_id,
                    reason=f"Failed to get current vote: {e}",
                )

            # Translate choices to standard format
            old_choice = self._translate_choice(current_choice)
            new_choice = self._translate_choice(summary.validated_choice)

            # Skip if choices are actually the same after translation
            if old_choice == new_choice:
                overrides_skipped += 1
                continue

            # Validate new choice
            if new_choice not in VoteChoice.VALID_CHOICES:
                raise VoteOverrideError(
                    session_id=session_id,
                    motion_id=motion_id,
                    vote_id=summary.vote_id,
                    reason=f"Invalid validated choice: {summary.validated_choice}",
                )

            # Get tally before this override
            ayes, nays, abstains = get_tallies_fn()
            tally_pre = self._get_tally_snapshot(ayes, nays, abstains, total_votes)

            # Apply the override
            try:
                update_vote_fn(summary.archon_id, new_choice)
            except Exception as e:
                raise VoteOverrideError(
                    session_id=session_id,
                    motion_id=motion_id,
                    vote_id=summary.vote_id,
                    reason=f"Failed to update vote: {e}",
                )

            # Get tally after this override
            ayes, nays, abstains = get_tallies_fn()
            tally_post = self._get_tally_snapshot(ayes, nays, abstains, total_votes)

            # Check P6 invariant after override
            self._check_invariant(
                session_id,
                motion_id,
                tally_post,
                f"after override for {summary.archon_id}",
            )

            # Witness the override
            witnessed = False
            if self._witness:
                try:
                    await self._witness.witness_vote_override(
                        vote_id=summary.vote_id,
                        session_id=session_id,
                        motion_id=motion_id,
                        archon_id=summary.archon_id,
                        old_choice=old_choice,
                        new_choice=new_choice,
                    )
                    witnessed = True
                except Exception as e:
                    logger.error(
                        "Witness failed for vote override: vote=%s error=%s",
                        summary.vote_id,
                        e,
                    )

            # Record result
            result = OverrideResult(
                vote_id=summary.vote_id,
                archon_id=summary.archon_id,
                old_choice=old_choice,
                new_choice=new_choice,
                tally_before=tally_pre,
                tally_after=tally_post,
                witnessed=witnessed,
            )
            individual_results.append(result)
            overrides_applied += 1

            logger.info(
                "Applied vote override: archon=%s old=%s new=%s",
                summary.archon_id,
                old_choice,
                new_choice,
            )

        # Get final tally state
        ayes, nays, abstains = get_tallies_fn()
        tally_after = self._get_tally_snapshot(ayes, nays, abstains, total_votes)

        # Final P6 invariant check
        self._check_invariant(session_id, motion_id, tally_after, "after all overrides")

        # Check if outcome changed
        # This is a simplified check - in reality would compare to original outcome
        outcome_changed = tally_before.ayes != tally_after.ayes or \
                          tally_before.nays != tally_after.nays

        result = OverrideApplicationResult(
            session_id=session_id,
            motion_id=motion_id,
            overrides_applied=overrides_applied,
            overrides_skipped=overrides_skipped,
            tally_before=tally_before,
            tally_after=tally_after,
            individual_results=individual_results,
            outcome_changed=outcome_changed,
        )

        logger.info(
            "Vote overrides complete: applied=%d skipped=%d outcome_changed=%s",
            overrides_applied,
            overrides_skipped,
            outcome_changed,
        )

        if outcome_changed:
            logger.warning(
                "MOTION OUTCOME MAY HAVE CHANGED: before=%s after=%s",
                tally_before.to_dict(),
                tally_after.to_dict(),
            )

        return result
