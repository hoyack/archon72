"""Unit tests for IndependentVerificationService.

Story: consent-gov-9.3: Independent Verification

Tests cover:
- AC1: Independent hash chain verification (FR58)
- AC2: Independent Merkle proof verification
- AC3: State derivable through event replay (NFR-AUDIT-06)
- AC4: Verification possible offline with exported ledger
- AC5: Event audit.verification.completed emitted after verification
- AC6: Verification detects tampering
- AC7: Verification detects missing events
- AC8: Unit tests for verification
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.independent_verification_service import (
    IndependentVerificationService,
    VERIFICATION_COMPLETED_EVENT,
)
from src.domain.governance.audit.ledger_export import (
    ExportMetadata,
    LedgerExport,
    VerificationInfo,
)
from src.domain.governance.audit.verification_result import (
    DetectedIssue,
    IssueType,
    VerificationResult,
    VerificationStatus,
)
from src.domain.governance.events.event_envelope import EventMetadata, GovernanceEvent
from src.application.ports.governance.ledger_port import PersistedGovernanceEvent

# Test algorithm
TEST_ALGORITHM = "sha256"


# ============================================================================
# Fixtures
# ============================================================================


class MockTimeAuthority:
    """Mock time authority for testing."""

    def __init__(self, frozen_time: datetime | None = None) -> None:
        self._time = frozen_time or datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._time


class MockEventEmitter:
    """Mock event emitter for testing."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.append({
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
        })

    def get_last(self, event_type: str) -> dict[str, Any] | None:
        for event in reversed(self.events):
            if event["event_type"] == event_type:
                return event
        return None


class MockStateReplayer:
    """Mock state replayer for testing."""

    def __init__(self, should_fail: bool = False, state_value: Any = "derived_state") -> None:
        self._should_fail = should_fail
        self._state_value = state_value

    async def replay(self, events: list) -> Any:
        if self._should_fail:
            raise RuntimeError("State replay failed")
        return self._state_value


def make_event_hash(content: str, sequence: int, prev_hash: str, algorithm: str = TEST_ALGORITHM) -> str:
    """Create a deterministic hash for testing."""
    import hashlib
    data = f"{content}:{sequence}:{prev_hash}"
    digest = hashlib.sha256(data.encode()).hexdigest()
    return f"{algorithm}:{digest}"


def make_prev_hash(event_hash: str) -> str:
    """Extract hash for prev_hash linking."""
    return event_hash


def create_governance_event(
    event_id: UUID,
    event_type: str,
    timestamp: datetime,
    actor_id: str,
    payload: dict,
    prev_hash: str,
    event_hash: str,
) -> GovernanceEvent:
    """Create a GovernanceEvent with proper metadata structure."""
    metadata = EventMetadata(
        event_id=event_id,
        event_type=event_type,
        timestamp=timestamp,
        actor_id=actor_id,
        schema_version="1.0.0",
        trace_id=str(uuid4()),
        prev_hash=prev_hash,
        hash=event_hash,
    )
    return GovernanceEvent(metadata=metadata, payload=payload)


def create_valid_events(count: int = 5) -> list[PersistedGovernanceEvent]:
    """Create a list of valid events with correct hash chain."""
    events = []
    prev_hash = ""  # Empty for genesis

    for i in range(count):
        sequence = i + 1
        event_type = f"executive.task.created"  # Valid event type with branch.noun.verb
        actor_id = str(uuid4())
        timestamp = datetime(2026, 1, 17, 12, 0, i, tzinfo=timezone.utc)
        payload = {"index": i, "data": f"event_{i}"}
        payload_json = json.dumps(payload, sort_keys=True)

        # Compute hash for this event
        event_hash = make_event_hash(payload_json, sequence, prev_hash)

        gov_event = create_governance_event(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=timestamp,
            actor_id=actor_id,
            payload=payload,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )

        persisted = PersistedGovernanceEvent(
            event=gov_event,
            sequence=sequence,
        )
        events.append(persisted)

        # Next event links to this one
        prev_hash = event_hash

    return events


