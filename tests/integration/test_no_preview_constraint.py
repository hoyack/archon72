"""Integration tests for FR9 No Preview Constraint (Story 2.1, Task 7).

These tests verify the complete FR9 constraint enforcement across
all components working together.

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- AC1: Immediate Output Commitment
- AC2: Hash Verification on View
- AC3: Pre-Commit Access Denial
- AC4: No Preview Code Path - atomic commit-then-serve
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.deliberation_output import StoredOutput
from src.application.services.deliberation_output_service import (
    DeliberationOutputService,
)
from src.domain.errors.no_preview import FR9ViolationError
from src.domain.events.deliberation_output import DeliberationOutputPayload
from src.domain.services.no_preview_enforcer import NoPreviewEnforcer
from src.infrastructure.stubs.deliberation_output_stub import DeliberationOutputStub


class TestNoPreviewConstraintIntegration:
    """Integration tests for FR9 No Preview constraint."""

    @pytest.fixture
    def halt_checker(self) -> AsyncMock:
        """Mock halt checker that is never halted."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        checker.get_halt_reason.return_value = None
        return checker

    @pytest.fixture
    def enforcer(self) -> NoPreviewEnforcer:
        """Fresh NoPreviewEnforcer instance."""
        return NoPreviewEnforcer()

    @pytest.fixture
    def output_stub(self) -> DeliberationOutputStub:
        """Fresh DeliberationOutputStub instance."""
        return DeliberationOutputStub()

    @pytest.fixture
    def service(
        self,
        output_stub: DeliberationOutputStub,
        halt_checker: AsyncMock,
        enforcer: NoPreviewEnforcer,
    ) -> DeliberationOutputService:
        """DeliberationOutputService with real components."""
        return DeliberationOutputService(
            output_port=output_stub,
            halt_checker=halt_checker,
            no_preview_enforcer=enforcer,
        )

    @pytest.mark.asyncio
    async def test_cannot_view_output_before_commit_ac3(
        self,
        service: DeliberationOutputService,
    ) -> None:
        """AC3: Cannot view output that hasn't been committed.

        This is the core FR9 test - attempting to view uncommitted output
        must raise FR9ViolationError with the prescribed message.
        """
        output_id = uuid4()

        with pytest.raises(FR9ViolationError) as exc_info:
            await service.get_for_viewing(output_id, viewer_id="user-123")

        # AC3: Error message must include "FR9: Output must be recorded before viewing"
        assert "FR9" in str(exc_info.value)
        assert "recorded before viewing" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_can_view_output_after_commit_ac1_ac2(
        self,
        service: DeliberationOutputService,
    ) -> None:
        """AC1 + AC2: Output is viewable only after commit with hash verification."""
        output_id = uuid4()
        content_hash = "a" * 64
        raw_content = "This is the agent deliberation output"

        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash=content_hash,
            content_type="text/plain",
            raw_content=raw_content,
        )

        # First, commit the output (AC1)
        committed = await service.commit_and_store(payload)
        assert committed.output_id == output_id
        assert committed.content_hash == content_hash

        # Now, view should succeed with hash verification (AC2)
        result = await service.get_for_viewing(output_id, viewer_id="user-456")

        assert result is not None
        assert result.output_id == output_id
        assert result.content == raw_content
        assert result.content_hash == content_hash

    @pytest.mark.asyncio
    async def test_hash_mismatch_detected_and_rejected_ac2(
        self,
        output_stub: DeliberationOutputStub,
        halt_checker: AsyncMock,
        enforcer: NoPreviewEnforcer,
    ) -> None:
        """AC2: Hash mismatch during view is detected and rejected."""
        output_id = uuid4()
        original_hash = "b" * 64
        tampered_hash = "c" * 64

        # Store output with original hash
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash=original_hash,
            content_type="text/plain",
            raw_content="Original content",
        )
        await output_stub.store_output(payload, event_sequence=1)

        # Mark committed with DIFFERENT hash (simulating tampering detection)
        enforcer.mark_committed(output_id, content_hash=tampered_hash)

        service = DeliberationOutputService(
            output_port=output_stub,
            halt_checker=halt_checker,
            no_preview_enforcer=enforcer,
        )

        # Viewing should detect mismatch and raise FR9ViolationError
        with pytest.raises(FR9ViolationError) as exc_info:
            await service.get_for_viewing(output_id, viewer_id="user-789")

        assert "hash mismatch" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_view_event_logged_after_successful_retrieval(
        self,
        service: DeliberationOutputService,
        output_stub: DeliberationOutputStub,
    ) -> None:
        """AC2: View event is logged with viewer identity after successful retrieval.

        Note: Full view event logging will be implemented with EventWriterService
        integration. This test verifies the flow works with viewer identity.
        """
        output_id = uuid4()
        viewer_id = "user-audit-test"

        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="d" * 64,
            content_type="text/plain",
            raw_content="Audit test content",
        )

        await service.commit_and_store(payload)

        # View with specific viewer_id
        result = await service.get_for_viewing(output_id, viewer_id=viewer_id)

        assert result is not None
        # The viewer_id is passed through; actual event logging would be verified
        # by checking EventWriterService calls in a full integration test

    @pytest.mark.asyncio
    async def test_atomic_failure_if_store_fails_mid_commit_ac4(
        self,
        halt_checker: AsyncMock,
        enforcer: NoPreviewEnforcer,
    ) -> None:
        """AC4: Atomic failure - output NOT marked committed if store fails."""
        output_id = uuid4()

        # Create a failing output port
        failing_port = AsyncMock()
        failing_port.store_output.side_effect = Exception("Storage failure")

        service = DeliberationOutputService(
            output_port=failing_port,
            halt_checker=halt_checker,
            no_preview_enforcer=enforcer,
        )

        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="e" * 64,
            content_type="text/plain",
            raw_content="Should not be committed",
        )

        # Commit should fail
        with pytest.raises(Exception, match="Storage failure"):
            await service.commit_and_store(payload)

        # Output should NOT be marked committed
        assert enforcer.is_committed(output_id) is False

        # Attempting to view should fail with FR9 error
        with pytest.raises(FR9ViolationError):
            # Need to create a working service for this check
            working_port = DeliberationOutputStub()
            working_service = DeliberationOutputService(
                output_port=working_port,
                halt_checker=halt_checker,
                no_preview_enforcer=enforcer,
            )
            await working_service.get_for_viewing(output_id, viewer_id="user-123")


