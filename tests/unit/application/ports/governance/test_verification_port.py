"""Unit tests for verification port interface.

Story: consent-gov-9.3: Independent Verification

Tests:
- VerificationPort protocol methods
- Structural subtyping verification
- Method signatures
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.verification_port import (
    StateReplayerPort,
    VerificationPort,
)
from src.domain.governance.audit.ledger_export import LedgerExport
from src.domain.governance.audit.verification_result import (
    VerificationResult,
    VerificationStatus,
)


class FakeStateReplayer:
    """Fake state replayer for testing."""

    async def replay(self, events: list) -> dict:
        """Replay events and return state."""
        return {"event_count": len(events)}


class FakeVerificationPortImpl:
    """Fake implementation for testing structural subtyping."""

    async def verify_complete(
        self,
        ledger_export: LedgerExport,
        verifier_id: UUID | None = None,
    ) -> VerificationResult:
        """Perform complete verification."""
        return VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.VALID,
            hash_chain_valid=True,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=0,
        )

    async def verify_hash_chain(
        self,
        events: list,
    ) -> tuple[bool, list]:
        """Verify hash chain independently."""
        return True, []

    async def verify_sequence(
        self,
        events: list,
    ) -> tuple[bool, list]:
        """Verify sequence is complete."""
        return True, []

    async def verify_merkle(
        self,
        events: list,
        expected_root: str,
    ) -> tuple[bool, list]:
        """Verify Merkle root."""
        return True, []

    async def verify_state_replay(
        self,
        events: list,
    ) -> tuple[bool, list]:
        """Verify state replay."""
        return True, []

    async def verify_offline(
        self,
        ledger_json: str,
    ) -> VerificationResult:
        """Verify from JSON export."""
        return VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.VALID,
            hash_chain_valid=True,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=0,
        )


class TestVerificationPort:
    """Tests for VerificationPort protocol."""

    def test_structural_subtyping(self) -> None:
        """FakeVerificationPortImpl satisfies VerificationPort protocol."""
        impl = FakeVerificationPortImpl()
        assert isinstance(impl, VerificationPort)

    def test_verify_complete_method_exists(self) -> None:
        """VerificationPort defines verify_complete method."""
        impl = FakeVerificationPortImpl()
        assert hasattr(impl, "verify_complete")
        assert callable(impl.verify_complete)

    def test_verify_hash_chain_method_exists(self) -> None:
        """VerificationPort defines verify_hash_chain method."""
        impl = FakeVerificationPortImpl()
        assert hasattr(impl, "verify_hash_chain")
        assert callable(impl.verify_hash_chain)

    def test_verify_sequence_method_exists(self) -> None:
        """VerificationPort defines verify_sequence method."""
        impl = FakeVerificationPortImpl()
        assert hasattr(impl, "verify_sequence")
        assert callable(impl.verify_sequence)

    def test_verify_merkle_method_exists(self) -> None:
        """VerificationPort defines verify_merkle method."""
        impl = FakeVerificationPortImpl()
        assert hasattr(impl, "verify_merkle")
        assert callable(impl.verify_merkle)

    def test_verify_state_replay_method_exists(self) -> None:
        """VerificationPort defines verify_state_replay method."""
        impl = FakeVerificationPortImpl()
        assert hasattr(impl, "verify_state_replay")
        assert callable(impl.verify_state_replay)

    def test_verify_offline_method_exists(self) -> None:
        """VerificationPort defines verify_offline method."""
        impl = FakeVerificationPortImpl()
        assert hasattr(impl, "verify_offline")
        assert callable(impl.verify_offline)


class TestStateReplayerPort:
    """Tests for StateReplayerPort protocol."""

    def test_structural_subtyping(self) -> None:
        """FakeStateReplayer satisfies StateReplayerPort protocol."""
        impl = FakeStateReplayer()
        assert isinstance(impl, StateReplayerPort)

    def test_replay_method_exists(self) -> None:
        """StateReplayerPort defines replay method."""
        impl = FakeStateReplayer()
        assert hasattr(impl, "replay")
        assert callable(impl.replay)


class TestVerificationPortAsync:
    """Tests for async behavior of VerificationPort."""

    @pytest.mark.asyncio
    async def test_verify_complete_is_async(self) -> None:
        """verify_complete is an async method."""
        impl = FakeVerificationPortImpl()
        result = await impl.verify_complete(None)  # type: ignore
        assert isinstance(result, VerificationResult)

    @pytest.mark.asyncio
    async def test_verify_hash_chain_is_async(self) -> None:
        """verify_hash_chain is an async method."""
        impl = FakeVerificationPortImpl()
        valid, issues = await impl.verify_hash_chain([])
        assert isinstance(valid, bool)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_verify_offline_is_async(self) -> None:
        """verify_offline is an async method."""
        impl = FakeVerificationPortImpl()
        result = await impl.verify_offline("{}")
        assert isinstance(result, VerificationResult)

    @pytest.mark.asyncio
    async def test_state_replayer_replay_is_async(self) -> None:
        """StateReplayerPort.replay is an async method."""
        impl = FakeStateReplayer()
        result = await impl.replay([])
        assert isinstance(result, dict)
