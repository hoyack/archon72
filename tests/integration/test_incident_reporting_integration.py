"""Integration tests for incident reporting (Story 8.4, FR54, FR145, FR147).

Tests the full incident reporting flow including:
- Halt incident creation with event witnessing
- Fork incident creation with event witnessing
- Override threshold incident creation (>3/day triggers)
- Publication after 7-day delay (FR147)
- Query API with filters

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable
- FR145: Following halt, fork, or >3 overrides/day: incident report required
- FR147: Incident reports SHALL be publicly available within 7 days of resolution
- CT-11: HALT CHECK FIRST - Check halt state before writes
- CT-12: Witnessing creates accountability - all events witnessed
- CT-13: Reads during halt always allowed
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.incident_reporting_service import (
    DuplicateIncidentError,
    IncidentNotFoundError,
    IncidentNotResolvedError,
    IncidentReportingService,
    PublicationNotEligibleError,
)
from src.domain.errors import SystemHaltedError
from src.domain.events.incident_report import (
    INCIDENT_REPORT_CREATED_EVENT_TYPE,
    INCIDENT_REPORT_PUBLISHED_EVENT_TYPE,
)
from src.domain.models.incident_report import (
    DAILY_OVERRIDE_THRESHOLD,
    PUBLICATION_DELAY_DAYS,
    IncidentReport,
    IncidentStatus,
    IncidentType,
    TimelineEntry,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.incident_report_repository_stub import (
    IncidentReportRepositoryStub,
)


class TestHaltIncidentIntegration:
    """Integration tests for halt incident creation (AC: 1)."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer that tracks calls."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a halt checker stub."""
        return HaltCheckerStub()

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> IncidentReportingService:
        """Create service with integrated dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_halt_incident_full_flow(
        self,
        incident_service: IncidentReportingService,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test complete halt incident creation flow (AC: 1)."""
        halt_event_id = uuid4()

        # Create halt incident
        incident = await incident_service.create_halt_incident(
            halt_event_id=halt_event_id,
            cause="Database connection pool exhausted",
            impact="All write operations suspended for 15 minutes",
            timeline=[
                TimelineEntry(
                    timestamp=datetime.now(timezone.utc) - timedelta(minutes=15),
                    description="First connection timeout detected",
                    actor="system.db_monitor",
                ),
                TimelineEntry(
                    timestamp=datetime.now(timezone.utc) - timedelta(minutes=10),
                    description="Halt triggered by connection failures",
                    actor="system.halt_trigger",
                ),
            ],
        )

        # Verify incident properties
        assert incident.incident_type == IncidentType.HALT
        assert incident.status == IncidentStatus.DRAFT
        assert halt_event_id in incident.related_event_ids
        assert len(incident.timeline) == 2

        # Verify event was written (CT-12)
        event_writer.write_event.assert_called_once()
        call_args = event_writer.write_event.call_args
        assert call_args.kwargs["event_type"] == INCIDENT_REPORT_CREATED_EVENT_TYPE

        # Verify incident is persisted
        stored = await incident_repo.get_by_id(incident.incident_id)
        assert stored is not None
        assert stored.incident_id == incident.incident_id

    @pytest.mark.asyncio
    async def test_halt_incident_blocked_during_halt(
        self,
        incident_service: IncidentReportingService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test halt incident creation blocked when halted (CT-11)."""
        # Trigger halt using set_halted method
        halt_checker.set_halted(True, "System under maintenance")

        with pytest.raises(SystemHaltedError) as exc_info:
            await incident_service.create_halt_incident(
                halt_event_id=uuid4(),
                cause="Test cause",
                impact="Test impact",
            )

        assert "CT-11" in str(exc_info.value)


class TestForkIncidentIntegration:
    """Integration tests for fork incident creation (AC: 2)."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer that tracks calls."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a halt checker stub."""
        return HaltCheckerStub()

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> IncidentReportingService:
        """Create service with integrated dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_fork_incident_full_flow(
        self,
        incident_service: IncidentReportingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test complete fork incident creation flow (AC: 2)."""
        fork_event_id = uuid4()
        affected_events = [uuid4() for _ in range(5)]

        # Create fork incident
        incident = await incident_service.create_fork_incident(
            fork_event_id=fork_event_id,
            detection_details="Hash chain divergence at sequence 1234",
            affected_events=affected_events,
        )

        # Verify incident properties
        assert incident.incident_type == IncidentType.FORK
        assert incident.status == IncidentStatus.DRAFT
        assert fork_event_id in incident.related_event_ids

        # Verify event was written (CT-12)
        event_writer.write_event.assert_called_once()


class TestOverrideThresholdIncidentIntegration:
    """Integration tests for override threshold incident creation (AC: 3)."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer that tracks calls."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a halt checker stub."""
        return HaltCheckerStub()

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> IncidentReportingService:
        """Create service with integrated dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_override_threshold_incident_full_flow(
        self,
        incident_service: IncidentReportingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test override threshold incident creation (AC: 3, FR145)."""
        # Simulate >3 overrides in a day
        override_event_ids = [uuid4() for _ in range(DAILY_OVERRIDE_THRESHOLD + 1)]
        keeper_ids = ["keeper-001", "keeper-002"]

        # Create override threshold incident
        incident = await incident_service.create_override_threshold_incident(
            override_event_ids=override_event_ids,
            keeper_ids=keeper_ids,
        )

        # Verify incident properties
        assert incident.incident_type == IncidentType.OVERRIDE_THRESHOLD
        assert incident.status == IncidentStatus.DRAFT
        assert f">{DAILY_OVERRIDE_THRESHOLD}" in incident.cause

        # Verify event was written (CT-12)
        event_writer.write_event.assert_called_once()


class TestPublicationIntegration:
    """Integration tests for incident publication (AC: 4, FR147)."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer that tracks calls."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a halt checker stub."""
        return HaltCheckerStub()

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> IncidentReportingService:
        """Create service with integrated dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_publication_full_flow(
        self,
        incident_service: IncidentReportingService,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
    ) -> None:
        """Test complete publication flow (AC: 4, FR147)."""
        # Create an incident with old creation date (8 days ago)
        old_incident = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Old halt incident",
            timeline=[],
            cause="Test cause",
            impact="Test impact",
            response="",
            prevention_recommendations=[],
            related_event_ids=[uuid4()],
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
            status=IncidentStatus.DRAFT,
        )
        await incident_repo.save(old_incident)

        # Resolve the incident
        resolved = await incident_service.resolve_incident(
            incident_id=old_incident.incident_id,
            response="Issue resolved by increasing connection pool",
            recommendations=["Monitor connection pool usage", "Set up alerts"],
        )

        assert resolved.status == IncidentStatus.PENDING_PUBLICATION
        assert resolved.resolution_at is not None

        # Check eligibility
        eligible = await incident_service.get_incidents_eligible_for_publication()
        assert len(eligible) == 1
        assert eligible[0].incident_id == old_incident.incident_id

        # Publish the incident
        event_writer.reset_mock()
        published = await incident_service.publish_incident(
            incident_id=old_incident.incident_id,
        )

        assert published.status == IncidentStatus.PUBLISHED
        assert published.published_at is not None

        # Verify publication event was written (CT-12)
        event_writer.write_event.assert_called_once()
        call_args = event_writer.write_event.call_args
        assert call_args.kwargs["event_type"] == INCIDENT_REPORT_PUBLISHED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_publication_with_redactions(
        self,
        incident_service: IncidentReportingService,
        incident_repo: IncidentReportRepositoryStub,
    ) -> None:
        """Test publication with field redactions (FR147)."""
        # Create an old incident
        old_incident = IncidentReport(
            incident_id=uuid4(),
            incident_type=IncidentType.HALT,
            title="Security-sensitive halt",
            timeline=[],
            cause="Security vulnerability exploited",
            impact="Potential data exposure",
            response="",
            prevention_recommendations=[],
            related_event_ids=[uuid4()],
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
            status=IncidentStatus.DRAFT,
        )
        await incident_repo.save(old_incident)

        # Resolve and publish with redactions
        await incident_service.resolve_incident(
            incident_id=old_incident.incident_id,
            response="Patched the vulnerability",
            recommendations=["Update security policies"],
        )

        published = await incident_service.publish_incident(
            incident_id=old_incident.incident_id,
            redacted_fields=["cause"],  # Redact security details
        )

        assert published.status == IncidentStatus.PUBLISHED
        assert "cause" in published.redacted_fields


class TestQueryIntegration:
    """Integration tests for incident query API (AC: 5)."""

    @pytest.fixture
    def incident_repo(self) -> IncidentReportRepositoryStub:
        """Create a fresh incident repository stub."""
        return IncidentReportRepositoryStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer that tracks calls."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a halt checker stub."""
        return HaltCheckerStub()

    @pytest.fixture
    def incident_service(
        self,
        incident_repo: IncidentReportRepositoryStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> IncidentReportingService:
        """Create service with integrated dependencies."""
        return IncidentReportingService(
            repository=incident_repo,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_query_by_type_and_date(
        self,
        incident_service: IncidentReportingService,
    ) -> None:
        """Test query with type and date filters (AC: 5)."""
        # Create multiple incidents
        await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Halt 1",
            impact="Impact 1",
        )
        await incident_service.create_fork_incident(
            fork_event_id=uuid4(),
            detection_details="Fork 1",
            affected_events=[],
        )
        await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Halt 2",
            impact="Impact 2",
        )

        # Query by type
        halts = await incident_service.query_incidents(
            incident_type=IncidentType.HALT,
        )
        assert len(halts) == 2

        forks = await incident_service.query_incidents(
            incident_type=IncidentType.FORK,
        )
        assert len(forks) == 1

        # Query all
        all_incidents = await incident_service.query_incidents()
        assert len(all_incidents) == 3

    @pytest.mark.asyncio
    async def test_query_during_halt_allowed(
        self,
        incident_service: IncidentReportingService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test queries work during halt (CT-13)."""
        # Create incident
        await incident_service.create_halt_incident(
            halt_event_id=uuid4(),
            cause="Test",
            impact="Test",
        )

        # Trigger halt using set_halted method
        halt_checker.set_halted(True, "Test halt")

        # Query should still work (CT-13: reads during halt)
        results = await incident_service.query_incidents()
        assert len(results) == 1

        # Get by ID should still work
        incident = results[0]
        fetched = await incident_service.get_incident_by_id(incident.incident_id)
        assert fetched is not None

        # Published list should still work
        published = await incident_service.get_published_incidents()
        assert isinstance(published, list)
