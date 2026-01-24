"""Startup health gate for Kafka async validation.

Story 2.2.2: Implement Startup Health Gate
Pre-mortems: P7 (Worker presence check)
Red Team: R2 (Schema Registry required)

This module checks Kafka infrastructure health at application startup
and configures the circuit breaker accordingly. If Kafka is unhealthy,
the circuit breaker is forced OPEN so the application starts in a
safe state that falls back to sync validation.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.application.ports.kafka_health import KafkaHealthProtocol, KafkaHealthStatus
from src.infrastructure.adapters.kafka.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class StartupHealthResult(Enum):
    """Result of startup health check."""

    HEALTHY = "healthy"  # All checks passed, async validation enabled
    DEGRADED = "degraded"  # Some checks failed, circuit breaker OPEN
    UNAVAILABLE = "unavailable"  # Kafka completely unavailable


@dataclass(frozen=True)
class StartupHealthReport:
    """Report from startup health gate.

    Attributes:
        result: Overall health result
        kafka_status: Detailed Kafka health status
        circuit_breaker_state: State of circuit breaker after startup
        async_validation_enabled: Whether async validation can proceed
        errors: List of health check errors
        recommendations: Suggestions for resolving issues
    """

    result: StartupHealthResult
    kafka_status: KafkaHealthStatus | None
    circuit_breaker_state: str
    async_validation_enabled: bool
    errors: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/monitoring."""
        return {
            "result": self.result.value,
            "async_validation_enabled": self.async_validation_enabled,
            "circuit_breaker_state": self.circuit_breaker_state,
            "kafka_status": {
                "broker_reachable": self.kafka_status.broker_reachable
                if self.kafka_status
                else False,
                "schema_registry_reachable": self.kafka_status.schema_registry_reachable
                if self.kafka_status
                else False,
                "consumer_group_active": self.kafka_status.consumer_group_active
                if self.kafka_status
                else False,
                "consumer_lag": self.kafka_status.consumer_lag
                if self.kafka_status
                else -1,
            },
            "errors": self.errors,
            "recommendations": self.recommendations,
        }


