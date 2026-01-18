"""Unit tests for KnightWitnessAdapter.

Tests the Furcas (Knight-Witness) service implementation per Government PRD:
- FR-GOV-19: Exists outside all branches, does not govern
- FR-GOV-20: Observe, record, publish, trigger acknowledgment
- FR-GOV-21: May NOT propose, debate, define execution, judge, enforce
- FR-GOV-22: Statements are append-only, non-binding, must be acknowledged
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.knight_witness import (
    AcknowledgmentRequest,
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatement,
    WitnessStatementType,
)
from src.infrastructure.adapters.witness.knight_witness_adapter import (
    KnightWitnessAdapter,
    create_knight_witness,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def adapter() -> KnightWitnessAdapter:
    """Create a KnightWitnessAdapter for testing."""
    return KnightWitnessAdapter(verbose=True)


@pytest.fixture
def observation_context() -> ObservationContext:
    """Create a sample observation context."""
    return ObservationContext(
        event_type="motion_proposed",
        event_id=uuid4(),
        description="King Paimon proposed a motion regarding data governance",
        participants=["Paimon", "Bael"],
        target_id="motion-123",
        target_type="motion",
        metadata={"round": 1},
    )


@pytest.fixture
def violation_record() -> ViolationRecord:
    """Create a sample violation record."""
    return ViolationRecord(
        violation_type="role_violation",
        violator_id=uuid4(),
        violator_name="Paimon",
        violator_rank="executive_director",
        description="King defined execution details (step 1, step 2...)",
        target_id="motion-123",
        target_type="motion",
        prd_reference="FR-GOV-6",
        requires_acknowledgment=True,
        metadata={"detected_patterns": ["step 1", "step 2"]},
    )


# =============================================================================
# TEST INITIALIZATION
# =============================================================================


class TestKnightWitnessAdapterInit:
    """Test adapter initialization."""

    def test_implements_protocol(self, adapter: KnightWitnessAdapter) -> None:
        """Verify adapter implements KnightWitnessProtocol."""
        assert isinstance(adapter, KnightWitnessProtocol)

    def test_factory_function_creates_adapter(self) -> None:
        """Test the factory function."""
        witness = create_knight_witness(verbose=True)
        assert isinstance(witness, KnightWitnessProtocol)
        assert isinstance(witness, KnightWitnessAdapter)

    def test_adapter_is_furcas(self, adapter: KnightWitnessAdapter) -> None:
        """Verify the witness is always Furcas."""
        # Create any statement and check witness field
        ctx = ObservationContext(
            event_type="session_start",
            event_id=uuid4(),
            description="Test",
            participants=[],
        )
        statement = adapter.observe(ctx)
        assert statement.witness == "furcas"


# =============================================================================
# TEST OBSERVE
# =============================================================================


class TestObserve:
    """Test the observe() method."""

    def test_observe_creates_statement(
        self,
        adapter: KnightWitnessAdapter,
        observation_context: ObservationContext,
    ) -> None:
        """Test that observe creates a witness statement."""
        statement = adapter.observe(observation_context)

        assert statement is not None
        assert isinstance(statement, WitnessStatement)
        assert statement.witness == "furcas"
        assert statement.description == observation_context.description
        assert statement.roles_involved == observation_context.participants
        assert statement.target_id == observation_context.target_id

    def test_observe_maps_event_types(self, adapter: KnightWitnessAdapter) -> None:
        """Test that event types are mapped to statement types."""
        test_cases = [
            ("session_start", WitnessStatementType.PROCEDURAL_START),
            ("session_end", WitnessStatementType.PROCEDURAL_END),
            ("motion_proposed", WitnessStatementType.MOTION_INTRODUCED),
            ("motion_passed", WitnessStatementType.MOTION_RATIFIED),
            ("motion_failed", WitnessStatementType.MOTION_FAILED),
        ]

        for event_type, expected_statement_type in test_cases:
            ctx = ObservationContext(
                event_type=event_type,
                event_id=uuid4(),
                description=f"Test {event_type}",
                participants=["Test"],
            )
            statement = adapter.observe(ctx)
            assert statement.statement_type == expected_statement_type, (
                f"Expected {expected_statement_type} for {event_type}, "
                f"got {statement.statement_type}"
            )

    def test_observe_stores_statement(
        self,
        adapter: KnightWitnessAdapter,
        observation_context: ObservationContext,
    ) -> None:
        """Test that observed statements are stored."""
        statement = adapter.observe(observation_context)

        retrieved = adapter.get_statement(statement.statement_id)
        assert retrieved is not None
        assert retrieved.statement_id == statement.statement_id


# =============================================================================
# TEST RECORD VIOLATION
# =============================================================================


class TestRecordViolation:
    """Test the record_violation() method."""

    def test_record_violation_creates_statement(
        self,
        adapter: KnightWitnessAdapter,
        violation_record: ViolationRecord,
    ) -> None:
        """Test that record_violation creates a witness statement."""
        statement = adapter.record_violation(violation_record)

        assert statement is not None
        assert isinstance(statement, WitnessStatement)
        assert statement.witness == "furcas"
        assert statement.statement_type == WitnessStatementType.ROLE_VIOLATION
        assert "VIOLATION" in statement.description
        assert violation_record.violator_name in statement.description

    def test_record_violation_includes_prd_reference(
        self,
        adapter: KnightWitnessAdapter,
        violation_record: ViolationRecord,
    ) -> None:
        """Test that PRD reference is included in metadata."""
        statement = adapter.record_violation(violation_record)

        assert statement.metadata.get("prd_reference") == "FR-GOV-6"

    def test_record_violation_tracks_in_violations_list(
        self,
        adapter: KnightWitnessAdapter,
        violation_record: ViolationRecord,
    ) -> None:
        """Test that violations are tracked."""
        statement = adapter.record_violation(violation_record)

        violations = adapter.get_violations()
        assert len(violations) == 1
        assert violations[0].statement_id == statement.statement_id

    def test_record_violation_creates_acknowledgment_request(
        self,
        adapter: KnightWitnessAdapter,
        violation_record: ViolationRecord,
    ) -> None:
        """Test that violations with acknowledgment required create requests."""
        statement = adapter.record_violation(violation_record)

        pending = adapter.get_pending_acknowledgments()
        assert len(pending) == 1
        assert pending[0].statement_id == statement.statement_id

    def test_branch_violation_type(self, adapter: KnightWitnessAdapter) -> None:
        """Test that branch violations get correct statement type."""
        violation = ViolationRecord(
            violation_type="branch_violation",
            violator_id=uuid4(),
            violator_name="Test",
            violator_rank="executive_director",
            description="Acted in multiple branches",
            requires_acknowledgment=False,
        )
        statement = adapter.record_violation(violation)
        assert statement.statement_type == WitnessStatementType.BRANCH_VIOLATION

    def test_sequence_violation_type(self, adapter: KnightWitnessAdapter) -> None:
        """Test that sequence violations get correct statement type."""
        violation = ViolationRecord(
            violation_type="sequence_violation",
            violator_id=uuid4(),
            violator_name="Test",
            violator_rank="director",
            description="Skipped governance step",
            requires_acknowledgment=False,
        )
        statement = adapter.record_violation(violation)
        assert statement.statement_type == WitnessStatementType.SEQUENCE_VIOLATION


# =============================================================================
# TEST PUBLISH STATEMENT
# =============================================================================


class TestPublishStatement:
    """Test the publish_statement() method."""

    def test_publish_returns_hash(
        self,
        adapter: KnightWitnessAdapter,
        observation_context: ObservationContext,
    ) -> None:
        """Test that publish_statement returns a hash reference."""
        statement = adapter.observe(observation_context)
        hash_ref = adapter.publish_statement(statement)

        assert hash_ref is not None
        assert isinstance(hash_ref, str)
        assert len(hash_ref) == 64  # SHA-256 hex

    def test_publish_updates_statement_hash_reference(
        self,
        adapter: KnightWitnessAdapter,
        observation_context: ObservationContext,
    ) -> None:
        """Test that publish updates the statement's hash reference."""
        statement = adapter.observe(observation_context)
        hash_ref = adapter.publish_statement(statement)

        # Retrieve the statement to check if hash_reference is updated
        retrieved = adapter.get_statement(statement.statement_id)
        assert retrieved is not None
        assert retrieved.hash_reference == hash_ref


