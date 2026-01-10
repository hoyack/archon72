# Story 4.9: Observer API Uptime SLA (RT-5)

## Story

**As an** external observer,
**I want** 99.9% API uptime with external monitoring,
**So that** I can rely on verification access.

## Status

Status: done

## Context

### Business Context
This is the ninth story in Epic 4 (Observer Verification Interface). It delivers the **Observer API uptime SLA** with external monitoring to ensure external observers can rely on verification access. Per RT-5 (Red Team Hardening), observers need guaranteed API availability with external uptime monitoring, checkpoint fallback when unavailable, and genesis anchor verification during outages.

Key business drivers:
1. **Reliability for verification**: Observers must be able to verify chain integrity at any time
2. **External monitoring**: Uptime measured externally, not self-reported (independence)
3. **Graceful degradation**: Checkpoint anchors provide fallback during API unavailability
4. **Constitutional compliance**: External detectability requirement (FR53 via Epic 8)

### Technical Context
- **RT-5**: Observer API 99.9% uptime SLA with external uptime monitoring (Red Team Hardening - Epic 4)
- **ADR-8**: Observer Consistency + Genesis Anchor - observers can verify via genesis anchor during API outage
- **FR53**: External detectability - system unavailability independently detectable (Epic 8 scope, but relevant)
- **CT-11**: Silent failure destroys legitimacy - health status must be accurate
- **CT-13**: Reads allowed during halt (but API must be available for reads)

**Story 4.8 Delivered (Previous Story):**
- `NotificationService` with webhook/SSE push notifications
- `/events/stream` SSE endpoint
- `/subscriptions/webhook` subscription endpoints
- Multi-channel delivery (RT-5 partial - breach event push)
- `sse-starlette` library integration

**Key Files from Previous Stories:**
- `src/api/routes/observer.py` - Observer API endpoints (~1000 lines)
- `src/api/routes/health.py` - Basic health check endpoint
- `src/api/models/health.py` - HealthResponse model
- `src/api/models/observer.py` - Observer API models
- `src/api/dependencies/observer.py` - Dependency injection
- `src/application/services/observer_service.py` - ObserverService
- `src/application/services/notification_service.py` - NotificationService

### Dependencies
- **Story 4.1**: Public read access without registration (DONE) - same auth model (none)
- **Story 4.5**: Historical queries (DONE) - query functionality that must remain available
- **Story 4.6**: Merkle proofs (DONE) - checkpoint anchors for fallback
- **Story 4.8**: Push notifications (DONE) - notification infrastructure

### Constitutional Constraints
- **RT-5**: 99.9% uptime SLA with external monitoring, checkpoint fallback
- **FR44**: No authentication required (health endpoints public)
- **FR48**: Rate limits identical for all users
- **CT-11**: Silent failure destroys legitimacy - health must be accurate
- **ADR-8**: Genesis anchor verification works during API outage

### Architecture Decisions
Per ADR-8 (Observer Consistency + Genesis Anchor):
- Observers can verify via genesis anchor even during API outage
- Checkpoint anchors provide verification fallback
- Observer catch-up: verify all checkpoints since last healthy timestamp

Per RT-5 (Red Team Hardening - Epics context):
- 99.9% availability target externally monitored
- Fallback to checkpoint anchor when API unavailable
- Genesis anchor verification still works during outage

Per Project Context (NFR requirements):
- Health endpoints: `/health` (liveness) and `/ready` (readiness)
- Prometheus metrics at `/metrics` endpoint
- Alert severity levels defined (CRITICAL, HIGH, MEDIUM, LOW, INFO)

## Acceptance Criteria

### AC1: Observer API uptime measured externally
**Given** the observer API
**When** uptime is measured externally
**Then** it meets 99.9% availability target
**And** external monitoring service is configured

### AC2: Checkpoint fallback during unavailability
**Given** API unavailability
**When** it occurs
**Then** observers can fallback to checkpoint anchors
**And** genesis anchor verification still works

