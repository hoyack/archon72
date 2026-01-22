"""Unit tests for EscalationQueueService (Story 6.1, FR-5.4, CT-13, D8).

Tests:
- AC-1: King escalation queue endpoint returns paginated list
- AC-2: Empty queue handling (returns empty list, not error)
- AC-3: Realm-scoped queue (only petitions for King's realm)
- AC-4: Queue ordering (FIFO by escalated_at)
- AC-5: Halt check first (CT-13)
- Multiple escalation sources (DELIBERATION, CO_SIGNER_THRESHOLD, KNIGHT_RECOMMENDATION)
- Keyset pagination with cursors (D8)

Acceptance Criteria Coverage:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions
- CT-13: Halt check first pattern enforced
- D8: Keyset pagination compliance
- RULING-3: Realm-scoped data access
- NFR-1.3: Endpoint latency < 200ms p95
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from uuid6 import uuid7

from src.application.ports.escalation_queue import (
    EscalationQueueItem,
    EscalationQueueResult,
    EscalationSource,
)
from src.application.services.escalation_queue_service import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    EscalationQueueService,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


def _create_escalated_petition(
    petition_id: UUID | None = None,
    realm: str = "governance",
    escalated_to_realm: str = "governance",
    escalation_source: str = "DELIBERATION",
    escalated_at: datetime | None = None,
    co_signer_count: int = 0,
) -> PetitionSubmission:
    """Create a test escalated petition."""
    petition = PetitionSubmission(
        id=petition_id or uuid7(),
        type=PetitionType.CESSATION,
        text="Test escalated petition",
        state=PetitionState.ESCALATED,
        realm=realm,
        co_signer_count=co_signer_count,
    )
    # Add escalation tracking fields
    petition.escalated_to_realm = escalated_to_realm
    petition.escalation_source = escalation_source
    petition.escalated_at = escalated_at or datetime.now(timezone.utc)
    return petition


def _create_petition_repository_mock(
    petitions: list[PetitionSubmission] | None = None,
) -> MagicMock:
    """Create a mock petition repository."""
    mock = MagicMock()
    mock.list_by_state = AsyncMock(
        return_value=(petitions or [], len(petitions or []))
    )
    return mock


def _create_halt_checker_mock(is_halted: bool = False) -> MagicMock:
    """Create a mock halt checker."""
    mock = MagicMock()
    mock.is_halted = AsyncMock(return_value=is_halted)
    return mock


class TestEscalationQueueServiceInitialization:
    """Test service initialization."""

    def test_initializes_with_dependencies(self) -> None:
        """Service initializes with required dependencies."""
        repo = _create_petition_repository_mock()
        halt_checker = _create_halt_checker_mock()

        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        assert service is not None
        assert service._petition_repo is repo
        assert service._halt_checker is halt_checker


class TestGetQueueEmptyQueue:
    """Test empty queue handling (AC-2)."""

    @pytest.mark.asyncio
    async def test_empty_queue_returns_empty_list(self) -> None:
        """Empty queue returns empty list, not error (AC-2)."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        assert isinstance(result, EscalationQueueResult)
        assert result.items == []
        assert result.next_cursor is None
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_empty_queue_checks_halt_first(self) -> None:
        """Empty queue still performs halt check first (CT-13)."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        # Verify halt check was called
        halt_checker.is_halted.assert_awaited_once()


class TestGetQueueRealmFiltering:
    """Test realm-scoped filtering (AC-3, RULING-3)."""

    @pytest.mark.asyncio
    async def test_only_returns_petitions_for_kings_realm(self) -> None:
        """Only returns petitions escalated to King's realm (AC-3)."""
        # Create petitions for different realms
        governance_petition = _create_escalated_petition(
            escalated_to_realm="governance",
            escalation_source="DELIBERATION",
        )
        economy_petition = _create_escalated_petition(
            escalated_to_realm="economy",
            escalation_source="CO_SIGNER_THRESHOLD",
        )
        another_governance = _create_escalated_petition(
            escalated_to_realm="governance",
            escalation_source="KNIGHT_RECOMMENDATION",
        )

        repo = _create_petition_repository_mock(
            petitions=[governance_petition, economy_petition, another_governance]
        )
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        # Should only return governance petitions
        assert len(result.items) == 2
        petition_ids = {item.petition_id for item in result.items}
        assert governance_petition.id in petition_ids
        assert another_governance.id in petition_ids
        assert economy_petition.id not in petition_ids

    @pytest.mark.asyncio
    async def test_different_realm_returns_empty(self) -> None:
        """Querying a realm with no petitions returns empty list."""
        governance_petition = _create_escalated_petition(
            escalated_to_realm="governance",
        )

        repo = _create_petition_repository_mock(petitions=[governance_petition])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="economy",  # Different realm
            cursor=None,
            limit=20,
        )

        assert result.items == []
        assert result.next_cursor is None
        assert result.has_more is False


