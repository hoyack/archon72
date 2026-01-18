"""Unit tests for IncidentReportingService (Story 8.4, FR54, FR145, FR147).

Tests cover:
- create_halt_incident() with event writing (AC: 1)
- create_fork_incident() with event writing (AC: 2)
- create_override_threshold_incident() (AC: 3)
- resolve_incident() and publication eligibility (FR147, AC: 4)
- publish_incident() with 7-day rule (FR147)
- query_incidents() with filters (AC: 5)
- HALT CHECK FIRST pattern (CT-11)
- READS DURING HALT allowed (CT-13)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.incident_reporting_service import (
    IncidentNotFoundError,
    IncidentNotResolvedError,
    IncidentReportingService,
    PublicationNotEligibleError,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.incident_report import (
    DAILY_OVERRIDE_THRESHOLD,
    IncidentReport,
    IncidentStatus,
    IncidentType,
    TimelineEntry,
)
from src.infrastructure.stubs.incident_report_repository_stub import (
    IncidentReportRepositoryStub,
)


class TestIncidentReportingServiceCreate:
    """Tests for incident creation methods."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: AsyncMock,
    ) -> IncidentReportingService:
        """Create an incident reporting service with test dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_create_halt_incident_success(
        self,
        incident_service: IncidentReportingService,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test successful halt incident creation (AC: 1)."""
        halt_event_id = uuid4()

        result = await incident_service.create_halt_incident(
            halt_event_id=halt_event_id,
            cause="Database connection lost",
            impact="System operations halted for 30 minutes",
        )

        assert isinstance(result, IncidentReport)
        assert result.incident_type == IncidentType.HALT
        assert result.status == IncidentStatus.DRAFT
        assert "Database connection lost" in result.cause
        assert halt_event_id in result.related_event_ids

        # Event should be written (CT-12)
        event_writer.write_event.assert_called_once()

        # Incident should be stored
        stored = await incident_repo.get_by_id(result.incident_id)
        assert stored is not None

    @pytest.mark.asyncio
    async def test_create_halt_incident_with_timeline(
        self,
        incident_service: IncidentReportingService,
    ) -> None:
        """Test halt incident creation with custom timeline."""
        halt_event_id = uuid4()
        timeline = [
            TimelineEntry(
                timestamp=datetime.now(timezone.utc),
                description="Initial detection",
                actor="system.monitor",
            ),
        ]

        result = await incident_service.create_halt_incident(
            halt_event_id=halt_event_id,
            cause="Test cause",
            impact="Test impact",
            timeline=timeline,
        )

        assert len(result.timeline) == 1
        assert result.timeline[0].description == "Initial detection"

    @pytest.mark.asyncio
    async def test_create_halt_incident_during_halt(
        self,
        incident_service: IncidentReportingService,
        halt_checker: AsyncMock,
    ) -> None:
        """Test halt incident creation blocked during halt (CT-11)."""
        halt_checker.is_halted = AsyncMock(return_value=True)
        halt_checker.get_halt_reason = AsyncMock(return_value="System is halted")

        with pytest.raises(SystemHaltedError):
            await incident_service.create_halt_incident(
                halt_event_id=uuid4(),
                cause="Test cause",
                impact="Test impact",
            )

    @pytest.mark.asyncio
    async def test_create_fork_incident_success(
        self,
        incident_service: IncidentReportingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test successful fork incident creation (AC: 2)."""
        fork_event_id = uuid4()
        affected_events = [uuid4(), uuid4()]

        result = await incident_service.create_fork_incident(
            fork_event_id=fork_event_id,
            detection_details="Hash chain divergence detected",
            affected_events=affected_events,
        )

        assert isinstance(result, IncidentReport)
        assert result.incident_type == IncidentType.FORK
        assert result.status == IncidentStatus.DRAFT
        assert "Hash chain divergence" in result.cause

        # Event should be written (CT-12)
        event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_override_threshold_incident_success(
        self,
        incident_service: IncidentReportingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test successful override threshold incident creation (AC: 3)."""
        override_event_ids = [uuid4() for _ in range(4)]
        keeper_ids = ["keeper-001", "keeper-002"]

        result = await incident_service.create_override_threshold_incident(
            override_event_ids=override_event_ids,
            keeper_ids=keeper_ids,
        )

        assert isinstance(result, IncidentReport)
        assert result.incident_type == IncidentType.OVERRIDE_THRESHOLD
        assert result.status == IncidentStatus.DRAFT
        assert f">{DAILY_OVERRIDE_THRESHOLD}" in result.cause

        # Event should be written (CT-12)
        event_writer.write_event.assert_called_once()


class TestIncidentReportingServiceResolve:
    """Tests for incident resolution and publication."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: AsyncMock,
    ) -> IncidentReportingService:
        """Create an incident reporting service with test dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.fixture
    async def draft_incident(
        self,
        incident_service: IncidentReportingService,
    ) -> IncidentReport:
        """Create a draft incident for testing."""
        return await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Test cause",
            impact="Test impact",
        )

    @pytest.mark.asyncio
    async def test_resolve_incident_success(
        self,
        incident_service: IncidentReportingService,
        draft_incident: IncidentReport,
    ) -> None:
        """Test successful incident resolution (AC: 4)."""
        result = await incident_service.resolve_incident(
            incident_id=draft_incident.incident_id,
            response="Issue resolved by restarting the service",
            recommendations=["Implement better monitoring", "Add redundancy"],
        )

        assert result.status == IncidentStatus.PENDING_PUBLICATION
        assert result.resolution_at is not None
        assert "restarting" in result.response

    @pytest.mark.asyncio
    async def test_resolve_incident_not_found(
        self,
        incident_service: IncidentReportingService,
    ) -> None:
        """Test resolution of non-existent incident."""
        with pytest.raises(IncidentNotFoundError):
            await incident_service.resolve_incident(
                incident_id=uuid4(),
                response="Test response",
                recommendations=[],
            )

    @pytest.mark.asyncio
    async def test_publish_incident_not_resolved(
        self,
        incident_service: IncidentReportingService,
        draft_incident: IncidentReport,
    ) -> None:
        """Test publication of unresolved incident fails."""
        with pytest.raises(IncidentNotResolvedError):
            await incident_service.publish_incident(
                incident_id=draft_incident.incident_id,
            )

    @pytest.mark.asyncio
    async def test_publish_incident_before_7_days(
        self,
        incident_service: IncidentReportingService,
        draft_incident: IncidentReport,
    ) -> None:
        """Test publication before 7-day delay fails (FR147)."""
        # Resolve the incident
        await incident_service.resolve_incident(
            incident_id=draft_incident.incident_id,
            response="Issue resolved",
            recommendations=[],
        )

        # Try to publish immediately (should fail - not 7 days yet)
        with pytest.raises(PublicationNotEligibleError):
            await incident_service.publish_incident(
                incident_id=draft_incident.incident_id,
            )


