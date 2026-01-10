"""Integration tests for sticky halt semantics (Story 3.4).

Tests the complete sticky halt flow:
- Halt cannot be cleared without ceremony
- Clearing requires >= 2 Keeper approvers
- HaltClearedEvent is created after successful clear
- DB trigger protection enforces stickiness

ADR-3: Halt is sticky - clearing requires witnessed ceremony
ADR-6: Tier 1 ceremony requires 2 Keepers
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.halt_clear import (
    HaltClearDeniedError,
    InsufficientApproversError,
    InvalidCeremonyError,
)
from src.domain.events.halt_cleared import HaltClearedPayload
from src.domain.models.ceremony_evidence import (
    HALT_CLEAR_CEREMONY_TYPE,
    ApproverSignature,
    CeremonyEvidence,
)
from src.infrastructure.stubs.dual_channel_halt_stub import DualChannelHaltTransportStub


class TestStickyHaltIntegration:
    """Integration tests for sticky halt semantics."""

    @pytest.fixture
    def halt_transport(self) -> DualChannelHaltTransportStub:
        """Create a fresh halt transport stub."""
        return DualChannelHaltTransportStub()

    @pytest.fixture
    def valid_ceremony_evidence(self) -> CeremonyEvidence:
        """Create valid ceremony evidence with 2 approvers (Tier 1)."""
        return CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature(
                    keeper_id="keeper-001",
                    signature=b"valid_signature_1",
                    signed_at=datetime.now(timezone.utc),
                ),
                ApproverSignature(
                    keeper_id="keeper-002",
                    signature=b"valid_signature_2",
                    signed_at=datetime.now(timezone.utc),
                ),
            ),
            created_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_halt_is_sticky_cannot_clear_without_ceremony(
        self, halt_transport: DualChannelHaltTransportStub
    ) -> None:
        """AC #1: Halt cannot be cleared without ceremony evidence."""
        # Set halt state
        crisis_id = uuid4()
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        # Verify halted
        assert await halt_transport.is_halted() is True

        # Attempt to clear without ceremony should fail
        with pytest.raises(HaltClearDeniedError) as exc_info:
            await halt_transport.clear_halt(None)  # type: ignore[arg-type]
        assert "ceremony required" in str(exc_info.value)

        # Verify still halted after failed clear attempt
        assert await halt_transport.is_halted() is True

    @pytest.mark.asyncio
    async def test_clear_halt_with_valid_ceremony_succeeds(
        self,
        halt_transport: DualChannelHaltTransportStub,
        valid_ceremony_evidence: CeremonyEvidence,
    ) -> None:
        """AC #2: Clearing halt with valid ceremony succeeds and creates event."""
        # Set halt state
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )
        assert await halt_transport.is_halted() is True

        # Clear with valid ceremony
        payload = await halt_transport.clear_halt(valid_ceremony_evidence)

        # Verify cleared
        assert await halt_transport.is_halted() is False

        # Verify HaltClearedPayload returned
        assert isinstance(payload, HaltClearedPayload)
        assert payload.ceremony_id == valid_ceremony_evidence.ceremony_id
        assert payload.clearing_authority == "Keeper Council"
        assert len(payload.approvers) == 2
        assert "keeper-001" in payload.approvers
        assert "keeper-002" in payload.approvers

    @pytest.mark.asyncio
    async def test_clear_halt_requires_two_keepers(
        self, halt_transport: DualChannelHaltTransportStub
    ) -> None:
        """AC #5: Clearing halt requires at least 2 Keepers (ADR-6 Tier 1)."""
        # Set halt state
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # Create ceremony with only 1 approver (invalid for Tier 1)
        invalid_evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature(
                    keeper_id="keeper-001",
                    signature=b"valid_signature",
                    signed_at=datetime.now(timezone.utc),
                ),
            ),
            created_at=datetime.now(timezone.utc),
        )

        # Attempt to clear with insufficient approvers
        with pytest.raises(InsufficientApproversError) as exc_info:
            await halt_transport.clear_halt(invalid_evidence)
        assert "2 Keepers" in str(exc_info.value)

        # Verify still halted
        assert await halt_transport.is_halted() is True

    @pytest.mark.asyncio
    async def test_clear_halt_rejects_invalid_signatures(
        self, halt_transport: DualChannelHaltTransportStub
    ) -> None:
        """AC #4: Clearing halt rejects empty/invalid signatures."""
        # Set halt state
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # Create ceremony with empty signature (invalid)
        invalid_evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature(
                    keeper_id="keeper-001",
                    signature=b"valid_signature",
                    signed_at=datetime.now(timezone.utc),
                ),
                ApproverSignature(
                    keeper_id="keeper-002",
                    signature=b"",  # Empty signature!
                    signed_at=datetime.now(timezone.utc),
                ),
            ),
            created_at=datetime.now(timezone.utc),
        )

        # Attempt to clear with invalid signature
        with pytest.raises(InvalidCeremonyError) as exc_info:
            await halt_transport.clear_halt(invalid_evidence)
        assert "keeper-002" in str(exc_info.value)

        # Verify still halted
        assert await halt_transport.is_halted() is True

    @pytest.mark.asyncio
    async def test_clear_halt_works_with_three_keepers(
        self, halt_transport: DualChannelHaltTransportStub
    ) -> None:
        """Clearing halt with > 2 Keepers also works."""
        # Set halt state
        await halt_transport.write_halt(
            reason="FR17: Fork detected",
            crisis_event_id=uuid4(),
        )

        # Create ceremony with 3 approvers
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature(
                    keeper_id="keeper-001",
                    signature=b"sig1",
                    signed_at=datetime.now(timezone.utc),
                ),
                ApproverSignature(
                    keeper_id="keeper-002",
                    signature=b"sig2",
                    signed_at=datetime.now(timezone.utc),
                ),
                ApproverSignature(
                    keeper_id="keeper-003",
                    signature=b"sig3",
                    signed_at=datetime.now(timezone.utc),
                ),
            ),
            created_at=datetime.now(timezone.utc),
        )

        # Clear should succeed
        payload = await halt_transport.clear_halt(evidence)

        # Verify cleared
        assert await halt_transport.is_halted() is False
        assert len(payload.approvers) == 3


