"""Event Replicator port - interface for replica propagation and verification.

Story: 1.10 - Replica Configuration Preparation (FR8, FR94-FR95)

This port defines the interface for:
- FR94: Event propagation to replicas (propagate_event)
- FR95: Replica verification (verify_replicas)

Constitutional Context:
- CT-12: Witnessing creates accountability - replicas must maintain integrity
- ADR-1: Single canonical Writer - replicas are read-only

Architecture (from ADR-1):
- Single Writer writes to primary PostgreSQL
- Read-only replicas via managed Postgres replication (Supabase)
- Failover is ceremony-based: watchdog detection + human approval + witnessed promotion

Epic 1 Implementation:
- This story creates the interface and stub only
- Actual replication is deployment-phase work
- Stub returns success (no replicas configured in development)

Future Implementation (Deployment Phase):
- Wire to Supabase read replica APIs
- Implement replica health monitoring
- Add lag detection and alerting
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ReplicationStatus(Enum):
    """Status of event replication to replicas."""

    PENDING = "pending"  # Replication in progress
    CONFIRMED = "confirmed"  # All replicas confirmed receipt
    FAILED = "failed"  # Replication failed (requires investigation)
    NOT_CONFIGURED = "not_configured"  # No replicas configured (dev mode)


@dataclass(frozen=True)
class ReplicationReceipt:
    """Receipt confirming event propagation to replicas.

    Attributes:
        event_id: The UUID of the event that was propagated.
        replica_ids: Tuple of replica identifiers that received the event (immutable).
        status: Current replication status.
        timestamp: When the propagation was initiated/completed.
    """

    event_id: UUID
    replica_ids: tuple[str, ...]
    status: ReplicationStatus
    timestamp: datetime


@dataclass(frozen=True)
class VerificationResult:
    """Result of replica consistency verification.

    Verification checks that all replicas:
    1. Have the same head hash as primary
    2. Maintain valid signatures on all events
    3. Use compatible schema versions

    Attributes:
        head_hash_match: True if all replica head hashes match primary.
        signature_valid: True if all signatures verified successfully.
        schema_version_match: True if all replicas use compatible schema.
        errors: Tuple of error messages if verification failed (immutable).
    """

    head_hash_match: bool
    signature_valid: bool
    schema_version_match: bool
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Check if all verification checks passed."""
        return (
            self.head_hash_match
            and self.signature_valid
            and self.schema_version_match
            and len(self.errors) == 0
        )


class EventReplicatorPort(ABC):
    """Abstract interface for event replication operations.

    This port enables dependency inversion for replication infrastructure.
    Epic 1 uses a stub that returns success (no replicas configured).
    Production implementations will wire to Supabase replica APIs.

    Single-Writer Architecture (ADR-1):
    - All writes go to primary PostgreSQL only
    - Replicas receive events via logical replication
    - This interface is for MONITORING and VERIFICATION, not for writes

    Usage:
        # Check if replicas are healthy before operations
        result = await replicator.verify_replicas()
        if not result.is_valid:
            log.warning("replica_drift_detected", errors=result.errors)

        # Optionally notify about new events (optimization, not required)
        receipt = await replicator.propagate_event(event_id)
    """

    @abstractmethod
    async def propagate_event(self, event_id: UUID) -> ReplicationReceipt:
        """Notify replicas of a new event.

        This method is an OPTIONAL optimization. PostgreSQL logical replication
        handles actual data propagation. This interface allows:
        - Tracking propagation status
        - Alerting on replication lag
        - Coordinating read-after-write scenarios

        Note: In single-writer architecture, events are written to primary only.
        Replicas receive data via PostgreSQL logical replication, not this method.

        Args:
            event_id: The UUID of the event to propagate.

        Returns:
            ReplicationReceipt with propagation status and replica list.
        """
        ...

    @abstractmethod
    async def verify_replicas(self) -> VerificationResult:
        """Verify all replicas are consistent with primary.

        Verification checks:
        1. Head hash match - all replicas have same latest event hash
        2. Signature validity - all events have valid signatures
        3. Schema version - all replicas use compatible schema version

        This method should be called:
        - Periodically by health monitoring
        - Before critical operations (optional)
        - After suspected replication issues

        Returns:
            VerificationResult with consistency check outcomes.
        """
        ...
