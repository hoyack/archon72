"""Time Authority Service for clock drift detection (Story 1.5, FR6-FR7).

This service monitors clock drift between local timestamps and the time authority
(database). Drift detection is for investigation/monitoring only - it does NOT
reject events because sequence is the authoritative ordering.

Constitutional Constraints:
- FR6: Events must have dual timestamps (local + authority)
- FR7: Sequence numbers must be monotonically increasing and unique
- CT-12: Witnessing creates accountability -> drift logged for investigation

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Events must be verifiable

Note:
    Clock drift does NOT invalidate events. The sequence number is the
    authoritative ordering mechanism. Drift is logged for time sync
    investigation purposes only.
"""

from datetime import datetime, timedelta

from structlog import get_logger

logger = get_logger()

# Default threshold for clock drift warning (5 seconds per AC4)
DEFAULT_DRIFT_THRESHOLD_SECONDS: float = 5.0


class TimeAuthorityService:
    """Service for time authority and clock drift detection (FR6-FR7).

    Constitutional Constraint (CT-12):
    Events must be verifiable - clock drift doesn't invalidate events
    but must be logged for investigation.

    This service checks the drift between local_timestamp (from event source)
    and authority_timestamp (from database). If drift exceeds the configurable
    threshold, a warning is logged.

    IMPORTANT: Drift detection does NOT reject events. The sequence number
    is the authoritative ordering mechanism per FR7.

    Attributes:
        _threshold: The maximum allowed drift before warning (timedelta).

    Example:
        >>> from datetime import datetime, timezone
        >>> service = TimeAuthorityService(drift_threshold_seconds=5.0)
        >>> local_ts = datetime.now(timezone.utc)
        >>> authority_ts = datetime.now(timezone.utc)
        >>> service.check_drift(local_ts, authority_ts, "event-123")
    """

    def __init__(self, drift_threshold_seconds: float = DEFAULT_DRIFT_THRESHOLD_SECONDS) -> None:
        """Initialize the time authority service.

        Args:
            drift_threshold_seconds: Maximum drift in seconds before warning.
                Defaults to 5 seconds per AC4.
        """
        self._threshold = timedelta(seconds=drift_threshold_seconds)

    def check_drift(
        self,
        local_timestamp: datetime,
        authority_timestamp: datetime,
        event_id: str,
    ) -> timedelta:
        """Check for clock drift and log warning if threshold exceeded.

        Args:
            local_timestamp: Timestamp from event source.
            authority_timestamp: Timestamp from time authority (DB).
            event_id: Event ID for logging context.

        Returns:
            The absolute drift between timestamps (always positive).

        Note:
            This does NOT reject the event - sequence is authoritative.
            Clock drift is informational only (AC4).
        """
        drift = abs(authority_timestamp - local_timestamp)

        if drift > self._threshold:
            log = logger.bind(
                event_id=event_id,
                local_timestamp=local_timestamp.isoformat(),
                authority_timestamp=authority_timestamp.isoformat(),
                drift_seconds=drift.total_seconds(),
            )
            log.warning(
                "clock_drift_detected",
                message="FR6: Clock drift exceeds threshold - investigate time sync",
            )

        return drift
