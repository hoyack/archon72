"""Certified result event types (Story 2.8, FR99-FR101).

This module defines the CertifiedResultPayload and event type constant
for recording certified deliberation results. Certification ensures that
deliberation outcomes are officially recorded and can be verified by
external observers.

Constitutional Constraints:
- FR99: Deliberation results SHALL have certified result events
- FR100: Certification SHALL include result_hash, participant_count, certification_timestamp
- FR101: Certification signature SHALL be verifiable
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

# Event type constant following lowercase.dot.notation convention
CERTIFIED_RESULT_EVENT_TYPE: str = "deliberation.result.certified"


@dataclass(frozen=True, eq=True)
class CertifiedResultPayload:
    """Payload for certified result events (FR99-FR101).

    Records a certified deliberation result. Certification ensures the result
    is officially recorded with cryptographic proof that can be verified by
    external observers.

    Attributes:
        result_id: Unique identifier for this certified result (UUID).
        deliberation_id: ID of the deliberation being certified (UUID).
        result_hash: SHA-256 hash of result content (64 hex chars).
        participant_count: Number of participants in the deliberation.
        certification_timestamp: When certification was created.
        certification_key_id: ID of key used for certification signature.
        result_type: Type of result (e.g., "vote", "resolution", "decision").

    Constitutional Constraints:
        - FR99: Certification creates official record of result
        - FR100: Required fields enable verification
        - FR101: Key ID enables signature verification
        - CT-12: Result is witnessed and certified before disclosure

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> payload = CertifiedResultPayload(
        ...     result_id=uuid4(),
        ...     deliberation_id=uuid4(),
        ...     result_hash="a" * 64,
        ...     participant_count=72,
        ...     certification_timestamp=datetime.now(timezone.utc),
        ...     certification_key_id="CERT:key-001",
        ...     result_type="vote",
        ... )
    """

    result_id: UUID
    deliberation_id: UUID
    result_hash: str
    participant_count: int
    certification_timestamp: datetime
    certification_key_id: str
    result_type: str

    def __post_init__(self) -> None:
        """Validate payload fields.

        Raises:
            TypeError: If result_id or deliberation_id is not a UUID.
            ValueError: If any field fails validation.
        """
        self._validate_result_id()
        self._validate_deliberation_id()
        self._validate_result_hash()
        self._validate_participant_count()
        self._validate_certification_key_id()
        self._validate_result_type()

    def _validate_result_id(self) -> None:
        """Validate result_id is a UUID."""
        if not isinstance(self.result_id, UUID):
            raise TypeError(
                f"result_id must be UUID, got {type(self.result_id).__name__}"
            )

    def _validate_deliberation_id(self) -> None:
        """Validate deliberation_id is a UUID."""
        if not isinstance(self.deliberation_id, UUID):
            raise TypeError(
                f"deliberation_id must be UUID, got {type(self.deliberation_id).__name__}"
            )

    def _validate_result_hash(self) -> None:
        """Validate result_hash is 64 character hex string (SHA-256)."""
        if not isinstance(self.result_hash, str) or len(self.result_hash) != 64:
            length = (
                len(self.result_hash) if isinstance(self.result_hash, str) else "N/A"
            )
            raise ValueError(
                f"result_hash must be 64 character hex string (SHA-256), got length {length}"
            )

    def _validate_participant_count(self) -> None:
        """Validate participant_count is non-negative."""
        if not isinstance(self.participant_count, int) or self.participant_count < 0:
            raise ValueError(
                f"participant_count must be >= 0, got {self.participant_count}"
            )

    def _validate_certification_key_id(self) -> None:
        """Validate certification_key_id is non-empty string."""
        if (
            not isinstance(self.certification_key_id, str)
            or not self.certification_key_id
        ):
            raise ValueError("certification_key_id must be non-empty string")

    def _validate_result_type(self) -> None:
        """Validate result_type is non-empty string."""
        if not isinstance(self.result_type, str) or not self.result_type:
            raise ValueError("result_type must be non-empty string")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for event payload field.

        Returns:
            Dictionary with values suitable for JSON serialization.
        """
        return {
            "result_id": str(self.result_id),
            "deliberation_id": str(self.deliberation_id),
            "result_hash": self.result_hash,
            "participant_count": self.participant_count,
            "certification_timestamp": self.certification_timestamp.isoformat(),
            "certification_key_id": self.certification_key_id,
            "result_type": self.result_type,
        }
