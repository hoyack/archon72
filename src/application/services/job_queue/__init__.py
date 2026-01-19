"""Job queue services for deadline monitoring (Story 0.4, HP-1, HC-6).

This module provides the application services for job scheduling and
deadline monitoring in the Three Fates petition system.

Available services:
- JobWorkerService: Polls and executes scheduled jobs (AC5)
- DLQAlertService: Dead letter queue monitoring and alerting (AC6, HC-6)

Constitutional Constraints:
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
- NFR-7.5: 10-second polling interval with heartbeat monitoring
- FM-7.1: Persistent job queue prevents "timeout never fires" failure mode
"""

from src.application.services.job_queue.dlq_alert_service import (
    ALERT_SEVERITY_CRITICAL,
    ALERT_SEVERITY_WARNING,
    CRITICAL_DLQ_DEPTH_THRESHOLD,
    DEFAULT_DLQ_CHECK_INTERVAL_SECONDS,
    AlertCallback,
    DLQAlertService,
    create_log_alert_callback,
)
from src.application.services.job_queue.job_worker_service import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    JobHandler,
    JobWorkerService,
)

__all__ = [
    # Job Worker Service (AC5)
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "JobHandler",
    "JobWorkerService",
    # DLQ Alert Service (AC6, HC-6)
    "ALERT_SEVERITY_CRITICAL",
    "ALERT_SEVERITY_WARNING",
    "CRITICAL_DLQ_DEPTH_THRESHOLD",
    "DEFAULT_DLQ_CHECK_INTERVAL_SECONDS",
    "AlertCallback",
    "DLQAlertService",
    "create_log_alert_callback",
]
