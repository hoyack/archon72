"""Material repository port (Story 9.3, FR57).

Abstract interface for material storage operations.
Materials are public content items subject to quarterly
audit for prohibited language per FR57.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol

# Material type constants
MATERIAL_TYPE_PUBLICATION: Final[str] = "publication"
MATERIAL_TYPE_DOCUMENT: Final[str] = "document"
MATERIAL_TYPE_ANNOUNCEMENT: Final[str] = "announcement"


@dataclass(frozen=True, eq=True)
class Material:
    """A public material subject to audit (FR57).

    Materials are any public-facing content that must be
    scanned for prohibited language during quarterly audits.

    Attributes:
        material_id: Unique identifier for the material.
        material_type: Type of material (publication, document, etc.).
        title: Display title of the material.
        content: Full text content to scan.
        published_at: When the material was published.
        author_id: Optional author identifier.
    """

    material_id: str
    material_type: str
    title: str
    content: str
    published_at: datetime
    author_id: str | None = None

    def __post_init__(self) -> None:
        """Validate material fields per FR57.

        Raises:
            ValueError: If required fields are missing.
        """
        if not self.material_id:
            raise ValueError("FR57: material_id is required")
        if not self.material_type:
            raise ValueError("FR57: material_type is required")
        if not self.title:
            raise ValueError("FR57: title is required")
        if not self.content:
            raise ValueError("FR57: content is required for scanning")

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "material_id": self.material_id,
            "material_type": self.material_type,
            "title": self.title,
            "content": self.content,
            "published_at": self.published_at.isoformat(),
            "author_id": self.author_id,
        }


class MaterialRepositoryProtocol(Protocol):
    """Repository protocol for materials (FR57).

    Provides access to all public materials for quarterly
    audit scanning. Implementations may connect to various
    storage backends.

    Constitutional Constraints:
    - FR57: All public materials must be retrievable for audit
    - CT-11: Operations should respect halt state
    """

    async def get_all_public_materials(self) -> list[Material]:
        """Get all public materials for audit.

        Returns all materials that are subject to quarterly
        audit scanning. This includes publications, documents,
        and other public content.

        Returns:
            List of all public materials.

        Note:
            For large datasets, implementations may need to
            support pagination or streaming. The base interface
            returns all materials for simplicity.
        """
        ...

    async def get_materials_by_type(
        self, material_type: str
    ) -> list[Material]:
        """Get materials filtered by type.

        Args:
            material_type: Type of material to retrieve.

        Returns:
            List of materials matching the specified type.
        """
        ...

    async def get_material_count(self) -> int:
        """Get total count of public materials.

        Returns:
            Total number of public materials in the system.
        """
        ...

    async def get_material(self, material_id: str) -> Material | None:
        """Get a specific material by ID.

        Args:
            material_id: The ID of the material to retrieve.

        Returns:
            The material if found, None otherwise.
        """
        ...