### AC3: Operational alerts on downtime
**Given** the uptime monitoring
**When** downtime is detected
**Then** alerts are sent to operations
**And** incident is recorded

## Tasks

### Task 1: Enhance Observer API health endpoints

Add dedicated observer health endpoints with detailed status.

**Files:**
- `src/api/routes/observer.py` (modify - add observer health endpoint)
- `src/api/models/observer.py` (modify - add health models)
- `tests/unit/api/test_observer_routes.py` (modify - add health tests)

**Test Cases (RED):**
- `test_observer_health_returns_status`
- `test_observer_health_includes_dependencies`
- `test_observer_health_degraded_when_db_unavailable`
- `test_observer_ready_returns_readiness`
- `test_observer_ready_not_ready_during_startup`

**Implementation (GREEN):**
```python
# Add to src/api/models/observer.py

from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ObserverHealthStatus(str, Enum):
    """Observer API health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    """Health status of a single dependency.

    Attributes:
        name: Dependency name (e.g., "database", "redis").
        status: Health status of this dependency.
        latency_ms: Optional latency in milliseconds.
        last_check: When this dependency was last checked.
        error: Optional error message if unhealthy.
    """
    name: str
    status: ObserverHealthStatus
    latency_ms: Optional[float] = None
    last_check: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None


class ObserverHealthResponse(BaseModel):
    """Observer API health response (RT-5).

    Per CT-11: Health status must be accurate, not optimistic.

    Attributes:
        status: Overall health status.
        version: API version string.
        timestamp: When health check was performed.
        dependencies: Health of each dependency.
        uptime_seconds: How long the API has been running.
        last_checkpoint_sequence: Last checkpoint anchor sequence (for fallback).
    """
    status: ObserverHealthStatus
    version: str = Field(default="1.0.0")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dependencies: list[DependencyHealth] = Field(default_factory=list)
    uptime_seconds: float = Field(ge=0)
    last_checkpoint_sequence: Optional[int] = Field(
        default=None,
        description="Last checkpoint anchor sequence for fallback verification"
    )


class ObserverReadyResponse(BaseModel):
    """Observer API readiness response (RT-5).

    Indicates whether the API is ready to serve requests.

    Attributes:
        ready: Whether API is ready to serve requests.
        reason: Optional reason if not ready.
        startup_complete: Whether startup initialization is complete.
    """
    ready: bool
    reason: Optional[str] = None
    startup_complete: bool = True
```

```python
# Add to src/api/routes/observer.py

import time
from src.api.models.observer import (
    DependencyHealth,
    ObserverHealthResponse,
    ObserverHealthStatus,
    ObserverReadyResponse,
)

# Track API startup time for uptime calculation
_API_START_TIME: float = time.time()
_API_READY: bool = False


def mark_api_ready() -> None:
    """Mark API as ready after startup initialization."""
    global _API_READY
    _API_READY = True


@router.get("/health", response_model=ObserverHealthResponse)
async def observer_health(
    request: Request,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverHealthResponse:
    """Observer API health check endpoint (RT-5).

    Returns detailed health status for external monitoring.
    No authentication required (FR44).

    Per RT-5: External uptime monitoring requires this endpoint.
    Per CT-11: Status must be accurate (HALT OVER DEGRADE).

    Args:
        request: The FastAPI request object.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        ObserverHealthResponse with detailed health status.
    """
    await rate_limiter.check_rate_limit(request)

    dependencies: list[DependencyHealth] = []
    overall_status = ObserverHealthStatus.HEALTHY

    # Check database connectivity
    db_health = await _check_database_health(observer_service)
    dependencies.append(db_health)
    if db_health.status == ObserverHealthStatus.UNHEALTHY:
        overall_status = ObserverHealthStatus.UNHEALTHY
    elif db_health.status == ObserverHealthStatus.DEGRADED:
        overall_status = ObserverHealthStatus.DEGRADED

    # Get last checkpoint for fallback info
    last_checkpoint = await observer_service.get_last_checkpoint_sequence()

    return ObserverHealthResponse(
        status=overall_status,
        uptime_seconds=time.time() - _API_START_TIME,
        dependencies=dependencies,
        last_checkpoint_sequence=last_checkpoint,
    )


@router.get("/ready", response_model=ObserverReadyResponse)
async def observer_ready(
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverReadyResponse:
    """Observer API readiness check endpoint (RT-5).

    Returns whether API is ready to serve requests.
    Used by load balancers and orchestrators.

    No authentication required (FR44).

    Args:
        request: The FastAPI request object.
        rate_limiter: Injected rate limiter.

    Returns:
        ObserverReadyResponse indicating readiness.
    """
    await rate_limiter.check_rate_limit(request)

    if not _API_READY:
        return ObserverReadyResponse(
            ready=False,
            reason="API startup not complete",
            startup_complete=False,
        )

    return ObserverReadyResponse(ready=True)


async def _check_database_health(
    observer_service: ObserverService,
) -> DependencyHealth:
    """Check database health with latency measurement."""
    start = time.time()
    try:
        # Simple query to check DB connectivity
        await observer_service.check_database_health()
        latency = (time.time() - start) * 1000  # Convert to ms

        # Determine status based on latency
        if latency > 1000:  # > 1 second is degraded
            return DependencyHealth(
                name="database",
                status=ObserverHealthStatus.DEGRADED,
                latency_ms=latency,
            )

        return DependencyHealth(
            name="database",
            status=ObserverHealthStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as e:
        return DependencyHealth(
            name="database",
            status=ObserverHealthStatus.UNHEALTHY,
            latency_ms=None,
            error=str(e),
        )
```

