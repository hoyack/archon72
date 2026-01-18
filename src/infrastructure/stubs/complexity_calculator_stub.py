"""Complexity calculator stub implementation (Story 8.6, CT-14, RT-6, SC-3).

This module provides an in-memory stub implementation of ComplexityCalculatorPort
for testing and development purposes.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event, not just alert.
- SC-3: Self-consistency finding - complexity budget dashboard required.

Usage:
    # Default stub (within budget)
    stub = ComplexityCalculatorStub()

    # Stub with custom values
    stub = ComplexityCalculatorStub(
        adr_count=12,
        ceremony_types=8,
        cross_component_deps=15,
    )

    # Stub with breached values
    stub = ComplexityCalculatorStub.with_breached_adr_count()
"""

from __future__ import annotations

from src.application.ports.complexity_calculator import ComplexityCalculatorPort
from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
    ComplexitySnapshot,
)

# Default values (within budget, at 50% utilization)
DEFAULT_ADR_COUNT: int = 7
DEFAULT_CEREMONY_TYPES: int = 5
DEFAULT_CROSS_COMPONENT_DEPS: int = 10


class ComplexityCalculatorStub(ComplexityCalculatorPort):
    """In-memory stub for complexity calculation (testing only).

    This stub provides configurable complexity metrics for testing scenarios.
    Default values are set to 50% of limits (within budget).

    The stub supports both static configuration and dynamic updates for
    testing different scenarios.
    """

    def __init__(
        self,
        adr_count: int = DEFAULT_ADR_COUNT,
        ceremony_types: int = DEFAULT_CEREMONY_TYPES,
        cross_component_deps: int = DEFAULT_CROSS_COMPONENT_DEPS,
    ) -> None:
        """Initialize the stub with configurable values.

        Args:
            adr_count: Number of ADRs (default: 7, limit: 15).
            ceremony_types: Number of ceremony types (default: 5, limit: 10).
            cross_component_deps: Number of cross-component deps (default: 10, limit: 20).
        """
        self._adr_count = adr_count
        self._ceremony_types = ceremony_types
        self._cross_component_deps = cross_component_deps
        self._snapshot_count = 0
        self._failure_mode: Exception | None = None

    # Factory methods for common test scenarios

    @classmethod
    def with_default_values(cls) -> ComplexityCalculatorStub:
        """Create stub with default values (within budget at 50%)."""
        return cls()

    @classmethod
    def with_warning_values(cls) -> ComplexityCalculatorStub:
        """Create stub with values at warning threshold (80%+)."""
        return cls(
            adr_count=12,  # 80% of 15
            ceremony_types=8,  # 80% of 10
            cross_component_deps=16,  # 80% of 20
        )

    @classmethod
    def with_breached_adr_count(cls) -> ComplexityCalculatorStub:
        """Create stub with breached ADR count."""
        return cls(
            adr_count=ADR_LIMIT + 3,  # 18 (breach by 3)
            ceremony_types=DEFAULT_CEREMONY_TYPES,
            cross_component_deps=DEFAULT_CROSS_COMPONENT_DEPS,
        )

    @classmethod
    def with_breached_ceremony_types(cls) -> ComplexityCalculatorStub:
        """Create stub with breached ceremony types."""
        return cls(
            adr_count=DEFAULT_ADR_COUNT,
            ceremony_types=CEREMONY_TYPE_LIMIT + 2,  # 12 (breach by 2)
            cross_component_deps=DEFAULT_CROSS_COMPONENT_DEPS,
        )

    @classmethod
    def with_breached_cross_component_deps(cls) -> ComplexityCalculatorStub:
        """Create stub with breached cross-component dependencies."""
        return cls(
            adr_count=DEFAULT_ADR_COUNT,
            ceremony_types=DEFAULT_CEREMONY_TYPES,
            cross_component_deps=CROSS_COMPONENT_DEP_LIMIT + 5,  # 25 (breach by 5)
        )

    @classmethod
    def with_all_breached(cls) -> ComplexityCalculatorStub:
        """Create stub with all dimensions breached."""
        return cls(
            adr_count=ADR_LIMIT + 3,
            ceremony_types=CEREMONY_TYPE_LIMIT + 2,
            cross_component_deps=CROSS_COMPONENT_DEP_LIMIT + 5,
        )

    @classmethod
    def with_custom_values(
        cls,
        adr_count: int | None = None,
        ceremony_types: int | None = None,
        cross_component_deps: int | None = None,
    ) -> ComplexityCalculatorStub:
        """Create stub with custom values.

        Args:
            adr_count: Custom ADR count (None = use default).
            ceremony_types: Custom ceremony types (None = use default).
            cross_component_deps: Custom deps (None = use default).

        Returns:
            Configured stub instance.
        """
        return cls(
            adr_count=adr_count if adr_count is not None else DEFAULT_ADR_COUNT,
            ceremony_types=ceremony_types
            if ceremony_types is not None
            else DEFAULT_CEREMONY_TYPES,
            cross_component_deps=cross_component_deps
            if cross_component_deps is not None
            else DEFAULT_CROSS_COMPONENT_DEPS,
        )

    # Protocol implementation

    async def count_adrs(self) -> int:
        """Count ADRs (Architecture Decision Records).

        Returns:
            Current ADR count.

        Raises:
            Exception: If failure mode is set.
        """
        if self._failure_mode:
            raise self._failure_mode
        return self._adr_count

    async def count_ceremony_types(self) -> int:
        """Count ceremony types.

        Returns:
            Current ceremony type count.

        Raises:
            Exception: If failure mode is set.
        """
        if self._failure_mode:
            raise self._failure_mode
        return self._ceremony_types

    async def count_cross_component_deps(self) -> int:
        """Count cross-component dependencies.

        Returns:
            Current cross-component dependency count.

        Raises:
            Exception: If failure mode is set.
        """
        if self._failure_mode:
            raise self._failure_mode
        return self._cross_component_deps

    async def calculate_snapshot(
        self,
        triggered_by: str | None = None,
    ) -> ComplexitySnapshot:
        """Calculate current complexity snapshot.

        Args:
            triggered_by: Optional identifier of what triggered this calculation.

        Returns:
            ComplexitySnapshot with current values for all dimensions.

        Raises:
            Exception: If failure mode is set.
        """
        if self._failure_mode:
            raise self._failure_mode

        self._snapshot_count += 1

        snapshot = ComplexitySnapshot.create(
            adr_count=self._adr_count,
            ceremony_types=self._ceremony_types,
            cross_component_deps=self._cross_component_deps,
            triggered_by=triggered_by,
        )

        return snapshot

    # Test helper methods (not part of protocol)

    def set_adr_count(self, count: int) -> None:
        """Update ADR count (for testing dynamic changes)."""
        self._adr_count = count

    def set_ceremony_types(self, count: int) -> None:
        """Update ceremony type count (for testing dynamic changes)."""
        self._ceremony_types = count

    def set_cross_component_deps(self, count: int) -> None:
        """Update cross-component dependency count (for testing dynamic changes)."""
        self._cross_component_deps = count

    def set_failure_mode(self, error: Exception | None) -> None:
        """Set an exception to raise on all operations (for testing failures).

        Args:
            error: Exception to raise, or None to clear failure mode.
        """
        self._failure_mode = error

    def clear_failure_mode(self) -> None:
        """Clear failure mode (resume normal operation)."""
        self._failure_mode = None

    def get_snapshot_count(self) -> int:
        """Get number of snapshots calculated."""
        return self._snapshot_count

    def reset_snapshot_count(self) -> None:
        """Reset snapshot count to zero."""
        self._snapshot_count = 0

    @property
    def current_values(self) -> dict[str, int]:
        """Get current values as a dictionary (for debugging)."""
        return {
            "adr_count": self._adr_count,
            "ceremony_types": self._ceremony_types,
            "cross_component_deps": self._cross_component_deps,
        }
