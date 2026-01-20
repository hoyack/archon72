"""Unit tests for ReferralTimeoutService (Story 4.6, FR-4.5).

This module tests the referral timeout service implementation.

Test Coverage:
- AC-1: Timeout triggers expiration and auto-acknowledge
- AC-2: Completed referral no-op
- AC-3: Already expired no-op (idempotency)
- AC-4: Witness hash generation (CT-12)
- AC-5: Petition state transition (REFERRED -> ACKNOWLEDGED)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.ports.referral_timeout import (
    ReferralTimeoutAcknowledgeError,
    ReferralTimeoutAction,
    ReferralTimeoutResult,
    ReferralTimeoutWitnessError,
)
from src.application.services.referral_timeout_service import (
    ReferralTimeoutService,
)
from src.domain.events.referral import REFERRAL_EXPIRED_EVENT_TYPE
from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode
from src.domain.models.realm import Realm, RealmStatus
from src.domain.models.referral import (
    Referral,
    ReferralRecommendation,
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

    async def save(self, referral: Referral) -> None:
        """Save a referral."""
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
        self.should_fail = False

    async def compute_hash(self, content: str) -> str:
        """Generate a deterministic hash."""
        if self.should_fail:
            raise RuntimeError("Hash computation failed")
        self._counter += 1
        return f"blake3:test-hash-{self._counter:06d}"


class MockAcknowledgment:
    """Simple mock acknowledgment for testing."""

    def __init__(
        self,
        id: UUID,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        rationale: str,
    ) -> None:
        self.id = id
        self.petition_id = petition_id
        self.reason_code = reason_code
        self.rationale = rationale
        self.acknowledging_archon_ids: tuple[int, ...] = ()
        self.acknowledged_at = datetime.now(timezone.utc)


class MockAcknowledgmentService:
    """Mock acknowledgment service for testing."""

    def __init__(self) -> None:
        self.acknowledgments: list[MockAcknowledgment] = []
        self.should_fail = False
        self._counter = 0

    async def execute_system_acknowledge(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        rationale: str,
    ) -> MockAcknowledgment:
        """Execute system acknowledgment."""
        if self.should_fail:
            raise RuntimeError("Acknowledgment failed")
        self._counter += 1
        ack = MockAcknowledgment(
            id=uuid4(),
            petition_id=petition_id,
            reason_code=reason_code,
            rationale=rationale,
        )
        self.acknowledgments.append(ack)
        return ack


class MockRealmRegistry:
    """Mock realm registry for testing."""

    def __init__(self) -> None:
        self._realms: dict[UUID, Realm] = {}

    def add(self, realm: Realm) -> None:
        """Add a realm."""
        self._realms[realm.id] = realm

    def get_realm_by_id(self, realm_id: UUID) -> Realm | None:
        """Get realm by ID."""
        return self._realms.get(realm_id)


def create_test_referral(
    referral_id: UUID | None = None,
    petition_id: UUID | None = None,
    realm_id: UUID | None = None,
    knight_id: UUID | None = None,
    status: ReferralStatus = ReferralStatus.PENDING,
    extensions_granted: int = 0,
    deadline: datetime | None = None,
    recommendation: ReferralRecommendation | None = None,
    rationale: str | None = None,
    completed_at: datetime | None = None,
) -> Referral:
    """Create a test referral with default values."""
    now = datetime.now(timezone.utc)

    # Handle COMPLETED status requirements
    if status == ReferralStatus.COMPLETED:
        if recommendation is None:
            recommendation = ReferralRecommendation.ACKNOWLEDGE
        if rationale is None:
            rationale = "Test rationale for completion"
        if completed_at is None:
            completed_at = now
        if knight_id is None:
            knight_id = uuid4()

    return Referral(
        referral_id=referral_id or uuid4(),
        petition_id=petition_id or uuid4(),
        realm_id=realm_id or uuid4(),
        assigned_knight_id=knight_id,
        status=status,
        deadline=deadline or (now + timedelta(weeks=3)),
        extensions_granted=extensions_granted,
        created_at=now,
        recommendation=recommendation,
        rationale=rationale,
        completed_at=completed_at,
    )


def create_test_realm(
    realm_id: UUID | None = None,
    name: str = "test_realm",
) -> Realm:
    """Create a test realm."""
    return Realm(
        id=realm_id or uuid4(),
        name=name,
        display_name=name.replace("_", " ").title(),
        description="Test realm",
        status=RealmStatus.ACTIVE,
        knight_capacity=5,
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
def acknowledgment_service() -> MockAcknowledgmentService:
    """Create a mock acknowledgment service."""
    return MockAcknowledgmentService()


@pytest.fixture
def realm_registry() -> MockRealmRegistry:
    """Create a mock realm registry."""
    return MockRealmRegistry()


@pytest.fixture
def service(
    repo: MockReferralRepository,
    acknowledgment_service: MockAcknowledgmentService,
    event_writer: MockEventWriter,
    hash_service: MockHashService,
    realm_registry: MockRealmRegistry,
) -> ReferralTimeoutService:
    """Create the referral timeout service."""
    return ReferralTimeoutService(
        referral_repo=repo,
        acknowledgment_service=acknowledgment_service,
        event_writer=event_writer,
        hash_service=hash_service,
        realm_registry=realm_registry,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - AC-1: Timeout Triggers Expiration
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_timeout_expires_pending_referral(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
    event_writer: MockEventWriter,
    acknowledgment_service: MockAcknowledgmentService,
) -> None:
    """Test that timeout expires a PENDING referral."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    # Setup
    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.PENDING,
    )
    repo.add(referral)

    realm = create_test_realm(realm_id=realm_id, name="test_domain")
    realm_registry.add(realm)

    # Execute
    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    # Verify result
    assert result.action == ReferralTimeoutAction.EXPIRED
    assert result.was_processed is True
    assert result.acknowledgment_id is not None
    assert result.witness_hash is not None
    assert "test_domain" in (result.rationale or "")

    # Verify referral was updated
    updated_referral = await repo.get_by_id(referral_id)
    assert updated_referral is not None
    assert updated_referral.status == ReferralStatus.EXPIRED

    # Verify event was emitted
    assert len(event_writer.events) == 1
    assert event_writer.events[0]["event_type"] == REFERRAL_EXPIRED_EVENT_TYPE

    # Verify acknowledgment was created
    assert len(acknowledgment_service.acknowledgments) == 1