### Task 2: Add checkpoint fallback endpoint

Add endpoint to get checkpoint anchors for fallback verification.

**Files:**
- `src/api/routes/observer.py` (modify - add checkpoint fallback endpoint)
- `src/api/models/observer.py` (modify - add fallback models)
- `tests/unit/api/test_observer_routes.py` (modify - add fallback tests)

**Test Cases (RED):**
- `test_checkpoint_fallback_returns_latest_checkpoint`
- `test_checkpoint_fallback_includes_genesis_anchor`
- `test_checkpoint_fallback_works_during_degraded_state`
- `test_checkpoint_list_returns_recent_checkpoints`

**Implementation (GREEN):**
```python
# Add to src/api/models/observer.py

class CheckpointFallback(BaseModel):
    """Checkpoint fallback information for API unavailability (RT-5).

    Per ADR-8: Observers can verify via checkpoint anchors during outage.

    Attributes:
        latest_checkpoint: Most recent checkpoint anchor.
        genesis_anchor_hash: Genesis anchor hash for root verification.
        checkpoint_count: Total number of checkpoints available.
        verification_url: URL for offline verification toolkit.
    """
    latest_checkpoint: Optional[CheckpointAnchor] = None
    genesis_anchor_hash: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="Genesis anchor hash for root verification"
    )
    checkpoint_count: int = Field(ge=0)
    verification_url: str = Field(
        default="/v1/observer/verification-spec",
        description="URL for verification specification"
    )
    fallback_instructions: str = Field(
        default="During API unavailability, use checkpoints with the verification toolkit for offline verification.",
        description="Instructions for using fallback verification"
    )
```

```python
# Add to src/api/routes/observer.py

@router.get("/fallback", response_model=CheckpointFallback)
async def get_checkpoint_fallback(
    request: Request,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CheckpointFallback:
    """Get checkpoint fallback information (RT-5).

    Returns checkpoint anchors for fallback verification during
    API unavailability. Per ADR-8: Genesis anchor verification
    works during API outage.

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Args:
        request: The FastAPI request object.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        CheckpointFallback with checkpoint and genesis info.
    """
    await rate_limiter.check_rate_limit(request)

    latest_checkpoint = await observer_service.get_latest_checkpoint()
    genesis_hash = await observer_service.get_genesis_anchor_hash()
    checkpoint_count = await observer_service.get_checkpoint_count()

    return CheckpointFallback(
        latest_checkpoint=latest_checkpoint,
        genesis_anchor_hash=genesis_hash,
        checkpoint_count=checkpoint_count,
    )
```

