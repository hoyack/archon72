"""Integration tests for pre-operational verification (Story 8.5, FR146, NFR35).

Tests the complete verification checklist execution and startup integration.

Constitutional Constraints:
- FR146: Startup SHALL execute verification checklist - blocked until pass
- NFR35: System startup SHALL complete verification checklist before operation
- CT-13: Integrity outranks availability
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.api.startup import run_pre_operational_verification
from src.application.services.pre_operational_verification_service import (
    PreOperationalVerificationService,
)
from src.domain.models.verification_result import (
    VerificationStatus,
)


@pytest.fixture
def mock_hash_verifier() -> AsyncMock:
    """Create mock hash verifier that passes."""
    mock = AsyncMock()
    mock.run_full_scan.return_value = MagicMock(
        passed=True,
        events_scanned=1000,
        scan_id="scan-001",
        failed_event_id=None,
        expected_hash=None,
        actual_hash=None,
    )
    return mock


@pytest.fixture
def mock_witness_pool_monitor() -> AsyncMock:
    """Create mock witness pool monitor with healthy pool."""
    mock = AsyncMock()
    mock.get_pool_status.return_value = MagicMock(
        available_count=12,
        effective_count=12,
        excluded_witnesses=(),
        is_degraded=False,
    )
    return mock


@pytest.fixture
def mock_keeper_key_registry() -> AsyncMock:
    """Create mock keeper key registry with active keys."""
    mock = AsyncMock()
    now = datetime.now(timezone.utc)
    mock.get_all_keys_for_keeper.return_value = [
        MagicMock(
            key_id="key-001",
            keeper_id="KEEPER:primary",
            active_from=now - timedelta(days=30),
            active_until=None,
        )
    ]
    return mock


@pytest.fixture
def mock_checkpoint_repository() -> AsyncMock:
    """Create mock checkpoint repository with recent checkpoint."""
    mock = AsyncMock()
    now = datetime.now(timezone.utc)
    checkpoint = MagicMock(
        checkpoint_id=uuid4(),
        event_sequence=1000,
        timestamp=now - timedelta(hours=1),
        anchor_hash="abc123",
        anchor_type="periodic",
    )
    mock.get_all_checkpoints.return_value = [checkpoint]
    mock.get_latest_checkpoint.return_value = checkpoint
    return mock


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker that is not halted."""
    mock = AsyncMock()
    mock.is_halted.return_value = False
    mock.get_halt_reason.return_value = None
    return mock


@pytest.fixture
def mock_event_replicator() -> AsyncMock:
    """Create mock event replicator with healthy replicas."""
    mock = AsyncMock()
    mock.verify_replicas.return_value = MagicMock(
        is_valid=True,
        head_hash_match=True,
        signature_valid=True,
        schema_version_match=True,
        errors=(),
    )
    return mock


@pytest.fixture
def service_with_passing_checks(
    mock_hash_verifier: AsyncMock,
    mock_witness_pool_monitor: AsyncMock,
    mock_keeper_key_registry: AsyncMock,
    mock_checkpoint_repository: AsyncMock,
    mock_halt_checker: AsyncMock,
    mock_event_replicator: AsyncMock,
) -> PreOperationalVerificationService:
    """Create service with all passing mocks."""
    return PreOperationalVerificationService(
        hash_verifier=mock_hash_verifier,
        witness_pool_monitor=mock_witness_pool_monitor,
        keeper_key_registry=mock_keeper_key_registry,
        checkpoint_repository=mock_checkpoint_repository,
        halt_checker=mock_halt_checker,
        event_replicator=mock_event_replicator,
    )


