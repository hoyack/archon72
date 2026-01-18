"""Unit tests for WaiverDocumentationService (Story 9.8, SC-4, SR-10).

Tests for waiver documentation operations with HALT CHECK FIRST pattern.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All waiver events witnessed
"""

from unittest.mock import AsyncMock

import pytest

from src.application.services.waiver_documentation_service import (
    WAIVER_DOCUMENTATION_SYSTEM_AGENT_ID,
    WaiverDocumentationService,
)
from src.domain.errors import SystemHaltedError
from src.domain.events.waiver import (
    WAIVER_DOCUMENTED_EVENT_TYPE,
    WaiverStatus,
)
from src.infrastructure.stubs.waiver_repository_stub import WaiverRepositoryStub


class TestWaiverDocumentationServiceHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.fixture
    def halted_checker(self) -> AsyncMock:
        """Create a halt checker that returns halted."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=True)
        return checker

    @pytest.fixture
    def not_halted_checker(self) -> AsyncMock:
        """Create a halt checker that returns not halted."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def repository(self) -> WaiverRepositoryStub:
        """Create a fresh repository stub."""
        return WaiverRepositoryStub()

    @pytest.mark.asyncio
    async def test_document_waiver_raises_when_halted(
        self,
        halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test document_waiver raises SystemHaltedError when halted."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError, match="System halted"):
            await service.document_waiver(
                waiver_id="TEST",
                ct_id="CT-1",
                ct_statement="Test",
                what_is_waived="Test",
                rationale="Test",
                target_phase="Phase 1",
            )

    @pytest.mark.asyncio
    async def test_get_waiver_raises_when_halted(
        self,
        halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test get_waiver raises SystemHaltedError when halted."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError, match="System halted"):
            await service.get_waiver("TEST")

    @pytest.mark.asyncio
    async def test_get_all_waivers_raises_when_halted(
        self,
        halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test get_all_waivers raises SystemHaltedError when halted."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError, match="System halted"):
            await service.get_all_waivers()

    @pytest.mark.asyncio
    async def test_get_active_waivers_raises_when_halted(
        self,
        halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test get_active_waivers raises SystemHaltedError when halted."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError, match="System halted"):
            await service.get_active_waivers()


class TestWaiverDocumentationServiceDocumentWaiver:
    """Tests for document_waiver method."""

    @pytest.fixture
    def not_halted_checker(self) -> AsyncMock:
        """Create a halt checker that returns not halted."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def repository(self) -> WaiverRepositoryStub:
        """Create a fresh repository stub."""
        return WaiverRepositoryStub()

    @pytest.mark.asyncio
    async def test_document_waiver_success(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test successful waiver documentation."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        result = await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Legitimacy requires consent",
            what_is_waived="Consent implementation",
            rationale="MVP scope",
            target_phase="Phase 2",
        )

        assert result.waiver_id == "CT-15-MVP-WAIVER"
        assert result.constitutional_truth_id == "CT-15"
        assert result.status == WaiverStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_document_waiver_creates_event(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test document_waiver creates witnessed event (CT-12)."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
        )

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == WAIVER_DOCUMENTED_EVENT_TYPE
        assert call_kwargs["agent_id"] == WAIVER_DOCUMENTATION_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_document_waiver_saves_to_repository(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test document_waiver saves waiver to repository."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
        )

        saved = await repository.get_waiver("CT-15-MVP-WAIVER")
        assert saved is not None
        assert saved.waiver_id == "CT-15-MVP-WAIVER"


class TestWaiverDocumentationServiceIdempotency:
    """Tests for idempotent waiver documentation."""

    @pytest.fixture
    def not_halted_checker(self) -> AsyncMock:
        """Create a halt checker that returns not halted."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def repository(self) -> WaiverRepositoryStub:
        """Create a fresh repository stub."""
        return WaiverRepositoryStub()

    @pytest.mark.asyncio
    async def test_document_waiver_is_idempotent(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test documenting same waiver twice returns existing."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        # First call
        result1 = await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
        )

        # Second call with same ID
        result2 = await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Different",  # Would be different if not idempotent
            what_is_waived="Different",
            rationale="Different",
            target_phase="Phase 3",
        )

        assert result1.waiver_id == result2.waiver_id
        assert (
            result2.constitutional_truth_statement == "Test"
        )  # Original value preserved

    @pytest.mark.asyncio
    async def test_document_waiver_only_creates_one_event(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test idempotent calls only create one event."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        # First call
        await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
        )

        # Second call
        await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
        )

        # Event should only be written once
        assert mock_event_writer.write_event.call_count == 1


class TestWaiverDocumentationServiceRetrieval:
    """Tests for waiver retrieval methods."""

    @pytest.fixture
    def not_halted_checker(self) -> AsyncMock:
        """Create a halt checker that returns not halted."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def repository(self) -> WaiverRepositoryStub:
        """Create a fresh repository stub."""
        return WaiverRepositoryStub()

    @pytest.mark.asyncio
    async def test_get_waiver_returns_existing(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test get_waiver returns existing waiver."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
        )

        result = await service.get_waiver("CT-15-MVP-WAIVER")
        assert result is not None
        assert result.waiver_id == "CT-15-MVP-WAIVER"

    @pytest.mark.asyncio
    async def test_get_waiver_returns_none_for_nonexistent(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test get_waiver returns None for nonexistent waiver."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        result = await service.get_waiver("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_waivers_returns_all(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test get_all_waivers returns all waivers."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        await service.document_waiver(
            waiver_id="WAIVER-1",
            ct_id="CT-1",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 1",
        )
        await service.document_waiver(
            waiver_id="WAIVER-2",
            ct_id="CT-2",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 1",
        )

        result = await service.get_all_waivers()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_waiver_exists_returns_true_for_existing(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test waiver_exists returns True for existing waiver."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
        )

        assert await service.waiver_exists("CT-15-MVP-WAIVER") is True

    @pytest.mark.asyncio
    async def test_waiver_exists_returns_false_for_nonexistent(
        self,
        not_halted_checker: AsyncMock,
        mock_event_writer: AsyncMock,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test waiver_exists returns False for nonexistent waiver."""
        service = WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=not_halted_checker,
        )

        assert await service.waiver_exists("nonexistent") is False
