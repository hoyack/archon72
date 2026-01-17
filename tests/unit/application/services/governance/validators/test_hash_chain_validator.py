"""Tests for hash chain validator.

Story: consent-gov-1.4: Write-Time Validation
AC2: Hash chain breaks rejected before append (with specific error)
AC7: Hash chain verification completes in ≤50ms
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.application.services.governance.validators.hash_chain_validator import (
    HashChainValidator,
)
from src.domain.governance.errors.validation_errors import HashChainBreakError
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.hash_algorithms import GENESIS_PREV_HASH


@pytest.fixture
def mock_ledger() -> AsyncMock:
    """Create a mock ledger port."""
    ledger = AsyncMock()
    ledger.get_latest_event = AsyncMock(return_value=None)
    return ledger


@pytest.fixture
def validator(mock_ledger: AsyncMock) -> HashChainValidator:
    """Create a validator with the mock ledger."""
    return HashChainValidator(mock_ledger)


@pytest.fixture
def bypass_validator(mock_ledger: AsyncMock) -> HashChainValidator:
    """Create a validator with validation bypassed."""
    return HashChainValidator(mock_ledger, skip_validation=True)


def make_event(*, prev_hash: str = "", event_hash: str = "") -> GovernanceEvent:
    """Create a test event with hash fields."""
    # Create event without hash first, then manually set hash fields
    event = GovernanceEvent.create(
        event_id=uuid4(),
        event_type="executive.task.accepted",
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        trace_id=str(uuid4()),
        payload={"test": "data"},
    )

    # Use create_with_hash if we want proper hashes
    if prev_hash or event_hash:
        from src.domain.governance.events.event_envelope import EventMetadata

        new_metadata = EventMetadata(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            actor_id=event.actor_id,
            schema_version=event.schema_version,
            trace_id=event.trace_id,
            prev_hash=prev_hash,
            hash=event_hash,
        )
        return GovernanceEvent(
            metadata=new_metadata,
            payload=dict(event.payload),
        )

    return event


def make_hashed_event(prev_hash: str | None = None) -> GovernanceEvent:
    """Create a properly hashed event."""
    return GovernanceEvent.create_with_hash(
        event_id=uuid4(),
        event_type="executive.task.accepted",
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        trace_id=str(uuid4()),
        payload={"test": "data"},
        prev_event=None if prev_hash is None else None,  # Genesis for None
    )


class TestHashChainValidator:
    """Tests for HashChainValidator."""

    @pytest.mark.asyncio
    async def test_genesis_event_passes(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Genesis event with proper genesis hash passes."""
        mock_ledger.get_latest_event.return_value = None

        event = make_hashed_event()
        await validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_event_without_hash_rejected(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Event without hash fields is rejected."""
        mock_ledger.get_latest_event.return_value = None

        event = make_event()  # No hash fields

        with pytest.raises(HashChainBreakError):
            await validator.validate(event)

    @pytest.mark.asyncio
    async def test_chained_event_passes(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Event correctly chained to previous event passes."""
        # Create genesis event
        genesis = make_hashed_event()

        # Create mock persisted event
        mock_persisted = MagicMock()
        mock_persisted.event = genesis
        mock_persisted.sequence = 1
        mock_ledger.get_latest_event.return_value = mock_persisted

        # Create next event chained to genesis
        from src.domain.governance.events.hash_chain import add_hash_to_event

        next_event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.completed",
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id=str(uuid4()),
            payload={"result": "done"},
        )
        chained_event = add_hash_to_event(next_event, genesis.hash)

        await validator.validate(chained_event)  # Should not raise

    @pytest.mark.asyncio
    async def test_broken_chain_rejected(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Event with wrong prev_hash is rejected."""
        # Create genesis event
        genesis = make_hashed_event()

        # Create mock persisted event
        mock_persisted = MagicMock()
        mock_persisted.event = genesis
        mock_persisted.sequence = 1
        mock_ledger.get_latest_event.return_value = mock_persisted

        # Create event with wrong prev_hash
        wrong_event = make_event(
            prev_hash="blake3:wrong12345678901234567890123456789012345678901234567890123456789a",
            event_hash="blake3:somehash234567890123456789012345678901234567890123456789012345",
        )

        with pytest.raises(HashChainBreakError) as exc_info:
            await validator.validate(wrong_event)

        assert exc_info.value.expected_prev_hash == genesis.hash
        assert "wrong" in exc_info.value.actual_prev_hash

    @pytest.mark.asyncio
    async def test_error_includes_latest_sequence(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Error includes latest sequence for debugging."""
        genesis = make_hashed_event()

        mock_persisted = MagicMock()
        mock_persisted.event = genesis
        mock_persisted.sequence = 42
        mock_ledger.get_latest_event.return_value = mock_persisted

        wrong_event = make_event(
            prev_hash="blake3:wrong12345678901234567890123456789012345678901234567890123456789a",
            event_hash="blake3:somehash234567890123456789012345678901234567890123456789012345",
        )

        with pytest.raises(HashChainBreakError) as exc_info:
            await validator.validate(wrong_event)

        assert exc_info.value.latest_sequence == 42

    @pytest.mark.asyncio
    async def test_skip_validation_allows_any_hash(
        self, bypass_validator: HashChainValidator
    ) -> None:
        """Skip validation mode allows any hash."""
        event = make_event()  # No hash fields
        await bypass_validator.validate(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_is_valid_chain_link_true(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """is_valid_chain_link returns True for valid chain."""
        mock_ledger.get_latest_event.return_value = None
        event = make_hashed_event()
        assert await validator.is_valid_chain_link(event) is True

    @pytest.mark.asyncio
    async def test_is_valid_chain_link_false(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """is_valid_chain_link returns False for invalid chain."""
        mock_ledger.get_latest_event.return_value = None
        event = make_event()  # No hash fields
        assert await validator.is_valid_chain_link(event) is False


class TestHashChainValidatorGenesis:
    """Tests for genesis event handling."""

    @pytest.mark.asyncio
    async def test_genesis_requires_genesis_hash(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Genesis event must use genesis prev_hash."""
        mock_ledger.get_latest_event.return_value = None

        # Event with non-genesis prev_hash when ledger is empty
        wrong_genesis = make_event(
            prev_hash="blake3:notgenesis345678901234567890123456789012345678901234567890123",
            event_hash="blake3:somehash234567890123456789012345678901234567890123456789012345",
        )

        with pytest.raises(HashChainBreakError) as exc_info:
            await validator.validate(wrong_genesis)

        assert GENESIS_PREV_HASH in exc_info.value.expected_prev_hash


class TestHashChainValidatorPerformance:
    """Performance tests for HashChainValidator."""

    @pytest.mark.asyncio
    async def test_validation_performance(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Hash chain verification completes in ≤50ms (AC7)."""
        import time

        mock_ledger.get_latest_event.return_value = None
        event = make_hashed_event()

        # Single validation should be fast
        start = time.perf_counter()
        await validator.validate(event)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms <= 50, f"Hash chain verification took {elapsed_ms}ms, limit is 50ms"

    @pytest.mark.asyncio
    async def test_bulk_validation_performance(
        self, validator: HashChainValidator, mock_ledger: AsyncMock
    ) -> None:
        """Multiple hash chain verifications are performant."""
        import time

        mock_ledger.get_latest_event.return_value = None
        events = [make_hashed_event() for _ in range(10)]

        start = time.perf_counter()
        for event in events:
            await validator.validate(event)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 10 validations should complete in reasonable time
        assert elapsed_ms < 500, f"10 validations took {elapsed_ms}ms"
