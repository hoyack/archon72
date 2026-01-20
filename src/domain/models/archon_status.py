"""Archon status enums for deliberation sessions (Story 2B.4, NFR-10.6).

This module defines the status tracking for Archons within a deliberation
session, enabling substitution when an Archon fails mid-deliberation.

Constitutional Constraints:
- AT-6: Deliberation is collective judgment, not unilateral decision
- CT-11: Silent failure destroys legitimacy - failures must be handled gracefully
- NFR-10.6: Archon substitution latency < 10 seconds on failure

Developer Golden Rules:
1. IMMUTABILITY - Enums are immutable
2. TRACEABILITY - Status changes must be recorded with reason
3. COMPLETENESS - All failure modes must be represented
"""

from __future__ import annotations

from enum import Enum


class ArchonStatus(str, Enum):
    """Status of an Archon within a deliberation session (Story 2B.4).

    Tracks the participation status of each assigned Archon during
    deliberation. Used for substitution tracking when failures occur.

    Constitutional Constraints:
    - AT-6: Exactly 3 ACTIVE Archons required for valid deliberation
    - CT-11: FAILED status must trigger substitution or abort

    Values:
        ACTIVE: Archon is actively participating in deliberation.
        FAILED: Archon failed and needs substitution.
        SUBSTITUTED: Archon was substituted (original is no longer active).
    """

    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    SUBSTITUTED = "SUBSTITUTED"

    def is_participating(self) -> bool:
        """Check if this status represents active participation.

        Returns:
            True if ACTIVE, False otherwise.
        """
        return self == ArchonStatus.ACTIVE

    def requires_substitution(self) -> bool:
        """Check if this status requires a substitution.

        Returns:
            True if FAILED, False otherwise.
        """
        return self == ArchonStatus.FAILED


class ArchonFailureReason(str, Enum):
    """Reasons an Archon may fail during deliberation (Story 2B.4, AC-1, AC-6).

    Categorizes failure modes for logging, metrics, and event emission.
    Each reason corresponds to specific detection logic in the adapter layer.

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy - reason must be recorded
    - NFR-10.2: Individual Archon response time p95 < 30 seconds

    Values:
        RESPONSE_TIMEOUT: Archon didn't respond within 30 seconds (NFR-10.2).
        API_ERROR: CrewAI or LLM API returned an error.
        INVALID_RESPONSE: Response couldn't be parsed or was malformed.
    """

    RESPONSE_TIMEOUT = "RESPONSE_TIMEOUT"
    API_ERROR = "API_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"

    def is_timeout(self) -> bool:
        """Check if this failure is due to timeout.

        Returns:
            True if RESPONSE_TIMEOUT, False otherwise.
        """
        return self == ArchonFailureReason.RESPONSE_TIMEOUT