class StartupHealthGate:
    """Startup health gate for Kafka async validation.

    Checks Kafka infrastructure health at startup and configures
    the circuit breaker for safe operation.

    Decision matrix:
    - Broker + Schema Registry + Workers = HEALTHY (async enabled)
    - Broker + Schema Registry (no workers) = DEGRADED (circuit OPEN)
    - Schema Registry down = DEGRADED (circuit OPEN, R2)
    - Broker down = UNAVAILABLE (circuit OPEN)

    Usage:
        gate = StartupHealthGate(health_checker, circuit_breaker)

        # At application startup
        report = await gate.check_and_configure()

        if report.async_validation_enabled:
            logger.info("Async validation enabled")
        else:
            logger.warning("Async validation disabled, using sync fallback")

    Thread Safety:
        This class is designed to be called once at startup.
        It is NOT safe for concurrent calls.
    """

    def __init__(
        self,
        health_checker: KafkaHealthProtocol,
        circuit_breaker: CircuitBreaker,
        retry_count: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> None:
        """Initialize the startup health gate.

        Args:
            health_checker: Kafka health checker instance
            circuit_breaker: Circuit breaker to configure
            retry_count: Number of health check retries
            retry_delay_seconds: Delay between retries
        """
        self._health_checker = health_checker
        self._circuit_breaker = circuit_breaker
        self._retry_count = retry_count
        self._retry_delay = retry_delay_seconds

    async def check_and_configure(self) -> StartupHealthReport:
        """Check Kafka health and configure circuit breaker.

        This method:
        1. Performs health check with retries
        2. Analyzes results
        3. Configures circuit breaker based on health
        4. Returns detailed report

        Returns:
            StartupHealthReport with results and recommendations
        """
        logger.info("Starting Kafka health gate check (retries=%d)", self._retry_count)

        # Attempt health check with retries
        kafka_status: KafkaHealthStatus | None = None
        last_error: str | None = None

        for attempt in range(1, self._retry_count + 1):
            try:
                kafka_status = await self._health_checker.check_health()

                if kafka_status.healthy:
                    logger.info(
                        "Kafka health check passed on attempt %d/%d",
                        attempt,
                        self._retry_count,
                    )
                    break

                logger.warning(
                    "Kafka health check failed on attempt %d/%d: %s",
                    attempt,
                    self._retry_count,
                    kafka_status.error_message,
                )

                if attempt < self._retry_count:
                    await asyncio.sleep(self._retry_delay)

            except Exception as e:
                last_error = str(e)
                logger.error(
                    "Kafka health check error on attempt %d/%d: %s",
                    attempt,
                    self._retry_count,
                    e,
                )
                if attempt < self._retry_count:
                    await asyncio.sleep(self._retry_delay)

        # Analyze results and configure circuit breaker
        return self._analyze_and_configure(kafka_status, last_error)

    def _analyze_and_configure(
        self,
        kafka_status: KafkaHealthStatus | None,
        last_error: str | None,
    ) -> StartupHealthReport:
        """Analyze health results and configure circuit breaker.

        Args:
            kafka_status: Health status from checker (may be None on error)
            last_error: Last error message if check failed

        Returns:
            StartupHealthReport with analysis and recommendations
        """
        errors: list[str] = []
        recommendations: list[str] = []

        # Handle complete failure to check health
        if kafka_status is None:
            self._circuit_breaker.force_open()
            errors.append(f"Failed to check Kafka health: {last_error}")
            recommendations.append("Check Kafka broker connectivity")
            recommendations.append("Verify KAFKA_BOOTSTRAP_SERVERS configuration")

            return StartupHealthReport(
                result=StartupHealthResult.UNAVAILABLE,
                kafka_status=None,
                circuit_breaker_state=self._circuit_breaker.state.value,
                async_validation_enabled=False,
                errors=errors,
                recommendations=recommendations,
            )

        # Analyze individual health components
        if not kafka_status.broker_reachable:
            errors.append("Kafka broker is not reachable")
            recommendations.append("Ensure Redpanda/Kafka is running")
            recommendations.append("Check KAFKA_BOOTSTRAP_SERVERS configuration")

        if not kafka_status.schema_registry_reachable:
            errors.append("Schema Registry is not reachable (R2 violation)")
            recommendations.append("Ensure Schema Registry is running")
            recommendations.append("Check SCHEMA_REGISTRY_URL configuration")

        if not kafka_status.consumer_group_active:
            errors.append("No active validator workers (P7 violation)")
            recommendations.append("Start validator worker containers")
            recommendations.append("Check consumer group configuration")

        # Add error message if present
        if kafka_status.error_message:
            errors.append(kafka_status.error_message)

        # Determine result and configure circuit breaker
        if kafka_status.healthy:
            # All good - close circuit breaker
            self._circuit_breaker.force_closed()
            logger.info("Kafka startup health gate PASSED - async validation enabled")

            return StartupHealthReport(
                result=StartupHealthResult.HEALTHY,
                kafka_status=kafka_status,
                circuit_breaker_state=self._circuit_breaker.state.value,
                async_validation_enabled=True,
                errors=[],
                recommendations=[],
            )

        elif kafka_status.broker_reachable:
            # Broker up but other issues - DEGRADED
            self._circuit_breaker.force_open()
            logger.warning(
                "Kafka startup health gate DEGRADED - async validation disabled"
            )

            return StartupHealthReport(
                result=StartupHealthResult.DEGRADED,
                kafka_status=kafka_status,
                circuit_breaker_state=self._circuit_breaker.state.value,
                async_validation_enabled=False,
                errors=errors,
                recommendations=recommendations,
            )

        else:
            # Broker down - UNAVAILABLE
            self._circuit_breaker.force_open()
            logger.error("Kafka startup health gate FAILED - Kafka unavailable")

            return StartupHealthReport(
                result=StartupHealthResult.UNAVAILABLE,
                kafka_status=kafka_status,
                circuit_breaker_state=self._circuit_breaker.state.value,
                async_validation_enabled=False,
                errors=errors,
                recommendations=recommendations,
            )

    async def wait_for_healthy(
        self,
        timeout_seconds: float = 60.0,
        check_interval_seconds: float = 5.0,
    ) -> StartupHealthReport:
        """Wait for Kafka to become healthy (optional blocking startup).

        This can be used for deployments that require Kafka to be
        healthy before the application accepts traffic.

        Args:
            timeout_seconds: Maximum time to wait
            check_interval_seconds: Time between checks

        Returns:
            StartupHealthReport (may be DEGRADED/UNAVAILABLE if timeout)
        """
        logger.info(
            "Waiting for Kafka to become healthy (timeout=%.1fs)",
            timeout_seconds,
        )

        start_time = asyncio.get_event_loop().time()
        last_report: StartupHealthReport | None = None

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            last_report = await self.check_and_configure()

            if last_report.async_validation_enabled:
                logger.info(
                    "Kafka became healthy after %.1fs",
                    asyncio.get_event_loop().time() - start_time,
                )
                return last_report

            logger.info(
                "Kafka not yet healthy, waiting %.1fs before retry...",
                check_interval_seconds,
            )
            await asyncio.sleep(check_interval_seconds)

        # Timeout - return last status
        logger.warning(
            "Timeout waiting for Kafka to become healthy after %.1fs",
            timeout_seconds,
        )

        return last_report or StartupHealthReport(
            result=StartupHealthResult.UNAVAILABLE,
            kafka_status=None,
            circuit_breaker_state=self._circuit_breaker.state.value,
            async_validation_enabled=False,
            errors=["Timeout waiting for Kafka to become healthy"],
            recommendations=["Check Kafka infrastructure and retry"],
        )


async def create_startup_health_gate(
    bootstrap_servers: str,
    schema_registry_url: str,
    consumer_group: str,
    circuit_breaker: CircuitBreaker,
) -> tuple[StartupHealthGate, StartupHealthReport]:
    """Factory function to create and run startup health gate.

    Convenience function that creates the health checker, gate,
    and runs the initial health check.

    Args:
        bootstrap_servers: Kafka bootstrap servers
        schema_registry_url: Schema Registry URL
        consumer_group: Consumer group to check
        circuit_breaker: Circuit breaker to configure

    Returns:
        Tuple of (gate, initial_report)
    """
    from src.infrastructure.adapters.kafka.kafka_health_checker import (
        KafkaHealthChecker,
    )

    health_checker = KafkaHealthChecker(
        bootstrap_servers=bootstrap_servers,
        schema_registry_url=schema_registry_url,
        consumer_group=consumer_group,
    )

    gate = StartupHealthGate(
        health_checker=health_checker,
        circuit_breaker=circuit_breaker,
    )

    report = await gate.check_and_configure()

    return gate, report
