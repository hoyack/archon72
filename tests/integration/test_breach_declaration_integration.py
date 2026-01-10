"""Integration tests for Breach Declaration (Story 6.1, FR30).

Tests the full breach declaration flow with stub implementations.

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events with
        breach_type, violated_requirement, detection_timestamp
- CT-11: HALT CHECK FIRST at every operation
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.breach_declaration_service import (
    BREACH_DECLARATION_SYSTEM_AGENT_ID,
    BreachDeclarationService,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BREACH_DECLARED_EVENT_TYPE,
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)
from src.infrastructure.stubs.breach_repository_stub import BreachRepositoryStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def breach_repository() -> BreachRepositoryStub:
    """Create a fresh breach repository stub."""
    return BreachRepositoryStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a halt checker that returns not halted."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def halted_checker() -> HaltCheckerStub:
    """Create a halt checker that returns halted."""
    return HaltCheckerStub(force_halted=True, halt_reason="Fork detected")


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer that captures write calls."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def service(
    breach_repository: BreachRepositoryStub,
    mock_event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> BreachDeclarationService:
    """Create a BreachDeclarationService with stub implementations."""
    return BreachDeclarationService(
        breach_repository=breach_repository,
        event_writer=mock_event_writer,
        halt_checker=halt_checker,
    )


@pytest.fixture
def halted_service(
    breach_repository: BreachRepositoryStub,
    mock_event_writer: AsyncMock,
    halted_checker: HaltCheckerStub,
) -> BreachDeclarationService:
    """Create a BreachDeclarationService in halted state."""
    return BreachDeclarationService(
        breach_repository=breach_repository,
        event_writer=mock_event_writer,
        halt_checker=halted_checker,
    )


class TestFR30BreachCreatesConstitutionalEvent:
    """Tests for FR30: Breach declarations create constitutional events."""

    @pytest.mark.asyncio
    async def test_fr30_breach_creates_constitutional_event(
        self,
        service: BreachDeclarationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Breach declaration creates a constitutional event (FR30, AC1)."""
        result = await service.declare_breach(
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            details={"expected": "abc", "actual": "def"},
        )

        # Event was written
        mock_event_writer.write_event.assert_called_once()

        # Event has correct type
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == BREACH_DECLARED_EVENT_TYPE

        # Payload exists
        assert result.breach_id is not None

    @pytest.mark.asyncio
    async def test_breach_event_includes_required_fields(
        self,
        service: BreachDeclarationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Breach event includes breach_type, violated_requirement, detection_timestamp (FR30, AC1)."""
        await service.declare_breach(
            breach_type=BreachType.THRESHOLD_VIOLATION,
            violated_requirement="FR33",
            severity=BreachSeverity.HIGH,
            details={"threshold": 10, "actual": 5},
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]

        # FR30 required fields
        assert "breach_type" in payload
        assert payload["breach_type"] == "THRESHOLD_VIOLATION"

        assert "violated_requirement" in payload
        assert payload["violated_requirement"] == "FR33"

        assert "detection_timestamp" in payload
        assert payload["detection_timestamp"] is not None


class TestBreachEventIsWitnessed:
    """Tests for CT-12: Breach events are witnessed."""

    @pytest.mark.asyncio
    async def test_breach_event_is_witnessed(
        self,
        service: BreachDeclarationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Breach event is written via EventWriterService for witnessing (CT-12, AC2)."""
        await service.declare_breach(
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            details={},
        )

        # EventWriterService.write_event() was called (which handles witnessing)
        mock_event_writer.write_event.assert_called_once()

        # Agent ID is the breach declaration system
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["agent_id"] == BREACH_DECLARATION_SYSTEM_AGENT_ID


class TestBreachEventIsImmutable:
    """Tests for AC2: Breach events are immutable."""

    @pytest.mark.asyncio
    async def test_breach_event_is_immutable(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Breach event payload is immutable (frozen dataclass) (AC2)."""
        result = await service.declare_breach(
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            details={},
        )

        # Attempt to modify should fail
        with pytest.raises(AttributeError):
            result.breach_type = BreachType.SIGNATURE_INVALID  # type: ignore[misc]

    @pytest.mark.asyncio
    async def test_breach_event_cannot_be_deleted(
        self,
        service: BreachDeclarationService,
        breach_repository: BreachRepositoryStub,
    ) -> None:
        """Breach events cannot be deleted from repository (AC2).

        Note: The stub doesn't have a delete method, demonstrating
        the append-only nature of breach storage.
        """
        result = await service.declare_breach(
            breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
            violated_requirement="FR80",
            severity=BreachSeverity.CRITICAL,
            details={},
        )

        # No delete method on repository (by design)
        assert not hasattr(breach_repository, "delete")
        assert not hasattr(breach_repository, "remove")

        # Breach remains in storage
        stored = await breach_repository.get_by_id(result.breach_id)
        assert stored is not None


class TestQueryAllBreaches:
    """Tests for AC3: Breach history queries."""

    @pytest.mark.asyncio
    async def test_query_all_breaches(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Can query all breach events (AC3)."""
        # Create multiple breaches
        await service.declare_breach(
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            details={},
        )
        await service.declare_breach(
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            details={},
        )
        await service.declare_breach(
            breach_type=BreachType.QUORUM_VIOLATION,
            violated_requirement="FR9",
            severity=BreachSeverity.MEDIUM,
            details={},
        )

        results = await service.list_all_breaches()

        assert len(results) == 3


class TestFilterBreachesByType:
    """Tests for AC3: Filtering by type."""

    @pytest.mark.asyncio
    async def test_filter_breaches_by_type(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Breaches are filterable by type (FR30, AC3)."""
        # Create breaches of different types
        await service.declare_breach(
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            details={},
        )
        await service.declare_breach(
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            details={},
        )
        await service.declare_breach(
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            details={},
        )

        # Filter by HASH_MISMATCH
        results = await service.filter_breaches(
            breach_type=BreachType.HASH_MISMATCH
        )

        assert len(results) == 2
        assert all(b.breach_type == BreachType.HASH_MISMATCH for b in results)


class TestFilterBreachesByDateRange:
    """Tests for AC3: Filtering by date range."""

    @pytest.mark.asyncio
    async def test_filter_breaches_by_date_range(
        self,
        breach_repository: BreachRepositoryStub,
        service: BreachDeclarationService,
    ) -> None:
        """Breaches are filterable by date range (FR30, AC3)."""
        now = datetime.now(timezone.utc)

        # Create breach with known timestamp in the past
        old_breach = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=30),
            details={},
        )
        await breach_repository.save(old_breach)

        # Create recent breach via service
        await service.declare_breach(
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            details={},
        )

        # Filter for last 7 days only
        start = now - timedelta(days=7)
        end = now + timedelta(hours=1)

        results = await service.filter_breaches(
            start_date=start,
            end_date=end,
        )

        # Should only get the recent breach
        assert len(results) == 1
        assert results[0].breach_type == BreachType.SIGNATURE_INVALID


class TestFilterBreachesByTypeAndDate:
    """Tests for AC3: Combined type and date filtering."""

    @pytest.mark.asyncio
    async def test_filter_breaches_by_type_and_date(
        self,
        breach_repository: BreachRepositoryStub,
        service: BreachDeclarationService,
    ) -> None:
        """Breaches are filterable by both type and date (FR30, AC3)."""
        now = datetime.now(timezone.utc)

        # Old HASH_MISMATCH (out of date range)
        old_hash = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=30),
            details={},
        )
        await breach_repository.save(old_hash)

        # Recent HASH_MISMATCH (in range, correct type)
        recent_hash = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=3),
            details={},
        )
        await breach_repository.save(recent_hash)

        # Recent SIGNATURE_INVALID (in range, wrong type)
        recent_sig = BreachEventPayload(
            breach_id=uuid4(),
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=now - timedelta(days=3),
            details={},
        )
        await breach_repository.save(recent_sig)

        # Filter for HASH_MISMATCH in last 7 days
        start = now - timedelta(days=7)
        end = now + timedelta(hours=1)

        results = await service.filter_breaches(
            breach_type=BreachType.HASH_MISMATCH,
            start_date=start,
            end_date=end,
        )

        assert len(results) == 1
        assert results[0].breach_id == recent_hash.breach_id


class TestHaltCheckPreventsOperations:
    """Tests for CT-11: HALT CHECK FIRST."""

    @pytest.mark.asyncio
    async def test_halt_check_prevents_declaration_during_halt(
        self,
        halted_service: BreachDeclarationService,
    ) -> None:
        """Halt check prevents breach declaration during system halt (CT-11)."""
        with pytest.raises(SystemHaltedError) as exc_info:
            await halted_service.declare_breach(
                breach_type=BreachType.OVERRIDE_ABUSE,
                violated_requirement="FR86",
                severity=BreachSeverity.HIGH,
                details={},
            )

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_check_prevents_query_during_halt(
        self,
        halted_service: BreachDeclarationService,
    ) -> None:
        """Halt check prevents breach queries during system halt (CT-11)."""
        with pytest.raises(SystemHaltedError):
            await halted_service.list_all_breaches()

        with pytest.raises(SystemHaltedError):
            await halted_service.filter_breaches(
                breach_type=BreachType.HASH_MISMATCH
            )

        with pytest.raises(SystemHaltedError):
            await halted_service.get_breach_by_id(uuid4())


class TestMultipleBreachesSameType:
    """Tests for multiple breaches of the same type."""

    @pytest.mark.asyncio
    async def test_multiple_breaches_same_type(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Can create multiple breaches of the same type."""
        # Create 5 HASH_MISMATCH breaches
        breach_ids = []
        for i in range(5):
            result = await service.declare_breach(
                breach_type=BreachType.HASH_MISMATCH,
                violated_requirement="FR82",
                severity=BreachSeverity.CRITICAL,
                details={"occurrence": i},
            )
            breach_ids.append(result.breach_id)

        # All IDs are unique
        assert len(set(breach_ids)) == 5

        # All can be queried
        results = await service.filter_breaches(
            breach_type=BreachType.HASH_MISMATCH
        )
        assert len(results) == 5


class TestBreachWithSourceEventLinkage:
    """Tests for breach linkage to source events."""

    @pytest.mark.asyncio
    async def test_breach_with_source_event_linkage(
        self,
        service: BreachDeclarationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Breach can link to the source event that triggered it."""
        source_event_id = uuid4()

        result = await service.declare_breach(
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            details={"agent_id": "archon-42"},
            source_event_id=source_event_id,
        )

        # Breach has source event linkage
        assert result.source_event_id == source_event_id

        # Event payload includes source_event_id
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert "source_event_id" in payload
        assert payload["source_event_id"] == str(source_event_id)


class TestBreachSeverityLevels:
    """Tests for different breach severity levels."""

    @pytest.mark.asyncio
    async def test_critical_severity_breach(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Can create CRITICAL severity breach."""
        result = await service.declare_breach(
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            details={},
        )
        assert result.severity == BreachSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_high_severity_breach(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Can create HIGH severity breach."""
        result = await service.declare_breach(
            breach_type=BreachType.THRESHOLD_VIOLATION,
            violated_requirement="FR33",
            severity=BreachSeverity.HIGH,
            details={},
        )
        assert result.severity == BreachSeverity.HIGH

    @pytest.mark.asyncio
    async def test_medium_severity_breach(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Can create MEDIUM severity breach."""
        result = await service.declare_breach(
            breach_type=BreachType.WITNESS_COLLUSION,
            violated_requirement="FR59",
            severity=BreachSeverity.MEDIUM,
            details={},
        )
        assert result.severity == BreachSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_low_severity_breach(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """Can create LOW severity breach."""
        result = await service.declare_breach(
            breach_type=BreachType.QUORUM_VIOLATION,
            violated_requirement="FR9",
            severity=BreachSeverity.LOW,
            details={},
        )
        assert result.severity == BreachSeverity.LOW


class TestAllBreachTypes:
    """Tests for all breach type variants."""

    @pytest.mark.asyncio
    async def test_all_breach_types_can_be_declared(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """All breach types can be declared."""
        breach_configs = [
            (BreachType.THRESHOLD_VIOLATION, "FR33"),
            (BreachType.WITNESS_COLLUSION, "FR59"),
            (BreachType.HASH_MISMATCH, "FR82"),
            (BreachType.SIGNATURE_INVALID, "FR104"),
            (BreachType.CONSTITUTIONAL_CONSTRAINT, "FR80"),
            (BreachType.TIMING_VIOLATION, "FR21"),
            (BreachType.QUORUM_VIOLATION, "FR9"),
            (BreachType.OVERRIDE_ABUSE, "FR86"),
        ]

        for breach_type, requirement in breach_configs:
            result = await service.declare_breach(
                breach_type=breach_type,
                violated_requirement=requirement,
                severity=BreachSeverity.HIGH,
                details={},
            )
            assert result.breach_type == breach_type
            assert result.violated_requirement == requirement

        # All 8 types created
        all_breaches = await service.list_all_breaches()
        assert len(all_breaches) == 8
