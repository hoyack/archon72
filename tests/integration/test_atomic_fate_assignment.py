"""Integration tests for atomic fate assignment CAS (Story 1.6, FR-2.4, NFR-3.2).

These tests verify that the atomic CAS fate assignment mechanism correctly
prevents double-fate assignment under concurrent conditions.

Constitutional Constraints:
- FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]

Test Strategy:
- Simulate high-concurrency scenarios with multiple coroutines
- Verify exactly one fate assignment succeeds
- Verify no petition ever receives double fate
- Test retry behavior after CAS failure
"""

import asyncio
import uuid
from collections import Counter
from datetime import datetime, timezone

import pytest

from src.domain.errors.concurrent_modification import ConcurrentModificationError
from src.domain.errors.state_transition import PetitionAlreadyFatedError
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


def _make_deliberating_petition() -> PetitionSubmission:
    """Create a petition in DELIBERATING state for fate assignment tests."""
    return PetitionSubmission(
        id=uuid.uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for fate assignment",
        state=PetitionState.DELIBERATING,
        realm="test-realm",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestAtomicFateAssignmentIntegration:
    """Integration tests for atomic CAS fate assignment."""

    @pytest.fixture
    def repository(self) -> PetitionSubmissionRepositoryStub:
        """Create a fresh repository for each test."""
        return PetitionSubmissionRepositoryStub()

    @pytest.mark.asyncio
    async def test_fr24_high_concurrency_single_fate(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """FR-2.4: High concurrency - exactly one fate wins (10 concurrent)."""
        petition = _make_deliberating_petition()
        await repository.save(petition)

        successes = 0
        failures = 0
        winning_states: list[PetitionState] = []

        async def attempt_fate(fate: PetitionState) -> None:
            nonlocal successes, failures
            try:
                result = await repository.assign_fate_cas(
                    submission_id=petition.id,
                    expected_state=PetitionState.DELIBERATING,
                    new_state=fate,
                )
                successes += 1
                winning_states.append(result.state)
            except (ConcurrentModificationError, PetitionAlreadyFatedError):
                failures += 1

        # Create 10 concurrent fate attempts (mix of all terminal fates)
        fates = [
            PetitionState.ACKNOWLEDGED,
            PetitionState.REFERRED,
            PetitionState.ESCALATED,
            PetitionState.DEFERRED,
            PetitionState.NO_RESPONSE,
        ] * 2  # 10 attempts, 2 of each

        tasks = [attempt_fate(fate) for fate in fates]
        await asyncio.gather(*tasks)

        # Exactly one success
        assert successes == 1, f"Expected exactly 1 success, got {successes}"
        assert failures == 9, f"Expected 9 failures, got {failures}"
        assert len(winning_states) == 1

        # Verify final state
        final = await repository.get(petition.id)
        assert final is not None
        assert final.state == winning_states[0]
        assert final.state.is_terminal()

    @pytest.mark.asyncio
    async def test_nfr32_zero_double_fate_guarantee(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """NFR-3.2: Zero tolerance for double-fate - stress test."""
        # Run 50 petitions with concurrent fate assignments
        petitions = [_make_deliberating_petition() for _ in range(50)]
        for p in petitions:
            await repository.save(p)

        results: dict[uuid.UUID, list[PetitionState]] = {p.id: [] for p in petitions}
        errors: dict[uuid.UUID, int] = {p.id: 0 for p in petitions}

        async def attempt_fate(petition_id: uuid.UUID, fate: PetitionState) -> None:
            try:
                result = await repository.assign_fate_cas(
                    submission_id=petition_id,
                    expected_state=PetitionState.DELIBERATING,
                    new_state=fate,
                )
                results[petition_id].append(result.state)
            except (ConcurrentModificationError, PetitionAlreadyFatedError):
                errors[petition_id] += 1

        # For each petition, try concurrent fate assignments for all terminal fates
        all_tasks = []
        for petition in petitions:
            for fate in [
                PetitionState.ACKNOWLEDGED,
                PetitionState.REFERRED,
                PetitionState.ESCALATED,
                PetitionState.DEFERRED,
                PetitionState.NO_RESPONSE,
            ]:
                all_tasks.append(attempt_fate(petition.id, fate))

        await asyncio.gather(*all_tasks)

        # Verify EVERY petition has exactly one fate
        for petition in petitions:
            fates_assigned = results[petition.id]
            assert len(fates_assigned) == 1, (
                f"Petition {petition.id} has {len(fates_assigned)} fates: {fates_assigned}"
            )

            # Verify in storage
            stored = await repository.get(petition.id)
            assert stored is not None
            assert stored.state == fates_assigned[0]
            assert stored.state.is_terminal()

    @pytest.mark.asyncio
    async def test_cas_retry_pattern_success(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Test retry pattern after CAS failure - demonstrating proper handling."""
        petition = _make_deliberating_petition()
        await repository.save(petition)

        # First, successfully assign a fate
        result = await repository.assign_fate_cas(
            submission_id=petition.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.ACKNOWLEDGED,
        )
        assert result.state == PetitionState.ACKNOWLEDGED

        # Now simulate a retry attempt with stale state
        # The proper pattern: read current state, detect already fated, abort
        current = await repository.get(petition.id)
        assert current is not None
        assert current.state.is_terminal()

        # Attempting retry should fail with PetitionAlreadyFatedError
        with pytest.raises(PetitionAlreadyFatedError):
            await repository.assign_fate_cas(
                submission_id=petition.id,
                expected_state=PetitionState.DELIBERATING,
                new_state=PetitionState.ESCALATED,
            )

    @pytest.mark.asyncio
    async def test_cas_failure_preserves_state(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """CAS failure leaves petition state unchanged."""
        petition = _make_deliberating_petition()
        await repository.save(petition)

        # Attempt CAS with wrong expected state
        with pytest.raises(ConcurrentModificationError):
            await repository.assign_fate_cas(
                submission_id=petition.id,
                expected_state=PetitionState.RECEIVED,  # Wrong!
                new_state=PetitionState.ACKNOWLEDGED,
            )

        # State should still be DELIBERATING
        current = await repository.get(petition.id)
        assert current is not None
        assert current.state == PetitionState.DELIBERATING

    @pytest.mark.asyncio
    async def test_fate_distribution_under_contention(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Under contention, all fate types can win (fairness check)."""
        # Run many petitions to check fate distribution
        n_petitions = 30
        petitions = [_make_deliberating_petition() for _ in range(n_petitions)]
        for p in petitions:
            await repository.save(p)

        fate_wins: Counter[PetitionState] = Counter()

        async def race_for_fate(petition_id: uuid.UUID) -> None:
            """Race concurrent fate assignments."""
            results = []

            async def try_fate(fate: PetitionState) -> None:
                try:
                    result = await repository.assign_fate_cas(
                        submission_id=petition_id,
                        expected_state=PetitionState.DELIBERATING,
                        new_state=fate,
                    )
                    results.append(result.state)
                except (ConcurrentModificationError, PetitionAlreadyFatedError):
                    pass

            await asyncio.gather(
                try_fate(PetitionState.ACKNOWLEDGED),
                try_fate(PetitionState.REFERRED),
                try_fate(PetitionState.ESCALATED),
                try_fate(PetitionState.DEFERRED),
                try_fate(PetitionState.NO_RESPONSE),
            )

            assert len(results) == 1
            fate_wins[results[0]] += 1

        # Race all petitions
        await asyncio.gather(*[race_for_fate(p.id) for p in petitions])

        # Multiple fate types should have won at least once
        # (probabilistically, with 30 trials this is very likely)
        assert len(fate_wins) >= 2, f"Too few fate types won: {dict(fate_wins)}"
        assert sum(fate_wins.values()) == n_petitions

    @pytest.mark.asyncio
    async def test_terminal_state_immutability(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Terminal states are immutable - subsequent CAS always fails."""
        petition = _make_deliberating_petition()
        await repository.save(petition)

        # Assign initial fate
        await repository.assign_fate_cas(
            submission_id=petition.id,
            expected_state=PetitionState.DELIBERATING,
            new_state=PetitionState.REFERRED,
        )

        # Try to change from REFERRED to other fates - all should fail
        for new_fate in [
            PetitionState.ACKNOWLEDGED,
            PetitionState.ESCALATED,
            PetitionState.DEFERRED,
            PetitionState.NO_RESPONSE,
            PetitionState.DELIBERATING,
        ]:
            with pytest.raises(PetitionAlreadyFatedError):
                await repository.assign_fate_cas(
                    submission_id=petition.id,
                    expected_state=PetitionState.REFERRED,
                    new_state=new_fate,
                )

        # Verify state unchanged
        final = await repository.get(petition.id)
        assert final is not None
        assert final.state == PetitionState.REFERRED

    @pytest.mark.asyncio
    async def test_cas_idempotent_check_pattern(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Demonstrate idempotent check-then-act pattern."""
        petition = _make_deliberating_petition()
        await repository.save(petition)

        async def safe_assign_fate(
            petition_id: uuid.UUID, desired_fate: PetitionState
        ) -> tuple[bool, PetitionState]:
            """
            Safe fate assignment with idempotent behavior.
            Returns (success: bool, final_state: PetitionState).
            """
            current = await repository.get(petition_id)
            if current is None:
                raise KeyError(f"Petition {petition_id} not found")

            if current.state.is_terminal():
                # Already fated - return current state (idempotent)
                return False, current.state

            try:
                result = await repository.assign_fate_cas(
                    submission_id=petition_id,
                    expected_state=current.state,
                    new_state=desired_fate,
                )
                return True, result.state
            except ConcurrentModificationError:
                # Another process won - get final state
                final = await repository.get(petition_id)
                return False, final.state if final else PetitionState.RECEIVED
            except PetitionAlreadyFatedError:
                final = await repository.get(petition_id)
                return False, final.state if final else PetitionState.RECEIVED

        # First call assigns fate
        success1, state1 = await safe_assign_fate(
            petition.id, PetitionState.ACKNOWLEDGED
        )
        assert success1 is True
        assert state1 == PetitionState.ACKNOWLEDGED

        # Second call is idempotent - returns existing state
        success2, state2 = await safe_assign_fate(petition.id, PetitionState.ESCALATED)
        assert success2 is False
        assert state2 == PetitionState.ACKNOWLEDGED  # Original fate preserved
