"""Job Queue adapters for deadline monitoring (Story 0.4, HP-1, HC-6).

This module provides PostgreSQL-backed implementations for job scheduling
and deadline monitoring in the Three Fates petition system.

Available adapters:
- PostgresJobScheduler: Production PostgreSQL implementation (AC4)

Constitutional Constraints:
- HP-1: Job queue for reliable deadline execution
- HC-6: Dead-letter alerting for failed jobs
- NFR-7.5: Timeout job monitoring with heartbeat on scheduler
- FM-7.1: Persistent job queue prevents "timeout never fires" failure mode
"""

from src.infrastructure.adapters.job_queue.postgres_job_scheduler import (
    PostgresJobScheduler,
)

__all__ = [
    "PostgresJobScheduler",
]
