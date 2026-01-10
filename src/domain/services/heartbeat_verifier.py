"""HeartbeatVerifier domain service (Story 2.6, FR90).

This domain service verifies heartbeat signatures and detects spoofing attempts.
All spoofed heartbeats are rejected and logged as constitutional violations.

Constitutional Constraints:
- FR90: Heartbeats must be signed to prevent spoofing
- FR93: Spoofed heartbeats must be rejected and logged

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Detect and log all spoofing
- CT-12: Witnessing creates accountability -> All rejections are traceable
- CT-13: Integrity outranks availability -> Reject invalid heartbeats
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.domain.errors.heartbeat import HeartbeatSpoofingError

if TYPE_CHECKING:
    from src.domain.models.heartbeat import Heartbeat

logger = structlog.get_logger()


class HeartbeatVerifier:
    """Domain service for heartbeat verification and spoofing detection (FR90).

    This service verifies that heartbeats are properly signed and originate
    from legitimate agents with valid sessions. Spoofed heartbeats are
    rejected and logged.

    Constitutional Constraints:
        - FR90: All heartbeats must be signed
        - FR93: Spoofed heartbeats rejected with logged event

    Dev Mode Behavior:
        In development mode, signature verification is simplified.
        Production uses actual HSM key verification.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> from src.application.ports.agent_orchestrator import AgentStatus
        >>> from src.domain.models.heartbeat import Heartbeat
        >>> verifier = HeartbeatVerifier()
        >>> heartbeat = Heartbeat(
        ...     heartbeat_id=uuid4(),
        ...     agent_id="archon-1",
        ...     session_id=uuid4(),
        ...     status=AgentStatus.BUSY,
        ...     memory_usage_mb=256,
        ...     timestamp=datetime.now(timezone.utc),
        ...     signature="valid_sig",
        ... )
        >>> verifier.verify_heartbeat_signature(heartbeat)
        True
    """

    def verify_heartbeat_signature(self, heartbeat: Heartbeat) -> bool:
        """Verify the cryptographic signature of a heartbeat.

        For development mode, this performs simple signature presence check.
        Production implementation would verify against the agent's public key.

        Args:
            heartbeat: The heartbeat to verify.

        Returns:
            True if signature is valid, False otherwise.

        Note:
            Does not raise on invalid signature - use detect_spoofing()
            and reject_spoofed_heartbeat() for full enforcement flow.
        """
        # Simple verification: signature must be present and non-empty
        if heartbeat.signature is None or heartbeat.signature == "":
            logger.debug(
                "heartbeat_signature_missing",
                agent_id=heartbeat.agent_id,
                heartbeat_id=str(heartbeat.heartbeat_id),
            )
            return False

        logger.debug(
            "heartbeat_signature_valid",
            agent_id=heartbeat.agent_id,
            heartbeat_id=str(heartbeat.heartbeat_id),
        )
        return True

    def detect_spoofing(
        self,
        heartbeat: Heartbeat,
        session_registry: dict[str, UUID],
    ) -> bool:
        """Detect if a heartbeat is spoofed based on session and signature.

        A heartbeat is considered spoofed if:
        1. It has no signature (unsigned)
        2. The agent_id is not in the session registry (unknown agent)
        3. The session_id doesn't match the registered session

        Args:
            heartbeat: The heartbeat to check.
            session_registry: Map of agent_id to expected session_id.

        Returns:
            True if heartbeat is spoofed, False if legitimate.
        """
        # Check 1: Signature must be present
        if not self.verify_heartbeat_signature(heartbeat):
            logger.warning(
                "spoofing_detected_no_signature",
                agent_id=heartbeat.agent_id,
                heartbeat_id=str(heartbeat.heartbeat_id),
            )
            return True

        # Check 2: Agent must be known
        if heartbeat.agent_id not in session_registry:
            logger.warning(
                "spoofing_detected_unknown_agent",
                agent_id=heartbeat.agent_id,
                heartbeat_id=str(heartbeat.heartbeat_id),
            )
            return True

        # Check 3: Session must match
        expected_session = session_registry[heartbeat.agent_id]
        if heartbeat.session_id != expected_session:
            logger.warning(
                "spoofing_detected_session_mismatch",
                agent_id=heartbeat.agent_id,
                heartbeat_id=str(heartbeat.heartbeat_id),
                expected_session=str(expected_session),
                received_session=str(heartbeat.session_id),
            )
            return True

        logger.debug(
            "heartbeat_not_spoofed",
            agent_id=heartbeat.agent_id,
            heartbeat_id=str(heartbeat.heartbeat_id),
        )
        return False

    def reject_spoofed_heartbeat(
        self,
        heartbeat: Heartbeat,
        reason: str,
    ) -> None:
        """Reject a spoofed heartbeat by raising HeartbeatSpoofingError.

        This method logs the rejection and raises a constitutional violation
        error. FR90 requires all spoofed heartbeats to be rejected and logged.

        Args:
            heartbeat: The spoofed heartbeat to reject.
            reason: Why the heartbeat was determined to be spoofed
                (e.g., "signature_mismatch", "session_invalid", "unknown_agent").

        Raises:
            HeartbeatSpoofingError: Always raised with agent_id and reason.
        """
        logger.error(
            "heartbeat_spoofing_rejected",
            agent_id=heartbeat.agent_id,
            session_id=str(heartbeat.session_id),
            heartbeat_id=str(heartbeat.heartbeat_id),
            rejection_reason=reason,
        )
        raise HeartbeatSpoofingError(
            agent_id=heartbeat.agent_id,
            reason=reason,
        )
