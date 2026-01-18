"""Keeper Key Registry Stub for testing (FR68, FR76).

In-memory implementation of KeeperKeyRegistryProtocol for use in tests.

Constitutional Constraints:
- FR68: Overrides require cryptographic signature from registered Keeper key
- FR76: Historical keys must be preserved (no deletion)

H3 Security Enhancement:
- Emergency revocation bypasses 30-day transition period
- Used when a key is known to be compromised
- Immediate revocation with audit trail
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from structlog import get_logger

from src.application.ports.keeper_key_registry import KeeperKeyRegistryProtocol
from src.domain.models.keeper_key import KeeperKey

logger = get_logger()


class KeeperKeyRegistryStub(KeeperKeyRegistryProtocol):
    """In-memory stub implementation of KeeperKeyRegistryProtocol.

    Used for testing purposes. Stores keys in memory and provides
    all protocol methods.

    Note: Keys are NEVER deleted to comply with FR76.
    """

    def __init__(self, *, with_dev_key: bool = True) -> None:
        """Initialize registry.

        Args:
            with_dev_key: If True, include a default dev mode key.
                         This allows startup verification to pass in
                         development environments. Default: True.
        """
        self._keys: dict[str, KeeperKey] = {}  # key_id -> KeeperKey
        self._transitions: dict[str, str] = {}  # old_key_id -> new_key_id
        self._emergency_revocations: dict[
            str, dict
        ] = {}  # H3: Track emergency revocations

        if with_dev_key:
            self._add_dev_mode_key()

    def _add_dev_mode_key(self) -> None:
        """Add a default dev mode key for startup verification."""
        from uuid import uuid4

        now = datetime.now(timezone.utc)
        # Ed25519 public keys are 32 bytes - use placeholder bytes for dev mode
        dev_public_key = b"[DEV MODE - NOT REAL KEY!]"  # Exactly 26 bytes
        dev_public_key = dev_public_key + b"\x00" * (
            32 - len(dev_public_key)
        )  # Pad to 32 bytes

        dev_key = KeeperKey(
            id=uuid4(),
            key_id="[DEV-KEY-001]",
            keeper_id="KEEPER:primary",  # Use expected ID for verification
            public_key=dev_public_key,
            active_from=now - timedelta(days=30),
            active_until=None,  # Perpetually active
        )
        self._keys[dev_key.key_id] = dev_key
        logger.warning(
            "keeper_key_registry_stub_dev_key_added",
            key_id=dev_key.key_id,
            keeper_id=dev_key.keeper_id,
            watermark="[DEV MODE - STUB KEY NOT FOR PRODUCTION]",
        )

    async def get_key_by_id(self, key_id: str) -> KeeperKey | None:
        """Get a key by its HSM key_id.

        Args:
            key_id: The HSM key identifier.

        Returns:
            KeeperKey if found, None otherwise.
        """
        return self._keys.get(key_id)

    async def get_active_key_for_keeper(
        self,
        keeper_id: str,
        at_time: datetime | None = None,
    ) -> KeeperKey | None:
        """Get the active key for a Keeper at a specific time.

        Args:
            keeper_id: The Keeper identifier.
            at_time: The time to check (default: current time).

        Returns:
            KeeperKey if found and active, None otherwise.
        """
        check_time = at_time or datetime.now(timezone.utc)

        for key in self._keys.values():
            if key.keeper_id == keeper_id and key.is_active_at(check_time):
                return key

        return None

    async def register_key(self, key: KeeperKey) -> None:
        """Register a new Keeper key.

        Args:
            key: The KeeperKey to register.
        """
        self._keys[key.key_id] = key

    async def deactivate_key(
        self,
        key_id: str,
        deactivated_at: datetime,
    ) -> None:
        """Mark a key as deactivated (set active_until).

        Note: Keys are NEVER deleted (FR76). This only sets the
        active_until timestamp.

        Args:
            key_id: The key to deactivate.
            deactivated_at: When the key becomes inactive.

        Raises:
            KeyError: If key_id doesn't exist.
        """
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")

        existing_key = self._keys[key_id]

        # Create new key with active_until set (frozen dataclass)
        deactivated_key = replace(existing_key, active_until=deactivated_at)
        self._keys[key_id] = deactivated_key

    async def key_exists(self, key_id: str) -> bool:
        """Check if a key exists in the registry.

        Args:
            key_id: The key identifier to check.

        Returns:
            True if key exists, False otherwise.
        """
        return key_id in self._keys

    async def get_all_keys_for_keeper(self, keeper_id: str) -> list[KeeperKey]:
        """Get all keys for a Keeper, including historical keys (FR76).

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            List of all KeeperKeys for the Keeper.
        """
        return [key for key in self._keys.values() if key.keeper_id == keeper_id]

    # Test helper methods

    def add_keeper_key(self, key: KeeperKey) -> None:
        """Synchronous helper to add a key for test setup.

        Args:
            key: The KeeperKey to add.
        """
        self._keys[key.key_id] = key

    def clear(self) -> None:
        """Clear all keys from the registry for test cleanup."""
        self._keys.clear()
        self._transitions.clear()
        self._emergency_revocations.clear()

    def get_key_count(self) -> int:
        """Get the number of keys in the registry.

        Returns:
            Number of keys stored.
        """
        return len(self._keys)

    # ADR-4: Key Transition Support (Story 5.7)

    async def begin_transition(
        self,
        old_key_id: str,
        new_key_id: str,
        transition_end_at: datetime,
    ) -> None:
        """Begin a key transition period (ADR-4).

        During the transition period, both old and new keys are valid.

        Args:
            old_key_id: The key being rotated out.
            new_key_id: The new key being rotated in.
            transition_end_at: When the transition period ends.

        Raises:
            KeyError: If either key doesn't exist.
        """
        if old_key_id not in self._keys:
            raise KeyError(f"Old key not found: {old_key_id}")
        if new_key_id not in self._keys:
            raise KeyError(f"New key not found: {new_key_id}")

        # Set transition end on old key (ADR-4: both valid during overlap)
        old_key = self._keys[old_key_id]
        deactivated_key = replace(old_key, active_until=transition_end_at)
        self._keys[old_key_id] = deactivated_key

        # Track transition (new key already active from registration)
        self._transitions[old_key_id] = new_key_id

    async def complete_transition(self, old_key_id: str) -> None:
        """Complete a key transition by revoking the old key (ADR-4).

        Called after the transition period ends.

        Args:
            old_key_id: The key to finalize revocation for.

        Raises:
            KeyError: If key doesn't exist.
        """
        if old_key_id not in self._keys:
            raise KeyError(f"Key not found: {old_key_id}")

        # Remove from active transitions
        if old_key_id in self._transitions:
            del self._transitions[old_key_id]

        # Key already has active_until set from begin_transition
        # No further action needed - key will fail is_active_at() checks

    async def get_keys_in_transition(self, keeper_id: str) -> list[KeeperKey]:
        """Get keys currently in transition period (ADR-4).

        Returns keys that have active_until set but are still
        within their transition period.

        Args:
            keeper_id: The Keeper identifier.

        Returns:
            List of keys in transition.
        """
        now = datetime.now(timezone.utc)
        result: list[KeeperKey] = []

        for key in self._keys.values():
            if key.keeper_id != keeper_id:
                continue
            # Key is in transition if it has active_until set
            # but that time hasn't passed yet
            if key.active_until is not None and key.active_until > now:
                result.append(key)

        return result

    # H3 Security Fix: Emergency Key Revocation

    async def emergency_revoke_key(
        self,
        key_id: str,
        reason: str,
        revoked_by: str,
    ) -> datetime:
        """Emergency revoke a key immediately, bypassing transition period (H3 fix).

        This method provides IMMEDIATE key revocation for compromised keys,
        bypassing the normal 30-day transition window.

        Args:
            key_id: The key to immediately revoke.
            reason: The reason for emergency revocation.
            revoked_by: Who initiated the revocation.

        Returns:
            The datetime when the key was revoked.

        Raises:
            KeyError: If key_id doesn't exist.
        """
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")

        existing_key = self._keys[key_id]
        now = datetime.now(timezone.utc)

        # Immediately revoke by setting active_until to now
        revoked_key = replace(existing_key, active_until=now)
        self._keys[key_id] = revoked_key

        # Track emergency revocation (in production, this would be an event)
        self._emergency_revocations[key_id] = {
            "revoked_at": now,
            "reason": reason,
            "revoked_by": revoked_by,
            "security_finding": "H3",
        }

        logger.critical(
            "emergency_key_revocation",
            key_id=key_id,
            keeper_id=existing_key.keeper_id,
            reason=reason,
            revoked_by=revoked_by,
            revoked_at=now.isoformat(),
            message="H3: Key emergency revoked - bypassing transition period",
        )

        # Remove from any active transition
        if key_id in self._transitions:
            del self._transitions[key_id]

        return now

    def get_emergency_revocations(self) -> dict[str, dict]:
        """Get all emergency revocations (test helper).

        Returns:
            Dictionary mapping key_id to revocation details.
        """
        return dict(self._emergency_revocations)
