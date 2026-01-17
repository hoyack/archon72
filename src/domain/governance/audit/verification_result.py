"""Verification result domain models for independent ledger verification.

Story: consent-gov-9.3: Independent Verification

Domain models for capturing results of independent ledger verification.
These models represent the outcome of verification operations including:
- Hash chain verification
- Merkle proof verification
- Sequence completeness checks
- State replay validation

Constitutional Requirements:
- FR58: Any participant can independently verify ledger integrity
- NFR-AUDIT-06: Ledger export enables deterministic state derivation by replay
- AC1: Independent hash chain verification
- AC2: Independent Merkle proof verification
- AC6: Verification detects tampering
- AC7: Verification detects missing events

Verification Philosophy:
- Verification produces detailed results, not just pass/fail
- Every issue is recorded with specifics (what, where, expected vs actual)
- Results enable external auditors to understand verification status
- Math provides guarantees - no trust required
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class VerificationStatus(Enum):
    """Status of verification operation.

    Attributes:
        VALID: All verification checks passed.
        INVALID: Verification failed - integrity issues detected.
        PARTIAL: Some checks passed, some failed.
    """

    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"


class IssueType(Enum):
    """Type of issue detected during verification.

    Attributes:
        HASH_MISMATCH: Event hash doesn't match computed hash (tampering).
        SEQUENCE_GAP: Missing sequence number (missing events).
        BROKEN_LINK: prev_hash doesn't match previous event's hash.
        MERKLE_MISMATCH: Computed Merkle root doesn't match expected.
        STATE_MISMATCH: State replay produced unexpected result.
    """

    HASH_MISMATCH = "hash_mismatch"
    SEQUENCE_GAP = "sequence_gap"
    BROKEN_LINK = "broken_link"
    MERKLE_MISMATCH = "merkle_mismatch"
    STATE_MISMATCH = "state_mismatch"


@dataclass(frozen=True)
class DetectedIssue:
    """Issue detected during verification.

    Records details about a specific verification failure, enabling
    auditors to understand exactly what went wrong and where.

    Attributes:
        issue_type: Category of the detected issue.
        event_id: ID of the affected event (if applicable).
        sequence_number: Sequence number where issue was detected (if applicable).
        description: Human-readable description of the issue.
        expected: What was expected (hash, sequence, etc.).
        actual: What was actually found.
    """

    issue_type: IssueType
    event_id: Optional[UUID]
    sequence_number: Optional[int]
    description: str
    expected: Optional[str]
    actual: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON export.
        """
        return {
            "issue_type": self.issue_type.value,
            "event_id": str(self.event_id) if self.event_id else None,
            "sequence_number": self.sequence_number,
            "description": self.description,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class VerificationResult:
    """Result of independent ledger verification.

    Contains detailed results of all verification checks performed
    on a ledger export. This enables external auditors to understand
    the integrity status of the ledger.

    All verification checks are run independently without requiring
    any cooperation from the system.

    Attributes:
        verification_id: Unique identifier for this verification run.
        verified_at: When the verification was performed (UTC).
        status: Overall verification status (VALID/INVALID/PARTIAL).
        hash_chain_valid: Whether the hash chain validates correctly.
        merkle_valid: Whether the Merkle root matches (if applicable).
        sequence_complete: Whether there are no sequence gaps.
        state_replay_valid: Whether state can be derived from events.
        issues: List of all detected issues.
        total_events_verified: Number of events that were verified.
    """

    verification_id: UUID
    verified_at: datetime
    status: VerificationStatus
    hash_chain_valid: bool
    merkle_valid: bool
    sequence_complete: bool
    state_replay_valid: bool
    issues: list[DetectedIssue]
    total_events_verified: int

    def __post_init__(self) -> None:
        """Validate verification result fields."""
        if self.total_events_verified < 0:
            raise ValueError(
                f"total_events_verified must be non-negative, got {self.total_events_verified}"
            )

    @property
    def is_valid(self) -> bool:
        """Check if verification indicates a valid ledger.

        Returns True only if status is VALID.
        """
        return self.status == VerificationStatus.VALID

    @property
    def has_issues(self) -> bool:
        """Check if any issues were detected.

        Returns True if there are one or more issues.
        """
        return len(self.issues) > 0

    def issues_by_type(self, issue_type: IssueType) -> list[DetectedIssue]:
        """Get all issues of a specific type.

        Args:
            issue_type: The type of issues to filter for.

        Returns:
            List of issues matching the specified type.
        """
        return [i for i in self.issues if i.issue_type == issue_type]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON export.
        """
        return {
            "verification_id": str(self.verification_id),
            "verified_at": self.verified_at.isoformat(),
            "status": self.status.value,
            "hash_chain_valid": self.hash_chain_valid,
            "merkle_valid": self.merkle_valid,
            "sequence_complete": self.sequence_complete,
            "state_replay_valid": self.state_replay_valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "total_events_verified": self.total_events_verified,
        }


class VerificationFailedError(ValueError):
    """Raised when verification fails.

    This indicates the ledger has integrity issues:
    - Hash mismatch (tampering detected)
    - Sequence gap (missing events)
    - Merkle root mismatch (tree altered)
    - State replay failure

    Attributes:
        result: The VerificationResult containing failure details (optional).
    """

    def __init__(
        self,
        message: str,
        result: Optional[VerificationResult] = None,
    ) -> None:
        super().__init__(message)
        self.result = result
