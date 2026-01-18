"""Unit tests for PanelFindingService.

Story: consent-gov-6-5: Panel Finding Preservation

Tests verify:
- AC1: Findings recorded in append-only ledger (FR40)
- AC3: Dissent preserved alongside majority finding
- AC4: Event judicial.panel.finding_issued emitted
- AC5: Finding includes complete voting record
- AC6: Finding links to witness statement reviewed
- AC7: Historical findings queryable
- AC8: Unit tests for immutability

References:
    - FR40: System can record all panel findings in append-only ledger
    - NFR-CONST-06: Panel findings cannot be deleted or modified
    - FR39: Prince Panel can record dissent in finding
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.panel_finding_service import (
    DISSENT_RECORDED_EVENT,
    FINDING_ISSUED_EVENT,
    PanelFindingService,
    compute_finding_hash,
)
from src.domain.governance.panel import (
    Determination,
    Dissent,
    FindingRecord,
    PanelFinding,
    RemedyType,
)


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._time

    def advance(self, seconds: int) -> None:
        """Advance time by seconds."""
        self._time = self._time + timedelta(seconds=seconds)


class FakeEventEmitter:
    """Fake event emitter that captures events for testing."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )

    def get_last(self, event_type: str) -> dict | None:
        """Get last event of given type."""
        for event in reversed(self.events):
            if event["event_type"] == event_type:
                return event
        return None

    def count(self, event_type: str) -> int:
        """Count events of given type."""
        return sum(1 for e in self.events if e["event_type"] == event_type)


class FakePanelFindingAdapter:
    """In-memory fake implementation of PanelFindingPort for testing.

    Provides append-only semantics for testing purposes.
    """

    def __init__(self, time_authority: FakeTimeAuthority | None = None) -> None:
        self._records: dict[UUID, FindingRecord] = {}
        self._by_finding_id: dict[UUID, FindingRecord] = {}
        self._by_statement: dict[UUID, list[FindingRecord]] = {}
        self._by_panel: dict[UUID, list[FindingRecord]] = {}
        self._sequence = 0
        self._time = time_authority

    async def record_finding(
        self,
        finding: PanelFinding,
    ) -> FindingRecord:
        """Record a finding to the fake ledger."""
        self._sequence += 1
        recorded_at = self._time.now() if self._time else datetime.now(timezone.utc)
        record = FindingRecord(
            record_id=uuid4(),
            finding=finding,
            recorded_at=recorded_at,
            ledger_position=self._sequence,
            integrity_hash=compute_finding_hash(finding),
        )

        # Store by various keys
        self._records[record.record_id] = record
        self._by_finding_id[finding.finding_id] = record

        if finding.statement_id not in self._by_statement:
            self._by_statement[finding.statement_id] = []
        self._by_statement[finding.statement_id].append(record)

        if finding.panel_id not in self._by_panel:
            self._by_panel[finding.panel_id] = []
        self._by_panel[finding.panel_id].append(record)

        return record

    async def get_finding(
        self,
        finding_id: UUID,
    ) -> FindingRecord | None:
        return self._by_finding_id.get(finding_id)

    async def get_finding_by_record_id(
        self,
        record_id: UUID,
    ) -> FindingRecord | None:
        return self._records.get(record_id)

    async def get_findings_for_statement(
        self,
        statement_id: UUID,
    ) -> list[FindingRecord]:
        return self._by_statement.get(statement_id, [])

    async def get_findings_by_panel(
        self,
        panel_id: UUID,
    ) -> list[FindingRecord]:
        return self._by_panel.get(panel_id, [])

    async def get_findings_by_determination(
        self,
        determination: Determination,
        since: datetime | None = None,
    ) -> list[FindingRecord]:
        results = []
        for record in self._records.values():
            if record.determination == determination:
                if since is None or record.issued_at >= since:
                    results.append(record)
        return sorted(results, key=lambda r: r.issued_at)

    async def get_findings_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[FindingRecord]:
        results = []
        for record in self._records.values():
            if start <= record.recorded_at <= end:
                results.append(record)
        return sorted(results, key=lambda r: r.recorded_at)

    async def get_finding_by_position(
        self,
        position: int,
    ) -> FindingRecord | None:
        for record in self._records.values():
            if record.ledger_position == position:
                return record
        return None

    async def get_latest_finding(self) -> FindingRecord | None:
        if not self._records:
            return None
        return max(self._records.values(), key=lambda r: r.ledger_position)

    async def count_findings(
        self,
        determination: Determination | None = None,
        since: datetime | None = None,
    ) -> int:
        count = 0
        for record in self._records.values():
            if determination and record.determination != determination:
                continue
            if since and record.recorded_at < since:
                continue
            count += 1
        return count