### Task 3: Create uptime metrics service

Create service to track and expose uptime metrics for external monitoring.

**Files:**
- `src/application/services/uptime_service.py` (new)
- `src/application/ports/uptime_tracker.py` (new - port interface)
- `tests/unit/application/test_uptime_service.py` (new)

**Test Cases (RED):**
- `test_uptime_service_tracks_availability`
- `test_uptime_service_calculates_percentage`
- `test_uptime_service_records_downtime_incident`
- `test_uptime_service_returns_sla_status`
- `test_uptime_service_rolling_window_calculation`

**Implementation (GREEN):**
```python
# In src/application/services/uptime_service.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class DowntimeIncident:
    """Record of a downtime incident.

    Attributes:
        start_time: When downtime started.
        end_time: When downtime ended (None if ongoing).
        reason: Reason for downtime.
        duration_seconds: Total duration in seconds.
    """
    start_time: datetime
    end_time: Optional[datetime] = None
    reason: str = "unknown"

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()


@dataclass
class UptimeSLAStatus:
    """Uptime SLA status for reporting.

    Attributes:
        target_percentage: SLA target (99.9%).
        current_percentage: Current uptime percentage.
        meeting_sla: Whether currently meeting SLA.
        window_hours: Calculation window in hours.
        total_downtime_seconds: Total downtime in window.
        incidents: List of downtime incidents in window.
    """
    target_percentage: float = 99.9
    current_percentage: float = 100.0
    meeting_sla: bool = True
    window_hours: int = 720  # 30 days default
    total_downtime_seconds: float = 0.0
    incidents: list[DowntimeIncident] = field(default_factory=list)


class UptimeService:
    """Service for tracking Observer API uptime (RT-5).

    Per RT-5: 99.9% uptime SLA with external monitoring.
    Per CT-11: Accurate reporting, no optimistic status.

    Tracks:
    - Availability windows
    - Downtime incidents
    - SLA compliance
    """

    SLA_TARGET = 99.9  # 99.9% uptime target

    def __init__(
        self,
        window_hours: int = 720,  # 30 days rolling window
    ) -> None:
        self._window_hours = window_hours
        self._incidents: list[DowntimeIncident] = []
        self._current_incident: Optional[DowntimeIncident] = None
        self._service_start: datetime = datetime.now(timezone.utc)

    def record_downtime_start(self, reason: str = "unknown") -> None:
        """Record start of downtime incident.

        Args:
            reason: Reason for the downtime.
        """
        if self._current_incident is not None:
            log.warning("downtime_already_active", reason=reason)
            return

        self._current_incident = DowntimeIncident(
            start_time=datetime.now(timezone.utc),
            reason=reason,
        )

        log.error(
            "downtime_started",
            reason=reason,
            start_time=self._current_incident.start_time.isoformat(),
        )

    def record_downtime_end(self) -> Optional[DowntimeIncident]:
        """Record end of current downtime incident.

        Returns:
            The completed incident, or None if no active incident.
        """
        if self._current_incident is None:
            log.warning("no_active_downtime")
            return None

        self._current_incident.end_time = datetime.now(timezone.utc)
        incident = self._current_incident
        self._incidents.append(incident)
        self._current_incident = None

        log.info(
            "downtime_ended",
            duration_seconds=incident.duration_seconds,
            reason=incident.reason,
        )

        return incident

    def get_sla_status(self) -> UptimeSLAStatus:
        """Get current SLA status.

        Returns:
            UptimeSLAStatus with current uptime metrics.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=self._window_hours)

        # Calculate total seconds in window
        service_start = max(self._service_start, window_start)
        total_seconds = (now - service_start).total_seconds()

        if total_seconds <= 0:
            return UptimeSLAStatus(
                target_percentage=self.SLA_TARGET,
                current_percentage=100.0,
                meeting_sla=True,
                window_hours=self._window_hours,
            )

        # Calculate downtime in window
        downtime_seconds = 0.0
        window_incidents: list[DowntimeIncident] = []

        for incident in self._incidents:
            if incident.end_time and incident.end_time >= window_start:
                # Incident overlaps with window
                incident_start = max(incident.start_time, window_start)
                incident_end = min(incident.end_time, now)
                downtime_seconds += (incident_end - incident_start).total_seconds()
                window_incidents.append(incident)

        # Include current incident if active
        if self._current_incident is not None:
            incident_start = max(self._current_incident.start_time, window_start)
            downtime_seconds += (now - incident_start).total_seconds()
            window_incidents.append(self._current_incident)

        # Calculate uptime percentage
        uptime_seconds = total_seconds - downtime_seconds
        uptime_percentage = (uptime_seconds / total_seconds) * 100.0

        return UptimeSLAStatus(
            target_percentage=self.SLA_TARGET,
            current_percentage=round(uptime_percentage, 4),
            meeting_sla=uptime_percentage >= self.SLA_TARGET,
            window_hours=self._window_hours,
            total_downtime_seconds=downtime_seconds,
            incidents=window_incidents,
        )

    def get_uptime_percentage(self) -> float:
        """Get current uptime percentage.

        Returns:
            Uptime percentage (0-100).
        """
        return self.get_sla_status().current_percentage

    def is_meeting_sla(self) -> bool:
        """Check if currently meeting SLA.

        Returns:
            True if meeting 99.9% SLA.
        """
        return self.get_sla_status().meeting_sla
```