@pytest.mark.asyncio
async def test_process_timeout_expires_assigned_referral(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
) -> None:
    """Test that timeout expires an ASSIGNED referral."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()
    knight_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        knight_id=knight_id,
        status=ReferralStatus.ASSIGNED,
    )
    repo.add(referral)
    realm_registry.add(create_test_realm(realm_id=realm_id))

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    assert result.action == ReferralTimeoutAction.EXPIRED
    updated = await repo.get_by_id(referral_id)
    assert updated is not None
    assert updated.status == ReferralStatus.EXPIRED


@pytest.mark.asyncio
async def test_process_timeout_expires_in_review_referral(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
) -> None:
    """Test that timeout expires an IN_REVIEW referral."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()
    knight_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
    )
    repo.add(referral)
    realm_registry.add(create_test_realm(realm_id=realm_id))

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    assert result.action == ReferralTimeoutAction.EXPIRED


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - AC-2: Completed Referral No-Op
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_timeout_noop_for_completed_referral(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    event_writer: MockEventWriter,
    acknowledgment_service: MockAcknowledgmentService,
) -> None:
    """Test that timeout is no-op for COMPLETED referral."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.COMPLETED,
    )
    repo.add(referral)

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    # Verify no-op result
    assert result.action == ReferralTimeoutAction.ALREADY_COMPLETED
    assert result.was_processed is False
    assert "completed before timeout" in result.message.lower()

    # Verify no events emitted
    assert len(event_writer.events) == 0

    # Verify no acknowledgment created
    assert len(acknowledgment_service.acknowledgments) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - AC-3: Already Expired No-Op (Idempotency)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_timeout_noop_for_already_expired(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    event_writer: MockEventWriter,
    acknowledgment_service: MockAcknowledgmentService,
) -> None:
    """Test that timeout is idempotent for already expired referral."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    # Create an already expired referral
    now = datetime.now(timezone.utc)
    referral = Referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        deadline=now - timedelta(days=1),
        created_at=now - timedelta(days=7),
        status=ReferralStatus.EXPIRED,
        completed_at=now - timedelta(hours=1),  # Already expired
    )
    repo.add(referral)

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    # Verify idempotent no-op result
    assert result.action == ReferralTimeoutAction.ALREADY_EXPIRED
    assert result.was_processed is False
    assert "already expired" in result.message.lower()

    # Verify no duplicate events
    assert len(event_writer.events) == 0
    assert len(acknowledgment_service.acknowledgments) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - AC-4: Witness Hash Generation (CT-12)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_timeout_generates_witness_hash(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
    event_writer: MockEventWriter,
) -> None:
    """Test that timeout generates witness hash per CT-12."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.PENDING,
    )
    repo.add(referral)
    realm_registry.add(create_test_realm(realm_id=realm_id))

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    # Verify witness hash exists
    assert result.witness_hash is not None
    assert result.witness_hash.startswith("blake3:")

    # Verify hash in event
    assert len(event_writer.events) == 1
    assert event_writer.events[0]["witness_hash"] == result.witness_hash


@pytest.mark.asyncio
async def test_process_timeout_fails_on_hash_error(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
    hash_service: MockHashService,
) -> None:
    """Test that timeout fails properly when hash generation fails."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.PENDING,
    )
    repo.add(referral)
    realm_registry.add(create_test_realm(realm_id=realm_id))

    # Make hash service fail
    hash_service.should_fail = True

    with pytest.raises(ReferralTimeoutWitnessError) as exc_info:
        await service.process_timeout(
            referral_id=referral_id,
            petition_id=petition_id,
            realm_id=realm_id,
        )

    assert exc_info.value.referral_id == referral_id
    assert exc_info.value.petition_id == petition_id


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - AC-5: Event Emission
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_timeout_emits_referral_expired_event(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
    event_writer: MockEventWriter,
) -> None:
    """Test that timeout emits ReferralExpiredEvent."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.PENDING,
    )
    repo.add(referral)
    realm_registry.add(create_test_realm(realm_id=realm_id))

    await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    # Verify event
    assert len(event_writer.events) == 1
    event = event_writer.events[0]
    assert event["event_type"] == REFERRAL_EXPIRED_EVENT_TYPE
    assert event["referral_id"] == str(referral_id)
    assert event["petition_id"] == str(petition_id)
    assert event["realm_id"] == str(realm_id)
    assert "expired_at" in event
    assert "witness_hash" in event


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - Rationale Generation
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_timeout_sets_correct_rationale(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
    acknowledgment_service: MockAcknowledgmentService,
) -> None:
    """Test that timeout sets correct rationale with realm name."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.PENDING,
    )
    repo.add(referral)

    realm = create_test_realm(realm_id=realm_id, name="privacy_realm")
    realm_registry.add(realm)

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    # Verify rationale contains realm name
    assert result.rationale is not None
    assert "privacy_realm" in result.rationale
    assert "expired without Knight response" in result.rationale

    # Verify acknowledgment has same rationale
    assert len(acknowledgment_service.acknowledgments) == 1
    ack = acknowledgment_service.acknowledgments[0]
    assert ack.rationale == result.rationale


