"""Final deliberation service (Story 7.8, FR135).

Orchestrates recording the final deliberation before cessation.

Constitutional Constraints:
- FR135: Before cessation, final deliberation SHALL be recorded and immutable;
         if recording fails, that failure is the final event
- FR12: Dissent percentages visible in every vote tally
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

Developer Golden Rules:
1. DELIBERATION FIRST - Record deliberation BEFORE cessation event
2. FAIL LOUD - Recording failure becomes final event
3. WITNESS EVERYTHING - Both success and failure witnessed
4. HALT ON COMPLETE FAILURE - If can't record anything, HALT
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.final_deliberation_recorder import (
    FinalDeliberationRecorder,
    RecordDeliberationResult,
)
from src.domain.events.cessation_deliberation import (
    ArchonDeliberation,
    ArchonPosition,
    CessationDeliberationEventPayload,
    REQUIRED_ARCHON_COUNT,
)
from src.domain.events.collective_output import VoteCounts
from src.domain.events.deliberation_recording_failed import (
    DeliberationRecordingFailedEventPayload,
)


# Error code constants for deliberation recording failures
ERROR_CODE_UNKNOWN = "UNKNOWN_ERROR"
ERROR_CODE_COMPLETE_FAILURE = "COMPLETE_FAILURE"


class DeliberationRecordingCompleteFailure(Exception):
    """Raised when both deliberation and failure recording fail (CT-13).

    This is a critical failure that should cause system HALT.
    Per CT-13: Integrity outranks availability.

    Attributes:
        error_code: Machine-readable error code.
        error_message: Human-readable error description.
    """

    def __init__(self, error_code: str, error_message: str) -> None:
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(
            f"FR135 VIOLATED: Complete recording failure - "
            f"error_code={error_code}, message={error_message}"
        )


class FinalDeliberationService:
    """Service for recording final deliberation before cessation (FR135).

    This service orchestrates the recording of the final deliberation
    before cessation. It ensures:
    1. All 72 Archon votes are recorded
    2. Dissent percentage is calculated (FR12)
    3. If recording fails, the failure is recorded as final event (FR135)
    4. If complete failure, raises error for system HALT (CT-13)

    Constitutional Constraints:
    - FR135: Final deliberation SHALL be recorded and immutable
    - FR12: Dissent percentage visible in vote tally
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability
    - CT-13: Integrity outranks availability -> HALT on complete failure
    """

    def __init__(
        self,
        recorder: FinalDeliberationRecorder,
        max_retries: int = 3,
    ) -> None:
        """Initialize the service.

        Args:
            recorder: The recorder implementation for persisting events.
            max_retries: Maximum retry attempts before recording failure.
        """
        self._recorder = recorder
        self._max_retries = max_retries

    async def record_and_proceed(
        self,
        deliberation_id: UUID,
        started_at: datetime,
        ended_at: datetime,
        archon_deliberations: list[ArchonDeliberation],
    ) -> RecordDeliberationResult:
        """Record final deliberation before cessation (FR135).

        Records the complete deliberation with all 72 Archon votes.
        If recording fails, records the failure as the final event.
        If both fail, raises DeliberationRecordingCompleteFailure.

        Args:
            deliberation_id: Unique ID for this deliberation.
            started_at: When deliberation began (UTC).
            ended_at: When deliberation concluded (UTC).
            archon_deliberations: All 72 Archon deliberations.

        Returns:
            RecordDeliberationResult indicating what was recorded.

        Raises:
            ValueError: If not exactly 72 deliberations.
            DeliberationRecordingCompleteFailure: If recording failed completely.
        """
        # Validate 72 Archons (FR135 requirement)
        if len(archon_deliberations) != REQUIRED_ARCHON_COUNT:
            raise ValueError(
                f"FR135: Cessation deliberation requires exactly 72 Archon "
                f"entries, got {len(archon_deliberations)}"
            )

        # Calculate vote counts
        vote_counts = self._count_votes(archon_deliberations)

        # Calculate dissent percentage (FR12)
        dissent_percentage = self._calculate_dissent_percentage(vote_counts)

        # Calculate duration
        duration_seconds = int((ended_at - started_at).total_seconds())

        # Build payload
        payload = CessationDeliberationEventPayload(
            deliberation_id=deliberation_id,
            deliberation_started_at=started_at,
            deliberation_ended_at=ended_at,
            vote_recorded_at=datetime.now(timezone.utc),
            duration_seconds=duration_seconds,
            archon_deliberations=tuple(archon_deliberations),
            vote_counts=vote_counts,
            dissent_percentage=dissent_percentage,
        )

        # Attempt to record deliberation
        result = await self._recorder.record_deliberation(payload)

        if result.success:
            return result

        # Recording failed - record failure as final event (FR135)
        return await self._record_failure(
            deliberation_id=deliberation_id,
            attempted_at=started_at,
            error_code=result.error_code or ERROR_CODE_UNKNOWN,
            error_message=result.error_message or "Unknown recording failure",
            retry_count=self._max_retries,
            partial_archon_count=len(archon_deliberations),
        )

    async def _record_failure(
        self,
        deliberation_id: UUID,
        attempted_at: datetime,
        error_code: str,
        error_message: str,
        retry_count: int,
        partial_archon_count: int,
    ) -> RecordDeliberationResult:
        """Record deliberation failure as final event (FR135).

        Per FR135: If recording fails, that failure IS the final event.

        Args:
            deliberation_id: ID of the failed deliberation.
            attempted_at: When recording was first attempted.
            error_code: Machine-readable error code.
            error_message: Human-readable error description.
            retry_count: Number of retry attempts made.
            partial_archon_count: Number of deliberations collected.

        Returns:
            RecordDeliberationResult from failure recording.

        Raises:
            DeliberationRecordingCompleteFailure: If failure recording also fails.
        """
        failure_payload = DeliberationRecordingFailedEventPayload(
            deliberation_id=deliberation_id,
            attempted_at=attempted_at,
            failed_at=datetime.now(timezone.utc),
            error_code=error_code,
            error_message=error_message,
            retry_count=retry_count,
            partial_archon_count=partial_archon_count,
        )

        result = await self._recorder.record_failure(failure_payload)

        if result.success:
            return result

        # Complete failure - cannot record anything (CT-13: HALT)
        raise DeliberationRecordingCompleteFailure(
            error_code=result.error_code or ERROR_CODE_COMPLETE_FAILURE,
            error_message=result.error_message or "Cannot record any event",
        )

    def _count_votes(
        self,
        deliberations: list[ArchonDeliberation],
    ) -> VoteCounts:
        """Count votes from deliberations.

        Args:
            deliberations: List of Archon deliberations.

        Returns:
            VoteCounts with yes/no/abstain breakdown.
        """
        yes_count = sum(
            1 for d in deliberations
            if d.position == ArchonPosition.SUPPORT_CESSATION
        )
        no_count = sum(
            1 for d in deliberations
            if d.position == ArchonPosition.OPPOSE_CESSATION
        )
        abstain_count = sum(
            1 for d in deliberations
            if d.position == ArchonPosition.ABSTAIN
        )

        return VoteCounts(
            yes_count=yes_count,
            no_count=no_count,
            abstain_count=abstain_count,
        )

    def _calculate_dissent_percentage(self, vote_counts: VoteCounts) -> float:
        """Calculate dissent percentage (FR12).

        Dissent is calculated as the percentage of non-majority votes.
        For cessation deliberation, dissent = non-yes votes / total.

        Args:
            vote_counts: The vote breakdown.

        Returns:
            Dissent percentage (0.0 to 100.0).
        """
        total = vote_counts.total
        if total == 0:
            return 0.0

        # Dissent = votes against majority position
        # For cessation: non-yes votes are dissent
        dissent_votes = vote_counts.no_count + vote_counts.abstain_count
        return round((dissent_votes / total) * 100, 2)
