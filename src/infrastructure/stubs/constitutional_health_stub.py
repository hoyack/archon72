"""Constitutional health stub for testing (Story 8.10, ADR-10).

Provides in-memory implementation of ConstitutionalHealthPort for unit tests.

Usage:
    stub = ConstitutionalHealthStub()
    stub.set_breach_count(5)
    stub.set_override_rate(2)

    health = await stub.get_constitutional_health()
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.ports.constitutional_health import ConstitutionalHealthPort
from src.domain.models.constitutional_health import (
    ConstitutionalHealthSnapshot,
    ConstitutionalHealthStatus,
)


class ConstitutionalHealthStub(ConstitutionalHealthPort):
    """In-memory stub implementation of ConstitutionalHealthPort.

    Allows tests to set specific metric values and verify behavior
    without real infrastructure dependencies.

    All values default to healthy ranges.
    """

    def __init__(self) -> None:
        """Initialize stub with healthy default values."""
        self._breach_count: int = 0
        self._override_rate: int = 0
        self._dissent_health: float = 50.0  # Healthy default
        self._witness_coverage: int = 20  # Above minimum
        self._is_halted: bool = False

    # Configuration methods for tests

    def set_breach_count(self, count: int) -> None:
        """Set the breach count metric."""
        self._breach_count = count

    def set_override_rate(self, rate: int) -> None:
        """Set the daily override rate metric."""
        self._override_rate = rate

    def set_dissent_health(self, percent: float) -> None:
        """Set the dissent health percentage."""
        self._dissent_health = percent

    def set_witness_coverage(self, count: int) -> None:
        """Set the witness coverage count."""
        self._witness_coverage = count

    def set_halted(self, halted: bool) -> None:
        """Set the halt state for testing."""
        self._is_halted = halted

    def configure_healthy(self) -> None:
        """Configure all metrics to healthy values."""
        self._breach_count = 0
        self._override_rate = 0
        self._dissent_health = 50.0
        self._witness_coverage = 20
        self._is_halted = False

    def configure_warning(self, metric: str = "breach_count") -> None:
        """Configure a specific metric to warning level.

        Args:
            metric: Which metric to set to warning.
                   Options: breach_count, override_rate, dissent_health, witness_coverage
        """
        self.configure_healthy()
        if metric == "breach_count":
            self._breach_count = 8  # At warning threshold
        elif metric == "override_rate":
            self._override_rate = 3  # At incident threshold
        elif metric == "dissent_health":
            self._dissent_health = 9.0  # Below 10% warning
        elif metric == "witness_coverage":
            self._witness_coverage = 10  # Below 12 degraded

    def configure_critical(self, metric: str = "breach_count") -> None:
        """Configure a specific metric to critical level.

        Args:
            metric: Which metric to set to critical.
                   Options: breach_count, override_rate, dissent_health, witness_coverage
        """
        self.configure_healthy()
        if metric == "breach_count":
            self._breach_count = 11  # Above 10 critical
        elif metric == "override_rate":
            self._override_rate = 7  # Above 6 critical
        elif metric == "dissent_health":
            self._dissent_health = 4.0  # Below 5% critical
        elif metric == "witness_coverage":
            self._witness_coverage = 5  # Below 6 critical

    # Protocol implementation

    async def get_constitutional_health(self) -> ConstitutionalHealthSnapshot:
        """Get full constitutional health snapshot."""
        return ConstitutionalHealthSnapshot(
            breach_count=self._breach_count,
            override_rate_daily=self._override_rate,
            dissent_health_percent=self._dissent_health,
            witness_coverage=self._witness_coverage,
            calculated_at=datetime.now(timezone.utc),
        )

    async def get_breach_count(self) -> int:
        """Get unacknowledged breach count."""
        return self._breach_count

    async def get_override_rate(self) -> int:
        """Get daily override rate."""
        return self._override_rate

    async def get_dissent_health(self) -> float:
        """Get dissent health percentage."""
        return self._dissent_health

    async def get_witness_coverage(self) -> int:
        """Get witness coverage count."""
        return self._witness_coverage

    async def get_overall_status(self) -> ConstitutionalHealthStatus:
        """Get overall status from snapshot."""
        snapshot = await self.get_constitutional_health()
        return snapshot.overall_status

    async def is_blocking_ceremonies(self) -> bool:
        """Check if ceremonies are blocked."""
        status = await self.get_overall_status()
        return status == ConstitutionalHealthStatus.UNHEALTHY

    async def check_ceremony_allowed(self) -> tuple[bool, str | None]:
        """Check if a ceremony can proceed."""
        snapshot = await self.get_constitutional_health()

        if not snapshot.ceremonies_blocked:
            return (True, None)

        reasons = snapshot.blocking_reasons
        if reasons:
            reason_text = "; ".join(reasons)
            return (False, f"Constitutional health blocking ceremonies: {reason_text}")
        else:
            return (False, "Constitutional health is UNHEALTHY")