### Task 4: Add Prometheus metrics endpoint

Add `/metrics` endpoint for external monitoring integration.

**Files:**
- `src/api/routes/observer.py` (modify - add metrics endpoint)
- `src/api/models/observer.py` (modify - add metrics models)
- `tests/unit/api/test_observer_routes.py` (modify - add metrics tests)

**Test Cases (RED):**
- `test_metrics_endpoint_returns_prometheus_format`
- `test_metrics_includes_uptime_gauge`
- `test_metrics_includes_request_counter`
- `test_metrics_includes_latency_histogram`

**Implementation (GREEN):**
```python
# Add to src/api/models/observer.py

class ObserverMetrics(BaseModel):
    """Observer API metrics for Prometheus (RT-5).

    Attributes:
        uptime_seconds: Total uptime in seconds.
        uptime_percentage: Current uptime percentage.
        sla_target: SLA target percentage.
        meeting_sla: Whether meeting SLA (1 or 0).
        total_requests: Total requests served.
        error_count: Total error responses.
        last_checkpoint_age_seconds: Age of last checkpoint.
    """
    uptime_seconds: float
    uptime_percentage: float
    sla_target: float = 99.9
    meeting_sla: int  # 1 or 0 for Prometheus gauge
    total_requests: int = 0
    error_count: int = 0
    last_checkpoint_age_seconds: Optional[float] = None
```

