"""Domain models for vote reconciliation.

Story 4.1: Implement Reconciliation Service
Pre-mortems: P1 (Consumer lag zero), P2 (Hard gate, not warning)
Red Team: V1 (DLQ fallback tracking), R3 (Lag check in await_all)

These models represent the state and results of the reconciliation
process that ensures all votes are validated before session adjournment.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


class ReconciliationStatus(Enum):
    """Status of the reconciliation process."""

    PENDING = "pending"  # Reconciliation not yet started
    IN_PROGRESS = "in_progress"  # Waiting for validations
    COMPLETE = "complete"  # All validations processed
    TIMEOUT = "timeout"  # Timed out waiting for validations
    FAILED = "failed"  # Reconciliation failed


class ValidationOutcome(Enum):
    """Outcome of a single vote's validation."""

    VALIDATED_MATCH = "validated_match"  # Validated choice matches optimistic
    VALIDATED_OVERRIDE = "validated_override"  # Validated differs, override applied
    DLQ_FALLBACK = "dlq_fallback"  # DLQ, fell back to optimistic (V1)
    SYNC_VALIDATED = "sync_validated"  # Validated synchronously (fallback path)


@dataclass(frozen=True)
class VoteValidationSummary:
    """Summary of a single vote's validation outcome.

    Attributes:
        vote_id: The vote identifier
        archon_id: Archon who cast the vote
        optimistic_choice: Initial regex-parsed choice
        validated_choice: Final validated choice
        outcome: How the vote was resolved
        requires_override: Whether tally needs recalculation
        confidence: Validator confidence (0.0-1.0)
    """

    vote_id: UUID
    archon_id: str
    optimistic_choice: str
    validated_choice: str
    outcome: ValidationOutcome
    requires_override: bool
    confidence: float = 1.0

    @property
    def choice_changed(self) -> bool:
        """Check if the validated choice differs from optimistic."""
        return self.optimistic_choice != self.validated_choice


@dataclass
class ReconciliationResult:
    """Result of the reconciliation process.

    This is returned by await_all_validations() and contains
    summary information about how all votes were resolved.

    Attributes:
        session_id: The deliberation session
        motion_id: The motion being voted on
        status: Final reconciliation status
        validated_count: Votes validated via consensus
        dlq_fallback_count: Votes that fell back to optimistic (V1)
        sync_validated_count: Votes validated synchronously
        override_count: Votes where validated != optimistic
        pending_count: Votes still pending (should be 0 on success)
        consumer_lag: Final consumer lag (should be 0 on success - R3)
        vote_summaries: Per-vote validation outcomes
        started_at_ms: When reconciliation started
        completed_at_ms: When reconciliation completed
        error_message: Error details if failed
    """

    session_id: UUID
    motion_id: UUID
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    validated_count: int = 0
    dlq_fallback_count: int = 0
    sync_validated_count: int = 0
    override_count: int = 0
    pending_count: int = 0
    consumer_lag: int = 0
    vote_summaries: list[VoteValidationSummary] = field(default_factory=list)
    started_at_ms: int = 0
    completed_at_ms: int = 0
    error_message: str | None = None

    @property
    def total_votes(self) -> int:
        """Total number of votes processed."""
        return (
            self.validated_count
            + self.dlq_fallback_count
            + self.sync_validated_count
        )

    @property
    def fully_validated(self) -> bool:
        """Check if all votes were validated via consensus.

        Returns False if any votes used DLQ fallback (V1).
        """
        return self.dlq_fallback_count == 0 and self.status == ReconciliationStatus.COMPLETE

    @property
    def has_overrides(self) -> bool:
        """Check if any votes required override."""
        return self.override_count > 0

    @property
    def is_complete(self) -> bool:
        """Check if reconciliation completed successfully."""
        return (
            self.status == ReconciliationStatus.COMPLETE
            and self.pending_count == 0
            and self.consumer_lag == 0  # R3
        )

    def add_vote_summary(self, summary: VoteValidationSummary) -> None:
        """Add a vote summary to the results.

        Args:
            summary: The vote validation summary
        """
        self.vote_summaries.append(summary)

        # Update counts
        if summary.outcome == ValidationOutcome.VALIDATED_MATCH:
            self.validated_count += 1
        elif summary.outcome == ValidationOutcome.VALIDATED_OVERRIDE:
            self.validated_count += 1
            self.override_count += 1
        elif summary.outcome == ValidationOutcome.DLQ_FALLBACK:
            self.dlq_fallback_count += 1
        elif summary.outcome == ValidationOutcome.SYNC_VALIDATED:
            self.sync_validated_count += 1

        if summary.requires_override:
            self.override_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/monitoring."""
        return {
            "session_id": str(self.session_id),
            "motion_id": str(self.motion_id),
            "status": self.status.value,
            "validated_count": self.validated_count,
            "dlq_fallback_count": self.dlq_fallback_count,
            "sync_validated_count": self.sync_validated_count,
            "override_count": self.override_count,
            "pending_count": self.pending_count,
            "consumer_lag": self.consumer_lag,
            "total_votes": self.total_votes,
            "fully_validated": self.fully_validated,
            "has_overrides": self.has_overrides,
            "is_complete": self.is_complete,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class ReconciliationConfig:
    """Configuration for the reconciliation process.

    Attributes:
        timeout_seconds: Maximum time to wait for validations
        poll_interval_seconds: How often to check status
        max_lag_for_complete: Maximum acceptable consumer lag (usually 0)
        require_zero_pending: Whether pending_count must be 0
    """

    timeout_seconds: float = 300.0  # 5 minutes default
    poll_interval_seconds: float = 1.0
    max_lag_for_complete: int = 0  # R3: Must be zero
    require_zero_pending: bool = True  # P1: Must have zero pending
