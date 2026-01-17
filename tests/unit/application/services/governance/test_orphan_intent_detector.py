"""Unit tests for OrphanIntentDetector service.

Story: consent-gov-1.6: Two-Phase Event Emission

Tests the OrphanIntentDetector service that finds and auto-resolves
orphaned intents (intents without corresponding outcome events).

Constitutional Reference:
- AD-3: Two-phase event emission
- NFR-CONST-07: No intent remains unresolved indefinitely
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.orphan_intent_detector import (
    OrphanIntentDetector,
    OrphanResolution,
)


@pytest.fixture
def mock_emitter() -> MagicMock:
    """Create a mock TwoPhaseEventEmitter.

    Note: get_pending_intents_with_age is synchronous, so we use MagicMock.
    emit_failure is async, so we configure it as AsyncMock.
    """
    emitter = MagicMock()
    emitter.emit_failure = AsyncMock()
    emitter.get_pending_intents_with_age.return_value = []
    return emitter


@pytest.fixture
def mock_time_authority() -> MagicMock:
    """Create a mock time authority."""
    time_authority = MagicMock()
    time_authority.now.return_value = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
    return time_authority


@pytest.fixture
def detector(
    mock_emitter: MagicMock, mock_time_authority: MagicMock
) -> OrphanIntentDetector:
    """Create an OrphanIntentDetector with mocked dependencies."""
    return OrphanIntentDetector(
        emitter=mock_emitter,
        time_authority=mock_time_authority,
        orphan_timeout=timedelta(minutes=5),
    )


class TestOrphanDetection:
    """Tests for orphan detection (AC6)."""

    @pytest.mark.asyncio
    async def test_no_orphans_when_no_pending_intents(
        self, detector: OrphanIntentDetector, mock_emitter: MagicMock
    ) -> None:
        """scan_and_resolve should return empty list when no pending intents."""
        mock_emitter.get_pending_intents_with_age.return_value = []

        orphans = await detector.scan_and_resolve_orphans()

        assert orphans == []
        mock_emitter.emit_failure.assert_not_called()

    @pytest.mark.asyncio
    async def test_detects_orphan_past_timeout(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """scan_and_resolve should detect intent past timeout threshold."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        # Intent emitted 10 minutes ago (past 5 minute timeout)
        old_time = now - timedelta(minutes=10)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, old_time)
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert len(orphans) == 1
        assert orphans[0].correlation_id == correlation_id

    @pytest.mark.asyncio
    async def test_ignores_intent_within_timeout(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """scan_and_resolve should not detect intent within timeout."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        # Intent emitted 2 minutes ago (within 5 minute timeout)
        recent_time = now - timedelta(minutes=2)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, recent_time)
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert orphans == []
        mock_emitter.emit_failure.assert_not_called()

    @pytest.mark.asyncio
    async def test_detects_multiple_orphans(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """scan_and_resolve should detect all orphans past timeout."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        id1, id2 = uuid4(), uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (id1, old_time),
            (id2, old_time),
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert len(orphans) == 2
        assert {o.correlation_id for o in orphans} == {id1, id2}

    @pytest.mark.asyncio
    async def test_mixed_orphan_and_valid_intents(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """scan_and_resolve should only detect orphans past timeout."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        recent_time = now - timedelta(minutes=2)
        orphan_id, valid_id = uuid4(), uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (orphan_id, old_time),
            (valid_id, recent_time),
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert len(orphans) == 1
        assert orphans[0].correlation_id == orphan_id


class TestOrphanResolution:
    """Tests for orphan auto-resolution (AC5)."""

    @pytest.mark.asyncio
    async def test_auto_emits_failure_for_orphan(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """scan_and_resolve should emit failure event for each orphan."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, old_time)
        ]

        await detector.scan_and_resolve_orphans()

        mock_emitter.emit_failure.assert_called_once()
        call_args = mock_emitter.emit_failure.call_args
        assert call_args.kwargs["correlation_id"] == correlation_id
        assert call_args.kwargs["failure_reason"] == "ORPHAN_TIMEOUT"

    @pytest.mark.asyncio
    async def test_failure_includes_timeout_details(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Orphan failure event should include timeout details."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, old_time)
        ]

        await detector.scan_and_resolve_orphans()

        call_args = mock_emitter.emit_failure.call_args
        details = call_args.kwargs["failure_details"]
        assert "timeout_seconds" in details
        assert details["timeout_seconds"] == 300  # 5 minutes
        assert details["auto_resolved"] is True

    @pytest.mark.asyncio
    async def test_orphan_resolution_includes_age(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """OrphanResolution should include the age of the orphan."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, old_time)
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert orphans[0].age == timedelta(minutes=10)

    @pytest.mark.asyncio
    async def test_resolves_all_orphans_in_scan(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """All detected orphans should be auto-resolved."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        ids = [uuid4(), uuid4(), uuid4()]
        mock_emitter.get_pending_intents_with_age.return_value = [
            (id_, old_time) for id_ in ids
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert mock_emitter.emit_failure.call_count == 3
        assert {o.correlation_id for o in orphans} == set(ids)


class TestOrphanResolutionModel:
    """Tests for OrphanResolution dataclass."""

    def test_orphan_resolution_fields(self) -> None:
        """OrphanResolution should have required fields."""
        resolution = OrphanResolution(
            correlation_id=uuid4(),
            emitted_at=datetime(2026, 1, 16, 11, 50, 0, tzinfo=timezone.utc),
            resolved_at=datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc),
            age=timedelta(minutes=10),
        )

        assert isinstance(resolution.correlation_id, UUID)
        assert isinstance(resolution.emitted_at, datetime)
        assert isinstance(resolution.resolved_at, datetime)
        assert isinstance(resolution.age, timedelta)

    def test_orphan_resolution_is_frozen(self) -> None:
        """OrphanResolution should be immutable."""
        resolution = OrphanResolution(
            correlation_id=uuid4(),
            emitted_at=datetime(2026, 1, 16, 11, 50, 0, tzinfo=timezone.utc),
            resolved_at=datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc),
            age=timedelta(minutes=10),
        )

        with pytest.raises(AttributeError):
            resolution.age = timedelta(minutes=5)  # type: ignore


class TestConfigurableTimeout:
    """Tests for configurable orphan timeout."""

    @pytest.mark.asyncio
    async def test_custom_timeout_threshold(
        self, mock_emitter: MagicMock, mock_time_authority: MagicMock
    ) -> None:
        """Detector should respect custom timeout threshold."""
        detector = OrphanIntentDetector(
            emitter=mock_emitter,
            time_authority=mock_time_authority,
            orphan_timeout=timedelta(minutes=10),  # Custom 10 minute timeout
        )

        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        # Intent 8 minutes old - should NOT be orphan with 10 min timeout
        age_8_min = now - timedelta(minutes=8)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, age_8_min)
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert orphans == []

    @pytest.mark.asyncio
    async def test_short_timeout_threshold(
        self, mock_emitter: MagicMock, mock_time_authority: MagicMock
    ) -> None:
        """Detector with short timeout detects orphans faster."""
        detector = OrphanIntentDetector(
            emitter=mock_emitter,
            time_authority=mock_time_authority,
            orphan_timeout=timedelta(minutes=1),  # Short 1 minute timeout
        )

        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        # Intent 2 minutes old - IS orphan with 1 min timeout
        age_2_min = now - timedelta(minutes=2)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, age_2_min)
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert len(orphans) == 1