```python
# Add to src/api/routes/observer.py

from fastapi.responses import PlainTextResponse


@router.get("/metrics", response_class=PlainTextResponse)
async def observer_metrics(
    request: Request,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> PlainTextResponse:
    """Observer API metrics in Prometheus format (RT-5).

    Returns metrics for external uptime monitoring.
    No authentication required (FR44).

    Per RT-5: External monitoring requires metrics endpoint.
    Per NFR27: Prometheus metrics for operational monitoring.

    Args:
        request: The FastAPI request object.
        observer_service: Injected observer service.
        rate_limiter: Injected rate limiter.

    Returns:
        Prometheus-formatted metrics.
    """
    await rate_limiter.check_rate_limit(request)

    uptime_seconds = time.time() - _API_START_TIME

    # Get SLA status from service
    # Note: In production, inject UptimeService
    uptime_percentage = 100.0  # Placeholder - wire up UptimeService
    meeting_sla = 1 if uptime_percentage >= 99.9 else 0

    # Get checkpoint age
    last_checkpoint = await observer_service.get_last_checkpoint_sequence()
    checkpoint_age = None
    if last_checkpoint:
        checkpoint_time = await observer_service.get_checkpoint_timestamp(last_checkpoint)
        if checkpoint_time:
            checkpoint_age = (datetime.now(timezone.utc) - checkpoint_time).total_seconds()

    # Format as Prometheus exposition format
    metrics = f"""# HELP observer_uptime_seconds Total uptime of Observer API in seconds
# TYPE observer_uptime_seconds gauge
observer_uptime_seconds {uptime_seconds}

# HELP observer_uptime_percentage Current uptime percentage
# TYPE observer_uptime_percentage gauge
observer_uptime_percentage {uptime_percentage}

# HELP observer_sla_target Target SLA percentage
# TYPE observer_sla_target gauge
observer_sla_target 99.9

# HELP observer_meeting_sla Whether currently meeting SLA (1=yes, 0=no)
# TYPE observer_meeting_sla gauge
observer_meeting_sla {meeting_sla}

# HELP observer_api_ready Whether API is ready to serve (1=ready, 0=not ready)
# TYPE observer_api_ready gauge
observer_api_ready {1 if _API_READY else 0}
"""

    if checkpoint_age is not None:
        metrics += f"""
# HELP observer_last_checkpoint_age_seconds Age of last checkpoint anchor in seconds
# TYPE observer_last_checkpoint_age_seconds gauge
observer_last_checkpoint_age_seconds {checkpoint_age}
"""

    return PlainTextResponse(content=metrics, media_type="text/plain; version=0.0.4")
```

### Task 5: Update ObserverService with health methods

Add health check methods to ObserverService for dependency checking.

**Files:**
- `src/application/services/observer_service.py` (modify - add health methods)
- `tests/unit/application/test_observer_service.py` (modify - add health tests)

**Test Cases (RED):**
- `test_observer_service_check_database_health`
- `test_observer_service_get_last_checkpoint_sequence`
- `test_observer_service_get_genesis_anchor_hash`
- `test_observer_service_get_checkpoint_count`
- `test_observer_service_get_checkpoint_timestamp`

**Implementation (GREEN):**
```python
# Add to src/application/services/observer_service.py

async def check_database_health(self) -> None:
    """Check database connectivity.

    Raises:
        Exception: If database is unavailable.
    """
    # Execute simple query to verify connectivity
    await self._event_store.count_events()

async def get_last_checkpoint_sequence(self) -> Optional[int]:
    """Get sequence number of last checkpoint anchor.

    Returns:
        Last checkpoint sequence, or None if no checkpoints.
    """
    checkpoint = await self._event_store.get_latest_checkpoint()
    return checkpoint.sequence if checkpoint else None

async def get_genesis_anchor_hash(self) -> str:
    """Get genesis anchor hash for root verification.

    Returns:
        Genesis anchor content hash.
    """
    genesis = await self._event_store.get_genesis_event()
    return genesis.content_hash if genesis else "0" * 64

async def get_checkpoint_count(self) -> int:
    """Get total number of checkpoint anchors.

    Returns:
        Number of checkpoints available.
    """
    return await self._event_store.count_checkpoints()

async def get_checkpoint_timestamp(self, sequence: int) -> Optional[datetime]:
    """Get timestamp of checkpoint at given sequence.

    Args:
        sequence: Checkpoint sequence number.

    Returns:
        Checkpoint timestamp, or None if not found.
    """
    checkpoint = await self._event_store.get_checkpoint_by_sequence(sequence)
    return checkpoint.authority_timestamp if checkpoint else None

async def get_latest_checkpoint(self) -> Optional[CheckpointAnchor]:
    """Get latest checkpoint anchor.

    Returns:
        Latest checkpoint, or None if no checkpoints.
    """
    return await self._event_store.get_latest_checkpoint()
```

### Task 6: Create external monitoring configuration

Create configuration for external uptime monitoring services.

**Files:**
- `src/infrastructure/monitoring/external_monitor.py` (new)
- `docs/runbooks/observer-api-monitoring.md` (new - runbook)
- `tests/unit/infrastructure/test_external_monitor.py` (new)

