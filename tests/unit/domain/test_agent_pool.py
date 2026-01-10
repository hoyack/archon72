"""Unit tests for AgentPool domain model (Story 2.2, Task 2).

Tests:
- AgentPool acquire/release logic
- Pool capacity (72 agents per FR10)
- AgentPoolExhaustedError when full
- Batch operations
- Resource management

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- CT-11: Silent failure destroys legitimacy -> report exhaustion
"""

from __future__ import annotations

import pytest


class TestAgentPoolBasics:
    """Test basic AgentPool functionality."""

    def test_pool_creation_with_defaults(self) -> None:
        """AgentPool created with default 72 max concurrent."""
        from src.domain.models.agent_pool import MAX_CONCURRENT_AGENTS, AgentPool

        pool = AgentPool()

        assert pool.max_concurrent == MAX_CONCURRENT_AGENTS
        assert pool.max_concurrent == 72
        assert pool.active_count == 0
        assert pool.available_count == 72
        assert not pool.is_exhausted

    def test_pool_creation_with_custom_max(self) -> None:
        """AgentPool can be created with custom max."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool(max_concurrent=10)

        assert pool.max_concurrent == 10
        assert pool.available_count == 10

    def test_active_agents_returns_frozenset(self) -> None:
        """active_agents property returns immutable frozenset."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        pool.acquire("archon-1")

        agents = pool.active_agents

        assert isinstance(agents, frozenset)
        assert "archon-1" in agents


class TestAgentPoolAcquire:
    """Test AgentPool acquire functionality."""

    def test_acquire_adds_agent_to_pool(self) -> None:
        """Acquiring an agent adds it to the active set."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        result = pool.acquire("archon-1")

        assert result is True
        assert pool.active_count == 1
        assert pool.is_active("archon-1")

    def test_acquire_multiple_agents(self) -> None:
        """Can acquire multiple different agents."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        pool.acquire("archon-1")
        pool.acquire("archon-2")
        pool.acquire("archon-3")

        assert pool.active_count == 3
        assert pool.is_active("archon-1")
        assert pool.is_active("archon-2")
        assert pool.is_active("archon-3")

    def test_acquire_same_agent_is_idempotent(self) -> None:
        """Acquiring an already-active agent returns False."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        pool.acquire("archon-1")
        result = pool.acquire("archon-1")

        assert result is False
        assert pool.active_count == 1

    def test_acquire_raises_when_exhausted(self) -> None:
        """Acquiring when pool exhausted raises AgentPoolExhaustedError."""
        from src.domain.errors.agent import AgentPoolExhaustedError
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool(max_concurrent=3)
        pool.acquire("archon-1")
        pool.acquire("archon-2")
        pool.acquire("archon-3")

        with pytest.raises(AgentPoolExhaustedError, match="FR10"):
            pool.acquire("archon-4")

    def test_acquire_72_agents_succeeds(self) -> None:
        """Can acquire exactly 72 agents (FR10 limit)."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()

        for i in range(72):
            pool.acquire(f"archon-{i}")

        assert pool.active_count == 72
        assert pool.is_exhausted
        assert pool.available_count == 0


