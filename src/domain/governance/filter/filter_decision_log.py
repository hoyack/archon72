"""FilterDecisionLog domain model for audit logging.

Story: consent-gov-3.3: Filter Decision Logging

This module defines the immutable log entry for filter decisions.
Each decision (accepted, rejected, blocked) is logged with full
metadata for audit and compliance.

Key Design Decisions:
- Content Privacy: Store HASHES, not raw content
- Immutability: All log entries are frozen dataclasses
- Audit Trail: All transformations recorded with rule IDs

References:
- FR19: Earl can view filter outcome before content is sent
- FR20: System can log all filter decisions with version and timestamp
- NFR-AUDIT-02: Complete audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.domain.governance.filter.filter_decision import FilterDecision
from src.domain.governance.filter.filter_version import FilterVersion
from src.domain.governance.filter.message_type import MessageType
from src.domain.governance.filter.rejection_reason import RejectionReason
from src.domain.governance.filter.violation_type import ViolationType


@dataclass(frozen=True)
class TransformationLog:
    """Immutable log entry for a single transformation.

    Records what was changed during content filtering,
    using hashes for privacy.

    Attributes:
        rule_id: Which rule was applied.
        pattern: The pattern that matched.
        original_hash: BLAKE3 hash of the original text.
        replacement_hash: BLAKE3 hash of the replacement text.
    """

    rule_id: str
    pattern: str
    original_hash: str
    replacement_hash: str

    def __post_init__(self) -> None:
        """Validate transformation log fields."""
        if not self.rule_id:
            raise ValueError("rule_id is required for audit trail")
        if not self.original_hash:
            raise ValueError("original_hash is required")
        if not self.replacement_hash:
            raise ValueError("replacement_hash is required")


@dataclass(frozen=True)
class FilterDecisionLog:
    """Immutable log entry for filter decision.

    Captures everything about a filter decision for audit:
    - Decision outcome (accepted, rejected, blocked)
    - Content hashes (privacy - no raw content stored)
    - Filter version (which rules were used)
    - Decision-specific details

    Content Privacy:
    Logs store HASHES of content, not raw content.
    - Sensitive information may be in task content
    - Hash proves what was filtered without exposing content
    - If needed, original can be retrieved from task record

    Attributes:
        decision_id: Unique identifier for this log entry.
        decision: The filter outcome (ACCEPTED, REJECTED, BLOCKED).
        input_hash: BLAKE3 hash of input content (privacy).
        output_hash: BLAKE3 hash of output (None if rejected/blocked).
        filter_version: Which filter rules processed this content.
        message_type: Type of message that was filtered.
        earl_id: Earl who submitted the content.
        timestamp: When the decision was made.
        transformations: Transformations applied (for ACCEPTED).
        rejection_reason: Why content was rejected (for REJECTED).
        rejection_guidance: Guidance for rewrite (for REJECTED).
        violation_type: Type of violation (for BLOCKED).
        violation_details: Details of violation (for BLOCKED).
    """

    decision_id: UUID
    decision: FilterDecision
    input_hash: str
    output_hash: str | None
    filter_version: FilterVersion
    message_type: MessageType
    earl_id: UUID
    timestamp: datetime

    # Decision-specific details
    transformations: tuple[TransformationLog, ...] = field(default_factory=tuple)
    rejection_reason: RejectionReason | None = None
    rejection_guidance: str | None = None
    violation_type: ViolationType | None = None
    violation_details: str | None = None

    def __post_init__(self) -> None:
        """Validate log entry consistency based on decision."""
        self._validate_input_hash()
        self._validate_accepted()
        self._validate_rejected()
        self._validate_blocked()

    def _validate_input_hash(self) -> None:
        """Validate input hash is present and properly formatted."""
        if not self.input_hash:
            raise ValueError("input_hash is required")
        if not self.input_hash.startswith(("blake3:", "sha256:")):
            raise ValueError(
                f"input_hash must be prefixed with algorithm, got: {self.input_hash}"
            )

    def _validate_accepted(self) -> None:
        """Validate ACCEPTED decision constraints."""
        if self.decision != FilterDecision.ACCEPTED:
            return
        if self.output_hash is None:
            raise ValueError("ACCEPTED log must include output_hash")
        if not self.output_hash.startswith(("blake3:", "sha256:")):
            raise ValueError(
                f"output_hash must be prefixed with algorithm, got: {self.output_hash}"
            )
        if self.rejection_reason is not None:
            raise ValueError("ACCEPTED log cannot have rejection_reason")
        if self.violation_type is not None:
            raise ValueError("ACCEPTED log cannot have violation_type")

    def _validate_rejected(self) -> None:
        """Validate REJECTED decision constraints."""
        if self.decision != FilterDecision.REJECTED:
            return
        if self.output_hash is not None:
            raise ValueError("REJECTED log cannot include output_hash")
        if self.rejection_reason is None:
            raise ValueError("REJECTED log must include rejection_reason")
        if self.violation_type is not None:
            raise ValueError("REJECTED log cannot have violation_type")
        if len(self.transformations) > 0:
            raise ValueError("REJECTED log cannot have transformations")

    def _validate_blocked(self) -> None:
        """Validate BLOCKED decision constraints."""
        if self.decision != FilterDecision.BLOCKED:
            return
        if self.output_hash is not None:
            raise ValueError("BLOCKED log cannot include output_hash")
        if self.violation_type is None:
            raise ValueError("BLOCKED log must include violation_type")
        if self.rejection_reason is not None:
            raise ValueError("BLOCKED log cannot have rejection_reason")
        if len(self.transformations) > 0:
            raise ValueError("BLOCKED log cannot have transformations")

    @property
    def was_transformed(self) -> bool:
        """Whether any transformations were applied."""
        return len(self.transformations) > 0

    @property
    def transformation_count(self) -> int:
        """Number of transformations applied."""
        return len(self.transformations)

    def to_event_payload(self) -> dict:
        """Convert to event payload format for ledger emission.

        Returns:
            Dict suitable for GovernanceEvent payload.
        """
        payload = {
            "decision_id": str(self.decision_id),
            "decision": self.decision.value,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "filter_version": str(self.filter_version),
            "message_type": self.message_type.value,
            "earl_id": str(self.earl_id),
            "timestamp": self.timestamp.isoformat(),
        }

        # Add decision-specific fields
        if self.decision == FilterDecision.ACCEPTED:
            payload["transformations"] = [
                {
                    "rule_id": t.rule_id,
                    "pattern": t.pattern,
                    "original_hash": t.original_hash,
                    "replacement_hash": t.replacement_hash,
                }
                for t in self.transformations
            ]
        elif self.decision == FilterDecision.REJECTED:
            payload["rejection_reason"] = (
                self.rejection_reason.value if self.rejection_reason else None
            )
            payload["rejection_guidance"] = self.rejection_guidance
        elif self.decision == FilterDecision.BLOCKED:
            payload["violation_type"] = (
                self.violation_type.value if self.violation_type else None
            )
            payload["violation_details"] = self.violation_details

        return payload

    @classmethod
    def for_accepted(
        cls,
        decision_id: UUID,
        input_hash: str,
        output_hash: str,
        filter_version: FilterVersion,
        message_type: MessageType,
        earl_id: UUID,
        timestamp: datetime,
        transformations: tuple[TransformationLog, ...] = (),
    ) -> "FilterDecisionLog":
        """Factory for ACCEPTED decision logs."""
        return cls(
            decision_id=decision_id,
            decision=FilterDecision.ACCEPTED,
            input_hash=input_hash,
            output_hash=output_hash,
            filter_version=filter_version,
            message_type=message_type,
            earl_id=earl_id,
            timestamp=timestamp,
            transformations=transformations,
        )

    @classmethod
    def for_rejected(
        cls,
        decision_id: UUID,
        input_hash: str,
        filter_version: FilterVersion,
        message_type: MessageType,
        earl_id: UUID,
        timestamp: datetime,
        rejection_reason: RejectionReason,
        rejection_guidance: str | None = None,
    ) -> "FilterDecisionLog":
        """Factory for REJECTED decision logs."""
        return cls(
            decision_id=decision_id,
            decision=FilterDecision.REJECTED,
            input_hash=input_hash,
            output_hash=None,
            filter_version=filter_version,
            message_type=message_type,
            earl_id=earl_id,
            timestamp=timestamp,
            rejection_reason=rejection_reason,
            rejection_guidance=rejection_guidance,
        )

    @classmethod
    def for_blocked(
        cls,
        decision_id: UUID,
        input_hash: str,
        filter_version: FilterVersion,
        message_type: MessageType,
        earl_id: UUID,
        timestamp: datetime,
        violation_type: ViolationType,
        violation_details: str | None = None,
    ) -> "FilterDecisionLog":
        """Factory for BLOCKED decision logs."""
        return cls(
            decision_id=decision_id,
            decision=FilterDecision.BLOCKED,
            input_hash=input_hash,
            output_hash=None,
            filter_version=filter_version,
            message_type=message_type,
            earl_id=earl_id,
            timestamp=timestamp,
            violation_type=violation_type,
            violation_details=violation_details,
        )