**Test Cases (RED):**
- `test_monitor_config_validates_webhook_url`
- `test_monitor_config_alert_thresholds`
- `test_monitor_sends_alert_on_downtime`
- `test_monitor_recovery_alert`

**Implementation (GREEN):**
```python
# In src/infrastructure/monitoring/external_monitor.py

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()


class AlertSeverity(str, Enum):
    """Alert severity levels per project context."""
    CRITICAL = "critical"  # Page immediately, halt system
    HIGH = "high"  # Page immediately
    MEDIUM = "medium"  # Alert on-call, 15 min response
    LOW = "low"  # Next business day
    INFO = "info"  # No alert, log only


@dataclass
class MonitoringConfig:
    """External monitoring configuration (RT-5).

    Attributes:
        health_endpoint: URL to monitor.
        check_interval_seconds: How often to check.
        alert_webhook_url: Where to send alerts.
        sla_target: Target uptime percentage.
        alert_after_failures: Alert after N consecutive failures.
    """
    health_endpoint: str = "http://localhost:8000/v1/observer/health"
    check_interval_seconds: int = 30
    alert_webhook_url: Optional[str] = None
    sla_target: float = 99.9
    alert_after_failures: int = 3


@dataclass
class MonitoringAlert:
    """Alert for monitoring events.

    Attributes:
        severity: Alert severity level.
        title: Short alert title.
        message: Detailed alert message.
        timestamp: When alert was generated.
        service: Service that generated alert.
        incident_id: Optional incident tracking ID.
    """
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    service: str = "observer-api"
    incident_id: Optional[str] = None


class ExternalMonitorClient:
    """Client for sending alerts to external monitoring services.

    Per RT-5: External uptime monitoring with alerts.
    Per CT-11: All monitoring events are logged.
    """

    def __init__(self, config: MonitoringConfig) -> None:
        self._config = config
        self._consecutive_failures = 0
        self._current_incident_id: Optional[str] = None

    async def send_alert(self, alert: MonitoringAlert) -> bool:
        """Send alert to external monitoring service.

        Args:
            alert: The alert to send.

        Returns:
            True if alert was sent successfully.
        """
        if not self._config.alert_webhook_url:
            log.warning("no_alert_webhook_configured")
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._config.alert_webhook_url,
                    json={
                        "severity": alert.severity.value,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "service": alert.service,
                        "incident_id": alert.incident_id,
                    },
                    timeout=10.0,
                )

                if response.status_code < 300:
                    log.info(
                        "alert_sent",
                        severity=alert.severity.value,
                        title=alert.title,
                        incident_id=alert.incident_id,
                    )
                    return True

                log.error(
                    "alert_send_failed",
                    status_code=response.status_code,
                )
                return False

            except Exception as e:
                log.error("alert_send_error", error=str(e))
                return False

    async def record_check_failure(self, reason: str) -> None:
        """Record a health check failure.

        Args:
            reason: Reason for failure.
        """
        self._consecutive_failures += 1

        log.warning(
            "health_check_failed",
            consecutive_failures=self._consecutive_failures,
            reason=reason,
        )

        if self._consecutive_failures >= self._config.alert_after_failures:
            if self._current_incident_id is None:
                # Start new incident
                self._current_incident_id = f"observer-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

                await self.send_alert(MonitoringAlert(
                    severity=AlertSeverity.HIGH,
                    title="Observer API Down",
                    message=f"Observer API health check failed {self._consecutive_failures} times. Reason: {reason}",
                    timestamp=datetime.now(timezone.utc),
                    incident_id=self._current_incident_id,
                ))

    async def record_check_success(self) -> None:
        """Record a successful health check."""
        if self._consecutive_failures > 0:
            if self._current_incident_id is not None:
                # Recovery alert
                await self.send_alert(MonitoringAlert(
                    severity=AlertSeverity.INFO,
                    title="Observer API Recovered",
                    message=f"Observer API recovered after {self._consecutive_failures} failed checks.",
                    timestamp=datetime.now(timezone.utc),
                    incident_id=self._current_incident_id,
                ))
                self._current_incident_id = None

            log.info(
                "health_check_recovered",
                previous_failures=self._consecutive_failures,
            )

        self._consecutive_failures = 0
```

