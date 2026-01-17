"""Port interface for Knight-Witness service (Furcas).

This module defines the abstract interface for the Knight-Witness service,
implementing the immutable observer role per Government PRD.

Per Government PRD §3.5: The Knight-Witness (Furcas) exists outside all branches.
Per Government PRD §5.1: Does not govern, makes governance visible.
Per Government PRD FR-GOV-19: Exists outside all branches; does not govern, makes governance visible.
Per Government PRD FR-GOV-20: Observe, record, publish, trigger acknowledgment.
Per Government PRD FR-GOV-21: May NOT propose, debate, define execution, judge, or enforce.
Per Government PRD FR-GOV-22: Witness statements are append-only, non-binding, must be acknowledged.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class WitnessStatementType(Enum):
    """Types of witness statements per Government PRD §5.4.

    These represent different categories of observations the Knight can record.
    """

    # Procedural observations
    PROCEDURAL_START = "procedural_start"  # Session/motion started
    PROCEDURAL_END = "procedural_end"  # Session/motion ended
    PROCEDURAL_TRANSITION = "procedural_transition"  # Phase change

    # Violation observations
    ROLE_VIOLATION = "role_violation"  # Archon exceeded jurisdiction
    BRANCH_VIOLATION = "branch_violation"  # Separation of powers violated
    SEQUENCE_VIOLATION = "sequence_violation"  # Governance flow broken

    # Governance observations
    MOTION_INTRODUCED = "motion_introduced"
    MOTION_RATIFIED = "motion_ratified"
    MOTION_FAILED = "motion_failed"
    VOTE_RECORDED = "vote_recorded"
    JUDGMENT_RENDERED = "judgment_rendered"

    # Administrative observations
    ACKNOWLEDGMENT_REQUIRED = "acknowledgment_required"
    ACKNOWLEDGMENT_RECEIVED = "acknowledgment_received"


@dataclass(frozen=True)
class WitnessStatement:
    """Immutable witness statement per Government PRD FR-GOV-22.

    Witness statements are:
    - Append-only (cannot be deleted)
    - Non-binding (observations, not orders)
    - Non-editable (immutable once created)
    - Must be acknowledged (not approved) by Conclave

    Attributes:
        statement_id: Unique identifier for this statement
        witness: Always "furcas" (the Knight-Witness)
        statement_type: Type of observation being recorded
        description: Human-readable description of what was witnessed
        roles_involved: List of Archons involved in the witnessed event
        target_id: Optional ID of the motion/task being witnessed
        target_type: Type of target (motion, task, session, etc.)
        metadata: Additional structured data about the observation
        acknowledgment_required: If True, must be acknowledged in next Conclave
        timestamp: When the observation was made (UTC)
        hash_reference: Optional reference to hash chain entry
    """

    statement_id: UUID
    witness: str  # Always "furcas"
    statement_type: WitnessStatementType
    description: str
    roles_involved: list[str]  # Archon names or IDs
    target_id: str | None = None
    target_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    acknowledgment_required: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    hash_reference: str | None = None  # Reference to hash chain entry

    @classmethod
    def create(
        cls,
        statement_type: WitnessStatementType,
        description: str,
        roles_involved: list[str],
        target_id: str | None = None,
        target_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        acknowledgment_required: bool = False,
    ) -> "WitnessStatement":
        """Create a new witness statement.

        Args:
            statement_type: Type of observation
            description: What was witnessed
            roles_involved: Archons involved
            target_id: Optional target ID
            target_type: Optional target type
            metadata: Additional data
            acknowledgment_required: If True, forces Conclave acknowledgment

        Returns:
            New immutable WitnessStatement
        """
        return cls(
            statement_id=uuid4(),
            witness="furcas",  # Always Furcas (the Knight-Witness)
            statement_type=statement_type,
            description=description,
            roles_involved=list(roles_involved),  # Defensive copy
            target_id=target_id,
            target_type=target_type,
            metadata=metadata or {},
            acknowledgment_required=acknowledgment_required,
            timestamp=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dict representation for storage/API
        """
        return {
            "statement_id": str(self.statement_id),
            "witness": self.witness,
            "type": self.statement_type.value,
            "description": self.description,
            "roles_involved": self.roles_involved,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "metadata": self.metadata,
            "acknowledgment_required": self.acknowledgment_required,
            "timestamp": self.timestamp.isoformat(),
            "hash_reference": self.hash_reference,
        }


