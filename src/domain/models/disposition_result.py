"""Disposition result domain models (Story 2A.8, FR-11.11).

This module defines the domain models for disposition emission
and pipeline routing results.

Constitutional Constraints:
- CT-14: Every claim terminates in witnessed fate
- CT-12: All transitions witnessed
- FR-11.11: Route to appropriate pipeline

Developer Golden Rules:
1. Models are immutable (frozen dataclasses)
2. All models include to_dict() for serialization (D2)
3. Use UUID for identifiers, not strings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.events.disposition import (
    DeliberationCompleteEvent,
    DispositionOutcome,
    PipelineRoutingEvent,
    PipelineType,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class DispositionResult:
    """Result of disposition emission (Story 2A.8).

    Captures both the deliberation completion event and
    the pipeline routing that follows.

    Attributes:
        deliberation_event: The DeliberationCompleteEvent.
        routing_event: The PipelineRoutingEvent.
        success: Whether emission completed successfully.
        error_message: Error details if success=False.
    """

    deliberation_event: DeliberationCompleteEvent
    routing_event: PipelineRoutingEvent
    success: bool = field(default=True)
    error_message: str | None = field(default=None)

    @property
    def outcome(self) -> DispositionOutcome:
        """The disposition outcome."""
        return self.deliberation_event.outcome

    @property
    def target_pipeline(self) -> PipelineType:
        """The target pipeline for routing."""
        return self.routing_event.pipeline

    @property
    def petition_id(self) -> UUID:
        """The petition ID."""
        return self.deliberation_event.petition_id

    @property
    def session_id(self) -> UUID:
        """The deliberation session ID."""
        return self.deliberation_event.session_id

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "deliberation_event": self.deliberation_event.to_dict(),
            "routing_event": self.routing_event.to_dict(),
            "success": self.success,
            "error_message": self.error_message,
            "schema_version": 1,
        }


@dataclass(frozen=True, eq=True)
class PendingDisposition:
    """A disposition waiting to be processed by a pipeline.

    Used by downstream pipelines (Epic 3, 4, 6) to retrieve
    their queued work from the disposition emission service.

    Attributes:
        petition_id: UUID of the petition.
        outcome: The disposition outcome.
        pipeline: Target pipeline.
        deliberation_event_id: The triggering event ID.
        queued_at: When added to the pipeline queue.
        priority: Processing priority (lower = higher priority).
        routing_metadata: Pipeline-specific metadata.
    """

    petition_id: UUID
    outcome: DispositionOutcome
    pipeline: PipelineType
    deliberation_event_id: UUID
    queued_at: datetime = field(default_factory=_utc_now)
    priority: int = field(default=100)
    routing_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "petition_id": str(self.petition_id),
            "outcome": self.outcome.value,
            "pipeline": self.pipeline.value,
            "deliberation_event_id": str(self.deliberation_event_id),
            "queued_at": self.queued_at.isoformat(),
            "priority": self.priority,
            "routing_metadata": self.routing_metadata,
            "schema_version": 1,
        }
