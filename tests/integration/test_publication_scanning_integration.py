"""Integration tests for publication scanning (Story 9.2, FR56).

Tests the complete publication scanning workflow including:
- Pre-publish scanning flow
- Event writing and witnessing
- Blocked publication handling
- Batch scanning workflow
- Scan history tracking

These tests use real implementations (stubs) instead of mocks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.publication_scanner import PublicationScanResultStatus
from src.application.services.publication_scanning_service import (
    PublicationScanningService,
)
from src.domain.errors.publication import (
    PublicationBlockedError,
    PublicationScanError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.publication_scan import (
    PUBLICATION_BLOCKED_EVENT_TYPE,
    PUBLICATION_SCANNED_EVENT_TYPE,
)
from src.domain.models.publication import (
    Publication,
    PublicationScanRequest,
    PublicationStatus,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.prohibited_language_scanner_stub import (
    ProhibitedLanguageScannerStub,
)
from src.infrastructure.stubs.publication_scanner_stub import (
    ConfigurablePublicationScannerStub,
    PublicationScannerStub,
)


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def scanner() -> ProhibitedLanguageScannerStub:
    """Create prohibited language scanner stub."""
    return ProhibitedLanguageScannerStub()


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer for integration tests."""
    writer = AsyncMock()
    writer.write_event.return_value = None
    return writer