def create_export_from_events(
    events: list[PersistedGovernanceEvent],
    merkle_root: str | None = None,
) -> LedgerExport:
    """Create a LedgerExport from events."""
    if not events:
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
            format_version="1.0.0",
            total_events=0,
            genesis_hash="",
            latest_hash="",
            sequence_range=(0, 0),
        )
    else:
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
            format_version="1.0.0",
            total_events=len(events),
            genesis_hash=events[0].event.hash,
            latest_hash=events[-1].event.hash,
            sequence_range=(events[0].sequence, events[-1].sequence),
        )

    verification = VerificationInfo(
        hash_algorithm=TEST_ALGORITHM.upper(),
        chain_valid=True,
        genesis_to_latest=True,
    )

    return LedgerExport(
        metadata=metadata,
        events=tuple(events),
        verification=verification,
    )


@pytest.fixture
def time_authority() -> MockTimeAuthority:
    """Provide a mock time authority."""
    return MockTimeAuthority()


@pytest.fixture
def event_emitter() -> MockEventEmitter:
    """Provide a mock event emitter."""
    return MockEventEmitter()


@pytest.fixture
def state_replayer() -> MockStateReplayer:
    """Provide a mock state replayer."""
    return MockStateReplayer()


@pytest.fixture
def failing_state_replayer() -> MockStateReplayer:
    """Provide a state replayer that fails."""
    return MockStateReplayer(should_fail=True)


