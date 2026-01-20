"""Unit tests for ExtensionRequestService (Story 4.5, FR-4.4).

This module tests the extension request service implementation.

Test Coverage:
- AC-1: Extension request success (deadline extended, event emitted)
- AC-2: Max extensions enforcement (MAX_EXTENSIONS_REACHED error)
- AC-3: Authorization check (NOT_ASSIGNED_KNIGHT error)
- AC-4: Invalid state check (INVALID_REFERRAL_STATE error)
- AC-5: Reason validation (REASON_REQUIRED error)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.ports.extension_request import (
    ExtensionRequest,
    ExtensionResult,
)
from src.application.services.extension_request_service import (
    EXTENSION_DURATION_CYCLES,
    MIN_REASON_LENGTH,
    ExtensionRequestService,
)
from src.domain.errors.referral import (
    ExtensionReasonRequiredError,
    InvalidReferralStateError,
    MaxExtensionsReachedError,
    NotAssignedKnightError,
    ReferralNotFoundError,
)
from src.domain.models.referral import (
    REFERRAL_DEFAULT_CYCLE_DURATION,
    Referral,
    ReferralStatus,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures and Helpers
# ═══════════════════════════════════════════════════════════════════════════════


class MockReferralRepository:
    """Mock referral repository for testing."""

    def __init__(self) -> None:
        self._referrals: dict[UUID, Referral] = {}

    def add(self, referral: Referral) -> None:
        """Add a referral."""
        self._referrals[referral.referral_id] = referral

    async def get_by_id(self, referral_id: UUID) -> Referral | None:
        """Get referral by ID."""
        return self._referrals.get(referral_id)

    async def update(self, referral: Referral) -> None:
        """Update a referral."""
        self._referrals[referral.referral_id] = referral


class MockEventWriter:
    """Mock event writer for testing."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def write(self, event: dict[str, Any]) -> None:
        """Record an event."""
        self.events.append(event)


class MockHashService:
    """Mock hash service for testing."""

    def __init__(self) -> None:
        self._counter = 0

    async def compute_hash(self, content: str) -> str:
        """Generate a deterministic hash."""
        self._counter += 1
        return f"test-hash-{self._counter:06d}"


class MockJobScheduler:
    """Mock job scheduler for testing."""

    def __init__(self) -> None:
        self.scheduled: list[dict[str, Any]] = []
        self.cancelled: list[str] = []

    async def schedule(
        self,
        job_id: str,
        run_at: datetime,
        handler: str,
        payload: dict[str, Any],
    ) -> None:
        """Record a scheduled job."""
        self.scheduled.append({
            "job_id": job_id,
            "run_at": run_at,
            "handler": handler,
            "payload": payload,
        })

    async def cancel(self, job_id: str) -> None:
        """Record a cancelled job."""
        self.cancelled.append(job_id)


def create_test_referral(
    referral_id: UUID | None = None,
    petition_id: UUID | None = None,
    realm_id: UUID | None = None,
    knight_id: UUID | None = None,
    status: ReferralStatus = ReferralStatus.IN_REVIEW,
    extensions_granted: int = 0,
    deadline: datetime | None = None,
) -> Referral:
    """Create a test referral with default values."""
    now = datetime.now(timezone.utc)
    return Referral(
        referral_id=referral_id or uuid4(),
        petition_id=petition_id or uuid4(),
        realm_id=realm_id or uuid4(),
        assigned_knight_id=knight_id,
        status=status,
        deadline=deadline or (now + timedelta(weeks=3)),
        extensions_granted=extensions_granted,
        created_at=now,
    )


@pytest.fixture
def repo() -> MockReferralRepository:
    """Create a mock referral repository."""
    return MockReferralRepository()


@pytest.fixture
def event_writer() -> MockEventWriter:
    """Create a mock event writer."""
    return MockEventWriter()


@pytest.fixture
def hash_service() -> MockHashService:
    """Create a mock hash service."""
    return MockHashService()


