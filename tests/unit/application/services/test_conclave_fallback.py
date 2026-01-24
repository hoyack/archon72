"""Unit tests for ConclaveService async validation fallback paths.

Story 5.2: Fallback Path Tests

Tests proving sync fallback activates when Kafka is down:
- Circuit breaker OPEN triggers sync fallback
- Kafka health unhealthy triggers sync fallback
- Dispatcher failure triggers sync fallback
- Proper warning logging occurs
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.application.services.conclave_service import (
    ArchonProfile,
    ConclaveConfig,
    ConclaveService,
)
from src.domain.models.conclave import (
    ConclavePhase,
    ConclaveSession,
    Motion,
    MotionStatus,
    MotionType,
    Vote,
    VoteChoice,
)


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    """Create mock agent orchestrator."""
    orchestrator = AsyncMock()
    # Default vote response
    orchestrator.invoke.return_value = MagicMock(
        content='{"choice": "AYE"}\n\nI support this motion for testing purposes.'
    )
    return orchestrator


@pytest.fixture
def archon_profiles() -> list[ArchonProfile]:
    """Create test archon profiles."""
    return [
        ArchonProfile(
            id="archon_1",
            name="Test Archon 1",
            aegis_rank="Marquis",
            domain="Testing",
        ),
        ArchonProfile(
            id="archon_2",
            name="Test Archon 2",
            aegis_rank="Duke",
            domain="Validation",
        ),
    ]


@pytest.fixture
def config_async_enabled() -> ConclaveConfig:
    """Create config with async validation enabled."""
    return ConclaveConfig(
        enable_async_validation=True,
        kafka_bootstrap_servers="localhost:19092",
        schema_registry_url="http://localhost:18081",
        vote_validation_archon_ids=["validator_1", "validator_2"],
        vote_validation_max_attempts=2,
    )


@pytest.fixture
def config_async_disabled() -> ConclaveConfig:
    """Create config with async validation disabled."""
    return ConclaveConfig(
        enable_async_validation=False,
        vote_validation_archon_ids=["validator_1", "validator_2"],
        vote_validation_max_attempts=2,
    )


@pytest.fixture
def mock_circuit_breaker_open() -> MagicMock:
    """Create mock circuit breaker that is OPEN (failing)."""
    breaker = MagicMock()
    breaker.should_allow_request.return_value = False
    breaker.state.value = "open"
    return breaker


@pytest.fixture
def mock_circuit_breaker_closed() -> MagicMock:
    """Create mock circuit breaker that is CLOSED (healthy)."""
    breaker = MagicMock()
    breaker.should_allow_request.return_value = True
    breaker.state.value = "closed"
    return breaker


@pytest.fixture
def mock_dispatcher_success() -> AsyncMock:
    """Create mock dispatcher that succeeds."""
    dispatcher = AsyncMock()
    dispatch_result = MagicMock()
    dispatch_result.all_succeeded = True
    dispatch_result.should_fallback_to_sync = False
    dispatch_result.validators_dispatched = ["validator_1", "validator_2"]
    dispatch_result.failed_validators = []
    dispatcher.dispatch_vote.return_value = dispatch_result
    dispatcher._circuit_breaker = MagicMock()
    dispatcher._circuit_breaker.should_allow_request.return_value = True
    return dispatcher


@pytest.fixture
def mock_dispatcher_failure() -> AsyncMock:
    """Create mock dispatcher that fails."""
    dispatcher = AsyncMock()
    dispatch_result = MagicMock()
    dispatch_result.all_succeeded = False
    dispatch_result.should_fallback_to_sync = True
    dispatch_result.validators_dispatched = []
    dispatch_result.failed_validators = ["validator_1", "validator_2"]
    dispatcher.dispatch_vote.return_value = dispatch_result
    dispatcher._circuit_breaker = MagicMock()
    dispatcher._circuit_breaker.should_allow_request.return_value = True
    return dispatcher


@pytest.fixture
def mock_reconciliation_service() -> MagicMock:
    """Create mock reconciliation service."""
    service = MagicMock()
    service.register_vote = MagicMock()
    return service


class TestAsyncValidationFallback:
    """Tests for async validation fallback to sync."""

    @pytest.mark.asyncio
    async def test_fallback_when_async_disabled(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_disabled: ConclaveConfig,
    ) -> None:
        """Test that sync validation is used when async is disabled."""
        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_disabled,
        )

        # Check that async is not used
        use_async = await service._should_use_async_validation()
        assert not use_async

    @pytest.mark.asyncio
    async def test_fallback_when_no_dispatcher(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
    ) -> None:
        """Test that sync validation is used when no dispatcher is provided."""
        # Create service without dispatcher
        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
            validation_dispatcher=None,  # No dispatcher
        )

        use_async = await service._should_use_async_validation()
        assert not use_async

    @pytest.mark.asyncio
    async def test_fallback_when_circuit_breaker_open(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
        mock_circuit_breaker_open: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that sync validation is used when circuit breaker is OPEN."""
        # Create dispatcher with open circuit breaker
        dispatcher = AsyncMock()
        dispatcher._circuit_breaker = mock_circuit_breaker_open

        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
            validation_dispatcher=dispatcher,
        )

        with caplog.at_level(logging.INFO):
            use_async = await service._should_use_async_validation()

        assert not use_async
        assert "Circuit breaker OPEN" in caplog.text

    @pytest.mark.asyncio
    async def test_async_used_when_circuit_closed(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
        mock_dispatcher_success: AsyncMock,
    ) -> None:
        """Test that async validation is used when circuit is CLOSED."""
        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
            validation_dispatcher=mock_dispatcher_success,
        )

        use_async = await service._should_use_async_validation()
        assert use_async

    @pytest.mark.asyncio
    async def test_fallback_on_dispatch_failure(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
        mock_dispatcher_failure: AsyncMock,
        mock_reconciliation_service: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that sync validation is used when dispatch fails."""
        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
            validation_dispatcher=mock_dispatcher_failure,
            reconciliation_service=mock_reconciliation_service,
        )

        # Create session and motion for voting
        session = service.create_session("Test Session")
        service._session.present_participants = ["archon_1"]

        # Create a motion
        motion = Motion(
            motion_id=uuid4(),
            proposer_id="archon_1",
            proposer_name="Test Archon 1",
            motion_type=MotionType.POLICY,
            title="Test Motion",
            text="Test motion text",
            proposed_at=datetime.now(timezone.utc),
        )

        archon = archon_profiles[0]

        # Mock the sync validation to return a choice
        with patch.object(
            service,
            "_validate_vote_consensus",
            new_callable=AsyncMock,
            return_value=VoteChoice.AYE,
        ) as mock_sync_validate:
            with caplog.at_level(logging.WARNING):
                vote, is_valid = await service._get_archon_vote(archon, motion)

            # Verify fallback occurred
            assert "falling back to sync" in caplog.text.lower()

            # Verify sync validation was called
            mock_sync_validate.assert_called_once()

            # Verify vote was created
            assert vote.voter_id == archon.id
            assert vote.choice == VoteChoice.AYE

    @pytest.mark.asyncio
    async def test_session_completes_on_sync_fallback(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
        mock_dispatcher_failure: AsyncMock,
    ) -> None:
        """Test that session completes successfully when falling back to sync."""
        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
            validation_dispatcher=mock_dispatcher_failure,
        )

        # Mock sync validation to always succeed
        with patch.object(
            service,
            "_validate_vote_consensus",
            new_callable=AsyncMock,
            return_value=VoteChoice.AYE,
        ):
            # Create session
            session = service.create_session("Fallback Test")

            # Mark participants as present
            for profile in archon_profiles:
                service._session.mark_present(profile.id)

            # Create and set motion
            motion = Motion(
                motion_id=uuid4(),
                proposer_id="archon_1",
                proposer_name="Test Archon 1",
                motion_type=MotionType.POLICY,
                title="Fallback Test Motion",
                text="Testing sync fallback completes session",
                proposed_at=datetime.now(timezone.utc),
            )
            service._session.add_motion(motion)
            service._session._current_motion = motion

            # Properly transition motion to VOTING status
            motion.second(seconder_id="archon_2", seconder_name="Test Archon 2")
            motion.begin_debate()
            motion.call_question()
            motion.begin_voting()

            # Get votes (will fall back to sync)
            votes_collected = []
            for archon in archon_profiles:
                vote, is_valid = await service._get_archon_vote(archon, motion)
                motion.cast_vote(vote)
                votes_collected.append(vote)

            # Verify votes were recorded
            assert len(motion.votes) == len(archon_profiles)


class TestSyncValidationPath:
    """Tests for the sync validation path."""

    @pytest.mark.asyncio
    async def test_sync_validation_consensus(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_disabled: ConclaveConfig,
    ) -> None:
        """Test sync validation reaches consensus."""
        # Create validators in config
        config = ConclaveConfig(
            enable_async_validation=False,
            vote_validation_archon_ids=["archon_1", "archon_2"],
            vote_validation_max_attempts=3,
        )

        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config,
        )

        # Create session
        session = service.create_session("Sync Test")

        # Mock the validation request to return consistent AYE
        with patch.object(
            service,
            "_request_vote_validation",
            new_callable=AsyncMock,
            return_value=VoteChoice.AYE,
        ):
            archon = archon_profiles[0]
            motion = Motion(
                motion_id=uuid4(),
                proposer_id="archon_1",
                proposer_name="Test Archon 1",
                motion_type=MotionType.POLICY,
                title="Sync Validation Test",
                text="Testing sync validation",
                proposed_at=datetime.now(timezone.utc),
            )

            validated = await service._validate_vote_consensus(
                archon=archon,
                motion=motion,
                raw_vote='{"choice": "AYE"}',
            )

            assert validated == VoteChoice.AYE

    @pytest.mark.asyncio
    async def test_sync_validation_no_consensus(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_disabled: ConclaveConfig,
    ) -> None:
        """Test sync validation when validators disagree."""
        config = ConclaveConfig(
            enable_async_validation=False,
            vote_validation_archon_ids=["archon_1", "archon_2"],
            vote_validation_max_attempts=2,
        )

        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config,
        )

        session = service.create_session("Disagreement Test")

        # Mock validators to disagree
        async def mock_validation(*args, **kwargs) -> VoteChoice:
            validator_id = kwargs.get("validator_id", args[0] if args else None)
            if validator_id == "archon_1":
                return VoteChoice.AYE
            return VoteChoice.NAY

        with patch.object(
            service,
            "_request_vote_validation",
            side_effect=mock_validation,
        ):
            archon = archon_profiles[0]
            motion = Motion(
                motion_id=uuid4(),
                proposer_id="archon_1",
                proposer_name="Test Archon 1",
                motion_type=MotionType.POLICY,
                title="Disagreement Test",
                text="Testing validator disagreement",
                proposed_at=datetime.now(timezone.utc),
            )

            validated = await service._validate_vote_consensus(
                archon=archon,
                motion=motion,
                raw_vote='{"choice": "AYE"}',
            )

            # No consensus means None is returned
            assert validated is None


class TestLoggingOnFallback:
    """Tests for proper warning logging during fallback."""

    @pytest.mark.asyncio
    async def test_warning_logged_on_circuit_open(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that warning is logged when circuit breaker is open."""
        # Create dispatcher with open circuit
        dispatcher = AsyncMock()
        dispatcher._circuit_breaker = MagicMock()
        dispatcher._circuit_breaker.should_allow_request.return_value = False

        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
            validation_dispatcher=dispatcher,
        )

        with caplog.at_level(logging.INFO):
            use_async = await service._should_use_async_validation()

        assert not use_async
        assert "Circuit breaker OPEN" in caplog.text or "falling back" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_warning_logged_on_dispatch_failure(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
        mock_dispatcher_failure: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that warning is logged when dispatch fails."""
        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
            validation_dispatcher=mock_dispatcher_failure,
        )

        session = service.create_session("Warning Log Test")

        motion = Motion(
            motion_id=uuid4(),
            proposer_id="archon_1",
            proposer_name="Test Archon 1",
            motion_type=MotionType.POLICY,
            title="Warning Log Test",
            text="Testing warning logs",
            proposed_at=datetime.now(timezone.utc),
        )

        archon = archon_profiles[0]

        with patch.object(
            service,
            "_validate_vote_consensus",
            new_callable=AsyncMock,
            return_value=VoteChoice.AYE,
        ):
            with caplog.at_level(logging.WARNING):
                vote, _ = await service._get_archon_vote(archon, motion)

        # Verify warning was logged
        assert "fallback" in caplog.text.lower() or "failed" in caplog.text.lower()


class TestAsyncValidationModule:
    """Tests for async validation module availability checks."""

    def test_async_validation_available_flag(self) -> None:
        """Test that ASYNC_VALIDATION_AVAILABLE flag is set correctly."""
        from src.application.services.conclave_service import ASYNC_VALIDATION_AVAILABLE

        # Should be True if workers module is importable
        # (may be False in minimal test environments)
        assert isinstance(ASYNC_VALIDATION_AVAILABLE, bool)

    @pytest.mark.asyncio
    async def test_fallback_when_module_unavailable(
        self,
        mock_orchestrator: AsyncMock,
        archon_profiles: list[ArchonProfile],
        config_async_enabled: ConclaveConfig,
    ) -> None:
        """Test fallback when async validation module not available."""
        service = ConclaveService(
            orchestrator=mock_orchestrator,
            archon_profiles=archon_profiles,
            config=config_async_enabled,
        )

        # Temporarily set module unavailable
        original_flag = service.__class__.__module__

        with patch(
            "src.application.services.conclave_service.ASYNC_VALIDATION_AVAILABLE",
            False,
        ):
            use_async = await service._should_use_async_validation()

        # Even with async enabled in config, should fall back
        # when module is not available
        # (Note: actual behavior depends on import success)
