"""Phase 2 Dynamic Testing: H3 - Emergency Key Revocation.

Tests the security fix for H3: 30-Day Key Transition Window Risk.

The fix adds emergency_revoke_key() that immediately revokes a key,
bypassing the normal 30-day transition period for compromised keys.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.models.keeper_key import KeeperKey
from src.infrastructure.stubs.keeper_key_registry_stub import KeeperKeyRegistryStub


@pytest.fixture
def registry() -> KeeperKeyRegistryStub:
    """Create a fresh registry for each test."""
    return KeeperKeyRegistryStub(with_dev_key=False)


@pytest.fixture
def sample_key() -> KeeperKey:
    """Create a sample keeper key for testing."""
    now = datetime.now(timezone.utc)
    return KeeperKey(
        id=uuid4(),
        key_id="KEY-001",
        keeper_id="KEEPER:alice",
        public_key=b"test_public_key_32_bytes_here!00",
        active_from=now - timedelta(days=30),
        active_until=None,  # Currently active
    )


class TestEmergencyRevocationBasics:
    """Basic tests for emergency_revoke_key() function."""

    @pytest.mark.asyncio
    async def test_emergency_revoke_returns_datetime(
        self, registry: KeeperKeyRegistryStub, sample_key: KeeperKey
    ) -> None:
        """Emergency revoke should return the revocation datetime."""
        await registry.register_key(sample_key)

        revoked_at = await registry.emergency_revoke_key(
            key_id=sample_key.key_id,
            reason="Key compromised",
            revoked_by="KEEPER:admin",
        )

        assert isinstance(revoked_at, datetime)
        assert revoked_at.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_emergency_revoke_sets_active_until(
        self, registry: KeeperKeyRegistryStub, sample_key: KeeperKey
    ) -> None:
        """Emergency revoke should set active_until to NOW."""
        await registry.register_key(sample_key)

        # Verify key is active before revocation
        key_before = await registry.get_key_by_id(sample_key.key_id)
        assert key_before is not None
        assert key_before.active_until is None  # No end date

        revoked_at = await registry.emergency_revoke_key(
            key_id=sample_key.key_id,
            reason="Key compromised",
            revoked_by="KEEPER:admin",
        )

        # Verify key is now revoked
        key_after = await registry.get_key_by_id(sample_key.key_id)
        assert key_after is not None
        assert key_after.active_until == revoked_at

    @pytest.mark.asyncio
    async def test_emergency_revoke_key_not_found_raises(
        self, registry: KeeperKeyRegistryStub
    ) -> None:
        """Emergency revoke should raise KeyError for unknown key."""
        with pytest.raises(KeyError) as exc_info:
            await registry.emergency_revoke_key(
                key_id="NON-EXISTENT-KEY",
                reason="Testing",
                revoked_by="KEEPER:admin",
            )

        assert "NON-EXISTENT-KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_emergency_revoke_tracks_revocation_details(
        self, registry: KeeperKeyRegistryStub, sample_key: KeeperKey
    ) -> None:
        """Emergency revoke should track revocation details."""
        await registry.register_key(sample_key)

        await registry.emergency_revoke_key(
            key_id=sample_key.key_id,
            reason="Suspected compromise",
            revoked_by="KEEPER:security_officer",
        )

        # Check revocation tracking
        revocations = registry.get_emergency_revocations()
        assert sample_key.key_id in revocations

        revocation = revocations[sample_key.key_id]
        assert revocation["reason"] == "Suspected compromise"
        assert revocation["revoked_by"] == "KEEPER:security_officer"
        assert revocation["security_finding"] == "H3"


class TestEmergencyRevocationBypassesTransition:
    """Tests verifying H3 fix: emergency revocation bypasses transition."""

    @pytest.mark.asyncio
    async def test_key_in_transition_can_be_emergency_revoked(
        self, registry: KeeperKeyRegistryStub
    ) -> None:
        """H3 FIX: Key in 30-day transition can be immediately revoked."""
        now = datetime.now(timezone.utc)

        # Create old key (in transition)
        old_key = KeeperKey(
            id=uuid4(),
            key_id="OLD-KEY-001",
            keeper_id="KEEPER:alice",
            public_key=b"old_public_key_32_bytes_here!0XX",  # 32 bytes
            active_from=now - timedelta(days=60),
            active_until=now + timedelta(days=25),  # Still 25 days in transition
        )

        # Create new key
        new_key = KeeperKey(
            id=uuid4(),
            key_id="NEW-KEY-001",
            keeper_id="KEEPER:alice",
            public_key=b"new_public_key_32_bytes_here!0XX",  # 32 bytes
            active_from=now - timedelta(days=5),
            active_until=None,
        )

        await registry.register_key(old_key)
        await registry.register_key(new_key)

        # Old key is still valid (in transition)
        assert old_key.is_active_at(now)

        # Emergency revoke the old key
        revoked_at = await registry.emergency_revoke_key(
            key_id=old_key.key_id,
            reason="Old key compromised during transition",
            revoked_by="KEEPER:admin",
        )

        # Verify old key is NOW revoked (not waiting 25 more days)
        old_key_after = await registry.get_key_by_id(old_key.key_id)
        assert old_key_after is not None
        assert old_key_after.active_until == revoked_at
        assert old_key_after.active_until <= now + timedelta(
            seconds=5
        )  # Within seconds

    @pytest.mark.asyncio
    async def test_emergency_revoked_key_no_longer_active(
        self, registry: KeeperKeyRegistryStub, sample_key: KeeperKey
    ) -> None:
        """Emergency revoked key should fail is_active_at() checks."""
        await registry.register_key(sample_key)
        now = datetime.now(timezone.utc)

        # Key is active before revocation
        key_before = await registry.get_key_by_id(sample_key.key_id)
        assert key_before is not None
        assert key_before.is_active_at(now)

        # Emergency revoke
        await registry.emergency_revoke_key(
            key_id=sample_key.key_id,
            reason="Compromised",
            revoked_by="KEEPER:admin",
        )

        # Key is NOT active after revocation (even just microseconds later)
        key_after = await registry.get_key_by_id(sample_key.key_id)
        assert key_after is not None
        # The key is revoked at NOW, so checking NOW+epsilon should fail
        future_time = now + timedelta(seconds=1)
        assert not key_after.is_active_at(future_time)


class TestH3SecurityScenarios:
    """End-to-end security scenarios for H3 fix."""

    @pytest.mark.asyncio
    async def test_compromised_key_revoked_immediately(
        self, registry: KeeperKeyRegistryStub
    ) -> None:
        """SECURITY: Compromised key is revoked immediately, not after 30 days."""
        now = datetime.now(timezone.utc)

        compromised_key = KeeperKey(
            id=uuid4(),
            key_id="COMPROMISED-KEY",
            keeper_id="KEEPER:victim",
            public_key=b"compromised_key_32_bytes_here!XX",  # 32 bytes
            active_from=now - timedelta(days=100),
            active_until=None,  # Was perpetually active
        )

        await registry.register_key(compromised_key)

        # Security team discovers compromise
        revoked_at = await registry.emergency_revoke_key(
            key_id=compromised_key.key_id,
            reason="Key material leaked in security incident",
            revoked_by="KEEPER:incident_response",
        )

        # Verify immediate revocation
        key_after = await registry.get_key_by_id(compromised_key.key_id)
        assert key_after is not None
        assert key_after.active_until == revoked_at

        # Key should NOT be active even 1 second after revocation
        assert not key_after.is_active_at(revoked_at + timedelta(seconds=1))

    @pytest.mark.asyncio
    async def test_attacker_window_eliminated(
        self, registry: KeeperKeyRegistryStub
    ) -> None:
        """SECURITY: Attacker cannot use compromised key after emergency revocation."""
        now = datetime.now(timezone.utc)

        stolen_key = KeeperKey(
            id=uuid4(),
            key_id="STOLEN-KEY",
            keeper_id="KEEPER:target",
            public_key=b"stolen_key_32_bytes_here!00000XX",  # 32 bytes
            active_from=now - timedelta(days=30),
            active_until=None,
        )

        await registry.register_key(stolen_key)

        # Attacker has key, defender discovers and revokes
        await registry.emergency_revoke_key(
            key_id=stolen_key.key_id,
            reason="Key stolen - immediate revocation required",
            revoked_by="KEEPER:security",
        )

        # Attacker tries to use key 1 minute after revocation
        attacker_attempt_time = now + timedelta(minutes=1)
        key_status = await registry.get_key_by_id(stolen_key.key_id)

        assert key_status is not None
        assert not key_status.is_active_at(attacker_attempt_time)

    @pytest.mark.asyncio
    async def test_audit_trail_preserved(
        self, registry: KeeperKeyRegistryStub, sample_key: KeeperKey
    ) -> None:
        """Emergency revocation should preserve full audit trail."""
        await registry.register_key(sample_key)

        revoked_at = await registry.emergency_revoke_key(
            key_id=sample_key.key_id,
            reason="Audit test - full chain required",
            revoked_by="KEEPER:auditor",
        )

        # Verify audit trail
        revocations = registry.get_emergency_revocations()
        assert sample_key.key_id in revocations

        audit = revocations[sample_key.key_id]
        assert audit["revoked_at"] == revoked_at
        assert audit["reason"] == "Audit test - full chain required"
        assert audit["revoked_by"] == "KEEPER:auditor"
        assert audit["security_finding"] == "H3"

        # Key is preserved (FR76: no deletion)
        key_after = await registry.get_key_by_id(sample_key.key_id)
        assert key_after is not None  # Key still exists, just deactivated


class TestEmergencyRevocationEdgeCases:
    """Edge cases for emergency revocation."""

    @pytest.mark.asyncio
    async def test_revoke_already_revoked_key(
        self, registry: KeeperKeyRegistryStub, sample_key: KeeperKey
    ) -> None:
        """Revoking an already-revoked key should update the revocation."""
        await registry.register_key(sample_key)

        # First revocation
        first_revoke = await registry.emergency_revoke_key(
            key_id=sample_key.key_id,
            reason="First revocation",
            revoked_by="KEEPER:admin1",
        )

        # Second revocation (maybe more info discovered)
        second_revoke = await registry.emergency_revoke_key(
            key_id=sample_key.key_id,
            reason="Second revocation with more details",
            revoked_by="KEEPER:admin2",
        )

        # Should succeed (idempotent-ish behavior)
        assert second_revoke >= first_revoke

    @pytest.mark.asyncio
    async def test_revoke_removes_from_transition(
        self, registry: KeeperKeyRegistryStub
    ) -> None:
        """Emergency revoke should remove key from active transitions."""
        now = datetime.now(timezone.utc)

        old_key = KeeperKey(
            id=uuid4(),
            key_id="OLD-TRANSITION-KEY",
            keeper_id="KEEPER:bob",
            public_key=b"old_transition_key_32_bytes_0XX!",  # 32 bytes
            active_from=now - timedelta(days=60),
            active_until=None,
        )

        new_key = KeeperKey(
            id=uuid4(),
            key_id="NEW-TRANSITION-KEY",
            keeper_id="KEEPER:bob",
            public_key=b"new_transition_key_32_bytes_0XX!",  # 32 bytes
            active_from=now,
            active_until=None,
        )

        await registry.register_key(old_key)
        await registry.register_key(new_key)

        # Begin transition
        await registry.begin_transition(
            old_key_id=old_key.key_id,
            new_key_id=new_key.key_id,
            transition_end_at=now + timedelta(days=30),
        )

        # Old key should be in transition
        in_transition = await registry.get_keys_in_transition("KEEPER:bob")
        assert len(in_transition) == 1

        # Emergency revoke old key
        await registry.emergency_revoke_key(
            key_id=old_key.key_id,
            reason="Compromised during transition",
            revoked_by="KEEPER:admin",
        )

        # Old key should no longer be in transition (revoked immediately)
        in_transition_after = await registry.get_keys_in_transition("KEEPER:bob")
        assert len(in_transition_after) == 0
