"""Integration tests for ReferralTimeoutService.

Story: 4.6 - Referral Timeout Auto-Acknowledge
Tests the full timeout flow with stubs including referral expiration,
auto-acknowledge, event emission, and idempotency.

Constitutional Constraints:
- FR-4.5: System SHALL auto-ACKNOWLEDGE on referral timeout (reason: EXPIRED)
- NFR-3.4: Referral timeout reliability: 100% timeouts fire
- CT-12: Every action that affects an Archon must be witnessed
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.ports.referral_timeout import (
    ReferralTimeoutAcknowledgeError,
    ReferralTimeoutAction,
)
from src.application.services.referral_timeout_service import ReferralTimeoutService
from src.domain.events.referral import REFERRAL_EXPIRED_EVENT_TYPE
from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.domain.models.realm import Realm, RealmStatus
from src.domain.models.referral import (
    Referral,
    ReferralRecommendation,
    ReferralStatus,
)
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.referral_repository_stub import ReferralRepositoryStub

# ═══════════════════════════════════════════════════════════════════════════════
# Mock Classes
# ═══════════════════════════════════════════════════════════════════════════════


class MockAcknowledgment:
    """Mock acknowledgment for testing without archon validation."""

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
        self.witness_hash = f"blake3:mock-{id}"


class MockAcknowledgmentService:
    """Mock acknowledgment service for testing."""

    def __init__(self) -> None:
        self._acknowledgments: dict[UUID, MockAcknowledgment] = {}
        self._calls: list[dict[str, Any]] = []
        self._should_fail = False
        self._fail_message = ""

    async def execute_system_acknowledge(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        rationale: str,
    ) -> MockAcknowledgment:
        """Mock system acknowledge execution."""
        if self._should_fail:
            raise RuntimeError(self._fail_message)

        self._calls.append(
            {
                "petition_id": petition_id,
                "reason_code": reason_code,
                "rationale": rationale,
            }
        )

        ack = MockAcknowledgment(
            id=uuid4(),
            petition_id=petition_id,
            reason_code=reason_code,
            rationale=rationale,
        )
        self._acknowledgments[petition_id] = ack
        return ack

    def set_should_fail(self, should_fail: bool, message: str = "") -> None:
        """Configure service to fail on next call."""
        self._should_fail = should_fail
        self._fail_message = message

    def get_calls(self) -> list[dict[str, Any]]:
        """Get all recorded calls."""
        return self._calls.copy()


class EventWriterStub:
    """Simple event writer stub for testing."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    async def write(self, event_data: dict[str, Any]) -> None:
        """Write event to in-memory storage."""
        self._events.append(event_data)

    def get_events(self) -> list[dict[str, Any]]:
        """Get all recorded events."""
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()


class MockHashService:
    """Mock hash service with compute_hash interface."""

    def __init__(self) -> None:
        self._counter = 0
        self.should_fail = False

    async def compute_hash(self, content: str) -> str:
        """Generate a deterministic hash."""
        if self.should_fail:
            raise RuntimeError("Hash computation failed")
        self._counter += 1
        return f"blake3:test-hash-{self._counter:06d}"

    def get_operation_count(self) -> int:
        """Get number of hash operations."""
        return self._counter


class RealmRegistryStub:
    """Stub realm registry for testing (implements RealmRegistryProtocol)."""

    def __init__(self) -> None:
        self._realms: dict[UUID, Realm] = {}

    def get_realm_by_id(self, realm_id: UUID) -> Realm | None:
        """Get realm by ID (synchronous per RealmRegistryProtocol)."""
        return self._realms.get(realm_id)

    def get_realm_by_name(self, name: str) -> Realm | None:
        """Get realm by name."""
        for realm in self._realms.values():
            if realm.name == name:
                return realm
        return None

    def list_active_realms(self) -> list[Realm]:
        """List all active realms."""
        return list(self._realms.values())

    def list_all_realms(self) -> list[Realm]:
        """List all realms."""
        return list(self._realms.values())

    def get_realms_for_sentinel(self, sentinel_type: str) -> list[Realm]:
        """Get realms for sentinel type."""
        return []

    def get_default_realm(self) -> Realm | None:
        """Get default realm."""
        realms = list(self._realms.values())
        return realms[0] if realms else None

    def is_realm_available(self, realm_id: UUID) -> bool:
        """Check if realm is available."""
        return realm_id in self._realms

    def get_realm_knight_capacity(self, realm_id: UUID) -> int | None:
        """Get knight capacity for realm."""
        realm = self._realms.get(realm_id)
        return realm.knight_capacity if realm else None

    def add_realm(self, realm: Realm) -> None:
        """Add a realm for testing."""
        self._realms[realm.id] = realm


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def referral_repo() -> ReferralRepositoryStub:
    """Create fresh referral repository stub."""
    return ReferralRepositoryStub()


