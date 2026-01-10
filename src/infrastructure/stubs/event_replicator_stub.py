"""Stub EventReplicator for Epic 1 - always returns success (Story 1.10).

This stub allows Epic 1 code to use the replication interface without
actual replica infrastructure. In development, no replicas are configured.

Future Implementation (Deployment Phase):
- Wire to Supabase read replica APIs
- Implement replica health monitoring
- Add lag detection and alerting

WARNING: This stub is for development/testing only.
Production must use a real EventReplicator implementation.
"""

import sys
from datetime import datetime, timezone
from uuid import UUID

# Python 3.11+ has datetime.UTC, earlier versions need timezone.utc
# This compatibility shim allows running on Python 3.10 dev environments
# while project targets 3.11+
if sys.version_info >= (3, 11):  # noqa: UP036
    from datetime import timezone
else:
    UTC = timezone.utc  # noqa: UP017

import structlog

from src.application.ports.event_replicator import (
    EventReplicatorPort,
    ReplicationReceipt,
    ReplicationStatus,
    VerificationResult,
)

log = structlog.get_logger()


class EventReplicatorStub(EventReplicatorPort):
    """Stub implementation that always returns success (no replicas configured).

    This stub satisfies the EventReplicatorPort interface so Epic 1 code can
    use replication interfaces without depending on replica infrastructure.

    Development Mode Behavior:
    - propagate_event(): Returns NOT_CONFIGURED status (no replicas)
    - verify_replicas(): Returns positive verification (single-node mode)

    For testing replica behavior, use EventReplicatorStub with:
    - _force_failure=True to simulate failures
    - _replica_ids to simulate configured replicas

    Attributes:
        _force_failure: If True, operations return failed status (for testing).
        _replica_ids: Tuple of simulated replica IDs (for testing).
    """

    # Watermark for dev mode indication (following DevHSM pattern)
    DEV_MODE_WATERMARK = "[DEV MODE - NO REPLICAS]"

    def __init__(
        self,
        *,
        force_failure: bool = False,
        replica_ids: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        """Initialize the stub.

        Args:
            force_failure: If True, operations simulate failure (for testing).
            replica_ids: Tuple or list of simulated replica IDs (for testing).
        """
        self._force_failure = force_failure
        self._replica_ids: tuple[str, ...] = tuple(replica_ids) if replica_ids else ()

        log.info(
            "event_replicator_stub_initialized",
            watermark=self.DEV_MODE_WATERMARK,
            force_failure=force_failure,
            replica_count=len(self._replica_ids),
        )

    async def propagate_event(self, event_id: UUID) -> ReplicationReceipt:
        """Stub: Returns success receipt (no replicas configured).

        In development mode, there are no replicas to propagate to.
        Returns NOT_CONFIGURED status indicating single-node operation.

        Args:
            event_id: The UUID of the event to propagate.

        Returns:
            ReplicationReceipt with NOT_CONFIGURED or CONFIRMED status.
        """
        timestamp = datetime.now(timezone.utc)

        if self._force_failure:
            log.warning(
                "event_replicator_stub_forced_failure",
                event_id=str(event_id),
                watermark=self.DEV_MODE_WATERMARK,
            )
            return ReplicationReceipt(
                event_id=event_id,
                replica_ids=self._replica_ids,
                status=ReplicationStatus.FAILED,
                timestamp=timestamp,
            )

        if not self._replica_ids:
            # No replicas configured - development mode
            log.debug(
                "event_replicator_stub_no_replicas",
                event_id=str(event_id),
                watermark=self.DEV_MODE_WATERMARK,
            )
            return ReplicationReceipt(
                event_id=event_id,
                replica_ids=(),
                status=ReplicationStatus.NOT_CONFIGURED,
                timestamp=timestamp,
            )

        # Simulated replicas configured - return confirmed
        log.debug(
            "event_replicator_stub_propagate",
            event_id=str(event_id),
            replica_ids=self._replica_ids,
            watermark=self.DEV_MODE_WATERMARK,
        )
        return ReplicationReceipt(
            event_id=event_id,
            replica_ids=self._replica_ids,
            status=ReplicationStatus.CONFIRMED,
            timestamp=timestamp,
        )

    async def verify_replicas(self) -> VerificationResult:
        """Stub: Returns positive verification (single-node mode).

        In development mode with no replicas, verification always passes.
        This allows code to call verify_replicas() without actual replicas.

        Returns:
            VerificationResult with positive checks (or failure if forced).
        """
        if self._force_failure:
            log.warning(
                "event_replicator_stub_verify_forced_failure",
                watermark=self.DEV_MODE_WATERMARK,
            )
            return VerificationResult(
                head_hash_match=False,
                signature_valid=False,
                schema_version_match=False,
                errors=("Stub: Forced verification failure for testing",),
            )

        if not self._replica_ids:
            # No replicas - verification trivially passes
            log.debug(
                "event_replicator_stub_verify_no_replicas",
                watermark=self.DEV_MODE_WATERMARK,
            )
            return VerificationResult(
                head_hash_match=True,
                signature_valid=True,
                schema_version_match=True,
                errors=(),
            )

        # Simulated replicas - return positive verification
        log.debug(
            "event_replicator_stub_verify",
            replica_ids=self._replica_ids,
            watermark=self.DEV_MODE_WATERMARK,
        )
        return VerificationResult(
            head_hash_match=True,
            signature_valid=True,
            schema_version_match=True,
            errors=(),
        )

    def set_failure_mode(self, failure: bool) -> None:
        """Test helper: Set failure mode.

        Args:
            failure: If True, operations will simulate failure.
        """
        self._force_failure = failure
        log.debug(
            "event_replicator_stub_failure_mode_changed",
            force_failure=failure,
        )

    def set_replica_ids(self, replica_ids: tuple[str, ...] | list[str]) -> None:
        """Test helper: Set simulated replica IDs.

        Args:
            replica_ids: Tuple or list of simulated replica identifiers.
        """
        self._replica_ids = tuple(replica_ids)
        log.debug(
            "event_replicator_stub_replicas_changed",
            replica_count=len(replica_ids),
        )