@pytest.fixture
def verification_service(
    time_authority: MockTimeAuthority,
    event_emitter: MockEventEmitter,
    state_replayer: MockStateReplayer,
) -> IndependentVerificationService:
    """Provide a verification service with all dependencies."""
    return IndependentVerificationService(
        state_replayer=state_replayer,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


@pytest.fixture
def offline_verification_service(
    time_authority: MockTimeAuthority,
    state_replayer: MockStateReplayer,
) -> IndependentVerificationService:
    """Provide a verification service without event emitter (offline mode)."""
    return IndependentVerificationService(
        state_replayer=state_replayer,
        event_emitter=None,
        time_authority=time_authority,
    )


@pytest.fixture
def valid_events() -> list[PersistedGovernanceEvent]:
    """Provide valid events with correct hash chain."""
    return create_valid_events(5)


@pytest.fixture
def valid_export(valid_events: list[PersistedGovernanceEvent]) -> LedgerExport:
    """Provide a valid ledger export."""
    return create_export_from_events(valid_events)


@pytest.fixture
def empty_export() -> LedgerExport:
    """Provide an empty ledger export."""
    return create_export_from_events([])


# ============================================================================
# Test Classes
# ============================================================================


class TestIndependentVerificationService:
    """Unit tests for independent verification service."""

    @pytest.mark.asyncio
    async def test_valid_ledger_passes(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """AC1: Valid ledger passes all verification checks."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.status == VerificationStatus.VALID
        assert result.hash_chain_valid
        assert result.sequence_complete
        assert result.state_replay_valid
        assert not result.has_issues

    @pytest.mark.asyncio
    async def test_empty_ledger_passes(
        self,
        verification_service: IndependentVerificationService,
        empty_export: LedgerExport,
    ) -> None:
        """Empty ledger is valid."""
        result = await verification_service.verify_complete(
            ledger_export=empty_export,
        )

        assert result.status == VerificationStatus.VALID
        assert result.hash_chain_valid
        assert result.sequence_complete
        assert result.total_events_verified == 0

    @pytest.mark.asyncio
    async def test_verification_id_is_unique(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """Each verification gets unique ID."""
        result1 = await verification_service.verify_complete(ledger_export=valid_export)
        result2 = await verification_service.verify_complete(ledger_export=valid_export)

        assert result1.verification_id != result2.verification_id

    @pytest.mark.asyncio
    async def test_verified_at_timestamp(
        self,
        time_authority: MockTimeAuthority,
        event_emitter: MockEventEmitter,
        state_replayer: MockStateReplayer,
        valid_export: LedgerExport,
    ) -> None:
        """Verification timestamp matches time authority."""
        frozen_time = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        time_authority._time = frozen_time

        service = IndependentVerificationService(
            state_replayer=state_replayer,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        result = await service.verify_complete(ledger_export=valid_export)

        assert result.verified_at == frozen_time


class TestHashChainVerification:
    """Tests for hash chain verification (AC1, AC6)."""

    @pytest.mark.asyncio
    async def test_valid_chain_passes(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """Valid hash chain passes verification."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.hash_chain_valid
        assert not any(i.issue_type == IssueType.HASH_MISMATCH for i in result.issues)
        assert not any(i.issue_type == IssueType.BROKEN_LINK for i in result.issues)

    @pytest.mark.asyncio
    async def test_tampered_event_detected(
        self,
        verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """AC6: Tampered event (modified hash) is detected."""
        # Tamper with event 2's hash
        tampered_events = []
        for i, event in enumerate(valid_events):
            if i == 2:
                # Modify the hash to simulate tampering
                tampered_event = create_governance_event(
                    event_id=event.event.event_id,
                    event_type=event.event.event_type,
                    timestamp=event.event.timestamp,
                    actor_id=event.event.actor_id,
                    payload=dict(event.event.payload),
                    prev_hash=event.event.prev_hash,
                    event_hash="sha256:tampered_hash_value",  # Wrong hash
                )
                tampered_events.append(
                    PersistedGovernanceEvent(event=tampered_event, sequence=event.sequence)
                )
            else:
                tampered_events.append(event)

        export = create_export_from_events(tampered_events)

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        assert result.status != VerificationStatus.VALID
        assert not result.hash_chain_valid
        # Should detect hash mismatch or broken link
        assert result.has_issues

    @pytest.mark.asyncio
    async def test_broken_link_detected(
        self,
        verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """AC6: Broken prev_hash link is detected."""
        # Break the link on event 3
        broken_events = []
        for i, event in enumerate(valid_events):
            if i == 3:
                # Set wrong prev_hash
                broken_event = create_governance_event(
                    event_id=event.event.event_id,
                    event_type=event.event.event_type,
                    timestamp=event.event.timestamp,
                    actor_id=event.event.actor_id,
                    payload=dict(event.event.payload),
                    prev_hash="sha256:wrong_previous_hash",  # Wrong link
                    event_hash=event.event.hash,
                )
                broken_events.append(
                    PersistedGovernanceEvent(event=broken_event, sequence=event.sequence)
                )
            else:
                broken_events.append(event)

        export = create_export_from_events(broken_events)

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        assert not result.hash_chain_valid
        assert any(i.issue_type == IssueType.BROKEN_LINK for i in result.issues)


class TestSequenceVerification:
    """Tests for sequence completeness verification (AC7)."""

    @pytest.mark.asyncio
    async def test_complete_sequence_passes(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """Complete sequence with no gaps passes."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.sequence_complete
        assert not any(i.issue_type == IssueType.SEQUENCE_GAP for i in result.issues)

    @pytest.mark.asyncio
    async def test_sequence_gap_detected(
        self,
        verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """AC7: Missing sequence number (gap) is detected."""
        # Remove event at sequence 3 (index 2)
        events_with_gap = valid_events[:2] + valid_events[3:]

        # Update metadata to reflect actual events
        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
            format_version="1.0.0",
            total_events=len(events_with_gap),
            genesis_hash=events_with_gap[0].event.hash,
            latest_hash=events_with_gap[-1].event.hash,
            sequence_range=(events_with_gap[0].sequence, events_with_gap[-1].sequence),
        )

        verification = VerificationInfo(
            hash_algorithm=TEST_ALGORITHM.upper(),
            chain_valid=True,
            genesis_to_latest=True,
        )

        export = LedgerExport(
            metadata=metadata,
            events=tuple(events_with_gap),
            verification=verification,
        )

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        assert not result.sequence_complete
        gap_issues = [i for i in result.issues if i.issue_type == IssueType.SEQUENCE_GAP]
        assert len(gap_issues) > 0
        assert gap_issues[0].expected == "3"

    @pytest.mark.asyncio
    async def test_sequence_not_starting_at_one_detected(
        self,
        verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """Sequence not starting at 1 is detected."""
        # Remove first two events
        events_no_start = valid_events[2:]

        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
            format_version="1.0.0",
            total_events=len(events_no_start),
            genesis_hash=events_no_start[0].event.hash,
            latest_hash=events_no_start[-1].event.hash,
            sequence_range=(events_no_start[0].sequence, events_no_start[-1].sequence),
        )

        verification = VerificationInfo(
            hash_algorithm=TEST_ALGORITHM.upper(),
            chain_valid=True,
            genesis_to_latest=True,
        )

        export = LedgerExport(
            metadata=metadata,
            events=tuple(events_no_start),
            verification=verification,
        )

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        assert not result.sequence_complete
        gap_issues = [i for i in result.issues if i.issue_type == IssueType.SEQUENCE_GAP]
        assert len(gap_issues) > 0


class TestMerkleVerification:
    """Tests for Merkle verification (AC2)."""

    @pytest.mark.asyncio
    async def test_merkle_valid_when_root_matches(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """Merkle valid when no expected root provided (skip check)."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        # Without explicit merkle_root in export, should be valid
        assert result.merkle_valid

    @pytest.mark.asyncio
    async def test_merkle_root_mismatch_detected(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """AC2: Merkle root mismatch is detected when expected root doesn't match."""
        # Provide wrong expected root
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
            expected_merkle_root="sha256:wrong_merkle_root",
        )

        assert not result.merkle_valid
        assert any(i.issue_type == IssueType.MERKLE_MISMATCH for i in result.issues)


class TestStateReplay:
    """Tests for state derivation through replay (AC3)."""

    @pytest.mark.asyncio
    async def test_state_derivable(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """AC3: State is derivable from events."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.state_replay_valid

    @pytest.mark.asyncio
    async def test_state_replay_failure_detected(
        self,
        time_authority: MockTimeAuthority,
        event_emitter: MockEventEmitter,
        failing_state_replayer: MockStateReplayer,
        valid_export: LedgerExport,
    ) -> None:
        """State replay failure is detected."""
        service = IndependentVerificationService(
            state_replayer=failing_state_replayer,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        result = await service.verify_complete(
            ledger_export=valid_export,
        )

        assert not result.state_replay_valid
        assert any(i.issue_type == IssueType.STATE_MISMATCH for i in result.issues)

    @pytest.mark.asyncio
    async def test_state_replay_returns_none_detected(
        self,
        time_authority: MockTimeAuthority,
        event_emitter: MockEventEmitter,
        valid_export: LedgerExport,
    ) -> None:
        """State replayer returning None is detected."""
        replayer = MockStateReplayer(state_value=None)

        service = IndependentVerificationService(
            state_replayer=replayer,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        result = await service.verify_complete(
            ledger_export=valid_export,
        )

        assert not result.state_replay_valid
        assert any(i.issue_type == IssueType.STATE_MISMATCH for i in result.issues)


class TestOfflineVerification:
    """Tests for offline verification capability (AC4)."""

    @pytest.mark.asyncio
    async def test_works_offline(
        self,
        offline_verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """AC4: Verification works completely offline (no event emitter)."""
        result = await offline_verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.status == VerificationStatus.VALID

    @pytest.mark.asyncio
    async def test_no_events_emitted_offline(
        self,
        offline_verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """No events emitted when running offline."""
        # Service has no event emitter
        result = await offline_verification_service.verify_complete(
            ledger_export=valid_export,
            verifier_id=uuid4(),
        )

        # Should still work
        assert result is not None
        assert result.status == VerificationStatus.VALID

    @pytest.mark.asyncio
    async def test_verify_from_json(
        self,
        offline_verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """AC4: Verification from JSON export works."""
        export = create_export_from_events(valid_events)

        # Convert to JSON representation
        export_dict = {
            "metadata": {
                "export_id": str(export.metadata.export_id),
                "exported_at": export.metadata.exported_at.isoformat(),
                "format_version": export.metadata.format_version,
                "total_events": export.metadata.total_events,
                "genesis_hash": export.metadata.genesis_hash,
                "latest_hash": export.metadata.latest_hash,
                "sequence_range": list(export.metadata.sequence_range),
            },
            "events": [
                {
                    "event_id": str(e.event_id),
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "actor_id": e.actor_id,
                    "payload": dict(e.event.payload),  # Convert MappingProxy to dict
                    "prev_hash": e.event.prev_hash,
                    "hash": e.event.hash,
                    "sequence": e.sequence,
                }
                for e in export.events
            ],
            "verification": {
                "hash_algorithm": export.verification.hash_algorithm,
                "chain_valid": export.verification.chain_valid,
                "genesis_to_latest": export.verification.genesis_to_latest,
            },
        }

        ledger_json = json.dumps(export_dict)

        result = await offline_verification_service.verify_offline(
            ledger_json=ledger_json,
        )

        assert result.status == VerificationStatus.VALID
        assert result.total_events_verified == len(valid_events)


class TestVerificationEvents:
    """Tests for verification event emission (AC5)."""

    @pytest.mark.asyncio
    async def test_verification_event_emitted(
        self,
        verification_service: IndependentVerificationService,
        event_emitter: MockEventEmitter,
        valid_export: LedgerExport,
    ) -> None:
        """AC5: audit.verification.completed event is emitted."""
        verifier_id = uuid4()

        await verification_service.verify_complete(
            ledger_export=valid_export,
            verifier_id=verifier_id,
        )

        event = event_emitter.get_last(VERIFICATION_COMPLETED_EVENT)
        assert event is not None
        assert event["actor"] == str(verifier_id)
        assert event["payload"]["status"] == "valid"

    @pytest.mark.asyncio
    async def test_event_contains_verification_details(
        self,
        verification_service: IndependentVerificationService,
        event_emitter: MockEventEmitter,
        valid_export: LedgerExport,
    ) -> None:
        """Event contains all verification details."""
        verifier_id = uuid4()

        result = await verification_service.verify_complete(
            ledger_export=valid_export,
            verifier_id=verifier_id,
        )

        event = event_emitter.get_last(VERIFICATION_COMPLETED_EVENT)
        assert event is not None

        payload = event["payload"]
        assert payload["verification_id"] == str(result.verification_id)
        assert payload["verifier_id"] == str(verifier_id)
        assert payload["hash_chain_valid"] == result.hash_chain_valid
        assert payload["sequence_complete"] == result.sequence_complete
        assert payload["issues_count"] == len(result.issues)

    @pytest.mark.asyncio
    async def test_no_event_without_verifier_id(
        self,
        verification_service: IndependentVerificationService,
        event_emitter: MockEventEmitter,
        valid_export: LedgerExport,
    ) -> None:
        """No event emitted if verifier_id not provided."""
        await verification_service.verify_complete(
            ledger_export=valid_export,
            verifier_id=None,
        )

        event = event_emitter.get_last(VERIFICATION_COMPLETED_EVENT)
        assert event is None


class TestTamperingDetection:
    """Tests for tampering detection (AC6)."""

    @pytest.mark.asyncio
    async def test_modified_content_detected(
        self,
        verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """AC6: Modified event content with different hash is detected via broken chain link.

        When content is modified and the hash is changed, the next event's prev_hash
        won't match, breaking the chain. The verification detects this broken link.
        """
        # Modify event 2's hash to simulate someone changing content and recomputing hash
        # This breaks the link from event 3 (whose prev_hash points to original event 2 hash)
        modified_events = []
        for i, event in enumerate(valid_events):
            if i == 2:
                modified_event = create_governance_event(
                    event_id=event.event.event_id,
                    event_type=event.event.event_type,
                    timestamp=event.event.timestamp,
                    actor_id=event.event.actor_id,
                    payload={"index": 999, "data": "TAMPERED"},  # Modified content
                    prev_hash=event.event.prev_hash,
                    event_hash="sha256:modified_content_hash_value",  # New hash for modified content
                )
                modified_events.append(
                    PersistedGovernanceEvent(event=modified_event, sequence=event.sequence)
                )
            else:
                modified_events.append(event)

        export = create_export_from_events(modified_events)

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        # The chain should be broken because event 3's prev_hash points to original event 2 hash
        # but event 2 now has a different hash
        assert not result.hash_chain_valid
        assert result.has_issues
        assert any(i.issue_type == IssueType.BROKEN_LINK for i in result.issues)

    @pytest.mark.asyncio
    async def test_reordered_events_detected(
        self,
        verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """AC6: Reordered events are detected."""
        # Swap events 2 and 3
        reordered = valid_events.copy()
        reordered[2], reordered[3] = reordered[3], reordered[2]

        export = create_export_from_events(reordered)

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        # Reordering breaks both hash chain and sequence
        assert not result.hash_chain_valid or not result.sequence_complete


class TestGapDetection:
    """Tests for gap detection (AC7)."""

    @pytest.mark.asyncio
    async def test_sequence_gap_at_position_5(
        self,
        verification_service: IndependentVerificationService,
    ) -> None:
        """AC7: Gap at specific position is reported correctly."""
        # Create 10 events, remove event 5
        events = create_valid_events(10)
        events_with_gap = events[:4] + events[5:]  # Missing seq 5

        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
            format_version="1.0.0",
            total_events=len(events_with_gap),
            genesis_hash=events_with_gap[0].event.hash,
            latest_hash=events_with_gap[-1].event.hash,
            sequence_range=(events_with_gap[0].sequence, events_with_gap[-1].sequence),
        )

        verification = VerificationInfo(
            hash_algorithm=TEST_ALGORITHM.upper(),
            chain_valid=True,
            genesis_to_latest=True,
        )

        export = LedgerExport(
            metadata=metadata,
            events=tuple(events_with_gap),
            verification=verification,
        )

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        assert not result.sequence_complete
        gap_issues = [i for i in result.issues if i.issue_type == IssueType.SEQUENCE_GAP]
        assert len(gap_issues) > 0
        assert gap_issues[0].expected == "5"

    @pytest.mark.asyncio
    async def test_multiple_gaps_detected(
        self,
        verification_service: IndependentVerificationService,
    ) -> None:
        """AC7: Multiple gaps are all detected."""
        # Create 10 events, remove events 3 and 7
        events = create_valid_events(10)
        events_with_gaps = events[:2] + events[3:6] + events[7:]  # Missing seq 3 and 7

        metadata = ExportMetadata(
            export_id=uuid4(),
            exported_at=datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
            format_version="1.0.0",
            total_events=len(events_with_gaps),
            genesis_hash=events_with_gaps[0].event.hash,
            latest_hash=events_with_gaps[-1].event.hash,
            sequence_range=(events_with_gaps[0].sequence, events_with_gaps[-1].sequence),
        )

        verification = VerificationInfo(
            hash_algorithm=TEST_ALGORITHM.upper(),
            chain_valid=True,
            genesis_to_latest=True,
        )

        export = LedgerExport(
            metadata=metadata,
            events=tuple(events_with_gaps),
            verification=verification,
        )

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        assert not result.sequence_complete
        gap_issues = [i for i in result.issues if i.issue_type == IssueType.SEQUENCE_GAP]
        assert len(gap_issues) >= 2


class TestVerificationStatus:
    """Tests for verification status determination."""

    @pytest.mark.asyncio
    async def test_valid_status_when_all_pass(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ) -> None:
        """Status is VALID when all checks pass."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.status == VerificationStatus.VALID
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_invalid_status_when_critical_fails(
        self,
        verification_service: IndependentVerificationService,
        valid_events: list[PersistedGovernanceEvent],
    ) -> None:
        """Status is INVALID or PARTIAL when critical checks fail."""
        # Create events with all prev_hash links broken
        broken_events = []
        for event in valid_events:
            broken_event = create_governance_event(
                event_id=event.event.event_id,
                event_type=event.event.event_type,
                timestamp=event.event.timestamp,
                actor_id=event.event.actor_id,
                payload=dict(event.event.payload),
                prev_hash="sha256:wrong_hash_value",  # All links broken
                event_hash=event.event.hash,
            )
            broken_events.append(
                PersistedGovernanceEvent(event=broken_event, sequence=event.sequence)
            )

        export = create_export_from_events(broken_events)

        result = await verification_service.verify_complete(
            ledger_export=export,
        )

        # Should detect hash chain issues
        assert not result.hash_chain_valid
        assert result.status in (VerificationStatus.INVALID, VerificationStatus.PARTIAL)

    @pytest.mark.asyncio
    async def test_partial_status_when_some_pass(
        self,
        time_authority: MockTimeAuthority,
        event_emitter: MockEventEmitter,
        failing_state_replayer: MockStateReplayer,
        valid_export: LedgerExport,
    ) -> None:
        """Status is PARTIAL when some checks pass and some fail."""
        service = IndependentVerificationService(
            state_replayer=failing_state_replayer,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        result = await service.verify_complete(
            ledger_export=valid_export,
        )

        # Hash chain and sequence pass, but state replay fails
        assert result.hash_chain_valid
        assert result.sequence_complete
        assert not result.state_replay_valid
        assert result.status == VerificationStatus.PARTIAL
