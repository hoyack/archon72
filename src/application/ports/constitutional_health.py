"""Constitutional health port interface (Story 8.10, ADR-10).

Defines the protocol for querying constitutional health metrics.
This is a composite port that aggregates metrics from other ports:
- BreachRepository (breach count)
- OverrideTrendRepository (override rate)
- DissentMetricsPort (dissent health)
- WitnessPoolMonitor (witness coverage)

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- System health = worst component health (conservative)
"""

from __future__ import annotations

from typing import Protocol

from src.domain.models.constitutional_health import (
    ConstitutionalHealthSnapshot,
    ConstitutionalHealthStatus,
)


class ConstitutionalHealthPort(Protocol):
    """Protocol for constitutional health queries (ADR-10).

    This port provides unified access to constitutional health metrics.
    Implementations aggregate data from multiple sources:
    - Breach count from BreachRepository
    - Override rate from OverrideTrendRepository
    - Dissent health from DissentMetricsPort
    - Witness coverage from WitnessPoolMonitor

    Constitutional Constraints:
    - ADR-10: Constitutional health is a blocking gate
    - System health = worst component health (conservative)
    - UNHEALTHY status blocks ceremonies

    Methods:
        get_constitutional_health: Get full health snapshot.
        get_breach_count: Get unacknowledged breach count.
        get_override_rate: Get daily override rate.
        get_dissent_health: Get rolling average dissent percentage.
        get_witness_coverage: Get effective witness pool size.
        get_overall_status: Get calculated overall status.
        is_blocking_ceremonies: Check if ceremonies are blocked.
        check_ceremony_allowed: Check if a ceremony can proceed.
    """

    async def get_constitutional_health(self) -> ConstitutionalHealthSnapshot:
        """Get full constitutional health snapshot (AC1).

        Aggregates all constitutional metrics into a single snapshot.
        Calculates overall status per ADR-10: worst component health.

        Returns:
            ConstitutionalHealthSnapshot with all metrics and status.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        ...

    async def get_breach_count(self) -> int:
        """Get unacknowledged breach count in 90-day window (FR32).

        Returns:
            Number of unacknowledged breaches.
            WARNING at 8, CRITICAL at >10.

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...

    async def get_override_rate(self) -> int:
        """Get daily override rate (Story 8.4).

        Returns:
            Number of overrides today.
            WARNING at 3 (incident threshold), CRITICAL at 6.

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...

    async def get_dissent_health(self) -> float:
        """Get rolling 30-day average dissent percentage (NFR-023).

        Returns:
            Dissent percentage (0.0-100.0).
            WARNING if <10%, CRITICAL if <5%.

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...

    async def get_witness_coverage(self) -> int:
        """Get effective witness pool size (FR117).

        Returns:
            Number of available witnesses.
            WARNING if <12, CRITICAL if <6.

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...

    async def get_overall_status(self) -> ConstitutionalHealthStatus:
        """Get overall constitutional health status (ADR-10).

        Per ADR-10 resolution: System health = worst component health.

        Returns:
            UNHEALTHY if any metric is critical,
            WARNING if any metric is at warning,
            HEALTHY if all metrics are within acceptable ranges.

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...

    async def is_blocking_ceremonies(self) -> bool:
        """Check if ceremonies are blocked (AC4).

        Per ADR-10: Ceremonies are blocked when constitutional
        health is UNHEALTHY. Emergency override required to proceed.

        Returns:
            True if ceremonies cannot proceed due to health status.

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...

    async def check_ceremony_allowed(self) -> tuple[bool, str | None]:
        """Check if a ceremony can proceed (AC4).

        Provides detailed information about ceremony blocking status.

        Returns:
            Tuple of (allowed, reason):
            - (True, None) if ceremony can proceed
            - (False, reason_string) if blocked with explanation

        Raises:
            SystemHaltedError: If system is halted.
        """
        ...