@pytest.mark.asyncio
async def test_process_timeout_uses_realm_id_when_realm_not_found(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
) -> None:
    """Test that timeout uses realm_id when realm name not found."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.PENDING,
    )
    repo.add(referral)
    # Don't add realm to registry - should fallback to realm_id

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    # Rationale should contain realm_id as string
    assert result.rationale is not None
    assert str(realm_id) in result.rationale


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - Error Handling
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_timeout_handles_referral_not_found(
    service: ReferralTimeoutService,
) -> None:
    """Test that timeout handles referral not found."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    result = await service.process_timeout(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
    )

    assert result.action == ReferralTimeoutAction.NOT_FOUND
    assert result.was_processed is False
    assert "not found" in result.message.lower()


@pytest.mark.asyncio
async def test_process_timeout_raises_on_acknowledge_error(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
    realm_registry: MockRealmRegistry,
    acknowledgment_service: MockAcknowledgmentService,
) -> None:
    """Test that timeout raises error when auto-acknowledge fails."""
    referral_id = uuid4()
    petition_id = uuid4()
    realm_id = uuid4()

    referral = create_test_referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        status=ReferralStatus.PENDING,
    )
    repo.add(referral)
    realm_registry.add(create_test_realm(realm_id=realm_id))

    # Make acknowledgment service fail
    acknowledgment_service.should_fail = True

    with pytest.raises(ReferralTimeoutAcknowledgeError) as exc_info:
        await service.process_timeout(
            referral_id=referral_id,
            petition_id=petition_id,
            realm_id=realm_id,
        )

    assert exc_info.value.referral_id == referral_id
    assert exc_info.value.petition_id == petition_id


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - handle_expired_referral
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_handle_expired_referral_returns_true_for_completed(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
) -> None:
    """Test that handle_expired_referral returns True for COMPLETED."""
    referral = create_test_referral(status=ReferralStatus.COMPLETED)
    repo.add(referral)

    result = await service.handle_expired_referral(referral.referral_id)
    assert result is True