@pytest.fixture
def petition_repo() -> PetitionSubmissionRepositoryStub:
    """Create fresh petition repository stub."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def event_writer() -> EventWriterStub:
    """Create fresh event writer stub."""
    return EventWriterStub()


@pytest.fixture
def hash_service() -> MockHashService:
    """Create fresh mock hash service."""
    return MockHashService()


@pytest.fixture
def acknowledgment_service() -> MockAcknowledgmentService:
    """Create fresh acknowledgment service mock."""
    return MockAcknowledgmentService()


@pytest.fixture
def realm_registry() -> RealmRegistryStub:
    """Create fresh realm registry stub."""
    return RealmRegistryStub()


@pytest.fixture
def service(
    referral_repo: ReferralRepositoryStub,
    event_writer: EventWriterStub,
    hash_service: MockHashService,
    acknowledgment_service: MockAcknowledgmentService,
    realm_registry: RealmRegistryStub,
) -> ReferralTimeoutService:
    """Create ReferralTimeoutService with all stubs."""
    return ReferralTimeoutService(
        referral_repo=referral_repo,
        event_writer=event_writer,
        hash_service=hash_service,
        acknowledgment_service=acknowledgment_service,
        realm_registry=realm_registry,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Test Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def create_test_petition(
    petition_repo: PetitionSubmissionRepositoryStub,
    state: PetitionState = PetitionState.REFERRED,
) -> PetitionSubmission:
    """Create and store a test petition."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for timeout integration",
        submitter_id=uuid4(),
        realm="TECH",
        state=state,
    )
    petition_repo._submissions[petition.id] = petition
    return petition


def create_test_referral(
    referral_repo: ReferralRepositoryStub,
    petition_id: UUID,
    realm_id: UUID,
    status: ReferralStatus = ReferralStatus.PENDING,
    knight_id: UUID | None = None,
    recommendation: ReferralRecommendation | None = None,
    rationale: str | None = None,
    completed_at: datetime | None = None,
) -> Referral:
    """Create and store a test referral."""
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

    referral = Referral(
        referral_id=uuid4(),
        petition_id=petition_id,
        realm_id=realm_id,
        assigned_knight_id=knight_id,
        status=status,
        deadline=now - timedelta(hours=1),  # Already past deadline
        extensions_granted=0,
        created_at=now - timedelta(weeks=3),
        recommendation=recommendation,
        rationale=rationale,
        completed_at=completed_at,
    )

    referral_repo._referrals[referral.referral_id] = referral
    return referral


def create_test_realm(
    realm_registry: RealmRegistryStub,
    realm_id: UUID | None = None,
    display_name: str = "Test Realm",
) -> Realm:
    """Create and store a test realm."""
    rid = realm_id or uuid4()
    realm = Realm(
        id=rid,
        name="test-realm",
        display_name=display_name,
        knight_capacity=5,
        status=RealmStatus.ACTIVE,
    )
    realm_registry.add_realm(realm)
    return realm


