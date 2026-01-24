"""Orphan Petition Detection Job Handler (Story 8.3, FR-8.5).

This module provides the OrphanDetectionHandler that executes
when an orphan detection job fires from the job queue.

Constitutional Constraints:
- FR-8.5: System SHALL identify petitions stuck in RECEIVED state
- NFR-7.1: 100% of orphans must be detected
- CT-11: Silent failure destroys legitimacy - handler MUST complete
- CT-12: Witnessing creates accountability - detection events witnessed
- HP-1: Job queue for reliable daily execution

Architecture:
- Scheduled to run daily (at midnight UTC by default)
- Delegates to OrphanPetitionDetectionService for detection logic
- Saves results to repository for dashboard visibility
- Emits witnessed event when orphans are found
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.services.job_queue.job_worker_service import JobHandler
from src.domain.models.scheduled_job import ScheduledJob

if TYPE_CHECKING:
    from src.application.services.orphan_petition_detection_service import (
        OrphanPetitionDetectionService,
    )
    from src.application.ports.orphan_detection_repository import (
        OrphanDetectionRepositoryProtocol,
    )

logger = get_logger()

# Job type constant for orphan detection jobs
ORPHAN_DETECTION_JOB_TYPE: str = "orphan_detection"


class OrphanDetectionHandler(JobHandler):
    """Handler for orphan petition detection jobs (Story 8.3, FR-8.5).

    This handler is invoked by the job worker when a daily orphan
    detection job fires. It delegates to the OrphanPetitionDetectionService
    to execute the detection logic and persists results for dashboard visibility.

    Constitutional Constraints:
    - FR-8.5: Identify all petitions stuck in RECEIVED >24 hours
    - NFR-7.1: 100% detection rate required
    - CT-11: Handler MUST complete successfully (FAIL LOUD)
    - CT-12: Detection events must be witnessed

    Attributes:
        _detection_service: Service that handles orphan detection logic.
        _repository: Repository for persisting detection results.
        job_type: The job type this handler processes.
    """

    # Job type this handler processes
    job_type: str = ORPHAN_DETECTION_JOB_TYPE

    def __init__(
        self,
        detection_service: OrphanPetitionDetectionService,
        repository: OrphanDetectionRepositoryProtocol,
    ) -> None:
        """Initialize the orphan detection handler.

        Args:
            detection_service: Service that handles orphan detection.
            repository: Repository for persisting detection results.
        """
        self._detection_service = detection_service
        self._repository = repository

    async def execute(self, job: ScheduledJob) -> None:
        """Execute the orphan detection job.

        Called by the job worker when a detection job is due for execution.
        Extracts threshold from payload (defaults to 24 hours) and delegates
        to detection service.

        Constitutional Constraints:
        - FR-8.5: Detect all petitions stuck >threshold hours
        - NFR-7.1: 100% detection rate
        - CT-11: Must raise exception on failure for retry/DLQ

        Args:
            job: The ScheduledJob containing detection parameters in payload.

        Raises:
            Exception: If detection or persistence fails (FAIL LOUD).
        """
        log = logger.bind(
            job_id=str(job.id),
            job_type=job.job_type,
        )

        # Extract threshold from payload (optional, defaults to service default)
        threshold_hours = job.payload.get("threshold_hours")
        if threshold_hours is not None:
            # Override service threshold if provided in payload
            self._detection_service.threshold_hours = float(threshold_hours)

        log = log.bind(
            threshold_hours=self._detection_service.threshold_hours,
        )

        log.info(
            "orphan_detection_handler_executing",
            message="FR-8.5: Starting orphan petition detection scan",
        )

        # Execute detection (FR-8.5, NFR-7.1)
        detection_result = self._detection_service.detect_orphans()

        log = log.bind(
            detection_id=str(detection_result.detection_id),
            orphan_count=detection_result.total_orphans,
            oldest_orphan_age_hours=detection_result.oldest_orphan_age_hours,
        )

        # Persist result for dashboard visibility (AC6)
        self._repository.save_detection_result(detection_result)

        if detection_result.has_orphans():
            log.warning(
                "orphan_detection_handler_found_orphans",
                orphan_ids=[str(pid) for pid in detection_result.get_petition_ids()],
                message="FR-8.5: Orphaned petitions detected - operator attention required",
            )
        else:
            log.info(
                "orphan_detection_handler_no_orphans",
                message="FR-8.5: No orphaned petitions detected",
            )

        log.info(
            "orphan_detection_handler_completed",
            message="FR-8.5: Orphan detection scan completed and persisted",
        )