class TestHaltClearAuditTrail:
    """Tests for halt clear audit trail."""

    @pytest.fixture
    def halt_transport(self) -> DualChannelHaltTransportStub:
        """Create a fresh halt transport stub."""
        return DualChannelHaltTransportStub()

    @pytest.mark.asyncio
    async def test_halt_cleared_payload_includes_ceremony_details(
        self, halt_transport: DualChannelHaltTransportStub
    ) -> None:
        """HaltClearedPayload must include all ceremony details for audit."""
        ceremony_id = uuid4()
        evidence = CeremonyEvidence(
            ceremony_id=ceremony_id,
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature(
                    keeper_id="keeper-alpha",
                    signature=b"sig_alpha",
                    signed_at=datetime.now(timezone.utc),
                ),
                ApproverSignature(
                    keeper_id="keeper-beta",
                    signature=b"sig_beta",
                    signed_at=datetime.now(timezone.utc),
                ),
            ),
            created_at=datetime.now(timezone.utc),
        )

        # Set halt and clear
        await halt_transport.write_halt("Test halt", uuid4())
        payload = await halt_transport.clear_halt(evidence)

        # Verify audit trail
        assert payload.ceremony_id == ceremony_id
        assert payload.clearing_authority == "Keeper Council"
        assert "keeper-alpha" in payload.approvers
        assert "keeper-beta" in payload.approvers
        assert payload.cleared_at is not None
        assert str(ceremony_id) in payload.reason

    @pytest.mark.asyncio
    async def test_halt_cleared_payload_timestamp_is_recent(
        self, halt_transport: DualChannelHaltTransportStub
    ) -> None:
        """HaltClearedPayload timestamp should be close to current time."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-1", b"sig1", datetime.now(timezone.utc)),
                ApproverSignature("keeper-2", b"sig2", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )

        await halt_transport.write_halt("Test halt", uuid4())
        before_clear = datetime.now(timezone.utc)
        payload = await halt_transport.clear_halt(evidence)
        after_clear = datetime.now(timezone.utc)

        # Timestamp should be within the test window
        assert before_clear <= payload.cleared_at <= after_clear


class TestCeremonyEvidenceValidation:
    """Tests for ceremony evidence validation during clear."""

    @pytest.mark.asyncio
    async def test_ceremony_evidence_validate_method(self) -> None:
        """Ceremony evidence validate() should raise on invalid input."""
        # Zero approvers
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(),
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(InsufficientApproversError):
            evidence.validate()

        # One approver
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-1", b"sig", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(InsufficientApproversError):
            evidence.validate()

        # Empty signature
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-1", b"sig", datetime.now(timezone.utc)),
                ApproverSignature("keeper-2", b"", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(InvalidCeremonyError):
            evidence.validate()

    @pytest.mark.asyncio
    async def test_valid_ceremony_evidence_passes_validation(self) -> None:
        """Valid ceremony evidence should pass validate()."""
        evidence = CeremonyEvidence(
            ceremony_id=uuid4(),
            ceremony_type=HALT_CLEAR_CEREMONY_TYPE,
            approvers=(
                ApproverSignature("keeper-1", b"sig1", datetime.now(timezone.utc)),
                ApproverSignature("keeper-2", b"sig2", datetime.now(timezone.utc)),
            ),
            created_at=datetime.now(timezone.utc),
        )
        assert evidence.validate() is True
