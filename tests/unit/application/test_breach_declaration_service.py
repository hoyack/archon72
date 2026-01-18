"""Unit tests for BreachDeclarationService (Story 6.1, FR30).

Tests for breach declaration, witnessing, and query operations.

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events
- CT-11: HALT CHECK FIRST at every operation
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.breach_declaration_service import (
    BREACH_DECLARATION_SYSTEM_AGENT_ID,
    BreachDeclarationService,
)
from src.domain.errors.breach import BreachDeclarationError, BreachQueryError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BREACH_DECLARED_EVENT_TYPE,
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)


@pytest.fixture
def mock_breach_repository() -> AsyncMock:
    """Create a mock breach repository."""
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_all = AsyncMock(return_value=[])
    repo.filter_by_type = AsyncMock(return_value=[])
    repo.filter_by_date_range = AsyncMock(return_value=[])
    repo.filter_by_type_and_date = AsyncMock(return_value=[])
    repo.count_unacknowledged_in_window = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create a mock halt checker that returns not halted."""
    checker = AsyncMock()
    checker.is_halted = AsyncMock(return_value=False)
    checker.get_halt_reason = AsyncMock(return_value=None)
    return checker


@pytest.fixture
def mock_halt_checker_halted() -> AsyncMock:
    """Create a mock halt checker that returns halted."""
    checker = AsyncMock()
    checker.is_halted = AsyncMock(return_value=True)
    checker.get_halt_reason = AsyncMock(return_value="Fork detected")
    return checker


@pytest.fixture
def service(
    mock_breach_repository: AsyncMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
) -> BreachDeclarationService:
    """Create a BreachDeclarationService with mocked dependencies."""
    return BreachDeclarationService(
        breach_repository=mock_breach_repository,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
    )


@pytest.fixture
def halted_service(
    mock_breach_repository: AsyncMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker_halted: AsyncMock,
) -> BreachDeclarationService:
    """Create a BreachDeclarationService with halted state."""
    return BreachDeclarationService(
        breach_repository=mock_breach_repository,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker_halted,
    )


