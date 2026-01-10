"""Integration tests for CT-15 waiver (Story 9.8, SC-4, SR-10).

Tests for end-to-end CT-15 waiver documentation including:
- CT-15 waiver initialization
- Waiver documented event creation
- API endpoint functionality
- HALT CHECK FIRST across all services
- Event witnessing
- Idempotent initialization

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- CT-11: HALT CHECK FIRST
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.waiver import get_waiver_service, router as waiver_router
from src.application.services.waiver_documentation_service import (
    WAIVER_DOCUMENTATION_SYSTEM_AGENT_ID,
    WaiverDocumentationService,
)
from src.domain.errors import SystemHaltedError
from src.domain.events.waiver import (
    WAIVER_DOCUMENTED_EVENT_TYPE,
    WaiverStatus,
)
from src.infrastructure.initialization.ct15_waiver import (
    CT15_RATIONALE,
    CT15_STATEMENT,
    CT15_TARGET_PHASE,
    CT15_WAIVED_DESCRIPTION,
    CT15_WAIVER_ID,
    initialize_ct15_waiver,
)
from src.infrastructure.stubs.waiver_repository_stub import WaiverRepositoryStub


@pytest.fixture
def not_halted_checker() -> AsyncMock:
    """Create a halt checker that returns not halted."""
    checker = AsyncMock()
    checker.is_halted = AsyncMock(return_value=False)
    return checker


@pytest.fixture
def halted_checker() -> AsyncMock:
    """Create a halt checker that returns halted."""
    checker = AsyncMock()
    checker.is_halted = AsyncMock(return_value=True)
    return checker


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer that tracks calls."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def repository() -> WaiverRepositoryStub:
    """Create a fresh repository stub."""
    return WaiverRepositoryStub()


@pytest.fixture
def waiver_service(
    repository: WaiverRepositoryStub,
    mock_event_writer: AsyncMock,
    not_halted_checker: AsyncMock,
) -> WaiverDocumentationService:
    """Create a waiver service for testing."""
    return WaiverDocumentationService(
        waiver_repository=repository,
        event_writer=mock_event_writer,
        halt_checker=not_halted_checker,
    )


class TestCT15WaiverInitialization:
    """Tests for CT-15 waiver initialization (SC-4, SR-10)."""

    @pytest.mark.asyncio
    async def test_ct15_waiver_initialization_creates_waiver(
        self, waiver_service: WaiverDocumentationService
    ) -> None:
        """Test CT-15 waiver initialization creates the correct waiver."""
        result = await initialize_ct15_waiver(waiver_service)

        assert result.waiver_id == CT15_WAIVER_ID
        assert result.constitutional_truth_id == "CT-15"
        assert result.constitutional_truth_statement == CT15_STATEMENT
        assert result.what_is_waived == CT15_WAIVED_DESCRIPTION
        assert result.rationale == CT15_RATIONALE
        assert result.target_phase == CT15_TARGET_PHASE
        assert result.status == WaiverStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_ct15_waiver_initialization_is_idempotent(
        self,
        waiver_service: WaiverDocumentationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test CT-15 initialization can be called multiple times safely."""
        # First initialization
        result1 = await initialize_ct15_waiver(waiver_service)

        # Second initialization
        result2 = await initialize_ct15_waiver(waiver_service)

        assert result1.waiver_id == result2.waiver_id
        # Event should only be written once
        assert mock_event_writer.write_event.call_count == 1


class TestWaiverDocumentedEventCreation:
    """Tests for waiver documented event creation (CT-12)."""

    @pytest.mark.asyncio
    async def test_waiver_documentation_creates_event(
        self,
        waiver_service: WaiverDocumentationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test waiver documentation creates witnessed event."""
        await initialize_ct15_waiver(waiver_service)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == WAIVER_DOCUMENTED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_event_payload_contains_waiver_details(
        self,
        waiver_service: WaiverDocumentationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test event payload contains all waiver details."""
        await initialize_ct15_waiver(waiver_service)

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]

        assert payload["waiver_id"] == CT15_WAIVER_ID
        assert payload["constitutional_truth_id"] == "CT-15"
        assert payload["constitutional_truth_statement"] == CT15_STATEMENT
        assert payload["what_is_waived"] == CT15_WAIVED_DESCRIPTION
        assert payload["rationale"] == CT15_RATIONALE
        assert payload["target_phase"] == CT15_TARGET_PHASE
        assert payload["status"] == "ACTIVE"


