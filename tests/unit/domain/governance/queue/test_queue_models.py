"""Unit tests for queue domain models.

Story: consent-gov-6-3: Witness Statement Routing

Tests:
- QueuePriority enum values
- QueueItemStatus enum values
- QueuedStatement immutability and methods
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.queue.priority import QueuePriority
from src.domain.governance.queue.status import QueueItemStatus
from src.domain.governance.queue.queued_statement import QueuedStatement
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.observation_content import ObservationContent
from src.domain.governance.witness.witness_statement import WitnessStatement


class TestQueuePriority:
    """Test QueuePriority enum."""

    def test_critical_priority_exists(self) -> None:
        """CRITICAL priority exists for integrity issues."""
        assert QueuePriority.CRITICAL.value == "critical"

    def test_high_priority_exists(self) -> None:
        """HIGH priority exists for consent/coercion violations."""
        assert QueuePriority.HIGH.value == "high"

    def test_medium_priority_exists(self) -> None:
        """MEDIUM priority exists for timing anomalies."""
        assert QueuePriority.MEDIUM.value == "medium"

    def test_low_priority_exists(self) -> None:
        """LOW priority exists for other violations."""
        assert QueuePriority.LOW.value == "low"

    def test_all_priorities_defined(self) -> None:
        """All four priority levels are defined."""
        priorities = list(QueuePriority)
        assert len(priorities) == 4


class TestQueueItemStatus:
    """Test QueueItemStatus enum."""

    def test_pending_status_exists(self) -> None:
        """PENDING status exists for new items."""
        assert QueueItemStatus.PENDING.value == "pending"

    def test_acknowledged_status_exists(self) -> None:
        """ACKNOWLEDGED status exists for operator acknowledgment."""
        assert QueueItemStatus.ACKNOWLEDGED.value == "acknowledged"

    def test_in_review_status_exists(self) -> None:
        """IN_REVIEW status exists for panel review."""
        assert QueueItemStatus.IN_REVIEW.value == "in_review"

    def test_resolved_status_exists(self) -> None:
        """RESOLVED status exists for completed items."""
        assert QueueItemStatus.RESOLVED.value == "resolved"

    def test_all_statuses_defined(self) -> None:
        """All four lifecycle statuses are defined."""
        statuses = list(QueueItemStatus)
        assert len(statuses) == 4


class TestQueuedStatement:
    """Test QueuedStatement domain model."""

    @pytest.fixture
    def sample_witness_statement(self) -> WitnessStatement:
        """Create a sample witness statement for testing."""
        return WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.POTENTIAL_VIOLATION,
            content=ObservationContent(
                what="Task activated without explicit consent",
                when=datetime(2026, 1, 17, 10, 30, tzinfo=timezone.utc),
                who=("actor-uuid-1",),  # Tuple per HARDENING-1 compliance
                where="executive.task_coordination",
                event_type="executive.task.activated",
                event_id=uuid4(),
            ),
            observed_at=datetime(2026, 1, 17, 10, 30, 1, tzinfo=timezone.utc),
            hash_chain_position=42,
        )

    @pytest.fixture
    def sample_queued_statement(
        self,
        sample_witness_statement: WitnessStatement,
    ) -> QueuedStatement:
        """Create a sample queued statement for testing."""
        return QueuedStatement(
            queue_item_id=uuid4(),
            statement_id=sample_witness_statement.statement_id,
            statement=sample_witness_statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=datetime(2026, 1, 17, 10, 31, tzinfo=timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )

    def test_queued_statement_creation(
        self,
        sample_queued_statement: QueuedStatement,
    ) -> None:
        """Queued statement can be created with all fields."""
        assert sample_queued_statement.queue_item_id is not None
        assert sample_queued_statement.statement_id is not None
        assert sample_queued_statement.statement is not None
        assert sample_queued_statement.priority == QueuePriority.HIGH
        assert sample_queued_statement.status == QueueItemStatus.PENDING
        assert sample_queued_statement.queued_at is not None
        assert sample_queued_statement.acknowledged_at is None
        assert sample_queued_statement.resolved_at is None
        assert sample_queued_statement.finding_id is None

    def test_queued_statement_is_frozen(
        self,
        sample_queued_statement: QueuedStatement,
    ) -> None:
        """Queued statement is immutable (frozen dataclass)."""
        with pytest.raises(Exception):  # FrozenInstanceError
            sample_queued_statement.status = QueueItemStatus.RESOLVED  # type: ignore

    def test_queued_statement_equality(
        self,
        sample_witness_statement: WitnessStatement,
    ) -> None:
        """Two queued statements with same data are equal."""
        queue_id = uuid4()
        now = datetime.now(timezone.utc)

        queued1 = QueuedStatement(
            queue_item_id=queue_id,
            statement_id=sample_witness_statement.statement_id,
            statement=sample_witness_statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=now,
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )

        queued2 = QueuedStatement(
            queue_item_id=queue_id,
            statement_id=sample_witness_statement.statement_id,
            statement=sample_witness_statement,
            priority=QueuePriority.HIGH,
            status=QueueItemStatus.PENDING,
            queued_at=now,
            acknowledged_at=None,
            resolved_at=None,
            finding_id=None,
        )

        assert queued1 == queued2

    def test_queued_statement_hash(
        self,
        sample_queued_statement: QueuedStatement,
    ) -> None:
        """Queued statement is hashable based on queue_item_id."""
        hash_value = hash(sample_queued_statement)
        assert hash_value == hash(sample_queued_statement.queue_item_id)

    def test_with_status_creates_new_instance(
        self,
        sample_queued_statement: QueuedStatement,
    ) -> None:
        """with_status creates a new instance with updated status."""
        ack_time = datetime(2026, 1, 17, 11, 0, tzinfo=timezone.utc)

        acknowledged = sample_queued_statement.with_status(
            new_status=QueueItemStatus.ACKNOWLEDGED,
            acknowledged_at=ack_time,
        )

        # Original unchanged
        assert sample_queued_statement.status == QueueItemStatus.PENDING
        assert sample_queued_statement.acknowledged_at is None

        # New instance has updated status
        assert acknowledged.status == QueueItemStatus.ACKNOWLEDGED
        assert acknowledged.acknowledged_at == ack_time

        # Other fields preserved
        assert acknowledged.queue_item_id == sample_queued_statement.queue_item_id
        assert acknowledged.statement_id == sample_queued_statement.statement_id
        assert acknowledged.priority == sample_queued_statement.priority
        assert acknowledged.queued_at == sample_queued_statement.queued_at

    def test_with_status_to_resolved(
        self,
        sample_queued_statement: QueuedStatement,
    ) -> None:
        """with_status can transition to RESOLVED with finding."""
        resolved_time = datetime(2026, 1, 17, 12, 0, tzinfo=timezone.utc)
        finding_id = uuid4()

        resolved = sample_queued_statement.with_status(
            new_status=QueueItemStatus.RESOLVED,
            resolved_at=resolved_time,
            finding_id=finding_id,
        )

        assert resolved.status == QueueItemStatus.RESOLVED
        assert resolved.resolved_at == resolved_time
        assert resolved.finding_id == finding_id

    def test_with_status_preserves_previous_values(
        self,
        sample_queued_statement: QueuedStatement,
    ) -> None:
        """with_status preserves existing timestamps if not overridden."""
        ack_time = datetime(2026, 1, 17, 11, 0, tzinfo=timezone.utc)

        # First transition to ACKNOWLEDGED
        acknowledged = sample_queued_statement.with_status(
            new_status=QueueItemStatus.ACKNOWLEDGED,
            acknowledged_at=ack_time,
        )

        # Then transition to IN_REVIEW (should preserve acknowledged_at)
        in_review = acknowledged.with_status(
            new_status=QueueItemStatus.IN_REVIEW,
        )

        assert in_review.status == QueueItemStatus.IN_REVIEW
        assert in_review.acknowledged_at == ack_time  # Preserved

    def test_queue_item_id_different_from_statement_id(
        self,
        sample_queued_statement: QueuedStatement,
    ) -> None:
        """Queue item ID is different from statement ID (can requeue same statement)."""
        assert (
            sample_queued_statement.queue_item_id
            != sample_queued_statement.statement_id
        )
