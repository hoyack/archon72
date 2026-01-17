"""FilterResult value object for complete filter outcomes.

Contains the decision, content (if applicable), and all metadata
about how the filter processed the content.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.governance.filter.filter_decision import FilterDecision
from src.domain.governance.filter.filter_version import FilterVersion
from src.domain.governance.filter.filtered_content import FilteredContent
from src.domain.governance.filter.rejection_reason import RejectionReason
from src.domain.governance.filter.transformation import Transformation
from src.domain.governance.filter.violation_type import ViolationType


@dataclass(frozen=True)
class FilterResult:
    """Complete result of content filtering.

    This captures everything about how the filter processed content:
    - The decision (ACCEPTED, REJECTED, BLOCKED)
    - The filtered content (for ACCEPTED only)
    - Transformations applied (for ACCEPTED)
    - Rejection reason and guidance (for REJECTED)
    - Violation type and details (for BLOCKED)
    """

    decision: FilterDecision
    version: FilterVersion
    timestamp: datetime

    # For ACCEPTED - the filtered content and any transformations
    content: FilteredContent | None = None
    transformations: tuple[Transformation, ...] = field(default_factory=tuple)

    # For REJECTED - reason and guidance for rewrite
    rejection_reason: RejectionReason | None = None
    rejection_guidance: str | None = None

    # For BLOCKED - violation details
    violation_type: ViolationType | None = None
    violation_details: str | None = None

    def __post_init__(self) -> None:
        """Validate result consistency based on decision."""
        self._validate_accepted()
        self._validate_rejected()
        self._validate_blocked()

    def _validate_accepted(self) -> None:
        """Validate ACCEPTED decision constraints."""
        if self.decision != FilterDecision.ACCEPTED:
            return
        if self.content is None:
            raise ValueError("ACCEPTED result must include content")
        if self.rejection_reason is not None:
            raise ValueError("ACCEPTED result cannot have rejection_reason")
        if self.violation_type is not None:
            raise ValueError("ACCEPTED result cannot have violation_type")

    def _validate_rejected(self) -> None:
        """Validate REJECTED decision constraints."""
        if self.decision != FilterDecision.REJECTED:
            return
        if self.content is not None:
            raise ValueError("REJECTED result cannot include content")
        if self.rejection_reason is None:
            raise ValueError("REJECTED result must include rejection_reason")
        if self.violation_type is not None:
            raise ValueError("REJECTED result cannot have violation_type")

    def _validate_blocked(self) -> None:
        """Validate BLOCKED decision constraints."""
        if self.decision != FilterDecision.BLOCKED:
            return
        if self.content is not None:
            raise ValueError("BLOCKED result cannot include content")
        if self.violation_type is None:
            raise ValueError("BLOCKED result must include violation_type")
        if self.rejection_reason is not None:
            raise ValueError("BLOCKED result cannot have rejection_reason")

    def is_sendable(self) -> bool:
        """Returns True if content can be sent to participant.

        Only ACCEPTED results with content are sendable.
        """
        return self.decision == FilterDecision.ACCEPTED and self.content is not None

    @property
    def transformation_count(self) -> int:
        """Number of transformations applied to the content."""
        return len(self.transformations)

    @property
    def was_transformed(self) -> bool:
        """Whether any transformations were applied."""
        return len(self.transformations) > 0

    @classmethod
    def accepted(
        cls,
        content: FilteredContent,
        version: FilterVersion,
        timestamp: datetime,
        transformations: tuple[Transformation, ...] = (),
    ) -> "FilterResult":
        """Factory for ACCEPTED results."""
        return cls(
            decision=FilterDecision.ACCEPTED,
            version=version,
            timestamp=timestamp,
            content=content,
            transformations=transformations,
        )

    @classmethod
    def rejected(
        cls,
        reason: RejectionReason,
        version: FilterVersion,
        timestamp: datetime,
        guidance: str | None = None,
    ) -> "FilterResult":
        """Factory for REJECTED results."""
        return cls(
            decision=FilterDecision.REJECTED,
            version=version,
            timestamp=timestamp,
            rejection_reason=reason,
            rejection_guidance=guidance or reason.guidance,
        )

    @classmethod
    def blocked(
        cls,
        violation: ViolationType,
        version: FilterVersion,
        timestamp: datetime,
        details: str | None = None,
    ) -> "FilterResult":
        """Factory for BLOCKED results."""
        return cls(
            decision=FilterDecision.BLOCKED,
            version=version,
            timestamp=timestamp,
            violation_type=violation,
            violation_details=details,
        )
