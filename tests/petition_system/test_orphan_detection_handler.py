"""Tests for orphan detection job handler (Story 8.3, FR-8.5).

Constitutional Requirements:
- FR-8.5: System SHALL identify petitions stuck in RECEIVED state
- NFR-7.1: 100% of orphans must be detected
- CT-11: Handler must complete successfully
- CT-12: Detection events must be witnessed

Test Coverage:
- Successful detection execution with no orphans
- Successful detection execution with orphans found
- Custom threshold from job payload
- Detection result persistence
- Error propagation (FAIL LOUD)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.application.services.job_queue.orphan_detection_handler import (
    ORPHAN_DETECTION_JOB_TYPE,
    OrphanDetectionHandler,
)
from src.domain.models.orphan_petition_detection import (
    OrphanPetitionDetectionResult,
    OrphanPetitionInfo,
)
from src.domain.models.scheduled_job import JobStatus, ScheduledJob


class TestOrphanDetectionHandler:
    """Test orphan detection handler execution."""

    def test_handler_has_correct_job_type(self):
        """Test handler declares correct job type."""
        detection_service = Mock()
        repository = Mock()

        handler = OrphanDetectionHandler(
            detection_service=detection_service,
            repository=repository,
        )

        assert handler.job_type == ORPHAN_DETECTION_JOB_TYPE
        assert handler.job_type == "orphan_detection"

    @pytest.mark.asyncio
    async def test_executes_detection_and_persists_no_orphans(self):
        """Test handler executes detection when no orphans found (FR-8.5)."""
        # Setup: Detection finds no orphans
        detection_result = OrphanPetitionDetectionResult.create(
            detection_id=uuid4(),
            threshold_hours=24.0,
            orphan_petitions=[],
        )

        detection_service = Mock()
        detection_service.threshold_hours = 24.0
        detection_service.detect_orphans.return_value = detection_result

        repository = Mock()

        handler = OrphanDetectionHandler(
            detection_service=detection_service,
            repository=repository,
        )

        job = self._create_job()

        # Execute
        await handler.execute(job)

        # Verify detection was called
        detection_service.detect_orphans.assert_called_once()

        # Verify result was persisted
        repository.save_detection_result.assert_called_once_with(detection_result)

    @pytest.mark.asyncio
    async def test_executes_detection_and_persists_with_orphans(self):
        """Test handler executes detection when orphans found (FR-8.5)."""
        # Setup: Detection finds 2 orphans
        orphan_infos = [
            OrphanPetitionInfo(
                petition_id=uuid4(),
                created_at=datetime.now(timezone.utc),
                age_hours=30.0,
                petition_type="GENERAL",
                co_signer_count=5,
            ),
            OrphanPetitionInfo(
                petition_id=uuid4(),
                created_at=datetime.now(timezone.utc),
                age_hours=48.0,
                petition_type="CESSATION",
                co_signer_count=25,
            ),
        ]

        detection_result = OrphanPetitionDetectionResult.create(
            detection_id=uuid4(),
            threshold_hours=24.0,
            orphan_petitions=orphan_infos,
        )

        detection_service = Mock()
        detection_service.threshold_hours = 24.0
        detection_service.detect_orphans.return_value = detection_result

        repository = Mock()

        handler = OrphanDetectionHandler(
            detection_service=detection_service,
            repository=repository,
        )

        job = self._create_job()

        # Execute
        await handler.execute(job)

        # Verify detection was called
        detection_service.detect_orphans.assert_called_once()

        # Verify result was persisted
        repository.save_detection_result.assert_called_once_with(detection_result)

    @pytest.mark.asyncio
    async def test_uses_custom_threshold_from_payload(self):
        """Test handler uses threshold from job payload when provided."""
        # Setup: Job payload specifies custom threshold
        detection_result = OrphanPetitionDetectionResult.create(
            detection_id=uuid4(),
            threshold_hours=48.0,
            orphan_petitions=[],
        )

        detection_service = Mock()
        detection_service.threshold_hours = 24.0  # Default
        detection_service.detect_orphans.return_value = detection_result

        repository = Mock()

        handler = OrphanDetectionHandler(
            detection_service=detection_service,
            repository=repository,
        )

        job = self._create_job(payload={"threshold_hours": 48.0})

        # Execute
        await handler.execute(job)

        # Verify threshold was updated on service
        assert detection_service.threshold_hours == 48.0

        # Verify detection was called
        detection_service.detect_orphans.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_on_detection_failure(self):
        """Test handler raises exception on detection failure (CT-11)."""
        # Setup: Detection fails
        detection_service = Mock()
        detection_service.threshold_hours = 24.0
        detection_service.detect_orphans.side_effect = Exception("Database error")

        repository = Mock()

        handler = OrphanDetectionHandler(
            detection_service=detection_service,
            repository=repository,
        )

        job = self._create_job()

        # Execute & Verify: Exception is raised (FAIL LOUD)
        with pytest.raises(Exception, match="Database error"):
            await handler.execute(job)

        # Verify repository was not called (failure before persistence)
        repository.save_detection_result.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_on_persistence_failure(self):
        """Test handler raises exception on persistence failure (CT-11)."""
        # Setup: Detection succeeds but persistence fails
        detection_result = OrphanPetitionDetectionResult.create(
            detection_id=uuid4(),
            threshold_hours=24.0,
            orphan_petitions=[],
        )

        detection_service = Mock()
        detection_service.threshold_hours = 24.0
        detection_service.detect_orphans.return_value = detection_result

        repository = Mock()
        repository.save_detection_result.side_effect = Exception("Storage error")

        handler = OrphanDetectionHandler(
            detection_service=detection_service,
            repository=repository,
        )

        job = self._create_job()

        # Execute & Verify: Exception is raised (FAIL LOUD)
        with pytest.raises(Exception, match="Storage error"):
            await handler.execute(job)

    def _create_job(self, payload: dict | None = None) -> ScheduledJob:
        """Helper to create a scheduled job for testing."""
        return ScheduledJob(
            id=uuid4(),
            job_type=ORPHAN_DETECTION_JOB_TYPE,
            payload=payload or {},
            scheduled_for=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            attempts=0,
            last_attempt_at=None,
            status=JobStatus.PENDING,
        )