class TestDeclareBreach:
    """Tests for declare_breach() method."""

    @pytest.mark.asyncio
    async def test_declare_breach_creates_payload_with_required_fields(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """declare_breach() creates payload with all required fields (FR30)."""
        result = await service.declare_breach(
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            details={"expected": "abc", "actual": "def"},
        )

        assert result.breach_id is not None
        assert result.breach_type == BreachType.HASH_MISMATCH
        assert result.violated_requirement == "FR82"
        assert result.severity == BreachSeverity.CRITICAL
        assert result.detection_timestamp is not None
        assert result.details == {"expected": "abc", "actual": "def"}
        assert result.source_event_id is None

    @pytest.mark.asyncio
    async def test_declare_breach_includes_source_event_id(
        self,
        service: BreachDeclarationService,
    ) -> None:
        """declare_breach() includes source_event_id when provided."""
        source_id = uuid4()

        result = await service.declare_breach(
            breach_type=BreachType.SIGNATURE_INVALID,
            violated_requirement="FR104",
            severity=BreachSeverity.CRITICAL,
            details={},
            source_event_id=source_id,
        )

        assert result.source_event_id == source_id

    @pytest.mark.asyncio
    async def test_declare_breach_writes_witnessed_event(
        self,
        service: BreachDeclarationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """declare_breach() writes event via EventWriterService (CT-12)."""
        await service.declare_breach(
            breach_type=BreachType.THRESHOLD_VIOLATION,
            violated_requirement="FR33",
            severity=BreachSeverity.HIGH,
            details={"threshold": 10, "actual": 5},
        )

        mock_event_writer.write_event.assert_called_once()
        call_args = mock_event_writer.write_event.call_args
        assert call_args.kwargs["event_type"] == BREACH_DECLARED_EVENT_TYPE
        assert call_args.kwargs["agent_id"] == BREACH_DECLARATION_SYSTEM_AGENT_ID
        assert "breach_type" in call_args.kwargs["payload"]
        assert call_args.kwargs["payload"]["breach_type"] == "THRESHOLD_VIOLATION"

    @pytest.mark.asyncio
    async def test_declare_breach_saves_to_repository(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """declare_breach() saves breach to repository."""
        result = await service.declare_breach(
            breach_type=BreachType.QUORUM_VIOLATION,
            violated_requirement="FR9",
            severity=BreachSeverity.MEDIUM,
            details={},
        )

        mock_breach_repository.save.assert_called_once()
        saved_breach = mock_breach_repository.save.call_args[0][0]
        assert saved_breach.breach_id == result.breach_id

    @pytest.mark.asyncio
    async def test_declare_breach_halted_raises_system_halted_error(
        self,
        halted_service: BreachDeclarationService,
    ) -> None:
        """declare_breach() raises SystemHaltedError when halted (CT-11)."""
        with pytest.raises(SystemHaltedError) as exc_info:
            await halted_service.declare_breach(
                breach_type=BreachType.OVERRIDE_ABUSE,
                violated_requirement="FR86",
                severity=BreachSeverity.HIGH,
                details={},
            )

        assert "CT-11" in str(exc_info.value)
        assert "halted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_declare_breach_event_writer_failure_raises_declaration_error(
        self,
        service: BreachDeclarationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """declare_breach() raises BreachDeclarationError on event writer failure."""
        mock_event_writer.write_event.side_effect = Exception("Write failed")

        with pytest.raises(BreachDeclarationError) as exc_info:
            await service.declare_breach(
                breach_type=BreachType.TIMING_VIOLATION,
                violated_requirement="FR21",
                severity=BreachSeverity.HIGH,
                details={},
            )

        assert "FR30" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_declare_breach_repository_failure_raises_declaration_error(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """declare_breach() raises BreachDeclarationError on repository failure."""
        mock_breach_repository.save.side_effect = Exception("Save failed")

        with pytest.raises(BreachDeclarationError) as exc_info:
            await service.declare_breach(
                breach_type=BreachType.WITNESS_COLLUSION,
                violated_requirement="FR59",
                severity=BreachSeverity.MEDIUM,
                details={},
            )

        assert "FR30" in str(exc_info.value)


class TestGetBreachById:
    """Tests for get_breach_by_id() method."""

    @pytest.mark.asyncio
    async def test_get_breach_returns_breach_when_found(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """get_breach_by_id() returns breach when found."""
        breach_id = uuid4()
        expected = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.HASH_MISMATCH,
            violated_requirement="FR82",
            severity=BreachSeverity.CRITICAL,
            detection_timestamp=datetime.now(timezone.utc),
            details=MappingProxyType({}),
        )
        mock_breach_repository.get_by_id.return_value = expected

        result = await service.get_breach_by_id(breach_id)

        assert result == expected
        mock_breach_repository.get_by_id.assert_called_once_with(breach_id)

    @pytest.mark.asyncio
    async def test_get_breach_returns_none_when_not_found(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """get_breach_by_id() returns None when breach not found."""
        mock_breach_repository.get_by_id.return_value = None

        result = await service.get_breach_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_breach_halted_raises_system_halted_error(
        self,
        halted_service: BreachDeclarationService,
    ) -> None:
        """get_breach_by_id() raises SystemHaltedError when halted (CT-11)."""
        with pytest.raises(SystemHaltedError):
            await halted_service.get_breach_by_id(uuid4())

    @pytest.mark.asyncio
    async def test_get_breach_repository_failure_raises_query_error(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """get_breach_by_id() raises BreachQueryError on repository failure."""
        mock_breach_repository.get_by_id.side_effect = Exception("Query failed")

        with pytest.raises(BreachQueryError) as exc_info:
            await service.get_breach_by_id(uuid4())

        assert "FR30" in str(exc_info.value)


class TestListAllBreaches:
    """Tests for list_all_breaches() method."""

    @pytest.mark.asyncio
    async def test_list_all_breaches_returns_all(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """list_all_breaches() returns all breaches."""
        breaches = [
            BreachEventPayload(
                breach_id=uuid4(),
                breach_type=BreachType.HASH_MISMATCH,
                violated_requirement="FR82",
                severity=BreachSeverity.CRITICAL,
                detection_timestamp=datetime.now(timezone.utc),
                details=MappingProxyType({}),
            ),
            BreachEventPayload(
                breach_id=uuid4(),
                breach_type=BreachType.SIGNATURE_INVALID,
                violated_requirement="FR104",
                severity=BreachSeverity.CRITICAL,
                detection_timestamp=datetime.now(timezone.utc),
                details=MappingProxyType({}),
            ),
        ]
        mock_breach_repository.list_all.return_value = breaches

        result = await service.list_all_breaches()

        assert len(result) == 2
        assert result == breaches

    @pytest.mark.asyncio
    async def test_list_all_breaches_halted_raises_system_halted_error(
        self,
        halted_service: BreachDeclarationService,
    ) -> None:
        """list_all_breaches() raises SystemHaltedError when halted (CT-11)."""
        with pytest.raises(SystemHaltedError):
            await halted_service.list_all_breaches()


class TestFilterBreaches:
    """Tests for filter_breaches() method (FR30)."""

    @pytest.mark.asyncio
    async def test_filter_by_type_only(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """filter_breaches() filters by type only."""
        await service.filter_breaches(breach_type=BreachType.HASH_MISMATCH)

        mock_breach_repository.filter_by_type.assert_called_once_with(
            BreachType.HASH_MISMATCH
        )

    @pytest.mark.asyncio
    async def test_filter_by_date_range_only(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """filter_breaches() filters by date range only."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)

        await service.filter_breaches(start_date=start, end_date=end)

        mock_breach_repository.filter_by_date_range.assert_called_once_with(
            start=start, end=end
        )

    @pytest.mark.asyncio
    async def test_filter_by_type_and_date(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """filter_breaches() filters by both type and date range."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)

        await service.filter_breaches(
            breach_type=BreachType.THRESHOLD_VIOLATION,
            start_date=start,
            end_date=end,
        )

        mock_breach_repository.filter_by_type_and_date.assert_called_once_with(
            breach_type=BreachType.THRESHOLD_VIOLATION,
            start=start,
            end=end,
        )

    @pytest.mark.asyncio
    async def test_filter_no_filters_returns_all(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """filter_breaches() with no filters returns all breaches."""
        await service.filter_breaches()

        mock_breach_repository.list_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_breaches_halted_raises_system_halted_error(
        self,
        halted_service: BreachDeclarationService,
    ) -> None:
        """filter_breaches() raises SystemHaltedError when halted (CT-11)."""
        with pytest.raises(SystemHaltedError):
            await halted_service.filter_breaches(breach_type=BreachType.HASH_MISMATCH)


class TestCountUnacknowledgedBreaches:
    """Tests for count_unacknowledged_breaches() method."""

    @pytest.mark.asyncio
    async def test_count_unacknowledged_breaches_default_window(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """count_unacknowledged_breaches() uses default 90-day window."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 5

        result = await service.count_unacknowledged_breaches()

        assert result == 5
        mock_breach_repository.count_unacknowledged_in_window.assert_called_once_with(
            90
        )

    @pytest.mark.asyncio
    async def test_count_unacknowledged_breaches_custom_window(
        self,
        service: BreachDeclarationService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """count_unacknowledged_breaches() uses custom window."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 3

        result = await service.count_unacknowledged_breaches(window_days=30)

        assert result == 3
        mock_breach_repository.count_unacknowledged_in_window.assert_called_once_with(
            30
        )

    @pytest.mark.asyncio
    async def test_count_unacknowledged_breaches_halted_raises_system_halted_error(
        self,
        halted_service: BreachDeclarationService,
    ) -> None:
        """count_unacknowledged_breaches() raises SystemHaltedError when halted (CT-11)."""
        with pytest.raises(SystemHaltedError):
            await halted_service.count_unacknowledged_breaches()
