"""Port interface for Archon profile repository.

This module defines the abstract interface for accessing Archon profiles,
following hexagonal architecture principles. Implementations may load
profiles from CSV, database, or other sources.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.models.archon_profile import ArchonProfile


class ArchonProfileRepository(ABC):
    """Abstract repository interface for Archon profiles.

    This port defines operations for retrieving Archon profiles
    without specifying how they are stored or loaded. Adapters
    implement this interface for specific storage backends.

    The repository is read-only by design - Archon profiles are
    configuration data, not runtime state.
    """

    @abstractmethod
    def get_by_id(self, archon_id: UUID) -> ArchonProfile | None:
        """Retrieve an Archon profile by its unique identifier.

        Args:
            archon_id: The UUID of the archon

        Returns:
            The ArchonProfile if found, None otherwise
        """
        ...

    @abstractmethod
    def get_by_name(self, name: str) -> ArchonProfile | None:
        """Retrieve an Archon profile by name.

        Args:
            name: The archon's name (e.g., "Paimon", "Belial")

        Returns:
            The ArchonProfile if found, None otherwise
        """
        ...

    @abstractmethod
    def get_all(self) -> list[ArchonProfile]:
        """Retrieve all 72 Archon profiles.

        Returns:
            List of all ArchonProfile instances, ordered by rank_level
            (highest first) then by name alphabetically
        """
        ...

    @abstractmethod
    def get_by_rank(self, aegis_rank: str) -> list[ArchonProfile]:
        """Retrieve all Archons of a specific rank.

        Args:
            aegis_rank: The rank to filter by (e.g., "executive_director")

        Returns:
            List of ArchonProfile instances with the specified rank
        """
        ...

    @abstractmethod
    def get_by_tool(self, tool_name: str) -> list[ArchonProfile]:
        """Retrieve all Archons that have a specific tool.

        Args:
            tool_name: The tool identifier (e.g., "insight_tool")

        Returns:
            List of ArchonProfile instances with the specified tool
        """
        ...

    @abstractmethod
    def get_by_provider(self, provider: str) -> list[ArchonProfile]:
        """Retrieve all Archons bound to a specific LLM provider.

        Args:
            provider: The LLM provider (e.g., "anthropic", "openai")

        Returns:
            List of ArchonProfile instances using the specified provider
        """
        ...

    @abstractmethod
    def get_executives(self) -> list[ArchonProfile]:
        """Retrieve all executive director (King) Archons.

        Returns:
            List of ArchonProfile instances with executive_director rank
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the total number of Archon profiles.

        Returns:
            Total count (should be 72 for a complete dataset)
        """
        ...

    @abstractmethod
    def exists(self, archon_id: UUID) -> bool:
        """Check if an Archon with the given ID exists.

        Args:
            archon_id: The UUID to check

        Returns:
            True if the archon exists, False otherwise
        """
        ...


class ArchonProfileRepositoryError(Exception):
    """Base exception for Archon profile repository errors."""

    pass


class ArchonNotFoundError(ArchonProfileRepositoryError):
    """Raised when a requested Archon profile is not found."""

    def __init__(self, identifier: str | UUID) -> None:
        self.identifier = identifier
        super().__init__(f"Archon not found: {identifier}")


class ArchonProfileLoadError(ArchonProfileRepositoryError):
    """Raised when there's an error loading Archon profiles."""

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"Failed to load Archon profiles from {source}: {reason}")