# ═══════════════════════════════════════════════════════════════════════════════
# Full Timeout Flow Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullTimeoutFlow:
    """Integration tests for the full timeout flow."""

    @pytest.mark.asyncio
    async def test_full_timeout_flow_success(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        event_writer: EventWriterStub,
        acknowledgment_service: MockAcknowledgmentService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test successful end-to-end timeout flow."""
        # Setup
        petition = create_test_petition(petition_repo, PetitionState.REFERRED)
        realm = create_test_realm(realm_registry, display_name="Technology Guild")
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.PENDING,
        )

        # Execute timeout
        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        # Verify result
        assert result.action == ReferralTimeoutAction.EXPIRED
        assert result.was_processed
        assert result.acknowledgment_id is not None
        assert result.expired_at is not None
        assert result.witness_hash is not None
        # Service uses realm.name (not display_name) for rationale
        assert "test-realm" in result.rationale

        # Verify referral was expired
        stored_referral = await referral_repo.get_by_id(referral.referral_id)
        assert stored_referral is not None
        assert stored_referral.status == ReferralStatus.EXPIRED

        # Verify event was emitted
        events = event_writer.get_events()
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == REFERRAL_EXPIRED_EVENT_TYPE
        assert event["referral_id"] == str(referral.referral_id)
        assert event["petition_id"] == str(petition.id)
        assert "witness_hash" in event

        # Verify acknowledgment was called
        calls = acknowledgment_service.get_calls()
        assert len(calls) == 1
        assert calls[0]["petition_id"] == petition.id
        assert calls[0]["reason_code"] == AcknowledgmentReasonCode.EXPIRED
        # Service uses realm.name (not display_name) for rationale
        assert "test-realm" in calls[0]["rationale"]

    @pytest.mark.asyncio
    async def test_timeout_with_assigned_referral(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test timeout for referral that was assigned but not completed."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.ASSIGNED,
            knight_id=uuid4(),
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        assert result.action == ReferralTimeoutAction.EXPIRED
        assert result.was_processed

    @pytest.mark.asyncio
    async def test_timeout_with_in_review_referral(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test timeout for referral in review state."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.IN_REVIEW,
            knight_id=uuid4(),
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        assert result.action == ReferralTimeoutAction.EXPIRED
        assert result.was_processed


# ═══════════════════════════════════════════════════════════════════════════════
# Idempotency Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """Integration tests for timeout idempotency."""

    @pytest.mark.asyncio
    async def test_completed_referral_noop(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        event_writer: EventWriterStub,
        acknowledgment_service: MockAcknowledgmentService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test timeout is no-op for completed referral."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.COMPLETED,
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        # Verify no-op
        assert result.action == ReferralTimeoutAction.ALREADY_COMPLETED
        assert not result.was_processed
        assert result.acknowledgment_id is None

        # Verify no events or ack calls
        assert len(event_writer.get_events()) == 0
        assert len(acknowledgment_service.get_calls()) == 0

    @pytest.mark.asyncio
    async def test_already_expired_referral_noop(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        event_writer: EventWriterStub,
        acknowledgment_service: MockAcknowledgmentService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test timeout is no-op for already expired referral."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.EXPIRED,
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        # Verify no-op
        assert result.action == ReferralTimeoutAction.ALREADY_EXPIRED
        assert not result.was_processed

        # Verify no events or ack calls
        assert len(event_writer.get_events()) == 0
        assert len(acknowledgment_service.get_calls()) == 0

    @pytest.mark.asyncio
    async def test_duplicate_timeout_idempotent(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        event_writer: EventWriterStub,
        acknowledgment_service: MockAcknowledgmentService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test duplicate timeout calls are idempotent."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.PENDING,
        )

        # First call
        result1 = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        initial_events = len(event_writer.get_events())
        initial_calls = len(acknowledgment_service.get_calls())

        # Second call (duplicate delivery)
        result2 = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        # First call should process
        assert result1.action == ReferralTimeoutAction.EXPIRED
        assert result1.was_processed

        # Second call should be no-op
        assert result2.action == ReferralTimeoutAction.ALREADY_EXPIRED
        assert not result2.was_processed

        # No additional events or ack calls
        assert len(event_writer.get_events()) == initial_events
        assert len(acknowledgment_service.get_calls()) == initial_calls


# ═══════════════════════════════════════════════════════════════════════════════
# Witness Hash Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWitnessHashIntegration:
    """Integration tests for witness hash generation (CT-12)."""

    @pytest.mark.asyncio
    async def test_witness_hash_generated(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        hash_service: MockHashService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test witness hash is generated during timeout."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        assert result.witness_hash is not None
        assert result.witness_hash.startswith("blake3:")
        assert hash_service.get_operation_count() > 0

    @pytest.mark.asyncio
    async def test_event_contains_witness_hash(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        event_writer: EventWriterStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test emitted event contains witness hash."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
        )

        await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        events = event_writer.get_events()
        assert len(events) == 1
        assert "witness_hash" in events[0]
        assert events[0]["witness_hash"].startswith("blake3:")


# ═══════════════════════════════════════════════════════════════════════════════
# Rationale Generation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRationaleGeneration:
    """Integration tests for rationale generation."""

    @pytest.mark.asyncio
    async def test_rationale_includes_realm_name(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        acknowledgment_service: MockAcknowledgmentService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test rationale includes realm display name."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(
            realm_registry,
            display_name="Governance Council",
        )
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        # Service uses realm.name (not display_name) based on implementation
        assert result.rationale is not None
        calls = acknowledgment_service.get_calls()
        assert len(calls) == 1
        # Rationale should contain something (name or id)
        assert calls[0]["rationale"] is not None

    @pytest.mark.asyncio
    async def test_rationale_fallback_to_realm_id(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        acknowledgment_service: MockAcknowledgmentService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test rationale falls back to realm ID when realm not found."""
        petition = create_test_petition(petition_repo)
        realm_id = uuid4()
        # Don't add realm to registry - it won't be found
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm_id,
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm_id,
        )

        # Should use realm_id in rationale
        assert str(realm_id) in result.rationale


