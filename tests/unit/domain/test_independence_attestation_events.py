"""Unit tests for Independence Attestation event payloads (FR98, FR133).

Tests the event payloads for annual Keeper independence attestation tracking:
- IndependenceAttestationPayload
- KeeperIndependenceSuspendedPayload
- DeclarationChangeDetectedPayload

Constitutional Constraints Tested:
- FR133: Annual independence attestation requirement
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest


class TestIndependenceAttestationPayload:
    """Tests for IndependenceAttestationPayload."""

    def test_creation_with_all_fields(self) -> None:
        """Test payload creates with all required fields."""
        from src.domain.events.independence_attestation import (
            IndependenceAttestationPayload,
        )

        now = datetime.now(timezone.utc)
        payload = IndependenceAttestationPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            conflict_count=2,
            organization_count=3,
            attested_at=now,
        )

        assert payload.keeper_id == "KEEPER:alice"
        assert payload.attestation_year == 2026
        assert payload.conflict_count == 2
        assert payload.organization_count == 3
        assert payload.attested_at == now

    def test_frozen_immutable(self) -> None:
        """Test payload is immutable."""
        from src.domain.events.independence_attestation import (
            IndependenceAttestationPayload,
        )

        payload = IndependenceAttestationPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            conflict_count=0,
            organization_count=0,
            attested_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.keeper_id = "changed"  # type: ignore[misc]

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes for witnessing (CT-12)."""
        from src.domain.events.independence_attestation import (
            IndependenceAttestationPayload,
        )

        payload = IndependenceAttestationPayload(
            keeper_id="KEEPER:bob",
            attestation_year=2026,
            conflict_count=1,
            organization_count=2,
            attested_at=datetime.now(timezone.utc),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content is deterministic for same input."""
        from src.domain.events.independence_attestation import (
            IndependenceAttestationPayload,
        )

        now = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        payload1 = IndependenceAttestationPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            conflict_count=2,
            organization_count=3,
            attested_at=now,
        )
        payload2 = IndependenceAttestationPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            conflict_count=2,
            organization_count=3,
            attested_at=now,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_valid_json(self) -> None:
        """Test signable_content produces valid JSON."""
        from src.domain.events.independence_attestation import (
            IndependenceAttestationPayload,
        )

        payload = IndependenceAttestationPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            conflict_count=1,
            organization_count=2,
            attested_at=datetime.now(timezone.utc),
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_type"] == "IndependenceAttestation"
        assert parsed["keeper_id"] == "KEEPER:alice"
        assert parsed["attestation_year"] == 2026


class TestKeeperIndependenceSuspendedPayload:
    """Tests for KeeperIndependenceSuspendedPayload."""

    def test_creation_with_all_fields(self) -> None:
        """Test payload creates with all required fields."""
        from src.domain.events.independence_attestation import (
            KeeperIndependenceSuspendedPayload,
        )

        deadline = datetime(2026, 2, 14, tzinfo=timezone.utc)
        suspended = datetime(2026, 2, 15, tzinfo=timezone.utc)
        payload = KeeperIndependenceSuspendedPayload(
            keeper_id="KEEPER:alice",
            deadline_missed=deadline,
            suspended_at=suspended,
            capabilities_suspended=["override"],
        )

        assert payload.keeper_id == "KEEPER:alice"
        assert payload.deadline_missed == deadline
        assert payload.suspended_at == suspended
        assert payload.capabilities_suspended == ["override"]

    def test_frozen_immutable(self) -> None:
        """Test payload is immutable."""
        from src.domain.events.independence_attestation import (
            KeeperIndependenceSuspendedPayload,
        )

        payload = KeeperIndependenceSuspendedPayload(
            keeper_id="KEEPER:alice",
            deadline_missed=datetime.now(timezone.utc),
            suspended_at=datetime.now(timezone.utc),
            capabilities_suspended=["override"],
        )

        with pytest.raises(AttributeError):
            payload.keeper_id = "changed"  # type: ignore[misc]

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes for witnessing (CT-12)."""
        from src.domain.events.independence_attestation import (
            KeeperIndependenceSuspendedPayload,
        )

        payload = KeeperIndependenceSuspendedPayload(
            keeper_id="KEEPER:bob",
            deadline_missed=datetime.now(timezone.utc),
            suspended_at=datetime.now(timezone.utc),
            capabilities_suspended=["override"],
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content is deterministic for same input."""
        from src.domain.events.independence_attestation import (
            KeeperIndependenceSuspendedPayload,
        )

        deadline = datetime(2026, 2, 14, tzinfo=timezone.utc)
        suspended = datetime(2026, 2, 15, tzinfo=timezone.utc)

        payload1 = KeeperIndependenceSuspendedPayload(
            keeper_id="KEEPER:alice",
            deadline_missed=deadline,
            suspended_at=suspended,
            capabilities_suspended=["override"],
        )
        payload2 = KeeperIndependenceSuspendedPayload(
            keeper_id="KEEPER:alice",
            deadline_missed=deadline,
            suspended_at=suspended,
            capabilities_suspended=["override"],
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_valid_json(self) -> None:
        """Test signable_content produces valid JSON."""
        from src.domain.events.independence_attestation import (
            KeeperIndependenceSuspendedPayload,
        )

        payload = KeeperIndependenceSuspendedPayload(
            keeper_id="KEEPER:alice",
            deadline_missed=datetime.now(timezone.utc),
            suspended_at=datetime.now(timezone.utc),
            capabilities_suspended=["override"],
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_type"] == "KeeperIndependenceSuspended"
        assert parsed["keeper_id"] == "KEEPER:alice"


class TestDeclarationChangeDetectedPayload:
    """Tests for DeclarationChangeDetectedPayload."""

    def test_creation_with_all_fields(self) -> None:
        """Test payload creates with all required fields."""
        from src.domain.events.independence_attestation import (
            DeclarationChangeDetectedPayload,
        )

        now = datetime.now(timezone.utc)
        payload = DeclarationChangeDetectedPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            previous_conflicts=1,
            current_conflicts=3,
            change_summary="Added 2 new conflicts: FINANCIAL, ORGANIZATIONAL",
            detected_at=now,
        )

        assert payload.keeper_id == "KEEPER:alice"
        assert payload.attestation_year == 2026
        assert payload.previous_conflicts == 1
        assert payload.current_conflicts == 3
        assert "Added 2 new conflicts" in payload.change_summary
        assert payload.detected_at == now

    def test_frozen_immutable(self) -> None:
        """Test payload is immutable."""
        from src.domain.events.independence_attestation import (
            DeclarationChangeDetectedPayload,
        )

        payload = DeclarationChangeDetectedPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            previous_conflicts=0,
            current_conflicts=1,
            change_summary="Added new conflict",
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.keeper_id = "changed"  # type: ignore[misc]

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes for witnessing (CT-12)."""
        from src.domain.events.independence_attestation import (
            DeclarationChangeDetectedPayload,
        )

        payload = DeclarationChangeDetectedPayload(
            keeper_id="KEEPER:bob",
            attestation_year=2026,
            previous_conflicts=0,
            current_conflicts=2,
            change_summary="New conflicts declared",
            detected_at=datetime.now(timezone.utc),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content is deterministic for same input."""
        from src.domain.events.independence_attestation import (
            DeclarationChangeDetectedPayload,
        )

        now = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        payload1 = DeclarationChangeDetectedPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            previous_conflicts=1,
            current_conflicts=2,
            change_summary="Added conflict",
            detected_at=now,
        )
        payload2 = DeclarationChangeDetectedPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            previous_conflicts=1,
            current_conflicts=2,
            change_summary="Added conflict",
            detected_at=now,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_valid_json(self) -> None:
        """Test signable_content produces valid JSON."""
        from src.domain.events.independence_attestation import (
            DeclarationChangeDetectedPayload,
        )

        payload = DeclarationChangeDetectedPayload(
            keeper_id="KEEPER:alice",
            attestation_year=2026,
            previous_conflicts=1,
            current_conflicts=3,
            change_summary="Declaration changes",
            detected_at=datetime.now(timezone.utc),
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_type"] == "DeclarationChangeDetected"
        assert parsed["keeper_id"] == "KEEPER:alice"
        assert parsed["attestation_year"] == 2026


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_independence_attestation_event_type(self) -> None:
        """Test INDEPENDENCE_ATTESTATION_EVENT_TYPE constant."""
        from src.domain.events.independence_attestation import (
            INDEPENDENCE_ATTESTATION_EVENT_TYPE,
        )

        assert INDEPENDENCE_ATTESTATION_EVENT_TYPE == "keeper.independence_attestation"

    def test_keeper_independence_suspended_event_type(self) -> None:
        """Test KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE constant."""
        from src.domain.events.independence_attestation import (
            KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE,
        )

        assert KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE == "keeper.independence_suspended"

    def test_declaration_change_detected_event_type(self) -> None:
        """Test DECLARATION_CHANGE_DETECTED_EVENT_TYPE constant."""
        from src.domain.events.independence_attestation import (
            DECLARATION_CHANGE_DETECTED_EVENT_TYPE,
        )

        assert DECLARATION_CHANGE_DETECTED_EVENT_TYPE == "keeper.declaration_change_detected"
