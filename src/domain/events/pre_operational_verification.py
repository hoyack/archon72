"""Pre-Operational Verification event payloads (Story 8.5, FR146, NFR35).

This module defines the event payloads for pre-operational verification:
- VerificationBypassedPayload: When bypass is used during startup (witnessed)
- PostHaltVerificationStartedPayload: When post-halt stringent verification begins

Constitutional Constraints:
- FR146: Startup SHALL execute verification checklist: hash chain, witness pool,
         Keeper keys, checkpoint anchors. Blocked until pass.
- NFR35: System startup SHALL complete verification checklist before operation.
- CT-12: Witnessing creates accountability → bypass MUST be witnessed
- CT-13: Integrity outranks availability → bypass is exceptional, must be logged

Developer Golden Rules:
1. WITNESS EVERYTHING - Bypass events MUST be witnessed for audit trail
2. FAIL LOUD - Never silently bypass verification
3. POST-HALT STRINGENT - Post-halt verification is non-bypassable
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

# Event type constants for pre-operational verification events
VERIFICATION_BYPASSED_EVENT_TYPE: str = "system.verification.bypassed"
POST_HALT_VERIFICATION_STARTED_EVENT_TYPE: str = "system.verification.post_halt_started"
VERIFICATION_PASSED_EVENT_TYPE: str = "system.verification.passed"
VERIFICATION_FAILED_EVENT_TYPE: str = "system.verification.failed"

# System agent ID for verification events (automated system, not human agent)
VERIFICATION_SYSTEM_AGENT_ID: str = "system.pre_operational_verification"


@dataclass(frozen=True, eq=True)
class VerificationBypassedPayload:
    """Payload for verification bypass events (FR146 MVP Note, CT-12).

    A VerificationBypassedPayload is created when pre-operational verification
    fails but bypass is allowed due to continuous restart scenarios.

    This event MUST be witnessed (CT-12) to create an audit trail of bypasses.
    Bypass is NOT allowed in post-halt recovery mode (CT-13).

    Constitutional Constraints:
    - FR146: Bypass allowed only for continuous restart, limited count/window
    - CT-12: Witnessing creates accountability -> bypass MUST be witnessed
    - CT-13: Integrity outranks availability -> bypass logs are critical evidence

    Attributes:
        bypass_id: Unique identifier for this bypass event.
        failed_checks: List of check names that failed.
        bypass_reason: Human-readable reason for allowing bypass.
        bypass_count: Number of bypasses in current window.
        bypass_window_seconds: Duration of the bypass window.
        max_bypasses_allowed: Maximum bypasses allowed in window.
        bypassed_at: When the bypass occurred (UTC).
    """

    bypass_id: UUID
    failed_checks: tuple[str, ...]
    bypass_reason: str
    bypass_count: int
    bypass_window_seconds: int
    max_bypasses_allowed: int
    bypassed_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "bypass_count": self.bypass_count,
            "bypass_id": str(self.bypass_id),
            "bypass_reason": self.bypass_reason,
            "bypass_window_seconds": self.bypass_window_seconds,
            "bypassed_at": self.bypassed_at.isoformat(),
            "failed_checks": list(self.failed_checks),
            "max_bypasses_allowed": self.max_bypasses_allowed,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "bypass_id": str(self.bypass_id),
            "failed_checks": list(self.failed_checks),
            "bypass_reason": self.bypass_reason,
            "bypass_count": self.bypass_count,
            "bypass_window_seconds": self.bypass_window_seconds,
            "max_bypasses_allowed": self.max_bypasses_allowed,
            "bypassed_at": self.bypassed_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class PostHaltVerificationStartedPayload:
    """Payload for post-halt verification start events (FR146, CT-13).

    A PostHaltVerificationStartedPayload is created when the system starts
    verification after recovering from a halt state.

    Post-halt verification is STRINGENT:
    - Full hash chain verification (not limited to last N events)
    - NO bypass allowed (CT-13: integrity outranks availability)
    - All checks must pass before operation resumes

    Constitutional Constraints:
    - FR146: Verification checklist required after halt
    - CT-13: Integrity outranks availability -> no bypass in post-halt
    - CT-12: Witnessing creates accountability -> event must be witnessed

    Attributes:
        verification_id: Unique identifier for this verification run.
        halt_reason: Why the system was halted.
        halt_cleared_at: When the halt was cleared (UTC).
        verification_started_at: When verification began (UTC).
        checks_to_run: List of verification checks to be executed.
    """

    verification_id: UUID
    halt_reason: str
    halt_cleared_at: datetime
    verification_started_at: datetime
    checks_to_run: tuple[str, ...] = field(
        default=(
            "halt_state",
            "hash_chain",
            "checkpoint_anchors",
            "keeper_keys",
            "witness_pool",
            "replica_sync",
        )
    )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "checks_to_run": list(self.checks_to_run),
            "halt_cleared_at": self.halt_cleared_at.isoformat(),
            "halt_reason": self.halt_reason,
            "verification_id": str(self.verification_id),
            "verification_started_at": self.verification_started_at.isoformat(),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "verification_id": str(self.verification_id),
            "halt_reason": self.halt_reason,
            "halt_cleared_at": self.halt_cleared_at.isoformat(),
            "verification_started_at": self.verification_started_at.isoformat(),
            "checks_to_run": list(self.checks_to_run),
        }


@dataclass(frozen=True, eq=True)
class VerificationCompletedPayload:
    """Payload for verification completion events (FR146, NFR35).

    A VerificationCompletedPayload is created when pre-operational verification
    completes, regardless of outcome (passed or failed).

    This event captures the full verification result for audit purposes.

    Constitutional Constraints:
    - FR146: Verification checklist execution is logged
    - NFR35: System startup verification is tracked
    - CT-12: Witnessing creates accountability -> must be witnessed

    Attributes:
        verification_id: Unique identifier for this verification run.
        status: Outcome status (passed, failed, bypassed).
        check_count: Total number of checks executed.
        failure_count: Number of failed checks.
        failed_check_names: Names of checks that failed.
        duration_ms: Total duration in milliseconds.
        is_post_halt: Whether this was post-halt stringent verification.
        completed_at: When verification completed (UTC).
    """

    verification_id: UUID
    status: str  # "passed", "failed", "bypassed"
    check_count: int
    failure_count: int
    failed_check_names: tuple[str, ...]
    duration_ms: float
    is_post_halt: bool
    completed_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "check_count": self.check_count,
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "failed_check_names": list(self.failed_check_names),
            "failure_count": self.failure_count,
            "is_post_halt": self.is_post_halt,
            "status": self.status,
            "verification_id": str(self.verification_id),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "verification_id": str(self.verification_id),
            "status": self.status,
            "check_count": self.check_count,
            "failure_count": self.failure_count,
            "failed_check_names": list(self.failed_check_names),
            "duration_ms": self.duration_ms,
            "is_post_halt": self.is_post_halt,
            "completed_at": self.completed_at.isoformat(),
        }