class TestNoPreviewCodePath:
    """Tests verifying no code path allows preview before commit (AC4)."""

    @pytest.mark.asyncio
    async def test_enforcer_called_before_storage_retrieval(
        self,
    ) -> None:
        """AC4: NoPreviewEnforcer.verify_committed called before get_output."""
        output_id = uuid4()

        # Track call order
        call_order: list[str] = []

        # Create mock enforcer that tracks calls
        class OrderTrackingEnforcer:
            def mark_committed(
                self, oid: uuid4, *, content_hash: str | None = None
            ) -> None:
                pass

            def verify_committed(self, oid: uuid4) -> bool:
                call_order.append("verify_committed")
                return True

            def verify_hash(self, oid: uuid4, h: str) -> bool:
                call_order.append("verify_hash")
                return True

        # Create mock port that tracks calls
        class OrderTrackingPort:
            async def store_output(self, payload: any, event_sequence: int) -> any:
                call_order.append("store_output")
                return StoredOutput(
                    output_id=output_id,
                    content_hash="f" * 64,
                    event_sequence=1,
                    stored_at=datetime.now(timezone.utc),
                )

            async def get_output(self, oid: uuid4) -> any:
                call_order.append("get_output")
                return DeliberationOutputPayload(
                    output_id=output_id,
                    agent_id="archon-42",
                    content_hash="f" * 64,
                    content_type="text/plain",
                    raw_content="Test",
                )

            async def verify_hash(self, oid: uuid4, h: str) -> bool:
                return True

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        service = DeliberationOutputService(
            output_port=OrderTrackingPort(),  # type: ignore[arg-type]
            halt_checker=halt_checker,
            no_preview_enforcer=OrderTrackingEnforcer(),  # type: ignore[arg-type]
        )

        await service.get_for_viewing(output_id, viewer_id="user-123")

        # verify_committed MUST be called BEFORE get_output
        assert "verify_committed" in call_order
        assert "get_output" in call_order
        assert call_order.index("verify_committed") < call_order.index("get_output")


class TestDeliberationOutputPayloadValidation:
    """Tests for DeliberationOutputPayload validation."""

    def test_payload_validates_content_hash_length(self) -> None:
        """Payload validates content_hash is 64 characters."""
        with pytest.raises(ValueError, match="content_hash"):
            DeliberationOutputPayload(
                output_id=uuid4(),
                agent_id="archon-42",
                content_hash="tooshort",
                content_type="text/plain",
                raw_content="Test",
            )

    def test_payload_validates_agent_id_not_empty(self) -> None:
        """Payload validates agent_id is not empty."""
        with pytest.raises(ValueError, match="agent_id"):
            DeliberationOutputPayload(
                output_id=uuid4(),
                agent_id="",
                content_hash="g" * 64,
                content_type="text/plain",
                raw_content="Test",
            )
