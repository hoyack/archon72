"""Event signing utilities for constitutional event store (FR3, FR74).

This module provides functions for computing signable content and
converting signatures between bytes and base64 format.

Constitutional Constraints:
- FR3: Events must have agent attribution
- FR74: Invalid agent signatures must be rejected
- MA-2: Signature MUST cover prev_hash to bind signature to chain position

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Agent attribution creates verifiable authorship
- CT-13: Integrity outranks availability -> Reject invalid signatures, never degrade
"""

from __future__ import annotations

import base64
import json
from typing import Any

# Signature algorithm version (FR74)
# Version 1 = Ed25519
SIG_ALG_VERSION: int = 1
SIG_ALG_NAME: str = "Ed25519"


def compute_signable_content(
    content_hash: str,
    prev_hash: str,
    agent_id: str,
) -> bytes:
    """Compute the bytes to be signed for an event.

    CRITICAL: Includes prev_hash to bind signature to chain position (MA-2).
    This prevents an attacker from taking a valid event and inserting it
    at a different position in the chain without invalidating the signature.

    Args:
        content_hash: SHA-256 hash of event content.
        prev_hash: Hash of previous event (chain binding).
        agent_id: ID of agent creating the event.
            System agents use format "SYSTEM:{service_name}"
            (e.g., "SYSTEM:WATCHDOG").

    Returns:
        Canonical bytes representation for signing.
        Uses canonical JSON: sorted keys, no whitespace.

    Example:
        >>> content = compute_signable_content(
        ...     content_hash="abc123",
        ...     prev_hash="0" * 64,
        ...     agent_id="agent-001",
        ... )
        >>> isinstance(content, bytes)
        True
    """
    signable: dict[str, Any] = {
        "agent_id": agent_id,
        "content_hash": content_hash,
        "prev_hash": prev_hash,
    }
    # Canonical JSON: sorted keys, no whitespace
    canonical = json.dumps(signable, sort_keys=True, separators=(",", ":"))
    return canonical.encode("utf-8")


def signature_to_base64(signature: bytes) -> str:
    """Convert raw signature bytes to base64 string for storage.

    Ed25519 signatures are 64 bytes, which produces ~88 base64 characters.

    Args:
        signature: Raw signature bytes from HSM.

    Returns:
        Base64-encoded string suitable for database storage.

    Example:
        >>> sig_b64 = signature_to_base64(b"test")
        >>> isinstance(sig_b64, str)
        True
    """
    return base64.b64encode(signature).decode("ascii")


def signature_from_base64(signature_b64: str) -> bytes:
    """Convert base64 signature string back to bytes.

    Args:
        signature_b64: Base64-encoded signature from database.

    Returns:
        Raw signature bytes for verification.

    Raises:
        ValueError: If input is not valid base64.

    Example:
        >>> sig = signature_from_base64("dGVzdA==")
        >>> sig
        b'test'
    """
    return base64.b64decode(signature_b64)
