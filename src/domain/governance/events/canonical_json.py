"""Canonical JSON serialization for governance events.

Story: consent-gov-1.3: Hash Chain Implementation

This module provides deterministic JSON serialization for governance events
to ensure consistent hashing across all systems. Canonical JSON guarantees
that the same data structure always produces the same JSON string.

Canonical JSON Rules:
1. Keys sorted alphabetically (recursive)
2. No extra whitespace between elements
3. No trailing newlines
4. Datetime serialized as ISO-8601 UTC string
5. UUID serialized as lowercase string with dashes
6. Unicode strings normalized to NFKC form
7. NaN/Infinity floats rejected (not valid JSON)

Constitutional Constraints:
- NFR-AUDIT-06: Deterministic replay requires reproducible serialization
- AD-6: Hash computation depends on canonical serialization

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Hash Chain Implementation (Locked)]
"""

from __future__ import annotations

import json
import math
import unicodedata
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize values for canonical JSON serialization.

    This function:
    - Normalizes Unicode strings to NFKC form
    - Converts datetime to ISO-8601 UTC string
    - Converts UUID to lowercase string with dashes
    - Rejects NaN, Infinity, and -Infinity floats
    - Recursively processes nested structures

    Args:
        value: Any JSON-serializable value.

    Returns:
        Sanitized value safe for canonical JSON serialization.

    Raises:
        ConstitutionalViolationError: If value contains non-finite floats.
    """
    if isinstance(value, str):
        # Normalize Unicode to NFKC form for consistent representation
        return unicodedata.normalize("NFKC", value)

    elif isinstance(value, datetime):
        # Convert to ISO-8601 UTC string
        return value.isoformat()

    elif isinstance(value, UUID):
        # Convert UUID to lowercase string with dashes
        return str(value).lower()

    elif isinstance(value, float):
        # Reject non-finite floats (NaN, Infinity, -Infinity)
        if math.isnan(value) or math.isinf(value):
            raise ConstitutionalViolationError(
                f"NFR-AUDIT-06: Cannot serialize non-finite float value: {value!r}. "
                "NaN and Infinity are not valid JSON for deterministic serialization."
            )
        return value

    elif isinstance(value, dict):
        # Recursively sanitize dict values
        return {_sanitize_value(k): _sanitize_value(v) for k, v in value.items()}

    elif isinstance(value, (list, tuple)):
        # Recursively sanitize list/tuple items
        return [_sanitize_value(item) for item in value]

    elif isinstance(value, bytes):
        # Convert bytes to hex string for JSON compatibility
        return value.hex()

    else:
        # Pass through other JSON-native types (int, bool, None)
        return value


def canonical_json(data: dict[str, Any]) -> str:
    """Produce deterministic JSON representation for hashing.

    This function creates a canonical JSON string that is:
    - Deterministic: same input always produces same output
    - Sorted: keys are sorted alphabetically (recursive)
    - Compact: no whitespace between elements
    - Unicode-normalized: strings are NFKC normalized
    - Type-aware: datetime and UUID converted to strings

    Args:
        data: Dictionary to serialize.

    Returns:
        Canonical JSON string suitable for hashing.

    Raises:
        ConstitutionalViolationError: If data contains non-serializable values.

    Example:
        >>> canonical_json({"b": 1, "a": 2})
        '{"a":2,"b":1}'
        >>> canonical_json({"z": {"y": 1, "x": 2}})
        '{"z":{"x":2,"y":1}}'
    """
    try:
        sanitized = _sanitize_value(data)
        return json.dumps(
            sanitized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as e:
        raise ConstitutionalViolationError(
            f"NFR-AUDIT-06: Failed to produce canonical JSON: {e}"
        ) from e


def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    """Produce deterministic JSON bytes for hashing.

    Convenience wrapper that returns UTF-8 encoded bytes
    suitable for direct use with hash functions.

    Args:
        data: Dictionary to serialize.

    Returns:
        UTF-8 encoded canonical JSON bytes.

    Raises:
        ConstitutionalViolationError: If data contains non-serializable values.
    """
    return canonical_json(data).encode("utf-8")
