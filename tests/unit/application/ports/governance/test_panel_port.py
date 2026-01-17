"""Unit tests for PanelPort interface.

Story: consent-gov-6-4: Prince Panel Domain Model

Tests verify the port interface contract using a mock adapter.
The port is a Protocol, so we test that implementations comply
with the expected interface.

References:
    - AC2: Human Operator convenes panel
    - AC4: Panel can issue formal finding with remedy
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from src.domain.governance.panel import (
    PrincePanel,
    PanelStatus,
    PanelMember,
    MemberStatus,
    PanelFinding,
    Determination,
    RemedyType,
    RecusalRequest,
    ReviewSession,
)
from src.application.ports.governance.panel_port import PanelPort


class MockPanelAdapter:
    """In-memory mock implementation of PanelPort for testing."""

    def __init__(self) -> None:
        self._panels: Dict[UUID, PrincePanel] = {}
        self._findings: Dict[UUID, PanelFinding] = {}
        self._recusals: Dict[UUID, List[RecusalRequest]] = {}
        self._sessions: Dict[UUID, ReviewSession] = {}

    async def save_panel(self, panel: PrincePanel) -> None:
        """Save or update a panel."""
        self._panels[panel.panel_id] = panel

    async def get_panel(self, panel_id: UUID) -> Optional[PrincePanel]:
        """Get a panel by ID."""
        return self._panels.get(panel_id)

    async def get_panel_by_statement(
        self, statement_id: UUID
    ) -> Optional[PrincePanel]:
        """Get the panel reviewing a specific statement."""
        for panel in self._panels.values():
            if panel.statement_under_review == statement_id:
                return panel
        return None

    async def list_panels_by_status(
        self, status: str, limit: int = 100
    ) -> List[PrincePanel]:
        """List panels by status."""
        result = [
            p for p in self._panels.values()
            if p.status.value == status
        ]
        return result[:limit]

    async def save_finding(self, finding: PanelFinding) -> None:
        """Save a panel finding."""
        self._findings[finding.finding_id] = finding

    async def get_finding(self, finding_id: UUID) -> Optional[PanelFinding]:
        """Get a finding by ID."""
        return self._findings.get(finding_id)

    async def get_finding_by_panel(
        self, panel_id: UUID
    ) -> Optional[PanelFinding]:
        """Get the finding issued by a specific panel."""
        for finding in self._findings.values():
            if finding.panel_id == panel_id:
                return finding
        return None

    async def save_recusal(self, recusal: RecusalRequest) -> None:
        """Save a recusal request."""
        panel_id = recusal.panel_id
        if panel_id not in self._recusals:
            self._recusals[panel_id] = []
        self._recusals[panel_id].append(recusal)

    async def list_recusals_by_panel(
        self, panel_id: UUID
    ) -> List[RecusalRequest]:
        """List all recusals for a panel."""
        return self._recusals.get(panel_id, [])

    async def save_review_session(self, session: ReviewSession) -> None:
        """Save a review session."""
        self._sessions[session.session_id] = session

    async def get_review_session(
        self, session_id: UUID
    ) -> Optional[ReviewSession]:
        """Get a review session by ID."""
        return self._sessions.get(session_id)

    async def get_active_session_for_panel(
        self, panel_id: UUID
    ) -> Optional[ReviewSession]:
        """Get the active review session for a panel."""
        for session in self._sessions.values():
            if session.panel_id == panel_id and session.is_active:
                return session
        return None


def _create_active_member() -> PanelMember:
    """Helper to create an active panel member."""
    return PanelMember(
        member_id=uuid4(),
        joined_at=datetime.now(timezone.utc),
        status=MemberStatus.ACTIVE,
        recusal_reason=None,
    )


def _create_panel(
    panel_id: Optional[UUID] = None,
    status: PanelStatus = PanelStatus.CONVENED,
) -> PrincePanel:
    """Helper to create a panel."""
    return PrincePanel(
        panel_id=panel_id or uuid4(),
        convened_by=uuid4(),
        members=tuple(_create_active_member() for _ in range(3)),
        statement_under_review=uuid4(),
        status=status,
        convened_at=datetime.now(timezone.utc),
        finding=None,
    )


class TestMockPanelAdapterCompliesToProtocol:
    """Verify MockPanelAdapter complies with PanelPort protocol."""

    def test_mock_adapter_is_panel_port(self) -> None:
        """MockPanelAdapter implements PanelPort protocol."""
        adapter = MockPanelAdapter()
        # Protocol compliance check via isinstance would require runtime_checkable
        # Instead we verify all methods exist
        assert hasattr(adapter, "save_panel")
        assert hasattr(adapter, "get_panel")
        assert hasattr(adapter, "get_panel_by_statement")
        assert hasattr(adapter, "list_panels_by_status")
        assert hasattr(adapter, "save_finding")
        assert hasattr(adapter, "get_finding")
        assert hasattr(adapter, "get_finding_by_panel")
        assert hasattr(adapter, "save_recusal")
        assert hasattr(adapter, "list_recusals_by_panel")
        assert hasattr(adapter, "save_review_session")
        assert hasattr(adapter, "get_review_session")
        assert hasattr(adapter, "get_active_session_for_panel")


class TestPanelLifecycleOperations:
    """Tests for panel lifecycle operations via port."""

    @pytest.fixture
    def port(self) -> MockPanelAdapter:
        """Create a mock panel port."""
        return MockPanelAdapter()

    @pytest.mark.asyncio
    async def test_save_and_get_panel(self, port: MockPanelAdapter) -> None:
        """Can save and retrieve a panel."""
        panel = _create_panel()

        await port.save_panel(panel)
        retrieved = await port.get_panel(panel.panel_id)

        assert retrieved is not None
        assert retrieved.panel_id == panel.panel_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_panel_returns_none(
        self, port: MockPanelAdapter
    ) -> None:
        """Getting nonexistent panel returns None."""
        result = await port.get_panel(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_panel_by_statement(self, port: MockPanelAdapter) -> None:
        """Can get panel by statement being reviewed."""
        statement_id = uuid4()
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(_create_active_member() for _ in range(3)),
            statement_under_review=statement_id,
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        await port.save_panel(panel)
        retrieved = await port.get_panel_by_statement(statement_id)

        assert retrieved is not None
        assert retrieved.statement_under_review == statement_id

    @pytest.mark.asyncio
    async def test_list_panels_by_status(self, port: MockPanelAdapter) -> None:
        """Can list panels by status."""
        panel1 = _create_panel(status=PanelStatus.CONVENED)
        panel2 = _create_panel(status=PanelStatus.REVIEWING)
        panel3 = _create_panel(status=PanelStatus.CONVENED)

        await port.save_panel(panel1)
        await port.save_panel(panel2)
        await port.save_panel(panel3)

        convened = await port.list_panels_by_status("convened")
        reviewing = await port.list_panels_by_status("reviewing")

        assert len(convened) == 2
        assert len(reviewing) == 1

    @pytest.mark.asyncio
    async def test_list_panels_respects_limit(
        self, port: MockPanelAdapter
    ) -> None:
        """List panels respects limit parameter."""
        for _ in range(5):
            await port.save_panel(_create_panel(status=PanelStatus.CONVENED))

        result = await port.list_panels_by_status("convened", limit=3)
        assert len(result) == 3


class TestFindingOperations:
    """Tests for finding operations via port."""

    @pytest.fixture
    def port(self) -> MockPanelAdapter:
        """Create a mock panel port."""
        return MockPanelAdapter()

    @pytest.mark.asyncio
    async def test_save_and_get_finding(self, port: MockPanelAdapter) -> None:
        """Can save and retrieve a finding."""
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.WARNING,
            majority_rationale="Test rationale.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={},
        )

        await port.save_finding(finding)
        retrieved = await port.get_finding(finding.finding_id)

        assert retrieved is not None
        assert retrieved.finding_id == finding.finding_id
        assert retrieved.determination == Determination.VIOLATION_FOUND

    @pytest.mark.asyncio
    async def test_get_finding_by_panel(self, port: MockPanelAdapter) -> None:
        """Can get finding by panel ID."""
        panel_id = uuid4()
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=panel_id,
            statement_id=uuid4(),
            determination=Determination.NO_VIOLATION,
            remedy=None,
            majority_rationale="No violation found.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={},
        )

        await port.save_finding(finding)
        retrieved = await port.get_finding_by_panel(panel_id)

        assert retrieved is not None
        assert retrieved.panel_id == panel_id


class TestRecusalOperations:
    """Tests for recusal operations via port."""

    @pytest.fixture
    def port(self) -> MockPanelAdapter:
        """Create a mock panel port."""
        return MockPanelAdapter()

    @pytest.mark.asyncio
    async def test_save_and_list_recusals(self, port: MockPanelAdapter) -> None:
        """Can save and list recusals for a panel."""
        panel_id = uuid4()
        recusal1 = RecusalRequest(
            request_id=uuid4(),
            panel_id=panel_id,
            member_id=uuid4(),
            reason="Prior involvement.",
            requested_at=datetime.now(timezone.utc),
        )
        recusal2 = RecusalRequest(
            request_id=uuid4(),
            panel_id=panel_id,
            member_id=uuid4(),
            reason="Financial interest.",
            requested_at=datetime.now(timezone.utc),
        )

        await port.save_recusal(recusal1)
        await port.save_recusal(recusal2)

        recusals = await port.list_recusals_by_panel(panel_id)

        assert len(recusals) == 2

    @pytest.mark.asyncio
    async def test_list_recusals_empty_for_new_panel(
        self, port: MockPanelAdapter
    ) -> None:
        """List recusals returns empty for panel with no recusals."""
        recusals = await port.list_recusals_by_panel(uuid4())
        assert recusals == []


class TestReviewSessionOperations:
    """Tests for review session operations via port."""

    @pytest.fixture
    def port(self) -> MockPanelAdapter:
        """Create a mock panel port."""
        return MockPanelAdapter()

    @pytest.mark.asyncio
    async def test_save_and_get_session(self, port: MockPanelAdapter) -> None:
        """Can save and retrieve a review session."""
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            reviewed_artifacts=[],
            notes=None,
        )

        await port.save_review_session(session)
        retrieved = await port.get_review_session(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_get_active_session_for_panel(
        self, port: MockPanelAdapter
    ) -> None:
        """Can get active session for a panel."""
        panel_id = uuid4()
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=panel_id,
            statement_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=None,  # Active session
            reviewed_artifacts=[],
            notes=None,
        )

        await port.save_review_session(session)
        active = await port.get_active_session_for_panel(panel_id)

        assert active is not None
        assert active.is_active is True

    @pytest.mark.asyncio
    async def test_no_active_session_when_ended(
        self, port: MockPanelAdapter
    ) -> None:
        """No active session returned when session has ended."""
        panel_id = uuid4()
        now = datetime.now(timezone.utc)
        session = ReviewSession(
            session_id=uuid4(),
            panel_id=panel_id,
            statement_id=uuid4(),
            started_at=now,
            ended_at=now,  # Ended session
            reviewed_artifacts=[],
            notes=None,
        )

        await port.save_review_session(session)
        active = await port.get_active_session_for_panel(panel_id)

        assert active is None
