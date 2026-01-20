"""Deliberation orchestrator stubs for testing (Story 2A.4, FR-11.4).

This module provides deterministic stub implementations of the orchestrator
protocols for testing. The stubs allow precise control over phase execution
and voting outcomes.

Usage:
    >>> # Create stub with default unanimous vote
    >>> executor = PhaseExecutorStub()
    >>> orchestrator = DeliberationOrchestratorStub(executor)
    >>> result = orchestrator.orchestrate(session, package)
    >>> assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
    >>> assert result.is_unanimous

    >>> # Create stub with custom votes
    >>> executor = PhaseExecutorStub.with_votes({
    ...     archon1: DeliberationOutcome.ACKNOWLEDGE,
    ...     archon2: DeliberationOutcome.ACKNOWLEDGE,
    ...     archon3: DeliberationOutcome.REFER,
    ... })
    >>> result = orchestrator.orchestrate(session, package)
    >>> assert result.dissent_archon_id == archon3
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from src.application.services.deliberation_orchestrator_service import (
    DeliberationOrchestratorService,
)
from src.domain.models.deliberation_result import PhaseResult
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)

if TYPE_CHECKING:
    from src.domain.models.deliberation_context_package import (
        DeliberationContextPackage,
    )


def _compute_transcript_hash(content: str) -> bytes:
    """Compute Blake3-like hash (using SHA-256 for stub simplicity).

    In production, this would use Blake3. For testing, SHA-256 is sufficient.
    """
    return hashlib.sha256(content.encode()).digest()


class PhaseExecutorStub:
    """Stub implementation of PhaseExecutorProtocol for testing (Story 2A.4).

    Provides deterministic phase execution with configurable voting outcomes.
    All transcripts and timestamps are deterministic for reproducible tests.

    Default behavior produces a unanimous ACKNOWLEDGE vote. Use class methods
    to configure custom voting outcomes.

    Attributes:
        _votes: Map of archon_id to their vote (defaults to ACKNOWLEDGE).
        _phase_duration_ms: Duration to add per phase (default 100ms).
        _cross_examine_challenges: Number of challenges in cross-examine.
        _cross_examine_rounds: Number of rounds in cross-examine.
    """

    def __init__(
        self,
        votes: dict[UUID, DeliberationOutcome] | None = None,
        phase_duration_ms: int = 100,
        cross_examine_challenges: int = 2,
        cross_examine_rounds: int = 1,
    ) -> None:
        """Initialize PhaseExecutorStub.

        Args:
            votes: Custom votes for the VOTE phase. If None, defaults to
                unanimous ACKNOWLEDGE when archons are known.
            phase_duration_ms: Duration to add per phase for timestamps.
            cross_examine_challenges: Number of challenges for metadata.
            cross_examine_rounds: Number of rounds for metadata.
        """
        self._votes = votes
        self._phase_duration_ms = phase_duration_ms
        self._cross_examine_challenges = cross_examine_challenges
        self._cross_examine_rounds = cross_examine_rounds

    @classmethod
    def with_votes(cls, votes: dict[UUID, DeliberationOutcome]) -> PhaseExecutorStub:
        """Create stub with custom votes.

        Args:
            votes: Map of archon_id to their vote.

        Returns:
            Configured PhaseExecutorStub.
        """
        return cls(votes=votes)

    @classmethod
    def with_unanimous_vote(cls, outcome: DeliberationOutcome) -> PhaseExecutorStub:
        """Create stub that produces unanimous vote for given outcome.

        The actual votes are set when execute_vote is called, as we need
        the archon IDs from the session.

        Args:
            outcome: The unanimous outcome.

        Returns:
            Configured PhaseExecutorStub.
        """
        # Store outcome, votes will be created in execute_vote
        stub = cls()
        stub._unanimous_outcome = outcome
        return stub

    def _get_votes_for_session(
        self, session: DeliberationSession
    ) -> dict[UUID, DeliberationOutcome]:
        """Get votes for the session's archons.

        If explicit votes were configured, returns those.
        Otherwise, creates unanimous ACKNOWLEDGE votes.
        """
        if self._votes is not None:
            return self._votes

        # Check for unanimous outcome
        if hasattr(self, "_unanimous_outcome"):
            return {
                archon: self._unanimous_outcome for archon in session.assigned_archons
            }

        # Default: unanimous ACKNOWLEDGE
        return {
            archon: DeliberationOutcome.ACKNOWLEDGE
            for archon in session.assigned_archons
        }

    def _make_timestamp(self, offset_ms: int) -> datetime:
        """Create deterministic timestamp with offset."""
        base = datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)
        return base + timedelta(milliseconds=offset_ms)

    def execute_assess(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> PhaseResult:
        """Execute ASSESS phase with deterministic transcript.

        Args:
            session: The deliberation session.
            package: The context package.

        Returns:
            PhaseResult for ASSESS phase.
        """
        transcript_parts = [
            "=== ASSESS PHASE ===",
            f"Petition ID: {package.petition_id}",
            f"Petition Type: {package.petition_type}",
            "",
        ]

        for i, archon_id in enumerate(session.assigned_archons):
            transcript_parts.extend(
                [
                    f"--- Archon {i + 1} ({archon_id}) Assessment ---",
                    f"I have reviewed the petition of type {package.petition_type}.",
                    f"The petition text discusses: {package.petition_text[:50]}...",
                    f"Co-signers: {package.co_signer_count}",
                    "",
                ]
            )

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_transcript_hash(transcript)

        return PhaseResult(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=self._make_timestamp(0),
            completed_at=self._make_timestamp(self._phase_duration_ms),
            phase_metadata={
                "assessments_completed": 3,
                "petition_type": package.petition_type,
            },
        )

    def execute_position(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        assess_result: PhaseResult,
    ) -> PhaseResult:
        """Execute POSITION phase with deterministic transcript.

        Args:
            session: The deliberation session.
            package: The context package.
            assess_result: Result from ASSESS phase.

        Returns:
            PhaseResult for POSITION phase.
        """
        votes = self._get_votes_for_session(session)

        transcript_parts = [
            "=== POSITION PHASE ===",
            "Building on assessments from previous phase.",
            "",
        ]

        for i, archon_id in enumerate(session.assigned_archons):
            position = votes[archon_id]
            transcript_parts.extend(
                [
                    f"--- Archon {i + 1} ({archon_id}) Position ---",
                    f"My preferred disposition: {position.value}",
                    f"Rationale: Based on my assessment, I believe {position.value} is appropriate.",
                    "",
                ]
            )

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_transcript_hash(transcript)

        return PhaseResult(
            phase=DeliberationPhase.POSITION,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=self._make_timestamp(self._phase_duration_ms),
            completed_at=self._make_timestamp(self._phase_duration_ms * 2),
            phase_metadata={
                "positions_stated": 3,
                "positions_converged": len(set(votes.values())) == 1,
            },
        )

    def execute_cross_examine(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        position_result: PhaseResult,
    ) -> PhaseResult:
        """Execute CROSS_EXAMINE phase with deterministic transcript.

        Args:
            session: The deliberation session.
            package: The context package.
            position_result: Result from POSITION phase.

        Returns:
            PhaseResult for CROSS_EXAMINE phase.
        """
        transcript_parts = [
            "=== CROSS_EXAMINE PHASE ===",
            "Examining positions for consensus building.",
            "",
        ]

        for round_num in range(self._cross_examine_rounds):
            transcript_parts.append(f"--- Round {round_num + 1} ---")
            for i, archon_id in enumerate(session.assigned_archons):
                if i < self._cross_examine_challenges:
                    transcript_parts.extend(
                        [
                            f"Archon {i + 1} ({archon_id}): I challenge the reasoning.",
                            "Response: I maintain my position based on constitutional principles.",
                            "",
                        ]
                    )

        transcript_parts.append("No further challenges raised. Proceeding to vote.")

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_transcript_hash(transcript)

        return PhaseResult(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=self._make_timestamp(self._phase_duration_ms * 2),
            completed_at=self._make_timestamp(self._phase_duration_ms * 3),
            phase_metadata={
                "challenges_raised": self._cross_examine_challenges,
                "rounds_completed": self._cross_examine_rounds,
                "consensus_emerging": True,
            },
        )

    def execute_vote(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        cross_examine_result: PhaseResult,
    ) -> PhaseResult:
        """Execute VOTE phase with deterministic transcript.

        Args:
            session: The deliberation session.
            package: The context package.
            cross_examine_result: Result from CROSS_EXAMINE phase.

        Returns:
            PhaseResult for VOTE phase with votes in metadata.
        """
        votes = self._get_votes_for_session(session)

        transcript_parts = [
            "=== VOTE PHASE ===",
            "All Archons casting simultaneous votes.",
            "",
        ]

        for i, archon_id in enumerate(session.assigned_archons):
            vote = votes[archon_id]
            transcript_parts.extend(
                [
                    f"--- Archon {i + 1} ({archon_id}) Vote ---",
                    f"Final vote: {vote.value}",
                    "",
                ]
            )

        # Summary
        vote_counts: dict[DeliberationOutcome, int] = {}
        for vote in votes.values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        transcript_parts.append("=== VOTE SUMMARY ===")
        for outcome, count in vote_counts.items():
            transcript_parts.append(f"{outcome.value}: {count} vote(s)")

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_transcript_hash(transcript)

        return PhaseResult(
            phase=DeliberationPhase.VOTE,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=self._make_timestamp(self._phase_duration_ms * 3),
            completed_at=self._make_timestamp(self._phase_duration_ms * 4),
            phase_metadata={
                "votes": votes,  # Required for orchestrator to extract votes
                "vote_counts": {k.value: v for k, v in vote_counts.items()},
            },
        )


class DeliberationOrchestratorStub(DeliberationOrchestratorService):
    """Stub implementation of DeliberationOrchestratorProtocol for testing.

    This stub extends the real service to use stub executor. It provides
    deterministic behavior for testing while using the actual orchestration
    logic.

    For most tests, use this with PhaseExecutorStub:

        >>> executor = PhaseExecutorStub()
        >>> orchestrator = DeliberationOrchestratorStub(executor)
        >>> result = orchestrator.orchestrate(session, package)

    For custom voting:

        >>> executor = PhaseExecutorStub.with_votes({...})
        >>> orchestrator = DeliberationOrchestratorStub(executor)
    """

    @classmethod
    def with_unanimous_vote(
        cls, outcome: DeliberationOutcome
    ) -> DeliberationOrchestratorStub:
        """Create stub that produces unanimous vote.

        Args:
            outcome: The unanimous outcome.

        Returns:
            Configured orchestrator stub.
        """
        executor = PhaseExecutorStub.with_unanimous_vote(outcome)
        return cls(executor)

    @classmethod
    def with_votes(
        cls, votes: dict[UUID, DeliberationOutcome]
    ) -> DeliberationOrchestratorStub:
        """Create stub with custom votes.

        Args:
            votes: Map of archon_id to their vote.

        Returns:
            Configured orchestrator stub.
        """
        executor = PhaseExecutorStub.with_votes(votes)
        return cls(executor)

    @classmethod
    def default(cls) -> DeliberationOrchestratorStub:
        """Create stub with default behavior (unanimous ACKNOWLEDGE).

        Returns:
            Default orchestrator stub.
        """
        return cls(PhaseExecutorStub())
