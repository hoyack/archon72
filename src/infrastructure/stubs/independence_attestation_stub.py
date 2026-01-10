"""Independence Attestation Stub for testing (FR98, FR133).

In-memory implementation of IndependenceAttestationProtocol for use in tests.

Constitutional Constraints:
- FR133: Keepers SHALL annually attest independence; attestation recorded
- FR98: Anomalous signature patterns SHALL be flagged for manual review
- FR76: Historical attestations must be preserved (no deletion)
"""

from __future__ import annotations

from src.application.ports.independence_attestation import (
    IndependenceAttestationProtocol,
)
from src.domain.errors.independence_attestation import (
    DuplicateIndependenceAttestationError,
)
from src.domain.models.independence_attestation import IndependenceAttestation


class IndependenceAttestationStub(IndependenceAttestationProtocol):
    """In-memory stub implementation of IndependenceAttestationProtocol.

    Used for testing purposes. Stores independence attestations and
    Keeper suspension state in memory.

    Note: Attestations are NEVER deleted to comply with FR76.
    """

    def __init__(self) -> None:
        """Initialize empty state."""
        # keeper_id -> year -> IndependenceAttestation
        self._attestations: dict[str, dict[int, IndependenceAttestation]] = {}

        # Set of active Keeper IDs
        self._active_keepers: set[str] = set()

        # keeper_id -> suspension reason (if suspended)
        self._suspended_keepers: dict[str, str] = {}

    async def get_attestation(
        self, keeper_id: str, year: int
    ) -> IndependenceAttestation | None:
        """Get attestation for a Keeper for a specific year.

        Args:
            keeper_id: The Keeper identifier.
            year: The attestation year.

        Returns:
            IndependenceAttestation if found, None otherwise.
        """
        keeper_attestations = self._attestations.get(keeper_id, {})
        return keeper_attestations.get(year)

    async def record_attestation(self, attestation: IndependenceAttestation) -> None:
        """Record a new independence attestation.

        Args:
            attestation: The IndependenceAttestation to record.

        Raises:
            DuplicateIndependenceAttestationError: If attestation already exists for year.
        """
        keeper_id = attestation.keeper_id
        year = attestation.attestation_year

        # Check for duplicate
        if keeper_id in self._attestations:
            if year in self._attestations[keeper_id]:
                raise DuplicateIndependenceAttestationError(keeper_id, year)

        # Store attestation
        if keeper_id not in self._attestations:
            self._attestations[keeper_id] = {}
        self._attestations[keeper_id][year] = attestation

    async def get_attestation_history(
        self, keeper_id: str
    ) -> list[IndependenceAttestation]:
        """Get all attestations for a Keeper, ordered by year ascending.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            List of IndependenceAttestation ordered by year.
        """
        keeper_attestations = self._attestations.get(keeper_id, {})
        if not keeper_attestations:
            return []

        # Sort by year ascending
        return sorted(keeper_attestations.values(), key=lambda a: a.attestation_year)

    async def get_latest_attestation(
        self, keeper_id: str
    ) -> IndependenceAttestation | None:
        """Get the most recent attestation for a Keeper.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Most recent IndependenceAttestation if any, None otherwise.
        """
        keeper_attestations = self._attestations.get(keeper_id, {})
        if not keeper_attestations:
            return None

        # Find the most recent by year
        return max(keeper_attestations.values(), key=lambda a: a.attestation_year)

    async def get_keepers_overdue_attestation(self) -> list[str]:
        """Get Keepers who are overdue for attestation.

        Note: The actual deadline calculation is done in the service.
        This stub returns all active keepers without a current year attestation.

        Returns:
            List of Keeper IDs who need to attest.
        """
        # Import here to avoid circular dependency
        from src.domain.models.independence_attestation import (
            get_current_attestation_year,
        )

        current_year = get_current_attestation_year()
        overdue: list[str] = []

        for keeper_id in self._active_keepers:
            keeper_attestations = self._attestations.get(keeper_id, {})
            if current_year not in keeper_attestations:
                overdue.append(keeper_id)

        return overdue

    async def mark_keeper_suspended(self, keeper_id: str, reason: str) -> None:
        """Mark a Keeper as suspended.

        Args:
            keeper_id: The Keeper identifier.
            reason: Why the Keeper is suspended.
        """
        self._suspended_keepers[keeper_id] = reason

    async def is_keeper_suspended(self, keeper_id: str) -> bool:
        """Check if a Keeper is suspended.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            True if Keeper is suspended, False otherwise.
        """
        return keeper_id in self._suspended_keepers

    async def clear_suspension(self, keeper_id: str) -> None:
        """Clear a Keeper's suspension.

        Args:
            keeper_id: The Keeper identifier.
        """
        self._suspended_keepers.pop(keeper_id, None)

    async def get_all_active_keepers(self) -> list[str]:
        """Get list of all active Keeper IDs.

        Returns:
            List of active Keeper IDs.
        """
        return list(self._active_keepers)

    # Additional helper methods for testing

    def add_keeper(self, keeper_id: str) -> None:
        """Add a new active Keeper (test helper).

        Args:
            keeper_id: The Keeper identifier to add.
        """
        self._active_keepers.add(keeper_id)

    def remove_keeper(self, keeper_id: str) -> None:
        """Remove a Keeper from the active list (test helper).

        Note: Historical attestations are preserved (FR76).

        Args:
            keeper_id: The Keeper identifier to remove.
        """
        self._active_keepers.discard(keeper_id)

    def get_suspension_reason(self, keeper_id: str) -> str | None:
        """Get suspension reason for a Keeper (test helper).

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Suspension reason if Keeper is suspended, None otherwise.
        """
        return self._suspended_keepers.get(keeper_id)

    def get_suspended_keepers(self) -> list[str]:
        """Get list of all suspended Keepers (test helper).

        Returns:
            List of suspended Keeper IDs.
        """
        return list(self._suspended_keepers.keys())

    def reset(self) -> None:
        """Reset all state (test helper)."""
        self._attestations.clear()
        self._active_keepers.clear()
        self._suspended_keepers.clear()
