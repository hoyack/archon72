"""Fork Monitoring Application Service (FR16, FR84, FR85, Story 3.1, Story 3.8).

This service provides continuous fork monitoring by running a background
task that periodically checks for fork conditions.

Constitutional Constraints:
- FR16: System SHALL continuously monitor for conflicting hashes
- FR84: Fork detection signals MUST be signed by detecting service (Story 3.8)
- FR85: Rate limit: 3 signals/hour/source prevents DoS spam (Story 3.8)
- AC3: Fork checks run at least every 10 seconds
- CT-11: Silent failure destroys legitimacy -> Detection MUST be logged
- CT-12: Witnessing creates accountability

Note: This story (3.1) handles DETECTION only. Halt logic is in Story 3.2.
The callback mechanism allows Story 3.2 to plug in halt triggering.
Story 3.8 adds signing and rate limiting for fork signals.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from structlog import get_logger

from src.application.ports.fork_monitor import ForkMonitor
from src.application.ports.fork_signal_rate_limiter import ForkSignalRateLimiterPort
from src.domain.events.fork_detected import ForkDetectedPayload
from src.domain.models.signed_fork_signal import SignedForkSignal

if TYPE_CHECKING:
    pass


class SigningServiceProtocol(Protocol):
    """Protocol for signing service (Story 3.8, FR84).

    Allows dependency injection of signing service for fork signals.
    """

    async def sign_fork_signal(self, signable_content: bytes) -> tuple[str, str, int]:
        """Sign fork signal content.

        Args:
            signable_content: Bytes to sign

        Returns:
            Tuple of (signature_base64, key_id, alg_version)
        """
        ...

    async def verify_fork_signal(
        self, signable_content: bytes, signature: str, key_id: str
    ) -> bool:
        """Verify fork signal signature.

        Args:
            signable_content: Content that was signed
            signature: Base64-encoded signature
            key_id: Key ID used for signing

        Returns:
            True if valid, False otherwise
        """
        ...


@dataclass(frozen=True)
class ForkHandleResult:
    """Result of handling a fork with rate limiting (Story 3.8, FR85).

    Attributes:
        rate_limited: True if signal was rate-limited
        signed_signal: SignedForkSignal if not rate-limited, None otherwise
    """

    rate_limited: bool
    signed_signal: SignedForkSignal | None


logger = get_logger()

# Type alias for fork detection callback
ForkDetectedCallback = Callable[[ForkDetectedPayload], Awaitable[None]]


class ForkMonitoringService:
    """Application service for continuous fork monitoring.

    This service runs a background task that periodically checks for
    fork conditions using the injected ForkMonitor.

    When a fork is detected, the on_fork_detected callback is invoked.
    This allows Story 3.2 to plug in halt triggering without coupling
    the detection logic to halt logic.

    Constitutional Constraints:
    - FR16: System SHALL continuously monitor for conflicting hashes
    - AC3: Fork checks run at least every 10 seconds
    - CT-11: Silent failure destroys legitimacy

    Attributes:
        service_id: Identifier for this monitoring service
        monitoring_interval_seconds: Interval between checks

    Example:
        >>> async def on_fork(fork: ForkDetectedPayload) -> None:
        ...     print(f"Fork detected: {fork.prev_hash}")
        ...
        >>> service = ForkMonitoringService(
        ...     fork_monitor=fork_monitor,
        ...     on_fork_detected=on_fork,
        ...     service_id="monitor-001",
        ... )
        >>> await service.start_monitoring()
        >>> # ... runs in background
        >>> await service.stop_monitoring()
    """

    def __init__(
        self,
        *,
        fork_monitor: ForkMonitor,
        on_fork_detected: ForkDetectedCallback,
        service_id: str,
        signing_service: SigningServiceProtocol | None = None,
        rate_limiter: ForkSignalRateLimiterPort | None = None,
    ) -> None:
        """Initialize the fork monitoring service.

        Args:
            fork_monitor: The ForkMonitor to use for detection.
            on_fork_detected: Async callback invoked when fork is detected.
            service_id: Identifier for this service.
            signing_service: Optional signing service for FR84 (Story 3.8).
            rate_limiter: Optional rate limiter for FR85 (Story 3.8).
        """
        self._fork_monitor = fork_monitor
        self._on_fork_detected = on_fork_detected
        self._service_id = service_id
        self._is_monitoring = False
        self._monitoring_task: asyncio.Task[None] | None = None
        self._log = logger.bind(service_id=service_id)
        # Story 3.8: Signing and rate limiting
        self._signing_service = signing_service
        self._rate_limiter = rate_limiter

    @property
    def service_id(self) -> str:
        """Get the service ID."""
        return self._service_id

    @property
    def monitoring_interval_seconds(self) -> int:
        """Get the monitoring interval from the fork monitor."""
        return self._fork_monitor.monitoring_interval_seconds

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is currently active."""
        return self._is_monitoring

    async def check_for_forks(self) -> ForkDetectedPayload | None:
        """Check for fork conditions.

        Delegates to the injected ForkMonitor.

        Returns:
            ForkDetectedPayload if fork detected, None otherwise.
        """
        return await self._fork_monitor.check_for_forks()

    async def start_monitoring(self) -> None:
        """Start continuous fork monitoring.

        Starts a background task that calls check_for_forks at the
        configured interval. Continues until stop_monitoring is called.

        The monitoring loop:
        1. Calls check_for_forks at each interval
        2. Logs detection latency for each cycle
        3. Handles errors gracefully (log and continue)
        4. Invokes callback when fork is found
        """
        if self._is_monitoring:
            self._log.warning("monitoring_already_running")
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._log.info(
            "fork_monitoring_started",
            interval_seconds=self.monitoring_interval_seconds,
        )

    async def stop_monitoring(self) -> None:
        """Stop continuous fork monitoring.

        Gracefully stops the monitoring background task.
        Waits for current check to complete if one is in progress.
        """
        if not self._is_monitoring:
            self._log.debug("monitoring_not_running")
            return

        self._is_monitoring = False

        if self._monitoring_task is not None:
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task
            self._monitoring_task = None

        self._log.info("fork_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Background loop for continuous fork monitoring.

        Runs until is_monitoring is set to False.
        Logs detection latency for each cycle.
        """
        self._log.debug("monitoring_loop_started")

        while self._is_monitoring:
            start_time = time.monotonic()
            fork_found = False

            try:
                fork = await self._fork_monitor.check_for_forks()
                if fork is not None:
                    fork_found = True
                    self._log.warning(
                        "fork_detected",
                        prev_hash=fork.prev_hash,
                        conflicting_events=len(fork.conflicting_event_ids),
                    )
                    await self._on_fork_detected(fork)
            except asyncio.CancelledError:
                # Graceful shutdown
                break
            except Exception as e:
                self._log.error("fork_check_failed", error=str(e), exc_info=True)
            finally:
                latency_ms = (time.monotonic() - start_time) * 1000
                self._log.info(
                    "fork_check_completed",
                    latency_ms=round(latency_ms, 2),
                    fork_found=fork_found,
                )

            # Wait for next interval
            try:
                await asyncio.sleep(self.monitoring_interval_seconds)
            except asyncio.CancelledError:
                break

        self._log.debug("monitoring_loop_ended")

    # Story 3.8: Signed Fork Signal Methods (FR84-FR85)

    async def create_signed_fork_signal(
        self, fork: ForkDetectedPayload
    ) -> SignedForkSignal:
        """Create a signed fork signal from a detection payload (FR84).

        Signs the fork detection payload using the configured signing
        service for external observer verification.

        Constitutional Constraints:
        - FR84: Fork detection signals MUST be signed
        - CT-12: Witnessing creates accountability

        Args:
            fork: The fork detection payload to sign

        Returns:
            SignedForkSignal with signature

        Raises:
            ValueError: If signing_service not configured
        """
        if self._signing_service is None:
            raise ValueError("SigningService not configured for fork signal signing")

        signable_content = fork.signable_content()
        signature, key_id, alg_version = await self._signing_service.sign_fork_signal(
            signable_content
        )

        return SignedForkSignal(
            fork_payload=fork,
            signature=signature,
            signing_key_id=key_id,
            sig_alg_version=alg_version,
        )

    async def validate_fork_signal(self, signal: SignedForkSignal) -> bool:
        """Validate a signed fork signal (FR84, AC2).

        Verifies the cryptographic signature on a fork signal to ensure
        it was created by the claimed detecting service.

        Constitutional Constraints:
        - FR84: Fork signals must be signed AND verifiable
        - CT-11: Silent failure destroys legitimacy

        Args:
            signal: The signed fork signal to validate

        Returns:
            True if signature is valid, False otherwise

        Raises:
            ValueError: If signing_service not configured
        """
        if self._signing_service is None:
            raise ValueError("SigningService not configured for signature verification")

        signable_content = signal.get_signable_content()
        return await self._signing_service.verify_fork_signal(
            signable_content,
            signal.signature,
            signal.signing_key_id,
        )

    async def handle_fork_with_rate_limit(
        self, fork: ForkDetectedPayload
    ) -> ForkHandleResult:
        """Handle a fork detection with rate limiting (FR85).

        Checks rate limit before creating signed signal. If rate limit
        is exceeded, logs the event but does not create a signed signal.

        Constitutional Constraints:
        - FR85: 3 signals/hour/source prevents DoS spam
        - CT-11: Silent failure destroys legitimacy

        Args:
            fork: The fork detection payload

        Returns:
            ForkHandleResult indicating if rate-limited and signal if created

        Raises:
            ValueError: If rate_limiter or signing_service not configured
        """
        if self._rate_limiter is None:
            raise ValueError("RateLimiter not configured for rate limiting")
        if self._signing_service is None:
            raise ValueError("SigningService not configured for fork signal signing")

        source_id = fork.detecting_service_id

        # Check rate limit
        if not await self._rate_limiter.check_rate_limit(source_id):
            self._log.warning(
                "fork_signal_rate_limited",
                source_id=source_id,
                prev_hash=fork.prev_hash,
            )
            return ForkHandleResult(rate_limited=True, signed_signal=None)

        # Within limit - create signed signal and record
        await self._rate_limiter.record_signal(source_id)
        signed_signal = await self.create_signed_fork_signal(fork)

        self._log.info(
            "fork_signal_created",
            source_id=source_id,
            prev_hash=fork.prev_hash,
            key_id=signed_signal.signing_key_id,
        )

        return ForkHandleResult(rate_limited=False, signed_signal=signed_signal)