class TestAgentPoolRelease:
    """Test AgentPool release functionality."""

    def test_release_removes_agent_from_pool(self) -> None:
        """Releasing an agent removes it from the active set."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        pool.acquire("archon-1")
        result = pool.release("archon-1")

        assert result is True
        assert pool.active_count == 0
        assert not pool.is_active("archon-1")

    def test_release_nonactive_agent_returns_false(self) -> None:
        """Releasing an agent not in pool returns False."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        result = pool.release("archon-99")

        assert result is False

    def test_release_allows_reacquire(self) -> None:
        """After release, can acquire new agent."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool(max_concurrent=2)
        pool.acquire("archon-1")
        pool.acquire("archon-2")
        pool.release("archon-1")
        result = pool.acquire("archon-3")

        assert result is True
        assert pool.active_count == 2
        assert pool.is_active("archon-2")
        assert pool.is_active("archon-3")
        assert not pool.is_active("archon-1")


class TestAgentPoolBatchOperations:
    """Test AgentPool batch acquire/release."""

    def test_try_acquire_batch_success(self) -> None:
        """Batch acquire succeeds when capacity available."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool(max_concurrent=10)
        success, reason = pool.try_acquire_batch(
            ["archon-1", "archon-2", "archon-3"]
        )

        assert success is True
        assert reason is None
        assert pool.active_count == 3

    def test_try_acquire_batch_fails_capacity(self) -> None:
        """Batch acquire fails when exceeds capacity."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool(max_concurrent=2)
        success, reason = pool.try_acquire_batch(
            ["archon-1", "archon-2", "archon-3"]
        )

        assert success is False
        assert "FR10" in reason
        assert pool.active_count == 0  # No partial allocation

    def test_try_acquire_batch_fails_already_active(self) -> None:
        """Batch acquire fails if agent already active."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        pool.acquire("archon-1")

        success, reason = pool.try_acquire_batch(
            ["archon-1", "archon-2", "archon-3"]
        )

        assert success is False
        assert "already active" in reason

    def test_try_acquire_batch_deduplicates(self) -> None:
        """Batch acquire handles duplicate IDs correctly."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        success, reason = pool.try_acquire_batch(
            ["archon-1", "archon-1", "archon-2"]
        )

        assert success is True
        assert pool.active_count == 2  # Only 2 unique

    def test_release_batch_releases_all(self) -> None:
        """Batch release releases all specified agents."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        pool.try_acquire_batch(["archon-1", "archon-2", "archon-3"])

        released = pool.release_batch(["archon-1", "archon-3"])

        assert released == 2
        assert pool.active_count == 1
        assert pool.is_active("archon-2")

    def test_release_batch_ignores_nonactive(self) -> None:
        """Batch release ignores agents not active."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        pool.acquire("archon-1")

        released = pool.release_batch(["archon-1", "archon-99"])

        assert released == 1
        assert pool.active_count == 0


class TestAgentPoolReset:
    """Test AgentPool reset functionality."""

    def test_reset_clears_all_agents(self) -> None:
        """Reset removes all active agents."""
        from src.domain.models.agent_pool import AgentPool

        pool = AgentPool()
        for i in range(10):
            pool.acquire(f"archon-{i}")

        released = pool.reset()

        assert released == 10
        assert pool.active_count == 0
        assert pool.available_count == pool.max_concurrent


class TestMaxConcurrentAgentsConstant:
    """Test MAX_CONCURRENT_AGENTS constant."""

    def test_max_constant_is_72(self) -> None:
        """MAX_CONCURRENT_AGENTS is 72 (FR10)."""
        from src.domain.models.agent_pool import MAX_CONCURRENT_AGENTS

        assert MAX_CONCURRENT_AGENTS == 72

    def test_max_constant_exported_from_package(self) -> None:
        """MAX_CONCURRENT_AGENTS exported from domain.models."""
        from src.domain.models import MAX_CONCURRENT_AGENTS

        assert MAX_CONCURRENT_AGENTS == 72


class TestAgentErrors:
    """Test agent error classes."""

    def test_agent_pool_exhausted_error_inherits(self) -> None:
        """AgentPoolExhaustedError inherits from ConclaveError."""
        from src.domain.errors.agent import AgentPoolExhaustedError
        from src.domain.exceptions import ConclaveError

        assert issubclass(AgentPoolExhaustedError, ConclaveError)

    def test_agent_invocation_error_inherits(self) -> None:
        """AgentInvocationError inherits from ConclaveError."""
        from src.domain.errors.agent import AgentInvocationError
        from src.domain.exceptions import ConclaveError

        assert issubclass(AgentInvocationError, ConclaveError)

    def test_agent_not_found_error_inherits(self) -> None:
        """AgentNotFoundError inherits from ConclaveError."""
        from src.domain.errors.agent import AgentNotFoundError
        from src.domain.exceptions import ConclaveError

        assert issubclass(AgentNotFoundError, ConclaveError)

    def test_errors_exported_from_package(self) -> None:
        """Agent errors exported from domain.errors."""
        from src.domain.errors import (
            AgentInvocationError,
            AgentNotFoundError,
            AgentPoolExhaustedError,
        )

        # Just verify they can be imported
        assert AgentPoolExhaustedError is not None
        assert AgentInvocationError is not None
        assert AgentNotFoundError is not None


class TestAgentPoolNoInfrastructureImports:
    """Verify domain model has no infrastructure imports."""

    def test_pool_no_infrastructure_imports(self) -> None:
        """agent_pool.py has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/domain/models/agent_pool.py")
        source = file_path.read_text()
        tree = ast.parse(source)

        forbidden_modules = [
            "src.infrastructure",
            "src.application",
            "sqlalchemy",
            "redis",
            "supabase",
            "crewai",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_modules:
                        assert not node.module.startswith(forbidden), (
                            f"Forbidden import: {node.module}"
                        )

    def test_errors_no_infrastructure_imports(self) -> None:
        """agent.py errors has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/domain/errors/agent.py")
        source = file_path.read_text()
        tree = ast.parse(source)

        forbidden_modules = [
            "src.infrastructure",
            "src.application",
            "sqlalchemy",
            "redis",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_modules:
                        assert not node.module.startswith(forbidden), (
                            f"Forbidden import: {node.module}"
                        )
