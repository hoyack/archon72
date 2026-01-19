"""Unit tests for PetitionSubmissionRepositoryStub (Story 0.3, AC3, Story 1.6).

Tests verify the stub implementation works correctly for testing,
including atomic CAS fate assignment (FR-2.4, NFR-3.2).
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from src.domain.errors.concurrent_modification import ConcurrentModificationError
from src.domain.errors.state_transition import (
    InvalidStateTransitionError,
    PetitionAlreadyFatedError,
)
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


def _make_submission(
    submission_id: uuid.UUID | None = None,
    text: str = "Test petition content",
    state: PetitionState = PetitionState.RECEIVED,
    petition_type: PetitionType = PetitionType.CESSATION,
    realm: str = "cessation-realm",
) -> PetitionSubmission:
    """Helper to create a petition submission for testing."""
    return PetitionSubmission(
        id=submission_id or uuid.uuid4(),
        type=petition_type,
        text=text,
        state=state,
        realm=realm,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestPetitionSubmissionRepositoryStub:
    """Tests for PetitionSubmissionRepositoryStub implementation."""

    @pytest.fixture
    def stub(self) -> PetitionSubmissionRepositoryStub:
        """Create a fresh stub instance for each test."""
        return PetitionSubmissionRepositoryStub()

    @pytest.mark.asyncio
    async def test_save_stores_submission(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Verify save stores submission that can be retrieved."""
        submission = _make_submission()
        await stub.save(submission)
        retrieved = await stub.get(submission.id)
        assert retrieved is not None
        assert retrieved.id == submission.id
        assert retrieved.text == submission.text

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Verify get returns None for non-existent ID."""
        result = await stub.get(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_state_filters_correctly(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Verify list_by_state filters by state."""
        received = _make_submission(state=PetitionState.RECEIVED)
        deliberating = _make_submission(state=PetitionState.DELIBERATING)
        acknowledged = _make_submission(state=PetitionState.ACKNOWLEDGED)

        await stub.save(received)
        await stub.save(deliberating)
        await stub.save(acknowledged)

        results, total = await stub.list_by_state(PetitionState.RECEIVED)
        assert total == 1
        assert len(results) == 1
        assert results[0].id == received.id

    @pytest.mark.asyncio
    async def test_list_by_state_pagination(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Verify list_by_state respects limit and offset."""
        # Create 5 submissions in RECEIVED state
        submissions = [_make_submission(state=PetitionState.RECEIVED) for _ in range(5)]
        for sub in submissions:
            await stub.save(sub)

        # Test limit
        results, total = await stub.list_by_state(PetitionState.RECEIVED, limit=2)
        assert total == 5
        assert len(results) == 2

        # Test offset
        results2, total2 = await stub.list_by_state(
            PetitionState.RECEIVED, limit=2, offset=2
        )
        assert total2 == 5
        assert len(results2) == 2
        # Verify different submissions returned
        ids1 = {r.id for r in results}
        ids2 = {r.id for r in results2}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_update_state_changes_state(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Verify update_state changes submission state."""
        submission = _make_submission(state=PetitionState.RECEIVED)
        await stub.save(submission)

        await stub.update_state(submission.id, PetitionState.DELIBERATING)

        updated = await stub.get(submission.id)
        assert updated is not None
        assert updated.state == PetitionState.DELIBERATING

    @pytest.mark.asyncio
    async def test_update_state_raises_for_missing(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Verify update_state raises for non-existent ID."""
        with pytest.raises(KeyError):
            await stub.update_state(uuid.uuid4(), PetitionState.DELIBERATING)

    @pytest.mark.asyncio
    async def test_id_preservation_fr94(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Verify petition IDs are preserved exactly (FR-9.4)."""
        specific_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        submission = _make_submission(submission_id=specific_id)

        await stub.save(submission)
        retrieved = await stub.get(specific_id)

        assert retrieved is not None
        assert retrieved.id == specific_id
        assert str(retrieved.id) == "12345678-1234-5678-1234-567812345678"


class TestAssignFateCAS:
    """Tests for atomic CAS fate assignment (Story 1.6, FR-2.4, NFR-3.2)."""

    @pytest.fixture
    def stub(self) -> PetitionSubmissionRepositoryStub:
        """Create a fresh stub instance for each test."""
        return PetitionSubmissionRepositoryStub()

    @pytest.mark.asyncio
    async def test_cas_success_deliberating_to_acknowledged(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Successful CAS: DELIBERATING -> ACKNOWLEDGED."""
        submission = _make_submission(state=PetitionState.DELIBERATING)
        await stub.save(submission)

        result = await stub.assign_fate_cas(
            submission_id=submission.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ACKNOWLEDGED,
        )

        assert result.state == PetitionState.ACKNOWLEDGED
        assert result.id == submission.id
        # Verify persisted
        retrieved = await stub.get(submission.id)
        assert retrieved is not None
        assert retrieved.state == PetitionState.ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_cas_success_deliberating_to_referred(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Successful CAS: DELIBERATING -> REFERRED."""
        submission = _make_submission(state=PetitionState.DELIBERATING)
        await stub.save(submission)

        result = await stub.assign_fate_cas(
            submission_id=submission.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.REFERRED,
        )

        assert result.state == PetitionState.REFERRED

    @pytest.mark.asyncio
    async def test_cas_success_deliberating_to_escalated(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """Successful CAS: DELIBERATING -> ESCALATED."""
        submission = _make_submission(state=PetitionState.DELIBERATING)
        await stub.save(submission)

        result = await stub.assign_fate_cas(
            submission_id=submission.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ESCALATED,
        )

        assert result.state == PetitionState.ESCALATED

    @pytest.mark.asyncio
    async def test_cas_failure_state_mismatch(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS fails when expected state doesn't match current state."""
        submission = _make_submission(state=PetitionState.RECEIVED)
        await stub.save(submission)

        with pytest.raises(ConcurrentModificationError) as exc_info:
            await stub.assign_fate_cas(
                submission_id=submission.id,
                expected_state=PetitionState.DELIBERATING,  # Wrong!
                new_state=PetitionState.ACKNOWLEDGED,
            )

        assert exc_info.value.petition_id == submission.id
        assert exc_info.value.expected_state == PetitionState.DELIBERATING
        # State should be unchanged
        retrieved = await stub.get(submission.id)
        assert retrieved is not None
        assert retrieved.state == PetitionState.RECEIVED

    @pytest.mark.asyncio
    async def test_cas_failure_petition_not_found(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS fails when petition doesn't exist."""
        missing_id = uuid.uuid4()

        with pytest.raises(KeyError):
            await stub.assign_fate_cas(
                submission_id=missing_id,
                expected_state=PetitionState.DELIBERATING,
                new_state=PetitionState.ACKNOWLEDGED,
            )

    @pytest.mark.asyncio
    async def test_cas_failure_already_fated_acknowledged(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS fails when petition already has ACKNOWLEDGED fate (FR-2.6)."""
        submission = _make_submission(state=PetitionState.ACKNOWLEDGED)
        await stub.save(submission)

        with pytest.raises(PetitionAlreadyFatedError) as exc_info:
            await stub.assign_fate_cas(
                submission_id=submission.id,
                expected_state=PetitionState.ACKNOWLEDGED,
                new_state=PetitionState.ESCALATED,
            )

        assert exc_info.value.terminal_state == PetitionState.ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_cas_failure_already_fated_referred(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS fails when petition already has REFERRED fate (FR-2.6)."""
        submission = _make_submission(state=PetitionState.REFERRED)
        await stub.save(submission)

        with pytest.raises(PetitionAlreadyFatedError):
            await stub.assign_fate_cas(
                submission_id=submission.id,
                expected_state=PetitionState.REFERRED,
                new_state=PetitionState.ACKNOWLEDGED,
            )

    @pytest.mark.asyncio
    async def test_cas_failure_already_fated_escalated(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS fails when petition already has ESCALATED fate (FR-2.6)."""
        submission = _make_submission(state=PetitionState.ESCALATED)
        await stub.save(submission)

        with pytest.raises(PetitionAlreadyFatedError):
            await stub.assign_fate_cas(
                submission_id=submission.id,
                expected_state=PetitionState.ESCALATED,
                new_state=PetitionState.ACKNOWLEDGED,
            )

    @pytest.mark.asyncio
    async def test_cas_failure_invalid_transition(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS fails when transition is invalid (FR-2.1, FR-2.3)."""
        submission = _make_submission(state=PetitionState.RECEIVED)
        await stub.save(submission)

        # RECEIVED can't go directly to REFERRED (must go through DELIBERATING)
        with pytest.raises(InvalidStateTransitionError):
            await stub.assign_fate_cas(
                submission_id=submission.id,
                expected_state=PetitionState.RECEIVED,
                new_state=PetitionState.REFERRED,
            )

    @pytest.mark.asyncio
    async def test_cas_updates_timestamp(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS updates the updated_at timestamp."""
        submission = _make_submission(state=PetitionState.DELIBERATING)
        original_updated_at = submission.updated_at
        await stub.save(submission)

        # Small delay to ensure timestamp difference
        await asyncio.sleep(0.01)

        result = await stub.assign_fate_cas(
            submission_id=submission.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ACKNOWLEDGED,
        )

        assert result.updated_at > original_updated_at

    @pytest.mark.asyncio
    async def test_cas_preserves_other_fields(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS preserves all fields except state and updated_at."""
        submitter_id = uuid.uuid4()
        content_hash = b"0" * 32
        submission = PetitionSubmission(
            id=uuid.uuid4(),
            type=PetitionType.GRIEVANCE,
            text="Test petition with all fields",
            state=PetitionState.DELIBERATING,
            submitter_id=submitter_id,
            content_hash=content_hash,
            realm="test-realm",
        )
        await stub.save(submission)

        result = await stub.assign_fate_cas(
            submission_id=submission.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ESCALATED,
        )

        assert result.id == submission.id
        assert result.type == PetitionType.GRIEVANCE
        assert result.text == "Test petition with all fields"
        assert result.submitter_id == submitter_id
        assert result.content_hash == content_hash
        assert result.realm == "test-realm"
        assert result.created_at == submission.created_at

    @pytest.mark.asyncio
    async def test_nfr32_no_double_fate_sequential(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """NFR-3.2: No petition ever has double fate - sequential attempts."""
        submission = _make_submission(state=PetitionState.DELIBERATING)
        await stub.save(submission)

        # First fate assignment succeeds
        result1 = await stub.assign_fate_cas(
            submission_id=submission.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ACKNOWLEDGED,
        )
        assert result1.state == PetitionState.ACKNOWLEDGED

        # Second attempt fails - petition already fated
        with pytest.raises(PetitionAlreadyFatedError):
            await stub.assign_fate_cas(
                submission_id=submission.id,
                expected_state=PetitionState.DELIBERATING,  # Stale expectation
                new_state=PetitionState.ESCALATED,
            )

        # Verify only one fate assigned
        retrieved = await stub.get(submission.id)
        assert retrieved is not None
        assert retrieved.state == PetitionState.ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_nfr32_concurrent_fate_assignment_one_wins(
        self, stub: PetitionSubmissionRepositoryStub
    ) -> None:
        """NFR-3.2: Concurrent fate assignments - exactly one succeeds."""
        submission = _make_submission(state=PetitionState.DELIBERATING)
        await stub.save(submission)

        success_count = 0
        failure_count = 0
        results: list[PetitionState] = []

        async def attempt_fate(new_state: PetitionState) -> None:
            nonlocal success_count, failure_count
            try:
                result = await stub.assign_fate_cas(
                    submission_id=submission.id,
                    expected_state=PetitionState.DELIBERATING,
                    new_state=new_state,
                )
                success_count += 1
                results.append(result.state)
            except (ConcurrentModificationError, PetitionAlreadyFatedError):
                failure_count += 1

        # Run 3 concurrent fate assignments
        await asyncio.gather(
            attempt_fate(PetitionState.ACKNOWLEDGED),
            attempt_fate(PetitionState.REFERRED),
            attempt_fate(PetitionState.ESCALATED),
        )

        # Exactly one should succeed
        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert failure_count == 2, f"Expected 2 failures, got {failure_count}"
        assert len(results) == 1

        # Verify final state is one of the terminal states
        retrieved = await stub.get(submission.id)
        assert retrieved is not None
        assert retrieved.state in [
            PetitionState.ACKNOWLEDGED,
            PetitionState.REFERRED,
            PetitionState.ESCALATED,
        ]