@pytest.fixture
def job_scheduler() -> MockJobScheduler:
    """Create a mock job scheduler."""
    return MockJobScheduler()


@pytest.fixture
def service(
    repo: MockReferralRepository,
    event_writer: MockEventWriter,
    hash_service: MockHashService,
    job_scheduler: MockJobScheduler,
) -> ExtensionRequestService:
    """Create an ExtensionRequestService with mocks."""
    return ExtensionRequestService(
        referral_repo=repo,
        event_writer=event_writer,
        hash_service=hash_service,
        job_scheduler=job_scheduler,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AC-1: Extension Request Success
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_extension_success_in_review(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
    event_writer: MockEventWriter,
    job_scheduler: MockJobScheduler,
) -> None:
    """Test successful extension for IN_REVIEW referral."""
    # Arrange
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=0,
    )
    repo.add(referral)
    original_deadline = referral.deadline

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="Need more time to review complex petition with multiple stakeholders",
    )

    # Act
    result = await service.request_extension(request)

    # Assert
    assert isinstance(result, ExtensionResult)
    assert result.referral_id == referral.referral_id
    assert result.petition_id == referral.petition_id
    assert result.knight_id == knight_id
    assert result.previous_deadline == original_deadline
    assert result.new_deadline > original_deadline
    assert result.extensions_granted == 1
    assert result.witness_hash.startswith("test-hash-")

    # Verify referral was updated
    updated = await repo.get_by_id(referral.referral_id)
    assert updated is not None
    assert updated.extensions_granted == 1
    assert updated.deadline == result.new_deadline

    # Verify event was emitted
    assert len(event_writer.events) == 1
    event = event_writer.events[0]
    assert event["event_type"] == "petition.referral.extended"
    assert event["extensions_granted"] == 1

    # Verify job was rescheduled
    assert len(job_scheduler.cancelled) == 1
    assert len(job_scheduler.scheduled) == 1


@pytest.mark.asyncio
async def test_extension_success_assigned_status(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test successful extension for ASSIGNED referral."""
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.ASSIGNED,
        extensions_granted=0,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="Need more time to prepare for review",
    )

    result = await service.request_extension(request)

    assert result.extensions_granted == 1
    updated = await repo.get_by_id(referral.referral_id)
    assert updated is not None
    assert updated.extensions_granted == 1


@pytest.mark.asyncio
async def test_extension_success_second_extension(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test successful second extension (extensions_granted goes from 1 to 2)."""
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=1,  # Already has 1 extension
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="Still need additional time for thorough analysis",
    )

    result = await service.request_extension(request)

    assert result.extensions_granted == 2


@pytest.mark.asyncio
async def test_extension_deadline_calculation(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that deadline is extended by 1 cycle (1 week)."""
    knight_id = uuid4()
    now = datetime.now(timezone.utc)
    original_deadline = now + timedelta(weeks=2)
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
        deadline=original_deadline,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="Requesting standard extension",
    )

    result = await service.request_extension(request)

    expected_deadline = original_deadline + (EXTENSION_DURATION_CYCLES * REFERRAL_DEFAULT_CYCLE_DURATION)
    assert result.new_deadline == expected_deadline


# ═══════════════════════════════════════════════════════════════════════════════
# AC-2: Max Extensions Enforcement
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_max_extensions_reached_error(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised when max extensions (2) already granted."""
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=2,  # Already at max
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="Need one more extension please",
    )

    with pytest.raises(MaxExtensionsReachedError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.referral_id == referral.referral_id
    assert exc_info.value.extensions_granted == 2


@pytest.mark.asyncio
async def test_max_extensions_configurable_below_default(
    repo: MockReferralRepository,
    event_writer: MockEventWriter,
    hash_service: MockHashService,
    job_scheduler: MockJobScheduler,
) -> None:
    """Test that max extensions can be configured to less than default.

    Note: Increasing max_extensions above the Referral model's MAX_EXTENSIONS (2)
    is not supported because the model validates against its hardcoded limit.
    This tests the service's ability to enforce a *lower* limit.
    """
    service = ExtensionRequestService(
        referral_repo=repo,
        event_writer=event_writer,
        hash_service=hash_service,
        job_scheduler=job_scheduler,
        max_extensions=1,  # Lower than default (2)
    )

    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=1,  # At custom max of 1
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="This should fail with custom max of 1",
    )

    with pytest.raises(MaxExtensionsReachedError):
        await service.request_extension(request)


