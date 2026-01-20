"""Unit tests for AcknowledgmentExecutionService.

Story: 3.2 - Acknowledgment Execution Service
FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.acknowledgment import (
    InvalidArchonCountError,
    InvalidReferencePetitionError,
    PetitionNotFoundError,
    PetitionNotInDeliberatingStateError,
)
from src.domain.models.acknowledgment_reason import (
    AcknowledgmentReasonCode,
    RationaleRequiredError,
    ReferenceRequiredError,
)
from src.infrastructure.stubs.acknowledgment_execution_stub import (
    AcknowledgmentExecutionStub,
)


@pytest.fixture
def stub() -> AcknowledgmentExecutionStub:
    """Create a fresh stub for each test."""
    return AcknowledgmentExecutionStub()


@pytest.fixture
def deliberating_petition():
    """Create a petition in DELIBERATING state."""
    from src.domain.models.petition_submission import (
        PetitionState,
        PetitionSubmission,
        PetitionType,
    )

    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition",
        submitter_id=uuid4(),
        content_hash=b"a" * 32,
        realm="TECH",
        state=PetitionState.DELIBERATING,
    )


@pytest.fixture
def pending_petition():
    """Create a petition in RECEIVED state (not ready for acknowledgment)."""
    from src.domain.models.petition_submission import (
        PetitionState,
        PetitionSubmission,
        PetitionType,
    )

    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Pending petition",
        submitter_id=uuid4(),
        content_hash=b"b" * 32,
        realm="TECH",
        state=PetitionState.RECEIVED,
    )


class TestExecuteHappyPath:
    """Tests for successful acknowledgment execution."""

    @pytest.mark.asyncio
    async def test_execute_noted_success(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """Successfully acknowledge petition with NOTED reason."""
        stub.add_petition(deliberating_petition)

        ack = await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert ack.petition_id == deliberating_petition.id
        assert ack.reason_code == AcknowledgmentReasonCode.NOTED
        assert len(ack.acknowledging_archon_ids) == 2
        assert stub.was_executed(deliberating_petition.id)

    @pytest.mark.asyncio
    async def test_execute_addressed_success(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """Successfully acknowledge with ADDRESSED reason."""
        stub.add_petition(deliberating_petition)

        ack = await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.ADDRESSED,
            acknowledging_archon_ids=(15, 42, 67),
        )

        assert ack.reason_code == AcknowledgmentReasonCode.ADDRESSED
        assert ack.is_unanimous is True

    @pytest.mark.asyncio
    async def test_execute_refused_with_rationale(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """Successfully acknowledge with REFUSED and rationale per FR-3.3."""
        stub.add_petition(deliberating_petition)

        ack = await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.REFUSED,
            acknowledging_archon_ids=(15, 42),
            rationale="Violates community guidelines section 4.2",
        )

        assert ack.reason_code == AcknowledgmentReasonCode.REFUSED
        assert ack.rationale == "Violates community guidelines section 4.2"

    @pytest.mark.asyncio
    async def test_execute_duplicate_with_reference(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """Successfully acknowledge with DUPLICATE and reference per FR-3.4."""
        # Add reference petition
        reference_petition = deliberating_petition
        stub.add_petition(reference_petition)

        # Create new petition to acknowledge as duplicate
        from src.domain.models.petition_submission import (
            PetitionState,
            PetitionSubmission,
            PetitionType,
        )

        new_petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Duplicate petition",
            submitter_id=uuid4(),
            content_hash=b"c" * 32,
            realm="TECH",
            state=PetitionState.DELIBERATING,
        )
        stub.add_petition(new_petition)

        ack = await stub.execute(
            petition_id=new_petition.id,
            reason_code=AcknowledgmentReasonCode.DUPLICATE,
            acknowledging_archon_ids=(15, 42),
            reference_petition_id=reference_petition.id,
        )

        assert ack.reason_code == AcknowledgmentReasonCode.DUPLICATE
        assert ack.reference_petition_id == reference_petition.id


class TestValidationErrors:
    """Tests for validation error handling."""

    @pytest.mark.asyncio
    async def test_petition_not_found(self, stub: AcknowledgmentExecutionStub) -> None:
        """PetitionNotFoundError when petition doesn't exist."""
        with pytest.raises(PetitionNotFoundError) as exc_info:
            await stub.execute(
                petition_id=uuid4(),  # Non-existent
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
            )
        assert exc_info.value.petition_id is not None

    @pytest.mark.asyncio
    async def test_petition_not_in_deliberating_state(
        self, stub: AcknowledgmentExecutionStub, pending_petition
    ) -> None:
        """PetitionNotInDeliberatingStateError when not DELIBERATING."""
        stub.add_petition(pending_petition)

        with pytest.raises(PetitionNotInDeliberatingStateError) as exc_info:
            await stub.execute(
                petition_id=pending_petition.id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
            )
        assert exc_info.value.current_state == "RECEIVED"

    @pytest.mark.asyncio
    async def test_insufficient_archons(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """InvalidArchonCountError when less than 2 archons."""
        stub.add_petition(deliberating_petition)

        with pytest.raises(InvalidArchonCountError) as exc_info:
            await stub.execute(
                petition_id=deliberating_petition.id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15,),  # Only 1
            )
        assert exc_info.value.actual_count == 1

    @pytest.mark.asyncio
    async def test_refused_without_rationale(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """RationaleRequiredError for REFUSED without rationale."""
        stub.add_petition(deliberating_petition)

        with pytest.raises(RationaleRequiredError):
            await stub.execute(
                petition_id=deliberating_petition.id,
                reason_code=AcknowledgmentReasonCode.REFUSED,
                acknowledging_archon_ids=(15, 42),
                rationale=None,
            )

    @pytest.mark.asyncio
    async def test_no_action_warranted_without_rationale(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """RationaleRequiredError for NO_ACTION_WARRANTED without rationale."""
        stub.add_petition(deliberating_petition)

        with pytest.raises(RationaleRequiredError):
            await stub.execute(
                petition_id=deliberating_petition.id,
                reason_code=AcknowledgmentReasonCode.NO_ACTION_WARRANTED,
                acknowledging_archon_ids=(15, 42),
            )

    @pytest.mark.asyncio
    async def test_duplicate_without_reference(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """ReferenceRequiredError for DUPLICATE without reference."""
        stub.add_petition(deliberating_petition)

        with pytest.raises(ReferenceRequiredError):
            await stub.execute(
                petition_id=deliberating_petition.id,
                reason_code=AcknowledgmentReasonCode.DUPLICATE,
                acknowledging_archon_ids=(15, 42),
            )

    @pytest.mark.asyncio
    async def test_duplicate_with_invalid_reference(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """InvalidReferencePetitionError when reference doesn't exist."""
        stub.add_petition(deliberating_petition)

        with pytest.raises(InvalidReferencePetitionError) as exc_info:
            await stub.execute(
                petition_id=deliberating_petition.id,
                reason_code=AcknowledgmentReasonCode.DUPLICATE,
                acknowledging_archon_ids=(15, 42),
                reference_petition_id=uuid4(),  # Non-existent
            )
        assert exc_info.value.petition_id == deliberating_petition.id


class TestIdempotency:
    """Tests for idempotent execution."""

    @pytest.mark.asyncio
    async def test_duplicate_execution_returns_existing(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """Re-executing acknowledgment returns existing record."""
        stub.add_petition(deliberating_petition)

        # First execution
        ack1 = await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        # Second execution (same petition)
        ack2 = await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert ack1.id == ack2.id
        assert stub.get_execution_count() == 2


class TestEventEmission:
    """Tests for event emission (CT-12)."""

    @pytest.mark.asyncio
    async def test_event_emitted_on_success(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """PetitionAcknowledged event emitted on success."""
        stub.add_petition(deliberating_petition)

        await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        events = stub.get_emitted_events()
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "petition.fate.acknowledged"
        assert event["petition_id"] == str(deliberating_petition.id)
        assert event["reason_code"] == "NOTED"

    @pytest.mark.asyncio
    async def test_event_includes_witness_hash(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """Event includes witness hash for CT-12 compliance."""
        stub.add_petition(deliberating_petition)

        await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        event = stub.get_last_emitted_event()
        assert "witness_hash" in event
        assert event["witness_hash"].startswith("blake3:")

    @pytest.mark.asyncio
    async def test_event_includes_archon_ids(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """Event includes acknowledging archon IDs."""
        stub.add_petition(deliberating_petition)

        await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42, 67),
        )

        event = stub.get_last_emitted_event()
        assert event["acknowledging_archon_ids"] == [15, 42, 67]


class TestHashGenerationFailure:
    """Tests for hash generation error handling."""

    @pytest.mark.asyncio
    async def test_hash_generation_failure(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """WitnessHashGenerationError when hash fails."""
        stub.add_petition(deliberating_petition)
        stub.set_fail_hash_generation(True, "Hash service unavailable")

        from src.domain.errors.acknowledgment import WitnessHashGenerationError

        with pytest.raises(WitnessHashGenerationError) as exc_info:
            await stub.execute(
                petition_id=deliberating_petition.id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
            )
        assert "Hash service unavailable" in str(exc_info.value)


class TestStubHelpers:
    """Tests for stub helper methods."""

    @pytest.mark.asyncio
    async def test_was_executed(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """was_executed returns correct status."""
        stub.add_petition(deliberating_petition)

        assert stub.was_executed(deliberating_petition.id) is False

        await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert stub.was_executed(deliberating_petition.id) is True

    @pytest.mark.asyncio
    async def test_get_acknowledgment(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """get_acknowledgment retrieves by ID."""
        stub.add_petition(deliberating_petition)

        ack = await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        retrieved = await stub.get_acknowledgment(ack.id)
        assert retrieved is not None
        assert retrieved.id == ack.id

    @pytest.mark.asyncio
    async def test_get_acknowledgment_by_petition(
        self, stub: AcknowledgmentExecutionStub, deliberating_petition
    ) -> None:
        """get_acknowledgment_by_petition retrieves by petition ID."""
        stub.add_petition(deliberating_petition)

        await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        retrieved = await stub.get_acknowledgment_by_petition(deliberating_petition.id)
        assert retrieved is not None
        assert retrieved.petition_id == deliberating_petition.id

    def test_clear(self, stub: AcknowledgmentExecutionStub) -> None:
        """clear resets all state."""
        stub._execution_count = 5
        stub.clear()
        assert stub.get_execution_count() == 0
        assert len(stub.get_emitted_events()) == 0


class TestDwellTimeEnforcement:
    """Tests for minimum dwell time enforcement (FR-3.5, Story 3.5).

    FR-3.5: System SHALL enforce minimum dwell time before ACKNOWLEDGE
    to ensure petitions receive adequate deliberation time.
    """

    @pytest.fixture
    def dwell_config(self):
        """Create a config with 30 second dwell time for testing."""
        from src.config.deliberation_config import DeliberationConfig

        return DeliberationConfig(
            min_dwell_seconds=30,  # 30 second dwell time
            timeout_seconds=300,
            max_rounds=3,
        )

    @pytest.fixture
    def no_dwell_config(self):
        """Create a config with dwell time disabled (0)."""
        from src.config.deliberation_config import DeliberationConfig

        return DeliberationConfig(
            min_dwell_seconds=0,  # Disabled
            timeout_seconds=300,
            max_rounds=3,
        )

    @pytest.fixture
    def deliberating_petition_with_session(self):
        """Create a petition with an old enough session (dwell time elapsed)."""
        from dataclasses import replace
        from datetime import timedelta

        from src.domain.models.deliberation_session import DeliberationSession
        from src.domain.models.petition_submission import (
            PetitionState,
            PetitionSubmission,
            PetitionType,
        )

        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Dwell petition",
            submitter_id=uuid4(),
            content_hash=b"d" * 32,
            realm="TECH",
            state=PetitionState.DELIBERATING,
        )

        # Session started 60 seconds ago (dwell time has elapsed)
        session = DeliberationSession.create(
            petition_id=petition.id,
            archon_ids=(15, 42, 67),
        )
        session = replace(
            session,
            created_at=datetime.now(timezone.utc) - timedelta(seconds=60),
        )

        return petition, session

    @pytest.fixture
    def recent_petition_with_session(self):
        """Create a petition with a recent session (dwell time NOT elapsed)."""
        from dataclasses import replace
        from datetime import timedelta

        from src.domain.models.deliberation_session import DeliberationSession
        from src.domain.models.petition_submission import (
            PetitionState,
            PetitionSubmission,
            PetitionType,
        )

        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Recent petition",
            submitter_id=uuid4(),
            content_hash=b"e" * 32,
            realm="TECH",
            state=PetitionState.DELIBERATING,
        )

        # Session started 5 seconds ago (dwell time has NOT elapsed)
        session = DeliberationSession.create(
            petition_id=petition.id,
            archon_ids=(15, 42, 67),
        )
        session = replace(
            session,
            created_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )

        return petition, session

    @pytest.mark.asyncio
    async def test_dwell_time_not_elapsed_raises_error(
        self, dwell_config, recent_petition_with_session
    ) -> None:
        """DwellTimeNotElapsedError when dwell time has not elapsed (FR-3.5)."""
        from src.domain.errors.acknowledgment import DwellTimeNotElapsedError

        petition, session = recent_petition_with_session

        stub = AcknowledgmentExecutionStub(
            config=dwell_config,
            enforce_dwell_time=True,
        )
        stub.add_petition(petition, session)

        with pytest.raises(DwellTimeNotElapsedError) as exc_info:
            await stub.execute(
                petition_id=petition.id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
            )

        assert exc_info.value.petition_id == petition.id
        assert exc_info.value.min_dwell_seconds == 30
        assert exc_info.value.elapsed_seconds < 30
        assert exc_info.value.remaining_seconds > 0

    @pytest.mark.asyncio
    async def test_dwell_time_elapsed_allows_acknowledgment(
        self, dwell_config, deliberating_petition_with_session
    ) -> None:
        """Acknowledgment succeeds when dwell time has elapsed."""
        petition, session = deliberating_petition_with_session

        stub = AcknowledgmentExecutionStub(
            config=dwell_config,
            enforce_dwell_time=True,
        )
        stub.add_petition(petition, session)

        ack = await stub.execute(
            petition_id=petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert ack.petition_id == petition.id
        assert stub.was_executed(petition.id)

    @pytest.mark.asyncio
    async def test_dwell_time_disabled_skips_check(
        self, no_dwell_config, recent_petition_with_session
    ) -> None:
        """Dwell time check skipped when config is 0 (disabled)."""
        petition, session = recent_petition_with_session

        stub = AcknowledgmentExecutionStub(
            config=no_dwell_config,
            enforce_dwell_time=True,  # Even with enforcement, 0 disables
        )
        stub.add_petition(petition, session)

        # Should succeed even though session is very recent
        ack = await stub.execute(
            petition_id=petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert ack.petition_id == petition.id

    @pytest.mark.asyncio
    async def test_enforcement_disabled_skips_check(
        self, dwell_config, recent_petition_with_session
    ) -> None:
        """Dwell time check skipped when enforce_dwell_time=False."""
        petition, session = recent_petition_with_session

        stub = AcknowledgmentExecutionStub(
            config=dwell_config,
            enforce_dwell_time=False,  # Explicitly disabled
        )
        stub.add_petition(petition, session)

        # Should succeed even though dwell time hasn't elapsed
        ack = await stub.execute(
            petition_id=petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert ack.petition_id == petition.id

    @pytest.mark.asyncio
    async def test_missing_session_raises_error(
        self, dwell_config, deliberating_petition
    ) -> None:
        """DeliberationSessionNotFoundError when session not found."""
        from src.domain.errors.acknowledgment import DeliberationSessionNotFoundError

        stub = AcknowledgmentExecutionStub(
            config=dwell_config,
            enforce_dwell_time=True,
        )
        # Add petition WITHOUT session
        stub.add_petition(deliberating_petition)

        with pytest.raises(DeliberationSessionNotFoundError) as exc_info:
            await stub.execute(
                petition_id=deliberating_petition.id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
            )

        assert exc_info.value.petition_id == deliberating_petition.id

    @pytest.mark.asyncio
    async def test_dwell_error_includes_remaining_time(
        self, dwell_config, recent_petition_with_session
    ) -> None:
        """DwellTimeNotElapsedError includes remaining time information."""
        from src.domain.errors.acknowledgment import DwellTimeNotElapsedError

        petition, session = recent_petition_with_session

        stub = AcknowledgmentExecutionStub(
            config=dwell_config,
            enforce_dwell_time=True,
        )
        stub.add_petition(petition, session)

        with pytest.raises(DwellTimeNotElapsedError) as exc_info:
            await stub.execute(
                petition_id=petition.id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
            )

        # Check remaining_timedelta property
        remaining_td = exc_info.value.remaining_timedelta
        assert remaining_td.total_seconds() > 0
        assert remaining_td.total_seconds() < 30

    @pytest.mark.asyncio
    async def test_add_session_separately(
        self, dwell_config, deliberating_petition
    ) -> None:
        """Session can be added via add_session() after add_petition()."""
        from dataclasses import replace
        from datetime import timedelta

        from src.domain.models.deliberation_session import DeliberationSession

        stub = AcknowledgmentExecutionStub(
            config=dwell_config,
            enforce_dwell_time=True,
        )

        # Add petition first
        stub.add_petition(deliberating_petition)

        # Then add session (60 seconds old = dwell time elapsed)
        session = DeliberationSession.create(
            petition_id=deliberating_petition.id,
            archon_ids=(15, 42, 67),
        )
        session = replace(
            session,
            created_at=datetime.now(timezone.utc) - timedelta(seconds=60),
        )
        stub.add_session(deliberating_petition.id, session)

        # Should succeed
        ack = await stub.execute(
            petition_id=deliberating_petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert ack.petition_id == deliberating_petition.id