# Test fixtures


def _create_finding(
    finding_id: UUID | None = None,
    panel_id: UUID | None = None,
    statement_id: UUID | None = None,
    determination: Determination = Determination.VIOLATION_FOUND,
    remedy: RemedyType | None = RemedyType.WARNING,
    dissent: Dissent | None = None,
) -> PanelFinding:
    """Create a test finding."""
    member1, member2, member3 = uuid4(), uuid4(), uuid4()
    return PanelFinding(
        finding_id=finding_id or uuid4(),
        panel_id=panel_id or uuid4(),
        statement_id=statement_id or uuid4(),
        determination=determination,
        remedy=remedy,
        majority_rationale="Test rationale for majority view.",
        dissent=dissent,
        issued_at=datetime.now(timezone.utc),
        voting_record={
            member1: "violation",
            member2: "violation",
            member3: "no_violation",
        },
    )


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    return FakeTimeAuthority()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    return FakeEventEmitter()


@pytest.fixture
def finding_port(time_authority: FakeTimeAuthority) -> FakePanelFindingAdapter:
    return FakePanelFindingAdapter(time_authority=time_authority)


@pytest.fixture
def service(
    finding_port: FakePanelFindingAdapter,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> PanelFindingService:
    return PanelFindingService(
        finding_port=finding_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


class TestPreserveFinding:
    """Tests for preserve_finding (AC1)."""

    @pytest.mark.asyncio
    async def test_preserve_finding_records_to_ledger(
        self,
        service: PanelFindingService,
        finding_port: FakePanelFindingAdapter,
    ) -> None:
        """Finding is recorded to the ledger (AC1, FR40)."""
        finding = _create_finding()

        record = await service.preserve_finding(finding)

        assert record.finding == finding
        assert record.ledger_position > 0
        assert record.integrity_hash != ""

        # Verify persisted
        retrieved = await finding_port.get_finding(finding.finding_id)
        assert retrieved is not None
        assert retrieved.finding_id == finding.finding_id

    @pytest.mark.asyncio
    async def test_preserve_finding_assigns_sequence(
        self,
        service: PanelFindingService,
    ) -> None:
        """Findings get monotonically increasing ledger positions."""
        finding1 = _create_finding()
        finding2 = _create_finding()

        record1 = await service.preserve_finding(finding1)
        record2 = await service.preserve_finding(finding2)

        assert record2.ledger_position > record1.ledger_position

    @pytest.mark.asyncio
    async def test_preserve_finding_computes_hash(
        self,
        service: PanelFindingService,
    ) -> None:
        """Finding gets integrity hash for verification."""
        finding = _create_finding()

        record = await service.preserve_finding(finding)

        expected_hash = compute_finding_hash(finding)
        assert record.integrity_hash == expected_hash


class TestDissentPreservation:
    """Tests for dissent preservation (AC3, FR39)."""

    @pytest.mark.asyncio
    async def test_dissent_preserved_with_finding(
        self,
        service: PanelFindingService,
    ) -> None:
        """Dissent is preserved with the finding (AC3, FR39)."""
        dissent = Dissent(
            dissenting_member_ids=[uuid4(), uuid4()],
            rationale="Strong disagreement with majority reasoning.",
        )
        finding = _create_finding(dissent=dissent)

        record = await service.preserve_finding(finding)

        assert record.finding.dissent is not None
        assert len(record.finding.dissent.dissenting_member_ids) == 2
        assert (
            record.finding.dissent.rationale
            == "Strong disagreement with majority reasoning."
        )

    @pytest.mark.asyncio
    async def test_has_dissent_property_true_when_dissent(
        self,
        service: PanelFindingService,
    ) -> None:
        """has_dissent property returns True when dissent exists."""
        dissent = Dissent(
            dissenting_member_ids=[uuid4()],
            rationale="Dissent.",
        )
        finding = _create_finding(dissent=dissent)

        record = await service.preserve_finding(finding)

        assert record.has_dissent is True

    @pytest.mark.asyncio
    async def test_has_dissent_property_false_when_no_dissent(
        self,
        service: PanelFindingService,
    ) -> None:
        """has_dissent property returns False when no dissent."""
        finding = _create_finding(dissent=None)

        record = await service.preserve_finding(finding)

        assert record.has_dissent is False

    @pytest.mark.asyncio
    async def test_get_findings_with_dissent(
        self,
        service: PanelFindingService,
    ) -> None:
        """Can query findings that have dissent."""
        finding_with_dissent = _create_finding(
            dissent=Dissent(
                dissenting_member_ids=[uuid4()],
                rationale="Disagree.",
            )
        )
        finding_without_dissent = _create_finding(dissent=None)

        await service.preserve_finding(finding_with_dissent)
        await service.preserve_finding(finding_without_dissent)

        dissent_findings = await service.get_findings_with_dissent()

        assert len(dissent_findings) == 1
        assert dissent_findings[0].has_dissent is True


class TestEventEmission:
    """Tests for event emission (AC4)."""

    @pytest.mark.asyncio
    async def test_finding_issued_event_emitted(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """judicial.panel.finding_issued event is emitted (AC4)."""
        finding = _create_finding()

        await service.preserve_finding(finding)

        event = event_emitter.get_last(FINDING_ISSUED_EVENT)
        assert event is not None
        assert event["event_type"] == FINDING_ISSUED_EVENT
        assert event["actor"] == "panel"

    @pytest.mark.asyncio
    async def test_finding_issued_event_contains_finding_id(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event contains finding_id."""
        finding = _create_finding()

        await service.preserve_finding(finding)

        event = event_emitter.get_last(FINDING_ISSUED_EVENT)
        assert event["payload"]["finding_id"] == str(finding.finding_id)

    @pytest.mark.asyncio
    async def test_finding_issued_event_contains_determination(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event contains determination."""
        finding = _create_finding(determination=Determination.NO_VIOLATION)

        await service.preserve_finding(finding)

        event = event_emitter.get_last(FINDING_ISSUED_EVENT)
        assert event["payload"]["determination"] == "no_violation"

    @pytest.mark.asyncio
    async def test_finding_issued_event_contains_remedy(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event contains remedy type."""
        finding = _create_finding(remedy=RemedyType.CORRECTION)

        await service.preserve_finding(finding)

        event = event_emitter.get_last(FINDING_ISSUED_EVENT)
        assert event["payload"]["remedy"] == "correction"

    @pytest.mark.asyncio
    async def test_finding_issued_event_contains_has_dissent_flag(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event contains has_dissent flag."""
        finding = _create_finding(
            dissent=Dissent(
                dissenting_member_ids=[uuid4()],
                rationale="Dissent.",
            )
        )

        await service.preserve_finding(finding)

        event = event_emitter.get_last(FINDING_ISSUED_EVENT)
        assert event["payload"]["has_dissent"] is True
        assert event["payload"]["dissenting_count"] == 1

    @pytest.mark.asyncio
    async def test_dissent_event_emitted_when_dissent_exists(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Separate dissent_recorded event emitted when dissent exists."""
        finding = _create_finding(
            dissent=Dissent(
                dissenting_member_ids=[uuid4(), uuid4()],
                rationale="Strong disagreement.",
            )
        )

        await service.preserve_finding(finding)

        event = event_emitter.get_last(DISSENT_RECORDED_EVENT)
        assert event is not None
        assert event["payload"]["dissenting_count"] == 2

    @pytest.mark.asyncio
    async def test_no_dissent_event_when_no_dissent(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """No dissent_recorded event when no dissent."""
        finding = _create_finding(dissent=None)

        await service.preserve_finding(finding)

        event = event_emitter.get_last(DISSENT_RECORDED_EVENT)
        assert event is None


class TestVotingRecordPreservation:
    """Tests for voting record preservation (AC5)."""

    @pytest.mark.asyncio
    async def test_voting_record_preserved(
        self,
        service: PanelFindingService,
    ) -> None:
        """Complete voting record is preserved (AC5)."""
        member1, member2, member3 = uuid4(), uuid4(), uuid4()
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.WARNING,
            majority_rationale="Test.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={
                member1: "violation",
                member2: "violation",
                member3: "no_violation",
            },
        )

        record = await service.preserve_finding(finding)

        assert len(record.finding.voting_record) == 3
        assert record.finding.voting_record[member1] == "violation"
        assert record.finding.voting_record[member2] == "violation"
        assert record.finding.voting_record[member3] == "no_violation"

    @pytest.mark.asyncio
    async def test_voting_record_count_in_event(
        self,
        service: PanelFindingService,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Event contains voting record count."""
        finding = _create_finding()

        await service.preserve_finding(finding)

        event = event_emitter.get_last(FINDING_ISSUED_EVENT)
        assert event["payload"]["voting_record_count"] == 3


class TestStatementLinkage:
    """Tests for statement linkage (AC6)."""

    @pytest.mark.asyncio
    async def test_finding_links_to_statement(
        self,
        service: PanelFindingService,
    ) -> None:
        """Finding references the witness statement (AC6)."""
        statement_id = uuid4()
        finding = _create_finding(statement_id=statement_id)

        record = await service.preserve_finding(finding)

        assert record.statement_id == statement_id

    @pytest.mark.asyncio
    async def test_get_findings_for_statement(
        self,
        service: PanelFindingService,
    ) -> None:
        """Can query findings by statement ID (AC6)."""
        statement_id = uuid4()
        finding1 = _create_finding(statement_id=statement_id)
        finding2 = _create_finding()  # Different statement

        await service.preserve_finding(finding1)
        await service.preserve_finding(finding2)

        findings = await service.get_findings_for_statement(statement_id)

        assert len(findings) == 1
        assert findings[0].statement_id == statement_id

    @pytest.mark.asyncio
    async def test_multiple_findings_for_statement(
        self,
        service: PanelFindingService,
    ) -> None:
        """Multiple findings can reference the same statement."""
        statement_id = uuid4()
        finding1 = _create_finding(statement_id=statement_id)
        finding2 = _create_finding(statement_id=statement_id)

        await service.preserve_finding(finding1)
        await service.preserve_finding(finding2)

        findings = await service.get_findings_for_statement(statement_id)

        assert len(findings) == 2


class TestHistoricalQuery:
    """Tests for historical query support (AC7)."""

    @pytest.mark.asyncio
    async def test_query_findings_by_date_range(
        self,
        service: PanelFindingService,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Can query findings by date range (AC7)."""
        finding1 = _create_finding()
        await service.preserve_finding(finding1)

        time_authority.advance(3600)  # 1 hour later
        finding2 = _create_finding()
        await service.preserve_finding(finding2)

        now = time_authority.now()
        start = now - timedelta(hours=2)
        end = now + timedelta(hours=1)

        findings = await service.get_findings_in_range(start, end)

        assert len(findings) == 2

    @pytest.mark.asyncio
    async def test_query_findings_by_determination(
        self,
        service: PanelFindingService,
    ) -> None:
        """Can query findings by determination type (AC7)."""
        violation_finding = _create_finding(determination=Determination.VIOLATION_FOUND)
        no_violation_finding = _create_finding(determination=Determination.NO_VIOLATION)

        await service.preserve_finding(violation_finding)
        await service.preserve_finding(no_violation_finding)

        violations = await service.get_findings_by_determination(
            Determination.VIOLATION_FOUND
        )
        no_violations = await service.get_findings_by_determination(
            Determination.NO_VIOLATION
        )

        assert len(violations) == 1
        assert len(no_violations) == 1
        assert violations[0].determination == Determination.VIOLATION_FOUND

    @pytest.mark.asyncio
    async def test_query_findings_by_panel(
        self,
        service: PanelFindingService,
    ) -> None:
        """Can query findings by panel (AC7)."""
        panel_id = uuid4()
        finding1 = _create_finding(panel_id=panel_id)
        finding2 = _create_finding()  # Different panel

        await service.preserve_finding(finding1)
        await service.preserve_finding(finding2)

        findings = await service.get_findings_by_panel(panel_id)

        assert len(findings) == 1
        assert findings[0].panel_id == panel_id

    @pytest.mark.asyncio
    async def test_count_findings(
        self,
        service: PanelFindingService,
    ) -> None:
        """Can count findings."""
        await service.preserve_finding(
            _create_finding(determination=Determination.VIOLATION_FOUND)
        )
        await service.preserve_finding(
            _create_finding(determination=Determination.VIOLATION_FOUND)
        )
        await service.preserve_finding(
            _create_finding(determination=Determination.NO_VIOLATION)
        )

        total = await service.count_findings()
        violations = await service.count_findings(
            determination=Determination.VIOLATION_FOUND
        )

        assert total == 3
        assert violations == 2

    @pytest.mark.asyncio
    async def test_get_latest_finding(
        self,
        service: PanelFindingService,
    ) -> None:
        """Can get the latest finding."""
        finding1 = _create_finding()
        finding2 = _create_finding()

        await service.preserve_finding(finding1)
        record2 = await service.preserve_finding(finding2)

        latest = await service.get_latest_finding()

        assert latest is not None
        assert latest.finding_id == record2.finding_id


class TestComputeFindingHash:
    """Tests for the hash computation utility."""

    def test_same_finding_same_hash(self) -> None:
        """Same finding produces same hash."""
        finding = _create_finding()

        hash1 = compute_finding_hash(finding)
        hash2 = compute_finding_hash(finding)

        assert hash1 == hash2

    def test_different_finding_different_hash(self) -> None:
        """Different findings produce different hashes."""
        finding1 = _create_finding()
        finding2 = _create_finding()

        hash1 = compute_finding_hash(finding1)
        hash2 = compute_finding_hash(finding2)

        assert hash1 != hash2

    def test_hash_includes_dissent(self) -> None:
        """Hash changes when dissent is added."""
        finding_without = _create_finding(dissent=None)
        finding_with = PanelFinding(
            finding_id=finding_without.finding_id,
            panel_id=finding_without.panel_id,
            statement_id=finding_without.statement_id,
            determination=finding_without.determination,
            remedy=finding_without.remedy,
            majority_rationale=finding_without.majority_rationale,
            dissent=Dissent(
                dissenting_member_ids=[uuid4()],
                rationale="Dissent.",
            ),
            issued_at=finding_without.issued_at,
            voting_record=finding_without.voting_record,
        )

        hash_without = compute_finding_hash(finding_without)
        hash_with = compute_finding_hash(finding_with)

        assert hash_without != hash_with

    def test_hash_is_hex_string(self) -> None:
        """Hash is a hex-encoded string."""
        finding = _create_finding()

        hash_value = compute_finding_hash(finding)

        # SHA-256 produces 64 hex characters
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)
