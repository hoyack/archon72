"""Deliberation output event types (Story 2.1, FR9).

This module defines the DeliberationOutputPayload and event type constant
for recording agent deliberation outputs. This is the foundational component
for the No Preview constraint - all agent outputs must be recorded before
any human views them.

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

ADR-2: Context Bundles (Format + Integrity)
- Content hash computed from canonical JSON
- Hash algorithm version tracked
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

# Event type constant following lowercase.dot.notation convention
DELIBERATION_OUTPUT_EVENT_TYPE: str = "deliberation.output"


@dataclass(frozen=True, eq=True)
class DeliberationOutputPayload:
    """Payload for deliberation output events (FR9).

    Records agent output for the No Preview constraint. Every agent output
    must be committed to the event store with a content hash before any
    human can view it.

    Attributes:
        output_id: Unique identifier for this output (UUID).
        agent_id: ID of the agent that produced the output.
        content_hash: SHA-256 hash of the raw_content (64 hex chars).
        content_type: MIME type of the content (e.g., "text/plain").
        raw_content: The actual agent output content.

    Constitutional Constraints:
        - FR9: Content hash enables verification that output was not modified
        - CT-12: Output is witnessed and recorded before viewing

    Example:
        >>> from uuid import uuid4
        >>> payload = DeliberationOutputPayload(
        ...     output_id=uuid4(),
        ...     agent_id="archon-42",
        ...     content_hash="a" * 64,
        ...     content_type="text/plain",
        ...     raw_content="Agent deliberation output",
        ... )
    """

    output_id: UUID
    agent_id: str
    content_hash: str
    content_type: str
    raw_content: str

    def __post_init__(self) -> None:
        """Validate payload fields.

        Raises:
            TypeError: If output_id is not a UUID.
            ValueError: If any field fails validation.
        """
        self._validate_output_id()
        self._validate_agent_id()
        self._validate_content_hash()

    def _validate_output_id(self) -> None:
        """Validate output_id is a UUID."""
        if not isinstance(self.output_id, UUID):
            raise TypeError(
                f"output_id must be UUID, got {type(self.output_id).__name__}"
            )

    def _validate_agent_id(self) -> None:
        """Validate agent_id is non-empty string."""
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty string")

    def _validate_content_hash(self) -> None:
        """Validate content_hash is 64 character hex string (SHA-256)."""
        if not isinstance(self.content_hash, str) or len(self.content_hash) != 64:
            raise ValueError(
                f"content_hash must be 64 character hex string (SHA-256), "
                f"got {len(self.content_hash) if isinstance(self.content_hash, str) else type(self.content_hash).__name__}"
            )

    def to_dict(self) -> dict[str, str]:
        """Convert payload to dictionary for event payload field.

        Returns:
            Dictionary with string values suitable for JSON serialization.
        """
        return {
            "output_id": str(self.output_id),
            "agent_id": self.agent_id,
            "content_hash": self.content_hash,
            "content_type": self.content_type,
            "raw_content": self.raw_content,
        }
