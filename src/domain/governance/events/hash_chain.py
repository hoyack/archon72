"""Hash chain computation and verification for governance events.

Story: consent-gov-1.3: Hash Chain Implementation

This module provides hash chain functionality for the consent-based
governance event ledger, ensuring cryptographic linking between events.

Hash Chain Properties:
- Each event's hash is computed from its content
- Each event's prev_hash links to the previous event's hash
- Genesis event uses well-known null hash (all zeros)
- Both BLAKE3 and SHA-256 algorithms supported
- Tampering or gaps are detectable via verification

Hash Computation (Locked per governance-architecture.md):
    hash = algorithm(canonical_json(metadata_without_hash) + canonical_json(payload))

Constitutional Constraints:
- AD-6: BLAKE3/SHA-256 hash algorithms
- NFR-CONST-02: Event integrity verification
- NFR-AUDIT-06: Deterministic replay
- FR1: Events must be hash-chained
- FR2: Tampering detection

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Hash Chain Implementation (Locked)]
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.governance.events.canonical_json import canonical_json_bytes
from src.domain.governance.events.hash_algorithms import (
    DEFAULT_ALGORITHM,
    GENESIS_PREV_HASH,
    compute_hash,
    extract_algorithm_from_hash,
    is_genesis_hash,
    make_genesis_hash,
    validate_hash_format,
    verify_hash,
)

if TYPE_CHECKING:
    from src.domain.governance.events.event_envelope import (
        EventMetadata,
        GovernanceEvent,
    )


@dataclass(frozen=True)
class HashVerificationResult:
    """Result of hash chain verification.

    Attributes:
        is_valid: Whether the hash verification passed.
        event_hash_valid: Whether the event's hash matches its content.
        chain_link_valid: Whether prev_hash links correctly to previous event.
        error_message: Description of failure (if any).
        expected_hash: Expected hash value (for debugging).
        actual_hash: Actual computed hash value (for debugging).
    """

    is_valid: bool
    event_hash_valid: bool
    chain_link_valid: bool
    error_message: str = ""
    expected_hash: str = ""
    actual_hash: str = ""


def _metadata_to_dict_for_hash(metadata: "EventMetadata") -> dict[str, Any]:
    """Convert EventMetadata to dict for hashing, excluding hash field.

    Per AD-6: Hash is computed from metadata (excluding hash field) + payload.
    The hash field itself must be excluded to avoid circular dependency.

    Args:
        metadata: The EventMetadata to convert.

    Returns:
        Dictionary representation excluding the hash field.
    """
    return {
        "event_id": metadata.event_id,
        "event_type": metadata.event_type,
        "timestamp": metadata.timestamp,
        "actor_id": metadata.actor_id,
        "schema_version": metadata.schema_version,
        "trace_id": metadata.trace_id,
        "prev_hash": metadata.prev_hash,
        # hash field explicitly excluded - it's what we're computing
    }


def compute_event_hash(
    event: "GovernanceEvent",
    algorithm: str = DEFAULT_ALGORITHM,
) -> str:
    """Compute the hash of a governance event.

    Hash is computed from:
    - canonical_json(metadata_without_hash)
    - canonical_json(payload)

    The hash field in metadata is excluded from computation (would be circular).

    Args:
        event: The GovernanceEvent to hash.
        algorithm: Hash algorithm to use ('blake3' or 'sha256').

    Returns:
        Algorithm-prefixed hash string (e.g., 'blake3:abc123...').

    Raises:
        ConstitutionalViolationError: If event is missing prev_hash.
        ValueError: If algorithm is not supported.
    """
    if not event.prev_hash:
        raise ConstitutionalViolationError(
            "AD-6: Cannot compute event hash without prev_hash. "
            "Use compute_event_hash_with_prev() for events without prev_hash."
        )

    # Convert metadata (excluding hash) and payload to canonical JSON bytes
    metadata_dict = _metadata_to_dict_for_hash(event.metadata)
    payload_dict = dict(event.payload)  # Convert MappingProxyType to dict

    # Concatenate canonical JSON representations
    content = canonical_json_bytes(metadata_dict) + canonical_json_bytes(payload_dict)

    return compute_hash(content, algorithm)


def compute_event_hash_with_prev(
    event: "GovernanceEvent",
    prev_hash: str,
    algorithm: str = DEFAULT_ALGORITHM,
) -> str:
    """Compute event hash with a specified prev_hash.

    Use this when the event's prev_hash hasn't been set yet,
    such as when creating a new event for the chain.

    Args:
        event: The GovernanceEvent to hash.
        prev_hash: The prev_hash to use in computation.
        algorithm: Hash algorithm to use ('blake3' or 'sha256').

    Returns:
        Algorithm-prefixed hash string.

    Raises:
        ConstitutionalViolationError: If prev_hash format is invalid.
    """
    if not validate_hash_format(prev_hash) and not is_genesis_hash(prev_hash):
        raise ConstitutionalViolationError(
            f"AD-6: Invalid prev_hash format: {prev_hash!r}. "
            f"Expected format: algorithm:hex_digest"
        )

    # Build metadata dict with the provided prev_hash
    metadata_dict = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "actor_id": event.actor_id,
        "schema_version": event.schema_version,
        "trace_id": event.trace_id,
        "prev_hash": prev_hash,
    }
    payload_dict = dict(event.payload)

    content = canonical_json_bytes(metadata_dict) + canonical_json_bytes(payload_dict)

    return compute_hash(content, algorithm)


def verify_event_hash(event: "GovernanceEvent") -> HashVerificationResult:
    """Verify that an event's hash matches its content.

    The algorithm is extracted from the hash prefix, so this works
    for both BLAKE3 and SHA-256 hashed events.

    Args:
        event: The GovernanceEvent to verify.

    Returns:
        HashVerificationResult with verification details.
    """
    if not event.hash:
        return HashVerificationResult(
            is_valid=False,
            event_hash_valid=False,
            chain_link_valid=True,  # Can't verify chain without hash
            error_message="Event has no hash to verify",
        )

    if not event.prev_hash:
        return HashVerificationResult(
            is_valid=False,
            event_hash_valid=False,
            chain_link_valid=False,
            error_message="Event has no prev_hash",
        )

    try:
        # Extract algorithm from the stored hash
        algorithm = extract_algorithm_from_hash(event.hash)

        # Compute what the hash should be
        metadata_dict = _metadata_to_dict_for_hash(event.metadata)
        payload_dict = dict(event.payload)
        content = canonical_json_bytes(metadata_dict) + canonical_json_bytes(payload_dict)
        computed_hash = compute_hash(content, algorithm)

        # Compare
        is_valid = computed_hash == event.hash

        return HashVerificationResult(
            is_valid=is_valid,
            event_hash_valid=is_valid,
            chain_link_valid=True,  # Chain link verified separately
            error_message="" if is_valid else "Hash mismatch - event may have been tampered",
            expected_hash=event.hash,
            actual_hash=computed_hash,
        )

    except (ValueError, ConstitutionalViolationError) as e:
        return HashVerificationResult(
            is_valid=False,
            event_hash_valid=False,
            chain_link_valid=False,
            error_message=str(e),
        )


def verify_chain_link(
    current_event: "GovernanceEvent",
    previous_event: "GovernanceEvent | None",
) -> HashVerificationResult:
    """Verify that current event's prev_hash matches previous event's hash.

    For genesis events (previous_event is None), verifies that prev_hash
    is the well-known genesis hash (all zeros).

    Args:
        current_event: The event whose prev_hash to verify.
        previous_event: The previous event in the chain (None for genesis).

    Returns:
        HashVerificationResult with chain link verification details.
    """
    if previous_event is None:
        # Genesis case - prev_hash should be genesis hash
        if is_genesis_hash(current_event.prev_hash):
            return HashVerificationResult(
                is_valid=True,
                event_hash_valid=True,
                chain_link_valid=True,
            )
        else:
            return HashVerificationResult(
                is_valid=False,
                event_hash_valid=True,
                chain_link_valid=False,
                error_message=(
                    f"Genesis event should have null prev_hash, "
                    f"got: {current_event.prev_hash!r}"
                ),
                expected_hash=GENESIS_PREV_HASH,
                actual_hash=current_event.prev_hash,
            )

    # Non-genesis case - prev_hash should match previous event's hash
    if not previous_event.hash:
        return HashVerificationResult(
            is_valid=False,
            event_hash_valid=True,
            chain_link_valid=False,
            error_message="Previous event has no hash to link to",
        )

    if current_event.prev_hash == previous_event.hash:
        return HashVerificationResult(
            is_valid=True,
            event_hash_valid=True,
            chain_link_valid=True,
        )
    else:
        return HashVerificationResult(
            is_valid=False,
            event_hash_valid=True,
            chain_link_valid=False,
            error_message="Chain link broken - prev_hash does not match previous event's hash",
            expected_hash=previous_event.hash,
            actual_hash=current_event.prev_hash,
        )


def verify_event_full(
    event: "GovernanceEvent",
    previous_event: "GovernanceEvent | None" = None,
) -> HashVerificationResult:
    """Perform full verification of an event: hash and chain link.

    Args:
        event: The event to verify.
        previous_event: The previous event for chain link verification.
            If None, assumes this is a genesis event.

    Returns:
        HashVerificationResult with full verification details.
    """
    # First verify the event's own hash
    hash_result = verify_event_hash(event)
    if not hash_result.is_valid:
        return hash_result

    # Then verify the chain link
    link_result = verify_chain_link(event, previous_event)
    if not link_result.is_valid:
        return HashVerificationResult(
            is_valid=False,
            event_hash_valid=True,
            chain_link_valid=False,
            error_message=link_result.error_message,
            expected_hash=link_result.expected_hash,
            actual_hash=link_result.actual_hash,
        )

    return HashVerificationResult(
        is_valid=True,
        event_hash_valid=True,
        chain_link_valid=True,
    )


def add_hash_to_event(
    event: "GovernanceEvent",
    prev_hash: str | None = None,
    algorithm: str = DEFAULT_ALGORITHM,
) -> "GovernanceEvent":
    """Create a new event with computed hash fields.

    Since GovernanceEvent is frozen, this returns a new instance
    with the hash fields populated.

    Args:
        event: The event to add hashes to.
        prev_hash: The prev_hash to use. If None, uses genesis hash.
        algorithm: Hash algorithm to use.

    Returns:
        New GovernanceEvent instance with hash fields set.

    Raises:
        ConstitutionalViolationError: If event already has hash fields.
    """
    from src.domain.governance.events.event_envelope import (
        EventMetadata,
        GovernanceEvent,
    )

    if event.has_hash():
        raise ConstitutionalViolationError(
            "NFR-CONST-02: Cannot re-hash an event that already has hash fields. "
            "Events are immutable once hashed."
        )

    # Determine prev_hash
    actual_prev_hash = prev_hash if prev_hash else make_genesis_hash(algorithm)

    # Compute the event hash
    event_hash = compute_event_hash_with_prev(event, actual_prev_hash, algorithm)

    # Create new metadata with hash fields
    new_metadata = EventMetadata(
        event_id=event.event_id,
        event_type=event.event_type,
        timestamp=event.timestamp,
        actor_id=event.actor_id,
        schema_version=event.schema_version,
        trace_id=event.trace_id,
        prev_hash=actual_prev_hash,
        hash=event_hash,
    )

    # Create new event with hashed metadata
    return GovernanceEvent(
        metadata=new_metadata,
        payload=dict(event.payload),  # Convert MappingProxyType back to dict
    )


def chain_events(
    events: list["GovernanceEvent"],
    algorithm: str = DEFAULT_ALGORITHM,
) -> list["GovernanceEvent"]:
    """Add hash chain to a list of events.

    Takes a list of unhashed events and returns a new list with
    hash chain computed. First event uses genesis hash.

    Args:
        events: List of events to chain (in order).
        algorithm: Hash algorithm to use.

    Returns:
        New list of events with hash fields populated.

    Raises:
        ConstitutionalViolationError: If any event already has hashes.
    """
    if not events:
        return []

    result: list[GovernanceEvent] = []
    prev_hash: str | None = None

    for event in events:
        hashed_event = add_hash_to_event(event, prev_hash, algorithm)
        result.append(hashed_event)
        prev_hash = hashed_event.hash

    return result