class TestIncidentReportingServiceQuery:
    """Tests for incident query methods."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: AsyncMock,
    ) -> IncidentReportingService:
        """Create an incident reporting service with test dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_query_incidents_by_type(
        self,
        incident_service: IncidentReportingService,
    ) -> None:
        """Test querying incidents by type (AC: 5)."""
        # Create incidents of different types
        await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Test halt",
            impact="Test impact",
        )
        await incident_service.create_fork_incident(
            fork_event_id=uuid4(),
            detection_details="Test fork",
            affected_events=[],
        )

        # Query by type
        halts = await incident_service.query_incidents(
            incident_type=IncidentType.HALT,
        )
        forks = await incident_service.query_incidents(
            incident_type=IncidentType.FORK,
        )

        assert len(halts) == 1
        assert halts[0].incident_type == IncidentType.HALT
        assert len(forks) == 1
        assert forks[0].incident_type == IncidentType.FORK

    @pytest.mark.asyncio
    async def test_query_incidents_during_halt(
        self,
        incident_service: IncidentReportingService,
        halt_checker: AsyncMock,
    ) -> None:
        """Test queries work during halt (CT-13)."""
        # Create an incident first
        await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Test cause",
            impact="Test impact",
        )

        # Now simulate halt
        halt_checker.is_halted = AsyncMock(return_value=True)

        # Query should still work (CT-13: reads during halt)
        results = await incident_service.query_incidents()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_incident_by_id_during_halt(
        self,
        incident_service: IncidentReportingService,
        halt_checker: AsyncMock,
    ) -> None:
        """Test get by ID works during halt (CT-13)."""
        # Create an incident first
        incident = await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Test cause",
            impact="Test impact",
        )

        # Now simulate halt
        halt_checker.is_halted = AsyncMock(return_value=True)

        # Get should still work (CT-13: reads during halt)
        result = await incident_service.get_incident_by_id(incident.incident_id)
        assert result is not None
        assert result.incident_id == incident.incident_id


class TestIncidentReportingServiceTimeline:
    """Tests for timeline management."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Create a mock halt checker (not halted by default)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: AsyncMock,
    ) -> IncidentReportingService:
        """Create an incident reporting service with test dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_add_timeline_entry(
        self,
        incident_service: IncidentReportingService,
    ) -> None:
        """Test adding timeline entries to an incident."""
        # Create incident
        incident = await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Test cause",
            impact="Test impact",
        )

        initial_timeline_length = len(incident.timeline)

        # Add timeline entry
        entry = TimelineEntry(
            timestamp=datetime.now(timezone.utc),
            description="Additional investigation notes",
            actor="admin.operator",
        )

        result = await incident_service.add_timeline_entry(
            incident_id=incident.incident_id,
            entry=entry,
        )

        assert len(result.timeline) == initial_timeline_length + 1
        assert result.timeline[-1].description == "Additional investigation notes"

    @pytest.mark.asyncio
    async def test_add_timeline_entry_not_found(
        self,
        incident_service: IncidentReportingService,
    ) -> None:
        """Test adding timeline entry to non-existent incident."""
        entry = TimelineEntry(
            timestamp=datetime.now(timezone.utc),
            description="Test entry",
        )

        with pytest.raises(IncidentNotFoundError):
            await incident_service.add_timeline_entry(
                incident_id=uuid4(),
                entry=entry,
            )
