"""Integration tests for schema irreversibility (Story 7.3, FR40, NFR40).

Tests for:
- AC1: No CESSATION_REVERSAL event type exists in schema
- AC2: Writer rejects posts after cessation
- AC3: Prohibition enforced at import time
- AC4: Constitutional errors include NFR40 references
- AC5: Terminal check is BEFORE halt check

These tests validate the end-to-end behavior of the schema
irreversibility constraints across multiple components.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.schema_irreversibility import (
    EventTypeProhibitedError,
    SchemaIrreversibilityError,
)
from src.domain.events import CESSATION_EXECUTED_EVENT_TYPE
from src.domain.events.cessation_executed import CessationExecutedEventPayload
from src.domain.services.event_type_validator import (
    is_prohibited_event_type,
    validate_event_type,
)


class TestAC1NoReversalEventTypeInSchema:
    """AC1: No CESSATION_REVERSAL event type exists in the schema."""

    def test_cessation_reversal_event_type_does_not_exist(self) -> None:
        """Verify that no CESSATION_REVERSAL event type constant exists."""
        from src.domain import events

        # Check that no "reversal" event type constants exist
        event_type_names = [
            name for name in dir(events) if name.endswith("_EVENT_TYPE")
        ]

        # None should contain "reversal", "undo", "revert" for cessation
        prohibited_patterns = ["reversal", "undo", "revert", "cancel", "restore"]
        for name in event_type_names:
            name_lower = name.lower()
            for pattern in prohibited_patterns:
                if "cessation" in name_lower and pattern in name_lower:
                    pytest.fail(
                        f"Found prohibited event type constant: {name} "
                        f"(NFR40: No cessation reversal)"
                    )

    def test_cessation_executed_is_only_terminal_cessation_event(self) -> None:
        """Verify that CESSATION_EXECUTED is the only terminal cessation event."""
        from src.domain import events

        # Get all cessation event types
        cessation_types = [
            getattr(events, name)
            for name in dir(events)
            if name.endswith("_EVENT_TYPE") and "cessation" in name.lower()
        ]

        # Only cessation.executed should be "terminal"
        assert CESSATION_EXECUTED_EVENT_TYPE in cessation_types
        assert CESSATION_EXECUTED_EVENT_TYPE == "cessation.executed"


class TestAC2WriterRejectsPostCessation:
    """AC2: Writer rejects any event writes attempted after a CESSATION_EXECUTED event."""

    @pytest.mark.asyncio
    async def test_event_writer_rejects_post_cessation_writes(self) -> None:
        """EventWriterService should reject writes when system is terminated."""
        from unittest.mock import AsyncMock

        from src.application.services.event_writer_service import EventWriterService
        from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
        from src.infrastructure.stubs.terminal_event_detector_stub import (
            TerminalEventDetectorStub,
        )
        from src.infrastructure.stubs.writer_lock_stub import WriterLockStub

        # Setup mocks
        atomic_writer = AsyncMock()
        halt_checker = HaltCheckerStub()
        writer_lock = WriterLockStub()
        event_store = AsyncMock()
        event_store.get_latest_event = AsyncMock(return_value=None)
        terminal_detector = TerminalEventDetectorStub()

        service = EventWriterService(
            atomic_writer=atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=event_store,
            terminal_detector=terminal_detector,
        )

        # Setup: acquire lock and verify
        await writer_lock.acquire()
        await service.verify_startup()

        # Simulate cessation event
        terminal_detector.set_terminated_simple()

        # Act & Assert: should raise SchemaIrreversibilityError
        with pytest.raises(SchemaIrreversibilityError) as exc_info:
            await service.write_event(
                event_type="test.event",
                payload={"key": "value"},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "NFR40" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_terminal_state_is_permanent(self) -> None:
        """Terminal state should be permanent once set."""
        from src.infrastructure.stubs.terminal_event_detector_stub import (
            TerminalEventDetectorStub,
        )

        detector = TerminalEventDetectorStub()

        # Not terminated initially
        assert await detector.is_system_terminated() is False

        # Set terminated
        detector.set_terminated_simple()
        assert await detector.is_system_terminated() is True

        # Should remain terminated (in production, cannot be cleared)
        # Note: clear_termination() exists only for test isolation
        for _ in range(10):
            assert await detector.is_system_terminated() is True


class TestAC3ImportTimeValidation:
    """AC3: Prohibition is enforced at import time via event type validation."""

    def test_import_events_module_validates_all_types(self) -> None:
        """Importing events module should validate all event types."""
        # This import should succeed (no prohibited types in production)
        from src.domain import events  # noqa: F401

        # If we got here, import-time validation passed

    def test_validator_rejects_prohibited_patterns(self) -> None:
        """Event type validator should reject prohibited patterns."""
        prohibited_types = [
            "cessation.reversal",
            "cessation_undo",
            "cessation-revert",
            "cessationRestore",
            "CESSATION.CANCEL",
            "cessation.rollback",
            "uncease",
            "resurrect",
            "revive.system",
        ]

        for event_type in prohibited_types:
            with pytest.raises(EventTypeProhibitedError):
                validate_event_type(event_type)

    def test_validator_accepts_valid_cessation_types(self) -> None:
        """Event type validator should accept valid cessation types."""
        valid_types = [
            "cessation.executed",
            "cessation.consideration",
            "cessation.decision",
            "cessation.agenda.placement",
        ]

        for event_type in valid_types:
            assert validate_event_type(event_type) is True


class TestAC4ConstitutionalErrorReferences:
    """AC4: Constitutional errors include NFR40 references."""

    def test_schema_irreversibility_error_mentions_nfr40(self) -> None:
        """SchemaIrreversibilityError should include NFR40 reference."""
        error = SchemaIrreversibilityError("NFR40: Cannot write events after cessation")
        assert "NFR40" in str(error)

    def test_event_type_prohibited_error_mentions_nfr40(self) -> None:
        """EventTypeProhibitedError should include NFR40 reference."""
        try:
            validate_event_type("cessation.reversal")
        except EventTypeProhibitedError as e:
            assert "NFR40" in str(e)
        else:
            pytest.fail("Expected EventTypeProhibitedError")

    def test_cessation_executed_payload_enforces_is_terminal(self) -> None:
        """CessationExecutedEventPayload should enforce is_terminal=True."""
        with pytest.raises(ValueError) as exc_info:
            CessationExecutedEventPayload(
                cessation_id=uuid4(),
                execution_timestamp=datetime.now(timezone.utc),
                is_terminal=False,  # Invalid!
                final_sequence_number=1,
                final_hash="a" * 64,
                reason="Test",
                triggering_event_id=uuid4(),
            )

        assert "NFR40" in str(exc_info.value)


class TestAC5TerminalBeforeHalt:
    """AC5: Terminal check happens BEFORE halt check."""

    @pytest.mark.asyncio
    async def test_terminal_check_precedes_halt_check(self) -> None:
        """When both terminated and halted, terminal error should be raised first."""
        from unittest.mock import AsyncMock

        from src.application.services.event_writer_service import EventWriterService
        from src.domain.errors.writer import SystemHaltedError
        from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
        from src.infrastructure.stubs.terminal_event_detector_stub import (
            TerminalEventDetectorStub,
        )
        from src.infrastructure.stubs.writer_lock_stub import WriterLockStub

        # Setup with both terminal and halt state
        atomic_writer = AsyncMock()
        halt_checker = HaltCheckerStub()
        writer_lock = WriterLockStub()
        event_store = AsyncMock()
        event_store.get_latest_event = AsyncMock(return_value=None)
        terminal_detector = TerminalEventDetectorStub()

        service = EventWriterService(
            atomic_writer=atomic_writer,
            halt_checker=halt_checker,
            writer_lock=writer_lock,
            event_store=event_store,
            terminal_detector=terminal_detector,
        )

        # Both terminated AND halted
        terminal_detector.set_terminated_simple()
        halt_checker.set_halted(True, "System halted for maintenance")

        await writer_lock.acquire()
        service._verified = True

        # Act & Assert: SchemaIrreversibilityError should be raised, NOT SystemHaltedError
        with pytest.raises(SchemaIrreversibilityError):
            await service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )

        # Verify it was NOT SystemHaltedError
        try:
            await service.write_event(
                event_type="test.event",
                payload={},
                agent_id="agent-001",
                local_timestamp=datetime.now(timezone.utc),
            )
        except SchemaIrreversibilityError:
            pass  # Expected
        except SystemHaltedError:
            pytest.fail("SystemHaltedError raised - terminal check should come first!")


class TestCessationExecutedPayloadIntegration:
    """Integration tests for CessationExecutedEventPayload."""

    def test_payload_signable_content_includes_is_terminal(self) -> None:
        """Signable content should include is_terminal=True."""
        import json

        payload = CessationExecutedEventPayload.create(
            cessation_id=uuid4(),
            execution_timestamp=datetime.now(timezone.utc),
            final_sequence_number=100,
            final_hash="b" * 64,
            reason="Unanimous vote outcome",
            triggering_event_id=uuid4(),
        )

        content = json.loads(payload.signable_content().decode("utf-8"))
        assert content["is_terminal"] is True

    def test_payload_to_dict_serialization(self) -> None:
        """to_dict() should produce valid serialization."""
        cessation_id = uuid4()
        triggering_event_id = uuid4()
        execution_timestamp = datetime.now(timezone.utc)

        payload = CessationExecutedEventPayload.create(
            cessation_id=cessation_id,
            execution_timestamp=execution_timestamp,
            final_sequence_number=42,
            final_hash="c" * 64,
            reason="Test reason",
            triggering_event_id=triggering_event_id,
        )

        result = payload.to_dict()

        assert result["cessation_id"] == str(cessation_id)
        assert result["triggering_event_id"] == str(triggering_event_id)
        assert result["is_terminal"] is True
        assert result["final_sequence_number"] == 42


class TestEventTypeValidatorIntegration:
    """Integration tests for event type validator."""

    def test_is_prohibited_predicate(self) -> None:
        """is_prohibited_event_type should be usable as predicate."""
        # Prohibited
        assert is_prohibited_event_type("cessation.reversal") is True
        assert is_prohibited_event_type("uncease") is True

        # Valid
        assert is_prohibited_event_type("cessation.executed") is False
        assert is_prohibited_event_type("vote.cast") is False

    def test_validator_case_insensitive(self) -> None:
        """Validator should be case-insensitive."""
        prohibited_variants = [
            "cessation.reversal",
            "CESSATION.REVERSAL",
            "Cessation.Reversal",
            "cessationReversal",
            "CESSATIONREVERSAL",
        ]

        for variant in prohibited_variants:
            assert is_prohibited_event_type(variant) is True

    def test_all_existing_event_types_are_valid(self) -> None:
        """All existing event type constants should pass validation."""
        from src.domain import events

        event_type_names = [
            name for name in dir(events) if name.endswith("_EVENT_TYPE")
        ]

        for name in event_type_names:
            event_type_value = getattr(events, name)
            # Should not raise
            try:
                validate_event_type(event_type_value)
            except EventTypeProhibitedError:
                pytest.fail(
                    f"Event type {name}={event_type_value} unexpectedly prohibited"
                )


class TestSchemaDocumentation:
    """Tests for schema documentation compliance."""

    def test_events_module_docstring_mentions_nfr40(self) -> None:
        """Events module docstring should mention NFR40."""
        from src.domain import events

        docstring = events.__doc__ or ""
        assert "NFR40" in docstring

    def test_events_module_lists_prohibited_patterns(self) -> None:
        """Events module docstring should list prohibited patterns."""
        from src.domain import events

        docstring = events.__doc__ or ""
        assert "reversal" in docstring.lower()
        assert "prohibited" in docstring.lower()
