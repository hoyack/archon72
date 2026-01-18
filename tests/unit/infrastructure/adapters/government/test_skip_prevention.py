"""Unit tests for Skip Prevention (Story GOV-8.3).

Tests:
- AC1: Skip Detection - detects skipped states before transition
- AC2: Skip Rejection - rejects and witnesses skip attempts
- AC3: Violation Recording - records with correct severity and details
- AC4: Force Skip Prevention - rejects regardless of privilege
- AC5: API-Level Enforcement - validate_transition method
- AC6: Audit Trail - full audit trail maintained

Constitutional Constraints:
- FR-GOV-23: Governance Flow - No step may be skipped
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> Never allow skip
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance_state_machine import (
    ForceSkipAttemptError,
    GovernanceState,
    SkipAttemptError,
    SkipAttemptSeverity,
    SkipAttemptType,
    SkipAttemptViolation,
    TransitionRequest,
)
from src.infrastructure.adapters.government.governance_state_machine_adapter import (
    GovernanceStateMachineAdapter,
)

# =============================================================================
# Test Helpers
# =============================================================================


async def create_motion_in_introduced(
    state_machine: GovernanceStateMachineAdapter,
) -> tuple[UUID, GovernanceStateMachineAdapter]:
    """Create a motion in INTRODUCED state."""
    motion_id = uuid4()
    result = await state_machine.initialize_motion(motion_id, "king-001")
    assert result.success
    return motion_id, state_machine


async def create_motion_in_ratified(
    state_machine: GovernanceStateMachineAdapter,
) -> tuple[UUID, GovernanceStateMachineAdapter]:
    """Create a motion in RATIFIED state."""
    motion_id = uuid4()
    await state_machine.initialize_motion(motion_id, "king-001")

    # Progress through INTRODUCED -> DELIBERATING -> RATIFIED
    await state_machine.transition(
        TransitionRequest(
            motion_id=motion_id,
            to_state=GovernanceState.DELIBERATING,
            triggered_by="conclave-001",
        )
    )
    await state_machine.transition(
        TransitionRequest(
            motion_id=motion_id,
            to_state=GovernanceState.RATIFIED,
            triggered_by="conclave-001",
        )
    )

    return motion_id, state_machine


# =============================================================================
# AC1: Skip Detection Tests
# =============================================================================


class TestSkipDetection:
    """Tests for AC1: Skip Detection."""

    @pytest.mark.asyncio
    async def test_detects_single_state_skip(self) -> None:
        """Detects skip attempt that misses one state."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        # Try to skip DELIBERATING
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.RATIFIED,
                triggered_by="conclave-001",
            )
        )

        assert not result.success
        assert result.rejection is not None
        assert GovernanceState.DELIBERATING in result.rejection.skipped_states

    @pytest.mark.asyncio
    async def test_detects_multiple_state_skip(self) -> None:
        """Detects skip attempt that misses multiple states."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        # Try to skip DELIBERATING and RATIFIED and PLANNING
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )

        assert not result.success
        assert result.rejection is not None
        assert len(result.rejection.skipped_states) >= 2

    @pytest.mark.asyncio
    async def test_detects_skip_before_transition(self) -> None:
        """Skip is detected BEFORE any state change occurs."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        # Attempt skip
        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        # Verify state unchanged
        current = await sm.get_current_state(motion_id)
        assert current == GovernanceState.INTRODUCED

    @pytest.mark.asyncio
    async def test_valid_transition_not_flagged_as_skip(self) -> None:
        """Valid transitions are not flagged as skips."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        # Valid transition
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.DELIBERATING,
                triggered_by="conclave-001",
            )
        )

        assert result.success
        assert result.rejection is None


# =============================================================================
# AC2: Skip Rejection Tests
# =============================================================================


class TestSkipRejection:
    """Tests for AC2: Skip Rejection."""

    @pytest.mark.asyncio
    async def test_skip_is_rejected(self) -> None:
        """Skip attempts are rejected with TransitionResult.success=False."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        assert not result.success
        assert "Invalid transition" in (result.error or "")

    @pytest.mark.asyncio
    async def test_rejection_includes_error_details(self) -> None:
        """Rejection includes current state, attempted state, and required intermediate states."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        assert result.rejection is not None
        assert result.rejection.current_state == GovernanceState.INTRODUCED
        assert result.rejection.attempted_state == GovernanceState.PLANNING
        assert len(result.rejection.skipped_states) > 0
        assert result.rejection.prd_reference == "FR-GOV-23"


# =============================================================================
# AC3: Violation Recording Tests
# =============================================================================


class TestViolationRecording:
    """Tests for AC3: Violation Recording."""

    @pytest.mark.asyncio
    async def test_violation_includes_step_skip_attempt_type(self) -> None:
        """Violation includes violation_type: STEP_SKIP_ATTEMPT."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        # Check audit trail
        audit_entries = await sm.get_skip_attempts(motion_id)
        assert len(audit_entries) == 1

        violation = audit_entries[0].violation
        assert violation.to_dict()["violation_type"] == "STEP_SKIP_ATTEMPT"

    @pytest.mark.asyncio
    async def test_violation_severity_is_critical(self) -> None:
        """Violation severity is CRITICAL."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.severity == SkipAttemptSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_violation_includes_archon_id(self) -> None:
        """Violation includes archon_id of who attempted."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="malicious-archon-999",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.attempted_by == "malicious-archon-999"

    @pytest.mark.asyncio
    async def test_violation_includes_motion_id(self) -> None:
        """Violation includes motion_id affected."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.motion_id == motion_id

    @pytest.mark.asyncio
    async def test_violation_includes_transition_details(self) -> None:
        """Violation includes attempted_transition details."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.current_state == GovernanceState.INTRODUCED
        assert violation.attempted_state == GovernanceState.EXECUTING
        assert len(violation.skipped_states) > 0

    @pytest.mark.asyncio
    async def test_bulk_skip_type_for_multiple_states(self) -> None:
        """Bulk skip attempts are classified as BULK_SKIP."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        # Skip multiple states (INTRODUCED -> EXECUTING skips DELIBERATING, RATIFIED, PLANNING)
        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.attempt_type == SkipAttemptType.BULK_SKIP


# =============================================================================
# AC4: Force Skip Prevention Tests
# =============================================================================


class TestForceSkipPrevention:
    """Tests for AC4: Force Skip Prevention."""

    @pytest.mark.asyncio
    async def test_force_skip_rejected(self) -> None:
        """Force skip attempts are rejected."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        with pytest.raises(ForceSkipAttemptError):
            await sm.force_transition(
                TransitionRequest(
                    motion_id=motion_id,
                    to_state=GovernanceState.PLANNING,
                    triggered_by="privileged-admin",
                )
            )

    @pytest.mark.asyncio
    async def test_force_skip_rejected_regardless_of_privilege(self) -> None:
        """Force skip is rejected even for privileged users."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        privileged_users = ["system-admin", "root", "king-001", "supreme-archon"]

        for user in privileged_users:
            with pytest.raises(ForceSkipAttemptError):
                await sm.force_transition(
                    TransitionRequest(
                        motion_id=motion_id,
                        to_state=GovernanceState.PLANNING,
                        triggered_by=user,
                    )
                )

    @pytest.mark.asyncio
    async def test_force_skip_escalated_to_conclave(self) -> None:
        """Force skip attempts are escalated to Conclave review."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        try:
            await sm.force_transition(
                TransitionRequest(
                    motion_id=motion_id,
                    to_state=GovernanceState.PLANNING,
                    triggered_by="privileged-admin",
                )
            )
        except ForceSkipAttemptError as e:
            assert e.violation.escalated_to_conclave is True
            assert e.escalated is True

    @pytest.mark.asyncio
    async def test_force_skip_documented_as_forced_skip_attempt(self) -> None:
        """Force skip attempts are documented with FORCED_SKIP_ATTEMPT type."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        try:
            await sm.force_transition(
                TransitionRequest(
                    motion_id=motion_id,
                    to_state=GovernanceState.PLANNING,
                    triggered_by="privileged-admin",
                )
            )
        except ForceSkipAttemptError as e:
            assert e.violation.attempt_type == SkipAttemptType.FORCE_SKIP
            assert e.error_code == "FORCED_SKIP_ATTEMPT"

    @pytest.mark.asyncio
    async def test_valid_force_transition_succeeds(self) -> None:
        """Valid transitions via force_transition succeed normally."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        # Valid transition should work
        result = await sm.force_transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.DELIBERATING,
                triggered_by="conclave-001",
            )
        )

        assert result.success