# =============================================================================
# TEST ACKNOWLEDGMENT
# =============================================================================


class TestAcknowledgment:
    """Test acknowledgment functionality."""

    def test_trigger_acknowledgment(
        self,
        adapter: KnightWitnessAdapter,
        observation_context: ObservationContext,
    ) -> None:
        """Test triggering acknowledgment for a statement."""
        statement = adapter.observe(observation_context)
        request = adapter.trigger_acknowledgment(statement.statement_id)

        assert isinstance(request, AcknowledgmentRequest)
        assert request.statement_id == statement.statement_id
        assert request.acknowledged is False

    def test_trigger_acknowledgment_invalid_id_raises(
        self,
        adapter: KnightWitnessAdapter,
    ) -> None:
        """Test that invalid statement ID raises error."""
        with pytest.raises(ValueError, match="Statement not found"):
            adapter.trigger_acknowledgment(uuid4())

    def test_get_pending_acknowledgments(
        self,
        adapter: KnightWitnessAdapter,
        violation_record: ViolationRecord,
    ) -> None:
        """Test getting pending acknowledgments."""
        adapter.record_violation(violation_record)

        pending = adapter.get_pending_acknowledgments()
        assert len(pending) == 1
        assert pending[0].acknowledged is False

    def test_acknowledge_statement(
        self,
        adapter: KnightWitnessAdapter,
        violation_record: ViolationRecord,
    ) -> None:
        """Test acknowledging a statement."""
        statement = adapter.record_violation(violation_record)

        result = adapter.acknowledge_statement(
            statement.statement_id,
            acknowledged_by="conclave-session-123",
        )

        assert result is True

        # Check pending is now empty
        pending = adapter.get_pending_acknowledgments()
        assert len(pending) == 0

    def test_acknowledge_creates_acknowledgment_statement(
        self,
        adapter: KnightWitnessAdapter,
        violation_record: ViolationRecord,
    ) -> None:
        """Test that acknowledging creates a new witness statement."""
        statement = adapter.record_violation(violation_record)
        adapter.acknowledge_statement(statement.statement_id, "conclave")

        # Should have 2 statements: violation + acknowledgment
        statements = adapter.get_statements_by_target(
            str(statement.statement_id),
            "witness_statement",
        )
        assert len(statements) == 1
        assert (
            statements[0].statement_type == WitnessStatementType.ACKNOWLEDGMENT_RECEIVED
        )

    def test_acknowledge_invalid_id_returns_false(
        self,
        adapter: KnightWitnessAdapter,
    ) -> None:
        """Test that acknowledging invalid ID returns False."""
        result = adapter.acknowledge_statement(uuid4(), "conclave")
        assert result is False


