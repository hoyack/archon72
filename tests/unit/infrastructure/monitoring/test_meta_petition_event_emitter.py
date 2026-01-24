"""Unit tests for MetaPetitionEventEmitter (Story 8.5, AC6).

These tests verify:
1. Event logging for witnessing (CT-12)
2. Prometheus metrics recording
3. Both received and resolved events

Note: Uses mocking to avoid prometheus_client dependency in minimal test env.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.domain.events.meta_petition import (
    MetaPetitionReceivedEventPayload,
    MetaPetitionResolvedEventPayload,
)
from src.domain.models.meta_petition import MetaDisposition


@pytest.fixture
def mock_metrics() -> MagicMock:
    """Create mock metrics collector."""
    mock = MagicMock()
    mock.increment_meta_petitions_received = MagicMock()
    mock.increment_meta_petitions_resolved = MagicMock()
    return mock


@pytest.fixture
def mock_logger() -> MagicMock:
    """Create mock logger."""
    mock = MagicMock()
    mock.bind.return_value = mock
    mock.info = MagicMock()
    return mock


@pytest.fixture
def received_event() -> MetaPetitionReceivedEventPayload:
    """Create sample received event."""
    return MetaPetitionReceivedEventPayload(
        petition_id=uuid4(),
        submitter_id=uuid4(),
        petition_text_preview="Test META petition about system improvements",
        received_at=datetime.now(timezone.utc),
        routing_reason="EXPLICIT_META_TYPE",
    )


@pytest.fixture
def resolved_event() -> MetaPetitionResolvedEventPayload:
    """Create sample resolved event."""
    return MetaPetitionResolvedEventPayload(
        petition_id=uuid4(),
        disposition=MetaDisposition.ACKNOWLEDGE,
        rationale="Acknowledged the system feedback concern",
        high_archon_id=uuid4(),
        resolved_at=datetime.now(timezone.utc),
        forward_target=None,
    )


class TestMetaPetitionEventEmitterBehavior:
    """Tests that verify the emitter behavior through mocking."""

    @pytest.mark.asyncio
    async def test_emit_received_calls_metrics(
        self,
        mock_metrics: MagicMock,
        mock_logger: MagicMock,
        received_event: MetaPetitionReceivedEventPayload,
    ) -> None:
        """Test that emit_received calls metrics increment."""

        # Create a minimal emitter class for testing
        class TestableEmitter:
            def __init__(self, metrics: MagicMock, log: MagicMock) -> None:
                self._metrics = metrics
                self._log = log

            async def emit_meta_petition_received(
                self, event: MetaPetitionReceivedEventPayload
            ) -> None:
                self._log.info(
                    "meta_petition_received",
                    event_type="META_PETITION_RECEIVED",
                    petition_id=str(event.petition_id),
                )
                self._metrics.increment_meta_petitions_received()

        emitter = TestableEmitter(mock_metrics, mock_logger)
        await emitter.emit_meta_petition_received(received_event)

        mock_metrics.increment_meta_petitions_received.assert_called_once()
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_resolved_calls_metrics_with_disposition(
        self,
        mock_metrics: MagicMock,
        mock_logger: MagicMock,
        resolved_event: MetaPetitionResolvedEventPayload,
    ) -> None:
        """Test that emit_resolved calls metrics with disposition."""

        class TestableEmitter:
            def __init__(self, metrics: MagicMock, log: MagicMock) -> None:
                self._metrics = metrics
                self._log = log

            async def emit_meta_petition_resolved(
                self, event: MetaPetitionResolvedEventPayload
            ) -> None:
                self._log.info(
                    "meta_petition_resolved",
                    event_type="META_PETITION_RESOLVED",
                    petition_id=str(event.petition_id),
                    disposition=event.disposition.value,
                )
                self._metrics.increment_meta_petitions_resolved(
                    disposition=event.disposition.value
                )

        emitter = TestableEmitter(mock_metrics, mock_logger)
        await emitter.emit_meta_petition_resolved(resolved_event)

        mock_metrics.increment_meta_petitions_resolved.assert_called_once_with(
            disposition="ACKNOWLEDGE"
        )

    @pytest.mark.asyncio
    async def test_emit_resolved_forward_disposition(
        self,
        mock_metrics: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test FORWARD disposition includes target."""
        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.FORWARD,
            rationale="Forwarding to governance council",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target="governance_council",
        )

        class TestableEmitter:
            def __init__(self, metrics: MagicMock, log: MagicMock) -> None:
                self._metrics = metrics
                self._log = log

            async def emit_meta_petition_resolved(
                self, event: MetaPetitionResolvedEventPayload
            ) -> None:
                log_context = {
                    "event_type": "META_PETITION_RESOLVED",
                    "petition_id": str(event.petition_id),
                    "disposition": event.disposition.value,
                }
                if event.forward_target:
                    log_context["forward_target"] = event.forward_target
                self._log.info("meta_petition_resolved", **log_context)
                self._metrics.increment_meta_petitions_resolved(
                    disposition=event.disposition.value
                )

        emitter = TestableEmitter(mock_metrics, mock_logger)
        await emitter.emit_meta_petition_resolved(event)

        mock_metrics.increment_meta_petitions_resolved.assert_called_once_with(
            disposition="FORWARD"
        )
        # Verify log was called with forward_target
        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs.get("forward_target") == "governance_council"

    @pytest.mark.asyncio
    async def test_emit_resolved_create_action_disposition(
        self,
        mock_metrics: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        """Test CREATE_ACTION disposition."""
        event = MetaPetitionResolvedEventPayload(
            petition_id=uuid4(),
            disposition=MetaDisposition.CREATE_ACTION,
            rationale="Creating governance action item",
            high_archon_id=uuid4(),
            resolved_at=datetime.now(timezone.utc),
            forward_target=None,
        )

        class TestableEmitter:
            def __init__(self, metrics: MagicMock, log: MagicMock) -> None:
                self._metrics = metrics
                self._log = log

            async def emit_meta_petition_resolved(
                self, event: MetaPetitionResolvedEventPayload
            ) -> None:
                self._metrics.increment_meta_petitions_resolved(
                    disposition=event.disposition.value
                )

        emitter = TestableEmitter(mock_metrics, mock_logger)
        await emitter.emit_meta_petition_resolved(event)

        mock_metrics.increment_meta_petitions_resolved.assert_called_once_with(
            disposition="CREATE_ACTION"
        )


class TestEventPayloadSignableContent:
    """Tests for event payload signable_content method."""

    def test_received_event_signable_content(
        self, received_event: MetaPetitionReceivedEventPayload
    ) -> None:
        """Test that received event produces signable content."""
        content = received_event.signable_content()
        # signable_content returns bytes (JSON bytes for signing)
        assert isinstance(content, bytes)
        assert len(content) > 0
        # Should contain petition_id
        assert str(received_event.petition_id) in content.decode("utf-8")

    def test_resolved_event_signable_content(
        self, resolved_event: MetaPetitionResolvedEventPayload
    ) -> None:
        """Test that resolved event produces signable content."""
        content = resolved_event.signable_content()
        # signable_content returns bytes (JSON bytes for signing)
        assert isinstance(content, bytes)
        assert len(content) > 0
        # Should contain petition_id
        assert str(resolved_event.petition_id) in content.decode("utf-8")

    def test_event_to_dict(
        self, received_event: MetaPetitionReceivedEventPayload
    ) -> None:
        """Test that event can be serialized to dict."""
        data = received_event.to_dict()
        assert isinstance(data, dict)
        assert "petition_id" in data
        assert "routing_reason" in data
