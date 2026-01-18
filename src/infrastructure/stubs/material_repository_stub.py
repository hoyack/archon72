"""Material repository stub (Story 9.3, FR57).

In-memory stub implementation of MaterialRepositoryProtocol for testing.
Provides configurable behavior for unit and integration tests.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from src.application.ports.material_repository import (
    Material,
    MaterialRepositoryProtocol,
)


class MaterialRepositoryStub(MaterialRepositoryProtocol):
    """Stub implementation of MaterialRepositoryProtocol.

    Provides in-memory storage for materials with configurable
    behavior for testing scenarios.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._materials: dict[str, Material] = {}

    def clear(self) -> None:
        """Clear all stored data."""
        self._materials.clear()

    def add_material(self, material: Material) -> None:
        """Add a material directly to storage for testing.

        Args:
            material: The material to add.
        """
        self._materials[material.material_id] = material

    def add_materials(self, materials: list[Material]) -> None:
        """Add multiple materials for testing.

        Args:
            materials: List of materials to add.
        """
        for material in materials:
            self._materials[material.material_id] = material

    async def get_all_public_materials(self) -> list[Material]:
        """Get all public materials for audit.

        Returns:
            List of all public materials.
        """
        return list(self._materials.values())

    async def get_materials_by_type(self, material_type: str) -> list[Material]:
        """Get materials filtered by type.

        Args:
            material_type: Type of material to retrieve.

        Returns:
            List of materials matching the specified type.
        """
        return [m for m in self._materials.values() if m.material_type == material_type]

    async def get_material_count(self) -> int:
        """Get total count of public materials.

        Returns:
            Total number of public materials in the system.
        """
        return len(self._materials)

    async def get_material(self, material_id: str) -> Material | None:
        """Get a specific material by ID.

        Args:
            material_id: The ID of the material to retrieve.

        Returns:
            The material if found, None otherwise.
        """
        return self._materials.get(material_id)


class ConfigurableMaterialRepositoryStub(MaterialRepositoryStub):
    """Extended stub with additional configuration options.

    Provides more fine-grained control for testing edge cases.
    """

    def __init__(self) -> None:
        """Initialize the configurable stub."""
        super().__init__()
        self._get_all_should_fail = False
        self._get_all_failure_message = "Simulated get all failure"

    def configure_get_all_failure(
        self,
        should_fail: bool,
        message: str = "Simulated get all failure",
    ) -> None:
        """Configure whether get_all_public_materials should fail.

        Args:
            should_fail: Whether to raise error on get all.
            message: Error message to use.
        """
        self._get_all_should_fail = should_fail
        self._get_all_failure_message = message

    async def get_all_public_materials(self) -> list[Material]:
        """Get all public materials for audit.

        Returns:
            List of all public materials.

        Raises:
            RuntimeError: If configured to fail.
        """
        if self._get_all_should_fail:
            raise RuntimeError(self._get_all_failure_message)
        return await super().get_all_public_materials()