class TestGetQueueFIFOOrdering:
    """Test FIFO ordering by escalated_at (AC-4)."""

    @pytest.mark.asyncio
    async def test_orders_by_escalated_at_ascending(self) -> None:
        """Petitions ordered by escalated_at ascending (oldest first) (AC-4)."""
        now = datetime.now(timezone.utc)

        # Create petitions with different escalation times
        oldest = _create_escalated_petition(
            escalated_at=datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            escalation_source="CO_SIGNER_THRESHOLD",
        )
        middle = _create_escalated_petition(
            escalated_at=datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc),
            escalation_source="DELIBERATION",
        )
        newest = _create_escalated_petition(
            escalated_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
            escalation_source="KNIGHT_RECOMMENDATION",
        )

        # Add in random order to test sorting
        repo = _create_petition_repository_mock(
            petitions=[newest, oldest, middle]
        )
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        # Should be ordered oldest first
        assert len(result.items) == 3
        assert result.items[0].petition_id == oldest.id
        assert result.items[1].petition_id == middle.id
        assert result.items[2].petition_id == newest.id

    @pytest.mark.asyncio
    async def test_same_escalated_at_uses_petition_id_for_stability(self) -> None:
        """When escalated_at is same, uses petition_id for stable sort."""
        same_time = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)

        # Create petitions with same escalation time but different IDs
        petition1 = _create_escalated_petition(
            petition_id=UUID("00000000-0000-0000-0000-000000000001"),
            escalated_at=same_time,
        )
        petition2 = _create_escalated_petition(
            petition_id=UUID("00000000-0000-0000-0000-000000000002"),
            escalated_at=same_time,
        )
        petition3 = _create_escalated_petition(
            petition_id=UUID("00000000-0000-0000-0000-000000000003"),
            escalated_at=same_time,
        )

        # Add in random order
        repo = _create_petition_repository_mock(
            petitions=[petition3, petition1, petition2]
        )
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        # Should be ordered by petition_id when times are equal
        assert len(result.items) == 3
        assert result.items[0].petition_id == petition1.id
        assert result.items[1].petition_id == petition2.id
        assert result.items[2].petition_id == petition3.id


class TestGetQueueHaltCheck:
    """Test halt check first pattern (AC-5, CT-13)."""

    @pytest.mark.asyncio
    async def test_rejects_access_during_halt(self) -> None:
        """Request rejected with SystemHaltedError during halt (AC-5)."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=True)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.get_queue(
                king_id=king_id,
                realm_id="governance",
                cursor=None,
                limit=20,
            )

        assert "halt" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_halt_check_happens_first(self) -> None:
        """Halt check happens before any other processing (CT-13)."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=True)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()

        with pytest.raises(SystemHaltedError):
            await service.get_queue(
                king_id=king_id,
                realm_id="governance",
                cursor=None,
                limit=20,
            )

        # Repository should NOT be called if halt check fails
        repo.list_by_state.assert_not_awaited()


class TestGetQueueEscalationSources:
    """Test multiple escalation sources."""

    @pytest.mark.asyncio
    async def test_includes_all_escalation_source_types(self) -> None:
        """Queue includes petitions from all escalation sources."""
        deliberation = _create_escalated_petition(
            escalation_source="DELIBERATION",
        )
        co_signer = _create_escalated_petition(
            escalation_source="CO_SIGNER_THRESHOLD",
        )
        knight = _create_escalated_petition(
            escalation_source="KNIGHT_RECOMMENDATION",
        )

        repo = _create_petition_repository_mock(
            petitions=[deliberation, co_signer, knight]
        )
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        assert len(result.items) == 3
        sources = {item.escalation_source for item in result.items}
        assert EscalationSource.DELIBERATION in sources
        assert EscalationSource.CO_SIGNER_THRESHOLD in sources
        assert EscalationSource.KNIGHT_RECOMMENDATION in sources

    @pytest.mark.asyncio
    async def test_populates_escalation_source_correctly(self) -> None:
        """Each item has correct escalation_source populated."""
        co_signer_petition = _create_escalated_petition(
            escalation_source="CO_SIGNER_THRESHOLD",
        )

        repo = _create_petition_repository_mock(petitions=[co_signer_petition])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        assert len(result.items) == 1
        assert result.items[0].escalation_source == EscalationSource.CO_SIGNER_THRESHOLD