# =============================================================================
# TEST QUERIES
# =============================================================================


class TestQueries:
    """Test query methods."""

    def test_get_statement(
        self,
        adapter: KnightWitnessAdapter,
        observation_context: ObservationContext,
    ) -> None:
        """Test retrieving a statement by ID."""
        statement = adapter.observe(observation_context)

        retrieved = adapter.get_statement(statement.statement_id)
        assert retrieved is not None
        assert retrieved.statement_id == statement.statement_id

    def test_get_statement_not_found(self, adapter: KnightWitnessAdapter) -> None:
        """Test retrieving non-existent statement."""
        result = adapter.get_statement(uuid4())
        assert result is None

    def test_get_statements_by_target(
        self,
        adapter: KnightWitnessAdapter,
    ) -> None:
        """Test getting statements by target ID."""
        target_id = "motion-456"

        # Create multiple statements for same target
        for i in range(3):
            ctx = ObservationContext(
                event_type="phase_change",
                event_id=uuid4(),
                description=f"Phase change {i}",
                participants=["Test"],
                target_id=target_id,
                target_type="motion",
            )
            adapter.observe(ctx)

        statements = adapter.get_statements_by_target(target_id)
        assert len(statements) == 3

    def test_get_statements_by_target_filters_type(
        self,
        adapter: KnightWitnessAdapter,
    ) -> None:
        """Test filtering by target type."""
        target_id = "mixed-target"

        # Create statements with different target types
        ctx1 = ObservationContext(
            event_type="session_start",
            event_id=uuid4(),
            description="Session start",
            participants=[],
            target_id=target_id,
            target_type="session",
        )
        adapter.observe(ctx1)

        ctx2 = ObservationContext(
            event_type="motion_proposed",
            event_id=uuid4(),
            description="Motion proposed",
            participants=[],
            target_id=target_id,
            target_type="motion",
        )
        adapter.observe(ctx2)

        # Filter by type
        session_statements = adapter.get_statements_by_target(target_id, "session")
        assert len(session_statements) == 1
        assert session_statements[0].target_type == "session"

    def test_get_violations_since(self, adapter: KnightWitnessAdapter) -> None:
        """Test filtering violations by time."""
        # Create old violation
        old_violation = ViolationRecord(
            violation_type="role_violation",
            violator_id=uuid4(),
            violator_name="Old",
            violator_rank="director",
            description="Old violation",
            requires_acknowledgment=False,
        )
        adapter.record_violation(old_violation)

        # Use 'since' filter
        since = datetime.now(timezone.utc) + timedelta(hours=1)
        violations = adapter.get_violations(since=since)
        assert len(violations) == 0

        # Without filter
        all_violations = adapter.get_violations()
        assert len(all_violations) == 1

    def test_get_violations_by_violator(self, adapter: KnightWitnessAdapter) -> None:
        """Test filtering violations by violator."""
        violator1_id = uuid4()
        violator2_id = uuid4()

        # Create violations from different violators
        v1 = ViolationRecord(
            violation_type="role_violation",
            violator_id=violator1_id,
            violator_name="Violator1",
            violator_rank="director",
            description="V1 violation",
            requires_acknowledgment=False,
        )
        adapter.record_violation(v1)

        v2 = ViolationRecord(
            violation_type="role_violation",
            violator_id=violator2_id,
            violator_name="Violator2",
            violator_rank="director",
            description="V2 violation",
            requires_acknowledgment=False,
        )
        adapter.record_violation(v2)

        # Filter by violator
        v1_violations = adapter.get_violations(violator_id=violator1_id)
        assert len(v1_violations) == 1
        assert v1_violations[0].roles_involved == ["Violator1"]


