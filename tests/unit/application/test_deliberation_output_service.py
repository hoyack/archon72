"""Unit tests for DeliberationOutputService (Story 2.1, Task 5).

Tests:
- commit_and_store flow
- get_for_viewing flow with FR9 enforcement
- Atomic commit-then-serve behavior
- Error handling

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- AC1: Immediate Output Commitment
- AC2: Hash Verification on View
- AC3: Pre-Commit Access Denial
- AC4: No Preview Code Path
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.deliberation_output import StoredOutput
from src.domain.errors.no_preview import FR9ViolationError
from src.domain.events.deliberation_output import DeliberationOutputPayload


class TestCommitAndStore:
    """Test commit_and_store method."""

    @pytest.mark.asyncio
    async def test_commit_stores_output_and_returns_committed_output(self) -> None:
        """commit_and_store stores output and returns CommittedOutput."""
        from src.application.services.deliberation_output_service import (
            CommittedOutput,
            DeliberationOutputService,
        )

        # Setup mocks
        output_port = AsyncMock()
        output_port.store_output.return_value = StoredOutput(
            output_id=uuid4(),
            content_hash="a" * 64,
            event_sequence=42,
            stored_at=datetime.now(timezone.utc),
        )

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        no_preview_enforcer = MagicMock()

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        # Create payload
        output_id = uuid4()
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="a" * 64,
            content_type="text/plain",
            raw_content="Test output",
        )

        # Execute
        result = await service.commit_and_store(payload)

        # Verify
        assert isinstance(result, CommittedOutput)
        assert result.content_hash == "a" * 64
        output_port.store_output.assert_called_once()
        no_preview_enforcer.mark_committed.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_checks_halt_first(self) -> None:
        """commit_and_store checks halt state before any operation."""
        from src.application.services.deliberation_output_service import (
            DeliberationOutputService,
        )
        from src.domain.errors.writer import SystemHaltedError

        # Setup mocks
        output_port = AsyncMock()
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = True
        halt_checker.get_halt_reason.return_value = "Test halt"
        no_preview_enforcer = MagicMock()

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        payload = DeliberationOutputPayload(
            output_id=uuid4(),
            agent_id="archon-42",
            content_hash="b" * 64,
            content_type="text/plain",
            raw_content="Test",
        )

        # Execute and verify halt is checked first
        with pytest.raises(SystemHaltedError):
            await service.commit_and_store(payload)

        # Output should NOT be stored
        output_port.store_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_commit_marks_committed_in_enforcer(self) -> None:
        """commit_and_store marks output as committed in NoPreviewEnforcer."""
        from src.application.services.deliberation_output_service import (
            DeliberationOutputService,
        )

        output_id = uuid4()
        content_hash = "c" * 64

        output_port = AsyncMock()
        output_port.store_output.return_value = StoredOutput(
            output_id=output_id,
            content_hash=content_hash,
            event_sequence=1,
            stored_at=datetime.now(timezone.utc),
        )

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        no_preview_enforcer = MagicMock()

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash=content_hash,
            content_type="text/plain",
            raw_content="Test",
        )

        await service.commit_and_store(payload)

        # Verify mark_committed called with output_id and hash
        no_preview_enforcer.mark_committed.assert_called_once_with(
            output_id, content_hash=content_hash
        )


class TestGetForViewing:
    """Test get_for_viewing method."""

    @pytest.mark.asyncio
    async def test_get_for_viewing_returns_output_after_commit(self) -> None:
        """get_for_viewing returns output only if committed."""
        from src.application.services.deliberation_output_service import (
            DeliberationOutputService,
            ViewableOutput,
        )

        output_id = uuid4()
        content_hash = "d" * 64
        raw_content = "Agent output content"

        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash=content_hash,
            content_type="text/plain",
            raw_content=raw_content,
        )

        output_port = AsyncMock()
        output_port.get_output.return_value = payload
        output_port.verify_hash.return_value = True

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        no_preview_enforcer = MagicMock()
        no_preview_enforcer.verify_committed.return_value = True
        no_preview_enforcer.verify_hash.return_value = True

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        result = await service.get_for_viewing(output_id, viewer_id="user-123")

        assert isinstance(result, ViewableOutput)
        assert result.output_id == output_id
        assert result.content == raw_content

    @pytest.mark.asyncio
    async def test_get_for_viewing_raises_fr9_for_uncommitted(self) -> None:
        """get_for_viewing raises FR9ViolationError for uncommitted output."""
        from src.application.services.deliberation_output_service import (
            DeliberationOutputService,
        )

        output_id = uuid4()

        output_port = AsyncMock()
        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        no_preview_enforcer = MagicMock()
        no_preview_enforcer.verify_committed.side_effect = FR9ViolationError(
            "FR9: Output must be recorded before viewing"
        )

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        with pytest.raises(FR9ViolationError) as exc_info:
            await service.get_for_viewing(output_id, viewer_id="user-123")

        assert "FR9" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_for_viewing_verifies_hash(self) -> None:
        """get_for_viewing verifies content hash matches."""
        from src.application.services.deliberation_output_service import (
            DeliberationOutputService,
        )

        output_id = uuid4()

        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="e" * 64,
            content_type="text/plain",
            raw_content="Test",
        )

        output_port = AsyncMock()
        output_port.get_output.return_value = payload
        output_port.verify_hash.return_value = True

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        no_preview_enforcer = MagicMock()
        no_preview_enforcer.verify_committed.return_value = True
        no_preview_enforcer.verify_hash.return_value = True

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        await service.get_for_viewing(output_id, viewer_id="user-123")

        # Verify hash verification was called
        no_preview_enforcer.verify_hash.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_for_viewing_returns_none_for_not_found(self) -> None:
        """get_for_viewing returns None if output not found in storage."""
        from src.application.services.deliberation_output_service import (
            DeliberationOutputService,
        )

        output_id = uuid4()

        output_port = AsyncMock()
        output_port.get_output.return_value = None

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        no_preview_enforcer = MagicMock()
        no_preview_enforcer.verify_committed.return_value = True

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        result = await service.get_for_viewing(output_id, viewer_id="user-123")

        assert result is None


class TestAtomicBehavior:
    """Test atomic commit-then-serve behavior (AC4)."""

    @pytest.mark.asyncio
    async def test_commit_failure_does_not_mark_committed(self) -> None:
        """If store fails, output is NOT marked as committed."""
        from src.application.services.deliberation_output_service import (
            DeliberationOutputService,
        )

        output_port = AsyncMock()
        output_port.store_output.side_effect = Exception("Storage failed")

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        no_preview_enforcer = MagicMock()

        service = DeliberationOutputService(
            output_port=output_port,
            halt_checker=halt_checker,
            no_preview_enforcer=no_preview_enforcer,
        )

        payload = DeliberationOutputPayload(
            output_id=uuid4(),
            agent_id="archon-42",
            content_hash="f" * 64,
            content_type="text/plain",
            raw_content="Test",
        )

        with pytest.raises(Exception, match="Storage failed"):
            await service.commit_and_store(payload)

        # mark_committed should NOT be called
        no_preview_enforcer.mark_committed.assert_not_called()


class TestNoInfrastructureImports:
    """Verify application service has no infrastructure imports."""

    def test_service_no_infrastructure_imports(self) -> None:
        """deliberation_output_service.py has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/application/services/deliberation_output_service.py")
        source = file_path.read_text()
        tree = ast.parse(source)

        forbidden_modules = ["src.infrastructure", "sqlalchemy", "redis", "supabase"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in forbidden_modules:
                    assert not node.module.startswith(forbidden), (
                        f"Forbidden import: {node.module}"
                    )