# ═══════════════════════════════════════════════════════════════════════════════
# AC-3: Authorization Check
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_not_assigned_knight_error(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised when requester is not assigned Knight."""
    assigned_knight = uuid4()
    wrong_knight = uuid4()
    referral = create_test_referral(
        knight_id=assigned_knight,
        status=ReferralStatus.IN_REVIEW,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=wrong_knight,  # Wrong knight
        reason="I am not the assigned knight",
    )

    with pytest.raises(NotAssignedKnightError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.referral_id == referral.referral_id
    assert exc_info.value.requester_id == wrong_knight
    assert exc_info.value.assigned_knight_id == assigned_knight


@pytest.mark.asyncio
async def test_no_knight_assigned_error(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised when referral is in PENDING state (no Knight assigned).

    Note: The Referral model enforces that IN_REVIEW status requires assigned_knight_id.
    A referral without an assigned Knight is in PENDING status, which is not a valid
    state for extension (only ASSIGNED and IN_REVIEW are valid).
    """
    # Create a PENDING referral (no knight assigned)
    referral = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        assigned_knight_id=None,
        status=ReferralStatus.PENDING,  # PENDING allows no knight
        deadline=datetime.now(timezone.utc) + timedelta(weeks=3),
        extensions_granted=0,
        created_at=datetime.now(timezone.utc),
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=uuid4(),
        reason="No knight assigned yet",
    )

    # Should fail because PENDING is not a valid state for extension
    with pytest.raises(InvalidReferralStateError):
        await service.request_extension(request)