@pytest.mark.asyncio
async def test_handle_expired_referral_returns_true_for_expired(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
) -> None:
    """Test that handle_expired_referral returns True for EXPIRED."""
    now = datetime.now(timezone.utc)
    referral = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        deadline=now - timedelta(days=1),
        created_at=now - timedelta(days=7),
        status=ReferralStatus.EXPIRED,
        completed_at=now,
    )
    repo.add(referral)

    result = await service.handle_expired_referral(referral.referral_id)
    assert result is True


@pytest.mark.asyncio
async def test_handle_expired_referral_returns_false_for_pending(
    service: ReferralTimeoutService,
    repo: MockReferralRepository,
) -> None:
    """Test that handle_expired_referral returns False for PENDING."""
    referral = create_test_referral(status=ReferralStatus.PENDING)
    repo.add(referral)

    result = await service.handle_expired_referral(referral.referral_id)
    assert result is False


@pytest.mark.asyncio
async def test_handle_expired_referral_returns_true_for_not_found(
    service: ReferralTimeoutService,
) -> None:
    """Test that handle_expired_referral returns True when not found."""
    result = await service.handle_expired_referral(uuid4())
    assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# Test Cases - Result Model
# ═══════════════════════════════════════════════════════════════════════════════


def test_referral_timeout_result_to_dict() -> None:
    """Test ReferralTimeoutResult.to_dict()."""
    referral_id = uuid4()
    petition_id = uuid4()
    ack_id = uuid4()
    expired_at = datetime.now(timezone.utc)

    result = ReferralTimeoutResult(
        referral_id=referral_id,
        petition_id=petition_id,
        action=ReferralTimeoutAction.EXPIRED,
        acknowledgment_id=ack_id,
        expired_at=expired_at,
        witness_hash="blake3:abc123",
        rationale="Test rationale",
        message="Test message",
    )

    result_dict = result.to_dict()

    assert result_dict["referral_id"] == str(referral_id)
    assert result_dict["petition_id"] == str(petition_id)
    assert result_dict["action"] == "expired"
    assert result_dict["was_processed"] is True
    assert result_dict["acknowledgment_id"] == str(ack_id)
    assert result_dict["expired_at"] == expired_at.isoformat()
    assert result_dict["witness_hash"] == "blake3:abc123"
    assert result_dict["rationale"] == "Test rationale"


def test_referral_timeout_result_was_processed() -> None:
    """Test ReferralTimeoutResult.was_processed property."""
    # EXPIRED -> was_processed = True
    expired_result = ReferralTimeoutResult(
        referral_id=uuid4(),
        petition_id=uuid4(),
        action=ReferralTimeoutAction.EXPIRED,
    )
    assert expired_result.was_processed is True

    # ALREADY_COMPLETED -> was_processed = False
    completed_result = ReferralTimeoutResult(
        referral_id=uuid4(),
        petition_id=uuid4(),
        action=ReferralTimeoutAction.ALREADY_COMPLETED,
    )
    assert completed_result.was_processed is False

    # ALREADY_EXPIRED -> was_processed = False
    already_expired_result = ReferralTimeoutResult(
        referral_id=uuid4(),
        petition_id=uuid4(),
        action=ReferralTimeoutAction.ALREADY_EXPIRED,
    )
    assert already_expired_result.was_processed is False

    # NOT_FOUND -> was_processed = False
    not_found_result = ReferralTimeoutResult(
        referral_id=uuid4(),
        petition_id=uuid4(),
        action=ReferralTimeoutAction.NOT_FOUND,
    )
    assert not_found_result.was_processed is False