class TestEdgeCases:
    """Tests for edge cases in orphan detection."""

    @pytest.mark.asyncio
    async def test_exact_timeout_boundary(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Intent exactly at timeout boundary should be detected as orphan."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        # Exactly 5 minutes old (at boundary)
        exactly_at_timeout = now - timedelta(minutes=5)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, exactly_at_timeout)
        ]

        orphans = await detector.scan_and_resolve_orphans()

        # At exact boundary, should be considered orphan (>= timeout)
        assert len(orphans) == 1

    @pytest.mark.asyncio
    async def test_just_before_timeout(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Intent just before timeout should NOT be detected as orphan."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        # 4 minutes 59 seconds old (just before 5 min timeout)
        just_before = now - timedelta(minutes=4, seconds=59)
        correlation_id = uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (correlation_id, just_before)
        ]

        orphans = await detector.scan_and_resolve_orphans()

        assert orphans == []

    @pytest.mark.asyncio
    async def test_failure_emit_error_does_not_crash(
        self,
        detector: OrphanIntentDetector,
        mock_emitter: MagicMock,
        mock_time_authority: MagicMock,
    ) -> None:
        """Error in emit_failure should not crash entire scan."""
        now = datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        mock_time_authority.now.return_value = now

        old_time = now - timedelta(minutes=10)
        id1, id2 = uuid4(), uuid4()
        mock_emitter.get_pending_intents_with_age.return_value = [
            (id1, old_time),
            (id2, old_time),
        ]

        # First call fails, second succeeds
        mock_emitter.emit_failure.side_effect = [
            Exception("First emit failed"),
            None,
        ]

        # Should continue processing remaining orphans
        orphans = await detector.scan_and_resolve_orphans()

        # Should have attempted both
        assert mock_emitter.emit_failure.call_count == 2
        # But only second one resolved successfully
        assert len(orphans) == 1
        assert orphans[0].correlation_id == id2
