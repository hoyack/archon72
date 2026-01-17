"""Unit tests for hash_chain module.

Story: consent-gov-1.3: Hash Chain Implementation

Tests hash chain computation, verification, and factory methods per AC1-AC10.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)
from src.domain.governance.events.hash_algorithms import (
    GENESIS_PREV_HASH,
    is_genesis_hash,
)
from src.domain.governance.events.hash_chain import (
    HashVerificationResult,
    add_hash_to_event,
    chain_events,
    compute_event_hash,
    compute_event_hash_with_prev,
    verify_chain_link,
    verify_event_full,
    verify_event_hash,
)


def make_test_event(
    event_type: str = "executive.task.accepted",
    payload: dict | None = None,
    prev_hash: str = "",
    hash_: str = "",
) -> GovernanceEvent:
    """Create a test GovernanceEvent."""
    metadata = EventMetadata(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        schema_version="1.0.0",
        trace_id=str(uuid4()),
        prev_hash=prev_hash,
        hash=hash_,
    )
    return GovernanceEvent(
        metadata=metadata,
        payload=payload or {"key": "value"},
    )


class TestComputeEventHash:
    """Tests for compute_event_hash function (AC6)."""

    def test_compute_hash_returns_prefixed_string(self) -> None:
        """compute_event_hash returns algorithm-prefixed hash."""
        event = make_test_event(prev_hash=GENESIS_PREV_HASH)
        result = compute_event_hash(event, "blake3")
        assert result.startswith("blake3:")
        assert len(result) == 7 + 64

    def test_compute_hash_deterministic(self) -> None:
        """Same event produces same hash."""
        event = make_test_event(prev_hash=GENESIS_PREV_HASH)
        hash1 = compute_event_hash(event, "blake3")
        hash2 = compute_event_hash(event, "blake3")
        assert hash1 == hash2

    def test_compute_hash_different_for_different_payload(self) -> None:
        """Different payload produces different hash."""
        event1 = make_test_event(prev_hash=GENESIS_PREV_HASH, payload={"a": 1})
        event2 = make_test_event(prev_hash=GENESIS_PREV_HASH, payload={"a": 2})
        hash1 = compute_event_hash(event1, "blake3")
        hash2 = compute_event_hash(event2, "blake3")
        assert hash1 != hash2

    def test_compute_hash_different_for_different_prev_hash(self) -> None:
        """Different prev_hash produces different hash."""
        event1 = make_test_event(prev_hash=GENESIS_PREV_HASH)
        event2 = make_test_event(prev_hash=f"blake3:{'a' * 64}")
        hash1 = compute_event_hash(event1, "blake3")
        hash2 = compute_event_hash(event2, "blake3")
        assert hash1 != hash2

    def test_compute_hash_requires_prev_hash(self) -> None:
        """compute_event_hash raises if event has no prev_hash."""
        event = make_test_event()  # No prev_hash
        with pytest.raises(ConstitutionalViolationError, match="prev_hash"):
            compute_event_hash(event)

    def test_compute_hash_sha256_algorithm(self) -> None:
        """compute_event_hash works with SHA-256."""
        event = make_test_event(prev_hash=GENESIS_PREV_HASH)
        result = compute_event_hash(event, "sha256")
        assert result.startswith("sha256:")
        assert len(result) == 7 + 64


class TestComputeEventHashWithPrev:
    """Tests for compute_event_hash_with_prev function."""

    def test_computes_hash_with_provided_prev_hash(self) -> None:
        """Can compute hash with explicitly provided prev_hash."""
        event = make_test_event()  # No prev_hash in metadata
        result = compute_event_hash_with_prev(event, GENESIS_PREV_HASH, "blake3")
        assert result.startswith("blake3:")

    def test_validates_prev_hash_format(self) -> None:
        """Raises for invalid prev_hash format."""
        event = make_test_event()
        with pytest.raises(ConstitutionalViolationError, match="Invalid prev_hash"):
            compute_event_hash_with_prev(event, "invalid", "blake3")


class TestVerifyEventHash:
    """Tests for verify_event_hash function (AC7)."""

    def test_verify_valid_hash(self) -> None:
        """Valid hash verification returns success."""
        # Create event with computed hash
        unhashed_event = make_test_event()
        hashed_event = add_hash_to_event(unhashed_event, None, "blake3")

        result = verify_event_hash(hashed_event)
        assert result.is_valid is True
        assert result.event_hash_valid is True

    def test_verify_returns_false_for_no_hash(self) -> None:
        """Event without hash returns invalid result."""
        event = make_test_event()
        result = verify_event_hash(event)
        assert result.is_valid is False
        assert "no hash" in result.error_message.lower()

    def test_verify_returns_false_for_no_prev_hash(self) -> None:
        """Event without prev_hash returns invalid result."""
        # Create event with hash but no prev_hash
        metadata = EventMetadata(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            schema_version="1.0.0",
            trace_id=str(uuid4()),
            prev_hash="",
            hash=f"blake3:{'a' * 64}",
        )
        event = GovernanceEvent(metadata=metadata, payload={"key": "value"})

        result = verify_event_hash(event)
        assert result.is_valid is False
        assert "prev_hash" in result.error_message.lower()

    def test_verify_detects_tampered_payload(self) -> None:
        """Tampered payload fails verification."""
        # Create valid hashed event
        unhashed_event = make_test_event(payload={"original": "data"})
        hashed_event = add_hash_to_event(unhashed_event, None, "blake3")

        # Tamper with payload by creating new event with same hash but different payload
        tampered_metadata = EventMetadata(
            event_id=hashed_event.event_id,
            event_type=hashed_event.event_type,
            timestamp=hashed_event.timestamp,
            actor_id=hashed_event.actor_id,
            schema_version=hashed_event.schema_version,
            trace_id=hashed_event.trace_id,
            prev_hash=hashed_event.prev_hash,
            hash=hashed_event.hash,
        )
        tampered_event = GovernanceEvent(
            metadata=tampered_metadata,
            payload={"tampered": "data"},
        )

        result = verify_event_hash(tampered_event)
        assert result.is_valid is False
        assert "mismatch" in result.error_message.lower()


class TestVerifyChainLink:
    """Tests for verify_chain_link function (AC7)."""

    def test_genesis_event_with_null_hash(self) -> None:
        """Genesis event with null prev_hash is valid."""
        unhashed_event = make_test_event()
        hashed_event = add_hash_to_event(unhashed_event, None, "blake3")

        result = verify_chain_link(hashed_event, None)
        assert result.is_valid is True
        assert result.chain_link_valid is True

    def test_genesis_event_with_non_null_hash(self) -> None:
        """Genesis event with non-null prev_hash is invalid."""
        # Create event with non-genesis prev_hash but no previous event
        event = make_test_event(
            prev_hash=f"blake3:{'a' * 64}",
            hash_=f"blake3:{'b' * 64}",
        )

        result = verify_chain_link(event, None)
        assert result.is_valid is False
        assert "genesis" in result.error_message.lower()

    def test_chained_events_valid(self) -> None:
        """Properly chained events verify successfully."""
        # Create first event
        event1 = add_hash_to_event(make_test_event(), None, "blake3")

        # Create second event chained to first
        event2_unhashed = make_test_event(payload={"second": "event"})
        event2 = add_hash_to_event(event2_unhashed, event1.hash, "blake3")

        result = verify_chain_link(event2, event1)
        assert result.is_valid is True
        assert result.chain_link_valid is True

    def test_broken_chain_detected(self) -> None:
        """Broken chain link is detected."""
        # Create first event
        event1 = add_hash_to_event(make_test_event(), None, "blake3")

        # Create second event with wrong prev_hash
        event2 = make_test_event(
            prev_hash=f"blake3:{'x' * 64}",  # Wrong prev_hash
            hash_=f"blake3:{'y' * 64}",
        )

        result = verify_chain_link(event2, event1)
        assert result.is_valid is False
        assert "broken" in result.error_message.lower()


class TestVerifyEventFull:
    """Tests for verify_event_full function (combined verification)."""

    def test_full_verification_genesis(self) -> None:
        """Full verification of genesis event succeeds."""
        unhashed_event = make_test_event()
        hashed_event = add_hash_to_event(unhashed_event, None, "blake3")

        result = verify_event_full(hashed_event, None)
        assert result.is_valid is True
        assert result.event_hash_valid is True
        assert result.chain_link_valid is True

    def test_full_verification_chain(self) -> None:
        """Full verification of chained events succeeds."""
        # Create chain of 2 events
        event1 = add_hash_to_event(make_test_event(), None, "blake3")
        event2 = add_hash_to_event(
            make_test_event(payload={"seq": 2}),
            event1.hash,
            "blake3",
        )

        # Verify event 2 against event 1
        result = verify_event_full(event2, event1)
        assert result.is_valid is True

    def test_full_verification_fails_on_hash_mismatch(self) -> None:
        """Full verification fails when hash is wrong."""
        event = make_test_event(
            prev_hash=GENESIS_PREV_HASH,
            hash_=f"blake3:{'w' * 64}",  # Wrong hash
        )

        result = verify_event_full(event, None)
        assert result.is_valid is False
        assert result.event_hash_valid is False


class TestAddHashToEvent:
    """Tests for add_hash_to_event function."""

    def test_adds_genesis_hash(self) -> None:
        """First event gets genesis prev_hash."""
        unhashed_event = make_test_event()
        hashed_event = add_hash_to_event(unhashed_event, None, "blake3")

        assert is_genesis_hash(hashed_event.prev_hash)
        assert hashed_event.hash.startswith("blake3:")
        assert hashed_event.has_hash() is True

    def test_adds_chain_hash(self) -> None:
        """Subsequent event gets previous hash as prev_hash."""
        event1 = add_hash_to_event(make_test_event(), None, "blake3")
        event2 = add_hash_to_event(
            make_test_event(payload={"seq": 2}),
            event1.hash,
            "blake3",
        )

        assert event2.prev_hash == event1.hash
        assert event2.hash.startswith("blake3:")

    def test_preserves_event_data(self) -> None:
        """Adding hash preserves all other event data."""
        original = make_test_event(
            event_type="witness.observation.recorded",
            payload={"observation": "test"},
        )
        hashed = add_hash_to_event(original, None, "blake3")

        assert hashed.event_id == original.event_id
        assert hashed.event_type == original.event_type
        assert hashed.actor_id == original.actor_id
        assert dict(hashed.payload) == dict(original.payload)

    def test_raises_for_already_hashed_event(self) -> None:
        """Cannot re-hash an already hashed event."""
        event = add_hash_to_event(make_test_event(), None, "blake3")

        with pytest.raises(ConstitutionalViolationError, match="already has hash"):
            add_hash_to_event(event, None, "blake3")

    def test_uses_sha256_algorithm(self) -> None:
        """Can create hash with SHA-256."""
        unhashed_event = make_test_event()
        hashed_event = add_hash_to_event(unhashed_event, None, "sha256")

        assert hashed_event.hash.startswith("sha256:")
        assert hashed_event.prev_hash.startswith("sha256:")


class TestChainEvents:
    """Tests for chain_events function."""

    def test_chains_empty_list(self) -> None:
        """Empty list returns empty list."""
        result = chain_events([])
        assert result == []

    def test_chains_single_event(self) -> None:
        """Single event gets genesis prev_hash."""
        events = [make_test_event()]
        result = chain_events(events)

        assert len(result) == 1
        assert is_genesis_hash(result[0].prev_hash)
        assert result[0].has_hash()

    def test_chains_multiple_events(self) -> None:
        """Multiple events are properly chained."""
        events = [
            make_test_event(payload={"seq": 1}),
            make_test_event(payload={"seq": 2}),
            make_test_event(payload={"seq": 3}),
        ]
        result = chain_events(events)

        assert len(result) == 3

        # First event has genesis prev_hash
        assert is_genesis_hash(result[0].prev_hash)

        # Each subsequent event links to previous
        assert result[1].prev_hash == result[0].hash
        assert result[2].prev_hash == result[1].hash

        # All have valid hashes
        for event in result:
            assert event.has_hash()
            verification = verify_event_hash(event)
            assert verification.is_valid

    def test_chain_verification_all_valid(self) -> None:
        """Entire chain verifies successfully."""
        events = [make_test_event(payload={"seq": i}) for i in range(5)]
        chained = chain_events(events)

        # Verify each event against its predecessor
        for i, event in enumerate(chained):
            prev = chained[i - 1] if i > 0 else None
            result = verify_event_full(event, prev)
            assert result.is_valid, f"Event {i} failed verification"


class TestGovernanceEventCreateWithHash:
    """Tests for GovernanceEvent.create_with_hash factory method."""

    def test_create_genesis_event(self) -> None:
        """create_with_hash creates genesis event with null prev_hash."""
        event = GovernanceEvent.create_with_hash(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"key": "value"},
            prev_event=None,
        )

        assert event.has_hash()
        assert is_genesis_hash(event.prev_hash)
        assert verify_event_hash(event).is_valid

    def test_create_chained_event(self) -> None:
        """create_with_hash creates chained event with prev_hash."""
        # Create first event
        event1 = GovernanceEvent.create_with_hash(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"seq": 1},
        )

        # Create second event chained to first
        event2 = GovernanceEvent.create_with_hash(
            event_id=uuid4(),
            event_type="executive.task.completed",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"seq": 2},
            prev_event=event1,
        )

        assert event2.prev_hash == event1.hash
        assert verify_chain_link(event2, event1).is_valid

    def test_create_with_sha256_algorithm(self) -> None:
        """create_with_hash can use SHA-256."""
        event = GovernanceEvent.create_with_hash(
            event_id=uuid4(),
            event_type="witness.observation.recorded",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"observation": "test"},
            algorithm="sha256",
        )

        assert event.hash.startswith("sha256:")


class TestHashVerificationResult:
    """Tests for HashVerificationResult dataclass."""

    def test_result_is_frozen(self) -> None:
        """HashVerificationResult is immutable."""
        result = HashVerificationResult(is_valid=True, event_hash_valid=True, chain_link_valid=True)
        with pytest.raises(Exception):
            result.is_valid = False  # type: ignore

    def test_result_with_error(self) -> None:
        """HashVerificationResult can include error details."""
        result = HashVerificationResult(
            is_valid=False,
            event_hash_valid=False,
            chain_link_valid=True,
            error_message="Hash mismatch detected",
            expected_hash="blake3:aaa...",
            actual_hash="blake3:bbb...",
        )
        assert result.is_valid is False
        assert "mismatch" in result.error_message