# =============================================================================
# AC5: API-Level Enforcement Tests
# =============================================================================


class TestApiLevelEnforcement:
    """Tests for AC5: API-Level Enforcement."""

    @pytest.mark.asyncio
    async def test_validate_transition_detects_skip(self) -> None:
        """validate_transition detects skip before calling state machine."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        is_valid, skipped = await sm.validate_transition(
            motion_id, GovernanceState.PLANNING
        )

        assert not is_valid
        assert len(skipped) > 0

    @pytest.mark.asyncio
    async def test_validate_transition_returns_skipped_states(self) -> None:
        """validate_transition returns the skipped states."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        is_valid, skipped = await sm.validate_transition(
            motion_id, GovernanceState.EXECUTING
        )

        assert not is_valid
        assert GovernanceState.DELIBERATING in skipped

    @pytest.mark.asyncio
    async def test_validate_transition_accepts_valid(self) -> None:
        """validate_transition returns (True, []) for valid transitions."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        is_valid, skipped = await sm.validate_transition(
            motion_id, GovernanceState.DELIBERATING
        )

        assert is_valid
        assert skipped == []

    @pytest.mark.asyncio
    async def test_validate_transition_handles_missing_motion(self) -> None:
        """validate_transition handles non-existent motion gracefully."""
        sm = GovernanceStateMachineAdapter()
        is_valid, skipped = await sm.validate_transition(
            uuid4(), GovernanceState.DELIBERATING
        )

        assert not is_valid
        assert skipped == []


# =============================================================================
# AC6: Audit Trail Tests
# =============================================================================


class TestAuditTrail:
    """Tests for AC6: Audit Trail."""

    @pytest.mark.asyncio
    async def test_skip_attempt_recorded_in_audit(self) -> None:
        """Skip attempts are recorded in audit trail."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        assert len(audit_entries) == 1

    @pytest.mark.asyncio
    async def test_audit_includes_timestamp(self) -> None:
        """Audit entry includes timestamp of attempt."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)
        before = datetime.now(timezone.utc)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        after = datetime.now(timezone.utc)

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert before <= violation.attempted_at <= after

    @pytest.mark.asyncio
    async def test_audit_includes_archon_who_attempted(self) -> None:
        """Audit entry includes Archon who attempted."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="suspicious-archon-666",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.attempted_by == "suspicious-archon-666"

    @pytest.mark.asyncio
    async def test_audit_includes_source_of_attempt(self) -> None:
        """Audit entry includes source of attempt."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.source in ("api", "service", "manual", "force_api")

    @pytest.mark.asyncio
    async def test_audit_includes_current_and_attempted_state(self) -> None:
        """Audit entry includes current state and attempted state."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.current_state == GovernanceState.INTRODUCED
        assert violation.attempted_state == GovernanceState.EXECUTING

    @pytest.mark.asyncio
    async def test_audit_includes_rejection_reason(self) -> None:
        """Audit entry indicates rejection reason."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        violation = audit_entries[0].violation

        assert violation.rejected is True
        assert violation.prd_reference == "FR-GOV-23"

    @pytest.mark.asyncio
    async def test_get_skip_attempts_filters_by_motion(self) -> None:
        """get_skip_attempts can filter by motion_id."""
        sm = GovernanceStateMachineAdapter()
        motion_id_1 = uuid4()
        motion_id_2 = uuid4()

        await sm.initialize_motion(motion_id_1, "king-001")
        await sm.initialize_motion(motion_id_2, "king-001")

        # Create skip attempt for motion 1
        await sm.transition(
            TransitionRequest(
                motion_id=motion_id_1,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )

        # Create skip attempt for motion 2
        await sm.transition(
            TransitionRequest(
                motion_id=motion_id_2,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )

        # Filter by motion 1
        motion_1_entries = await sm.get_skip_attempts(motion_id_1)
        assert len(motion_1_entries) == 1
        assert motion_1_entries[0].violation.motion_id == motion_id_1

        # Get all
        all_entries = await sm.get_skip_attempts()
        assert len(all_entries) == 2

    @pytest.mark.asyncio
    async def test_multiple_skip_attempts_all_recorded(self) -> None:
        """Multiple skip attempts for same motion are all recorded."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)

        # Multiple skip attempts
        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )
        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )
        await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.ACKNOWLEDGED,
                triggered_by="conclave-001",
            )
        )

        audit_entries = await sm.get_skip_attempts(motion_id)
        assert len(audit_entries) == 3


