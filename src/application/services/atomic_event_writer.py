"""Atomic Event Writer with witness attestation (FR4, FR5, FR6, FR81).

This service coordinates atomic event writing with both agent signing
and witness attestation. All operations are performed atomically -
either the complete event (with signatures) is persisted, or nothing is.

Constitutional Constraints:
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- FR6: Events must have dual timestamps (Story 1.5)
- FR81: Atomic operations - complete success or complete rollback

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Witness attestation creates verifiable audit trail
- CT-13: Integrity outranks availability -> Reject writes without witnesses
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.application.ports.event_store import EventStorePort
from src.application.services.signing_service import SigningService
from src.application.services.witness_service import WitnessService
from src.domain.events.event import Event
from src.domain.events.hash_utils import get_prev_hash
from src.domain.primitives import AtomicOperationContext

if TYPE_CHECKING:
    from src.application.services.time_authority_service import TimeAuthorityService


def _compute_signable_hash(
    event_type: str,
    payload: dict[str, Any],
    local_timestamp: datetime,
    agent_id: str | None,
) -> str:
    """Compute hash of event data for signing purposes.

    This hash is computed BEFORE signatures are created, so it does NOT
    include signature, witness_id, or witness_signature fields.

    The signatures then cover this hash (plus chain binding).
    The final content_hash (stored in DB) includes signatures.

    Args:
        event_type: Event type classification.
        payload: Event payload data.
        local_timestamp: Timestamp from event source.
        agent_id: ID of agent creating the event (if any).

    Returns:
        SHA-256 hash of the signable content (64 hex chars).
    """
    # Convert timestamp to ISO format
    ts_str = (
        local_timestamp.isoformat()
        if isinstance(local_timestamp, datetime)
        else str(local_timestamp)
    )

    hashable: dict[str, Any] = {
        "event_type": event_type,
        "payload": payload,
        "local_timestamp": ts_str,
    }

    if agent_id is not None:
        hashable["agent_id"] = agent_id

    # Canonical JSON: sorted keys, no whitespace
    canonical = json.dumps(
        hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AtomicEventWriter:
    """Atomic event writing with witness attestation (FR4, FR5, FR6, FR81).

    Constitutional Constraint (CT-12):
    Witnessing creates accountability - no unwitnessed events.

    Uses AtomicOperationContext primitive from Epic 0 to guarantee:
    - All or nothing: event + witness or neither
    - No partial state on failure
    - Rollback handlers execute on any exception

    The write operation performs these steps atomically:
    1. Get next sequence from event store
    2. Compute content hash
    3. Get agent signature (Story 1-3)
    4. Get witness attestation (Story 1-4)
    5. Create event with all signatures
    6. Persist event to store
    7. Check clock drift (Story 1-5, FR6 - post-write, informational only)

    If any step fails, no event is persisted.

    Attributes:
        _signing_service: Service for agent signing operations.
        _witness_service: Service for witness attestation.
        _event_store: Port for event storage operations.
        _time_authority: Optional service for clock drift detection (FR6).
    """

    def __init__(
        self,
        signing_service: SigningService,
        witness_service: WitnessService,
        event_store: EventStorePort,
        time_authority: TimeAuthorityService | None = None,
    ) -> None:
        """Initialize the atomic event writer.

        Args:
            signing_service: Service for agent signing.
            witness_service: Service for witness attestation.
            event_store: Port for event storage.
            time_authority: Optional TimeAuthorityService for clock drift
                detection (FR6). If provided, drift is checked after write
                but does NOT reject events (sequence is authoritative).
        """
        self._signing_service = signing_service
        self._witness_service = witness_service
        self._event_store = event_store
        self._time_authority = time_authority

    async def write_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        agent_id: str,
        local_timestamp: datetime,
    ) -> Event:
        """Write event with atomic witness attestation.

        This method performs all operations atomically:
        1. Gets next sequence from event store
        2. Computes content hash
        3. Gets agent signature (Story 1-3)
        4. Gets witness attestation (this story)
        5. Creates event with all signatures
        6. Persists event atomically (all or nothing)

        Args:
            event_type: Event type classification.
            payload: Event payload data.
            agent_id: Agent creating the event.
            local_timestamp: Timestamp from event source.

        Returns:
            The created Event with witness attestation.

        Raises:
            NoWitnessAvailableError: If no witnesses available (RT-1).
                This MUST cause the event write to be rejected.
            SigningError: If agent or witness signing fails.
            EventStoreError: If event persistence fails.
        """
        persisted_event: Event
        async with AtomicOperationContext():
            # Step 1: Get latest event for chain continuity
            latest_event = await self._event_store.get_latest_event()

            # Determine sequence and previous hash
            if latest_event is None:
                sequence = 1
                previous_content_hash: str | None = None
            else:
                sequence = latest_event.sequence + 1
                previous_content_hash = latest_event.content_hash

            # Compute prev_hash using domain function
            prev_hash = get_prev_hash(
                sequence=sequence,
                previous_content_hash=previous_content_hash,
            )

            # Step 2: Compute signable hash (content without signatures)
            # This is what gets signed by both agent and witness
            signable_hash = _compute_signable_hash(
                event_type=event_type,
                payload=payload,
                local_timestamp=local_timestamp,
                agent_id=agent_id,
            )

            # Step 3: Agent signs (Story 1-3 pattern)
            # This MUST complete before witness attestation
            (
                signature,
                signing_key_id,
                sig_alg_version,
            ) = await self._signing_service.sign_event(
                content_hash=signable_hash,
                prev_hash=prev_hash,
                agent_id=agent_id,
            )

            # Step 4: Witness attests (THIS STORY - atomic with event write)
            # If no witness available, NoWitnessAvailableError is raised
            # and the entire operation is rolled back (no event persisted)
            witness_id, witness_signature = await self._witness_service.attest_event(
                event_content_hash=signable_hash,
            )

            # Step 5: Create event with all signatures
            event = Event.create_with_hash(
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                signature=signature,
                signing_key_id=signing_key_id,
                witness_id=witness_id,
                witness_signature=witness_signature,
                local_timestamp=local_timestamp,
                previous_content_hash=previous_content_hash,
                agent_id=agent_id,
            )

            # Step 6: Persist atomically
            persisted_event = await self._event_store.append_event(event)

            # Step 7: Check clock drift (FR6 - informational only, post-write)
            # This does NOT reject events - sequence is authoritative (AC4)
            if (
                self._time_authority is not None
                and persisted_event.authority_timestamp is not None
            ):
                self._time_authority.check_drift(
                    local_timestamp=persisted_event.local_timestamp,
                    authority_timestamp=persisted_event.authority_timestamp,
                    event_id=str(persisted_event.event_id),
                )

        return persisted_event