@pytest.fixture
def service(
    scanner: ProhibitedLanguageScannerStub,
    mock_event_writer: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> PublicationScanningService:
    """Create publication scanning service with real stubs."""
    return PublicationScanningService(
        scanner=scanner,
        event_writer=mock_event_writer,
        halt_checker=halt_checker,
    )


class TestPrePublishFlow:
    """Tests for end-to-end pre-publish scanning flow."""

    @pytest.mark.asyncio
    async def test_clean_publication_passes_pre_publish(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test clean publication passes pre-publish scan (FR56, AC1)."""
        request = PublicationScanRequest(
            publication_id="pub-clean-001",
            content="This is a completely normal article about software.",
            title="Clean Article",
        )

        result = await service.scan_for_pre_publish(request)

        assert result.is_clean is True
        assert result.publication_id == "pub-clean-001"
        assert result.status == PublicationScanResultStatus.CLEAN

    @pytest.mark.asyncio
    async def test_publication_with_emergence_is_blocked(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test publication containing 'emergence' is blocked (FR56, AC3)."""
        request = PublicationScanRequest(
            publication_id="pub-blocked-001",
            content="Our AI system has achieved emergence.",
            title="Blocked Article",
        )

        with pytest.raises(PublicationBlockedError) as exc_info:
            await service.scan_for_pre_publish(request)

        assert "emergence" in exc_info.value.matched_terms
        assert exc_info.value.publication_id == "pub-blocked-001"

    @pytest.mark.asyncio
    async def test_publication_with_consciousness_is_blocked(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test publication containing 'consciousness' is blocked (FR56, AC3)."""
        request = PublicationScanRequest(
            publication_id="pub-blocked-002",
            content="The system exhibits signs of consciousness.",
            title="Another Blocked Article",
        )

        with pytest.raises(PublicationBlockedError) as exc_info:
            await service.scan_for_pre_publish(request)

        assert "consciousness" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_publication_with_sentience_is_blocked(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test publication containing 'sentience' is blocked (FR56, AC3)."""
        request = PublicationScanRequest(
            publication_id="pub-blocked-003",
            content="We believe our AI has achieved sentience.",
            title="Sentience Article",
        )

        with pytest.raises(PublicationBlockedError) as exc_info:
            await service.scan_for_pre_publish(request)

        assert "sentience" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_pre_publish_creates_event(
        self,
        service: PublicationScanningService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test pre-publish scan creates witnessed event (FR56, AC5)."""
        request = PublicationScanRequest(
            publication_id="pub-event-001",
            content="Normal content here.",
            title="Event Test Article",
        )

        await service.scan_for_pre_publish(request)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == PUBLICATION_SCANNED_EVENT_TYPE


class TestBlockedPublicationEvents:
    """Tests for blocked publication event creation (CT-12)."""

    @pytest.mark.asyncio
    async def test_blocked_publication_creates_blocked_event(
        self,
        service: PublicationScanningService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test blocked publication creates PUBLICATION_BLOCKED event."""
        request = PublicationScanRequest(
            publication_id="pub-blocked-event-001",
            content="Our AI achieved consciousness today.",
            title="Blocked Event Article",
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(request)

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == PUBLICATION_BLOCKED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_blocked_event_contains_publication_id(
        self,
        service: PublicationScanningService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test blocked event payload includes publication_id."""
        request = PublicationScanRequest(
            publication_id="pub-blocked-event-002",
            content="The emergence of our AI was surprising.",
            title="Publication ID Test",
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(request)

        payload = mock_event_writer.write_event.call_args.kwargs["payload"]
        assert payload["publication_id"] == "pub-blocked-event-002"

    @pytest.mark.asyncio
    async def test_blocked_event_contains_matched_terms(
        self,
        service: PublicationScanningService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test blocked event payload includes matched terms."""
        request = PublicationScanRequest(
            publication_id="pub-blocked-event-003",
            content="Emergence and consciousness are observed.",
            title="Multiple Terms Test",
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(request)

        payload = mock_event_writer.write_event.call_args.kwargs["payload"]
        assert "emergence" in payload["matched_terms"]
        assert "consciousness" in payload["matched_terms"]

    @pytest.mark.asyncio
    async def test_blocked_event_has_correct_scan_result(
        self,
        service: PublicationScanningService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test blocked event has scan_result = 'blocked'."""
        request = PublicationScanRequest(
            publication_id="pub-blocked-event-004",
            content="Our AI gained self-awareness.",
            title="Scan Result Test",
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(request)

        payload = mock_event_writer.write_event.call_args.kwargs["payload"]
        assert payload["scan_result"] == "blocked"


class TestCleanPublicationApproval:
    """Tests for clean publication approval flow."""

    @pytest.mark.asyncio
    async def test_clean_publication_returns_clean_status(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test clean publication returns CLEAN status."""
        request = PublicationScanRequest(
            publication_id="pub-clean-status-001",
            content="A technical article about programming.",
            title="Clean Status Test",
        )

        result = await service.scan_for_pre_publish(request)

        assert result.status == PublicationScanResultStatus.CLEAN

    @pytest.mark.asyncio
    async def test_clean_publication_has_empty_matched_terms(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test clean publication has no matched terms."""
        request = PublicationScanRequest(
            publication_id="pub-clean-terms-001",
            content="A normal article about databases.",
            title="Clean Terms Test",
        )

        result = await service.scan_for_pre_publish(request)

        assert result.matched_terms == ()
        assert result.terms_count == 0

    @pytest.mark.asyncio
    async def test_clean_publication_event_has_correct_result(
        self,
        service: PublicationScanningService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test clean publication event has scan_result = 'clean'."""
        request = PublicationScanRequest(
            publication_id="pub-clean-event-001",
            content="An article about cloud computing.",
            title="Clean Event Test",
        )

        await service.scan_for_pre_publish(request)

        payload = mock_event_writer.write_event.call_args.kwargs["payload"]
        assert payload["scan_result"] == "clean"
        assert payload["matched_terms"] == []


class TestBatchScanningWorkflow:
    """Tests for batch scanning workflow."""

    @pytest.mark.asyncio
    async def test_batch_scan_processes_all_publications(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test batch scan processes all publications."""
        requests = [
            PublicationScanRequest(
                publication_id=f"pub-batch-{i}",
                content=f"Clean content number {i}",
                title=f"Batch Article {i}",
            )
            for i in range(5)
        ]

        results = await service.batch_scan_publications(requests)

        assert len(results) == 5
        for result in results:
            assert result.is_clean is True

    @pytest.mark.asyncio
    async def test_batch_scan_identifies_blocked_publications(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test batch scan identifies blocked publications."""
        requests = [
            PublicationScanRequest(
                publication_id="pub-batch-clean",
                content="Clean content here.",
                title="Clean Article",
            ),
            PublicationScanRequest(
                publication_id="pub-batch-blocked",
                content="The emergence of AI is here.",
                title="Blocked Article",
            ),
            PublicationScanRequest(
                publication_id="pub-batch-clean-2",
                content="Another clean article.",
                title="Clean Article 2",
            ),
        ]

        results = await service.batch_scan_publications(requests)

        assert len(results) == 3
        assert results[0].is_clean is True
        assert results[1].is_blocked is True
        assert results[2].is_clean is True

    @pytest.mark.asyncio
    async def test_batch_scan_creates_events_for_all(
        self,
        service: PublicationScanningService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test batch scan creates events for all publications."""
        requests = [
            PublicationScanRequest(
                publication_id=f"pub-events-{i}",
                content=f"Content {i}",
                title=f"Article {i}",
            )
            for i in range(3)
        ]

        await service.batch_scan_publications(requests)

        assert mock_event_writer.write_event.call_count == 3


class TestScanHistoryTracking:
    """Tests for scan history tracking."""

    @pytest.mark.asyncio
    async def test_scan_history_tracks_clean_scan(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test scan history tracks clean scans."""
        request = PublicationScanRequest(
            publication_id="pub-history-clean",
            content="Clean content.",
            title="History Clean",
        )

        await service.scan_for_pre_publish(request)

        history = await service.get_scan_history("pub-history-clean")
        assert len(history) == 1
        assert history[0].is_clean is True

    @pytest.mark.asyncio
    async def test_scan_history_tracks_blocked_scan(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test scan history tracks blocked scans."""
        request = PublicationScanRequest(
            publication_id="pub-history-blocked",
            content="The emergence is real.",
            title="History Blocked",
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(request)

        history = await service.get_scan_history("pub-history-blocked")
        assert len(history) == 1
        assert history[0].is_blocked is True

    @pytest.mark.asyncio
    async def test_scan_history_orders_most_recent_first(
        self,
        service: PublicationScanningService,
        scanner: ProhibitedLanguageScannerStub,
    ) -> None:
        """Test scan history returns most recent first."""
        pub_id = "pub-history-ordered"

        # First scan - clean
        clean_request = PublicationScanRequest(
            publication_id=pub_id,
            content="Clean content.",
            title="First Scan",
        )
        await service.scan_for_pre_publish(clean_request)

        # Second scan - blocked (different content)
        blocked_request = PublicationScanRequest(
            publication_id=pub_id,
            content="Now with emergence.",
            title="Second Scan",
        )
        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(blocked_request)

        history = await service.get_scan_history(pub_id)
        assert len(history) == 2
        assert history[0].is_blocked is True  # Most recent
        assert history[1].is_clean is True


class TestPublicationScannerStub:
    """Tests for PublicationScannerStub."""

    @pytest.mark.asyncio
    async def test_stub_uses_real_scanner(self) -> None:
        """Test stub uses real ProhibitedLanguageScannerStub."""
        stub = PublicationScannerStub()
        request = PublicationScanRequest(
            publication_id="pub-stub-001",
            content="The emergence of AI.",
            title="Stub Test",
        )

        result = await stub.scan_publication(request)

        assert result.is_blocked is True
        assert "emergence" in result.matched_terms

    @pytest.mark.asyncio
    async def test_stub_tracks_scan_count(self) -> None:
        """Test stub tracks scan count."""
        stub = PublicationScannerStub()

        for i in range(3):
            request = PublicationScanRequest(
                publication_id=f"pub-count-{i}",
                content="Clean content.",
                title=f"Count Test {i}",
            )
            await stub.scan_publication(request)

        assert stub.scan_count == 3

    @pytest.mark.asyncio
    async def test_stub_can_configure_next_scan(self) -> None:
        """Test stub can configure next scan result."""
        stub = PublicationScannerStub()
        stub.configure_next_scan_blocked(("forced_term",))

        request = PublicationScanRequest(
            publication_id="pub-configured-001",
            content="Actually clean content.",
            title="Configured Test",
        )

        result = await stub.scan_publication(request)

        assert result.is_blocked is True
        assert "forced_term" in result.matched_terms

    @pytest.mark.asyncio
    async def test_stub_configuration_is_one_time(self) -> None:
        """Test stub configuration only affects next scan."""
        stub = PublicationScannerStub()
        stub.configure_next_scan_blocked(("one_time_term",))

        # First scan - uses configuration
        request1 = PublicationScanRequest(
            publication_id="pub-one-time-1",
            content="Clean content.",
            title="First",
        )
        result1 = await stub.scan_publication(request1)
        assert result1.is_blocked is True

        # Second scan - uses real scanner
        request2 = PublicationScanRequest(
            publication_id="pub-one-time-2",
            content="Clean content.",
            title="Second",
        )
        result2 = await stub.scan_publication(request2)
        assert result2.is_clean is True


class TestConfigurablePublicationScannerStub:
    """Tests for ConfigurablePublicationScannerStub."""

    @pytest.mark.asyncio
    async def test_configurable_stub_default_is_clean(self) -> None:
        """Test configurable stub defaults to clean results."""
        stub = ConfigurablePublicationScannerStub()
        request = PublicationScanRequest(
            publication_id="pub-default-001",
            content="Any content.",
            title="Default Test",
        )

        result = await stub.scan_publication(request)

        assert result.is_clean is True

    @pytest.mark.asyncio
    async def test_configurable_stub_can_be_set_to_blocked(self) -> None:
        """Test configurable stub can be set to return blocked."""
        stub = ConfigurablePublicationScannerStub()
        stub.configure_blocked_result(matched_terms=("custom_term",))

        request = PublicationScanRequest(
            publication_id="pub-blocked-config-001",
            content="Any content.",
            title="Blocked Config Test",
        )

        result = await stub.scan_publication(request)

        assert result.is_blocked is True
        assert "custom_term" in result.matched_terms

    @pytest.mark.asyncio
    async def test_configurable_stub_can_raise_exception(self) -> None:
        """Test configurable stub can raise exceptions."""
        stub = ConfigurablePublicationScannerStub()
        stub.configure_exception(RuntimeError("Test error"))

        request = PublicationScanRequest(
            publication_id="pub-error-001",
            content="Any content.",
            title="Error Test",
        )

        with pytest.raises(RuntimeError, match="Test error"):
            await stub.scan_publication(request)

    @pytest.mark.asyncio
    async def test_configurable_stub_tracks_scan_history(self) -> None:
        """Test configurable stub tracks scan history."""
        stub = ConfigurablePublicationScannerStub()
        request = PublicationScanRequest(
            publication_id="pub-history-stub-001",
            content="Content.",
            title="History Stub Test",
        )

        await stub.scan_publication(request)
        await stub.scan_publication(request)

        history = await stub.get_scan_history("pub-history-stub-001")
        assert len(history) == 2


class TestHaltCheckIntegration:
    """Tests for halt check integration (CT-11)."""

    @pytest.mark.asyncio
    async def test_scan_blocked_when_halted(
        self,
        service: PublicationScanningService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test scan is blocked when system is halted (CT-11)."""
        halt_checker.set_halted(True)

        request = PublicationScanRequest(
            publication_id="pub-halted-001",
            content="Any content.",
            title="Halted Test",
        )

        with pytest.raises(SystemHaltedError):
            await service.scan_for_pre_publish(request)

    @pytest.mark.asyncio
    async def test_batch_scan_blocked_when_halted(
        self,
        service: PublicationScanningService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test batch scan is blocked when system is halted."""
        halt_checker.set_halted(True)

        requests = [
            PublicationScanRequest(
                publication_id=f"pub-halted-batch-{i}",
                content="Content.",
                title=f"Halted Batch {i}",
            )
            for i in range(3)
        ]

        with pytest.raises(SystemHaltedError):
            await service.batch_scan_publications(requests)

    @pytest.mark.asyncio
    async def test_scan_proceeds_when_not_halted(
        self,
        service: PublicationScanningService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test scan proceeds when system is not halted."""
        halt_checker.set_halted(False)

        request = PublicationScanRequest(
            publication_id="pub-not-halted-001",
            content="Clean content.",
            title="Not Halted Test",
        )

        result = await service.scan_for_pre_publish(request)

        assert result.is_clean is True


class TestPublicationDomainModel:
    """Tests for Publication domain model integration."""

    def test_publication_from_scan_request(self) -> None:
        """Test creating scan request from publication."""
        now = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-model-001",
            content="Test content.",
            title="Test Title",
            author_agent_id="agent-001",
            status=PublicationStatus.DRAFT,
            created_at=now,
        )

        request = PublicationScanRequest.from_publication(pub)

        assert request.publication_id == pub.id
        assert request.content == pub.content
        assert request.title == pub.title

    def test_publication_status_transitions(self) -> None:
        """Test publication status transitions."""
        now = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-status-001",
            content="Test content.",
            title="Status Test",
            author_agent_id="agent-001",
            status=PublicationStatus.DRAFT,
            created_at=now,
        )

        # Transition to PENDING_REVIEW
        pub_review = pub.with_status(PublicationStatus.PENDING_REVIEW)
        assert pub_review.status == PublicationStatus.PENDING_REVIEW

        # Transition to BLOCKED
        pub_blocked = pub_review.with_status(PublicationStatus.BLOCKED)
        assert pub_blocked.status == PublicationStatus.BLOCKED

        # Transition to APPROVED
        pub_approved = pub_review.with_status(PublicationStatus.APPROVED)
        assert pub_approved.status == PublicationStatus.APPROVED