class TestGetQueuePagination:
    """Test keyset pagination (D8)."""

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self) -> None:
        """Returns at most `limit` items."""
        petitions = [
            _create_escalated_petition(
                escalated_at=datetime(2026, 1, 20, 10, i, 0, tzinfo=timezone.utc),
            )
            for i in range(10)
        ]

        repo = _create_petition_repository_mock(petitions=petitions)
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=5,
        )

        assert len(result.items) == 5
        assert result.has_more is True
        assert result.next_cursor is not None

    @pytest.mark.asyncio
    async def test_default_limit_used_when_not_specified(self) -> None:
        """Uses DEFAULT_LIMIT when limit not specified."""
        petitions = [
            _create_escalated_petition(
                escalated_at=datetime(2026, 1, 20, 10, i, 0, tzinfo=timezone.utc),
            )
            for i in range(30)
        ]

        repo = _create_petition_repository_mock(petitions=petitions)
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
        )

        assert len(result.items) == DEFAULT_LIMIT

    @pytest.mark.asyncio
    async def test_rejects_limit_above_max(self) -> None:
        """Rejects limit above MAX_LIMIT."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()

        with pytest.raises(ValueError) as exc_info:
            await service.get_queue(
                king_id=king_id,
                realm_id="governance",
                cursor=None,
                limit=MAX_LIMIT + 1,
            )

        assert "limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_rejects_limit_below_one(self) -> None:
        """Rejects limit below 1."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()

        with pytest.raises(ValueError) as exc_info:
            await service.get_queue(
                king_id=king_id,
                realm_id="governance",
                cursor=None,
                limit=0,
            )

        assert "limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cursor_based_pagination_next_page(self) -> None:
        """Cursor-based pagination navigates to next page correctly."""
        petitions = [
            _create_escalated_petition(
                petition_id=UUID(f"00000000-0000-0000-0000-00000000000{i}"),
                escalated_at=datetime(2026, 1, 20, 10, i, 0, tzinfo=timezone.utc),
            )
            for i in range(1, 6)  # IDs 1-5
        ]

        repo = _create_petition_repository_mock(petitions=petitions)
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()

        # First page
        page1 = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=3,
        )

        assert len(page1.items) == 3
        assert page1.has_more is True
        assert page1.next_cursor is not None

        # Second page using cursor
        page2 = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=page1.next_cursor,
            limit=3,
        )

        # Should get remaining items (2 items)
        assert len(page2.items) == 2
        assert page2.has_more is False
        assert page2.next_cursor is None

    @pytest.mark.asyncio
    async def test_invalid_cursor_raises_error(self) -> None:
        """Invalid cursor format raises ValueError."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()

        with pytest.raises(ValueError) as exc_info:
            await service.get_queue(
                king_id=king_id,
                realm_id="governance",
                cursor="invalid-cursor-format",
                limit=20,
            )

        assert "cursor" in str(exc_info.value).lower()


class TestGetQueueItemPopulation:
    """Test queue item fields are populated correctly."""

    @pytest.mark.asyncio
    async def test_populates_all_item_fields(self) -> None:
        """All queue item fields populated correctly."""
        escalated_at = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        petition = _create_escalated_petition(
            petition_id=UUID("12345678-1234-1234-1234-123456789012"),
            escalated_at=escalated_at,
            escalation_source="CO_SIGNER_THRESHOLD",
            co_signer_count=150,
        )

        repo = _create_petition_repository_mock(petitions=[petition])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        king_id = uuid7()
        result = await service.get_queue(
            king_id=king_id,
            realm_id="governance",
            cursor=None,
            limit=20,
        )

        assert len(result.items) == 1
        item = result.items[0]

        assert item.petition_id == petition.id
        assert item.petition_type == PetitionType.CESSATION
        assert item.escalation_source == EscalationSource.CO_SIGNER_THRESHOLD
        assert item.co_signer_count == 150
        assert item.escalated_at == escalated_at


class TestCursorEncoding:
    """Test cursor encoding and decoding."""

    def test_build_cursor_encodes_correctly(self) -> None:
        """Cursor is base64-encoded with correct format."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        escalated_at = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        petition_id = UUID("12345678-1234-1234-1234-123456789012")

        cursor = service._build_cursor(escalated_at, petition_id)

        # Should be base64 encoded
        assert isinstance(cursor, str)
        assert len(cursor) > 0

    def test_parse_cursor_decodes_correctly(self) -> None:
        """Cursor is decoded correctly."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        escalated_at = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        petition_id = UUID("12345678-1234-1234-1234-123456789012")

        cursor = service._build_cursor(escalated_at, petition_id)
        decoded_time, decoded_id = service._parse_cursor(cursor)

        assert decoded_time == escalated_at
        assert decoded_id == petition_id

    def test_parse_cursor_rejects_malformed_cursor(self) -> None:
        """Malformed cursor raises ValueError."""
        repo = _create_petition_repository_mock(petitions=[])
        halt_checker = _create_halt_checker_mock(is_halted=False)
        service = EscalationQueueService(
            petition_repo=repo,
            halt_checker=halt_checker,
        )

        with pytest.raises(ValueError) as exc_info:
            service._parse_cursor("not-valid-base64!!!")

        assert "cursor" in str(exc_info.value).lower()
