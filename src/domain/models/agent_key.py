"""Agent key domain model for cryptographic signing (FR75, FR76).

This module defines the AgentKey entity for the agent key registry.
Agent keys are used to sign events and verify agent attribution.

Constitutional Constraints:
- FR75: Key registry must track active keys
- FR76: Historical keys must be preserved (no deletion)
- FR3: Events must have agent attribution

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Agent attribution creates verifiable authorship

Note: DeletePreventionMixin ensures `.delete()` raises
ConstitutionalViolationError before any DB interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.primitives import DeletePreventionMixin

# System agent ID prefix
SYSTEM_AGENT_PREFIX: str = "SYSTEM:"


@dataclass(frozen=True, eq=True)
class AgentKey(DeletePreventionMixin):
    """Agent signing key entity - immutable, deletion prohibited.

    Agent keys are the foundation of cryptographic attribution in the
    constitutional event store. Each key is associated with an agent
    and has a temporal validity period.

    Constitutional Constraints:
    - FR75: Key registry must track active keys
    - FR76: Historical keys must be preserved (no deletion)

    Attributes:
        id: Unique identifier for this key record (UUID)
        agent_id: ID of agent that owns this key
            Format: "agent-{uuid}" or "SYSTEM:{service_name}"
        key_id: HSM key identifier (unique across all keys)
        public_key: Ed25519 public key bytes (32 bytes)
        active_from: When this key became active
        active_until: When this key was rotated out (None = currently active)
        created_at: When this record was created

    Note:
        DeletePreventionMixin ensures `.delete()` raises
        ConstitutionalViolationError before any DB interaction.
    """

    # Primary identifier
    id: UUID

    # Agent identifier (FR3)
    agent_id: str

    # HSM key identifier (unique)
    key_id: str

    # Ed25519 public key bytes (32 bytes)
    public_key: bytes

    # Temporal validity
    active_from: datetime

    # Expiry (None = currently active)
    active_until: datetime | None = field(default=None)

    # Audit timestamp
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_id()
        self._validate_agent_id()
        self._validate_key_id()
        self._validate_public_key()

    def _validate_id(self) -> None:
        """Validate id is UUID."""
        if not isinstance(self.id, UUID):
            raise ConstitutionalViolationError(
                f"FR75: AgentKey validation failed - id must be UUID, got {type(self.id).__name__}"
            )

    def _validate_agent_id(self) -> None:
        """Validate agent_id is non-empty string."""
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise ConstitutionalViolationError(
                "FR75: AgentKey validation failed - agent_id must be non-empty string"
            )

    def _validate_key_id(self) -> None:
        """Validate key_id is non-empty string."""
        if not isinstance(self.key_id, str) or not self.key_id.strip():
            raise ConstitutionalViolationError(
                "FR75: AgentKey validation failed - key_id must be non-empty string"
            )

    def _validate_public_key(self) -> None:
        """Validate public_key is Ed25519 public key (32 bytes)."""
        if not isinstance(self.public_key, bytes):
            raise ConstitutionalViolationError(
                "FR75: AgentKey validation failed - public_key must be bytes"
            )
        # Ed25519 public keys are exactly 32 bytes
        if len(self.public_key) != 32:
            raise ConstitutionalViolationError(
                f"FR75: AgentKey validation failed - public_key must be 32 bytes (Ed25519), got {len(self.public_key)}"
            )

    def __hash__(self) -> int:
        """Hash based on id (unique identifier).

        Note: public_key is excluded from hash since bytes are included
        in the dataclass comparison but we want set membership to be
        based on id alone.
        """
        return hash(self.id)

    def is_system_agent(self) -> bool:
        """Check if this key belongs to a system agent.

        System agents use the format "SYSTEM:{service_name}"
        (e.g., "SYSTEM:WATCHDOG", "SYSTEM:SCHEDULER").

        Returns:
            True if agent_id starts with "SYSTEM:", False otherwise.
        """
        return self.agent_id.startswith(SYSTEM_AGENT_PREFIX)

    def is_active_at(self, timestamp: datetime) -> bool:
        """Check if this key was active at a specific time.

        Used for historical verification - when verifying old events,
        we need to find the key that was active when the event was created.

        Args:
            timestamp: The time to check against.

        Returns:
            True if key was active at the given time, False otherwise.
        """
        # Must be after active_from
        if timestamp < self.active_from:
            return False

        # If no expiry, key is still active
        if self.active_until is None:
            return True

        # Must be before active_until
        return timestamp < self.active_until

    def is_currently_active(self) -> bool:
        """Check if this key is currently active.

        Convenience method that calls is_active_at with current time.

        Returns:
            True if key is currently active, False otherwise.
        """
        return self.is_active_at(datetime.now(timezone.utc))