### Task 7: Integration tests for Observer API SLA

End-to-end tests for uptime SLA functionality.

**Files:**
- `tests/integration/test_observer_api_sla_integration.py` (new)

**Test Cases:**
- `test_observer_health_endpoint_integration`
- `test_observer_ready_endpoint_integration`
- `test_observer_metrics_endpoint_integration`
- `test_observer_fallback_endpoint_integration`
- `test_health_degraded_when_db_slow`
- `test_uptime_service_tracks_downtime`
- `test_sla_calculation_over_time`
- `test_checkpoint_fallback_provides_verification_path`

## Technical Notes

### Implementation Order
1. Task 1: Observer health endpoints (foundation)
2. Task 5: ObserverService health methods (dependency)
3. Task 3: Uptime metrics service
4. Task 4: Prometheus metrics endpoint
5. Task 2: Checkpoint fallback endpoint
6. Task 6: External monitoring configuration
7. Task 7: Integration tests

### Testing Strategy
- Unit tests for each component using pytest-asyncio
- Integration tests verify end-to-end SLA functionality
- Mock database for health check unit tests
- Use time mocking for uptime calculations
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| RT-5 | Health endpoints, metrics, 99.9% SLA tracking |
| ADR-8 | Checkpoint fallback, genesis anchor verification |
| FR44 | No auth on health/metrics endpoints |
| FR48 | Same rate limits for all users |
| CT-11 | Accurate health status (HALT OVER DEGRADE) |

### Key Design Decisions
1. **Separate health and ready endpoints**: `/health` for liveness, `/ready` for readiness
2. **Prometheus format**: Standard exposition format for monitoring tools
3. **Rolling window SLA**: 30-day rolling window for percentage calculation
4. **Checkpoint fallback**: Dedicated endpoint for offline verification path
5. **Alert thresholds**: 3 consecutive failures before alerting
6. **Dependency health**: Includes latency measurement for degraded detection

### Performance Considerations
- **Health check latency**: Should return < 100ms
- **Metrics generation**: Lightweight, no heavy queries
- **SLA calculation**: Cached or incremental, not computed on every request
- **Checkpoint queries**: Use indexed lookups

### External Monitoring Integration
- Configure external monitoring service (e.g., UptimeRobot, Pingdom, Datadog)
- Point to `/v1/observer/health` endpoint
- Set check interval to 30 seconds
- Alert on 3 consecutive failures
- Webhook integration for alerts

### Runbook Requirements
Per Epic 4 runbook requirement: "Observer API Operations"
- Document health endpoint interpretation
- Checkpoint fallback verification procedure
- SLA reporting and incident response
- External monitoring setup guide

## Dev Notes

### Project Structure Notes
- API routes: `src/api/routes/observer.py` (add health endpoints)
- Models: `src/api/models/observer.py` (add health models)
- New service: `src/application/services/uptime_service.py`
- New port: `src/application/ports/uptime_tracker.py`
- New monitoring: `src/infrastructure/monitoring/external_monitor.py`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.9]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-8]
- [Source: _bmad-output/project-context.md - Alert severity levels, health endpoints]
- [Source: src/api/routes/observer.py - Existing observer endpoints]
- [Source: src/api/routes/health.py - Basic health check pattern]
- [Source: _bmad-output/implementation-artifacts/stories/4-8-observer-push-notifications.md - Previous story]
- [External: Prometheus Exposition Format](https://prometheus.io/docs/instrumenting/exposition_formats/)
- [External: UptimeRobot API](https://uptimerobot.com/api/)

### Patterns to Follow
- Use Pydantic models for all API request/response types
- Async/await for all I/O operations
- Type hints on all functions
- FastAPI Depends for dependency injection
- Structlog for logging (no print, no f-strings in logs)
- Domain exceptions for error cases
- PlainTextResponse for Prometheus metrics

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