# ═══════════════════════════════════════════════════════════════════════════════
# AC-4: Invalid State Check
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invalid_state_pending(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised for PENDING status."""
    referral = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        assigned_knight_id=None,
        status=ReferralStatus.PENDING,
        deadline=datetime.now(timezone.utc) + timedelta(weeks=3),
        extensions_granted=0,
        created_at=datetime.now(timezone.utc),
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=uuid4(),
        reason="Cannot extend pending referral",
    )

    with pytest.raises(InvalidReferralStateError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.current_status == "pending"
    assert "assigned" in exc_info.value.required_statuses or "in_review" in exc_info.value.required_statuses


@pytest.mark.asyncio
async def test_invalid_state_completed(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised for COMPLETED status."""
    knight_id = uuid4()
    now = datetime.now(timezone.utc)
    from src.domain.models.referral import ReferralRecommendation

    referral = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        assigned_knight_id=knight_id,
        status=ReferralStatus.COMPLETED,
        deadline=now + timedelta(weeks=3),
        extensions_granted=0,
        recommendation=ReferralRecommendation.ACKNOWLEDGE,
        rationale="Completed with recommendation",
        created_at=now,
        completed_at=now,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="Cannot extend completed referral",
    )

    with pytest.raises(InvalidReferralStateError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.current_status == "completed"


@pytest.mark.asyncio
async def test_invalid_state_expired(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised for EXPIRED status."""
    knight_id = uuid4()
    now = datetime.now(timezone.utc)

    referral = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        assigned_knight_id=knight_id,
        status=ReferralStatus.EXPIRED,
        deadline=now - timedelta(days=1),  # Past deadline
        extensions_granted=0,
        created_at=now - timedelta(weeks=4),
        completed_at=now,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="Cannot extend expired referral",
    )

    with pytest.raises(InvalidReferralStateError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.current_status == "expired"


# ═══════════════════════════════════════════════════════════════════════════════
# AC-5: Reason Validation
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reason_required_empty(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised for empty reason."""
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="",  # Empty reason
    )

    with pytest.raises(ExtensionReasonRequiredError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.provided_length == 0
    assert exc_info.value.min_length == MIN_REASON_LENGTH


@pytest.mark.asyncio
async def test_reason_required_too_short(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised for reason that's too short."""
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="short",  # Only 5 chars, need 10
    )

    with pytest.raises(ExtensionReasonRequiredError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.provided_length == 5
    assert exc_info.value.min_length == MIN_REASON_LENGTH


@pytest.mark.asyncio
async def test_reason_whitespace_only(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that error is raised for whitespace-only reason."""
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="         ",  # Only whitespace
    )

    with pytest.raises(ExtensionReasonRequiredError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.provided_length == 0  # After strip


@pytest.mark.asyncio
async def test_reason_minimum_length_accepted(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test that exactly minimum length reason is accepted."""
    knight_id = uuid4()
    referral = create_test_referral(
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
    )
    repo.add(referral)

    request = ExtensionRequest(
        referral_id=referral.referral_id,
        knight_id=knight_id,
        reason="A" * MIN_REASON_LENGTH,  # Exactly 10 chars
    )

    result = await service.request_extension(request)
    assert result.extensions_granted == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Referral Not Found
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_referral_not_found(
    service: ExtensionRequestService,
) -> None:
    """Test that error is raised when referral doesn't exist."""
    non_existent_id = uuid4()
    request = ExtensionRequest(
        referral_id=non_existent_id,
        knight_id=uuid4(),
        reason="This referral doesn't exist",
    )

    with pytest.raises(ReferralNotFoundError) as exc_info:
        await service.request_extension(request)

    assert exc_info.value.referral_id == non_existent_id


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Methods
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_extension_count(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test get_extension_count method."""
    referral = create_test_referral(
        knight_id=uuid4(),
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=1,
    )
    repo.add(referral)

    count = await service.get_extension_count(referral.referral_id)
    assert count == 1


@pytest.mark.asyncio
async def test_get_extension_count_not_found(
    service: ExtensionRequestService,
) -> None:
    """Test get_extension_count raises error for non-existent referral."""
    with pytest.raises(ReferralNotFoundError):
        await service.get_extension_count(uuid4())


@pytest.mark.asyncio
async def test_can_extend_true(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test can_extend returns True when extension is possible."""
    referral = create_test_referral(
        knight_id=uuid4(),
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=0,
    )
    repo.add(referral)

    can_extend = await service.can_extend(referral.referral_id)
    assert can_extend is True


@pytest.mark.asyncio
async def test_can_extend_false_max_reached(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test can_extend returns False when max extensions reached."""
    referral = create_test_referral(
        knight_id=uuid4(),
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=2,
    )
    repo.add(referral)

    can_extend = await service.can_extend(referral.referral_id)
    assert can_extend is False


@pytest.mark.asyncio
async def test_can_extend_false_invalid_state(
    service: ExtensionRequestService,
    repo: MockReferralRepository,
) -> None:
    """Test can_extend returns False for invalid state."""
    knight_id = uuid4()
    now = datetime.now(timezone.utc)
    from src.domain.models.referral import ReferralRecommendation

    referral = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        assigned_knight_id=knight_id,
        status=ReferralStatus.COMPLETED,
        deadline=now + timedelta(weeks=3),
        extensions_granted=0,
        recommendation=ReferralRecommendation.ACKNOWLEDGE,
        rationale="Done",
        created_at=now,
        completed_at=now,
    )
    repo.add(referral)

    can_extend = await service.can_extend(referral.referral_id)
    assert can_extend is False


@pytest.mark.asyncio
async def test_can_extend_not_found(
    service: ExtensionRequestService,
) -> None:
    """Test can_extend raises error for non-existent referral."""
    with pytest.raises(ReferralNotFoundError):
        await service.can_extend(uuid4())