class TestFullChecklistExecution:
    """Tests for complete verification checklist execution."""

    @pytest.mark.asyncio
    async def test_full_checklist_with_all_checks_passing(
        self,
        service_with_passing_checks: PreOperationalVerificationService,
    ) -> None:
        """Should execute all 6 checks and return PASSED status."""
        result = await service_with_passing_checks.run_verification_checklist()

        # Verify all 6 checks were executed
        assert result.check_count == 6

        # Verify all checks passed
        assert result.status == VerificationStatus.PASSED
        assert result.failure_count == 0

        # Verify each check by name
        expected_checks = [
            "halt_state",
            "hash_chain",
            "checkpoint_anchors",
            "keeper_keys",
            "witness_pool",
            "replica_sync",
        ]
        for check_name in expected_checks:
            check = result.get_check_by_name(check_name)
            assert check is not None, f"Missing check: {check_name}"
            assert check.passed is True, f"Check {check_name} should pass"

    @pytest.mark.asyncio
    async def test_checklist_execution_timing(
        self,
        service_with_passing_checks: PreOperationalVerificationService,
    ) -> None:
        """Should complete verification in reasonable time."""
        result = await service_with_passing_checks.run_verification_checklist()

        # Duration should be reasonable (< 5 seconds for test mocks)
        assert result.duration_ms < 5000
        assert result.started_at < result.completed_at


class TestStartupBlocking:
    """Tests for startup blocking on verification failure."""

    @pytest.mark.asyncio
    async def test_startup_blocked_on_hash_chain_failure(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should block startup when hash chain verification fails."""
        # Make hash chain fail
        mock_hash_verifier.run_full_scan.return_value = MagicMock(
            passed=False,
            events_scanned=500,
            scan_id="scan-002",
            failed_event_id="event-456",
            expected_hash="expected123",
            actual_hash="actual789",
        )

        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        assert result.status == VerificationStatus.FAILED
        assert result.failure_count == 1

        failed_check = result.get_check_by_name("hash_chain")
        assert failed_check is not None
        assert not failed_check.passed

    @pytest.mark.asyncio
    async def test_startup_blocked_on_witness_pool_failure(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should block startup when witness pool is insufficient."""
        # Make witness pool insufficient
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=3,
            effective_count=3,
            excluded_witnesses=(),
            is_degraded=True,
        )

        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        assert result.status == VerificationStatus.FAILED

        failed_check = result.get_check_by_name("witness_pool")
        assert failed_check is not None
        assert not failed_check.passed

    @pytest.mark.asyncio
    async def test_startup_proceeds_when_all_checks_pass(
        self,
        service_with_passing_checks: PreOperationalVerificationService,
    ) -> None:
        """Should allow startup to proceed when all checks pass."""
        result = await service_with_passing_checks.run_verification_checklist()

        assert result.status == VerificationStatus.PASSED
        # All checks should have passed
        for check in result.checks:
            assert check.passed is True


class TestPostHaltVerificationMode:
    """Tests for post-halt stringent verification."""

    @pytest.mark.asyncio
    async def test_post_halt_sets_flag_in_result(
        self,
        service_with_passing_checks: PreOperationalVerificationService,
    ) -> None:
        """Should set is_post_halt flag in verification result."""
        result = await service_with_passing_checks.run_verification_checklist(
            is_post_halt=True
        )

        assert result.is_post_halt is True

    @pytest.mark.asyncio
    async def test_post_halt_full_chain_verification(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should verify full hash chain in post-halt mode."""
        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        await service.run_verification_checklist(is_post_halt=True)

        # Should call with max_events=None for full verification
        mock_hash_verifier.run_full_scan.assert_called_once_with(max_events=None)

    @pytest.mark.asyncio
    async def test_post_halt_no_bypass_allowed(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should never allow bypass in post-halt mode even with failure."""
        # Make a check fail
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=4,
            effective_count=4,
            excluded_witnesses=(),
            is_degraded=True,
        )

        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        result = await service.run_verification_checklist(
            is_post_halt=True,
            allow_bypass=True,  # Should be ignored
        )

        # Should be FAILED, not BYPASSED
        assert result.status == VerificationStatus.FAILED
        assert result.bypass_reason is None


class TestVerificationResultLogging:
    """Tests for verification results are logged correctly."""

    @pytest.mark.asyncio
    async def test_result_contains_check_details(
        self,
        service_with_passing_checks: PreOperationalVerificationService,
    ) -> None:
        """Should include details in each check result."""
        result = await service_with_passing_checks.run_verification_checklist()

        for check in result.checks:
            # Each check should have meaningful details
            assert check.name is not None
            assert check.details is not None
            assert len(check.details) > 0
            assert check.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_result_summary_generation(
        self,
        service_with_passing_checks: PreOperationalVerificationService,
    ) -> None:
        """Should generate readable summary."""
        result = await service_with_passing_checks.run_verification_checklist()

        summary = result.to_summary()

        assert "Pre-Operational Verification" in summary
        assert "PASSED" in summary
        assert "Duration:" in summary
        assert "Checks:" in summary


