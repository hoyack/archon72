"""Witness routing service for routing statements to Prince Panel queue.

Story: consent-gov-6-3: Witness Statement Routing

This service routes witness statements to the appropriate queues based
on observation type. Not all statements are routed - only those requiring
review by the Prince Panel.

Routing Rules:
-------------
Observation Type       │ Route to Panel │ Priority
───────────────────────┼────────────────┼──────────
POTENTIAL_VIOLATION    │ Yes            │ Based on content
TIMING_ANOMALY         │ Yes            │ MEDIUM
HASH_CHAIN_GAP         │ Yes            │ CRITICAL
BRANCH_ACTION          │ No             │ N/A

Why not route all statements?
- BRANCH_ACTION is normal operation
- Panel would be overwhelmed with noise
- Panel reviews violations, not normal activity
- Normal activity still in ledger (auditable)

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All routing logged
- NFR-CONST-07: Statements cannot be suppressed

References:
    - FR35: System can route witness statements to Prince Panel queue
    - AC1: Statements routed to Prince Panel queue
    - AC3: Statements with POTENTIAL_VIOLATION type routed
    - AC4: Normal BRANCH_ACTION statements not queued for panel
    - AC5: Event judicial.witness.statement_queued emitted
    - AC6: Queue includes priority based on observation type
"""

from __future__ import annotations

from uuid import uuid4

from src.application.ports.governance.panel_queue_port import PanelQueuePort
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.queue.priority import QueuePriority
from src.domain.governance.queue.queued_statement import QueuedStatement
from src.domain.governance.queue.status import QueueItemStatus
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement

# Routing rules: which observation types get routed to panel
ROUTING_RULES: dict[ObservationType, bool] = {
    ObservationType.POTENTIAL_VIOLATION: True,  # Route - review needed
    ObservationType.TIMING_ANOMALY: True,  # Route - investigation needed
    ObservationType.HASH_CHAIN_GAP: True,  # Route - critical
    ObservationType.BRANCH_ACTION: False,  # Don't route - normal operation
}

# Keywords that indicate high-priority content
HIGH_PRIORITY_KEYWORDS: frozenset[str] = frozenset(
    [
        "consent",
        "coercion",
        "blocked",
        "violation",
        "unauthorized",
        "forbidden",
        "denied",
        "refused",
    ]
)


def determine_priority(statement: WitnessStatement) -> QueuePriority:
    """Determine queue priority for a witness statement.

    Priority is based on observation type and content analysis.
    This is routing logic, not judgment - it determines review order.

    Args:
        statement: The witness statement to prioritize.

    Returns:
        QueuePriority for this statement.
    """
    # Hash chain gaps are always CRITICAL (integrity issues)
    if statement.observation_type == ObservationType.HASH_CHAIN_GAP:
        return QueuePriority.CRITICAL

    # Check content for high-priority keywords
    content_lower = statement.content.what.lower()
    if any(keyword in content_lower for keyword in HIGH_PRIORITY_KEYWORDS):
        return QueuePriority.HIGH

    # Timing anomalies are MEDIUM priority
    if statement.observation_type == ObservationType.TIMING_ANOMALY:
        return QueuePriority.MEDIUM

    # Default for other potential violations
    return QueuePriority.LOW


class WitnessRoutingService:
    """Routes witness statements to Prince Panel queue.

    This service determines which witness statements require panel
    review and routes them to the appropriate queue with the
    correct priority.

    Not all statements are routed - only those that may indicate
    violations or anomalies. Normal branch actions are NOT routed
    to prevent panel overwhelm.

    Example:
        >>> service = WitnessRoutingService(
        ...     panel_queue=queue_adapter,
        ...     event_emitter=emitter,
        ...     time_authority=time_service,
        ... )
        >>> # Violation statement - will be queued
        >>> queued = await service.route_statement(violation_statement)
        >>> assert queued is True
        >>> # Normal action - will NOT be queued
        >>> queued = await service.route_statement(branch_action)
        >>> assert queued is False
    """

    def __init__(
        self,
        panel_queue: PanelQueuePort,
        event_emitter: TwoPhaseEventEmitterPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the routing service.

        Args:
            panel_queue: Port for panel queue operations.
            event_emitter: Port for emitting governance events.
            time_authority: Port for consistent timestamps.
        """
        self._queue = panel_queue
        self._event_emitter = event_emitter
        self._time = time_authority

    async def route_statement(
        self,
        statement: WitnessStatement,
    ) -> bool:
        """Route a witness statement to panel queue if needed.

        Evaluates the statement against routing rules and queues
        it for panel review if applicable. Emits events for all
        routing decisions (for Knight observability).

        Args:
            statement: The witness statement to route.

        Returns:
            True if statement was queued, False if not routed.

        Note:
            BRANCH_ACTION statements are NOT queued (normal operations).
            Only potential violations, timing anomalies, and hash chain
            gaps are routed to the panel.
        """
        # Check routing rules
        should_route = ROUTING_RULES.get(statement.observation_type, False)

        if not should_route:
            # Not routing - normal operation, no event needed
            return False

        # Determine priority
        priority = determine_priority(statement)

        # Create queue item
        now = self._time.utcnow()
        queue_item_id = uuid4()

        queued_statement = QueuedStatement(
            queue_item_id=queue_item_id,
            statement_id=statement.statement_id,
            statement=statement,
            priority=priority,
            status=QueueItemStatus.PENDING,
            queued_at=now,
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )

        # Two-phase: emit intent
        correlation_id = await self._event_emitter.emit_intent(
            operation_type="judicial.witness.queue_statement",
            actor_id="witness_router",
            target_entity_id=str(statement.statement_id),
            intent_payload={
                "queue_item_id": str(queue_item_id),
                "statement_id": str(statement.statement_id),
                "observation_type": statement.observation_type.value,
                "priority": priority.value,
            },
        )

        try:
            # Enqueue the statement
            await self._queue.enqueue_statement(queued_statement)

            # Two-phase: emit commit with queued event details
            await self._event_emitter.emit_commit(
                correlation_id=correlation_id,
                result_payload={
                    "event_type": "judicial.witness.statement_queued",
                    "queue_item_id": str(queue_item_id),
                    "statement_id": str(statement.statement_id),
                    "observation_type": statement.observation_type.value,
                    "priority": priority.value,
                    "queued_at": now.isoformat(),
                },
            )

            return True

        except Exception as e:
            # Two-phase: emit failure
            await self._event_emitter.emit_failure(
                correlation_id=correlation_id,
                failure_reason="QUEUE_FAILED",
                failure_details={
                    "error": str(e),
                    "queue_item_id": str(queue_item_id),
                    "statement_id": str(statement.statement_id),
                },
            )
            raise

    def should_route(self, observation_type: ObservationType) -> bool:
        """Check if an observation type should be routed to panel.

        Convenience method for checking routing rules without
        actually routing a statement.

        Args:
            observation_type: The observation type to check.

        Returns:
            True if statements of this type are routed.
        """
        return ROUTING_RULES.get(observation_type, False)

    def get_priority_for_type(
        self,
        observation_type: ObservationType,
    ) -> QueuePriority | None:
        """Get default priority for an observation type.

        Returns the base priority for an observation type without
        considering content analysis.

        Args:
            observation_type: The observation type.

        Returns:
            Default priority, or None if type is not routed.
        """
        if not self.should_route(observation_type):
            return None

        if observation_type == ObservationType.HASH_CHAIN_GAP:
            return QueuePriority.CRITICAL
        if observation_type == ObservationType.TIMING_ANOMALY:
            return QueuePriority.MEDIUM
        return QueuePriority.LOW
