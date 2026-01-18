"""Unit tests for complexity budget events (Story 8.6, SC-3, RT-6).

Tests for ComplexityBudgetBreachedPayload and ComplexityBudgetEscalatedPayload.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.complexity_budget import (
    COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE,
    COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE,
    COMPLEXITY_SYSTEM_AGENT_ID,
    ComplexityBudgetBreachedPayload,
    ComplexityBudgetEscalatedPayload,
)
from src.domain.models.complexity_budget import ComplexityDimension


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_breached_event_type(self) -> None:
        """Test breach event type constant."""
        assert COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE == "complexity.budget.breached"

    def test_escalated_event_type(self) -> None:
        """Test escalation event type constant."""
        assert COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE == "complexity.budget.escalated"

    def test_system_agent_id(self) -> None:
        """Test system agent ID constant."""
        assert COMPLEXITY_SYSTEM_AGENT_ID == "system.complexity_monitor"


class TestComplexityBudgetBreachedPayload:
    """Tests for ComplexityBudgetBreachedPayload."""

    def test_create_breach_payload(self) -> None:
        """Test creating a breach payload."""
        breach_id = uuid4()
        now = datetime.now(timezone.utc)
        payload = ComplexityBudgetBreachedPayload(
            breach_id=breach_id,
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=17,
            breached_at=now,
        )
        assert payload.breach_id == breach_id
        assert payload.dimension == ComplexityDimension.ADR_COUNT
        assert payload.limit == 15
        assert payload.actual_value == 17
        assert payload.breached_at == now

    def test_requires_governance_ceremony_default(self) -> None:
        """Test requires_governance_ceremony defaults to True (RT-6)."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        assert payload.requires_governance_ceremony is True

    def test_is_resolved_when_resolved(self) -> None:
        """Test is_resolved property when resolved."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
            resolved_at=datetime.now(timezone.utc),
        )
        assert payload.is_resolved is True

    def test_is_resolved_when_not_resolved(self) -> None:
        """Test is_resolved property when not resolved."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        assert payload.is_resolved is False

    def test_overage_calculation(self) -> None:
        """Test overage calculation."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=18,
            breached_at=datetime.now(timezone.utc),
        )
        assert payload.overage == 3

    def test_overage_zero_when_under_limit(self) -> None:
        """Test overage is zero when under limit."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=14,
            breached_at=datetime.now(timezone.utc),
        )
        assert payload.overage == 0

    def test_overage_percent(self) -> None:
        """Test overage percent calculation."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=10,
            actual_value=12,
            breached_at=datetime.now(timezone.utc),
        )
        assert payload.overage_percent == 20.0

    def test_signable_content_is_bytes(self) -> None:
        """Test signable_content returns bytes."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_deterministic(self) -> None:
        """Test signable_content is deterministic for same values."""
        breach_id = uuid4()
        now = datetime.now(timezone.utc)

        payload1 = ComplexityBudgetBreachedPayload(
            breach_id=breach_id,
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=now,
        )
        payload2 = ComplexityBudgetBreachedPayload(
            breach_id=breach_id,
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=now,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_parseable_json(self) -> None:
        """Test signable_content produces valid JSON."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert "breach_id" in parsed
        assert "dimension" in parsed
        assert parsed["dimension"] == "adr_count"

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        breach_id = uuid4()
        now = datetime.now(timezone.utc)
        payload = ComplexityBudgetBreachedPayload(
            breach_id=breach_id,
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=now,
        )
        d = payload.to_dict()
        assert d["breach_id"] == str(breach_id)
        assert d["dimension"] == "adr_count"
        assert d["limit"] == 15
        assert d["actual_value"] == 16

    def test_to_dict_with_optional_fields(self) -> None:
        """Test to_dict includes optional fields when present."""
        governance_id = uuid4()
        deadline = datetime.now(timezone.utc)
        resolved = datetime.now(timezone.utc)

        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
            resolution_deadline=deadline,
            governance_approval_id=governance_id,
            resolved_at=resolved,
        )
        d = payload.to_dict()
        assert "resolution_deadline" in d
        assert "governance_approval_id" in d
        assert d["governance_approval_id"] == str(governance_id)
        assert "resolved_at" in d

    def test_payload_is_frozen(self) -> None:
        """Test that payload is immutable."""
        payload = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            payload.actual_value = 20  # type: ignore[misc]


class TestComplexityBudgetEscalatedPayload:
    """Tests for ComplexityBudgetEscalatedPayload."""

    def test_create_escalation_payload(self) -> None:
        """Test creating an escalation payload."""
        escalation_id = uuid4()
        breach_id = uuid4()
        now = datetime.now(timezone.utc)
        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=escalation_id,
            breach_id=breach_id,
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=now,
            escalated_at=now,
            days_without_resolution=8,
        )
        assert payload.escalation_id == escalation_id
        assert payload.breach_id == breach_id
        assert payload.days_without_resolution == 8

    def test_default_escalation_level(self) -> None:
        """Test escalation_level defaults to 1."""
        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=datetime.now(timezone.utc),
            escalated_at=datetime.now(timezone.utc),
            days_without_resolution=8,
        )
        assert payload.escalation_level == 1

    def test_default_requires_immediate_action(self) -> None:
        """Test requires_immediate_action defaults to False."""
        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=datetime.now(timezone.utc),
            escalated_at=datetime.now(timezone.utc),
            days_without_resolution=8,
        )
        assert payload.requires_immediate_action is False

    def test_negative_days_raises_error(self) -> None:
        """Test negative days_without_resolution raises ValueError."""
        with pytest.raises(
            ValueError, match="days_without_resolution cannot be negative"
        ):
            ComplexityBudgetEscalatedPayload(
                escalation_id=uuid4(),
                breach_id=uuid4(),
                dimension=ComplexityDimension.ADR_COUNT,
                original_breach_at=datetime.now(timezone.utc),
                escalated_at=datetime.now(timezone.utc),
                days_without_resolution=-1,
            )

    def test_zero_escalation_level_raises_error(self) -> None:
        """Test escalation_level < 1 raises ValueError."""
        with pytest.raises(ValueError, match="escalation_level must be at least 1"):
            ComplexityBudgetEscalatedPayload(
                escalation_id=uuid4(),
                breach_id=uuid4(),
                dimension=ComplexityDimension.ADR_COUNT,
                original_breach_at=datetime.now(timezone.utc),
                escalated_at=datetime.now(timezone.utc),
                days_without_resolution=8,
                escalation_level=0,
            )

    def test_signable_content_is_bytes(self) -> None:
        """Test signable_content returns bytes."""
        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=datetime.now(timezone.utc),
            escalated_at=datetime.now(timezone.utc),
            days_without_resolution=8,
        )
        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_deterministic(self) -> None:
        """Test signable_content is deterministic for same values."""
        escalation_id = uuid4()
        breach_id = uuid4()
        original = datetime.now(timezone.utc)
        escalated = datetime.now(timezone.utc)

        payload1 = ComplexityBudgetEscalatedPayload(
            escalation_id=escalation_id,
            breach_id=breach_id,
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=original,
            escalated_at=escalated,
            days_without_resolution=8,
        )
        payload2 = ComplexityBudgetEscalatedPayload(
            escalation_id=escalation_id,
            breach_id=breach_id,
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=original,
            escalated_at=escalated,
            days_without_resolution=8,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_parseable_json(self) -> None:
        """Test signable_content produces valid JSON."""
        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=datetime.now(timezone.utc),
            escalated_at=datetime.now(timezone.utc),
            days_without_resolution=8,
        )
        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert "escalation_id" in parsed
        assert "breach_id" in parsed
        assert parsed["days_without_resolution"] == 8

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        escalation_id = uuid4()
        breach_id = uuid4()
        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=escalation_id,
            breach_id=breach_id,
            dimension=ComplexityDimension.CEREMONY_TYPES,
            original_breach_at=datetime.now(timezone.utc),
            escalated_at=datetime.now(timezone.utc),
            days_without_resolution=10,
            escalation_level=2,
            requires_immediate_action=True,
        )
        d = payload.to_dict()
        assert d["escalation_id"] == str(escalation_id)
        assert d["breach_id"] == str(breach_id)
        assert d["dimension"] == "ceremony_types"
        assert d["days_without_resolution"] == 10
        assert d["escalation_level"] == 2
        assert d["requires_immediate_action"] is True

    def test_payload_is_frozen(self) -> None:
        """Test that payload is immutable."""
        payload = ComplexityBudgetEscalatedPayload(
            escalation_id=uuid4(),
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            original_breach_at=datetime.now(timezone.utc),
            escalated_at=datetime.now(timezone.utc),
            days_without_resolution=8,
        )
        with pytest.raises(AttributeError):
            payload.days_without_resolution = 10  # type: ignore[misc]