# =============================================================================
# Domain Model Tests
# =============================================================================


class TestSkipAttemptViolation:
    """Tests for SkipAttemptViolation domain model."""

    def test_create_violation(self) -> None:
        """SkipAttemptViolation.create() works correctly."""
        motion_id = uuid4()

        violation = SkipAttemptViolation.create(
            motion_id=motion_id,
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.EXECUTING,
            skipped_states=[GovernanceState.DELIBERATING, GovernanceState.PLANNING],
            attempt_type=SkipAttemptType.BULK_SKIP,
            attempted_by="test-archon",
            source="api",
            escalate=False,
            timestamp=datetime.now(timezone.utc),
        )

        assert violation.motion_id == motion_id
        assert violation.current_state == GovernanceState.INTRODUCED
        assert violation.attempted_state == GovernanceState.EXECUTING
        assert len(violation.skipped_states) == 2
        assert violation.attempt_type == SkipAttemptType.BULK_SKIP
        assert violation.attempted_by == "test-archon"
        assert violation.severity == SkipAttemptSeverity.CRITICAL
        assert violation.rejected is True

    def test_violation_is_frozen(self) -> None:
        """SkipAttemptViolation is immutable."""
        violation = SkipAttemptViolation.create(
            motion_id=uuid4(),
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.PLANNING,
            skipped_states=[GovernanceState.DELIBERATING],
            attempt_type=SkipAttemptType.SIMPLE_SKIP,
            attempted_by="test-archon",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            violation.attempted_by = "modified"  # type: ignore

    def test_violation_to_dict(self) -> None:
        """SkipAttemptViolation.to_dict() includes all fields."""
        violation = SkipAttemptViolation.create(
            motion_id=uuid4(),
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.PLANNING,
            skipped_states=[GovernanceState.DELIBERATING],
            attempt_type=SkipAttemptType.SIMPLE_SKIP,
            attempted_by="test-archon",
            timestamp=datetime.now(timezone.utc),
        )

        d = violation.to_dict()

        assert d["violation_type"] == "STEP_SKIP_ATTEMPT"
        assert d["severity"] == "critical"
        assert d["prd_reference"] == "FR-GOV-23"
        assert d["rejected"] is True


class TestSkipAttemptError:
    """Tests for SkipAttemptError exception."""

    def test_error_message_includes_states(self) -> None:
        """SkipAttemptError message includes state information."""
        violation = SkipAttemptViolation.create(
            motion_id=uuid4(),
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.PLANNING,
            skipped_states=[GovernanceState.DELIBERATING, GovernanceState.RATIFIED],
            attempt_type=SkipAttemptType.BULK_SKIP,
            attempted_by="test-archon",
            timestamp=datetime.now(timezone.utc),
        )

        error = SkipAttemptError(violation)

        assert "introduced" in str(error)
        assert "planning" in str(error)
        assert "deliberating" in str(error)

    def test_error_response_format(self) -> None:
        """SkipAttemptError.to_error_response() matches spec."""
        violation = SkipAttemptViolation.create(
            motion_id=uuid4(),
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.PLANNING,
            skipped_states=[GovernanceState.DELIBERATING, GovernanceState.RATIFIED],
            attempt_type=SkipAttemptType.BULK_SKIP,
            attempted_by="test-archon",
            timestamp=datetime.now(timezone.utc),
        )

        error = SkipAttemptError(violation)
        response = error.to_error_response()

        assert response["error_code"] == "STEP_SKIP_VIOLATION"
        assert response["prd_reference"] == "FR-GOV-23"
        assert response["current_state"] == "introduced"
        assert response["attempted_state"] == "planning"
        assert response["required_next_state"] == "deliberating"
        assert "deliberating" in response["skipped_states"]


class TestForceSkipAttemptError:
    """Tests for ForceSkipAttemptError exception."""

    def test_force_skip_error_code(self) -> None:
        """ForceSkipAttemptError has FORCED_SKIP_ATTEMPT error code."""
        violation = SkipAttemptViolation.create(
            motion_id=uuid4(),
            current_state=GovernanceState.INTRODUCED,
            attempted_state=GovernanceState.PLANNING,
            skipped_states=[GovernanceState.DELIBERATING],
            attempt_type=SkipAttemptType.FORCE_SKIP,
            attempted_by="admin",
            escalate=True,
            timestamp=datetime.now(timezone.utc),
        )

        error = ForceSkipAttemptError(violation)

        assert error.error_code == "FORCED_SKIP_ATTEMPT"
        assert error.escalated is True


# =============================================================================
# Invalid Transition Matrix Tests
# =============================================================================


class TestInvalidTransitionMatrix:
    """Test all invalid transitions per the matrix in story requirements."""

    @pytest.mark.asyncio
    async def test_introduced_cannot_skip_to_ratified(self) -> None:
        """INTRODUCED cannot go directly to RATIFIED."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.RATIFIED,
                triggered_by="conclave-001",
            )
        )
        assert not result.success

    @pytest.mark.asyncio
    async def test_introduced_cannot_skip_to_planning(self) -> None:
        """INTRODUCED cannot go directly to PLANNING."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.PLANNING,
                triggered_by="president-001",
            )
        )
        assert not result.success

    @pytest.mark.asyncio
    async def test_introduced_cannot_skip_to_executing(self) -> None:
        """INTRODUCED cannot go directly to EXECUTING."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_introduced(sm)
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )
        assert not result.success

    @pytest.mark.asyncio
    async def test_ratified_cannot_skip_to_executing(self) -> None:
        """RATIFIED cannot skip PLANNING to go to EXECUTING."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_ratified(sm)
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.EXECUTING,
                triggered_by="duke-001",
            )
        )
        assert not result.success

    @pytest.mark.asyncio
    async def test_ratified_cannot_skip_to_acknowledged(self) -> None:
        """RATIFIED cannot skip all the way to ACKNOWLEDGED."""
        sm = GovernanceStateMachineAdapter()
        motion_id, sm = await create_motion_in_ratified(sm)
        result = await sm.transition(
            TransitionRequest(
                motion_id=motion_id,
                to_state=GovernanceState.ACKNOWLEDGED,
                triggered_by="conclave-001",
            )
        )
        assert not result.success