@dataclass(frozen=True)
class ViolationRecord:
    """Record of a governance violation to be witnessed.

    This is the input to the Knight's violation recording function.
    """

    violation_type: str  # e.g., "role_violation", "branch_violation"
    violator_id: UUID
    violator_name: str
    violator_rank: str
    description: str
    target_id: str | None = None
    target_type: str | None = None
    prd_reference: str | None = None  # e.g., "FR-GOV-6"
    requires_acknowledgment: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservationContext:
    """Context for an observation to be witnessed.

    This is the input to the Knight's observe function.
    """

    event_type: str  # Type of event being observed
    event_id: UUID
    description: str
    participants: list[str]  # Archon names involved
    target_id: str | None = None
    target_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AcknowledgmentRequest:
    """Request for acknowledgment in Conclave.

    Represents a pending acknowledgment that must be addressed
    before Conclave can proceed per FR-GOV-22.
    """

    statement_id: UUID
    statement: WitnessStatement
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None  # Session ID or "conclave"


class KnightWitnessProtocol(ABC):
    """Abstract protocol for Knight-Witness service.

    Per Government PRD FR-GOV-19: The Knight-Witness exists outside all branches.
    The Knight does NOT govern - the Knight makes governance VISIBLE.

    This protocol EXPLICITLY INCLUDES (per FR-GOV-20):
    - observe(event): Observe governance events
    - record_violation(violation): Record procedural violations
    - publish_statement(statement): Publish immutable witness statements
    - trigger_acknowledgment(): Force acknowledgment in next Conclave

    This protocol EXPLICITLY EXCLUDES (per FR-GOV-21):
    - propose(): Knights may NOT propose motions
    - debate(): Knights may NOT debate intent
    - define_execution(): Knights may NOT define execution plans
    - judge(): Knights may NOT judge compliance
    - enforce(): Knights may NOT enforce consequences

    Implementation notes:
    - All statements are append-only (cannot be deleted)
    - All statements are non-editable (immutable)
    - Statements with acknowledgment_required=True must be acknowledged
    - Statements are non-binding (observations, not orders)
    """

    @abstractmethod
    def observe(self, context: ObservationContext) -> WitnessStatement:
        """Observe a governance event and create a witness statement.

        Per FR-GOV-20: Knight may observe all proceedings.

        Args:
            context: Context of the event being observed

        Returns:
            WitnessStatement recording the observation
        """
        ...

    @abstractmethod
    def record_violation(self, violation: ViolationRecord) -> WitnessStatement:
        """Record a procedural or role violation.

        Per FR-GOV-20: Knight may record procedural violations.

        Args:
            violation: Details of the violation

        Returns:
            WitnessStatement of type ROLE_VIOLATION or BRANCH_VIOLATION
        """
        ...

    @abstractmethod
    def publish_statement(self, statement: WitnessStatement) -> str:
        """Publish a witness statement to the immutable log.

        Per FR-GOV-20: Knight may publish immutable witness statements.
        Per FR-GOV-22: Statements are append-only and non-editable.

        Args:
            statement: The statement to publish

        Returns:
            Hash reference to the stored statement
        """
        ...

    @abstractmethod
    def trigger_acknowledgment(self, statement_id: UUID) -> AcknowledgmentRequest:
        """Trigger forced acknowledgment in next Conclave.

        Per FR-GOV-20: Knight may trigger forced acknowledgment.
        Per FR-GOV-22: Statements must be acknowledged (not approved) by Conclave.

        Args:
            statement_id: ID of statement requiring acknowledgment

        Returns:
            AcknowledgmentRequest for the Conclave
        """
        ...

    @abstractmethod
    def get_pending_acknowledgments(self) -> list[AcknowledgmentRequest]:
        """Get all statements pending acknowledgment.

        Per FR-GOV-22: Acknowledgments cannot be ignored.

        Returns:
            List of AcknowledgmentRequests for next Conclave
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def get_statement(self, statement_id: UUID) -> WitnessStatement | None:
        """Retrieve a witness statement by ID.

        Args:
            statement_id: The statement ID

        Returns:
            WitnessStatement if found, None otherwise
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...