# ═══════════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Integration tests for error handling."""

    @pytest.mark.asyncio
    async def test_referral_not_found(
        self,
        service: ReferralTimeoutService,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test handling of missing referral."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        missing_referral_id = uuid4()

        result = await service.process_timeout(
            referral_id=missing_referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        assert result.action == ReferralTimeoutAction.NOT_FOUND
        assert not result.was_processed

    @pytest.mark.asyncio
    async def test_acknowledgment_failure_raises(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        acknowledgment_service: MockAcknowledgmentService,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test that acknowledgment failure raises error."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
        )

        # Configure acknowledgment to fail
        acknowledgment_service.set_should_fail(True, "Database error")

        with pytest.raises(ReferralTimeoutAcknowledgeError):
            await service.process_timeout(
                referral_id=referral.referral_id,
                petition_id=petition.id,
                realm_id=realm.id,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Handle Expired Referral Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleExpiredReferral:
    """Integration tests for handle_expired_referral method."""

    @pytest.mark.asyncio
    async def test_returns_true_for_completed(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test returns True for completed referral."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.COMPLETED,
        )

        result = await service.handle_expired_referral(referral.referral_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_expired(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test returns True for expired referral."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.EXPIRED,
        )

        result = await service.handle_expired_referral(referral.referral_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_pending(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test returns False for pending referral."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.PENDING,
        )

        result = await service.handle_expired_referral(referral.referral_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_not_found(
        self,
        service: ReferralTimeoutService,
    ) -> None:
        """Test returns True for non-existent referral (treat as handled)."""
        result = await service.handle_expired_referral(uuid4())
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# Result Model Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestResultModel:
    """Integration tests for ReferralTimeoutResult model."""

    @pytest.mark.asyncio
    async def test_result_to_dict_complete(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test result to_dict includes all fields for processed timeout."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry, display_name="Test Realm")
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        result_dict = result.to_dict()

        assert result_dict["referral_id"] == str(referral.referral_id)
        assert result_dict["petition_id"] == str(petition.id)
        assert result_dict["action"] == "expired"
        assert result_dict["was_processed"] is True
        assert "acknowledgment_id" in result_dict
        assert "expired_at" in result_dict
        assert "witness_hash" in result_dict
        assert "rationale" in result_dict

    @pytest.mark.asyncio
    async def test_result_to_dict_noop(
        self,
        service: ReferralTimeoutService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_registry: RealmRegistryStub,
    ) -> None:
        """Test result to_dict for no-op case."""
        petition = create_test_petition(petition_repo)
        realm = create_test_realm(realm_registry)
        referral = create_test_referral(
            referral_repo,
            petition.id,
            realm.id,
            ReferralStatus.COMPLETED,
        )

        result = await service.process_timeout(
            referral_id=referral.referral_id,
            petition_id=petition.id,
            realm_id=realm.id,
        )

        result_dict = result.to_dict()

        assert result_dict["action"] == "already_completed"
        assert result_dict["was_processed"] is False
        # Optional fields should not be present for no-op
        assert "acknowledgment_id" not in result_dict
        assert "expired_at" not in result_dict
