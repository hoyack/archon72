"""Waiver documentation event payloads (Story 9.8, SC-4, SR-10).

This module defines event payloads for constitutional waiver documentation:
- WaiverDocumentedEventPayload: When a CT waiver is documented
- WaiverStatus: Status of a waiver (active, implemented, cancelled)

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- CT-12: Witnessing creates accountability -> All waiver events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating waiver events
2. WITNESS EVERYTHING - All waiver events must be witnessed
3. FAIL LOUD - Never silently swallow waiver operations
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# Event type constant for waiver documentation
WAIVER_DOCUMENTED_EVENT_TYPE: str = "waiver.documented"

# System agent ID for waiver documentation events
WAIVER_SYSTEM_AGENT_ID: str = "system:waiver-documentation"


class WaiverStatus(Enum):
    """Status of a constitutional waiver (SC-4, SR-10).

    Each status represents the lifecycle state of a waiver.
    """

    ACTIVE = "ACTIVE"
    """Waiver is currently in effect."""

    IMPLEMENTED = "IMPLEMENTED"
    """Waived requirement has been implemented."""

    CANCELLED = "CANCELLED"
    """Waiver was cancelled (requirement no longer needed)."""


@dataclass(frozen=True, eq=True)
class WaiverDocumentedEventPayload:
    """Payload for constitutional waiver documentation events (SC-4, SR-10).

    A WaiverDocumentedEventPayload is created when a constitutional waiver
    is documented. This event MUST be witnessed (CT-12) and is immutable
    after creation.

    Constitutional Constraints:
    - SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
    - SR-10: CT-15 waiver documentation -> Must be explicit
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        waiver_id: Unique identifier for this waiver (e.g., "CT-15-MVP-WAIVER").
        constitutional_truth_id: The CT being waived (e.g., "CT-15").
        constitutional_truth_statement: Full text of the CT being waived.
        what_is_waived: Description of what specific requirement is waived.
        rationale: Detailed reason for the waiver.
        target_phase: When the waived requirement will be addressed.
        status: Current status of the waiver.
        documented_at: When the waiver was created (UTC).
        documented_by: Agent/system that documented the waiver.
    """

    waiver_id: str
    constitutional_truth_id: str
    constitutional_truth_statement: str
    what_is_waived: str
    rationale: str
    target_phase: str
    status: WaiverStatus
    documented_at: datetime
    documented_by: str

    def __post_init__(self) -> None:
        """Validate waiver payload fields."""
        if not self.waiver_id:
            raise ValueError("waiver_id is required")
        if not self.constitutional_truth_id:
            raise ValueError("constitutional_truth_id is required")
        if not self.constitutional_truth_statement:
            raise ValueError("constitutional_truth_statement is required")
        if not self.what_is_waived:
            raise ValueError("what_is_waived is required")
        if not self.rationale:
            raise ValueError("rationale is required")
        if not self.target_phase:
            raise ValueError("target_phase is required")
        if not self.documented_by:
            raise ValueError("documented_by is required")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary representation of the waiver payload.
        """
        return {
            "waiver_id": self.waiver_id,
            "constitutional_truth_id": self.constitutional_truth_id,
            "constitutional_truth_statement": self.constitutional_truth_statement,
            "what_is_waived": self.what_is_waived,
            "rationale": self.rationale,
            "target_phase": self.target_phase,
            "status": self.status.value,
            "documented_at": self.documented_at.isoformat(),
            "documented_by": self.documented_by,
        }

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "waiver_id": self.waiver_id,
            "constitutional_truth_id": self.constitutional_truth_id,
            "constitutional_truth_statement": self.constitutional_truth_statement,
            "what_is_waived": self.what_is_waived,
            "rationale": self.rationale,
            "target_phase": self.target_phase,
            "status": self.status.value,
            "documented_at": self.documented_at.isoformat(),
            "documented_by": self.documented_by,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")
