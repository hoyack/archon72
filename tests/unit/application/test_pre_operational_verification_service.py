"""Unit tests for PreOperationalVerificationService (Story 8.5, FR146, NFR35).

Tests for:
- Complete verification checklist execution
- Individual verification checks
- Bypass logic
- Post-halt stringent verification
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.application.services.pre_operational_verification_service import (
    PreOperationalVerificationService,
)
from src.domain.errors.pre_operational import BypassNotAllowedError
from src.domain.models.verification_result import (
    VerificationStatus,
)


@pytest.fixture
def mock_hash_verifier() -> AsyncMock:
    """Create mock hash verifier."""
    mock = AsyncMock()
    # Default to passing scan
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
    """Create mock witness pool monitor."""
    mock = AsyncMock()
    # Default to healthy pool
    mock.get_pool_status.return_value = MagicMock(
        available_count=12,
        effective_count=12,
        excluded_witnesses=(),
        is_degraded=False,
    )
    return mock


@pytest.fixture
def mock_keeper_key_registry() -> AsyncMock:
    """Create mock keeper key registry."""
    mock = AsyncMock()
    # Default to having active keys
    now = datetime.now(timezone.utc)
    mock.get_all_keys_for_keeper.return_value = [
        MagicMock(
            key_id="key-001",
            keeper_id="KEEPER:primary",
            active_from=now - timedelta(days=30),
            active_until=None,  # Currently active
        )
    ]
    return mock


@pytest.fixture
def mock_checkpoint_repository() -> AsyncMock:
    """Create mock checkpoint repository."""
    mock = AsyncMock()
    # Default to having checkpoints
    now = datetime.now(timezone.utc)
    checkpoint = MagicMock(
        checkpoint_id=uuid4(),
        event_sequence=1000,
        timestamp=now - timedelta(hours=1),  # Recent checkpoint
        anchor_hash="abc123",
        anchor_type="periodic",
    )
    mock.get_all_checkpoints.return_value = [checkpoint]
    mock.get_latest_checkpoint.return_value = checkpoint
    return mock


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker."""
    mock = AsyncMock()
    # Default to not halted
    mock.is_halted.return_value = False
    mock.get_halt_reason.return_value = None
    return mock


@pytest.fixture
def mock_event_replicator() -> AsyncMock:
    """Create mock event replicator."""
    mock = AsyncMock()
    # Default to healthy replicas
    mock.verify_replicas.return_value = MagicMock(
        is_valid=True,
        head_hash_match=True,
        signature_valid=True,
        schema_version_match=True,
        errors=(),
    )
    return mock


@pytest.fixture
def service(
    mock_hash_verifier: AsyncMock,
    mock_witness_pool_monitor: AsyncMock,
    mock_keeper_key_registry: AsyncMock,
    mock_checkpoint_repository: AsyncMock,
    mock_halt_checker: AsyncMock,
    mock_event_replicator: AsyncMock,
) -> PreOperationalVerificationService:
    """Create service with all mocked dependencies."""
    return PreOperationalVerificationService(
        hash_verifier=mock_hash_verifier,
        witness_pool_monitor=mock_witness_pool_monitor,
        keeper_key_registry=mock_keeper_key_registry,
        checkpoint_repository=mock_checkpoint_repository,
        halt_checker=mock_halt_checker,
        event_replicator=mock_event_replicator,
    )


class TestVerificationChecklist:
    """Tests for complete verification checklist."""

    @pytest.mark.asyncio
    async def test_all_checks_pass_returns_passed(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should return PASSED when all checks pass."""
        result = await service.run_verification_checklist()

        assert result.status == VerificationStatus.PASSED
        assert result.check_count == 6  # All 6 checks
        assert result.failure_count == 0
        assert result.bypass_reason is None

    @pytest.mark.asyncio
    async def test_single_failure_returns_failed(
        self,
        service: PreOperationalVerificationService,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Should return FAILED when any check fails."""
        # Make witness pool insufficient
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=4,
            effective_count=4,
            excluded_witnesses=(),
            is_degraded=True,
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        assert result.status == VerificationStatus.FAILED
        assert result.failure_count == 1
        failed = result.get_check_by_name("witness_pool")
        assert failed is not None
        assert not failed.passed

    @pytest.mark.asyncio
    async def test_multiple_failures_all_captured(
        self,
        service: PreOperationalVerificationService,
        mock_witness_pool_monitor: AsyncMock,
        mock_keeper_key_registry: AsyncMock,
    ) -> None:
        """Should capture all failures when multiple checks fail."""
        # Make witness pool insufficient
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=4,
            effective_count=4,
            excluded_witnesses=(),
            is_degraded=True,
        )
        # Make keeper keys return no active keys
        mock_keeper_key_registry.get_all_keys_for_keeper.return_value = []

        result = await service.run_verification_checklist(allow_bypass=False)

        assert result.status == VerificationStatus.FAILED
        assert result.failure_count == 2
        assert result.get_check_by_name("witness_pool") is not None
        assert result.get_check_by_name("keeper_keys") is not None


