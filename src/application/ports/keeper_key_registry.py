"""Keeper Key Registry protocol definition (FR68, FR76).

Defines the abstract interface for Keeper key registry operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR68: Overrides require cryptographic signature from registered Keeper key
- FR76: Historical keys must be preserved (no deletion)

H3 Security Enhancement:
- Emergency revocation bypasses 30-day transition period
- Used when a key is known to be compromised
- Immediate revocation with audit trail
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.models.keeper_key import KeeperKey


class KeeperKeyRegistryProtocol(ABC):
    """Abstract protocol for Keeper key registry operations.

    All Keeper key registry implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific storage implementations.

    Constitutional Requirements:
    - FR68: Must track Keeper keys for signature verification
    - FR76: Historical keys must never be deleted
    """

    @abstractmethod
    async def get_key_by_id(self, key_id: str) -> KeeperKey | None:
        """Get a key by its HSM key_id.

        Args:
            key_id: The HSM key identifier.

        Returns:
            KeeperKey if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_active_key_for_keeper(
        self,
        keeper_id: str,
        at_time: datetime | None = None,
    ) -> KeeperKey | None:
        """Get the active key for a Keeper at a specific time.

        Args:
            keeper_id: The Keeper identifier (e.g., "KEEPER:alice").
            at_time: The time to check (default: current time).

        Returns:
            KeeperKey if found and active at the specified time, None otherwise.
        """
        ...

    @abstractmethod
    async def register_key(self, key: KeeperKey) -> None:
        """Register a new Keeper key.

        Args:
            key: The KeeperKey to register.

        Raises:
            KeyAlreadyExistsError: If key_id already exists.
        """
        ...

    @abstractmethod
    async def deactivate_key(
        self,
        key_id: str,
        deactivated_at: datetime,
    ) -> None:
        """Mark a key as deactivated (set active_until).

        Note: Keys are NEVER deleted (FR76). This only sets the
        active_until timestamp to prevent future use.

        Args:
            key_id: The key to deactivate.
            deactivated_at: When the key becomes inactive.

        Raises:
            KeyNotFoundError: If key_id doesn't exist.
        """
        ...

    @abstractmethod
    async def key_exists(self, key_id: str) -> bool:
        """Check if a key exists in the registry.

        Args:
            key_id: The key identifier to check.

        Returns:
            True if key exists, False otherwise.
        """
        ...

    @abstractmethod
    async def get_all_keys_for_keeper(self, keeper_id: str) -> list[KeeperKey]:
        """Get all keys for a Keeper, including historical keys (FR76).

        This method returns ALL keys ever registered for a Keeper,
        including expired and deactivated keys. This is essential for
        verifying old overrides signed with previous keys.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            List of all KeeperKeys for the Keeper (may be empty).
        """
        ...

    # ADR-4: Key Transition Support (Story 5.7)

    @abstractmethod
    async def begin_transition(
        self,
        old_key_id: str,
        new_key_id: str,
        transition_end_at: datetime,
    ) -> None:
        """Begin a key transition period (ADR-4).

        During the transition period, both old and new keys are valid.
        This enables 30-day overlap for key rotation.

        Args:
            old_key_id: The key being rotated out.
            new_key_id: The new key being rotated in.
            transition_end_at: When the transition period ends.

        Raises:
            KeyError: If either key doesn't exist.
        """
        ...

    @abstractmethod
    async def complete_transition(self, old_key_id: str) -> None:
        """Complete a key transition by revoking the old key (ADR-4).

        Called after the transition period ends to finalize
        the old key's deactivation.

        Args:
            old_key_id: The key to finalize revocation for.

        Raises:
            KeyError: If key doesn't exist.
        """
        ...

    @abstractmethod
    async def get_keys_in_transition(self, keeper_id: str) -> list[KeeperKey]:
        """Get keys currently in transition period (ADR-4).

        Returns keys that have active_until set but are still
        within their transition period.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            List of keys in transition (may be empty).
        """
        ...

    # H3 Security Fix: Emergency Key Revocation

    @abstractmethod
    async def emergency_revoke_key(
        self,
        key_id: str,
        reason: str,
        revoked_by: str,
    ) -> datetime:
        """Emergency revoke a key immediately, bypassing transition period (H3 fix).

        This method provides IMMEDIATE key revocation for compromised keys,
        bypassing the normal 30-day transition window. Use only when a key
        is known or suspected to be compromised.

        H3 Security Finding:
        - Normal key rotation has 30-day transition where both keys are valid
        - If a key is compromised, attacker has 30 days to use it
        - This method allows immediate revocation for compromised keys

        Constitutional Note (FR76):
        Keys are NEVER deleted. This sets active_until to NOW and marks
        the key as emergency-revoked in metadata.

        Args:
            key_id: The key to immediately revoke.
            reason: The reason for emergency revocation (e.g., "Key compromised").
            revoked_by: Who initiated the revocation (e.g., "KEEPER:admin").

        Returns:
            The datetime when the key was revoked (for audit trail).

        Raises:
            KeyError: If key_id doesn't exist.
        """
        ...