class TestWaiverAPIEndpoints:
    """Tests for waiver API endpoints (AC3)."""

    @pytest.fixture
    def app(self, waiver_service: WaiverDocumentationService) -> FastAPI:
        """Create a FastAPI app with waiver routes."""
        app = FastAPI()
        app.include_router(waiver_router)

        # Override the dependency
        async def get_test_waiver_service() -> WaiverDocumentationService:
            return waiver_service

        app.dependency_overrides[get_waiver_service] = get_test_waiver_service
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_list_waivers_returns_empty_initially(
        self, client: TestClient
    ) -> None:
        """Test GET /v1/waivers returns empty list initially."""
        response = client.get("/v1/waivers")
        assert response.status_code == 200
        data = response.json()
        assert data["waivers"] == []
        assert data["total_count"] == 0

    @pytest.mark.asyncio
    async def test_list_waivers_returns_documented_waiver(
        self, client: TestClient, waiver_service: WaiverDocumentationService
    ) -> None:
        """Test GET /v1/waivers returns documented waivers."""
        await initialize_ct15_waiver(waiver_service)

        response = client.get("/v1/waivers")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["waivers"][0]["waiver_id"] == CT15_WAIVER_ID

    @pytest.mark.asyncio
    async def test_list_active_waivers(
        self, client: TestClient, waiver_service: WaiverDocumentationService
    ) -> None:
        """Test GET /v1/waivers/active returns only active waivers."""
        await initialize_ct15_waiver(waiver_service)

        response = client.get("/v1/waivers/active")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["waivers"][0]["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_get_waiver_by_id(
        self, client: TestClient, waiver_service: WaiverDocumentationService
    ) -> None:
        """Test GET /v1/waivers/{waiver_id} returns specific waiver."""
        await initialize_ct15_waiver(waiver_service)

        response = client.get(f"/v1/waivers/{CT15_WAIVER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["waiver_id"] == CT15_WAIVER_ID
        assert data["constitutional_truth_id"] == "CT-15"

    @pytest.mark.asyncio
    async def test_get_nonexistent_waiver_returns_404(
        self, client: TestClient
    ) -> None:
        """Test GET /v1/waivers/{waiver_id} returns 404 for nonexistent."""
        response = client.get("/v1/waivers/nonexistent")
        assert response.status_code == 404


class TestHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.fixture
    def halted_service(
        self,
        repository: WaiverRepositoryStub,
        mock_event_writer: AsyncMock,
        halted_checker: AsyncMock,
    ) -> WaiverDocumentationService:
        """Create a waiver service with halted checker."""
        return WaiverDocumentationService(
            waiver_repository=repository,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

    @pytest.mark.asyncio
    async def test_document_waiver_fails_when_halted(
        self, halted_service: WaiverDocumentationService
    ) -> None:
        """Test document_waiver raises SystemHaltedError when halted."""
        with pytest.raises(SystemHaltedError):
            await halted_service.document_waiver(
                waiver_id="TEST",
                ct_id="CT-1",
                ct_statement="Test",
                what_is_waived="Test",
                rationale="Test",
                target_phase="Phase 1",
            )

    @pytest.mark.asyncio
    async def test_get_waiver_fails_when_halted(
        self, halted_service: WaiverDocumentationService
    ) -> None:
        """Test get_waiver raises SystemHaltedError when halted."""
        with pytest.raises(SystemHaltedError):
            await halted_service.get_waiver("TEST")

    @pytest.mark.asyncio
    async def test_initialization_fails_when_halted(
        self, halted_service: WaiverDocumentationService
    ) -> None:
        """Test CT-15 initialization fails when halted."""
        with pytest.raises(SystemHaltedError):
            await initialize_ct15_waiver(halted_service)


class TestIdempotentInitialization:
    """Tests for idempotent waiver initialization."""

    @pytest.mark.asyncio
    async def test_multiple_initializations_same_waiver(
        self,
        waiver_service: WaiverDocumentationService,
        repository: WaiverRepositoryStub,
    ) -> None:
        """Test multiple initializations don't create duplicates."""
        await initialize_ct15_waiver(waiver_service)
        await initialize_ct15_waiver(waiver_service)
        await initialize_ct15_waiver(waiver_service)

        all_waivers = await repository.get_all_waivers()
        assert len(all_waivers) == 1

    @pytest.mark.asyncio
    async def test_initialization_preserves_original_values(
        self,
        waiver_service: WaiverDocumentationService,
    ) -> None:
        """Test re-initialization doesn't change original waiver."""
        first = await initialize_ct15_waiver(waiver_service)
        original_timestamp = first.documented_at

        # Simulate time passing
        second = await initialize_ct15_waiver(waiver_service)

        # Should return exact same waiver
        assert second.documented_at == original_timestamp


class TestWaiverConstants:
    """Tests for CT-15 waiver constants."""

    def test_waiver_id_constant(self) -> None:
        """Test CT-15 waiver ID constant."""
        assert CT15_WAIVER_ID == "CT-15-MVP-WAIVER"

    def test_statement_constant(self) -> None:
        """Test CT-15 statement constant."""
        assert CT15_STATEMENT == "Legitimacy requires consent"

    def test_target_phase_constant(self) -> None:
        """Test target phase constant."""
        assert CT15_TARGET_PHASE == "Phase 2 - Seeker Journey"

    def test_rationale_mentions_mvp(self) -> None:
        """Test rationale mentions MVP scope."""
        assert "MVP" in CT15_RATIONALE

    def test_waived_description_mentions_consent(self) -> None:
        """Test waived description mentions consent."""
        assert "consent" in CT15_WAIVED_DESCRIPTION.lower()