class TestHaltStateCheck:
    """Tests for halt state verification check."""

    @pytest.mark.asyncio
    async def test_not_halted_passes(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should pass when system is not halted."""
        result = await service.run_verification_checklist()

        halt_check = result.get_check_by_name("halt_state")
        assert halt_check is not None
        assert halt_check.passed is True
        assert "not halted" in halt_check.details

    @pytest.mark.asyncio
    async def test_halted_still_passes_but_flags(
        self,
        service: PreOperationalVerificationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Should pass but flag when system is halted (informational)."""
        mock_halt_checker.is_halted.return_value = True
        mock_halt_checker.get_halt_reason.return_value = "Fork detected"

        result = await service.run_verification_checklist()

        halt_check = result.get_check_by_name("halt_state")
        assert halt_check is not None
        assert halt_check.passed is True  # Informational, doesn't fail verification
        assert "halted" in halt_check.details
        assert halt_check.metadata.get("is_halted") is True


class TestHashChainCheck:
    """Tests for hash chain verification check."""

    @pytest.mark.asyncio
    async def test_valid_chain_passes(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should pass when hash chain is valid."""
        result = await service.run_verification_checklist()

        chain_check = result.get_check_by_name("hash_chain")
        assert chain_check is not None
        assert chain_check.passed is True

    @pytest.mark.asyncio
    async def test_corrupted_chain_fails(
        self,
        service: PreOperationalVerificationService,
        mock_hash_verifier: AsyncMock,
    ) -> None:
        """Should fail when hash chain is corrupted."""
        mock_hash_verifier.run_full_scan.return_value = MagicMock(
            passed=False,
            events_scanned=500,
            scan_id="scan-002",
            failed_event_id="event-456",
            expected_hash="abc123",
            actual_hash="xyz789",
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        chain_check = result.get_check_by_name("hash_chain")
        assert chain_check is not None
        assert chain_check.passed is False
        assert "mismatch" in chain_check.details.lower()

    @pytest.mark.asyncio
    async def test_post_halt_verifies_full_chain(
        self,
        service: PreOperationalVerificationService,
        mock_hash_verifier: AsyncMock,
    ) -> None:
        """Should verify full chain in post-halt mode."""
        await service.run_verification_checklist(is_post_halt=True)

        # Should call with max_events=None for full verification
        mock_hash_verifier.run_full_scan.assert_called_once_with(max_events=None)

    @pytest.mark.asyncio
    async def test_normal_verifies_limited_events(
        self,
        service: PreOperationalVerificationService,
        mock_hash_verifier: AsyncMock,
    ) -> None:
        """Should verify limited events in normal mode."""
        await service.run_verification_checklist(is_post_halt=False)

        # Should call with max_events limit
        mock_hash_verifier.run_full_scan.assert_called_once()
        call_args = mock_hash_verifier.run_full_scan.call_args
        assert call_args.kwargs.get("max_events") is not None


class TestWitnessPoolCheck:
    """Tests for witness pool verification check."""

    @pytest.mark.asyncio
    async def test_adequate_pool_passes(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should pass when pool has sufficient witnesses."""
        result = await service.run_verification_checklist()

        pool_check = result.get_check_by_name("witness_pool")
        assert pool_check is not None
        assert pool_check.passed is True

    @pytest.mark.asyncio
    async def test_insufficient_pool_fails(
        self,
        service: PreOperationalVerificationService,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Should fail when pool has insufficient witnesses."""
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=5,
            effective_count=5,
            excluded_witnesses=(),
            is_degraded=True,
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        pool_check = result.get_check_by_name("witness_pool")
        assert pool_check is not None
        assert pool_check.passed is False
        assert "minimum" in pool_check.details.lower()


class TestKeeperKeysCheck:
    """Tests for Keeper key verification check."""

    @pytest.mark.asyncio
    async def test_active_keys_pass(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should pass when active Keeper keys exist."""
        result = await service.run_verification_checklist()

        keys_check = result.get_check_by_name("keeper_keys")
        assert keys_check is not None
        assert keys_check.passed is True

    @pytest.mark.asyncio
    async def test_no_active_keys_fails(
        self,
        service: PreOperationalVerificationService,
        mock_keeper_key_registry: AsyncMock,
    ) -> None:
        """Should fail when no active Keeper keys exist."""
        mock_keeper_key_registry.get_all_keys_for_keeper.return_value = []

        result = await service.run_verification_checklist(allow_bypass=False)

        keys_check = result.get_check_by_name("keeper_keys")
        assert keys_check is not None
        assert keys_check.passed is False


class TestCheckpointAnchorsCheck:
    """Tests for checkpoint anchors verification check."""

    @pytest.mark.asyncio
    async def test_recent_checkpoint_passes(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should pass when recent checkpoint exists."""
        result = await service.run_verification_checklist()

        checkpoint_check = result.get_check_by_name("checkpoint_anchors")
        assert checkpoint_check is not None
        assert checkpoint_check.passed is True

    @pytest.mark.asyncio
    async def test_fresh_install_passes_with_warning(
        self,
        service: PreOperationalVerificationService,
        mock_checkpoint_repository: AsyncMock,
    ) -> None:
        """Should pass for fresh install with no checkpoints."""
        mock_checkpoint_repository.get_all_checkpoints.return_value = []
        mock_checkpoint_repository.get_latest_checkpoint.return_value = None

        result = await service.run_verification_checklist()

        checkpoint_check = result.get_check_by_name("checkpoint_anchors")
        assert checkpoint_check is not None
        assert checkpoint_check.passed is True
        assert "fresh install" in checkpoint_check.details.lower()

    @pytest.mark.asyncio
    async def test_stale_checkpoint_fails(
        self,
        service: PreOperationalVerificationService,
        mock_checkpoint_repository: AsyncMock,
    ) -> None:
        """Should fail when checkpoint is too old."""
        now = datetime.now(timezone.utc)
        stale_checkpoint = MagicMock(
            checkpoint_id=uuid4(),
            event_sequence=1000,
            timestamp=now - timedelta(days=10),  # 10 days old (> 7 day limit)
            anchor_hash="abc123",
            anchor_type="periodic",
        )
        mock_checkpoint_repository.get_all_checkpoints.return_value = [stale_checkpoint]
        mock_checkpoint_repository.get_latest_checkpoint.return_value = stale_checkpoint

        result = await service.run_verification_checklist(allow_bypass=False)

        checkpoint_check = result.get_check_by_name("checkpoint_anchors")
        assert checkpoint_check is not None
        assert checkpoint_check.passed is False
        assert "hours old" in checkpoint_check.details


class TestReplicaSyncCheck:
    """Tests for replica sync verification check."""

    @pytest.mark.asyncio
    async def test_synced_replicas_pass(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should pass when replicas are in sync."""
        result = await service.run_verification_checklist()

        sync_check = result.get_check_by_name("replica_sync")
        assert sync_check is not None
        assert sync_check.passed is True

    @pytest.mark.asyncio
    async def test_out_of_sync_replicas_fail(
        self,
        service: PreOperationalVerificationService,
        mock_event_replicator: AsyncMock,
    ) -> None:
        """Should fail when replicas are out of sync."""
        mock_event_replicator.verify_replicas.return_value = MagicMock(
            is_valid=False,
            head_hash_match=False,
            signature_valid=True,
            schema_version_match=True,
            errors=("Replica lag exceeds threshold",),
        )

        result = await service.run_verification_checklist(allow_bypass=False)

        sync_check = result.get_check_by_name("replica_sync")
        assert sync_check is not None
        assert sync_check.passed is False


class TestBypassLogic:
    """Tests for verification bypass logic."""

    @pytest.fixture(autouse=True)
    def reset_bypass_tracking(self) -> None:
        """Reset bypass tracking before each test."""
        PreOperationalVerificationService.reset_bypass_tracking()

    @pytest.mark.asyncio
    async def test_bypass_allowed_when_enabled(
        self,
        service: PreOperationalVerificationService,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Should allow bypass when enabled and within limits."""
        # Make a check fail
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=4,
            effective_count=4,
            excluded_witnesses=(),
            is_degraded=True,
        )

        with patch.dict(
            "os.environ",
            {"VERIFICATION_BYPASS_ENABLED": "true"},
        ):
            # Need to re-import to pick up env var
            from src.application.services import pre_operational_verification_service

            original_enabled = (
                pre_operational_verification_service.VERIFICATION_BYPASS_ENABLED
            )
            pre_operational_verification_service.VERIFICATION_BYPASS_ENABLED = True

            try:
                result = await service.run_verification_checklist(allow_bypass=True)
                assert result.status == VerificationStatus.BYPASSED
                assert result.bypass_reason is not None
                assert result.bypass_count == 1
            finally:
                pre_operational_verification_service.VERIFICATION_BYPASS_ENABLED = (
                    original_enabled
                )

    @pytest.mark.asyncio
    async def test_bypass_not_allowed_post_halt(
        self,
        service: PreOperationalVerificationService,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Should never allow bypass post-halt."""
        # Make a check fail
        mock_witness_pool_monitor.get_pool_status.return_value = MagicMock(
            available_count=4,
            effective_count=4,
            excluded_witnesses=(),
            is_degraded=True,
        )

        result = await service.run_verification_checklist(
            is_post_halt=True,
            allow_bypass=True,
        )

        assert result.status == VerificationStatus.FAILED
        assert result.bypass_reason is None

    def test_check_bypass_allowed_raises_for_post_halt(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should raise BypassNotAllowedError for post-halt."""
        with pytest.raises(BypassNotAllowedError) as exc_info:
            service.check_bypass_allowed(is_post_halt=True)

        assert exc_info.value.is_post_halt is True
        assert "post-halt" in str(exc_info.value).lower()


class TestPostHaltVerification:
    """Tests for post-halt stringent verification."""

    @pytest.mark.asyncio
    async def test_post_halt_flag_set_in_result(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should set is_post_halt flag in result."""
        result = await service.run_verification_checklist(is_post_halt=True)

        assert result.is_post_halt is True

    @pytest.mark.asyncio
    async def test_post_halt_logs_mode(
        self,
        service: PreOperationalVerificationService,
    ) -> None:
        """Should log post-halt verification mode."""
        result = await service.run_verification_checklist(is_post_halt=True)

        # Check metadata indicates post-halt
        hash_check = result.get_check_by_name("hash_chain")
        assert hash_check is not None
        assert hash_check.metadata.get("is_post_halt") is True


class TestErrorHandling:
    """Tests for error handling in verification checks."""

    @pytest.mark.asyncio
    async def test_hash_verifier_exception_captured(
        self,
        service: PreOperationalVerificationService,
        mock_hash_verifier: AsyncMock,
    ) -> None:
        """Should capture exception from hash verifier."""
        mock_hash_verifier.run_full_scan.side_effect = Exception("Connection error")

        result = await service.run_verification_checklist(allow_bypass=False)

        hash_check = result.get_check_by_name("hash_chain")
        assert hash_check is not None
        assert hash_check.passed is False
        assert "connection error" in hash_check.details.lower()

    @pytest.mark.asyncio
    async def test_witness_pool_exception_captured(
        self,
        service: PreOperationalVerificationService,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Should capture exception from witness pool monitor."""
        mock_witness_pool_monitor.get_pool_status.side_effect = Exception("Timeout")

        result = await service.run_verification_checklist(allow_bypass=False)

        pool_check = result.get_check_by_name("witness_pool")
        assert pool_check is not None
        assert pool_check.passed is False

    @pytest.mark.asyncio
    async def test_halt_checker_exception_captured(
        self,
        service: PreOperationalVerificationService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Should capture exception from halt checker."""
        mock_halt_checker.is_halted.side_effect = Exception("Redis down")

        result = await service.run_verification_checklist(allow_bypass=False)

        halt_check = result.get_check_by_name("halt_state")
        assert halt_check is not None
        assert halt_check.passed is False


class TestResetBypassTracking:
    """Tests for bypass tracking reset."""

    def test_reset_clears_timestamps(self) -> None:
        """Should clear all bypass timestamps."""
        # Add some timestamps manually
        PreOperationalVerificationService._bypass_timestamps = [1.0, 2.0, 3.0]

        PreOperationalVerificationService.reset_bypass_tracking()

        assert PreOperationalVerificationService._bypass_timestamps == []
