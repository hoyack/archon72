"""Port for reconstitution validation operations.

Story: consent-gov-8.3: Reconstitution Validation

This port defines the interface for reconstitution validation result
persistence. Implementation stores validation results for audit.

Constitutional Context:
- FR53: System can validate Reconstitution Artifact before new instance
- Validation results are persisted for audit trail
"""

from typing import Protocol
from uuid import UUID

from src.domain.governance.cessation import ValidationResult


class ReconstitutionPort(Protocol):
    """Port for reconstitution validation result persistence.

    Stores validation results so they can be retrieved later
    for audit or verification purposes.

    Example:
        >>> port: ReconstitutionPort = InMemoryReconstitutionAdapter()
        >>> await port.store_validation_result(result)
        >>> stored = await port.get_validation_result(artifact_id)
    """

    async def store_validation_result(
        self,
        result: ValidationResult,
    ) -> None:
        """Store validation result.

        Args:
            result: The validation result to store.
        """
        ...

    async def get_validation_result(
        self,
        artifact_id: UUID,
    ) -> ValidationResult | None:
        """Get validation result for artifact.

        Args:
            artifact_id: The artifact ID to look up.

        Returns:
            The validation result if found, None otherwise.
        """
        ...
