"""Complexity Calculator port definition (Story 8.6, SC-3, RT-6).

Defines the abstract interface for calculating complexity metrics.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- SC-3: Self-consistency finding - complexity budget dashboard required.

Usage:
    from src.application.ports.complexity_calculator import ComplexityCalculatorPort

    class MyComplexityCalculator(ComplexityCalculatorPort):
        async def count_adrs(self) -> int:
            # Implementation...
            pass
"""

from abc import ABC, abstractmethod

from src.domain.models.complexity_budget import ComplexitySnapshot


class ComplexityCalculatorPort(ABC):
    """Abstract protocol for complexity metric calculations.

    All complexity calculator implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific calculation implementations.

    Constitutional Constraint (CT-14):
    Complexity must be budgeted. This port defines how to measure the
    current values of each complexity dimension.

    Implementation Notes:
    - ADR count could scan ADR files or query a metadata store
    - Ceremony types could query a ceremony registry
    - Cross-component deps could analyze import graph or dependency manifest
    - For MVP, a stub implementation with configurable values is acceptable

    Methods:
        count_adrs: Count Architecture Decision Records
        count_ceremony_types: Count governance ceremony types
        count_cross_component_deps: Count cross-component dependencies
        calculate_snapshot: Calculate a full complexity snapshot
    """

    @abstractmethod
    async def count_adrs(self) -> int:
        """Count the number of Architecture Decision Records (ADRs).

        Constitutional Constraint (CT-14):
        ADRs represent architectural complexity that must be budgeted.
        The limit is 15 per CT-14.

        Returns:
            Current count of ADRs in the system.

        Raises:
            RuntimeError: If counting fails due to infrastructure issues.
        """
        ...

    @abstractmethod
    async def count_ceremony_types(self) -> int:
        """Count the number of governance ceremony types.

        Constitutional Constraint (CT-14):
        Each ceremony type adds governance complexity. The limit is 10.

        Returns:
            Current count of ceremony types defined in the system.

        Raises:
            RuntimeError: If counting fails due to infrastructure issues.
        """
        ...

    @abstractmethod
    async def count_cross_component_deps(self) -> int:
        """Count the number of cross-component dependencies.

        Constitutional Constraint (CT-14):
        Cross-component dependencies add coupling complexity. The limit is 20.

        Returns:
            Current count of cross-component dependencies.

        Raises:
            RuntimeError: If counting fails due to infrastructure issues.
        """
        ...

    async def calculate_snapshot(
        self,
        triggered_by: str | None = None,
    ) -> ComplexitySnapshot:
        """Calculate a complete complexity snapshot.

        Calls all count methods and combines results into a ComplexitySnapshot.
        This is a convenience method with a default implementation.

        Args:
            triggered_by: Optional description of what triggered this snapshot.

        Returns:
            ComplexitySnapshot with current values for all dimensions.

        Raises:
            RuntimeError: If any counting operation fails.
        """
        adr_count = await self.count_adrs()
        ceremony_types = await self.count_ceremony_types()
        cross_component_deps = await self.count_cross_component_deps()

        return ComplexitySnapshot.create(
            adr_count=adr_count,
            ceremony_types=ceremony_types,
            cross_component_deps=cross_component_deps,
            triggered_by=triggered_by,
        )
