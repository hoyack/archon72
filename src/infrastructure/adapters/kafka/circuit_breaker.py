"""Circuit breaker for Kafka publish operations.

Story 2.2.1: Implement Circuit Breaker for Kafka
Pattern: Circuit breaker (Hystrix-style)

The circuit breaker prevents repeated attempts to use Kafka when it's
unhealthy, allowing fast fallback to sync validation without retry overhead.

States:
- CLOSED: Normal operation, requests go through
- OPEN: Kafka unhealthy, requests immediately fall back to sync
- HALF_OPEN: Testing if Kafka recovered, next request is a probe

Transitions:
- CLOSED -> OPEN: After FAILURE_THRESHOLD consecutive failures
- OPEN -> HALF_OPEN: After RESET_TIMEOUT seconds
- HALF_OPEN -> CLOSED: If probe succeeds
- HALF_OPEN -> OPEN: If probe fails
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast, fallback active
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitMetrics:
    """Metrics tracked by the circuit breaker."""

    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    last_state_change: float = field(default_factory=time.monotonic)
    transitions: int = 0


class CircuitBreaker:
    """Circuit breaker for Kafka operations.

    Usage:
        breaker = CircuitBreaker(failure_threshold=3, reset_timeout=30)

        if breaker.should_allow_request():
            try:
                await kafka_publish(...)
                breaker.record_success()
            except KafkaError:
                breaker.record_failure()
                # Fall back to sync
        else:
            # Circuit is open, fall back to sync immediately
            await sync_validation(...)

    The circuit breaker is NOT async-safe for concurrent modifications.
    In practice, this is fine because vote publishing is sequential
    per session (archons vote one at a time).
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
        success_threshold: int = 1,
        on_state_change: Callable[[CircuitState, CircuitState], None] | None = None,
    ) -> None:
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Consecutive failures before circuit opens
            reset_timeout: Seconds before half-open state
            success_threshold: Successes in half-open before closing
            on_state_change: Optional callback on state transitions
        """
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._success_threshold = success_threshold
        self._on_state_change = on_state_change

        self._state = CircuitState.CLOSED
        self._metrics = CircuitMetrics()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (may transition based on time)."""
        self._check_state_transition()
        return self._state

    @property
    def metrics(self) -> CircuitMetrics:
        """Get circuit metrics for monitoring."""
        return self._metrics

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    def _check_state_transition(self) -> None:
        """Check if time-based state transition is needed."""
        if self._state != CircuitState.OPEN:
            return

        # Check if reset timeout has elapsed
        elapsed = time.monotonic() - self._metrics.last_state_change
        if elapsed >= self._reset_timeout:
            self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if new_state == self._state:
            return

        old_state = self._state
        self._state = new_state
        self._metrics.last_state_change = time.monotonic()
        self._metrics.transitions += 1

        # Reset counters on state change
        if new_state == CircuitState.CLOSED:
            self._metrics.consecutive_failures = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._metrics.consecutive_successes = 0

        logger.info(
            "Circuit breaker state change: %s -> %s (transitions=%d)",
            old_state.value,
            new_state.value,
            self._metrics.transitions,
        )

        if self._on_state_change:
            self._on_state_change(old_state, new_state)

    def should_allow_request(self) -> bool:
        """Check if a request should be allowed through.

        Returns:
            True if request should proceed (CLOSED or HALF_OPEN)
            False if request should fall back (OPEN)
        """
        current_state = self.state  # Triggers time-based transitions

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            # Allow one probe request
            return True

        # OPEN state - reject immediately
        return False

    def record_success(self) -> None:
        """Record a successful operation.

        In HALF_OPEN: After success_threshold successes, close circuit
        In CLOSED: Reset failure counter
        """
        self._metrics.consecutive_successes += 1
        self._metrics.consecutive_failures = 0
        self._metrics.total_successes += 1
        self._metrics.last_success_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            if self._metrics.consecutive_successes >= self._success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def record_failure(self) -> None:
        """Record a failed operation.

        In CLOSED: After failure_threshold failures, open circuit
        In HALF_OPEN: Immediately re-open circuit
        """
        self._metrics.consecutive_failures += 1
        self._metrics.consecutive_successes = 0
        self._metrics.total_failures += 1
        self._metrics.last_failure_time = time.monotonic()

        if self._state == CircuitState.CLOSED:
            if self._metrics.consecutive_failures >= self._failure_threshold:
                self._transition_to(CircuitState.OPEN)

        elif self._state == CircuitState.HALF_OPEN:
            # Probe failed, re-open immediately
            self._transition_to(CircuitState.OPEN)

    def force_open(self) -> None:
        """Force circuit to open state.

        Used when startup health gate fails (Story 2.2.2).
        """
        self._transition_to(CircuitState.OPEN)
        logger.warning("Circuit breaker forced OPEN")

    def force_closed(self) -> None:
        """Force circuit to closed state.

        Used for testing or manual recovery.
        """
        self._transition_to(CircuitState.CLOSED)
        logger.info("Circuit breaker forced CLOSED")

    def reset(self) -> None:
        """Reset circuit to initial state."""
        self._state = CircuitState.CLOSED
        self._metrics = CircuitMetrics()
        logger.info("Circuit breaker reset")

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring.

        Returns:
            Dictionary with state and metrics
        """
        return {
            "state": self.state.value,
            "consecutive_failures": self._metrics.consecutive_failures,
            "consecutive_successes": self._metrics.consecutive_successes,
            "total_failures": self._metrics.total_failures,
            "total_successes": self._metrics.total_successes,
            "transitions": self._metrics.transitions,
            "failure_threshold": self._failure_threshold,
            "reset_timeout": self._reset_timeout,
        }
