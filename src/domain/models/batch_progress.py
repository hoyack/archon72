"""Batch progress model for query tracking (Story 8.8, FR106).

Domain model for tracking progress of batched queries.

Constitutional Constraints:
- FR106: Historical queries complete within 30 seconds for <10k events;
         larger ranges batched with progress indication.

Usage:
    from src.domain.models.batch_progress import BatchProgress

    progress = BatchProgress.create(
        query_id="q-123",
        total_events=50000,
        processed_events=25000,
    )
    print(progress.progress_percent)  # 50.0
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class BatchProgress:
    """Progress tracking for batched queries (FR106).

    Tracks the progress of large queries that are processed in batches
    to comply with the 30-second SLA for queries under 10,000 events.

    Constitutional Constraint (FR106):
    Larger ranges must be batched with progress indication.

    Attributes:
        progress_id: Unique identifier for this progress record.
        query_id: The query being tracked.
        total_events: Total number of events to process.
        processed_events: Number of events processed so far.
        batch_size: Size of each batch.
        current_batch: Current batch number.
        started_at: When processing started.
        estimated_completion: Estimated completion time.
        is_complete: Whether processing is complete.
    """

    progress_id: UUID
    query_id: str
    total_events: int
    processed_events: int
    batch_size: int
    current_batch: int
    started_at: datetime
    estimated_completion: datetime | None
    is_complete: bool

    def __post_init__(self) -> None:
        """Validate batch progress data."""
        if self.total_events < 0:
            raise ValueError(
                f"total_events cannot be negative, got {self.total_events}"
            )
        if self.processed_events < 0:
            raise ValueError(
                f"processed_events cannot be negative, got {self.processed_events}"
            )
        if self.processed_events > self.total_events:
            raise ValueError(
                f"processed_events ({self.processed_events}) cannot exceed "
                f"total_events ({self.total_events})"
            )
        if self.batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {self.batch_size}")

    @classmethod
    def create(
        cls,
        query_id: str,
        total_events: int,
        processed_events: int = 0,
        batch_size: int = 10000,
    ) -> "BatchProgress":
        """Factory method to create batch progress tracking.

        Args:
            query_id: The query being tracked.
            total_events: Total number of events to process.
            processed_events: Number processed so far (default 0).
            batch_size: Size of each batch (default 10,000 per FR106).

        Returns:
            A new BatchProgress with generated ID and timestamps.
        """
        started_at = datetime.now(timezone.utc)
        current_batch = (
            (processed_events // batch_size) + 1 if processed_events > 0 else 1
        )
        (total_events + batch_size - 1) // batch_size

        # Estimate completion based on progress so far
        estimated_completion = None
        if processed_events > 0:
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            if elapsed > 0:
                rate = processed_events / elapsed
                remaining = total_events - processed_events
                remaining_seconds = remaining / rate if rate > 0 else 0
                estimated_completion = started_at + timedelta(
                    seconds=elapsed + remaining_seconds
                )

        return cls(
            progress_id=uuid4(),
            query_id=query_id,
            total_events=total_events,
            processed_events=processed_events,
            batch_size=batch_size,
            current_batch=current_batch,
            started_at=started_at,
            estimated_completion=estimated_completion,
            is_complete=processed_events >= total_events,
        )

    @property
    def progress_percent(self) -> float:
        """Calculate progress as a percentage.

        Returns:
            Percentage complete (0-100).
        """
        if self.total_events == 0:
            return 100.0
        return (self.processed_events / self.total_events) * 100.0

    @property
    def remaining_events(self) -> int:
        """Calculate remaining events to process.

        Returns:
            Number of events not yet processed.
        """
        return self.total_events - self.processed_events

    @property
    def total_batches(self) -> int:
        """Calculate total number of batches.

        Returns:
            Total batches needed to process all events.
        """
        return (self.total_events + self.batch_size - 1) // self.batch_size

    @property
    def remaining_batches(self) -> int:
        """Calculate remaining batches.

        Returns:
            Number of batches not yet processed.
        """
        return self.total_batches - self.current_batch + (0 if self.is_complete else 1)

    def with_progress(self, additional_events: int) -> "BatchProgress":
        """Create updated progress with additional events processed.

        Args:
            additional_events: Number of additional events processed.

        Returns:
            New BatchProgress with updated counts.
        """
        new_processed = min(
            self.processed_events + additional_events, self.total_events
        )
        new_batch = (new_processed // self.batch_size) + 1

        # Recalculate estimated completion
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        estimated_completion = None
        if new_processed > 0 and elapsed > 0:
            rate = new_processed / elapsed
            remaining = self.total_events - new_processed
            remaining_seconds = remaining / rate if rate > 0 else 0
            estimated_completion = self.started_at + timedelta(
                seconds=elapsed + remaining_seconds
            )

        return BatchProgress(
            progress_id=self.progress_id,
            query_id=self.query_id,
            total_events=self.total_events,
            processed_events=new_processed,
            batch_size=self.batch_size,
            current_batch=new_batch,
            started_at=self.started_at,
            estimated_completion=estimated_completion,
            is_complete=new_processed >= self.total_events,
        )

    def to_summary(self) -> str:
        """Generate human-readable summary.

        Returns:
            Summary string suitable for logging or display.
        """
        status = (
            "✅ Complete" if self.is_complete else f"🔄 {self.progress_percent:.1f}%"
        )
        return (
            f"{status} Query {self.query_id}: "
            f"{self.processed_events}/{self.total_events} events "
            f"(batch {self.current_batch}/{self.total_batches})"
        )


# Need to import timedelta for the class
from datetime import timedelta  # noqa: E402
