"""Hash utilities for constitutional event chain (FR2, FR82-FR85).

This module provides deterministic hashing functions for the constitutional
event store. All events are hash-chained using SHA-256 to ensure tamper
detection and verifiable history.

Constitutional Constraints:
- FR2: Events must be hash-chained
- FR82: Hash chain continuity must be verified
- FR83: Algorithm version must be tracked
- FR85: Hash algorithm version tracking

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → Hash chain creates verifiable history
- CT-13: Integrity outranks availability → Reject invalid hashes, never degrade
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import datetime
from typing import Any

# Genesis hash: 64 zeros representing "no previous event"
# This is the prev_hash for the first event in any chain (sequence 1)
GENESIS_HASH: str = "0" * 64

# Hash algorithm version (FR85)
# Version 1 = SHA-256
HASH_ALG_VERSION: int = 1
HASH_ALG_NAME: str = "SHA-256"


def _sanitize_for_json(data: Any) -> Any:
    """Recursively sanitize data for deterministic JSON serialization.

    This function:
    - Normalizes Unicode strings using NFKC form (M1 fix)
    - Rejects NaN, Infinity, and -Infinity float values (M2 fix)
    - Recursively processes nested structures

    Args:
        data: Any JSON-serializable data.

    Returns:
        Sanitized data safe for deterministic JSON serialization.

    Raises:
        ValueError: If data contains NaN, Infinity, or -Infinity values.
    """
    if isinstance(data, str):
        # Normalize Unicode to NFKC form for consistent representation
        return unicodedata.normalize("NFKC", data)
    elif isinstance(data, float):
        # Reject non-finite floats that produce invalid JSON
        if math.isnan(data) or math.isinf(data):
            raise ValueError(
                f"Cannot serialize non-finite float value: {data!r}. "
                "NaN and Infinity are not valid JSON."
            )
        return data
    elif isinstance(data, dict):
        return {_sanitize_for_json(k): _sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_for_json(item) for item in data]
    else:
        return data


def canonical_json(data: Any) -> str:
    """Produce deterministic JSON representation for hashing.

    This function creates a canonical JSON string that is:
    - Deterministic: same input always produces same output
    - Sorted: keys are sorted alphabetically (recursive)
    - Compact: no whitespace between elements
    - Unicode-aware: does not escape non-ASCII characters
    - Unicode-normalized: strings are NFKC normalized for consistency
    - Float-safe: rejects NaN and Infinity values

    Args:
        data: Any JSON-serializable data (dict, list, str, number, bool, None)

    Returns:
        Canonical JSON string suitable for hashing.

    Raises:
        ValueError: If data contains NaN, Infinity, or -Infinity values.

    Example:
        >>> canonical_json({"b": 1, "a": 2})
        '{"a":2,"b":1}'
    """
    # Sanitize data first (Unicode normalization, NaN/Infinity rejection)
    sanitized = _sanitize_for_json(data)

    return json.dumps(
        sanitized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_content_hash(event_data: dict[str, Any]) -> str:
    """Compute SHA-256 hash of event content.

    The hash covers the immutable content fields of an event:
    - event_type: Type classification of the event
    - payload: Structured event data (canonical JSON)
    - signature: Cryptographic signature of the event
    - witness_id: ID of the witness that attested the event
    - witness_signature: Signature of the witness
    - local_timestamp: Timestamp from the event source (ISO format)
    - agent_id: ID of agent (if present)

    EXCLUDED fields (would create circular dependencies or are DB-assigned):
    - prev_hash: References previous content_hash (circular)
    - content_hash: Self-reference (circular)
    - sequence: Assigned by database
    - authority_timestamp: Set by database
    - hash_alg_version: Metadata, not content
    - sig_alg_version: Metadata, not content

    Args:
        event_data: Dictionary containing event fields.

    Returns:
        Lowercase hexadecimal SHA-256 hash (64 characters).

    Example:
        >>> from datetime import datetime, timezone
        >>> event_data = {
        ...     "event_type": "test.event",
        ...     "payload": {"key": "value"},
        ...     "signature": "sig123",
        ...     "witness_id": "witness-001",
        ...     "witness_signature": "wsig123",
        ...     "local_timestamp": datetime(2025, 12, 27, tzinfo=timezone.utc),
        ... }
        >>> len(compute_content_hash(event_data))
        64
    """
    # Build hashable content from event fields
    # Convert local_timestamp to ISO format for consistent serialization
    local_ts = event_data["local_timestamp"]
    if isinstance(local_ts, datetime):
        local_ts_str = local_ts.isoformat()
    else:
        local_ts_str = str(local_ts)

    hashable: dict[str, Any] = {
        "event_type": event_data["event_type"],
        "payload": event_data["payload"],
        "signature": event_data["signature"],
        "witness_id": event_data["witness_id"],
        "witness_signature": event_data["witness_signature"],
        "local_timestamp": local_ts_str,
    }

    # Include agent_id only if present (system events may not have it)
    agent_id = event_data.get("agent_id")
    if agent_id is not None:
        hashable["agent_id"] = agent_id

    # Compute SHA-256 hash of canonical JSON
    canonical = canonical_json(hashable)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_valid_sha256_hex(value: str) -> bool:
    """Check if a string is a valid SHA-256 hexadecimal hash.

    Args:
        value: The string to validate.

    Returns:
        True if the string is a valid 64-character lowercase hexadecimal string.
    """
    if len(value) != 64:
        return False
    try:
        int(value, 16)
        return value == value.lower()  # Must be lowercase
    except ValueError:
        return False


def get_prev_hash(sequence: int, previous_content_hash: str | None) -> str:
    """Determine the prev_hash for an event based on its sequence.

    Args:
        sequence: The sequence number of the event being created.
        previous_content_hash: The content_hash of the previous event
            (sequence - 1). Required for sequence > 1. Must be a valid
            64-character lowercase hexadecimal string.

    Returns:
        The prev_hash to use:
        - GENESIS_HASH for sequence 1
        - previous_content_hash for sequence > 1

    Raises:
        ValueError: If sequence < 1, if sequence > 1 without previous_content_hash,
            or if previous_content_hash is not a valid SHA-256 hex string.

    Example:
        >>> get_prev_hash(1, None)  # First event
        '0000000000000000000000000000000000000000000000000000000000000000'
        >>> get_prev_hash(2, "abc123...")  # Subsequent event
        'abc123...'
    """
    if sequence < 1:
        raise ValueError("sequence must be >= 1")

    if sequence == 1:
        return GENESIS_HASH

    if previous_content_hash is None:
        raise ValueError("previous_content_hash required for sequence > 1")

    # Validate hash format (H4 fix: prevent invalid hash formats)
    if not _is_valid_sha256_hex(previous_content_hash):
        raise ValueError(
            f"previous_content_hash must be a 64-character lowercase hex string, "
            f"got: {previous_content_hash!r}"
        )

    return previous_content_hash
