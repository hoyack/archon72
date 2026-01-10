"""Keeper Availability Stub for testing (FR77-FR79).

In-memory implementation of KeeperAvailabilityProtocol for use in tests.

Constitutional Constraints:
- FR78: Keepers SHALL attest availability weekly; 2 missed trigger replacement
- FR79: If registered Keeper count falls below 3, system SHALL halt
- FR76: Historical attestations must be preserved (no deletion)
"""

from __future__ import annotations

from datetime import datetime

from src.application.ports.keeper_availability import KeeperAvailabilityProtocol
from src.domain.errors.keeper_availability import DuplicateAttestationError
from src.domain.models.keeper_attestation import KeeperAttestation


class KeeperAvailabilityStub(KeeperAvailabilityProtocol):
    """In-memory stub implementation of KeeperAvailabilityProtocol.

    Used for testing purposes. Stores attestations and Keeper state
    in memory.

    Note: Attestations are NEVER deleted to comply with FR76.
    """

    def __init__(self) -> None:
        """Initialize empty state."""
        # keeper_id -> period_start -> KeeperAttestation
        self._attestations: dict[str, dict[str, KeeperAttestation]] = {}

        # keeper_id -> consecutive missed count
        self._missed_counts: dict[str, int] = {}

        # Set of active Keeper IDs
        self._active_keepers: set[str] = set()

        # Set of Keeper IDs pending replacement
        self._pending_replacement: set[str] = set()

        # keeper_id -> replacement reason
        self._replacement_reasons: dict[str, str] = {}

    async def get_attestation(
        self, keeper_id: str, period_start: datetime
    ) -> KeeperAttestation | None:
        """Get attestation for a Keeper at a specific period start.

        Args:
            keeper_id: The Keeper identifier.
            period_start: The start of the attestation period.

        Returns:
            KeeperAttestation if found, None otherwise.
        """
        keeper_attestations = self._attestations.get(keeper_id, {})
        key = period_start.isoformat()
        return keeper_attestations.get(key)

    async def record_attestation(self, attestation: KeeperAttestation) -> None:
        """Record a new Keeper attestation.

        Args:
            attestation: The KeeperAttestation to record.

        Raises:
            DuplicateAttestationError: If attestation already exists for period.
        """
        keeper_id = attestation.keeper_id
        period_key = attestation.period_start.isoformat()

        # Check for duplicate
        if keeper_id in self._attestations:
            if period_key in self._attestations[keeper_id]:
                raise DuplicateAttestationError(
                    f"FR78: Keeper {keeper_id} already attested for period "
                    f"{attestation.period_start.date()} to {attestation.period_end.date()}"
                )

        # Store attestation
        if keeper_id not in self._attestations:
            self._attestations[keeper_id] = {}
        self._attestations[keeper_id][period_key] = attestation

    async def get_missed_attestations_count(self, keeper_id: str) -> int:
        """Get count of consecutive missed attestations for a Keeper.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Number of consecutive missed attestations (0 if none).
        """
        return self._missed_counts.get(keeper_id, 0)

    async def increment_missed_attestations(self, keeper_id: str) -> int:
        """Increment the missed attestations count for a Keeper.

        Returns the new count after incrementing.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            New count of consecutive missed attestations.
        """
        current = self._missed_counts.get(keeper_id, 0)
        new_count = current + 1
        self._missed_counts[keeper_id] = new_count
        return new_count

    async def reset_missed_attestations(self, keeper_id: str) -> None:
        """Reset missed attestations count for a Keeper to 0.

        Called when a Keeper successfully submits an attestation.

        Args:
            keeper_id: The Keeper identifier.
        """
        self._missed_counts[keeper_id] = 0

    async def get_all_active_keepers(self) -> list[str]:
        """Get list of all active Keeper IDs.

        Returns:
            List of active Keeper IDs.
        """
        return list(self._active_keepers)

    async def get_keepers_pending_replacement(self) -> list[str]:
        """Get list of Keepers marked for replacement.

        Returns:
            List of Keeper IDs pending replacement.
        """
        return list(self._pending_replacement)

    async def mark_keeper_for_replacement(
        self, keeper_id: str, reason: str
    ) -> None:
        """Mark a Keeper for replacement (FR78).

        Args:
            keeper_id: The Keeper identifier.
            reason: Why the Keeper is being replaced.
        """
        self._pending_replacement.add(keeper_id)
        self._replacement_reasons[keeper_id] = reason

    async def get_current_keeper_count(self) -> int:
        """Get the current count of active Keepers.

        Returns:
            Number of active Keepers.
        """
        # Active Keepers minus those pending replacement
        return len(self._active_keepers - self._pending_replacement)

    async def add_keeper(self, keeper_id: str) -> None:
        """Add a new active Keeper.

        Args:
            keeper_id: The Keeper identifier to add.
        """
        self._active_keepers.add(keeper_id)
        # Initialize missed count to 0
        self._missed_counts[keeper_id] = 0

    async def remove_keeper(self, keeper_id: str) -> None:
        """Remove a Keeper from the active list.

        Note: Historical attestations are preserved (FR76).

        Args:
            keeper_id: The Keeper identifier to remove.
        """
        self._active_keepers.discard(keeper_id)
        self._pending_replacement.discard(keeper_id)
        self._replacement_reasons.pop(keeper_id, None)

    async def get_last_attestation(
        self, keeper_id: str
    ) -> KeeperAttestation | None:
        """Get the most recent attestation for a Keeper.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Most recent KeeperAttestation if any, None otherwise.
        """
        keeper_attestations = self._attestations.get(keeper_id, {})
        if not keeper_attestations:
            return None

        # Find the most recent by period_start
        latest = max(keeper_attestations.values(), key=lambda a: a.period_start)
        return latest

    # Additional helper methods for testing

    def get_all_attestations(self, keeper_id: str) -> list[KeeperAttestation]:
        """Get all attestations for a Keeper (test helper).

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            List of all attestations for the Keeper.
        """
        keeper_attestations = self._attestations.get(keeper_id, {})
        return list(keeper_attestations.values())

    def get_replacement_reason(self, keeper_id: str) -> str | None:
        """Get replacement reason for a Keeper (test helper).

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            Replacement reason if Keeper is marked for replacement, None otherwise.
        """
        return self._replacement_reasons.get(keeper_id)

    def reset(self) -> None:
        """Reset all state (test helper)."""
        self._attestations.clear()
        self._missed_counts.clear()
        self._active_keepers.clear()
        self._pending_replacement.clear()
        self._replacement_reasons.clear()
