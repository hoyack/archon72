"""Integrity Case update event payloads (Story 7.10, FR144).

This module defines event payloads for Integrity Case Artifact updates.
When constitutional amendments affect guarantees, an update event is created.

Constitutional Constraints:
- FR144: Artifact SHALL be updated with each constitutional amendment
- CT-11: Silent failure destroys legitimacy -> Update failures must be logged
- CT-12: Witnessing creates accountability -> All updates must be witnessed

Developer Golden Rules:
1. WITNESS EVERYTHING - All artifact updates must be witnessed
2. ATOMIC WITH AMENDMENT - Update should be in same transaction as amendment
3. VERSION TRACKING - Each update increments version
4. FAIL LOUD - Failed update = logged event with reason

Usage:
    from src.domain.events.integrity_case import (
        IntegrityCaseUpdatedEventPayload,
        INTEGRITY_CASE_UPDATED_EVENT_TYPE,
    )

    # Create an update event
    payload = IntegrityCaseUpdatedEventPayload(
        artifact_version="1.0.1",
        previous_version="1.0.0",
        amendment_event_id="amend-123",
        guarantees_added=["new-guarantee-id"],
        guarantees_modified=["modified-guarantee-id"],
        guarantees_removed=[],
        updated_at=datetime.now(timezone.utc),
        reason="Constitutional amendment XYZ added new guarantee",
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


# Event type constant for integrity case updates
INTEGRITY_CASE_UPDATED_EVENT_TYPE: str = "integrity_case.updated"


@dataclass(frozen=True, eq=True)
class IntegrityCaseUpdatedEventPayload:
    """Payload for Integrity Case Artifact update events (FR144).

    An IntegrityCaseUpdatedEventPayload is created when the artifact is
    updated due to a constitutional amendment. This event is witnessed
    to provide accountability (CT-12).

    Constitutional Constraints:
    - FR144: Updated with each constitutional amendment
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        artifact_version: New version of the artifact after update.
        previous_version: Version before update.
        amendment_event_id: ID of the amendment that triggered this update.
        guarantees_added: IDs of new guarantees added.
        guarantees_modified: IDs of guarantees that were modified.
        guarantees_removed: IDs of guarantees that were removed.
        updated_at: When the update occurred (UTC).
        reason: Human-readable reason for the update.

    Example:
        >>> payload = IntegrityCaseUpdatedEventPayload(
        ...     artifact_version="1.0.1",
        ...     previous_version="1.0.0",
        ...     amendment_event_id="amend-123",
        ...     guarantees_added=("new-guarantee",),
        ...     guarantees_modified=(),
        ...     guarantees_removed=(),
        ...     updated_at=datetime.now(timezone.utc),
        ...     reason="Added new guarantee per amendment XYZ",
        ... )
    """

    artifact_version: str
    previous_version: str
    amendment_event_id: str
    guarantees_added: tuple[str, ...]
    guarantees_modified: tuple[str, ...]
    guarantees_removed: tuple[str, ...]
    updated_at: datetime
    reason: str

    def __post_init__(self) -> None:
        """Validate update event payload."""
        if not self.artifact_version:
            raise ValueError("artifact_version must be non-empty")
        if not self.previous_version:
            raise ValueError("previous_version must be non-empty")
        if not self.amendment_event_id:
            raise ValueError("amendment_event_id must be non-empty")
        if not self.reason:
            raise ValueError("reason must be non-empty")
        # At least one change must have occurred
        if not (
            self.guarantees_added
            or self.guarantees_modified
            or self.guarantees_removed
        ):
            raise ValueError(
                "At least one of guarantees_added, guarantees_modified, "
                "or guarantees_removed must be non-empty"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": INTEGRITY_CASE_UPDATED_EVENT_TYPE,
                "artifact_version": self.artifact_version,
                "previous_version": self.previous_version,
                "amendment_event_id": self.amendment_event_id,
                "guarantees_added": list(self.guarantees_added),
                "guarantees_modified": list(self.guarantees_modified),
                "guarantees_removed": list(self.guarantees_removed),
                "updated_at": self.updated_at.isoformat(),
                "reason": self.reason,
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "artifact_version": self.artifact_version,
            "previous_version": self.previous_version,
            "amendment_event_id": self.amendment_event_id,
            "guarantees_added": list(self.guarantees_added),
            "guarantees_modified": list(self.guarantees_modified),
            "guarantees_removed": list(self.guarantees_removed),
            "updated_at": self.updated_at.isoformat(),
            "reason": self.reason,
        }

    @property
    def change_summary(self) -> str:
        """Generate a summary of changes for logging.

        Returns:
            Human-readable summary of changes.
        """
        parts = []
        if self.guarantees_added:
            parts.append(f"added {len(self.guarantees_added)}")
        if self.guarantees_modified:
            parts.append(f"modified {len(self.guarantees_modified)}")
        if self.guarantees_removed:
            parts.append(f"removed {len(self.guarantees_removed)}")
        return f"Guarantees: {', '.join(parts)}"
