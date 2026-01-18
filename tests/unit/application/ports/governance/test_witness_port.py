"""Unit tests for witness port interface.

Story: consent-gov-6-1: Knight Witness Domain Model

Tests the WitnessPort interface which enforces suppression prevention
by design (no delete or modify methods exist).

References:
    - FR33: Knight can observe all branch actions
    - NFR-CONST-07: Witness statements cannot be suppressed by any role
    - AC4: Statements cannot be suppressed by any role
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.witness_port import WitnessPort
from src.domain.governance.witness.observation_content import ObservationContent
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement


class TestWitnessPortSuppressionPrevention:
    """Tests that WitnessPort enforces suppression prevention by design."""

    def test_port_has_no_delete_method(self) -> None:
        """Port interface has no delete method (AC4: suppression prevention)."""
        # WitnessPort should NOT have delete_statement method
        assert not hasattr(WitnessPort, "delete_statement")

    def test_port_has_no_modify_method(self) -> None:
        """Port interface has no modify method (AC4: immutability)."""
        # WitnessPort should NOT have modify_statement method
        assert not hasattr(WitnessPort, "modify_statement")

    def test_port_has_no_update_method(self) -> None:
        """Port interface has no update method (AC4: immutability)."""
        assert not hasattr(WitnessPort, "update_statement")

    def test_port_has_no_remove_method(self) -> None:
        """Port interface has no remove method (AC4: suppression prevention)."""
        assert not hasattr(WitnessPort, "remove_statement")

    def test_port_has_record_statement_method(self) -> None:
        """Port has record_statement for append-only writes."""
        assert hasattr(WitnessPort, "record_statement")

    def test_port_has_get_statements_for_event_method(self) -> None:
        """Port has get_statements_for_event for reads."""
        assert hasattr(WitnessPort, "get_statements_for_event")

    def test_port_has_get_statements_by_type_method(self) -> None:
        """Port has get_statements_by_type for filtered reads."""
        assert hasattr(WitnessPort, "get_statements_by_type")

    def test_port_has_get_statement_chain_method(self) -> None:
        """Port has get_statement_chain for gap detection reads."""
        assert hasattr(WitnessPort, "get_statement_chain")


class TestWitnessPortProtocol:
    """Tests that WitnessPort is properly defined as a Protocol."""

    def test_port_is_runtime_checkable(self) -> None:
        """WitnessPort can be used with isinstance checks."""
        # Protocol should be decorated with @runtime_checkable
        # This enables isinstance() checks at runtime
        assert hasattr(WitnessPort, "__protocol_attrs__") or hasattr(
            WitnessPort, "_is_runtime_protocol"
        )


def create_test_statement(
    statement_id: UUID | None = None,
    observation_type: ObservationType = ObservationType.BRANCH_ACTION,
) -> WitnessStatement:
    """Helper to create a test statement."""
    return WitnessStatement(
        statement_id=statement_id or uuid4(),
        observation_type=observation_type,
        content=ObservationContent(
            what="Task state changed",
            when=datetime.now(timezone.utc),
            who=("actor-uuid-1",),
            where="executive",
            event_type="executive.task.activated",
            event_id=uuid4(),
        ),
        observed_at=datetime.now(timezone.utc),
        hash_chain_position=1,
    )


class InMemoryWitnessAdapter:
    """In-memory adapter for testing WitnessPort compliance."""

    def __init__(self) -> None:
        self._statements: list[WitnessStatement] = []

    async def record_statement(self, statement: WitnessStatement) -> None:
        """Record witness statement to append-only store."""
        self._statements.append(statement)

    async def get_statements_for_event(self, event_id: UUID) -> list[WitnessStatement]:
        """Get all witness statements for an event."""
        return [s for s in self._statements if s.content.event_id == event_id]

    async def get_statements_by_type(
        self,
        observation_type: ObservationType,
        since: datetime | None = None,
    ) -> list[WitnessStatement]:
        """Get statements by observation type."""
        result = [s for s in self._statements if s.observation_type == observation_type]
        if since:
            result = [s for s in result if s.observed_at >= since]
        return result

    async def get_statement_chain(
        self,
        start_position: int,
        end_position: int,
    ) -> list[WitnessStatement]:
        """Get statements by chain position for gap detection."""
        return [
            s
            for s in self._statements
            if start_position <= s.hash_chain_position <= end_position
        ]


class TestInMemoryWitnessAdapter:
    """Tests for the in-memory witness adapter (demonstrates WitnessPort usage)."""

    @pytest.fixture
    def adapter(self) -> InMemoryWitnessAdapter:
        """Create in-memory adapter."""
        return InMemoryWitnessAdapter()

    @pytest.mark.asyncio
    async def test_record_statement_persists(
        self,
        adapter: InMemoryWitnessAdapter,
    ) -> None:
        """Recorded statements are persisted (AC: append-only)."""
        event_id = uuid4()
        statement = WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.BRANCH_ACTION,
            content=ObservationContent(
                what="Task state changed",
                when=datetime.now(timezone.utc),
                who=("actor-uuid-1",),
                where="executive",
                event_type="executive.task.activated",
                event_id=event_id,
            ),
            observed_at=datetime.now(timezone.utc),
            hash_chain_position=1,
        )

        await adapter.record_statement(statement)

        retrieved = await adapter.get_statements_for_event(event_id)
        assert statement in retrieved

    @pytest.mark.asyncio
    async def test_get_statements_by_type(
        self,
        adapter: InMemoryWitnessAdapter,
    ) -> None:
        """Can filter statements by observation type."""
        statement1 = create_test_statement(
            observation_type=ObservationType.BRANCH_ACTION
        )
        statement2 = create_test_statement(
            observation_type=ObservationType.POTENTIAL_VIOLATION
        )

        await adapter.record_statement(statement1)
        await adapter.record_statement(statement2)

        violations = await adapter.get_statements_by_type(
            ObservationType.POTENTIAL_VIOLATION
        )
        assert len(violations) == 1
        assert violations[0] == statement2

    @pytest.mark.asyncio
    async def test_get_statement_chain_for_gap_detection(
        self,
        adapter: InMemoryWitnessAdapter,
    ) -> None:
        """Can retrieve statement chain for gap detection."""
        # Create statements with sequential positions
        for i in range(1, 6):
            statement = WitnessStatement(
                statement_id=uuid4(),
                observation_type=ObservationType.BRANCH_ACTION,
                content=ObservationContent(
                    what=f"Observation {i}",
                    when=datetime.now(timezone.utc),
                    who=("actor-uuid-1",),
                    where="executive",
                    event_type="executive.task.activated",
                    event_id=uuid4(),
                ),
                observed_at=datetime.now(timezone.utc),
                hash_chain_position=i,
            )
            await adapter.record_statement(statement)

        # Get statements from positions 2 to 4
        chain = await adapter.get_statement_chain(2, 4)
        assert len(chain) == 3
        positions = [s.hash_chain_position for s in chain]
        assert 2 in positions
        assert 3 in positions
        assert 4 in positions

    @pytest.mark.asyncio
    async def test_adapter_has_no_delete_method(
        self,
        adapter: InMemoryWitnessAdapter,
    ) -> None:
        """Adapter has no delete method (suppression prevention)."""
        assert not hasattr(adapter, "delete_statement")

    @pytest.mark.asyncio
    async def test_adapter_has_no_modify_method(
        self,
        adapter: InMemoryWitnessAdapter,
    ) -> None:
        """Adapter has no modify method (immutability)."""
        assert not hasattr(adapter, "modify_statement")