# =============================================================================
# TEST WITNESS STATEMENT MODEL
# =============================================================================


class TestWitnessStatementModel:
    """Test the WitnessStatement dataclass."""

    def test_create_statement(self) -> None:
        """Test creating a witness statement."""
        statement = WitnessStatement.create(
            statement_type=WitnessStatementType.PROCEDURAL_START,
            description="Session started",
            roles_involved=["Chair"],
            target_id="session-1",
            target_type="session",
        )

        assert statement.witness == "furcas"
        assert statement.statement_type == WitnessStatementType.PROCEDURAL_START
        assert statement.acknowledgment_required is False

    def test_statement_is_immutable(self) -> None:
        """Test that statements are frozen (immutable)."""
        statement = WitnessStatement.create(
            statement_type=WitnessStatementType.PROCEDURAL_START,
            description="Test",
            roles_involved=[],
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            statement.description = "Modified"  # type: ignore

    def test_statement_to_dict(self) -> None:
        """Test serialization to dict."""
        statement = WitnessStatement.create(
            statement_type=WitnessStatementType.ROLE_VIOLATION,
            description="Violation occurred",
            roles_involved=["Paimon"],
            target_id="motion-1",
            target_type="motion",
            acknowledgment_required=True,
        )

        d = statement.to_dict()

        assert d["witness"] == "furcas"
        assert d["type"] == "role_violation"
        assert d["description"] == "Violation occurred"
        assert d["roles_involved"] == ["Paimon"]
        assert d["acknowledgment_required"] is True
        assert "statement_id" in d
        assert "timestamp" in d


# =============================================================================
# TEST FR-GOV-21 COMPLIANCE (Knight Prohibitions)
# =============================================================================


class TestKnightProhibitions:
    """Test that Knight-Witness does NOT have prohibited methods.

    Per FR-GOV-21: Knight may NOT propose, debate, define_execution, judge, enforce.
    These methods should NOT exist on the adapter.
    """

    def test_no_propose_method(self, adapter: KnightWitnessAdapter) -> None:
        """Knight cannot propose motions."""
        assert not hasattr(adapter, "propose")
        assert not hasattr(adapter, "propose_motion")

    def test_no_debate_method(self, adapter: KnightWitnessAdapter) -> None:
        """Knight cannot debate."""
        assert not hasattr(adapter, "debate")
        assert not hasattr(adapter, "contribute_debate")

    def test_no_define_execution_method(self, adapter: KnightWitnessAdapter) -> None:
        """Knight cannot define execution."""
        assert not hasattr(adapter, "define_execution")
        assert not hasattr(adapter, "create_execution_plan")

    def test_no_judge_method(self, adapter: KnightWitnessAdapter) -> None:
        """Knight cannot judge."""
        assert not hasattr(adapter, "judge")
        assert not hasattr(adapter, "render_judgment")

    def test_no_enforce_method(self, adapter: KnightWitnessAdapter) -> None:
        """Knight cannot enforce."""
        assert not hasattr(adapter, "enforce")
        assert not hasattr(adapter, "enforce_consequence")
