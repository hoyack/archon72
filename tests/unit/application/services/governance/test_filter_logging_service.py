"""Unit tests for FilterLoggingService.

Story: consent-gov-3.3: Filter Decision Logging

Tests:
- AC1: All decisions logged with input, output, version, timestamp
- AC3: Logs include transformation details for accept outcomes
- AC4: Logs include rejection reason for reject outcomes
- AC5: Logs include violation details for block outcomes
- AC6: Event custodial.filter.decision_logged emitted
- AC7: Preview operations are NOT logged
- AC8: Logged decisions are immutable (append-only ledger)
- AC9: Unit tests for logging each outcome type
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.coercion_filter_port import MessageType
from src.application.ports.governance.ledger_port import (
    GovernanceLedgerPort,
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.application.services.governance.filter_logging_service import (
    FILTER_DECISION_LOGGED_EVENT,
    FilterLoggingService,
)
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.filter import (
    FilterDecision,
    FilteredContent,
    FilterResult,
    FilterVersion,
    RejectionReason,
    Transformation,
    ViolationType,
)


class FakeTimeAuthority(TimeAuthorityProtocol):
    """Fake time authority for deterministic testing."""

    def __init__(self) -> None:
        self._time = datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._time

    def utcnow(self) -> datetime:
        return self._time

    def monotonic(self) -> float:
        return 0.0


class EventCapture:
    """Captures events for testing."""

    def __init__(self) -> None:
        self.events: list[GovernanceEvent] = []
        self._sequence = 0

    def get_last(self, event_type: str) -> GovernanceEvent | None:
        """Get most recent event of given type."""
        for event in reversed(self.events):
            if event.event_type == event_type:
                return event
        return None

    def count(self, event_type: str) -> int:
        """Count events of given type."""
        return sum(1 for e in self.events if e.event_type == event_type)


class FakeLedger(GovernanceLedgerPort):
    """Fake ledger for testing event emission."""

    def __init__(self, capture: EventCapture) -> None:
        self._capture = capture
        self._sequence = 0

    async def append_event(
        self,
        event: GovernanceEvent,
    ) -> PersistedGovernanceEvent:
        self._capture.events.append(event)
        self._sequence += 1
        return PersistedGovernanceEvent(event=event, sequence=self._sequence)

    async def get_latest_event(self) -> PersistedGovernanceEvent | None:
        if not self._capture.events:
            return None
        return PersistedGovernanceEvent(
            event=self._capture.events[-1],
            sequence=self._sequence,
        )

    async def get_max_sequence(self) -> int:
        return self._sequence

    async def read_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> list[PersistedGovernanceEvent]:
        return []

    async def get_event_by_sequence(
        self,
        sequence: int,
    ) -> PersistedGovernanceEvent | None:
        return None

    async def get_event_by_id(
        self,
        event_id: UUID,
    ) -> PersistedGovernanceEvent | None:
        return None

    async def count_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> int:
        return len(self._capture.events)


@pytest.fixture
def filter_version() -> FilterVersion:
    return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash")


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    return FakeTimeAuthority()


@pytest.fixture
def event_capture() -> EventCapture:
    return EventCapture()


@pytest.fixture
def ledger(event_capture: EventCapture) -> FakeLedger:
    return FakeLedger(event_capture)


@pytest.fixture
def logging_service(
    ledger: FakeLedger,
    time_authority: FakeTimeAuthority,
) -> FilterLoggingService:
    return FilterLoggingService(
        ledger=ledger,
        time_authority=time_authority,
    )


def create_accepted_result(
    filter_version: FilterVersion,
    content: str = "Filtered content",
    transformations: tuple[Transformation, ...] = (),
) -> FilterResult:
    """Create an ACCEPTED FilterResult for testing."""
    filtered_content = FilteredContent._create(
        content=content,
        original_content="Original content",
        filter_version=filter_version,
        filtered_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
    )
    return FilterResult.accepted(
        content=filtered_content,
        version=filter_version,
        timestamp=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
        transformations=transformations,
    )


def create_rejected_result(filter_version: FilterVersion) -> FilterResult:
    """Create a REJECTED FilterResult for testing."""
    return FilterResult.rejected(
        reason=RejectionReason.URGENCY_PRESSURE,
        version=filter_version,
        timestamp=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
        guidance="Remove urgency language.",
    )


def create_blocked_result(filter_version: FilterVersion) -> FilterResult:
    """Create a BLOCKED FilterResult for testing."""
    return FilterResult.blocked(
        violation=ViolationType.EXPLICIT_THREAT,
        version=filter_version,
        timestamp=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
        details="Explicit threat detected.",
    )


class TestLogDecisionAccepted:
    """Tests for logging ACCEPTED decisions (AC3)."""

    @pytest.mark.asyncio
    async def test_accepted_logged_with_transformations(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Accepted decisions log transformations."""
        transformation = Transformation(
            pattern_matched=r"URGENT",
            original_text="URGENT",
            replacement_text="",
            rule_id="urgency-1",
            position=0,
        )
        result = create_accepted_result(
            filter_version=filter_version,
            transformations=(transformation,),
        )

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="URGENT task",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        assert log_entry.decision == FilterDecision.ACCEPTED
        assert len(log_entry.transformations) == 1
        assert log_entry.transformations[0].rule_id == "urgency-1"

    @pytest.mark.asyncio
    async def test_accepted_event_emitted(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Accepted decisions emit event to ledger (AC6)."""
        result = create_accepted_result(filter_version=filter_version)

        await logging_service.log_decision(
            result=result,
            input_content="Clean content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last(FILTER_DECISION_LOGGED_EVENT)
        assert event is not None
        assert event.payload["decision"] == "accepted"

    @pytest.mark.asyncio
    async def test_accepted_includes_output_hash(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Accepted log includes output_hash."""
        result = create_accepted_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Clean content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        assert log_entry.output_hash is not None
        assert log_entry.output_hash.startswith("blake3:")


class TestLogDecisionRejected:
    """Tests for logging REJECTED decisions (AC4)."""

    @pytest.mark.asyncio
    async def test_rejected_logged_with_reason(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Rejected decisions log reason and guidance."""
        result = create_rejected_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="You must do this NOW!",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        assert log_entry.decision == FilterDecision.REJECTED
        assert log_entry.rejection_reason == RejectionReason.URGENCY_PRESSURE
        assert log_entry.rejection_guidance is not None

    @pytest.mark.asyncio
    async def test_rejected_event_emitted(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Rejected decisions emit event to ledger (AC6)."""
        result = create_rejected_result(filter_version=filter_version)

        await logging_service.log_decision(
            result=result,
            input_content="You must do this!",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last(FILTER_DECISION_LOGGED_EVENT)
        assert event is not None
        assert event.payload["decision"] == "rejected"
        assert event.payload["rejection_reason"] is not None

    @pytest.mark.asyncio
    async def test_rejected_has_no_output_hash(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Rejected log has no output_hash."""
        result = create_rejected_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="You must do this!",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        assert log_entry.output_hash is None


class TestLogDecisionBlocked:
    """Tests for logging BLOCKED decisions (AC5)."""

    @pytest.mark.asyncio
    async def test_blocked_logged_with_violation(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Blocked decisions log violation details."""
        result = create_blocked_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="I will hurt you.",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        assert log_entry.decision == FilterDecision.BLOCKED
        assert log_entry.violation_type == ViolationType.EXPLICIT_THREAT
        assert log_entry.violation_details is not None

    @pytest.mark.asyncio
    async def test_blocked_event_emitted(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Blocked decisions emit event to ledger (AC6)."""
        result = create_blocked_result(filter_version=filter_version)

        await logging_service.log_decision(
            result=result,
            input_content="Threatening content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last(FILTER_DECISION_LOGGED_EVENT)
        assert event is not None
        assert event.payload["decision"] == "blocked"
        assert event.payload["violation_type"] is not None


class TestContentHashing:
    """Tests for content privacy via hashing."""

    @pytest.mark.asyncio
    async def test_content_hashed_not_stored(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Logs store hashes, not raw content."""
        sensitive_content = "Sensitive task details with SSN 123-45-6789"
        result = create_accepted_result(filter_version=filter_version)

        await logging_service.log_decision(
            result=result,
            input_content=sensitive_content,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last(FILTER_DECISION_LOGGED_EVENT)
        assert event is not None
        # Raw content should NOT be in payload
        payload_str = str(event.payload)
        assert sensitive_content not in payload_str
        assert "SSN" not in payload_str
        # But hash should be present
        assert event.payload["input_hash"].startswith("blake3:")

    @pytest.mark.asyncio
    async def test_hash_is_deterministic(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Same content produces same hash."""
        content = "Test content"
        result = create_accepted_result(filter_version=filter_version)
        earl_id = uuid4()

        log1 = await logging_service.log_decision(
            result=result,
            input_content=content,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=earl_id,
        )
        log2 = await logging_service.log_decision(
            result=result,
            input_content=content,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=earl_id,
        )

        assert log1.input_hash == log2.input_hash


class TestDecisionMetadata:
    """Tests for decision metadata (AC1)."""

    @pytest.mark.asyncio
    async def test_log_includes_version(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Log includes filter version."""
        result = create_accepted_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        assert log_entry.filter_version == filter_version

    @pytest.mark.asyncio
    async def test_log_includes_timestamp(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Log includes timestamp."""
        result = create_accepted_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        assert log_entry.timestamp is not None

    @pytest.mark.asyncio
    async def test_log_includes_message_type(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Log includes message type."""
        result = create_accepted_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.REMINDER,
            earl_id=uuid4(),
        )

        assert log_entry.message_type == MessageType.REMINDER

    @pytest.mark.asyncio
    async def test_log_includes_earl_id(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Log includes Earl ID."""
        result = create_accepted_result(filter_version=filter_version)
        earl_id = uuid4()

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=earl_id,
        )

        assert log_entry.earl_id == earl_id


class TestDecisionHistory:
    """Tests for decision history queries."""

    @pytest.mark.asyncio
    async def test_get_decision_history(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Can retrieve decision history."""
        earl_id = uuid4()

        # Log multiple decisions
        for _ in range(3):
            result = create_accepted_result(filter_version=filter_version)
            await logging_service.log_decision(
                result=result,
                input_content="Test content",
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=earl_id,
            )

        history = await logging_service.get_decision_history(earl_id=earl_id)

        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_filter_by_decision_type(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Can filter history by decision type."""
        earl_id = uuid4()

        # Log mixed decisions
        await logging_service.log_decision(
            result=create_accepted_result(filter_version=filter_version),
            input_content="Clean",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=earl_id,
        )
        await logging_service.log_decision(
            result=create_rejected_result(filter_version=filter_version),
            input_content="Bad",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=earl_id,
        )

        rejected_only = await logging_service.get_decision_history(
            earl_id=earl_id,
            decision_type="rejected",
        )

        assert len(rejected_only) == 1
        assert rejected_only[0].decision == FilterDecision.REJECTED

    @pytest.mark.asyncio
    async def test_count_decisions(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Can count decisions matching criteria."""
        earl_id = uuid4()

        # Log multiple decisions
        for _ in range(5):
            result = create_accepted_result(filter_version=filter_version)
            await logging_service.log_decision(
                result=result,
                input_content="Test content",
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=earl_id,
            )

        count = await logging_service.count_decisions(earl_id=earl_id)

        assert count == 5

    @pytest.mark.asyncio
    async def test_get_decision_by_id(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Can retrieve specific decision by ID."""
        result = create_accepted_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        retrieved = await logging_service.get_decision_by_id(log_entry.decision_id)

        assert retrieved is not None
        assert retrieved.decision_id == log_entry.decision_id


class TestEventEmission:
    """Tests for event emission (AC6)."""

    @pytest.mark.asyncio
    async def test_event_type_is_correct(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Event type is custodial.filter.decision_logged."""
        result = create_accepted_result(filter_version=filter_version)

        await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last(FILTER_DECISION_LOGGED_EVENT)
        assert event is not None
        assert event.event_type == "custodial.filter.decision_logged"

    @pytest.mark.asyncio
    async def test_event_actor_is_system(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Event actor is 'system' (filter is system actor)."""
        result = create_accepted_result(filter_version=filter_version)

        await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last(FILTER_DECISION_LOGGED_EVENT)
        assert event is not None
        assert event.actor_id == "system"

    @pytest.mark.asyncio
    async def test_event_includes_decision_id_as_trace(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        event_capture: EventCapture,
    ) -> None:
        """Event trace_id is the decision_id."""
        result = create_accepted_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        event = event_capture.get_last(FILTER_DECISION_LOGGED_EVENT)
        assert event is not None
        assert event.trace_id == str(log_entry.decision_id)


class TestAppendOnlySemantics:
    """Tests for append-only semantics (AC8)."""

    @pytest.mark.asyncio
    async def test_decisions_are_immutable(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
    ) -> None:
        """Logged decisions cannot be modified."""
        result = create_accepted_result(filter_version=filter_version)

        log_entry = await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        # FilterDecisionLog is frozen - cannot be modified
        with pytest.raises(AttributeError):
            log_entry.decision = FilterDecision.REJECTED  # type: ignore

    @pytest.mark.asyncio
    async def test_event_appended_to_ledger(
        self,
        logging_service: FilterLoggingService,
        filter_version: FilterVersion,
        ledger: FakeLedger,
    ) -> None:
        """Events are appended to ledger (not updated)."""
        initial_sequence = await ledger.get_max_sequence()

        result = create_accepted_result(filter_version=filter_version)
        await logging_service.log_decision(
            result=result,
            input_content="Test content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
        )

        new_sequence = await ledger.get_max_sequence()
        assert new_sequence == initial_sequence + 1
