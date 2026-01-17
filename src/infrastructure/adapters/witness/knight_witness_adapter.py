"""Knight-Witness Adapter implementation.

This adapter implements the KnightWitnessProtocol, providing the immutable
observer functionality for the governance system.

Per Government PRD §3.5: Knight-Witness (Furcas) exists outside all branches.
Per Government PRD §5: The Knight observes and records but does not govern.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.knight_witness import (
    AcknowledgmentRequest,
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatement,
    WitnessStatementType,
)

logger = get_logger(__name__)


class KnightWitnessAdapter(KnightWitnessProtocol):
    """Adapter implementing Knight-Witness (Furcas) functionality.

    This implementation:
    1. Creates immutable witness statements for all observations
    2. Records violations with appropriate severity
    3. Manages acknowledgment requests for Conclave
    4. Integrates with hash chain for tamper-evident storage

    Per Government PRD NFR-GOV-4: Witnessing must be instantaneous.
    Per Government PRD NFR-GOV-8: Knight must be independently verifiable.

    Note: This is an in-memory implementation. For production, integrate
    with the event store (Story 7.5) for persistence.
    """

    def __init__(
        self,
        event_store: Any | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the Knight-Witness adapter.

        Args:
            event_store: Optional event store for persistence (Story 7.5)
            verbose: Enable verbose logging
        """
        self._verbose = verbose
        self._event_store = event_store

        # In-memory storage (to be replaced with event store integration)
        self._statements: dict[UUID, WitnessStatement] = {}
        self._statements_by_target: dict[str, list[UUID]] = defaultdict(list)
        self._pending_acknowledgments: dict[UUID, AcknowledgmentRequest] = {}
        self._violations: list[UUID] = []  # Track violation statement IDs

        logger.info(
            "knight_witness_initialized",
            witness="furcas",
            has_event_store=event_store is not None,
        )

    def observe(self, context: ObservationContext) -> WitnessStatement:
        """Observe a governance event and create a witness statement.

        Per FR-GOV-20: Knight may observe all proceedings.

        Args:
            context: Context of the event being observed

        Returns:
            WitnessStatement recording the observation
        """
        # Map event type to statement type
        statement_type = self._map_event_to_statement_type(context.event_type)

        statement = WitnessStatement.create(
            statement_type=statement_type,
            description=context.description,
            roles_involved=context.participants,
            target_id=context.target_id,
            target_type=context.target_type,
            metadata={
                "event_id": str(context.event_id),
                "event_type": context.event_type,
                **context.metadata,
            },
            acknowledgment_required=False,  # Most observations don't require ack
        )

        # Store the statement
        self._store_statement(statement)

        if self._verbose:
            logger.debug(
                "observation_recorded",
                statement_id=str(statement.statement_id),
                event_type=context.event_type,
                participants=context.participants,
            )

        return statement

    def record_violation(self, violation: ViolationRecord) -> WitnessStatement:
        """Record a procedural or role violation.

        Per FR-GOV-20: Knight may record procedural violations.
        Per Government PRD: Violations MUST be witnessed and visible.

        Args:
            violation: Details of the violation

        Returns:
            WitnessStatement of type ROLE_VIOLATION or BRANCH_VIOLATION
        """
        # Determine statement type based on violation type
        if "branch" in violation.violation_type.lower():
            statement_type = WitnessStatementType.BRANCH_VIOLATION
        elif "sequence" in violation.violation_type.lower():
            statement_type = WitnessStatementType.SEQUENCE_VIOLATION
        else:
            statement_type = WitnessStatementType.ROLE_VIOLATION

        # Build description
        description = (
            f"VIOLATION: {violation.violator_name} ({violation.violator_rank}) "
            f"committed {violation.violation_type}: {violation.description}"
        )

        statement = WitnessStatement.create(
            statement_type=statement_type,
            description=description,
            roles_involved=[violation.violator_name],
            target_id=violation.target_id,
            target_type=violation.target_type,
            metadata={
                "violator_id": str(violation.violator_id),
                "violator_rank": violation.violator_rank,
                "violation_type": violation.violation_type,
                "prd_reference": violation.prd_reference,
                **violation.metadata,
            },
            acknowledgment_required=violation.requires_acknowledgment,
        )

        # Store the statement
        self._store_statement(statement)
        self._violations.append(statement.statement_id)

        # If acknowledgment required, create request
        if violation.requires_acknowledgment:
            self._create_acknowledgment_request(statement)

        logger.warning(
            "violation_witnessed",
            statement_id=str(statement.statement_id),
            violator=violation.violator_name,
            violation_type=violation.violation_type,
            prd_reference=violation.prd_reference,
            acknowledgment_required=violation.requires_acknowledgment,
        )

        return statement

    def publish_statement(self, statement: WitnessStatement) -> str:
        """Publish a witness statement to the immutable log.

        Per FR-GOV-20: Knight may publish immutable witness statements.
        Per FR-GOV-22: Statements are append-only and non-editable.

        Args:
            statement: The statement to publish

        Returns:
            Hash reference to the stored statement
        """
        # For now, generate a simple hash reference
        # In production, this integrates with the hash chain (Story 7.5)
        import hashlib

        statement_json = str(statement.to_dict()).encode()
        hash_ref = hashlib.sha256(statement_json).hexdigest()

        # Store with hash reference
        # Note: Since WitnessStatement is frozen, we create a new one with the hash
        updated_statement = WitnessStatement(
            statement_id=statement.statement_id,
            witness=statement.witness,
            statement_type=statement.statement_type,
            description=statement.description,
            roles_involved=statement.roles_involved,
            target_id=statement.target_id,
            target_type=statement.target_type,
            metadata=statement.metadata,
            acknowledgment_required=statement.acknowledgment_required,
            timestamp=statement.timestamp,
            hash_reference=hash_ref,
        )

        self._statements[statement.statement_id] = updated_statement

        logger.info(
            "statement_published",
            statement_id=str(statement.statement_id),
            hash_reference=hash_ref[:16] + "...",
            statement_type=statement.statement_type.value,
        )

        return hash_ref

    def trigger_acknowledgment(self, statement_id: UUID) -> AcknowledgmentRequest:
        """Trigger forced acknowledgment in next Conclave.

        Per FR-GOV-20: Knight may trigger forced acknowledgment.
        Per FR-GOV-22: Statements must be acknowledged (not approved) by Conclave.

        Args:
            statement_id: ID of statement requiring acknowledgment

        Returns:
            AcknowledgmentRequest for the Conclave
        """
        statement = self._statements.get(statement_id)
        if not statement:
            raise ValueError(f"Statement not found: {statement_id}")

        request = AcknowledgmentRequest(
            statement_id=statement_id,
            statement=statement,
            requested_at=datetime.now(timezone.utc),
        )

        self._pending_acknowledgments[statement_id] = request

        logger.info(
            "acknowledgment_triggered",
            statement_id=str(statement_id),
            statement_type=statement.statement_type.value,
        )

        return request

    def get_pending_acknowledgments(self) -> list[AcknowledgmentRequest]:
        """Get all statements pending acknowledgment.

        Per FR-GOV-22: Acknowledgments cannot be ignored.

        Returns:
            List of AcknowledgmentRequests for next Conclave
        """
        return [
            req
            for req in self._pending_acknowledgments.values()
            if not req.acknowledged
        ]

    def acknowledge_statement(
        self,
        statement_id: UUID,
        acknowledged_by: str,
    ) -> bool:
        """Mark a statement as acknowledged.

        Note: Acknowledgment is NOT approval. The Conclave acknowledges
        they have seen the statement, not that they agree with it.

        Args:
            statement_id: ID of statement to acknowledge
            acknowledged_by: Who acknowledged (session ID or "conclave")

        Returns:
            True if acknowledgment recorded, False if statement not found
        """
        request = self._pending_acknowledgments.get(statement_id)
        if not request:
            return False

        # Update the request (AcknowledgmentRequest is mutable)
        request.acknowledged = True
        request.acknowledged_at = datetime.now(timezone.utc)
        request.acknowledged_by = acknowledged_by

        logger.info(
            "statement_acknowledged",
            statement_id=str(statement_id),
            acknowledged_by=acknowledged_by,
        )

        # Create a witness statement about the acknowledgment
        ack_statement = WitnessStatement.create(
            statement_type=WitnessStatementType.ACKNOWLEDGMENT_RECEIVED,
            description=f"Statement {statement_id} acknowledged by {acknowledged_by}",
            roles_involved=[acknowledged_by],
            target_id=str(statement_id),
            target_type="witness_statement",
            metadata={
                "original_statement_type": request.statement.statement_type.value,
            },
            acknowledgment_required=False,
        )
        self._store_statement(ack_statement)

        return True

    def get_statement(self, statement_id: UUID) -> WitnessStatement | None:
        """Retrieve a witness statement by ID.

        Args:
            statement_id: The statement ID

        Returns:
            WitnessStatement if found, None otherwise
        """
        return self._statements.get(statement_id)

    def get_statements_by_target(
        self,
        target_id: str,
        target_type: str | None = None,
    ) -> list[WitnessStatement]:
        """Get all witness statements for a target.

        Args:
            target_id: The target ID (motion ID, task ID, etc.)
            target_type: Optional filter by target type

        Returns:
            List of WitnessStatements for the target
        """
        statement_ids = self._statements_by_target.get(target_id, [])
        statements = [self._statements[sid] for sid in statement_ids if sid in self._statements]

        if target_type:
            statements = [s for s in statements if s.target_type == target_type]

        return statements

    def get_violations(
        self,
        since: datetime | None = None,
        violator_id: UUID | None = None,
    ) -> list[WitnessStatement]:
        """Get violation witness statements.

        Args:
            since: Optional filter for statements after this time
            violator_id: Optional filter for specific violator

        Returns:
            List of violation WitnessStatements
        """
        violations = [self._statements[sid] for sid in self._violations if sid in self._statements]

        if since:
            violations = [v for v in violations if v.timestamp >= since]

        if violator_id:
            violator_str = str(violator_id)
            violations = [
                v for v in violations
                if v.metadata.get("violator_id") == violator_str
            ]

        return violations

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _store_statement(self, statement: WitnessStatement) -> None:
        """Store a witness statement in memory.

        Args:
            statement: The statement to store
        """
        self._statements[statement.statement_id] = statement

        if statement.target_id:
            self._statements_by_target[statement.target_id].append(statement.statement_id)

    def _create_acknowledgment_request(self, statement: WitnessStatement) -> None:
        """Create an acknowledgment request for a statement.

        Args:
            statement: The statement requiring acknowledgment
        """
        request = AcknowledgmentRequest(
            statement_id=statement.statement_id,
            statement=statement,
            requested_at=datetime.now(timezone.utc),
        )
        self._pending_acknowledgments[statement.statement_id] = request

    def _map_event_to_statement_type(self, event_type: str) -> WitnessStatementType:
        """Map an event type string to a WitnessStatementType.

        Args:
            event_type: The event type string

        Returns:
            Corresponding WitnessStatementType
        """
        mapping = {
            "session_start": WitnessStatementType.PROCEDURAL_START,
            "session_end": WitnessStatementType.PROCEDURAL_END,
            "phase_change": WitnessStatementType.PROCEDURAL_TRANSITION,
            "motion_proposed": WitnessStatementType.MOTION_INTRODUCED,
            "motion_passed": WitnessStatementType.MOTION_RATIFIED,
            "motion_failed": WitnessStatementType.MOTION_FAILED,
            "vote_cast": WitnessStatementType.VOTE_RECORDED,
            "judgment": WitnessStatementType.JUDGMENT_RENDERED,
            "role_violation": WitnessStatementType.ROLE_VIOLATION,
            "branch_violation": WitnessStatementType.BRANCH_VIOLATION,
            "sequence_violation": WitnessStatementType.SEQUENCE_VIOLATION,
        }
        return mapping.get(event_type, WitnessStatementType.PROCEDURAL_TRANSITION)


def create_knight_witness(
    event_store: Any | None = None,
    verbose: bool = False,
) -> KnightWitnessProtocol:
    """Factory function to create a KnightWitnessProtocol instance.

    Args:
        event_store: Optional event store for persistence
        verbose: Enable verbose logging

    Returns:
        Configured KnightWitnessProtocol instance
    """
    return KnightWitnessAdapter(event_store=event_store, verbose=verbose)