class TestStartupIntegration:
    """Tests for startup.py integration."""

    @pytest.mark.asyncio
    async def test_run_pre_operational_verification_passes_with_stubs(self) -> None:
        """Should pass when using default stubs (happy path)."""
        # This uses the actual stub implementations
        # It should pass since stubs return healthy defaults
        await run_pre_operational_verification()
        # If we get here without exception, test passes

    @pytest.mark.asyncio
    async def test_run_pre_operational_verification_post_halt_flag(self) -> None:
        """Should support is_post_halt parameter."""
        # Test with post_halt=True - should still pass with healthy stubs
        await run_pre_operational_verification(is_post_halt=True)
        # If we get here without exception, test passes


class TestEdgeCases:
    """Tests for edge cases in verification."""

    @pytest.mark.asyncio
    async def test_fresh_install_with_no_checkpoints(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should pass for fresh install with no checkpoints."""
        # No checkpoints (fresh install)
        mock_checkpoint_repository.get_all_checkpoints.return_value = []
        mock_checkpoint_repository.get_latest_checkpoint.return_value = None

        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        result = await service.run_verification_checklist()

        # Should pass with warning
        assert result.status == VerificationStatus.PASSED

        checkpoint_check = result.get_check_by_name("checkpoint_anchors")
        assert checkpoint_check is not None
        assert checkpoint_check.passed is True
        assert "fresh install" in checkpoint_check.details.lower()

    @pytest.mark.asyncio
    async def test_halted_system_passes_informational_check(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should pass halt state check even when halted (informational)."""
        # System is halted
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Fork detected"

        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        result = await service.run_verification_checklist()

        # Overall should pass (halt state is informational)
        assert result.status == VerificationStatus.PASSED

        halt_check = result.get_check_by_name("halt_state")
        assert halt_check is not None
        assert halt_check.passed is True  # Informational, not blocking
        assert halt_check.metadata.get("is_halted") is True

    @pytest.mark.asyncio
    async def test_exception_in_check_is_handled(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should handle exceptions in individual checks gracefully."""
        # Make halt checker throw exception
        mock_halt_checker.is_halted.side_effect = Exception("Redis connection failed")

        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        # Should fail but not crash
        assert result.status == VerificationStatus.FAILED

        halt_check = result.get_check_by_name("halt_state")
        assert halt_check is not None
        assert halt_check.passed is False
        assert "Redis connection failed" in halt_check.details


class TestMultipleFailures:
    """Tests for handling multiple failures."""

    @pytest.mark.asyncio
    async def test_all_failures_captured_in_result(
        self,
        mock_hash_verifier: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
        mock_checkpoint_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should capture all failures when multiple checks fail."""
        # Make hash chain fail
        mock_hash_verifier.run_full_scan.return_value = MagicMock(
            passed=False,
            events_scanned=100,
            scan_id="scan-001",
            failed_event_id="event-001",
            expected_hash="expected",
            actual_hash="actual",
        )

        # Make witness pool fail
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=2,
            effective_count=2,
            excluded_witnesses=(),
            is_degraded=True,
        )

        # Make keeper keys fail
        mock_keeper_key_registry.get_all_keys_for_keeper.return_value = []

        service = PreOperationalVerificationService(
            hash_verifier=mock_hash_verifier,
            witness_pool_monitor=mock_witness_pool_monitor,
            keeper_key_registry=mock_keeper_key_registry,
            checkpoint_repository=mock_checkpoint_repository,
            halt_checker=mock_halt_checker,
            event_replicator=mock_event_replicator,
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        assert result.status == VerificationStatus.FAILED
        assert result.failure_count == 3

        # Verify each failure is captured
        failed_names = [c.name for c in result.failed_checks]
        assert "hash_chain" in failed_names
        assert "witness_pool" in failed_names
        assert "keeper_keys" in failed_names
